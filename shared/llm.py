"""Small async LLM client, selecting ASI:One when configured and otherwise Gemini.

Every caller must handle `LLMUnavailable` and fall back to deterministic logic, so the
agents keep working when keys are missing or an API is down.
"""

import json
import re

import httpx
from google import genai
from google.genai import types

from shared import config
from shared.retry import with_retry


class LLMUnavailable(Exception):
    pass


async def chat(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1200,
               timeout: float = 45.0) -> str:
    if not config.ASI_ONE_API_KEY and not config.GEMINI_API_KEY:
        raise LLMUnavailable("Set ASI_ONE_API_KEY or GEMINI_API_KEY to enable LLM features")

    async def _call() -> str:
        if config.ASI_ONE_API_KEY:
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

        if config.GEMINI_API_KEY:
            async with genai.Client(api_key=config.GEMINI_API_KEY).aio as client:
                response = await client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
            if response.text:
                return response.text
            raise LLMUnavailable("Gemini returned an empty response")

    try:
        return await with_retry(_call, attempts=2, label="LLM chat")
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
