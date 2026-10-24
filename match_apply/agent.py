"""Match & Apply agent: ranks jobs against a profile, and builds tailored Application Packs."""

from uagents import Agent, Context

from shared import config
from shared.loop import ensure_event_loop
from shared.models import MatchRequest, MatchResults, PackRequest, PackResult
from match_apply.matcher import rank_jobs
from match_apply.pack import build_pack

ensure_event_loop()  # needed on Python 3.14+
agent = Agent(
    name="match_apply",
    seed=config.MATCH_SEED,
    port=config.MATCH_PORT,
    mailbox=config.USE_MAILBOX,
    endpoint=None if config.USE_MAILBOX else [f"http://127.0.0.1:{config.MATCH_PORT}/submit"],
    description="Scores jobs against a resume profile with explanations, and writes tailored application packs.",
)


@agent.on_message(model=MatchRequest, replies={MatchResults})
async def handle_match(ctx: Context, sender: str, req: MatchRequest):
    matches = rank_jobs(req.profile, req.jobs, req.top_k)
    ctx.logger.info(f"Ranked {len(req.jobs)} jobs; top scores {[m.score for m in matches]}")
    await ctx.send(sender, MatchResults(session_id=req.session_id, matches=matches))


@agent.on_message(model=PackRequest, replies={PackResult})
async def handle_pack(ctx: Context, sender: str, req: PackRequest):
    ctx.logger.info(f"Building pack for {req.match.job.title} @ {req.match.job.company}")
    pack = await build_pack(req.session_id, req.profile, req.match, req.resume_text)
    await ctx.send(sender, pack)


if __name__ == "__main__":
    print(f"Match & Apply address: {agent.address}")
    agent.run()
