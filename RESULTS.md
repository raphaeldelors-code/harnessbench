# Run history

| Date | Run | Question | Model | Harnesses | Verdict |
|---|---|---|---|---|---|
| 2026-11-17 | [strata_iq3s × 5 harnesses, SWE-bench Verified (10)](runs/2026-11-17-strata-iq3s-sb10-5way/run.md) | Which harness is most efficient with a fixed local model? | strata_iq3s | Claude Code · DeepSeek TUI · mini-swe · OpenCode · Pi | Same 5/10 pass rate for all; **OpenCode best per GPU-hour (6.2)**, **mini-swe leanest on tokens**, **Claude Code most reliable (0 empty patches)**, Pi slowest. |
| 2026-11-18 | [strata_iq3s × 5 harnesses, SWE-bench Verified (40)](runs/2026-11-18-strata-iq3s-sb40-5way/run.md) | Enough data points to pick a leader? | strata_iq3s | Claude Code · DeepSeek TUI · mini-swe · OpenCode · Pi | **OpenCode 35/40 ≈ Claude Code 34/40 (statistical tie, p=1.0)**; Claude Code most efficient (5.22 res/GPU-h, 0 empty patches); Pi 32 solid third; **mini 26 & dsh 24 significantly behind (p<0.05)**. |

| 2026-11-19 | [strata_iq3s × 6 new leaderboard harnesses, SWE-bench Verified (40)](runs/2026-11-19-strata-iq3s-sb40-6way-new/run.md) | Can the new six join the top group? | strata_iq3s | Codex · Qwen Code · Kimi Code · Grok Build · OpenClaw · Hermes Agent | **Qwen Code 34 & Kimi Code 34 tie with OpenCode 35 / Claude Code 34 (p=1.0) — four-way top**; Codex 31 / Grok 30 mid tier; **OpenClaw 28 significantly behind leaders**; Hermes Agent 11/40 (16/40 harness-infra gateway deaths). |
Each run lives in its own directory under `runs/<date>-<slug>/`:

```
run.md      # run card (what & how), tables, embedded charts, findings
charts/     # PNG diagrams generated from data/results.json
data/       # consolidated results.json + official eval JSONs + preds + raw telemetry
```

To add a run: `hb.py run --harness <name>` → `hb.py eval --harness <name>` → run `scripts/consolidate.py` + `scripts/render_charts.py` → write `run.md`, link it here.
