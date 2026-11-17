#!/bin/bash
# sweep_hb.sh — full 5-harness sweep, sequential, autonomous
cd /home/rapha/harnessbench
export HB_TIMEOUT=1800
log(){ echo "[$(date -u +%FT%TZ)] $*"; }
for h in mini claude-code pi deepseek-harness opencode; do
  log "SWEEP_START $h"
  if [ "$h" = mini ]; then python3 hb.py run-mini; else python3 hb.py run --harness "$h"; fi
  log "RUN_END $h rc=$?"
  python3 hb.py eval --harness "$h"
  log "EVAL_END $h rc=$?"
done
python3 hb.py report | tee report.txt
log "ALL_SWEEP_DONE"
