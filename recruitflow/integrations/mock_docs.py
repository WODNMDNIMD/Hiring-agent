from __future__ import annotations

from pathlib import Path

import pandas as pd


MOCK_DOCS_PATH = Path("data/mock_tencent_docs.csv")


def sync_candidate(row: dict) -> dict:
    MOCK_DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([row])
    if MOCK_DOCS_PATH.exists():
        old = pd.read_csv(MOCK_DOCS_PATH)
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(MOCK_DOCS_PATH, index=False, encoding="utf-8-sig")
    return {"status": "mock_synced", "path": str(MOCK_DOCS_PATH)}

