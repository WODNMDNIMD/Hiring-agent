from __future__ import annotations

from .models import Stage


INITIAL_STAGE: Stage = "待二审"

TERMINAL_STAGES: set[Stage] = {"已入职", "不合适", "候选人放弃"}

ALLOWED_TRANSITIONS: dict[Stage, set[Stage]] = {
    "待二审": {"初试待安排", "不合适", "候选人放弃"},
    "初试待安排": {"初试待反馈", "不合适", "候选人放弃"},
    "初试待反馈": {"复试待安排", "Offer审批", "不合适", "候选人放弃"},
    "复试待安排": {"复试待反馈", "不合适", "候选人放弃"},
    "复试待反馈": {"终试待安排", "Offer审批", "不合适", "候选人放弃"},
    "终试待安排": {"Offer审批", "不合适", "候选人放弃"},
    "Offer审批": {"Offer已发", "不合适", "候选人放弃"},
    "Offer已发": {"待入职", "不合适", "候选人放弃"},
    "待入职": {"已入职", "候选人放弃"},
    "已入职": set(),
    "不合适": set(),
    "候选人放弃": set(),
}


def can_transition(old_stage: Stage, new_stage: Stage) -> bool:
    if old_stage == new_stage:
        return True
    return new_stage in ALLOWED_TRANSITIONS.get(old_stage, set())


def stage_for_feedback_intent(intent: str, current_stage: Stage) -> Stage:
    if intent == "不合适":
        return "不合适"
    if intent == "可以约面":
        return "初试待安排" if current_stage == "待二审" else current_stage
    if intent == "进入复试":
        return "复试待安排"
    if intent == "通过":
        if current_stage in {"初试待安排", "初试待反馈"}:
            return "复试待安排"
        if current_stage in {"复试待安排", "复试待反馈", "终试待安排"}:
            return "Offer审批"
    if intent == "发Offer":
        return "Offer审批"
    return current_stage

