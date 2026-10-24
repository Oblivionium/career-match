"""Job Scout agent: JobQuery -> JobResults (live listings from several APIs, cached)."""

import hashlib
import json
import time

from uagents import Agent, Context

from shared import config
from shared.loop import ensure_event_loop
from shared.models import JobListing, JobQuery, JobResults
from job_scout.sources import search_all

ensure_event_loop()  # needed on Python 3.14+
agent = Agent(
    name="job_scout",
    seed=config.SCOUT_SEED,
    port=config.SCOUT_PORT,
    mailbox=config.USE_MAILBOX,
    endpoint=None if config.USE_MAILBOX else [f"http://127.0.0.1:{config.SCOUT_PORT}/submit"],
    description="Searches live job and internship APIs and returns normalized, deduplicated listings.",
)


def cache_key(q: JobQuery) -> str:
    raw = json.dumps([q.role.lower(), q.location.lower(), q.remote_only, q.kind], sort_keys=True)
    return "jobs:" + hashlib.sha1(raw.encode()).hexdigest()[:16]


@agent.on_message(model=JobQuery, replies={JobResults})
async def handle_query(ctx: Context, sender: str, q: JobQuery):
    key = cache_key(q)
    cached = ctx.storage.get(key)
    if cached and time.time() - cached["ts"] < config.JOB_CACHE_TTL_SECONDS:
        ctx.logger.info(f"Cache hit for '{q.role}' ({len(cached['jobs'])} jobs)")
        await ctx.send(sender, JobResults(
            session_id=q.session_id, jobs=[JobListing(**j) for j in cached["jobs"]],
            sources_ok=cached["ok"] + ["cache"], sources_failed=[]))
        return

    report = await search_all(q)
    ctx.logger.info(f"'{q.role}': {len(report.jobs)} jobs; ok={report.ok} failed={report.failed}")

    if report.jobs:
        ctx.storage.set(key, {"ts": time.time(), "jobs": [j.dict() for j in report.jobs], "ok": report.ok})
    elif cached:
        # Every live source failed: serve stale cache rather than nothing, and say so.
        ctx.logger.warning("All sources failed; serving stale cache")
        await ctx.send(sender, JobResults(
            session_id=q.session_id, jobs=[JobListing(**j) for j in cached["jobs"]],
            sources_ok=["stale-cache"], sources_failed=report.failed))
        return

    await ctx.send(sender, JobResults(
        session_id=q.session_id, jobs=report.jobs,
        sources_ok=report.ok, sources_failed=report.failed))


if __name__ == "__main__":
    print(f"Job Scout address: {agent.address}")
    agent.run()
