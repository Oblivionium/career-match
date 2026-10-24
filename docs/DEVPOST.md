# Devpost submission draft

**Name:** CareerMatch

**Tagline:** Paste your resume in ASI:One. Get live internships that fit you, the skills you're
missing, and a tailored application, all in one chat.

## The problem
Students and fresh graduates apply to dozens of roles without knowing which ones they're
qualified for, why they're rejected, or how to tailor each application.

## Target users
College students looking for internships, and fresh graduates looking for entry-level jobs,
starting with India and remote roles.

## What it does / outcome
- Reads a pasted resume into a structured profile (skills, level, best-fit roles)
- Searches live listings from several job APIs in parallel
- Ranks them with an explainable score: which skills match, which are missing, why
- Sells a per-job Application Pack via the Agent Payment Protocol: tailored cover letter,
  resume bullets for the role, and a short plan to close skill gaps
- Entire flow runs inside ASI:One using Interactive Cards (form, carousel, detail, review)

## How we built it
Four uAgents registered on Agentverse: Career Coordinator (Chat Protocol, cards, payments,
orchestration), Resume Analyst, Job Scout, Match & Apply. ASI:One LLM for parsing and writing;
deterministic scoring for consistent, explainable rankings. Testnet FET payments verified
on-chain.

## Reliability
Parallel job sources with timeouts, retries and caching; local fallback when a worker agent is
unreachable; rule-based fallback when the LLM fails; every card has a text fallback.

## Monetization
Free matching to attract users; paid per-job Application Packs. Next: subscription alerts for
new matching roles and paid listings for companies hiring interns.

## Links
- ASI:One shared chat: TODO
- Agentverse profiles: Coordinator TODO · Resume Analyst TODO · Job Scout TODO · Match & Apply TODO
- GitHub: https://github.com/Oblivionium/agent
- Demo video: TODO

## AI tools disclosure
(Check the hackathon rules.) Code was initially drafted with Claude and refined, tested and
deployed by the team using Codex and manual work.
