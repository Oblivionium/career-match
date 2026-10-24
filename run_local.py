"""Run all four agents in one process for local development (no Agentverse needed).

    USE_MAILBOX=false python run_local.py

For ASI:One / Agentverse, run each agent separately with USE_MAILBOX=true instead
(see README).
"""

import os

os.environ.setdefault("USE_MAILBOX", "false")

from uagents import Bureau  # noqa: E402

from coordinator.agent import agent as coordinator  # noqa: E402
from job_scout.agent import agent as scout  # noqa: E402
from match_apply.agent import agent as matcher  # noqa: E402
from resume_analyst.agent import agent as resume  # noqa: E402

if __name__ == "__main__":
    bureau = Bureau(port=int(os.getenv("BUREAU_PORT", "8000")))
    for a in (coordinator, resume, scout, matcher):
        bureau.add(a)
        print(f"{a.name:20s} {a.address}")
    bureau.run()
