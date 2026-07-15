from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def ai_json(system_prompt: str, user_prompt: str, schema_hint: str) -> dict[str, Any] | None:
    provider = os.getenv("AI_PROVIDER", "mock").lower()
    api_key = os.getenv("AI_API_KEY")
    if provider == "mock" or not api_key:
        return None

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("AI_BASE_URL") or None,
    )
    response = client.chat.completions.create(
        model=os.getenv("AI_MODEL", "deepseek-chat"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{user_prompt}\n\nJSON字段说明：\n{schema_hint}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)

