"""End-to-end: a fake ASI:One user talks to the coordinator, which uses all three workers.

Runs all agents in one Bureau. Job APIs are replaced with fixtures; no LLM key, so the
deterministic fallbacks are exercised. Payments are disabled (PAYMENTS_ENABLED=false).
"""

import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Bureau, Context
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement, ChatMessage, TextContent, chat_protocol_spec,
)
from uagents import Protocol

from tests.fixtures import JOBS, RESUME_STRONG


def test_full_flow(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # agent storage files go to a fresh temp dir
    from job_scout import sources

    async def fake_source(q):
        return list(JOBS)

    async def broken_source(q):
        raise RuntimeError("simulated outage")

    monkeypatch.setattr(sources, "SOURCES", {"fixture": fake_source, "broken": broken_source})

    from coordinator.agent import agent as coord
    from job_scout.agent import agent as scout
    from match_apply.agent import agent as matcher
    from resume_analyst.agent import agent as resume

    from shared.loop import ensure_event_loop
    ensure_event_loop()
    user = Agent(name="fake_asi_user", seed="fake asi one user seed for tests")
    proto = Protocol(spec=chat_protocol_spec)
    inbox: list[ChatMessage] = []
    script = [
        RESUME_STRONG,
        json.dumps({"action": "submit_prefs", "role": "Machine Learning Intern", "location": "",
                    "kind": "internship", "remote": False}),
        "view 1",
        "pack 1",
        "confirm",
    ]
    done = asyncio.Event()

    def msg(text):
        return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(),
                           content=[TextContent(type="text", text=text)])

    # Each step: send, then wait until the coordinator's terminal reply for that step arrives.
    terminal_markers = ["What should I search for?", "Your best matches", "Get Application Pack",
                        "Get your Application Pack", "COVER LETTER"]

    @user.on_event("startup")
    async def start(ctx: Context):
        async def drive():
            for step, text in enumerate(script):
                n_before = len(inbox)
                await ctx.send(coord.address, msg(text))
                for _ in range(200):
                    await asyncio.sleep(0.1)
                    blob = " ".join(
                        (getattr(c, "text", "") or "") + json.dumps(getattr(c, "metadata", {}) or {})
                        for m in inbox[n_before:] for c in m.content)
                    if terminal_markers[step] in blob:
                        break
                else:
                    raise AssertionError(f"step {step} timed out; got: {blob[:500]}")
            done.set()
        asyncio.create_task(drive())

    @proto.on_message(ChatMessage)
    async def on_msg(ctx: Context, sender: str, m: ChatMessage):
        inbox.append(m)
        await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc),
                                                   acknowledged_msg_id=m.msg_id))

    @proto.on_message(ChatAcknowledgement)
    async def on_ack(ctx, sender, m):
        pass

    user.include(proto)

    async def main():
        bureau = Bureau(port=8765)
        for a in (coord, resume, scout, matcher, user):
            bureau.add(a)
        task = asyncio.create_task(bureau.run_async())
        try:
            await asyncio.wait_for(done.wait(), timeout=90)
        finally:
            task.cancel()

    asyncio.run(main())

    texts = [c.text for m in inbox for c in m.content if c.type == "text"]
    kinds = [c.metadata["card_kind"] for m in inbox for c in m.content if c.type == "metadata"]
    assert kinds == ["form", "carousel", "detail", "review"]
    carousel_text = next(t for t in texts if t.startswith("Top "))
    assert "Machine Learning Intern at DeepCo" in carousel_text.splitlines()[1]
    assert "broken didn't respond" in carousel_text  # fallback is visible to the user
    pack = next(t for t in texts if "COVER LETTER" in t)
    assert "DeepCo" in pack and "Apply here: https://example.com/1" in pack
