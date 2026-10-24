# CareerMatch: resume-to-internship agents on ASI:One

Students paste their resume into ASI:One. A team of four Fetch.ai agents reads it, searches
**live** job and internship listings, ranks them with honest explanations and skill gaps, and
(for a small FET payment) writes a tailored **Application Pack**: cover letter, resume bullets
rewritten for that role, and a plan to close the missing skills.

Built for the Fetch.ai **ASI:One Agent Challenge**.

## How it works

```
 ASI:One user
     │  Agent Chat Protocol + Interactive Cards + Payment Protocol
     ▼
 ┌────────────────────┐
 │ Career Coordinator │──ResumeRequest──▶ Resume Analyst  (LLM → structured profile)
 │  (chat, cards,     │──JobQuery──────▶ Job Scout       (Adzuna, JSearch, Remotive, Arbeitnow)
 │   payments, state) │──MatchRequest──▶ Match & Apply   (explainable scoring)
 └────────────────────┘──PackRequest───▶ Match & Apply   (tailored application pack)
```

**User flow in ASI:One**

1. Paste resume → agent replies with the skills it found and a **form card** (role, city, internship/job, remote).
2. **Carousel card** of the top 5 live matches, each with a match %.
3. **Detail card**: why it matches, which skills you have, which are missing, apply link.
4. **Review card**: buy the Application Pack → **Payment Protocol** request (testnet FET) → verified on-chain → pack delivered.

Every card also carries a plain-text version, and typed commands (`view 2`, `pack 2`, `back`,
`search data analyst in Pune`, `forget me`) work too, so the flow never dead-ends.

## Reliability

| Failure | What happens |
|---|---|
| A job API is down or slow | Other sources still return; the user is told which source failed |
| All job APIs down | Stale cached results are served, labelled as such |
| A worker agent is unreachable | Coordinator runs that step locally (logged as degraded) |
| LLM key missing / API error / bad JSON | Retry once, then rule-based parser / templated pack |
| Payment can't be verified | `CancelPayment` sent, user told they weren't charged |
| Any unexpected error | User gets a friendly retry message; their session is kept |

Set `SIMULATE_SOURCE_FAILURE=adzuna` to demonstrate source fallback live.

For LLM calls, CareerMatch uses ASI:One when `ASI_ONE_API_KEY` is set; otherwise it uses Gemini when `GEMINI_API_KEY` is set. With neither key, it uses the documented rule-based and template fallbacks.

## Setup (WSL / Linux)

```bash
git clone https://github.com/Oblivionium/agent.git && cd agent
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip && python -m pip install -r requirements.txt
cp .env.example .env     # then fill in seeds and keys (see comments in the file)
python -m pytest -q      # unit + end-to-end tests (no keys or network needed)
```

Generate the four seeds with `python -c "import secrets; print(secrets.token_hex(32))"`.

## Run

**Local development (all agents in one process, no Agentverse):**

```bash
USE_MAILBOX=false python run_local.py
```

**For ASI:One (each agent separately, connected through Agentverse mailboxes):**

```bash
./scripts/start_all.sh        # starts all 4 in the background, logs in logs/
./scripts/stop_all.sh
```

On first start, each agent prints an **Agent Inspector** link in its log
(`logs/<agent>.log`). Open each link while logged into agentverse.ai and click
**Connect → Mailbox**. Then paste the matching file from `docs/agentverse_readmes/` into each
agent's README on Agentverse, since ASI:One uses that text to discover the agent.

Test order: Agentverse **Testing** tab → ASI:One with `@` mention → ASI:One with a natural
question and no mention (e.g. "find internships that fit my resume").

## Monetization

Matching is free. The Application Pack costs a small FET fee per job (`PACK_PRICE_FET`,
default 0.5 testnet FET for the demo). Each pack costs us one LLM call, so the per-pack fee
covers its cost with margin. Next steps after the hackathon: weekly new-match alerts as a
subscription, and paid placement for companies hiring interns.

## Project layout

```
shared/          models (message contracts), config, LLM client, retry, skill vocabulary
coordinator/     ASI:One-facing agent: chat protocol, cards, intent parsing, payments
resume_analyst/  resume → structured profile
job_scout/       live job sources, normalization, dedupe, cache
match_apply/     scoring + application pack generation
tests/           unit tests + end-to-end multi-agent test
docs/            Agentverse READMEs, demo script, Devpost draft, team handoff
```

## Data handling

Resumes are stored only in the coordinator's local agent storage (`agent*_data.json`,
gitignored) to keep the session going. Users can type `forget me` to delete their data.

## Credits

Job data from Adzuna, JSearch (RapidAPI), Remotive and Arbeitnow, used through their public
APIs and subject to their terms. Initial code drafted with AI assistance (Claude), then
tested, configured and deployed by the team.

## License

MIT
