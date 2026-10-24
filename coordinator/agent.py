"""Career Coordinator: the ASI:One-facing agent.

Implements the Agent Chat Protocol, drives the Interactive Card flow, orchestrates the
three worker agents, and sells the Application Pack through the Agent Payment Protocol.

If a worker agent is unreachable, the coordinator falls back to running that step's logic
locally, so the user still gets an answer (and the logs show the degradation).
"""

import re
from datetime import datetime, timezone

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from shared import config
from shared.loop import ensure_event_loop
from shared.models import (
    JobQuery, JobResults, MatchRequest, MatchResult, MatchResults,
    PackRequest, PackResult, ResumeProfile, ResumeRequest,
)
from coordinator import cards, payments
from coordinator.selection import parse_intent

ensure_event_loop()  # needed on Python 3.14+
agent = Agent(
    name="career_coordinator",
    seed=config.COORD_SEED,
    port=config.COORD_PORT,
    mailbox=config.USE_MAILBOX,
    endpoint=None if config.USE_MAILBOX else [f"http://127.0.0.1:{config.COORD_PORT}/submit"],
    description=(
        "Finds internships and jobs that fit a student's resume. Paste your resume and get live, "
        "ranked matches with skill gaps, plus a tailored application pack."
    ),
)
chat_proto = Protocol(spec=chat_protocol_spec)
ROLEISH_RE = re.compile(r"intern|job|developer|engineer|analyst|designer|scientist|manager|"
                        r"marketing|\b(?:in|remote)\b", re.I)

WELCOME = (
    "Hi! I find internships and jobs that actually fit your resume.\n\n"
    "1. Paste your resume text here (copy it from your PDF or doc).\n"
    "2. I'll pull out your skills, search live listings, and rank them with reasons.\n"
    "3. For any job, I can write a tailored Application Pack: cover letter, resume bullets, "
    "and a plan to close your skill gaps.\n\n"
    "Commands: \"search <role> in <city>\", \"view 2\", \"pack 2\", \"back\", \"forget me\"."
)


# ---- session state -----------------------------------------------------------------------
def load(ctx: Context, user: str) -> dict:
    return ctx.storage.get(f"s:{user}") or {}


def save(ctx: Context, user: str, state: dict) -> None:
    state["updated"] = datetime.now(timezone.utc).isoformat()
    ctx.storage.set(f"s:{user}", state)


async def reply(ctx: Context, user: str, msg: ChatMessage) -> None:
    await ctx.send(user, msg)


async def say(ctx: Context, user: str, text: str) -> None:
    await ctx.send(user, cards.text_message(text))


# ---- worker calls with local fallback -----------------------------------------------------
async def get_profile(ctx: Context, user: str, text: str) -> ResumeProfile:
    resp, status = await ctx.send_and_receive(
        config.RESUME_ADDR, ResumeRequest(session_id=user, resume_text=text),
        response_type=ResumeProfile, timeout=config.WORKER_TIMEOUT)
    if isinstance(resp, ResumeProfile):
        return resp
    ctx.logger.warning(f"Resume Analyst unavailable ({status.detail}); parsing locally")
    from resume_analyst.parser import parse_resume
    return await parse_resume(user, text)


async def get_jobs(ctx: Context, q: JobQuery) -> JobResults:
    resp, status = await ctx.send_and_receive(
        config.SCOUT_ADDR, q, response_type=JobResults, timeout=config.WORKER_TIMEOUT)
    if isinstance(resp, JobResults):
        return resp
    ctx.logger.warning(f"Job Scout unavailable ({status.detail}); searching locally")
    from job_scout.sources import search_all
    rep = await search_all(q)
    return JobResults(session_id=q.session_id, jobs=rep.jobs,
                      sources_ok=rep.ok, sources_failed=rep.failed + ["job-scout-agent"])


async def get_matches(ctx: Context, req: MatchRequest) -> list[MatchResult]:
    resp, status = await ctx.send_and_receive(
        config.MATCH_ADDR, req, response_type=MatchResults, timeout=config.WORKER_TIMEOUT)
    if isinstance(resp, MatchResults):
        return resp.matches
    ctx.logger.warning(f"Match agent unavailable ({status.detail}); ranking locally")
    from match_apply.matcher import rank_jobs
    return rank_jobs(req.profile, req.jobs, req.top_k)


async def get_pack(ctx: Context, req: PackRequest) -> PackResult:
    resp, status = await ctx.send_and_receive(
        config.MATCH_ADDR, req, response_type=PackResult, timeout=config.WORKER_TIMEOUT + 30)
    if isinstance(resp, PackResult):
        return resp
    ctx.logger.warning(f"Match agent unavailable for pack ({status.detail}); building locally")
    from match_apply.pack import build_pack
    return await build_pack(req.session_id, req.profile, req.match, req.resume_text)


# ---- helpers ------------------------------------------------------------------------------
def find_match(state: dict, job_id: str | None = None, index: int | None = None) -> MatchResult | None:
    matches = [MatchResult(**m) for m in state.get("matches", [])]
    if job_id:
        return next((m for m in matches if m.job.id == job_id), None)
    if index and 1 <= index <= len(matches):
        return matches[index - 1]
    if state.get("current_job"):
        return next((m for m in matches if m.job.id == state["current_job"]), None)
    return None


def source_note(res: JobResults) -> str:
    failed = [s for s in res.sources_failed if s]
    if not failed:
        return ""
    return (f"(Note: {', '.join(failed)} didn't respond, so these come from "
            f"{', '.join(res.sources_ok) or 'cached results'}.)")


# ---- flow steps ---------------------------------------------------------------------------
async def handle_resume(ctx: Context, user: str, text: str) -> None:
    await say(ctx, user, "Reading your resume…")
    profile = await get_profile(ctx, user, text)
    state = load(ctx, user)
    state.update({"resume_text": text[:12000], "profile": profile.dict(), "matches": [], "current_job": None})
    save(ctx, user, state)
    await reply(ctx, user, cards.prefs_form(profile))


async def handle_search(ctx: Context, user: str, sel: dict) -> None:
    state = load(ctx, user)
    if not state.get("profile"):
        await say(ctx, user, "Paste your resume first, then I can search for roles that fit it.")
        return
    profile = ResumeProfile(**state["profile"])
    role = (sel.get("role") or "").strip() or (profile.target_roles[0] if profile.target_roles else "software developer")
    kind = sel.get("kind") if sel.get("kind") in {"internship", "job", "any"} else "any"
    remote = sel.get("remote") in (True, "true", "on", "yes", "1")
    q = JobQuery(session_id=user, role=role, location=(sel.get("location") or "").strip(),
                 remote_only=remote, kind=kind, skills=profile.skills)
    state["prefs"] = q.dict()
    save(ctx, user, state)

    await say(ctx, user, f"Searching live listings for \"{role}\"…")
    res = await get_jobs(ctx, q)
    if not res.jobs:
        hint = " Some sources were down, try again in a minute." if res.sources_failed else ""
        await say(ctx, user, f"I couldn't find live listings for \"{role}\"{' in ' + q.location if q.location else ''}."
                             f"{hint} Try a broader role or no city, e.g. \"search python intern\".")
        return

    matches = await get_matches(ctx, MatchRequest(session_id=user, profile=profile, jobs=res.jobs, top_k=5))
    state["matches"] = [m.dict() for m in matches]
    state["current_job"] = None
    save(ctx, user, state)
    await reply(ctx, user, cards.results_carousel(matches, role, source_note(res)))


async def handle_view(ctx: Context, user: str, sel: dict) -> None:
    state = load(ctx, user)
    m = find_match(state, sel.get("job_id"), sel.get("index"))
    if not m:
        await say(ctx, user, "I couldn't find that job in your current results. Type \"back\" to see them.")
        return
    state["current_job"] = m.job.id
    save(ctx, user, state)
    await reply(ctx, user, cards.job_detail(m))


async def handle_request_pack(ctx: Context, user: str, sel: dict) -> None:
    state = load(ctx, user)
    m = find_match(state, sel.get("job_id"), sel.get("index"))
    if not m:
        await say(ctx, user, "Pick a job first: type \"view 1\" (or tap a result card).")
        return
    state["current_job"] = m.job.id
    save(ctx, user, state)
    await reply(ctx, user, cards.pack_review(m))


async def deliver_pack(ctx: Context, user: str, job_id: str) -> None:
    state = load(ctx, user)
    m = find_match(state, job_id)
    if not m or not state.get("profile"):
        await say(ctx, user, "Your session expired before I could build the pack. Paste your resume again "
                             "and I'll rebuild it; your payment reference is saved in my logs.")
        ctx.logger.error(f"Pack delivery failed: missing session for {user[:16]} job {job_id}")
        return
    await say(ctx, user, "Writing your Application Pack…")
    pack = await get_pack(ctx, PackRequest(session_id=user, profile=ResumeProfile(**state["profile"]),
                                           match=m, resume_text=state.get("resume_text", "")))
    await say(ctx, user, cards.pack_text(m, pack.cover_letter, pack.resume_bullets, pack.gap_plan))


async def handle_confirm(ctx: Context, user: str, sel: dict) -> None:
    state = load(ctx, user)
    m = find_match(state, sel.get("job_id"))
    if not m:
        await say(ctx, user, "Pick a job first: type \"view 1\", then \"pack\".")
        return
    if not config.PAYMENTS_ENABLED:
        await deliver_pack(ctx, user, m.job.id)
        return
    await payments.request_pack_payment(ctx, user, m.job.id, m.job.title)
    await say(ctx, user, f"I've sent a payment request for {config.PACK_PRICE_FET} FET"
                         f"{' (testnet)' if config.FET_USE_TESTNET else ''}. Approve it and your pack "
                         "will arrive right after the payment is verified on-chain.")


async def on_paid(ctx: Context, user: str, pending: dict) -> None:
    await say(ctx, user, "Payment verified on-chain. Thank you!")
    await deliver_pack(ctx, user, pending["job_id"])


async def on_declined(ctx: Context, user: str, pending: dict, why: str) -> None:
    if why == "verification_failed":
        await say(ctx, user, "I couldn't verify that payment on-chain, so you haven't been charged for the pack. "
                             "If FET left your wallet, reply with the transaction hash and I'll recheck.")
    else:
        await say(ctx, user, "No problem, no payment taken. Your matches are still here: type \"back\".")


payments.on_paid = on_paid
payments.on_declined = on_declined


# ---- chat protocol -------------------------------------------------------------------------
@chat_proto.on_message(ChatMessage)
async def handle_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc),
                                               acknowledged_msg_id=msg.msg_id))
    text = "\n".join(c.text for c in msg.content if isinstance(c, TextContent)).strip()
    if not text:
        return  # start-session / metadata-only messages
    sel = parse_intent(text)
    action = sel.get("action")
    ctx.logger.info(f"[{sender[:14]}…] action={action}")

    try:
        if action == "resume":
            await handle_resume(ctx, sender, sel["text"])
        elif action == "submit_prefs":
            await handle_search(ctx, sender, sel)
        elif action == "view_job":
            await handle_view(ctx, sender, sel)
        elif action == "request_pack":
            await handle_request_pack(ctx, sender, sel)
        elif action == "confirm_pack":
            await handle_confirm(ctx, sender, sel)
        elif action == "back_to_results":
            state = load(ctx, sender)
            if state.get("matches"):
                ms = [MatchResult(**m) for m in state["matches"]]
                await reply(ctx, sender, cards.results_carousel(ms, (state.get("prefs") or {}).get("role", "your search")))
            else:
                await say(ctx, sender, "No results yet. Paste your resume to start.")
        elif action == "forget":
            ctx.storage.remove(f"s:{sender}")
            await say(ctx, sender, "Done. I've deleted your resume and results from my storage.")
        elif (action == "chat" and load(ctx, sender).get("profile") and len(text) < 150
              and ROLEISH_RE.search(text)):
            # With a resume on file, short free text is treated as a new search ("data analyst in Pune").
            from coordinator.selection import parse_search_command
            await handle_search(ctx, sender, parse_search_command("search " + text))
        else:
            await say(ctx, sender, WELCOME)
    except Exception as exc:  # noqa: BLE001 - never leave the user hanging
        ctx.logger.exception(f"Unhandled error for action {action}: {exc}")
        await say(ctx, sender, "Something went wrong on my side. Please try that again; "
                               "your resume and results are still saved.")


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(chat_proto, publish_manifest=True)
agent.include(payments.payment_proto, publish_manifest=True)


if __name__ == "__main__":
    print(f"Career Coordinator address: {agent.address}")
    print(f"Payment wallet: {config.PAYMENT_WALLET or agent.wallet.address()}")
    agent.run()
