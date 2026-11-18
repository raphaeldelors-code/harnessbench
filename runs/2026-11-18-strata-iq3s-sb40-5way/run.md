# Run: 2026-11-18 — strata_iq3s × 5 harnesses, 40 SWE-bench Verified instances

**Question:** with n=10 every harness tied at 5/10. Extend to 40 instances and find whether a leader emerges.

## Setup
- **Model (fixed):** `strata_iq3s` (Qwen3.8-27B IQ3_S, llama-swap, parallel=2, 128k ctx, MTP). Only the harness varies.
- **Dataset:** 40 SWE-bench Verified instances = the 10 from the first run + 30 new (`data/instances/sb40_new.json`), stratified proportional to the difficulty bands of the full Verified set, max 3 per repo, seed 42.
- **Harnesses** (headless, inside the official `sweb.eval` per-instance image): Claude Code 2.1.326, OpenCode 2.3.0, Pi 1.5.2, DeepSeek TUI 0.2.2-rc.3, mini-swe-agent 2.4.6.
- **Grading:** official swebench F2P/P2P grader, outside the harness container. 1800 s per-instance agent timeout, workers=2.
- Two mini-swe instances were re-run cleanly after an accidental double-sweep overlap touched their workdirs.

## Results

| Harness | Resolved | Empty patches | Wall (sum) | LLM calls | Input tok | Output tok | Resolved/GPU-h |
|---|---|---|---|---|---|---|---|
| OpenCode | **35/40** | 2 | 8.48 h | 2,334 | 80.7M | 874K | 4.13 |
| Claude Code | **34/40** | 0 | 6.51 h | 2,035 | 65.9M | 905K | 5.22 |
| Pi | **32/40** | 3 | 8.42 h | 2,010 | 51.3M | 718K | 3.80 |
| mini-swe-agent | **26/40** | 9 | 13.15 h | 2,511 | 62.9M | 1155K | 1.98 |
| DeepSeek TUI | **24/40** | 11 | 7.69 h | 1,865 | 56.2M | 791K | 3.12 |

![resolved](charts/resolved.png)
![efficiency](charts/resolved_per_gpu_h.png)
![matrix](charts/matrix.png)

## Paired significance (McNemar exact)

| Pair | discordant | p | significant (0.05) |
|---|---|---|---|
| OpenCode vs Claude Code | 0 : 1 | 1.0000 | no |
| OpenCode vs Pi | 0 : 3 | 0.2500 | no |
| OpenCode vs mini-swe-agent | 1 : 10 | 0.0117 | yes |
| OpenCode vs DeepSeek TUI | 1 : 12 | 0.0034 | yes |
| Claude Code vs Pi | 2 : 0 | 0.5000 | no |
| Claude Code vs mini-swe-agent | 2 : 10 | 0.0386 | yes |
| Claude Code vs DeepSeek TUI | 11 : 1 | 0.0063 | yes |
| Pi vs mini-swe-agent | 3 : 9 | 0.1460 | no |
| Pi vs DeepSeek TUI | 10 : 2 | 0.0386 | yes |
| mini-swe-agent vs DeepSeek TUI | 8 : 6 | 0.7905 | no |

## Verdict
- **Leader: OpenCode (35/40) ≈ Claude Code (34/40)** — statistically tied on correctness (1:0 discordant, p=1.0). **Claude Code wins on cost**: 6.5 h wall vs 8.5 h, 5.22 vs 4.13 resolved/GPU-h, and 0 empty patches vs 2.
- **Pi (32) is a solid third** — not significantly behind the leaders at n=40 (p=0.25 vs OpenCode).
- **mini-swe-agent (26) and DeepSeek TUI (24) are clearly behind** (vs OpenCode: p=0.012 and p=0.003; vs Claude Code: p=0.039 and p=0.006). mini is worst on efficiency too (1.98 resolved/GPU-h, 13.2 h wall).

## Caveats
- **Absolute scores are inflated by training-set memorization**: all 40 instances are classic pre-2022 SWE-bench cases; Qwen-class models have seen them. The *ranking* is still valid — contamination is held constant across harnesses — but do not read 35/40 as a general SWE-bench Verified score.
- Absolute token/cost numbers include llama-swap ring snapshots taken during each harness window (same method as the n=10 run).
- Raw `activity.jsonl` telemetry (26–83 MB per harness) is kept on the rig, not committed.
