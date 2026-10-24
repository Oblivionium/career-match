"""Turn raw resume text into a structured ResumeProfile.

Primary path: ASI:One LLM with a strict JSON schema.
Fallback path: deterministic keyword extraction, so the agent still works without the LLM.
"""

import logging
import re

from shared.llm import LLMUnavailable, chat_json
from shared.models import ResumeProfile
from shared.skills import extract_skills, normalize_skills

log = logging.getLogger(__name__)

MAX_RESUME_CHARS = 12000

SYSTEM_PROMPT = """You extract structured data from student and early-career resumes.
Return ONLY a JSON object with exactly these keys:
{
  "name": string (empty if absent),
  "skills": array of short skill names (technologies, tools, languages, domains), max 25,
  "education": string, one line, highest/current degree and institution,
  "level": one of "student", "fresher", "experienced",
  "target_roles": array of 1-3 job titles this person is best suited for right now,
  "summary": string, one sentence describing the candidate
}
Rules: never invent skills that are not supported by the resume. Use "student" if they are
still studying, "fresher" if graduated with under 1 year of work, else "experienced"."""

ROLE_HINTS = [
    (["machine learning", "deep learning", "pytorch", "tensorflow", "nlp", "llms"], "Machine Learning Intern"),
    (["data analysis", "power bi", "tableau", "excel", "statistics"], "Data Analyst Intern"),
    (["react", "javascript", "html", "css", "next.js", "angular", "vue"], "Frontend Developer Intern"),
    (["node.js", "django", "flask", "fastapi", "spring", "rest apis", "sql"], "Backend Developer Intern"),
    (["android", "flutter", "kotlin", "swift"], "Mobile App Developer Intern"),
    (["docker", "kubernetes", "aws", "azure", "gcp", "linux"], "DevOps Intern"),
    (["figma", "ui/ux"], "UI/UX Design Intern"),
    (["cybersecurity"], "Security Analyst Intern"),
    (["blockchain"], "Blockchain Developer Intern"),
    (["marketing"], "Marketing Intern"),
]


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_RESUME_CHARS]


def looks_like_resume(text: str) -> bool:
    """Cheap check used by the coordinator to decide whether a chat message is a resume."""
    t = text.lower()
    if len(t) < 150:
        return False
    signals = ["education", "experience", "skills", "project", "university", "college",
               "b.tech", "btech", "bachelor", "cgpa", "gpa", "intern", "certification", "@"]
    return sum(s in t for s in signals) >= 2 or len(extract_skills(t)) >= 4


def heuristic_profile(session_id: str, text: str) -> ResumeProfile:
    low = text.lower()
    skills = extract_skills(text)

    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    name = first_line if (len(first_line.split()) <= 4 and not any(c.isdigit() for c in first_line)
                          and "@" not in first_line) else ""

    edu = ""
    for ln in text.splitlines():
        if re.search(r"b\.?\s?tech|b\.?e\b|bachelor|m\.?tech|master|b\.?sc|bca|mca|university|college|institute", ln, re.I):
            edu = ln.strip()[:150]
            break

    if re.search(r"\b(20\d\d)\s*[-–]\s*(present|current|expected)|pursuing|currently studying|expected graduation", low):
        level = "student"
    elif re.search(r"\b\d+\+?\s*years? of experience", low):
        level = "experienced"
    else:
        level = "student" if ("cgpa" in low or "semester" in low) else "fresher"

    skill_set = {s.lower() for s in skills}
    roles = []
    for needles, role in ROLE_HINTS:
        hits = sum(n in skill_set for n in needles)
        if hits:
            roles.append((hits, role))
    roles.sort(key=lambda r: -r[0])
    target = [r for _, r in roles[:3]] or ["Software Developer Intern"]
    if level == "experienced":
        target = [r.replace(" Intern", "") for r in target]

    return ResumeProfile(
        session_id=session_id, name=name, skills=skills, education=edu, level=level,
        target_roles=target,
        summary=f"{level.capitalize()} with skills in {', '.join(skills[:5]) or 'general areas'}.",
        parsed_by="heuristic",
    )


async def parse_resume(session_id: str, raw_text: str) -> ResumeProfile:
    text = clean_text(raw_text)
    try:
        data = await chat_json(SYSTEM_PROMPT, f"Resume:\n\"\"\"\n{text}\n\"\"\"")
        skills = normalize_skills([str(s) for s in data.get("skills", []) if str(s).strip()])[:25]
        # Merge in keyword hits the LLM may have missed, so matching has the full picture.
        for s in extract_skills(text):
            if s.lower() not in {x.lower() for x in skills}:
                skills.append(s)
        level = data.get("level", "student")
        if level not in {"student", "fresher", "experienced"}:
            level = "student"
        roles = [str(r) for r in data.get("target_roles", []) if str(r).strip()][:3]
        if not skills:
            raise ValueError("LLM returned no skills")
        return ResumeProfile(
            session_id=session_id,
            name=str(data.get("name", ""))[:80],
            skills=skills,
            education=str(data.get("education", ""))[:200],
            level=level,
            target_roles=roles or heuristic_profile(session_id, text).target_roles,
            summary=str(data.get("summary", ""))[:300],
            parsed_by="llm",
        )
    except (LLMUnavailable, ValueError, TypeError, AttributeError) as exc:
        log.warning("LLM resume parse failed (%s); using heuristic parser", exc)
        return heuristic_profile(session_id, text)
