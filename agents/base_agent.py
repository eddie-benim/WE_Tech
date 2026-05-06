from __future__ import annotations

import os
import json
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

import config

class BaseAgent:

    def __init__(self, model: str | None = None):
        self.model = model or config.AGENT_MODEL
        self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", config.OPENAI_API_KEY))
        self.log: list[str] = []

    def _log(self, msg: str):
        self.log.append(msg)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _chat(self, system: str, user: str, max_tokens: int | None = None) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens or config.MAX_COMPLETION_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    def _chat_json(self, system: str, user: str, max_tokens: int | None = None) -> dict | list:
        raw = self._chat(system, user, max_tokens)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[: cleaned.rfind("```")]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"raw": raw, "parse_error": True}

    def _token_count(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4