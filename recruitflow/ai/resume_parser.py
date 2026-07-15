from __future__ import annotations

import re

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
    payload = ai_json(
        RESUME_INTAKE_SYSTEM_PROMPT,
        f"岗位名称：{job_title}\n岗位JD：{jd_text}\n\n简历文本：\n{resume_text}",
        SCHEMA_HINT,
    )
    if payload:
        return ResumeIntakeResult.model_validate(payload)
    return mock_parse_resume(resume_text, job_title, jd_text)


def mock_parse_resume(resume_text: str, job_title: str, jd_text: str) -> ResumeIntakeResult:
    name = _first_match(resume_text, [r"姓名[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,20})", r"候选人[:：]\s*([\u4e00-\u9fa5A-Za-z]{2,20})"]) or "李明"
    phone = _first_match(resume_text, [r"(1[3-9]\d{9})"])
    email = _first_match(resume_text, [r"([\w.+-]+@[\w-]+\.[\w.-]+)"])
    years = _first_match(resume_text, [r"(\d+(?:\.\d+)?)\s*年"])
    education = "硕士" if "硕士" in resume_text else "本科" if "本科" in resume_text else None
    skills = [kw for kw in ["Python", "SQL", "数据分析", "产品设计", "SaaS", "AI", "Java", "Vue", "FastAPI"] if kw.lower() in resume_text.lower()]
    jd_keywords = [kw for kw in ["Python", "SQL", "数据分析", "产品", "SaaS", "AI", "招聘", "Agent"] if kw.lower() in jd_text.lower()]
    matched = [kw for kw in skills if kw in jd_keywords] or skills[:3]
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
            education=education,
            experience_years=float(years) if years else None,
            skills=skills,
            expected_salary=_first_match(resume_text, [r"期望薪资[:：]?\s*([0-9Kk\-~万/月年]+)"]),
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


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

