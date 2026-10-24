"""Message contracts shared by every agent.

Every agent imports from here. If you change a model, every agent that sends or
receives it must be restarted, because uAgents matches messages by schema digest.
"""

from uagents import Model


class ResumeRequest(Model):
    session_id: str
    resume_text: str


class ResumeProfile(Model):
    session_id: str
    name: str = ""
    skills: list[str] = []
    education: str = ""
    level: str = "student"  # student | fresher | experienced
    target_roles: list[str] = []
    summary: str = ""
    parsed_by: str = "llm"  # llm | heuristic  (shown in logs, useful for the demo)


class JobListing(Model):
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    source: str
    remote: bool = False
    is_internship: bool = False
    posted: str = ""
    salary: str = ""


class JobQuery(Model):
    session_id: str
    role: str
    location: str = ""
    remote_only: bool = False
    kind: str = "any"  # internship | job | any
    skills: list[str] = []
    limit: int = 30


class JobResults(Model):
    session_id: str
    jobs: list[JobListing] = []
    sources_ok: list[str] = []
    sources_failed: list[str] = []


class MatchRequest(Model):
    session_id: str
    profile: ResumeProfile
    jobs: list[JobListing]
    top_k: int = 5


class MatchResult(Model):
    job: JobListing
    score: int  # 0-100
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    reasons: list[str] = []


class MatchResults(Model):
    session_id: str
    matches: list[MatchResult] = []


class PackRequest(Model):
    session_id: str
    profile: ResumeProfile
    match: MatchResult
    resume_text: str = ""


class PackResult(Model):
    session_id: str
    job_id: str
    cover_letter: str
    resume_bullets: list[str] = []
    gap_plan: list[str] = []
    generated_by: str = "llm"  # llm | template
