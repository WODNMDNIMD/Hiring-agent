from __future__ import annotations

import re

from recruitflow.core.models import FeedbackParseResult

from .client import ai_json
from .prompts import FEEDBACK_SYSTEM_PROMPT


SCHEMA_HINT = """
{
  "candidate_name": "string|null",
  "job_name": "string|null",
  "intent": "可以约面|不合适|进入复试|通过|发Offer|待补充|未知",
  "next_stage": "待二审|初试待安排|初试待反馈|复试待安排|复试待反馈|终试待安排|Offer审批|Offer已发|待入职|已入职|不合适|候选人放弃|null",
  "suggested_time": "string|null",
  "reason": "string|null",
  "invitation_message": "string|null",
  "confidence": 0.0
}
"""


def parse_feedback(text: str) -> FeedbackParseResult:
    payload = ai_json(FEEDBACK_SYSTEM_PROMPT, text, SCHEMA_HINT)
    if payload:
        return FeedbackParseResult.model_validate(payload)
    return mock_parse_feedback(text)


def mock_parse_feedback(text: str) -> FeedbackParseResult:
    name = _first_match(text, [r"([\u4e00-\u9fa5]{2,4})(?:可以|不合适|进入|通过|约面|复试|发Offer)"])
    if "不合适" in text or "淘汰" in text:
        intent = "不合适"
        next_stage = "不合适"
        reason = text
    elif "复试" in text:
        intent = "进入复试"
        next_stage = "复试待安排"
        reason = None
    elif "offer" in text.lower() or "发Offer" in text:
        intent = "发Offer"
        next_stage = "Offer审批"
        reason = None
    elif "可以" in text or "约面" in text or "安排" in text:
        intent = "可以约面"
        next_stage = "初试待安排"
        reason = None
    elif "通过" in text:
        intent = "通过"
        next_stage = "复试待安排"
        reason = None
    else:
        intent = "未知"
        next_stage = None
        reason = None
    time_hint = _first_match(text, [r"((?:今天|明天|后天|本周|下周|周[一二三四五六日天]).{0,12}(?:上午|下午|晚上|点)?)"])
    invitation = None
    if intent in {"可以约面", "进入复试", "通过"}:
        invitation = f"您好，想和您确认一下后续面试安排，建议时间为：{time_hint or '待HR确认'}。如方便请回复可参与时间。"
    return FeedbackParseResult(
        candidate_name=name,
        intent=intent,  # type: ignore[arg-type]
        next_stage=next_stage,  # type: ignore[arg-type]
        suggested_time=time_hint,
        reason=reason,
        invitation_message=invitation,
        confidence=0.76 if intent != "未知" else 0.45,
    )


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

