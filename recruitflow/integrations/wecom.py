from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_markdown_payload(summary: str) -> dict[str, Any]:
    return {"msgtype": "markdown", "markdown": {"content": summary}}


def build_text_payload(summary: str) -> dict[str, Any]:
    return {"msgtype": "text", "text": {"content": summary}}


def build_payload(summary: str, message_type: str | None = None) -> dict[str, Any]:
    selected = (message_type or os.getenv("WECOM_MESSAGE_TYPE", "markdown")).strip().lower()
    if selected == "text":
        return build_text_payload(summary)
    return build_markdown_payload(summary)


@dataclass(frozen=True)
class WeComAdapter:
    enabled: bool = False
    webhook_url: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "WeComAdapter":
        return cls(
            enabled=_env_enabled("WECOM_NOTIFY_ENABLED", default=False),
            webhook_url=os.getenv("WECOM_WEBHOOK_URL") or None,
            timeout_seconds=float(os.getenv("WECOM_TIMEOUT_SECONDS", "10")),
        )

    def send(self, summary: str, message_type: str | None = None) -> dict[str, Any]:
        payload = build_payload(summary, message_type)

        if not self.enabled:
            return {
                "status": "mock",
                "mode": "mock",
                "message": "WeCom notification is disabled; payload was generated but not sent.",
                "payload": payload,
            }

        if not self.webhook_url:
            return {
                "status": "config_error",
                "mode": "api",
                "message": "WECOM_WEBHOOK_URL is required when WECOM_NOTIFY_ENABLED=true.",
                "payload": payload,
            }

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                try:
                    response_data: Any = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    response_data = {"raw": raw}
                return {
                    "status": "sent",
                    "mode": "api",
                    "payload": payload,
                    "response": response_data,
                    "http_status": response.status,
                }
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return {
                "status": "failed",
                "mode": "api",
                "payload": payload,
                "http_status": exc.code,
                "error": error_body or str(exc),
            }
        except URLError as exc:
            return {
                "status": "failed",
                "mode": "api",
                "payload": payload,
                "error": str(exc.reason),
            }


def push_candidate_summary(summary: str) -> dict[str, Any]:
    return WeComAdapter.from_env().send(summary)
