#!/usr/bin/env python3
"""Driver: add the sb40 new-6-harness run to the repo (dirs, data, charts, run.md),
fix the two stale run-card timeout lines, append RESULTS.md row. Run at repo root."""
import json, os, shutil, subprocess
os.chdir("/home/rapha/harnessbench")

RUN = "2026-11-19-strata-iq3s-sb40-6way-new"
HS = ["codex", "qwen-code", "kimi-code", "grok", "openclaw", "hermes-agent"]

# 1. NAME map + card timeout fixes in publish_std.py
p = "scripts/publish_std.py"; t = open(p).read()
old_name = 'NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI",\n        "mini": "mini-swe-agent", "opencode": "OpenCode", "pi": "Pi"}'
assert old_name in t
t = t.replace(old_name, 'NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI",\n        "mini": "mini-swe-agent", "opencode": "OpenCode", "pi": "Pi",\n        "codex": "Codex", "qwen-code": "Qwen Code", "kimi-code": "Kimi Code",\n        "grok": "Grok Build", "openclaw": "OpenClaw", "hermes-agent": "Hermes Agent"}')
t = t.replace("1800 s timeout", "2700 s timeout")
open(p, "w").write(t)

# 2. run dir + data
os.makedirs(f"runs/{RUN}/data", exist_ok=True)
os.makedirs(f"runs/{RUN}/charts", exist_ok=True)
shutil.copy("/tmp/hb_sweep_results_new.json", f"runs/{RUN}/data/results.json")
for h in HS:
    shutil.copy(f"openai__strata_iq3s.hb_{h}.json", f"runs/{RUN}/data/openai__strata_iq3s.hb_{h}.json")
    shutil.copy(f"out/{h}/preds.json", f"runs/{RUN}/data/preds_{h}.json")
    shutil.copy(f"out/{h}/windows.jsonl", f"runs/{RUN}/data/windows_{h}.jsonl")
for f in os.listdir("/tmp/new6_charts"):
    shutil.copy(f"/tmp/new6_charts/{f}", f"runs/{RUN}/charts/{f}")

# 3. run.md
import importlib.util
spec = importlib.util.spec_from_file_location("ps", "scripts/publish_std.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)  # regenerates old runs too (idempotent, applies timeout fix)

R = json.load(open(f"runs/{RUN}/data/results.json"))
def hv(h, k): return R["harnesses"][h][k]
ps.run_md(RUN,
  "2026-11-19 — strata_iq3s × 6 new leaderboard harnesses, SWE-bench Verified (40)",
  "SWE-bench Verified, same 40 instances as the 2026-11-18 five-way run",
  "can the six harnesses newly added from the HF harness-leaderboard join the top group — and does n=40 reveal a single leader?",
  {"Date": "2026-11-18 → 2026-11-20 (openclaw 18:45 UTC 18th; codex→hermes-agent 23:56 UTC 18th → 00:43 UTC 20th; grading interleaved)",
   "Model (fixed)": "`strata_iq3s` (Qwen3.8-27B IQ3_S) via llama-swap `127.0.0.1:8080`",
   "Serving": "strata 0.2.13, `--context 128k --parallel 2 --kv k8v4 --vision cpu --mtp`, workers=2",
   "Dataset": "same 40 SWE-bench Verified instances as the five-way sb40 run (`sb40_new.json`)",
   "Grading": "official swebench F2P/P2P grader, **outside** the harness container",
   "Agent loop": "headless, official `swebench/sweb.eval.x86_64.*` image, 2700 s timeout; Hermes Agent ran in its own `nousresearch/hermes-agent` image",
   "Harnesses": "Codex 0.170.0 · Qwen Code 0.28.0 · Kimi Code 2.6.3 · Grok Build 1.0.89 · OpenClaw 2026.6.35 · Hermes Agent 0.23.1",
   "BYOK": "all harnesses pointed at llama-swap (`/v1` chat-completions; Codex via native Responses API `/v1/responses`)",
   "Telemetry": "llama-swap activity ring (per-request tokens) + per-instance wall windows"},
  [f"**Qwen Code and Kimi Code join the top group** — 34/40 each, statistically indistinguishable from OpenCode 35 and Claude Code 34 (all pairs p=1.0). At n=40 there is a four-way tie at the top, not a single leader.",
   f"**Codex {hv('codex','resolved')}/40 and Grok {hv('grok','resolved')}/40 form a solid mid tier** — not distinguishable from the top group at this n, but far from the tail.",
   f"**OpenClaw {hv('openclaw','resolved')}/40 is significantly below the leaders** (vs OpenCode p=0.016, Claude Code & Kimi Code p=0.031) and paid for it with {hv('openclaw','empty')} empty patches.",
   f"**Hermes Agent {hv('hermes-agent','resolved')}/40 finishes last — with a hard infra caveat** (see below): 16/40 runs died on its own gateway-disconnect failure before doing any work; among the 24 runs that completed normally it still resolved 11 (46% vs Qwen Code's 94% on completed runs).",
   f"**Efficiency crown stays with the original pair** — best of the new six is Kimi Code at {hv('kimi-code','resolved_per_gpu_h'):.2f} resolved/GPU-h, still below Claude Code (5.22) and OpenCode (6.22) from the five-way run; Qwen Code ({hv('qwen-code','resolved_per_gpu_h'):.2f}) and Grok ({hv('grok','resolved_per_gpu_h'):.2f}) burn the most wall per solve.",
   f"**Reliability clean-sheet again for Kimi Code** — {hv('kimi-code','empty')} empty patches, matching Claude Code; Qwen Code near-perfect with {hv('qwen-code','empty')}."],
  ["Hermes Agent's daemon architecture (gateway + unix socket) is fragile inside disposable containers: 16/40 runs exited 1 with `Gateway disconnected` and produced no trajectory. Treat 11/40 as its harness-integration floor, not its capability ceiling. Its runs also benefited from no Hindsight cron contention (cron paused all sweep).",
   "OpenClaw's 11 empty patches include suspected session-state interference at workers=2 (shared config home) — re-test at workers=1 before trusting its rank relative to Codex/Grok.",
   "Harness versions float: these are the Nov-2026 builds; upstream harnesses update fast.",
   "n=40 still cannot separate the four leaders; separating 34 from 35 needs ~150+ instances.",
   "Absolute scores inflated by training-set memorization of pre-2022 instances; ranking stays valid (contamination constant across harnesses)."])

# 4. RESULTS.md row
row = ("| 2026-11-19 | [strata_iq3s × 6 new leaderboard harnesses, SWE-bench Verified (40)]"
       f"(runs/{RUN}/run.md) | Can the new six join the top group? | strata_iq3s | "
       "Codex · Qwen Code · Kimi Code · Grok Build · OpenClaw · Hermes Agent | "
       "**Qwen Code 34 & Kimi Code 34 tie with OpenCode 35 / Claude Code 34 (p=1.0) — four-way top**; "
       "Codex 31 / Grok 30 mid tier; **OpenClaw 28 significantly behind leaders**; "
       "Hermes Agent 11/40 (16/40 harness-infra gateway deaths). |\n")
r = open("RESULTS.md").read()
if RUN not in r:
    anchor = "\nEach run lives"
    r = r.replace(anchor, "\n" + row.rstrip("\n") + anchor)
    open("RESULTS.md", "w").write(r)

# 5. leaderboard re-aggregate
subprocess.run(["python3", "scripts/aggregate.py"], check=True)
print("DRIVER_DONE", RUN)
