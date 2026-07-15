from __future__ import annotations

from typing import List, Literal, Optional

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
FeedbackIntent = Literal["可以约面", "不合适", "进入复试", "通过", "发Offer", "待补充", "未知"]


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
