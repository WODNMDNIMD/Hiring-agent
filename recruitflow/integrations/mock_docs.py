from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MOCK_DOCS_PATH = Path("data/mock_tencent_docs.csv")

BASE_FIELDS = [
    "application_id",
    "candidate_id",
    "name",
    "job_title",
    "stage",
    "score",
    "level",
    "recommendation_text",
    "feedback_intent",
    "updated_at",
]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalized_row(row: dict[str, Any]) -> dict[str, str]:
    normalized = {key: _stringify(value) for key, value in row.items()}
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
    return normalized


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _fieldnames(rows: list[dict[str, str]], next_row: dict[str, str]) -> list[str]:
    fields = list(BASE_FIELDS)
    for row in [*rows, next_row]:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def sync_candidate(row: dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else Path(os.getenv("TENCENT_DOCS_MOCK_PATH", str(DEFAULT_MOCK_DOCS_PATH)))
    target.parent.mkdir(parents=True, exist_ok=True)

    rows = _read_rows(target)
    next_row = _normalized_row(row)
    application_id = next_row.get("application_id")
    operation = "inserted"

    if application_id:
        for index, existing in enumerate(rows):
            if existing.get("application_id") == application_id:
                rows[index] = {**existing, **{key: value for key, value in next_row.items() if value != ""}}
                operation = "updated"
                break
        else:
            rows.append(next_row)
    else:
        rows.append(next_row)

    fields = _fieldnames(rows, next_row)
    with target.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "status": "mock_synced",
        "mode": "mock",
        "operation": operation,
        "path": str(target),
        "row": next_row,
    }
