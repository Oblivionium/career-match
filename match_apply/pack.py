"""Application Pack generation: tailored cover letter, resume bullet rewrites, gap plan."""

import logging

from shared.llm import LLMUnavailable, chat_json
from shared.models import MatchResult, PackResult, ResumeProfile

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a career coach writing for a student or early-career candidate.
Return ONLY a JSON object:
{
  "cover_letter": string, 180-250 words, specific to this job and company, first person,
                  no placeholders like [Your Name] except where the name is unknown,
  "resume_bullets": array of 3-5 strings, rewrites of the candidate's existing experience
                    phrased to match this job; never invent experience they don't have,
  "gap_plan": array of 2-4 strings, concrete steps (each doable within 1-2 weeks) to close
              the missing skills, e.g. a small project or a specific free course type
}
Be honest: if a skill is missing, the cover letter should not claim it."""


def template_pack(session_id: str, profile: ResumeProfile, match: MatchResult) -> PackResult:
    job = match.job
    name = profile.name or "[Your Name]"
    skills = ", ".join(match.matched_skills[:4]) or ", ".join(profile.skills[:4]) or "my technical skills"
    letter = (
        f"Dear Hiring Team at {job.company},\n\n"
        f"I am excited to apply for the {job.title} role. {profile.summary or ''} "
        f"My background in {skills} lines up closely with what this position needs, and I have "
        f"applied these skills in my projects and coursework.\n\n"
        f"I am particularly drawn to {job.company} because this role would let me contribute from "
        f"day one while growing in a team that ships real products. "
        + (f"I am also actively strengthening my {', '.join(match.missing_skills[:2])} skills so I can "
           f"ramp up quickly. " if match.missing_skills else "")
        + "\n\nThank you for your time and consideration. I would welcome the chance to discuss how "
        f"I can help.\n\nSincerely,\n{name}"
    )
    bullets = [f"Built projects using {s}, demonstrating hands-on ability relevant to {job.title}"
               for s in match.matched_skills[:3]] or [
        "Rewrite your strongest project bullet to start with an action verb and end with a measurable result"]
    gap = [f"Build a small weekend project that uses {s} and add it to your GitHub and resume"
           for s in match.missing_skills[:3]] or ["Your skills already cover this posting; focus on quantifying results"]
    return PackResult(session_id=session_id, job_id=job.id, cover_letter=letter,
                      resume_bullets=bullets, gap_plan=gap, generated_by="template")


async def build_pack(session_id: str, profile: ResumeProfile, match: MatchResult,
                     resume_text: str = "") -> PackResult:
    job = match.job
    user = (
        f"JOB: {job.title} at {job.company} ({job.location})\n"
        f"JOB DESCRIPTION:\n{job.description[:2500]}\n\n"
        f"CANDIDATE: {profile.name or 'unknown name'}, level={profile.level}, education={profile.education}\n"
        f"SKILLS: {', '.join(profile.skills)}\n"
        f"MATCHED SKILLS: {', '.join(match.matched_skills)}\n"
        f"MISSING SKILLS: {', '.join(match.missing_skills)}\n"
        f"RESUME TEXT:\n{resume_text[:5000]}"
    )
    try:
        data = await chat_json(SYSTEM_PROMPT, user, temperature=0.5, max_tokens=1500)
        letter = str(data.get("cover_letter", "")).strip()
        if len(letter) < 100:
            raise ValueError("cover letter too short")
        return PackResult(
            session_id=session_id, job_id=job.id, cover_letter=letter,
            resume_bullets=[str(b) for b in data.get("resume_bullets", [])][:5],
            gap_plan=[str(g) for g in data.get("gap_plan", [])][:4],
            generated_by="llm",
        )
    except (LLMUnavailable, ValueError, TypeError, AttributeError) as exc:
        log.warning("LLM pack generation failed (%s); using template", exc)
        return template_pack(session_id, profile, match)
