from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Stage = Literal[
    "待二审",
    "初试待安排",
    "初试待反馈",
    "复试待安排",
    "复试待反馈",
    "终试待安排",
    "Offer审批",
    "Offer已发",
    "待入职",
    "已入职",
    "不合适",
    "候选人放弃",
]

RecommendationLevel = Literal["建议推进", "人工复核", "暂不推进"]
FeedbackIntent = Literal["可以约面", "不合适", "进入复试", "通过", "发Offer", "候选人放弃", "待补充", "未知"]
RecruitmentEventType = Literal[
    "resume_parsed",
    "resume_confirmed",
    "candidate_upserted",
    "application_created",
    "application_updated",
    "feedback_parsed",
    "feedback_confirmed",
    "feedback_blocked",
    "stage_changed",
    "integration_synced",
    "integration_failed",
]
RecruitmentEventStatus = Literal["pending", "confirmed", "needs_review", "failed", "ignored"]
RecruitmentEventSource = Literal["ai", "manual", "system", "wecom", "tencent_docs"]
IntegrationType = Literal["wecom", "wecom_test", "tencent_docs", "ai_provider", "mock", "system"]
IntegrationStatus = Literal[
    "pending",
    "success",
    "failed",
    "mock",
    "mock_synced",
    "sent",
    "config_error",
    "not_implemented",
    "pending_api_credentials",
    "unknown",
]


class CandidateProfile(BaseModel):
    name: str = Field(default="未知候选人")
    phone: Optional[str] = None
    email: Optional[str] = None
    current_city: Optional[str] = None
    education: Optional[str] = None
    school: Optional[str] = None
    major: Optional[str] = None
    experience_years: Optional[float] = None
    latest_company: Optional[str] = None
    latest_title: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    job_status: Optional[str] = None
    expected_salary: Optional[str] = None
    arrival_time: Optional[str] = None


class MatchAnalysis(BaseModel):
    score: int = Field(default=70, ge=0, le=100)
    matched_points: List[str] = Field(default_factory=list)
    risk_points: List[str] = Field(default_factory=list)
    recommendation_level: RecommendationLevel = "人工复核"
    recommendation_text: str = ""
    confidence: float = Field(default=0.75, ge=0, le=1)


class ResumeIntakeResult(BaseModel):
    candidate: CandidateProfile
    match: MatchAnalysis


class FeedbackParseResult(BaseModel):
    candidate_name: Optional[str] = None
    job_name: Optional[str] = None
    intent: FeedbackIntent = "未知"
    next_stage: Optional[Stage] = None
    suggested_time: Optional[str] = None
    reason: Optional[str] = None
    invitation_message: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class RecruitmentEventCreate(BaseModel):
    event_type: RecruitmentEventType
    application_id: Optional[int] = None
    candidate_id: Optional[int] = None
    job_id: Optional[int] = None
    source: RecruitmentEventSource = "system"
    title: Optional[str] = None
    raw_content: Optional[str] = None
    parsed_content: Dict[str, Any] = Field(default_factory=dict)
    payload: Dict[str, Any] = Field(default_factory=dict)
    old_stage: Optional[Stage] = None
    new_stage: Optional[Stage] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    status: RecruitmentEventStatus = "confirmed"
    actor: Optional[str] = None


class IntegrationLogCreate(BaseModel):
    integration_type: IntegrationType
    status: IntegrationStatus
    event_id: Optional[int] = None
    request_data: Dict[str, Any] = Field(default_factory=dict)
    response_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
