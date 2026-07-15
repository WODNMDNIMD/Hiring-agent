from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recruitflow.integrations.mock_docs import sync_candidate as sync_mock_candidate
from recruitflow.integrations.tencent_docs import get_adapter
from recruitflow.integrations.wecom import build_payload, push_candidate_summary


class WeComIntegrationTest(unittest.TestCase):
    def test_disabled_wecom_returns_mock_payload_without_webhook(self) -> None:
        with patch.dict(os.environ, {"WECOM_NOTIFY_ENABLED": "false"}, clear=False):
            result = push_candidate_summary("candidate summary")

        self.assertEqual(result["status"], "mock")
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["payload"]["msgtype"], "markdown")
        self.assertEqual(result["payload"]["markdown"]["content"], "candidate summary")

    def test_text_payload_builder(self) -> None:
        payload = build_payload("candidate summary", "text")
        self.assertEqual(payload, {"msgtype": "text", "text": {"content": "candidate summary"}})


class TencentDocsIntegrationTest(unittest.TestCase):
    def test_mock_docs_upserts_by_application_id_and_preserves_existing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mock_docs.csv"

            inserted = sync_mock_candidate(
                {
                    "application_id": 101,
                    "candidate_id": 7,
                    "name": "Ada",
                    "stage": "screening",
                    "score": 91,
                },
                path=path,
            )
            updated = sync_mock_candidate(
                {
                    "application_id": 101,
                    "stage": "interview",
                    "feedback_intent": "schedule_interview",
                },
                path=path,
            )

            self.assertEqual(inserted["operation"], "inserted")
            self.assertEqual(updated["operation"], "updated")

            with path.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["application_id"], "101")
            self.assertEqual(rows[0]["candidate_id"], "7")
            self.assertEqual(rows[0]["name"], "Ada")
            self.assertEqual(rows[0]["stage"], "interview")
            self.assertEqual(rows[0]["feedback_intent"], "schedule_interview")

    def test_api_adapter_is_explicitly_not_implemented(self) -> None:
        adapter = get_adapter("api")
        result = adapter.sync_candidate({"application_id": 1})

        self.assertEqual(result["status"], "not_implemented")
        self.assertEqual(result["mode"], "api")


if __name__ == "__main__":
    unittest.main()
