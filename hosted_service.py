"""Run the four mailbox agents together behind a small HTTP health endpoint.

The agents keep their own uAgents ports for their local inspectors, while chat
traffic uses Agentverse mailboxes. The health endpoint listens on PORT for
hosts that require an HTTP listener; mailbox communication does not use it.
"""

from __future__ import annotations

import asyncio
import json
import os

# Make mailbox mode explicit before agent modules load shared.config.
os.environ["USE_MAILBOX"] = "true"

from shared.loop import ensure_event_loop

# Agent constructors capture the current event loop, so create it before
# importing their modules. All four agents and the health endpoint then share
# one loop and one Python process.
loop = ensure_event_loop()

from coordinator.agent import agent as coordinator  # noqa: E402
from job_scout.agent import agent as job_scout  # noqa: E402
from match_apply.agent import agent as match_apply  # noqa: E402
from resume_analyst.agent import agent as resume_analyst  # noqa: E402


AGENTS = {
    "career_coordinator": coordinator,
    "resume_analyst": resume_analyst,
    "job_scout": job_scout,
    "match_apply": match_apply,
}


async def handle_health_request(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    request_line = await reader.readline()
    while True:
        header = await reader.readline()
        if header in (b"\r\n", b"", b"\n"):
            break

    path = request_line.split(b" ")[1] if b" " in request_line else b"/"
    body = json.dumps(
        {
            "status": "ok",
            "agents": {name: agent.address for name, agent in AGENTS.items()},
        }
    ).encode()
    status = b"200 OK" if path in (b"/", b"/healthz") else b"404 Not Found"
    if status.startswith(b"404"):
        body = b'{"error":"not found"}'
    response = (
        b"HTTP/1.1 "
        + status
        + b"\r\nContent-Type: application/json\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\nConnection: close\r\n\r\n"
        + body
    )
    writer.write(response)
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def main() -> None:
    port = int(os.environ.get("PORT", "10000"))
    health_server = await asyncio.start_server(
        handle_health_request, host="0.0.0.0", port=port
    )
    print(f"Health endpoint listening on 0.0.0.0:{port}", flush=True)
    print("Starting all four CareerMatch mailbox agents", flush=True)

    agent_tasks = [asyncio.create_task(agent.run_async()) for agent in AGENTS.values()]
    try:
        _done, pending = await asyncio.wait(
            agent_tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        raise RuntimeError("A CareerMatch agent stopped unexpectedly; restarting service")
    finally:
        health_server.close()
        await health_server.wait_closed()


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    finally:
        if not loop.is_closed():
            loop.close()
