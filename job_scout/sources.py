"""Live job/internship sources. Each source returns normalized JobListing objects.

Sources without an API key are skipped (not counted as failures). Every source runs in
parallel with a timeout and retries, so one slow or broken API never blocks the others.
"""

import asyncio
import hashlib
import html
import logging
import re
from dataclasses import dataclass, field

import httpx

from shared import config
from shared.models import JobListing, JobQuery
from shared.retry import with_retry

log = logging.getLogger(__name__)

HTTP_TIMEOUT = 15.0
USER_AGENT = "CareerMatchAgent/1.0 (Fetch.ai ASI:One hackathon project)"
INTERN_RE = re.compile(r"\b(intern|internship|trainee|apprentice|graduate program|fresher|entry[- ]level)\b", re.I)


def strip_html(text: str, limit: int = 1500) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def make_id(source: str, raw_id: str) -> str:
    return "job_" + hashlib.sha1(f"{source}:{raw_id}".encode()).hexdigest()[:10]


def is_internship(title: str, extra: str = "") -> bool:
    return bool(INTERN_RE.search(title) or INTERN_RE.search(extra))


class SourceSkipped(Exception):
    """Raised when a source isn't configured; not treated as a failure."""


@dataclass
class SourceReport:
    jobs: list[JobListing] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def _search_terms(q: JobQuery) -> str:
    role = q.role.strip() or "software"
    # Strip "intern"/"internship" from the role for broader keyword search; we filter later.
    core = re.sub(r"\b(intern|internship)\b", "", role, flags=re.I).strip() or role
    if q.kind == "internship":
        return f"{core} intern"
    return core


async def _get_json(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict | list:
    async def _call():
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as c:
            r = await c.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()
    return await with_retry(_call, attempts=2, label=url.split("/")[2])


# --- Adzuna (needs free app_id/app_key; good India coverage) ---------------------------
async def fetch_adzuna(q: JobQuery) -> list[JobListing]:
    if not (config.ADZUNA_APP_ID and config.ADZUNA_APP_KEY):
        raise SourceSkipped
    params = {
        "app_id": config.ADZUNA_APP_ID, "app_key": config.ADZUNA_APP_KEY,
        "what": _search_terms(q), "results_per_page": 25, "content-type": "application/json",
    }
    if q.location and not q.remote_only:
        params["where"] = q.location
    data = await _get_json(
        f"https://api.adzuna.com/v1/api/jobs/{config.ADZUNA_COUNTRY}/search/1", params=params)
    out = []
    for j in data.get("results", []):
        title = j.get("title", "")
        desc = strip_html(j.get("description", ""))
        sal = ""
        if j.get("salary_min"):
            sal = f"{int(j['salary_min']):,}" + (f"–{int(j['salary_max']):,}" if j.get("salary_max") else "")
        out.append(JobListing(
            id=make_id("adzuna", str(j.get("id"))), title=strip_html(title, 140),
            company=(j.get("company") or {}).get("display_name", "Unknown"),
            location=(j.get("location") or {}).get("display_name", ""),
            url=j.get("redirect_url", ""), description=desc, source="Adzuna",
            remote="remote" in (title + desc).lower(), is_internship=is_internship(title, desc[:200]),
            posted=(j.get("created") or "")[:10], salary=sal,
        ))
    return out


# --- JSearch via RapidAPI (aggregates Google for Jobs: LinkedIn, Indeed, etc.) ----------
async def fetch_jsearch(q: JobQuery) -> list[JobListing]:
    if not config.JSEARCH_API_KEY:
        raise SourceSkipped
    query = _search_terms(q) + (f" in {q.location}" if q.location and not q.remote_only else "")
    params = {"query": query, "page": "1", "num_pages": "1"}
    if q.remote_only:
        params["remote_jobs_only"] = "true"
    if q.kind == "internship":
        params["employment_types"] = "INTERN"
    data = await _get_json(
        "https://jsearch.p.rapidapi.com/search", params=params,
        headers={"X-RapidAPI-Key": config.JSEARCH_API_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"})
    out = []
    for j in data.get("data", []):
        title = j.get("job_title", "")
        loc = ", ".join(x for x in [j.get("job_city"), j.get("job_country")] if x)
        out.append(JobListing(
            id=make_id("jsearch", str(j.get("job_id"))), title=title,
            company=j.get("employer_name") or "Unknown", location=loc or "—",
            url=j.get("job_apply_link") or "", description=strip_html(j.get("job_description", "")),
            source="JSearch", remote=bool(j.get("job_is_remote")),
            is_internship=(j.get("job_employment_type") or "").upper() == "INTERN" or is_internship(title),
            posted=(j.get("job_posted_at_datetime_utc") or "")[:10],
        ))
    return out


# --- Remotive (free, no key; remote jobs; please keep request volume low + credit them) --
async def fetch_remotive(q: JobQuery) -> list[JobListing]:
    data = await _get_json("https://remotive.com/api/remote-jobs",
                           params={"search": _search_terms(q).replace(" intern", ""), "limit": 30})
    out = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        desc = strip_html(j.get("description", ""))
        out.append(JobListing(
            id=make_id("remotive", str(j.get("id"))), title=title,
            company=j.get("company_name") or "Unknown",
            location=j.get("candidate_required_location") or "Remote",
            url=j.get("url", ""), description=desc, source="Remotive", remote=True,
            is_internship=is_internship(title, j.get("job_type", "")),
            posted=(j.get("publication_date") or "")[:10], salary=j.get("salary") or "",
        ))
    return out


# --- Arbeitnow (free, no key; mostly Europe, includes remote) ---------------------------
async def fetch_arbeitnow(q: JobQuery) -> list[JobListing]:
    data = await _get_json("https://www.arbeitnow.com/api/job-board-api")
    terms = [t for t in re.split(r"\W+", _search_terms(q).lower()) if len(t) > 2 and t != "intern"]
    out = []
    for j in data.get("data", []):
        title = j.get("title", "")
        hay = (title + " " + " ".join(j.get("tags", []))).lower()
        if terms and not any(t in hay for t in terms):
            continue
        out.append(JobListing(
            id=make_id("arbeitnow", str(j.get("slug"))), title=title,
            company=j.get("company_name") or "Unknown", location=j.get("location") or "",
            url=j.get("url", ""), description=strip_html(j.get("description", "")),
            source="Arbeitnow", remote=bool(j.get("remote")),
            is_internship=is_internship(title, " ".join(j.get("job_types", []))),
        ))
    return out


SOURCES = {
    "adzuna": fetch_adzuna,
    "jsearch": fetch_jsearch,
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
}


async def _run_source(name: str, fn, q: JobQuery) -> tuple[str, list[JobListing] | None, str]:
    """Returns (name, jobs or None on failure, status) where status is ok|failed|skipped."""
    if name in config.SIMULATE_SOURCE_FAILURE:
        log.warning("Simulating failure of source %s", name)
        return name, None, "failed"
    try:
        jobs = await asyncio.wait_for(fn(q), timeout=HTTP_TIMEOUT * 2.5)
        return name, jobs, "ok"
    except SourceSkipped:
        return name, None, "skipped"
    except Exception as exc:  # noqa: BLE001
        log.warning("Source %s failed: %s", name, exc)
        return name, None, "failed"


def _filter(jobs: list[JobListing], q: JobQuery) -> list[JobListing]:
    out = jobs
    if q.remote_only:
        out = [j for j in out if j.remote]
    if q.kind == "internship":
        interns = [j for j in out if j.is_internship]
        # If the market has few labelled internships, keep entry-level roles too rather than nothing.
        out = interns if len(interns) >= 3 else interns + [j for j in out if not j.is_internship]
    elif q.kind == "job":
        out = [j for j in out if not j.is_internship] or out
    return out


def dedupe(jobs: list[JobListing]) -> list[JobListing]:
    seen, out = set(), []
    for j in jobs:
        key = (re.sub(r"\W+", "", j.title.lower()), re.sub(r"\W+", "", j.company.lower()))
        if key in seen or not j.url:
            continue
        seen.add(key)
        out.append(j)
    return out


async def search_all(q: JobQuery, sources: dict | None = None) -> SourceReport:
    sources = sources or SOURCES
    results = await asyncio.gather(*(_run_source(n, fn, q) for n, fn in sources.items()))
    report = SourceReport()
    collected: list[JobListing] = []
    for name, jobs, status in results:
        if status == "ok":
            report.ok.append(name)
            collected.extend(jobs or [])
        elif status == "failed":
            report.failed.append(name)
    report.jobs = _filter(dedupe(collected), q)[: q.limit]
    return report
