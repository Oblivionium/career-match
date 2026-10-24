import asyncio
from types import SimpleNamespace

import pytest

from shared import config, llm


def test_chat_uses_gemini_when_asi_one_key_is_missing(monkeypatch):
    calls = {}

    class FakeModels:
        async def generate_content(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(text="Gemini reply")

    class FakeAio:
        models = FakeModels()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class FakeClient:
        def __init__(self, *, api_key):
            calls["api_key"] = api_key
            self.aio = FakeAio()

    monkeypatch.setattr(config, "ASI_ONE_API_KEY", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(config, "GEMINI_MODEL", "gemini-test-model")
    monkeypatch.setattr(llm.genai, "Client", FakeClient)

    reply = asyncio.run(llm.chat("Be helpful", "Explain this"))

    assert reply == "Gemini reply"
    assert calls["api_key"] == "test-gemini-key"
    assert calls["model"] == "gemini-test-model"
    assert calls["contents"] == "Explain this"
    assert calls["config"].system_instruction == "Be helpful"


def test_chat_prefers_asi_one_when_both_keys_are_configured(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ASI:One reply"}}]}

    class FakeHTTPClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(config, "ASI_ONE_API_KEY", "test-asi-key")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: FakeHTTPClient())
    monkeypatch.setattr(llm.genai, "Client", lambda **kwargs: pytest.fail("Gemini should not be called"))

    assert asyncio.run(llm.chat("Be helpful", "Explain this")) == "ASI:One reply"


def test_chat_requires_at_least_one_model_key(monkeypatch):
    monkeypatch.setattr(config, "ASI_ONE_API_KEY", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    with pytest.raises(llm.LLMUnavailable, match="ASI_ONE_API_KEY or GEMINI_API_KEY"):
        asyncio.run(llm.chat("Be helpful", "Explain this"))
