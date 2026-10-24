"""Turn an incoming chat text into an intent.

Card selections arrive in two forms (per ASI:One docs):
  * JSON string, when the user @mentions our agent directly
  * natural-language prose, when ASI:One's planner relays the selection
We also accept typed commands so the flow works even if a card fails to render.
"""

import json
import re

from resume_analyst.parser import looks_like_resume

JOB_ID_RE = re.compile(r"\bjob_[0-9a-f]{10}\b")
ACTIONS = ["submit_prefs", "view_job", "request_pack", "confirm_pack", "back_to_results"]


def _num(text: str) -> int | None:
    m = re.search(r"\b(\d{1,2})\b", text)
    return int(m.group(1)) if m else None


def parse_search_command(text: str) -> dict:
    """'search ml intern in bangalore remote' -> prefs dict."""
    body = re.sub(r"^\s*(search|find|look for)\s+(for\s+)?", "", text, flags=re.I).strip()
    remote = bool(re.search(r"\bremote\b", body, re.I))
    body = re.sub(r"\bremote(ly)?\b|\bonly\b", "", body, flags=re.I)
    kind = "any"
    if re.search(r"\bintern(ship)?s?\b", body, re.I):
        kind = "internship"
    elif re.search(r"\b(full[- ]time|jobs?)\b", body, re.I):
        kind = "job"
    location = ""
    m = re.search(r"\b(?:in|at|near)\s+([A-Za-z][A-Za-z .-]{1,40})$", body.strip())
    if m:
        location = m.group(1).strip()
        body = body[: m.start()]
    role = re.sub(r"\s+", " ", re.sub(r"\b(jobs?|full[- ]time)\b", "", body, flags=re.I)).strip(" ,.")
    return {"action": "submit_prefs", "role": role, "location": location,
            "kind": kind, "remote": remote}


def _form_from_prose(text: str) -> dict:
    out: dict = {"action": "submit_prefs"}
    for field in ("role", "location", "kind"):
        m = re.search(rf"\b{field}\b\W{{0,4}}(?:is|of|=|:)?\s*['\"]?([^,;'\"\n]+)", text, re.I)
        if m:
            val = m.group(1).strip().rstrip(".")
            val = re.split(r"\s+(?:and|with)\s+(?:location|kind|remote|role)\b", val, flags=re.I)[0]
            out[field] = val.strip()
    rm = re.search(r"\bremote\b\W{0,4}(?:is|=|:)?\s*(true|false|yes|no|checked|unchecked)", text, re.I)
    if rm:
        out["remote"] = rm.group(1).lower() in {"true", "yes", "checked"}
    elif re.search(r"\bremote only\b", text, re.I):
        out["remote"] = True
    if out.get("kind", "").lower() not in {"internship", "job", "any"}:
        k = out.get("kind", "").lower()
        out["kind"] = "internship" if "intern" in k else ("job" if "job" in k or "full" in k else "any")
    return out


def parse_intent(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {"action": "empty"}

    # 1) JSON selection from a card (direct @mention)
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("action"):
                return data
        except json.JSONDecodeError:
            pass

    low = raw.lower()

    # 2) Prose relayed by the ASI:One planner (contains our action ids / job ids)
    action = next((a for a in ACTIONS if a in low), None)
    if action:
        if action == "submit_prefs":
            return _form_from_prose(raw)
        out = {"action": action}
        jid = JOB_ID_RE.search(low)
        if jid:
            out["job_id"] = jid.group(0)
        return out

    # 3) A resume (check before short commands: resumes contain words like "search")
    if looks_like_resume(raw):
        return {"action": "resume", "text": raw}

    # 4) Typed commands (fallback when cards don't render)
    if re.match(r"^(forget me|delete my data|reset)\b", low):
        return {"action": "forget"}
    if re.match(r"^(help|\?|what can you do)", low):
        return {"action": "help"}
    if re.match(r"^(back|results|show results|go back)\b", low):
        return {"action": "back_to_results"}
    if re.match(r"^(confirm|yes|buy|pay|ok(ay)?)\b", low):
        return {"action": "confirm_pack"}
    if re.match(r"^(pack|cover letter|apply)\b", low):
        return {"action": "request_pack", "index": _num(low)}
    if re.match(r"^(view|details?|show|open)\b", low) or re.fullmatch(r"\d{1,2}", low):
        return {"action": "view_job", "index": _num(low)}
    if re.match(r"^(search|find|look for)\b", low):
        return parse_search_command(raw)

    return {"action": "chat", "text": raw}
