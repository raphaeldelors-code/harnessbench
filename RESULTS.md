# Run history

| Date | Run | Question | Model | Harnesses | Verdict |
|---|---|---|---|---|---|
| 2026-11-17 | [strata_iq3s × 5 harnesses, SWE-bench Verified (10)](runs/2026-11-17-strata-iq3s-sb10-5way/run.md) | Which harness is most efficient with a fixed local model? | strata_iq3s | Claude Code · DeepSeek TUI · mini-swe · OpenCode · Pi | Same 5/10 pass rate for all; **OpenCode best per GPU-hour (6.2)**, **mini-swe leanest on tokens**, **Claude Code most reliable (0 empty patches)**, Pi slowest. |

Each run lives in its own directory under `runs/<date>-<slug>/`:

```
run.md      # run card (what & how), tables, embedded charts, findings
charts/     # PNG diagrams generated from data/results.json
data/       # consolidated results.json + official eval JSONs + preds + raw telemetry
```

To add a run: `hb.py run --harness <name>` → `hb.py eval --harness <name>` → run `scripts/consolidate.py` + `scripts/render_charts.py` → write `run.md`, link it here.
