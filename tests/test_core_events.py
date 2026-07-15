from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from recruitflow.core import database as db
from recruitflow.core.models import RecruitmentEventCreate
from recruitflow.core.state_machine import INITIAL_STAGE


class CoreEventTests(unittest.TestCase):
    def test_structured_event_and_integration_log_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "recruitflow.db"
            db.init_db(db_path)

            job_id = db.add_job("AI产品经理", "负责AI招聘流程", "王芳", db_path)
            candidate_id = db.upsert_candidate(
                {"name": "李明", "phone": "13800138000", "skills": ["AI", "SQL"]},
                db_path,
            )
            application_id = db.create_application(
                candidate_id,
                job_id,
                INITIAL_STAGE,
                {"score": 88, "recommendation_level": "建议推进"},
                "王芳",
                db_path,
            )

            event_id = db.add_event(
                application_id,
                "resume_confirmed",
                "raw resume",
                {"candidate": {"name": "李明"}},
                new_stage=INITIAL_STAGE,
                confidence=0.92,
                source="manual",
                title="HR确认简历入库：李明",
                payload={"score": 88},
                actor="王芳",
                db_path=db_path,
            )
            log_id = db.add_integration_log(
                "wecom",
                "mock",
                response_data={"status": "mock"},
                event_id=event_id,
                db_path=db_path,
            )

            self.assertTrue(db.mark_event_confirmed(event_id, {"confirmed": True}, "王芳", db_path))

            events = db.list_recent_events(db_path=db_path)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["candidate_id"], candidate_id)
            self.assertEqual(events[0]["job_id"], job_id)
            self.assertEqual(events[0]["source"], "manual")
            self.assertEqual(events[0]["payload"], {"score": 88, "confirmed": True})
            self.assertGreater(log_id, 0)

    def test_event_model_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValidationError):
            RecruitmentEventCreate(
                event_type="resume_confirmed",
                status="done",
            )


if __name__ == "__main__":
    unittest.main()
