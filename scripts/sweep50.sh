#!/bin/bash
# sweep50.sh — extend harness bench from 10 to 40 Verified instances
cd /home/rapha/harnessbench
log(){ echo "[$(date -u +%FT%TZ)] $*"; }
mapfile -t NEW < data/instances/new30.txt
INST_ARGS=(); for i in "${NEW[@]}"; do INST_ARGS+=(--inst "$i"); done

log "PREP_START"
python3 hb.py prep
log "PREP_END rc=$?"

log "PULL_START"
python3 - <<'PYEOF'
import json
ds=json.load(open("data/instances/sb40_new.json"))
new=set(open("data/instances/new30.txt").read().split())
for d in ds:
    if d["instance_id"] in new: print(d["image"])
PYEOF
python3 - <<'PYEOF' | xargs -P3 -I{} docker pull -q {} >/dev/null && echo PULL_OK
import json
ds=json.load(open("data/instances/sb40_new.json"))
new=set(open("data/instances/new30.txt").read().split())
for d in ds:
    if d["instance_id"] in new: print(d["image"])
PYEOF
log "PULL_END rc=$?"

for h in mini claude-code pi deepseek-harness opencode; do
  log "SWEEP50_START $h"
  if [ "$h" = mini ]; then python3 hb.py run-mini "${INST_ARGS[@]}" --workers 2
  else python3 hb.py run --harness "$h" "${INST_ARGS[@]}" --workers 2 --resume; fi
  log "RUN50_END $h rc=$?"
  python3 hb.py eval --harness "$h" --resume
  log "EVAL50_END $h rc=$?"
done
log "ALL_SWEEP50_DONE"
