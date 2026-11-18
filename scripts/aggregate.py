#!/usr/bin/env python3
"""Cross-run leaderboard: aggregates every runs/*/data/results.json into
LEADERBOARD.md + charts/leaderboard.png at the repo root.

Grouping key = (model, bench). For each harness the BEST score across all
runs of that key is shown, with the run date that achieved it. Run dirs
stay untouched and authoritative; this view is derived and regenerable."""
import glob, json, os, re, collections

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI",
        "mini": "mini-swe-agent", "opencode": "OpenCode", "pi": "Pi",
        "kiro": "Kiro"}

runs = []
for d in sorted(glob.glob("runs/*/data/results.json")):
    slug = d.split("/")[1]
    m = re.match(r"(\d{4}-\d{2}-\d{2})-(.*)-5way", slug)
    date, rest = m.group(1), m.group(2)
    parts = rest.split("-")
    bench = next((p for p in parts if re.fullmatch(r"sb\d+", p)), "?")
    model = "-".join(p for p in parts if p != bench).replace("-", "_")
    runs.append({"date": date, "slug": slug, "bench": bench, "model": model,
                 "data": json.load(open(d))})

# best per (model, bench, harness)
best = {}
for r in runs:
    n = r["data"]["instances"] if isinstance(r["data"]["instances"], int) else len(r["data"]["instances"])
    for h, v in r["data"]["harnesses"].items():
        key = (r["model"], r["bench"], h)
        rate = v["resolved"] / n
        cur = best.get(key)
        if cur is None or rate > cur["rate"]:
            best[key] = {"rate": rate, "resolved": v["resolved"], "n": n,
                         "gpu_h": v["resolved_per_gpu_h"], "run": r["date"], "slug": r["slug"]}

BENCH_NAME = {"sb10": "SWE-bench Verified (10)", "sb40": "SWE-bench Verified (40)"}
lines = ["# Leaderboard — best score per harness (cross-run)",
         "",
         "Derived from every run below; the best rate per (model, bench, harness) wins.",
         "Regenerate: `python3 scripts/aggregate.py`. Each run's own numbers stay in `runs/<slug>/run.md`.",
         ""]
for (model, bench) in sorted({(m, b) for (m, b, _) in best}):
    hs = {h: v for (m, b, h), v in best.items() if (m, b) == (model, bench)}
    lines += [f"## {model} — {BENCH_NAME.get(bench, bench)}", "",
              "| Harness | Best resolved | Best rate | Resolved/GPU-h | Achieved in |",
              "|---|---|---|---|---|"]
    for h, v in sorted(hs.items(), key=lambda kv: -kv[1]["rate"]):
        lines.append(f"| {NAME.get(h, h)} | {v['resolved']}/{v['n']} | **{100*v['rate']:.1f}%** | {v['gpu_h']:.2f} | [{v['run']}](runs/{v['slug']}/run.md) |")
    lines.append("")
lines += ["![leaderboard](charts/leaderboard.png)", ""]
open("LEADERBOARD.md", "w").write("\n".join(lines))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
groups = sorted({(m, b) for (m, b, _) in best})
raw_h = sorted({h for (_, _, h) in best})
fig, ax = plt.subplots(figsize=(10, 5))
w = 0.8 / max(1, len(groups))
for gi, (m, b) in enumerate(groups):
    vals = [100 * best[(m, b, h)]["rate"] for h in raw_h if (m, b, h) in best]
    xs = [raw_h.index(h) + gi * w - 0.4 + w / 2 for h in raw_h if (m, b, h) in best]
    ax.bar(xs, vals, width=w, label=f"{m} · {BENCH_NAME.get(b, b)}")
    for x, v in zip(xs, vals):
        ax.text(x, v + 1, f"{v:.0f}", ha="center", fontsize=8)
ax.set_xticks(range(len(raw_h))); ax.set_xticklabels([NAME.get(h, h) for h in raw_h])
ax.set_ylim(0, 100)
ax.set_ylabel("resolved % (best per harness)")
ax.set_title("Cross-run best score per harness")
ax.legend(fontsize=8); ax.grid(axis="y", alpha=.3)
os.makedirs("charts", exist_ok=True)
fig.savefig("charts/leaderboard.png", dpi=140, bbox_inches="tight")
print("wrote LEADERBOARD.md + charts/leaderboard.png;",
      f"{len(runs)} runs aggregated, {len(best)} best-cells")
