from __future__ import annotations

import re
from typing import Any

from recruitflow.core.models import CandidateProfile, MatchAnalysis, ResumeIntakeResult

from .client import ai_json
from .prompts import RESUME_INTAKE_SYSTEM_PROMPT


SCHEMA_HINT = """
{
  "candidate": {
    "name": "string",
    "phone": "string|null",
    "email": "string|null",
    "current_city": "string|null",
    "education": "string|null",
    "school": "string|null",
    "major": "string|null",
    "experience_years": "number|null",
    "latest_company": "string|null",
    "latest_title": "string|null",
    "skills": ["string"],
    "job_status": "string|null",
    "expected_salary": "string|null",
    "arrival_time": "string|null"
  },
  "match": {
    "score": 0,
    "matched_points": ["string"],
    "risk_points": ["string"],
    "recommendation_level": "建议推进|人工复核|暂不推进",
    "recommendation_text": "string",
    "confidence": 0.0
  }
}
"""


def parse_resume_with_jd(resume_text: str, job_title: str, jd_text: str) -> ResumeIntakeResult:
    try:
        payload = ai_json(
            RESUME_INTAKE_SYSTEM_PROMPT,
            f"岗位名称：{job_title}\n岗位JD：{jd_text}\n\n简历文本：\n{resume_text}",
            SCHEMA_HINT,
        )
        if payload:
            return ResumeIntakeResult.model_validate(_normalize_provider_payload(payload))
    except Exception:
        pass
    return mock_parse_resume(resume_text, job_title, jd_text)


def mock_parse_resume(resume_text: str, job_title: str, jd_text: str) -> ResumeIntakeResult:
    name = _first_match(resume_text, [r"姓名[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,20})", r"候选人[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,20})"]) or "李明"
    phone = _first_match(resume_text, [r"(1[3-9]\d{9})"])
    email = _first_match(resume_text, [r"([\w.+-]+@[\w-]+\.[\w.-]+)"])
    years = _first_match(resume_text, [r"(\d+(?:\.\d+)?)\s*年"])
    education = _education_level(resume_text)
    skills = [
        kw for kw in [
            "Python", "SQL", "数据分析", "产品设计", "SaaS", "AI", "Agent", "招聘运营",
            "流程自动化", "项目推进", "Java", "Vue", "FastAPI", "Streamlit",
        ]
        if kw.lower() in resume_text.lower()
    ]
    jd_keywords = [
        kw for kw in ["Python", "SQL", "数据分析", "产品", "SaaS", "AI", "招聘", "Agent", "自动化", "协作"]
        if kw.lower() in jd_text.lower()
    ]
    matched = _match_keywords(skills, jd_keywords) or skills[:3]
    score = min(92, 65 + len(matched) * 8)
    level = "建议推进" if score >= 80 else "人工复核" if score >= 65 else "暂不推进"
    risk_points = []
    if not years:
        risk_points.append("工作年限未在简历中明确，需要HR复核")
    if len(matched) < 2:
        risk_points.append("岗位关键词匹配点偏少，需要结合项目经历进一步判断")
    recommendation = (
        f"{name} 应聘 {job_title}，"
        f"{education or '学历待确认'}，{years or '工作年限待确认'}年左右经验。"
        f"主要匹配点包括：{'、'.join(matched) if matched else '待进一步确认'}。"
        f"风险点：{'、'.join(risk_points) if risk_points else '暂无明显风险'}。"
        f"AI建议：{level}。"
    )
    return ResumeIntakeResult(
        candidate=CandidateProfile(
            name=name,
            phone=phone,
            email=email,
            current_city=_first_match(resume_text, [r"城市[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,30})", r"现居[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,30})"]),
            education=education,
            school=_first_match(resume_text, [r"([\u4e00-\u9fa5A-Za-z]+大学)", r"毕业院校[:：]\s*([\u4e00-\u9fa5A-Za-zA-Za-z\s]+)"]),
            major=_first_match(resume_text, [r"专业[:：]\s*([\u4e00-\u9fa5A-Za-z\s]+)", r"([\u4e00-\u9fa5A-Za-z]+专业)"]),
            experience_years=float(years) if years else None,
            latest_company=_first_match(resume_text, [r"最近(?:任职于|就职于)\s*([\u4e00-\u9fa5A-Za-z0-9]+)", r"最近公司[:：]\s*([\u4e00-\u9fa5A-Za-z0-9]+)"]),
            latest_title=_first_match(resume_text, [r"最近职位[:：]\s*([\u4e00-\u9fa5A-Za-zA-Za-z\s]+)", r"应聘[:：]\s*([\u4e00-\u9fa5A-Za-zA-Za-z\s]+)"]),
            skills=skills,
            job_status=_job_status(resume_text),
            expected_salary=_first_match(resume_text, [r"期望薪资[:：]?\s*([0-9Kk\-~万/月年]+)"]),
            arrival_time=_first_match(resume_text, [r"((?:一|两|二|三|四|\d+)\s*(?:周|个月)内到岗)", r"(随时到岗)", r"(已离职)"]),
        ),
        match=MatchAnalysis(
            score=score,
            matched_points=[f"具备{item}相关经验" for item in matched] or ["简历与岗位存在一定关联"],
            risk_points=risk_points,
            recommendation_level=level,
            recommendation_text=recommendation,
            confidence=0.78,
        ),
    )


def _normalize_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload.get("candidate") or payload.get("candidate_profile") or {}
    match = payload.get("match") or payload.get("analysis") or {}
    if not isinstance(candidate, dict):
        candidate = {}
    if not isinstance(match, dict):
        match = {}
    normalized = {
        "candidate": {
            "name": _pick(candidate, "name", "candidate_name", "姓名") or "未知候选人",
            "phone": _pick(candidate, "phone", "mobile", "电话", "手机"),
            "email": _pick(candidate, "email", "邮箱"),
            "current_city": _pick(candidate, "current_city", "city", "location", "城市"),
            "education": _pick(candidate, "education", "highest_education", "学历"),
            "school": _pick(candidate, "school", "university", "毕业院校"),
            "major": _pick(candidate, "major", "专业"),
            "experience_years": _to_float(_pick(candidate, "experience_years", "years", "工作年限")),
            "latest_company": _pick(candidate, "latest_company", "last_company", "最近公司"),
            "latest_title": _pick(candidate, "latest_title", "last_position", "最近职位"),
            "skills": _to_list(_pick(candidate, "skills", "技能")),
            "job_status": _pick(candidate, "job_status", "employment_status", "在离职状态"),
            "expected_salary": _pick(candidate, "expected_salary", "salary", "期望薪资"),
            "arrival_time": _pick(candidate, "arrival_time", "availability", "到岗时间"),
        },
        "match": {
            "score": _to_score(_pick(match, "score", "match_score", "匹配分")),
            "matched_points": _to_list(_pick(match, "matched_points", "match_points", "匹配点")),
            "risk_points": _to_list(_pick(match, "risk_points", "risks", "风险点")),
            "recommendation_level": _recommendation_level(_pick(match, "recommendation_level", "level", "推荐程度")),
            "recommendation_text": (
                _pick(match, "recommendation_text", "recommendation", "推荐语")
                or payload.get("recommendation_text")
                or ""
            ),
            "confidence": _to_confidence(_pick(match, "confidence", "置信度")),
        },
    }
    return normalized


def _pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[、,，;\n；]+", str(value)) if item.strip()]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def _to_score(value: Any) -> int:
    number = _to_float(value)
    if number is None:
        return 70
    return max(0, min(100, round(number)))


def _to_confidence(value: Any) -> float:
    number = _to_float(value)
    if number is None:
        return 0.75
    if number > 1:
        number = number / 100
    return max(0, min(1, number))


def _recommendation_level(value: Any) -> str:
    text = str(value or "")
    if "建议推进" in text:
        return "建议推进"
    if "暂不推进" in text or "不推进" in text:
        return "暂不推进"
    return "人工复核"


def _education_level(text: str) -> str | None:
    for level in ["博士", "硕士", "本科", "大专"]:
        if level in text:
            return level
    return None


def _job_status(text: str) -> str | None:
    if "已离职" in text:
        return "已离职"
    if "离职交接" in text:
        return "离职交接中"
    if "在职" in text:
        return "在职"
    return None


def _match_keywords(skills: list[str], jd_keywords: list[str]) -> list[str]:
    matched: list[str] = []
    for skill in skills:
        if any(skill.lower() in keyword.lower() or keyword.lower() in skill.lower() for keyword in jd_keywords):
            matched.append(skill)
    return matched


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None
