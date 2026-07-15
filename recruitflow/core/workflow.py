from __future__ import annotations

from recruitflow.integrations.tencent_docs import sync_candidate
from recruitflow.integrations.wecom import push_candidate_summary

from . import database as db
from .models import FeedbackParseResult, ResumeIntakeResult, Stage
from .state_machine import INITIAL_STAGE, can_transition, stage_for_feedback_intent


def confirm_resume_intake(job_id: int, result: ResumeIntakeResult, raw_resume: str, owner: str | None = None) -> dict:
    candidate_id = db.upsert_candidate(result.candidate.model_dump())
    application_id = db.create_application(
        candidate_id,
        job_id,
        INITIAL_STAGE,
        result.match.model_dump(),
        owner=owner,
    )
    event_id = db.add_event(
        application_id,
        "resume_confirmed",
        raw_resume,
        result.model_dump(),
        new_stage=INITIAL_STAGE,
        confidence=result.match.confidence,
    )
    wecom_result = push_candidate_summary(build_wecom_summary(result))
    docs_result = sync_candidate(
        {
            "candidate_id": candidate_id,
            "application_id": application_id,
            "name": result.candidate.name,
            "stage": INITIAL_STAGE,
            "score": result.match.score,
            "level": result.match.recommendation_level,
        }
    )
    db.add_integration_log("wecom", wecom_result.get("status", "unknown"), response_data=wecom_result, event_id=event_id)
    db.add_integration_log("tencent_docs", docs_result.get("status", "unknown"), response_data=docs_result, event_id=event_id)
    return {"candidate_id": candidate_id, "application_id": application_id, "event_id": event_id}


def confirm_feedback(application_id: int, current_stage: Stage, feedback: FeedbackParseResult, raw_feedback: str) -> dict:
    next_stage = feedback.next_stage or stage_for_feedback_intent(feedback.intent, current_stage)
    if not can_transition(current_stage, next_stage):
        event_id = db.add_event(
            application_id,
            "feedback_blocked",
            raw_feedback,
            feedback.model_dump(),
            old_stage=current_stage,
            new_stage=next_stage,
            confidence=feedback.confidence,
            status="needs_review",
        )
        return {"status": "blocked", "event_id": event_id, "message": "状态流转不合法，需要人工复核"}
    old_stage = db.update_application_stage(application_id, next_stage)
    event_id = db.add_event(
        application_id,
        "feedback_confirmed",
        raw_feedback,
        feedback.model_dump(),
        old_stage=old_stage,
        new_stage=next_stage,
        confidence=feedback.confidence,
    )
    docs_result = sync_candidate({"application_id": application_id, "stage": next_stage, "feedback_intent": feedback.intent})
    db.add_integration_log("tencent_docs", docs_result.get("status", "unknown"), response_data=docs_result, event_id=event_id)
    return {"status": "updated", "event_id": event_id, "old_stage": old_stage, "new_stage": next_stage}


def build_wecom_summary(result: ResumeIntakeResult) -> str:
    matched = "\n".join(f"> {item}" for item in result.match.matched_points[:3]) or "> 待确认"
    risks = "\n".join(f"> {item}" for item in result.match.risk_points[:3]) or "> 暂无明显风险"
    return f"""【候选人推荐】
> 候选人：{result.candidate.name}
> 学历：{result.candidate.education or '待确认'}
> 经验：{result.candidate.experience_years or '待确认'}年
> 期望薪资：{result.candidate.expected_salary or '待确认'}

匹配点：
{matched}

风险点：
{risks}

AI建议：{result.match.recommendation_level}，匹配分 {result.match.score}
请回复：可以约面 / 不合适：原因 / 进入复试
"""

