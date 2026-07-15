from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from recruitflow.ai.feedback_parser import mock_parse_feedback
from recruitflow.core import database as db
from recruitflow.core.models import FeedbackParseResult
from recruitflow.core.state_machine import can_transition, stage_for_feedback_intent
from recruitflow.core.workflow import confirm_feedback, resolve_feedback_next_stage


class FeedbackWorkflowTest(unittest.TestCase):
    def test_mock_parser_extracts_feedback_fields(self) -> None:
        result = mock_parse_feedback("候选人：李明\n岗位：AI产品经理\n反馈：李明可以约面，建议下周二下午。")

        self.assertEqual(result.candidate_name, "李明")
        self.assertEqual(result.job_name, "AI产品经理")
        self.assertEqual(result.intent, "可以约面")
        self.assertEqual(result.next_stage, "初试待安排")
        self.assertGreaterEqual(result.confidence, 0.7)

    def test_candidate_withdrawal_maps_to_terminal_stage(self) -> None:
        result = mock_parse_feedback("候选人：王芳\n岗位：后端工程师\n候选人放弃，暂不考虑机会。")

        self.assertEqual(result.intent, "候选人放弃")
        self.assertEqual(result.next_stage, "候选人放弃")

    def test_feedback_stage_depends_on_current_stage(self) -> None:
        feedback = FeedbackParseResult(intent="通过", next_stage="初试待安排", confidence=0.8)

        self.assertEqual(resolve_feedback_next_stage(feedback, "初试待反馈"), "复试待安排")
        self.assertEqual(resolve_feedback_next_stage(feedback, "复试待反馈"), "Offer审批")

    def test_illegal_transition_is_blocked(self) -> None:
        self.assertFalse(can_transition("已入职", "Offer审批"))

    def test_legal_intent_transition_is_allowed(self) -> None:
        next_stage = stage_for_feedback_intent("进入复试", "初试待反馈")

        self.assertEqual(next_stage, "复试待安排")
        self.assertTrue(can_transition("初试待反馈", next_stage))

    def test_confirm_feedback_updates_stage_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "recruitflow.db"
            db.init_db(db_path)
            job_id = db.add_job("AI产品经理", "负责AI产品", db_path=db_path)
            candidate_id = db.upsert_candidate({"name": "李明"}, db_path=db_path)
            application_id = db.create_application(candidate_id, job_id, "初试待反馈", {}, db_path=db_path)
            feedback = FeedbackParseResult(intent="进入复试", next_stage="复试待安排", confidence=0.86)

            output = confirm_feedback(application_id, "初试待反馈", feedback, "李明进入复试", db_path=db_path)

            self.assertEqual(output["status"], "updated")
            self.assertEqual(output["old_stage"], "初试待反馈")
            self.assertEqual(output["new_stage"], "复试待安排")
            view = db.applications_view(db_path)
            self.assertEqual(view.iloc[0]["stage"], "复试待安排")

    def test_confirm_feedback_blocks_illegal_database_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "recruitflow.db"
            db.init_db(db_path)
            job_id = db.add_job("AI产品经理", "负责AI产品", db_path=db_path)
            candidate_id = db.upsert_candidate({"name": "李明"}, db_path=db_path)
            application_id = db.create_application(candidate_id, job_id, "已入职", {}, db_path=db_path)
            feedback = FeedbackParseResult(intent="发Offer", next_stage="Offer审批", confidence=0.86)

            output = confirm_feedback(application_id, "已入职", feedback, "李明发Offer", db_path=db_path)

            self.assertEqual(output["status"], "blocked")
            view = db.applications_view(db_path)
            self.assertEqual(view.iloc[0]["stage"], "已入职")


if __name__ == "__main__":
    unittest.main()
