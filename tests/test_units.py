import asyncio
import json

import pytest

from coordinator import cards
from coordinator.payments import _transfer_matches, to_base_units
from coordinator.selection import parse_intent
from job_scout import sources
from match_apply.matcher import rank_jobs, score_job
from match_apply.pack import build_pack, template_pack
from resume_analyst.parser import looks_like_resume, parse_resume
from shared.llm import extract_json
from shared.models import JobQuery, MatchResult
from shared.skills import extract_skills
from tests.fixtures import JOBS, RESUME_STRONG, RESUME_WEAK


def run(coro):
    return asyncio.run(coro)


# ---- skills / parsing ---------------------------------------------------------------
def test_extract_skills_avoids_false_positives():
    s = extract_skills("Please rest, spring internship, express interest. We use Python and React.")
    assert "Python" in s and "React" in s
    assert "REST APIs" not in s and "Spring" not in s and "Node.js" not in s


def test_heuristic_parse_strong_resume():
    p = run(parse_resume("u1", RESUME_STRONG))  # no API key -> heuristic path
    assert p.parsed_by == "heuristic"
    assert {"Python", "PyTorch", "SQL", "Docker"} <= set(p.skills)
    assert p.level == "student"
    assert p.name == "Priya Sharma"
    assert any("Machine Learning" in r for r in p.target_roles)


def test_looks_like_resume():
    assert looks_like_resume(RESUME_STRONG)
    assert looks_like_resume(RESUME_WEAK)
    assert not looks_like_resume("find me python internships in pune")


def test_extract_json_handles_fences_and_chatter():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('here you go {"b": [1,2]} thanks') == {"b": [1, 2]}


# ---- matching ----------------------------------------------------------------------
def test_ranking_prefers_fitting_internship():
    p = run(parse_resume("u1", RESUME_STRONG))
    ranked = rank_jobs(p, JOBS, top_k=4)
    assert ranked[0].job.title == "Machine Learning Intern"
    senior = next(m for m in ranked if "Senior" in m.job.title)
    assert senior.score < ranked[0].score
    assert "Kubernetes" in ranked[0].missing_skills


def test_weak_resume_still_gets_honest_matches():
    p = run(parse_resume("u2", RESUME_WEAK))
    ranked = rank_jobs(p, JOBS, top_k=4)
    assert ranked[0].job.company == "BrandLab"
    ml = next(m for m in ranked if m.job.company == "DeepCo")
    assert ml.score < 40 and ml.missing_skills


def test_score_bounds():
    p = run(parse_resume("u1", RESUME_STRONG))
    for j in JOBS:
        assert 0 <= score_job(p, j).score <= 100


# ---- packs -------------------------------------------------------------------------
def test_pack_falls_back_to_template_without_llm():
    p = run(parse_resume("u1", RESUME_STRONG))
    m = rank_jobs(p, JOBS, 1)[0]
    pack = run(build_pack("u1", p, m, RESUME_STRONG))
    assert pack.generated_by == "template"
    assert "DeepCo" in pack.cover_letter and pack.resume_bullets and pack.gap_plan
    assert template_pack("u1", p, m).job_id == m.job.id


# ---- intents -----------------------------------------------------------------------
def test_intent_json_selection():
    assert parse_intent('{"action": "view_job", "job_id": "job_aaaaaaaaaa"}')["job_id"] == "job_aaaaaaaaaa"


def test_intent_planner_prose():
    i = parse_intent("The user picked job job_aaaaaaaaaa with action view_job.")
    assert i == {"action": "view_job", "job_id": "job_aaaaaaaaaa"}
    f = parse_intent("The user submitted the form (submit_prefs) with role: ML intern, location: Pune, "
                     "kind: internship, remote: false")
    assert f["action"] == "submit_prefs" and f["role"] == "ML intern"
    assert f["location"] == "Pune" and f["kind"] == "internship" and f["remote"] is False


def test_intent_typed_commands():
    assert parse_intent("view 2") == {"action": "view_job", "index": 2}
    assert parse_intent("pack 3") == {"action": "request_pack", "index": 3}
    assert parse_intent("3")["index"] == 3
    s = parse_intent("search data analyst internship in Pune")
    assert s["role"] == "data analyst internship" and s["location"] == "Pune" and s["kind"] == "internship"
    assert parse_intent("search python remote")["remote"] is True
    assert parse_intent(RESUME_STRONG)["action"] == "resume"


# ---- cards -------------------------------------------------------------------------
def _meta(msg):
    return next(c for c in msg.content if c.type == "metadata").metadata


@pytest.mark.parametrize("kind", ["form", "carousel", "detail", "review"])
def test_cards_are_well_formed(kind):
    p = run(parse_resume("u1", RESUME_STRONG))
    ms = rank_jobs(p, JOBS, 3)
    msg = {"form": lambda: cards.prefs_form(p),
           "carousel": lambda: cards.results_carousel(ms, "ML intern"),
           "detail": lambda: cards.job_detail(ms[0]),
           "review": lambda: cards.pack_review(ms[0])}[kind]()
    assert msg.content[0].type == "text" and msg.content[0].text  # text fallback always present
    meta = _meta(msg)
    assert meta["card_protocol_version"] == "1" and meta["card_kind"] == kind
    assert meta["requires_card_interaction"] == "true"
    assert all(isinstance(v, str) for v in meta.values())
    payload = json.loads(meta["card_payload"])
    assert "data" not in payload and payload["title"]
    if kind == "carousel":
        assert all(i["primary_cta"]["selection"]["job_id"].startswith("job_") for i in payload["items"])
    if kind == "form":
        sel = next(f for f in payload["fields"] if f["kind"] == "select")
        assert sel["options"]


# ---- job sources -------------------------------------------------------------------
def test_search_all_survives_failing_source(monkeypatch):
    async def good(q):
        return list(JOBS)

    async def bad(q):
        raise RuntimeError("API down")

    async def skipped(q):
        raise sources.SourceSkipped

    q = JobQuery(session_id="u", role="ml intern", kind="internship")
    rep = run(sources.search_all(q, {"good": good, "bad": bad, "nokey": skipped}))
    assert rep.ok == ["good"] and rep.failed == ["bad"]
    assert rep.jobs and all(j.is_internship for j in rep.jobs)


def test_simulated_failure_flag(monkeypatch):
    async def good(q):
        return list(JOBS)
    monkeypatch.setattr(sources.config, "SIMULATE_SOURCE_FAILURE", {"good"})
    rep = run(sources.search_all(JobQuery(session_id="u", role="x"), {"good": good, "other": good}))
    assert rep.failed == ["good"] and rep.ok == ["other"]


def test_remotive_normalization(monkeypatch):
    async def fake_get(url, **kw):
        return {"jobs": [{"id": 7, "title": "Python Developer Intern", "company_name": "R Co",
                          "candidate_required_location": "Worldwide", "url": "https://r.co/7",
                          "description": "<p>Python &amp; SQL</p>", "publication_date": "2026-10-20T10:00:00",
                          "job_type": "internship"}]}
    monkeypatch.setattr(sources, "_get_json", fake_get)
    jobs = run(sources.fetch_remotive(JobQuery(session_id="u", role="python")))
    assert jobs[0].description == "Python & SQL" and jobs[0].remote and jobs[0].is_internship
    assert jobs[0].posted == "2026-10-20" and jobs[0].id.startswith("job_")


def test_dedupe():
    dup = JOBS[0].copy(update={"id": "job_zzzzzzzzzz"})
    assert len(sources.dedupe([JOBS[0], dup])) == 1


# ---- payments ----------------------------------------------------------------------
def test_to_base_units():
    assert to_base_units("0.5") == 5 * 10**17
    assert to_base_units("2") == 2 * 10**18


def test_transfer_match():
    attrs = {"recipient": "fetch1abc", "amount": "500000000000000000atestfet"}
    assert _transfer_matches(attrs, "fetch1abc", 5 * 10**17)
    assert not _transfer_matches(attrs, "fetch1abc", 6 * 10**17)
    assert not _transfer_matches(attrs, "fetch1other", 1)
