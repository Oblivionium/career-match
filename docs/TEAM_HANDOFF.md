# Team handoff: who owns what

The code base was drafted in one pass. Each owner below should run, read and test their part
until they can explain it to a judge and fix it under pressure. Commit your own changes under
your own name.

## Integration lead
- [ ] Fill `.env` (seeds, keys); keep it out of git
- [ ] `python -m pytest -q` passes on your machine
- [ ] Run `./scripts/start_all.sh`, connect all 4 mailboxes via the Inspector links
- [ ] Paste `docs/agentverse_readmes/*` into each agent's Agentverse README
- [ ] Get all agents onto an always-on host before judging
- [ ] Record the demo (`docs/DEMO_SCRIPT.md`), share the chat, submit Devpost (`docs/DEVPOST.md`)

## Coordinator + cards owner (`coordinator/`)
- [ ] Paste each payload from `coordinator/cards.py` into https://asi1.ai/developer/card-playground
      and fix anything that doesn't render. Not yet verified: the `detail` card without
      `sub_options`/`hero_image`, and badge `variant` values other than `info`
- [ ] Test every step in ASI:One both with `@mention` (JSON selections) and without (planner prose)
- [ ] Check whether ASI:One passes PDF attachments to agents; if yes, add a `ResourceContent` handler

## Resume + matching owner (`resume_analyst/`, `match_apply/`)
- [ ] Get an ASI:One API key; confirm `parsed_by=llm` in logs and the pack is LLM-written
- [ ] Try 5+ real (anonymized) resumes; tune `shared/skills.py` and the score weights in `matcher.py`
- [ ] Add tests for any bug you find

## Jobs + payments owner (`job_scout/`, `coordinator/payments.py`)
- [ ] Get Adzuna and/or JSearch keys; confirm each source returns jobs (`logs/job_scout.log`)
- [ ] Check each API's terms (attribution, rate limits); Remotive asks for low request volume
- [ ] Get testnet FET (Fetch.ai testnet faucet) and run a real payment end to end in ASI:One;
      confirm `CompletePayment` and the on-chain check pass
- [ ] Test the reject path and a failed verification
