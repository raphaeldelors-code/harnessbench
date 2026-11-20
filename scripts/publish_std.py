#!/usr/bin/env python3
"""Canonical run.md generator + multi-metric leaderboard (cross-run).
Usage: python3 scripts/publish_std.py   (run at repo root)
Standard sections for every run: Run card / Results table (fixed columns) /
Charts (fixed 6, fixed order) / Paired significance / Findings / Caveats / Data."""
import json, math, itertools, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI",
        "mini": "mini-swe-agent", "opencode": "OpenCode", "pi": "Pi",
        "codex": "Codex", "qwen-code": "Qwen Code", "kimi-code": "Kimi Code",
        "grok": "Grok Build", "openclaw": "OpenClaw", "hermes-agent": "Hermes Agent"}
CHARTS = [("resolved.png", "Resolved instances"), ("resolved_per_gpu_h.png", "Efficiency"),
          ("wall_s.png", "Wall time (sum)"), ("input_tokens.png", "Input tokens"),
          ("calls.png", "LLM calls"), ("matrix.png", "Per-instance matrix")]

def mcnemar(R, H):
    rows = []
    for a, b in itertools.combinations(H, 2):
        sa = set(R["harnesses"][a]["resolved_ids"]); sb = set(R["harnesses"][b]["resolved_ids"])
        aonly, bonly = len(sa - sb), len(sb - sa)
        n = aonly + bonly
        p = 1.0 if n == 0 else min(1.0, sum(math.comb(n, i) for i in range(min(aonly, bonly) + 1)) / 2 ** (n - 1))
        rows.append((a, b, aonly, bonly, p))
    return rows

def fmt_tok(x): return f"{x/1e6:.2f}M" if x >= 1e6 else f"{x/1e3:.0f}K"

def run_md(run, title, bench, question, card, findings, caveats):
    R = json.load(open(f"runs/{run}/data/results.json"))
    n = R["instances"] if isinstance(R["instances"], int) else len(R["instances"])
    H = sorted(R["harnesses"], key=lambda h: -R["harnesses"][h]["resolved"])
    L = [f"# Run {title}", "",
         f"**Question:** {question}", ""]
    L += ["## Run card", "", "| | |", "|---|---|"] + [f"| {k} | {v} |" for k, v in card.items()] + [""]
    L += ["## Results", "",
          "| Harness | Resolved | Empty patches | Wall (sum) | LLM calls | Input tok | Output tok | Resolved/GPU-h |",
          "|---|---|---|---|---|---|---|---|"]
    for h in H:
        v = R["harnesses"][h]
        L.append(f"| {NAME.get(h, h)} | **{v['resolved']}/{n}** | {v['empty']} | {v['wall_s']/3600:.2f} h | {v['calls']:,} | {fmt_tok(v['input_tokens'])} | {fmt_tok(v['output_tokens'])} | {v['resolved_per_gpu_h']:.2f} |")
    L += ["", "## Charts", ""]
    for f, cap in CHARTS:
        L += [f"![{cap}](charts/{f})", ""]
    L += ["## Paired significance (McNemar exact)", "",
          "| Pair | discordant | p | significant (0.05) |", "|---|---|---|---|"]
    for a, b, ao, bo, p in mcnemar(R, H):
        L.append(f"| {NAME.get(a, a)} vs {NAME.get(b, b)} | {ao} : {bo} | {p:.4f} | {'yes' if p < 0.05 else 'no'} |")
    L += ["", "## Findings", ""] + [f"{i+1}. {t}" for i, t in enumerate(findings)]
    L += ["", "## Caveats", ""] + [f"- {c}" for c in caveats]
    L += ["", "## Data", "",
          "- `data/results.json` — consolidated numbers (this page is generated from it)",
          "- `data/eval_*.json` / `openai__*.json` — official swebench grader reports per harness",
          "- `data/preds_*.json` — model patches per instance",
          "- `data/windows_*.jsonl` — per-instance wall windows",
          "- Reproduce: `hb.py run --harness <name> && hb.py eval --harness <name>` then `scripts/consolidate.py && scripts/render_charts.py && scripts/publish_std.py`", ""]
    open(f"runs/{run}/run.md", "w").write("\n".join(L))
    print("regenerated", run)

R10 = json.load(open("runs/2026-11-17-strata-iq3s-sb10-5way/data/results.json"))
run_md("2026-11-17-strata-iq3s-sb10-5way",
       "2026-11-17 — strata_iq3s × 5 harnesses, SWE-bench Verified (10)",
       "SWE-bench Verified, 10 instances",
       "with the *model held fixed*, which coding harness gets the most solved tasks per unit of work?",
       {"Date": "2026-11-17 (sweep 07:40 → 10:48 UTC, grading until 12:29)",
        "Model (fixed)": "`strata_iq3s` (Qwen3.8-27B IQ3_S) via llama-swap `127.0.0.1:8080`",
        "Serving": "strata 0.2.13, `--context 128k --parallel 2 --kv k8v4 --mtp`, workers=1",
        "Dataset": "10 SWE-bench Verified instances (`sb10_new.json`)",
        "Grading": "official swebench F2P/P2P grader, **outside** the harness container",
        "Agent loop": "headless, official `swebench/sweb.eval.x86_64.*` image, 2700 s timeout",
        "Harnesses": "Claude Code 2.1.326 · DeepSeek TUI 0.2.2-rc.3 · mini-swe-agent 2.x · OpenCode 2.3.0 · Pi 1.5.2",
        "Telemetry": "llama-swap activity ring (per-request tokens) + per-instance wall windows"},
       ["**Pass rate is harness-insensitive at n=10** — all five solved the same 4 core instances; only divergence is the pylint tie (4604 vs 4551): sampling noise, not capability.",
        "**Efficiency separates them 2×** — OpenCode best resolved/GPU-h (6.22), fastest wall (0.80 h); Pi slowest and most expensive for the same solves.",
        "**mini-swe-agent has the leanest loop** — ~34–40% fewer calls and input tokens at equal pass rate.",
        "**Claude Code is the most reliable loop** — non-empty patch on every instance (0 empties, 0 timeouts); DeepSeek TUI least reliable (3 empties)."],
       ["n=10, single sample per harness; pass-rate ranking needs ≥30 instances (delivered by the sb40 run).",
        "`STRATA_ROUTE_PRIOR=0 STRATA_ROUTE_TAIL_SKIP=0` were active (bench8 A/B had shown zero effect on this task mix).",
        "Absolute scores inflated by training-set memorization of pre-2022 instances; ranking still valid (contamination constant across harnesses)."])

R40 = json.load(open("runs/2026-11-18-strata-iq3s-sb40-5way/data/results.json"))
run_md("2026-11-18-strata-iq3s-sb40-5way",
       "2026-11-18 — strata_iq3s × 5 harnesses, SWE-bench Verified (40)",
       "SWE-bench Verified, 40 instances (10 from sb10 + 30 new, stratified by difficulty, max 3/repo, seed 42)",
       "at n=40, do we have enough data points to distinguish a clear leader among the harnesses?",
       {"Date": "2026-11-17 13:31 → 2026-11-18 11:10 UTC (sweep + grading)",
        "Model (fixed)": "`strata_iq3s` (Qwen3.8-27B IQ3_S) via llama-swap, `--parallel 2`, 128k ctx, MTP",
        "Dataset": "40 SWE-bench Verified instances (`sb40_new.json`)",
        "Grading": "official swebench F2P/P2P grader, **outside** the harness container",
        "Agent loop": "headless, official `swebench/sweb.eval.x86_64.*` image, 2700 s timeout, workers=2",
        "Harnesses": "Claude Code 2.1.326 · DeepSeek TUI 0.2.2-rc.3 · mini-swe-agent 2.4.6 · OpenCode 2.3.0 · Pi 1.5.2",
        "Telemetry": "llama-swap activity ring (per-request tokens) + per-instance wall windows"},
       ["**Leader: OpenCode (35/40) ≈ Claude Code (34/40)** — statistically tied on correctness (1:0 discordant). **Claude Code wins on cost**: 6.5 h vs 8.5 h wall, 5.22 vs 4.13 resolved/GPU-h, 0 empty patches vs 2.",
        "**Pi (32/40) is a solid third** — not significantly behind the leaders at n=40 (p=0.25 vs OpenCode).",
        "**mini-swe-agent (26) and DeepSeek TUI (24) are clearly behind** — vs OpenCode p=0.012 / p=0.003; vs Claude Code p=0.039 / p=0.006. mini is worst on efficiency too (1.98 resolved/GPU-h)."],
       ["Absolute scores inflated by training-set memorization of classic pre-2022 instances; the *ranking* holds because contamination is identical across harnesses.",
        "Nightly Hindsight consolidation overlapped the Pi phase (~37 min of shared-model traffic): Pi wall/token totals slightly inflated (low single-digit %); resolved counts unaffected.",
        "Two mini instances were re-run cleanly after an accidental double-sweep overlap touched their workdirs.",
        "Raw `activity.jsonl` telemetry (26–83 MB per harness) is kept on the rig, not committed."])
print("done")
