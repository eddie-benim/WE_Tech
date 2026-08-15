from __future__ import annotations

import os
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI, AuthenticationError, RateLimitError, APIConnectionError

import config


class BaseAgent:

    def __init__(self, model: str | None = None):
        self.model = model or config.AGENT_MODEL
        api_key = os.environ.get("OPENAI_API_KEY") or config.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "No OpenAI API key found. Enter your key in the sidebar before running the agent."
            )
        self._client = OpenAI(api_key=api_key)
        self.log: list[str] = []
        self.usage_log: list[dict] = []

    def _log(self, msg: str):
        self.log.append(msg)

    def _track_usage(self, label: str, usage) -> None:
        if usage is None:
            return
        self.usage_log.append({
            "label": label,
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        })

    def usage_summary(self) -> str:
        return format_usage_table(self.usage_log)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        reraise=True,
    )
    def _chat(self, system: str, user: str, max_tokens: int | None = None, label: str = "chat") -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens or config.MAX_COMPLETION_TOKENS,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        self._track_usage(label, response.usage)
        return response.choices[0].message.content or ""

    def _chat_json(self, system: str, user: str, max_tokens: int | None = None, label: str = "chat_json") -> dict | list:
        raw = self._chat(system, user, max_tokens, label=label)
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


def format_usage_table(usage_log: list[dict]) -> str:
    if not usage_log:
        return "No usage recorded."
    totals: dict[str, dict] = {}
    for entry in usage_log:
        t = totals.setdefault(entry["label"], {"calls": 0, "prompt": 0, "completion": 0})
        t["calls"] += 1
        t["prompt"] += entry["prompt_tokens"]
        t["completion"] += entry["completion_tokens"]
    lines = [f"{'Label':<24}{'Calls':>7}{'Prompt':>10}{'Completion':>12}{'Total':>10}"]
    grand_total = 0
    for label, t in sorted(totals.items(), key=lambda kv: -(kv[1]["prompt"] + kv[1]["completion"])):
        total = t["prompt"] + t["completion"]
        grand_total += total
        lines.append(f"{label:<24}{t['calls']:>7}{t['prompt']:>10}{t['completion']:>12}{total:>10}")
    lines.append("-" * 63)
    lines.append(f"{'TOTAL':<24}{'':>7}{'':>10}{'':>12}{grand_total:>10}")
    return "\n".join(lines)
