<div align="center">

# CareerMatch

Find internships and early-career jobs that fit your resume, understand why they match, and prepare a tailored application pack.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![uAgents](https://img.shields.io/badge/uAgents-Multi--Agent-5B4BDB?style=flat-square)](https://fetch.ai/docs/agents/uagents/)
[![Agentverse](https://img.shields.io/badge/Agentverse-Mailboxes-00A67D?style=flat-square)](https://agentverse.ai/)
[![ASI:One](https://img.shields.io/badge/ASI%3AOne-Agent_Chat-111827?style=flat-square)](https://asi1.ai/)
[![Gemini](https://img.shields.io/badge/Gemini-LLM-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![Render](https://img.shields.io/badge/Render-Background_Workers-46E3B7?style=flat-square&logo=render&logoColor=111827)](https://render.com/)

**[Source Code](https://github.com/Oblivionium/career-match)**

</div>

## Overview

CareerMatch is a multi-agent job-search assistant for students and early-career candidates. Chat with the **Career Coordinator** in ASI:One, share your resume, and get relevant job listings ranked against your skills and experience.

Four Fetch.ai uAgents work together: the coordinator manages the conversation, the Resume Analyst extracts a candidate profile, the Job Scout searches job sources, and Match & Apply ranks listings and writes application materials.

Agents connect to Agentverse through mailboxes. They can run on a developer machine or on an always-on host such as Render. Mailbox mode registers and connects agents with Agentverse; it does not upload their source code to Agentverse Hosted Agents.

## Features

- Resume parsing with Gemini or ASI:One, with a rule-based fallback
- Job and internship search through Adzuna, JSearch, Remotive, and Arbeitnow
- Explainable job ranking, matched skills, and skill gaps
- Interactive preference forms, job carousels, and details in ASI:One
- Tailored cover letters, resume bullets, and skill-gap plans
- Optional FET payment flow for Application Packs
- Local fallbacks when an agent, model, or job source is unavailable

## How It Works

```text
ASI:One user
     |
     | Agent Chat Protocol
     v
Career Coordinator
     | ResumeRequest          | JobQuery
     +------------------------+--------------------+
     v                        v                    v
Resume Analyst           Job Scout           Match & Apply
     | ResumeProfile          | JobResults         | MatchResults / PackResult
     +------------------------+--------------------+
```

1. Paste your resume into Career Coordinator.
2. Choose a role, location, and work type in the preference form.
3. Review ranked matches and their reasons, matched skills, and gaps.
4. Request an Application Pack for a job. If payments are enabled, approve the FET request to receive it.

Text commands such as `search data analyst in Pune`, `view 2`, `pack 2`, `back`, and `forget me` are also supported.

## Tech Stack

- Python 3.12
- Fetch.ai uAgents and Agent Chat Protocol
- Agentverse mailboxes
- Gemini API or ASI:One API
- GitHub-hosted job APIs and public job boards
- pytest for unit and end-to-end tests

## Project Structure

```text
coordinator/      ASI:One conversation, cards, orchestration, and payments
resume_analyst/   Resume parsing and profile extraction
job_scout/        Job sources, normalization, filtering, and cache
match_apply/      Match scoring and Application Pack generation
shared/           Configuration, message support, LLM client, retry, and skills
models/           Message models shared between agents
scripts/          Startup and deployment helpers
docs/             Agentverse profiles, demo script, and team handoff
tests/            Unit and end-to-end tests
```

## Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/Oblivionium/career-match.git
cd career-match
```

### 2. Create a virtual environment and install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Set a unique, non-empty seed for each agent in `.env`. Keep the same seeds across restarts and deployments to preserve agent addresses. Add model and job-source API keys if you have them. Never commit `.env` or share its secret values.

Generate a seed with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Run all agents in one local process

For local development without Agentverse mailboxes:

```bash
USE_MAILBOX=false python run_local.py
```

## Connecting Local Agents to Agentverse

To chat with CareerMatch in ASI:One while the code runs on your computer, start each agent as a separate mailbox agent:

```bash
./scripts/start_all.sh
```

The script starts Resume Analyst, Job Scout, Match & Apply, and Career Coordinator. Open each Agent Inspector URL printed in the terminal or in `logs/<agent>.log`. While the agent is running, choose **Connect → Mailbox → Finish**. Allow browser local-network access if prompted.

In Agentverse, update the profiles with the corresponding README from `docs/agentverse_readmes/`. The user-facing profile is **Career Coordinator**. Start a new chat from that profile.

Check each log for successful mailbox registration. For example:

```text
Successfully registered as mailbox agent in Agentverse
```

Stop the local agents with:

```bash
./scripts/stop_all.sh
```

Mailbox mode connects a running local process to Agentverse; the process must stay running. It is not the same as uploading code to Agentverse Hosted Agents.

## Hosting on Render

Render Background Workers can keep the mailbox agents running without exposing public HTTP ports. Create four Background Worker services from the `main` branch of this repository, one for each agent. Render Background Workers require a paid service plan; see [Render service types](https://render.com/docs/service-types).

For each service, set:

- **Runtime:** Python 3
- **Python version:** `3.12.11`
- **Build command:** `pip install -r requirements.txt`
- **Root directory:** leave blank
- **Environment:** `USE_MAILBOX=true` and the matching agent seed

Use these start commands:

| Render service | Start command | Seed variable |
|---|---|---|
| Resume Analyst | `python -m resume_analyst.agent` | `RESUME_SEED` |
| Job Scout | `python -m job_scout.agent` | `SCOUT_SEED` |
| Match & Apply | `python -m match_apply.agent` | `MATCH_SEED` |
| Career Coordinator | `python -m coordinator.agent` | `COORD_SEED` |

Keep the same seeds used for the connected mailboxes. In the Career Coordinator service, set `RESUME_ADDR`, `SCOUT_ADDR`, and `MATCH_ADDR` to the worker addresses shown in their startup logs. This allows the coordinator to message the right agents.

Add secrets through each service's Render **Environment** settings; do not commit them:

- `GEMINI_API_KEY` or `ASI_ONE_API_KEY` for Career Coordinator, Resume Analyst, and Match & Apply
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, and/or `JSEARCH_API_KEY` for Job Scout (optional)
- `PAYMENTS_ENABLED=false` on Career Coordinator until the payment flow is configured; set it to `true` when ready

Before moving the agents to Render, connect each mailbox locally using the same seeds. Then stop local agent processes before starting the Render copies. Avoid running two processes with the same agent identity at once.

Render services use an ephemeral filesystem by default. CareerMatch stores chat sessions in the coordinator's local agent storage, so sessions can be lost after a restart or redeploy unless persistent storage is configured. See [Render persistent disks](https://render.com/docs/disks).

## Configuration

See `.env.example` for all supported settings. Common options include:

| Variable | Purpose |
|---|---|
| `COORD_SEED`, `RESUME_SEED`, `SCOUT_SEED`, `MATCH_SEED` | Stable identity for each agent; keep secret and unchanged |
| `USE_MAILBOX` | Connect local/hosted processes to Agentverse mailboxes |
| `ASI_ONE_API_KEY` | Preferred model API key when set |
| `GEMINI_API_KEY` | Gemini fallback model key |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Optional Adzuna job source credentials |
| `JSEARCH_API_KEY` | Optional JSearch/RapidAPI credential |
| `PAYMENTS_ENABLED` | Enable or disable paid Application Packs |
| `PACK_PRICE_FET`, `FET_USE_TESTNET` | Application Pack price and payment network |

Remotive and Arbeitnow can be used without API credentials. With no model key, the app uses the rule-based resume parser and template packs.

## Troubleshooting

- **Mailbox returns 401 or “mailbox not found”:** keep the agent running and complete **Connect → Mailbox → Finish** from its Inspector link. Confirm the process uses the same seed as the Agentverse profile.
- **Port already in use:** stop old agent processes before running `start_all.sh` again. Each local agent uses a separate port (`8001`–`8004`).
- **Coordinator cannot reach a worker:** confirm the worker is running, its mailbox is connected, and `RESUME_ADDR`, `SCOUT_ADDR`, or `MATCH_ADDR` matches the worker address.
- **No job listings:** configure Adzuna or JSearch for broader coverage; free sources may not have results for every role or location.

## Data Handling

CareerMatch stores resume text and results in the coordinator's agent storage so a user can continue their session. Users can type `forget me` to remove their stored session. Use trusted hosting, keep credentials out of source control, and configure persistent storage deliberately if session retention is required.

## License

MIT. See [LICENSE](LICENSE).
