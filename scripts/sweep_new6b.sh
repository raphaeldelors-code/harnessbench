#!/bin/bash
# Sweep for the 5 remaining new harnesses (openclaw already ran cleanly after the argv fix).
cd /home/rapha/harnessbench
log(){ echo "[$(date -u +%FT%TZ)] $*"; }
log "EVAL_OPENCLAW_START"
python3 hb.py eval --harness openclaw
log "EVAL_OPENCLAW_END rc=$?"
for h in codex qwen-code kimi-code grok hermes-agent; do
  log "SWEEP_START $h"
  python3 hb.py run --harness "$h" --workers 2
  log "RUN_END $h rc=$?"
  python3 hb.py eval --harness "$h"
  log "EVAL_END $h rc=$?"
done
log "ALL_SWEEP_NEW6_DONE"
