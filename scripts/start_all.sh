#!/usr/bin/env bash
# Start all four agents in the background for ASI:One (mailbox mode). Logs go to logs/.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && source .venv/bin/activate
[ -f .env ] || { echo "Missing .env (cp .env.example .env)"; exit 1; }
mkdir -p logs
export USE_MAILBOX=true
for mod in resume_analyst job_scout match_apply coordinator; do
  nohup python -m "$mod.agent" > "logs/$mod.log" 2>&1 &
  echo $! > "logs/$mod.pid"
  echo "started $mod (pid $!), log: logs/$mod.log"
  sleep 2
done
echo
echo "Inspector links (open each once to connect the mailbox):"
sleep 5
grep -ho "https://agentverse.ai/inspect[^ ]*" logs/*.log | sort -u || echo "(not printed yet; check logs/*.log)"
