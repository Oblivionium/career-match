"""Resume Analyst agent: ResumeRequest -> ResumeProfile."""

from uagents import Agent, Context

from shared import config
from shared.loop import ensure_event_loop
from shared.models import ResumeProfile, ResumeRequest
from resume_analyst.parser import parse_resume

ensure_event_loop()  # needed on Python 3.14+
agent = Agent(
    name="resume_analyst",
    seed=config.RESUME_SEED,
    port=config.RESUME_PORT,
    mailbox=config.USE_MAILBOX,
    endpoint=None if config.USE_MAILBOX else [f"http://127.0.0.1:{config.RESUME_PORT}/submit"],
    description="Extracts skills, education, level and suitable roles from a student resume.",
)


@agent.on_message(model=ResumeRequest, replies={ResumeProfile})
async def handle_resume(ctx: Context, sender: str, msg: ResumeRequest):
    ctx.logger.info(f"Parsing resume for session {msg.session_id[:12]}… ({len(msg.resume_text)} chars)")
    profile = await parse_resume(msg.session_id, msg.resume_text)
    ctx.logger.info(f"Parsed via {profile.parsed_by}: {len(profile.skills)} skills, roles={profile.target_roles}")
    await ctx.send(sender, profile)


if __name__ == "__main__":
    print(f"Resume Analyst address: {agent.address}")
    agent.run()
