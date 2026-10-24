"""Thin client for the ASI:One chat completions API (OpenAI-compatible).

Every caller must handle `LLMUnavailable` and fall back to deterministic logic, so the
agents keep working when the key is missing or the API is down.
"""

import json
import re

import httpx

from shared import config
from shared.retry import with_retry


class LLMUnavailable(Exception):
    pass


async def chat(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1200,
               timeout: float = 45.0) -> str:
    if not config.ASI_ONE_API_KEY:
        raise LLMUnavailable("ASI_ONE_API_KEY not set")

    async def _call() -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{config.ASI_ONE_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.ASI_ONE_API_KEY}"},
                json={
                    "model": config.ASI_ONE_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    try:
        return await with_retry(_call, attempts=2, label="asi1 chat")
    except Exception as exc:  # noqa: BLE001
        raise LLMUnavailable(str(exc)) from exc


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM reply (handles ```json fences and chatter)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in LLM reply")
        candidate = text[start : end + 1]
    return json.loads(candidate)


async def chat_json(system: str, user: str, **kwargs) -> dict:
    """Ask for JSON; retry once with a stricter reminder if the first reply doesn't parse."""
    reply = await chat(system, user, **kwargs)
    try:
        return extract_json(reply)
    except (ValueError, json.JSONDecodeError):
        reply = await chat(system + "\nReturn ONLY a valid JSON object. No prose.", user, **kwargs)
        try:
            return extract_json(reply)
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMUnavailable(f"LLM returned invalid JSON twice: {exc}") from exc
