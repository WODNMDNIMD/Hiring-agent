from __future__ import annotations

import os

import requests


def push_candidate_summary(summary: str) -> dict:
    webhook = os.getenv("WECOM_WEBHOOK_URL")
    if not webhook:
        return {"status": "mock", "message": "未配置企业微信群机器人，已进入演示模式", "summary": summary}
    response = requests.post(
        webhook,
        json={"msgtype": "markdown", "markdown": {"content": summary}},
        timeout=10,
    )
    response.raise_for_status()
    return {"status": "sent", "response": response.json()}

