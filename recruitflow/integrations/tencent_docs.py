from __future__ import annotations

import os

from .mock_docs import sync_candidate as mock_sync_candidate


def sync_candidate(row: dict) -> dict:
    mode = os.getenv("TENCENT_DOCS_MODE", "mock")
    if mode != "api":
        return mock_sync_candidate(row)
    # Formal Tencent Docs Open API access requires OAuth credentials and document permissions.
    # The adapter is isolated so the demo can run before enterprise authorization is ready.
    return {
        "status": "pending_api_credentials",
        "message": "腾讯文档真实 API 待接入：请配置 OAuth、file_id 和写入范围。",
        "row": row,
    }

