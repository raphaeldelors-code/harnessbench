#!/bin/bash
# sweep_new6.sh — 40 Verified instances for the 6 harnesses newly added from the
# joelniklaus/harness-leaderboard set: codex, qwen-code, kimi-code, grok, openclaw, hermes-agent.
cd /home/rapha/harnessbench
log(){ echo "[$(date -u +%FT%TZ)] $*"; }

log "PREP_START"
python3 hb.py prep
log "PREP_END rc=$?"

for h in codex qwen-code kimi-code grok openclaw hermes-agent; do
  log "SWEEP_START $h"
  python3 hb.py run --harness "$h" --workers 2
  log "RUN_END $h rc=$?"
  python3 hb.py eval --harness "$h"
  log "EVAL_END $h rc=$?"
done
log "ALL_SWEEP_NEW6_DONE"
