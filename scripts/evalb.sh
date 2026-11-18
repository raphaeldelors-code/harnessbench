#!/bin/bash
trap '' HUP
cd /home/rapha/harnessbench
log(){ echo "[$(date -u +%FT%TZ)] $*"; }
log "FIX_START"
python3 - <<'PYEOF'
import json
p="out/mini/preds.json"
d=json.load(open(p))
for i in ("astropy__astropy-13453","astropy__astropy-14096"):
    d.pop(i, None)
json.dump(d, open(p,"w"), indent=1)
print("mini preds now", len(d))
PYEOF
python3 hb.py run-mini --inst astropy__astropy-13453 --inst astropy__astropy-14096 --workers 2
log "FIX_MINI_END rc=$?"
for h in mini claude-code pi deepseek-harness opencode; do
  log "EVALB_START $h"
  python3 hb.py eval --harness "$h"
  log "EVALB_END $h rc=$?"
done
log "ALL_EVALB_DONE"
