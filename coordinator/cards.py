"""ASI:One Interactive Card builders (predefined schemas: form, carousel, detail, review).

Every card is paired with a plain-text version, because ASI:One silently falls back to the
text when a card fails validation. Users can also type commands ("view 2", "pack 2").
Preview payloads at https://asi1.ai/developer/card-playground before changing them.
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

from shared import config
from shared.models import MatchResult, ResumeProfile

MAX_PAYLOAD_BYTES = 64_000


def text_message(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        from uagents_core.contrib.protocols.chat import EndSessionContent
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content)


def card_message(text: str, kind: str, payload: dict) -> ChatMessage:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode()) > MAX_PAYLOAD_BYTES:
        return text_message(text)
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=text),
            MetadataContent(type="metadata", metadata={
                "card_protocol_version": "1",
                "requires_card_interaction": "true",
                "card_kind": kind,
                "card_payload": raw,
            }),
        ],
    )


def _short(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# --- form: search preferences ---------------------------------------------------------
def prefs_form(profile: ResumeProfile) -> ChatMessage:
    default_role = profile.target_roles[0] if profile.target_roles else "Software Developer Intern"
    skills = ", ".join(profile.skills[:8]) or "none detected"
    text = (
        f"I read your resume. Skills I found: {skills}.\n"
        f"Best-fit roles: {', '.join(profile.target_roles) or default_role}.\n\n"
        f"Tell me what to search for. (Typing works too, e.g. \"search {default_role} in Bangalore\" "
        f"or \"search {default_role} remote\".)"
    )
    payload = {
        "title": "What should I search for?",
        "fields": [
            {"name": "role", "kind": "text", "label": f"Role (suggested: {default_role})", "required": True},
            {"name": "location", "kind": "text", "label": "City (leave empty for anywhere)", "required": False},
            {"name": "kind", "kind": "select", "label": "Type", "required": True, "options": [
                {"value": "internship", "label": "Internship"},
                {"value": "job", "label": "Full-time job"},
                {"value": "any", "label": "Either"},
            ]},
            {"name": "remote", "kind": "checkbox", "label": "Remote only", "required": False},
        ],
        "submit_cta": {"label": "Find matches", "selection": {"action": "submit_prefs"}},
    }
    return card_message(text, "form", payload)


# --- carousel: top matches ---------------------------------------------------------------
def results_carousel(matches: list[MatchResult], role: str, note: str = "") -> ChatMessage:
    lines = [f"Top {len(matches)} matches for \"{role}\":"]
    items = []
    for i, m in enumerate(matches, 1):
        j = m.job
        lines.append(f"{i}. {j.title} at {j.company} ({j.location or 'n/a'}): {m.score}% match")
        badges = [{"label": f"{m.score}% match", "variant": "info"}]
        if j.is_internship:
            badges.append({"label": "Internship", "variant": "info"})
        if j.remote:
            badges.append({"label": "Remote", "variant": "info"})
        items.append({
            "id": j.id,
            "title": _short(f"{j.title}", 80),
            "subtitle": _short(f"{j.company} · {j.location or 'Location n/a'}", 80),
            "badges": badges,
            "secondary_text": _short(
                f"Have: {', '.join(m.matched_skills[:3])}" if m.matched_skills else f"Source: {j.source}", 60),
            "primary_cta": {"label": "Details", "selection": {"action": "view_job", "job_id": j.id}},
        })
    lines.append("\nTap a card, or type \"view 1\" for details / \"pack 1\" for a tailored application pack.")
    if note:
        lines.append(note)
    payload = {"title": "Your best matches", "subtitle": _short(role, 60), "items": items}
    return card_message("\n".join(lines), "carousel", payload)


# --- detail: one job, with why it matches + gaps ----------------------------------------
def job_detail(m: MatchResult) -> ChatMessage:
    j = m.job
    rows = [
        {"label": "Company", "value": _short(j.company, 60)},
        {"label": "Location", "value": _short(j.location or "n/a", 60)},
        {"label": "Match", "value": f"{m.score}%"},
        {"label": "You have", "value": _short(", ".join(m.matched_skills) or "—", 120)},
        {"label": "Missing", "value": _short(", ".join(m.missing_skills) or "Nothing major", 120)},
        {"label": "Source", "value": j.source + (f" · posted {j.posted}" if j.posted else "")},
    ]
    if j.salary:
        rows.append({"label": "Pay", "value": _short(j.salary, 60)})
    why = "\n".join(f"• {r}" for r in m.reasons) or "• General fit"
    text = (
        f"{j.title} at {j.company}: {m.score}% match\n{why}\n"
        f"Missing skills: {', '.join(m.missing_skills) or 'none major'}\n"
        f"Apply: {j.url}"
    )
    payload = {
        "title": _short(f"{j.title} · {j.company}", 90),
        "summary_rows": rows,
        "ctas": [
            {"label": "Get Application Pack", "selection": {"action": "request_pack", "job_id": j.id},
             "primary": True},
            {"label": "Back to results", "selection": {"action": "back_to_results"}},
        ],
    }
    return card_message(text, "detail", payload)


# --- review: confirm paid pack ------------------------------------------------------------
def pack_review(m: MatchResult) -> ChatMessage:
    price = f"{config.PACK_PRICE_FET} FET" + (" (testnet)" if config.FET_USE_TESTNET else "")
    if not config.PAYMENTS_ENABLED:
        price = "Free (payments disabled)"
    text = (
        f"Application Pack for {m.job.title} at {m.job.company}: a tailored cover letter, "
        f"resume bullet rewrites for this role, and a plan to close your skill gaps. Price: {price}.\n"
        "Type \"confirm\" to continue or \"back\" to return to results."
    )
    payload = {
        "title": "Get your Application Pack",
        "summary_rows": [
            {"label": "Job", "value": _short(m.job.title, 80)},
            {"label": "Company", "value": _short(m.job.company, 60)},
            {"label": "Includes", "value": "Cover letter · Resume bullets · Skill-gap plan"},
            {"label": "Price", "value": price},
        ],
        "approve_cta": {"label": "Confirm", "selection": {"action": "confirm_pack", "job_id": m.job.id},
                        "primary": True},
        "reject_cta": {"label": "Not now", "selection": {"action": "back_to_results"}},
    }
    return card_message(text, "review", payload)


def pack_text(m: MatchResult, cover_letter: str, bullets: list[str], gaps: list[str]) -> str:
    parts = [
        f"Your Application Pack: {m.job.title} at {m.job.company}",
        "",
        "COVER LETTER",
        cover_letter,
        "",
        "RESUME BULLETS FOR THIS ROLE",
        *[f"• {b}" for b in bullets],
        "",
        "PLAN TO CLOSE YOUR GAPS",
        *[f"• {g}" for g in gaps],
        "",
        f"Apply here: {m.job.url}",
        "",
        "Want another? Type \"back\" for your matches, or paste a new resume.",
    ]
    return "\n".join(parts)
