#!/usr/bin/env python3
"""Cross-run leaderboard: aggregates every runs/*/data/results.json into
LEADERBOARD.md + charts/leaderboard.png + charts/leaderboard_efficiency.png.

Grouping key = (model, bench). Best score per harness across all runs of that
key, for EVERY standard metric (resolved rate, resolved/GPU-h, wall, calls,
input tokens). Run dirs stay authoritative; this view is derived/regenerable."""
import glob, json, os, re

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI",
        "mini": "mini-swe-agent", "opencode": "OpenCode", "pi": "Pi",
        "kiro": "Kiro"}
BENCH_NAME = {"sb10": "SWE-bench Verified (10)", "sb40": "SWE-bench Verified (40)"}

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

best = {}   # (model,bench,harness) -> best value per metric across runs
for r in runs:
    n = r["data"]["instances"] if isinstance(r["data"]["instances"], int) else len(r["data"]["instances"])
    for h, v in r["data"]["harnesses"].items():
        k = (r["model"], r["bench"], h)
        e = best.setdefault(k, {"run": r["date"], "slug": r["slug"], "n": n})
        for f, val, how in [("rate", v["resolved"] / n, "max"),
                            ("gpu_h", v["resolved_per_gpu_h"], "max"),
                            ("wall_h", v["wall_s"] / 3600, "min"),
                            ("calls", v["calls"], "min"),
                            ("inp", v["input_tokens"], "min"),
                            ("out", v["output_tokens"], "min")]:
            if f not in e or (val > e[f] if how == "max" else val < e[f]):
                e[f] = val

def tbl(model, bench, metric, colname, fmt, desc=True):
    hs = {h: v for (m, b, h), v in best.items() if (m, b) == (model, bench)}
    out = [f"| Harness | {colname} | Achieved in |", "|---|---|---|"]
    for h, v in sorted(hs.items(), key=lambda kv: (-kv[1][metric] if desc else kv[1][metric])):
        out.append(f"| {NAME.get(h, h)} | {fmt(v[metric])} | [{v['run']}](runs/{v['slug']}/run.md) |")
    return out

lines = ["# Leaderboard — best score per harness (cross-run)", "",
         "Derived from every run; the best value per (model, bench, harness) **per metric** wins.",
         "Regenerate: `python3 scripts/aggregate.py`. Each run's own numbers stay in `runs/<slug>/run.md`.", ""]
groups = sorted({(m, b) for (m, b, _) in best})
for (model, bench) in groups:
    n = next(iter(v["n"] for k, v in best.items() if k[:2] == (model, bench)))
    lines += [f"## {model} — {BENCH_NAME.get(bench, bench)}", "",
              "**Resolved rate (higher = better)**", ""]
    lines += tbl(model, bench, "rate", f"Best of {n}", lambda x: f"**{100*x:.1f}%**") + [""]
    lines += ["**Efficiency — resolved per GPU-hour (higher = better)**", ""]
    lines += tbl(model, bench, "gpu_h", "Best resolved/GPU-h", lambda x: f"**{x:.2f}**") + [""]
    lines += ["**Leanest total wall time (lower = better)**", ""]
    lines += tbl(model, bench, "wall_h", "Best wall (sum)", lambda x: f"{x:.2f} h", desc=False) + [""]
    lines += ["**Leanest traffic — LLM calls / input tokens (lower = better)**", ""]
    hs = {h: v for (m, b, h), v in best.items() if (m, b) == (model, bench)}
    lines += ["| Harness | Best calls | Best input tok | Achieved in |", "|---|---|---|---|"]
    for h, v in sorted(hs.items(), key=lambda kv: kv[1]["calls"]):
        lines.append(f"| {NAME.get(h, h)} | {v['calls']:,} | {v['inp']/1e6:.2f}M | [{v['run']}](runs/{v['slug']}/run.md) |")
    lines.append("")

lines += ["![leaderboard](charts/leaderboard.png)", "",
          "![leaderboard_efficiency](charts/leaderboard_efficiency.png)", ""]
open("LEADERBOARD.md", "w").write("\n".join(lines))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def grouped_bar(metric, ylabel, title, fname, pct=False):
    raw_h = sorted({h for (_, _, h) in best})
    fig, ax = plt.subplots(figsize=(10, 5))
    wdt = 0.8 / max(1, len(groups))
    for gi, (m, b) in enumerate(groups):
        hs = [h for h in raw_h if (m, b, h) in best]
        vals = [100 * best[(m, b, h)][metric] if pct else best[(m, b, h)][metric] for h in hs]
        xs = [raw_h.index(h) + gi * wdt - 0.4 + wdt / 2 for h in hs]
        ax.bar(xs, vals, width=wdt, label=f"{m} · {BENCH_NAME.get(b, b)}")
        for x, v in zip(xs, vals):
            ax.text(x, v + (1 if pct else max(vals) * 0.02), f"{v:.0f}" if pct else f"{v:.1f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(raw_h))); ax.set_xticklabels([NAME.get(h, h) for h in raw_h])
    if pct: ax.set_ylim(0, 100)
    else: ax.set_ylim(0, max(max(100 * 0 + best[(m, b, h)][metric] for m, b in groups for h in raw_h if (m, b, h) in best), 1) * 1.15)
    ax.set_ylabel(ylabel); ax.set_title(title)
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=.3)
    os.makedirs("charts", exist_ok=True)
    fig.savefig(f"charts/{fname}", dpi=140, bbox_inches="tight")

grouped_bar("rate", "resolved % (best per harness)", "Cross-run best score per harness", "leaderboard.png", pct=True)
grouped_bar("gpu_h", "resolved per GPU-hour (best)", "Cross-run best efficiency per harness", "leaderboard_efficiency.png")
print(f"wrote LEADERBOARD.md + 2 charts; {len(runs)} runs, {len(best)} cells")
