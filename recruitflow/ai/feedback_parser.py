from __future__ import annotations

import re

from recruitflow.core.models import FeedbackParseResult
from recruitflow.core.state_machine import stage_for_feedback_intent

from .client import ai_json
from .prompts import FEEDBACK_SYSTEM_PROMPT


SCHEMA_HINT = """
{
  "candidate_name": "string|null",
  "job_name": "string|null",
  "intent": "可以约面|不合适|进入复试|通过|发Offer|候选人放弃|待补充|未知",
  "next_stage": "待二审|初试待安排|初试待反馈|复试待安排|复试待反馈|终试待安排|Offer审批|Offer已发|待入职|已入职|不合适|候选人放弃|null",
  "suggested_time": "string|null",
  "reason": "string|null",
  "invitation_message": "string|null",
  "confidence": 0.0
}
"""


INTENT_RULES: list[tuple[str, list[str], float, str]] = [
    ("候选人放弃", [r"候选人放弃", r"不考虑了", r"暂不考虑机会", r"退出流程", r"declin(?:e|ed)", r"withdraw"], 0.9, "候选人明确表示放弃或退出流程"),
    ("不合适", [r"不合适", r"不通过", r"淘汰", r"拒绝", r"pass\s+on", r"reject"], 0.9, "反馈明确表示不继续推进"),
    ("发Offer", [r"发\s*offer", r"offer", r"录用", r"薪资审批"], 0.88, "反馈建议进入 Offer 流程"),
    ("进入复试", [r"进入复试", r"安排复试", r"下一轮", r"二面", r"终面"], 0.84, "反馈建议进入下一轮面试"),
    ("可以约面", [r"可以约面", r"约面", r"安排面试", r"约.*面试", r"schedule"], 0.82, "反馈建议安排面试"),
    ("通过", [r"通过", r"推进", r"继续推进", r"建议推进"], 0.78, "反馈倾向继续推进"),
    ("待补充", [r"待定", r"再看看", r"补充", r"hold", r"pending"], 0.62, "反馈信息不足，需要补充确认"),
]

NEXT_STAGE_BY_INTENT = {
    "不合适": "不合适",
    "候选人放弃": "候选人放弃",
    "进入复试": "复试待安排",
    "发Offer": "Offer审批",
}


def parse_feedback(text: str) -> FeedbackParseResult:
    payload = ai_json(FEEDBACK_SYSTEM_PROMPT, text, SCHEMA_HINT)
    if payload:
        return FeedbackParseResult.model_validate(payload)
    return mock_parse_feedback(text)


def mock_parse_feedback(text: str) -> FeedbackParseResult:
    normalized = _normalize_text(text)
    name = extract_candidate_name(normalized)
    job_name = extract_job_name(normalized)
    intent, base_confidence, default_reason = infer_feedback_intent(normalized)
    next_stage = NEXT_STAGE_BY_INTENT.get(intent)
    if intent in {"可以约面", "通过"}:
        next_stage = stage_for_feedback_intent(intent, "待二审")
    if intent in {"待补充", "未知"}:
        next_stage = None

    time_hint = extract_suggested_time(normalized)
    reason = extract_reason(normalized) or default_reason
    confidence = max(0.25, min(0.96, base_confidence - (0 if name else 0.12) - (0 if job_name else 0.06)))
    invitation = build_invitation_message(name, intent, time_hint)

    return FeedbackParseResult(
        candidate_name=name,
        job_name=job_name,
        intent=intent,  # type: ignore[arg-type]
        next_stage=next_stage,  # type: ignore[arg-type]
        suggested_time=time_hint,
        reason=reason,
        invitation_message=invitation,
        confidence=confidence,
    )


def infer_feedback_intent(text: str) -> tuple[str, float, str | None]:
    lowered = text.lower()
    for intent, patterns, confidence, reason in INTENT_RULES:
        if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns):
            return intent, confidence, reason
    return "未知", 0.42, "未识别出明确的招聘动作"


def extract_candidate_name(text: str) -> str | None:
    return _first_match(
        text,
        [
            r"候选人[:：]\s*([^\s,，。；;|｜]{2,12})",
            r"姓名[:：]\s*([^\s,，。；;|｜]{2,12})",
            r"关于\s*([\u4e00-\u9fa5]{2,6})\s*(?:的)?(?:面试|反馈|候选人)",
            r"([\u4e00-\u9fa5]{2,4})(?:可以|不合适|进入|通过|约面|复试|发\s*Offer|放弃)",
        ],
    )


def extract_job_name(text: str) -> str | None:
    return _first_match(
        text,
        [
            r"岗位[:：]\s*([^\n\r,，。；;|｜]{2,30})",
            r"职位[:：]\s*([^\n\r,，。；;|｜]{2,30})",
            r"面试\s*([^\n\r,，。；;|｜]{2,30})\s*岗位",
        ],
    )


def extract_suggested_time(text: str) -> str | None:
    return _first_match(
        text,
        [
            r"((?:今天|明天|后天|本周|下周|周[一二三四五六日天]|[0-9]{1,2}[/-][0-9]{1,2}).{0,12}(?:上午|下午|晚上|点|:[0-9]{2})?)",
        ],
    )


def extract_reason(text: str) -> str | None:
    return _first_match(
        text,
        [
            r"(?:原因|理由|反馈|评价)[:：]\s*([^\n\r]{4,120})",
            r"(?:因为|由于)([^\n\r。；;]{4,80})",
        ],
    )


def build_invitation_message(name: str | None, intent: str, time_hint: str | None) -> str | None:
    if intent not in {"可以约面", "进入复试", "通过"}:
        return None
    display_name = name or "候选人"
    time_text = time_hint or "待HR确认"
    return f"{display_name}您好，面试反馈已收到，想和您确认后续面试安排，建议时间为：{time_text}。如方便请回复可参与时间。"


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None
