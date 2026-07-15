from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from .mock_docs import sync_candidate as mock_sync_candidate


class TencentDocsAdapter(Protocol):
    def sync_candidate(self, row: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class MockTencentDocsAdapter:
    def sync_candidate(self, row: dict[str, Any]) -> dict[str, Any]:
        return mock_sync_candidate(row)


@dataclass(frozen=True)
class ApiTencentDocsAdapter:
    file_id: str | None = None
    access_token: str | None = None

    @classmethod
    def from_env(cls) -> "ApiTencentDocsAdapter":
        return cls(
            file_id=os.getenv("TENCENT_DOCS_FILE_ID") or None,
            access_token=os.getenv("TENCENT_DOCS_ACCESS_TOKEN") or None,
        )

    def sync_candidate(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "mode": "api",
            "message": "Tencent Docs API adapter is reserved for enterprise authorization and is not implemented yet.",
            "file_id": self.file_id,
            "row": row,
        }


def get_adapter(mode: str | None = None) -> TencentDocsAdapter:
    selected = (mode or os.getenv("TENCENT_DOCS_MODE", "mock")).strip().lower()
    if selected == "api":
        return ApiTencentDocsAdapter.from_env()
    return MockTencentDocsAdapter()


def sync_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return get_adapter().sync_candidate(row)
