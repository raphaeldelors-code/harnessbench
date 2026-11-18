#!/usr/bin/env python3
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

R = json.load(open("/tmp/hb_sweep_results40.json"))
N = len(R["instances"])
H = ["claude-code", "deepseek-harness", "mini", "opencode", "pi"]
NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI", "mini": "mini-swe-agent",
        "opencode": "OpenCode", "pi": "Pi"}
C = {"claude-code": "#d97757", "deepseek-harness": "#4e79a7", "mini": "#59a14f",
     "opencode": "#b07aa1", "pi": "#f28e2b"}
out = "/tmp/hbcharts40"
import os; os.makedirs(out, exist_ok=True)

def bars(metric, title, fmt="{}", h=None):
    vals = [R["harnesses"][x][metric] if h is None else h[x] for x in H]
    fig, ax = plt.subplots(figsize=(7, 3.6), dpi=150)
    b = ax.bar([NAME[x] for x in H], vals, color=[C[x] for x in H])
    ax.set_title(title, fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", labelrotation=15)
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width()/2, r.get_height(), fmt.format(v),
                ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(vals) * 1.18)
    fig.tight_layout(); fig.savefig(f"{out}/{metric}.png"); plt.close(fig)

bars("resolved", f"Resolved instances (of {N} SWE-bench Verified)")
bars("wall_s", f"Agent wall time (seconds, sum over {N} instances)", fmt="{:,.0f}")
bars("input_tokens", f"Input tokens consumed (sum over {N} instances)", fmt="{:,.0f}")
bars("calls", f"LLM API calls (sum over {N} instances)", fmt="{:,.0f}")
rgh = {x: R["harnesses"][x]["resolved_per_gpu_h"] for x in H}
bars("resolved_per_gpu_h", "Efficiency: resolved per GPU-hour", fmt="{:.2f}", h=rgh)

# per-instance outcome matrix
insts = R["instances"]
short = [i.split("__")[1] for i in insts]
fig, ax = plt.subplots(figsize=(8.5, 11), dpi=150)
COLOR = {"R": "#2e7d32", "U": "#e0a800", "E": "#c62828", "T": "#6a1b9a", "?": "#9e9e9e"}
MARK = {"R": "resolved", "U": "patched, failed", "E": "empty patch", "T": "timeout", "?": "no run"}
for xi, x in enumerate(H):
    for yi, i in enumerate(insts):
        v = R["harnesses"][x]["per_instance"].get(i, "?")
        ax.add_patch(plt.Rectangle((xi, yi), 0.92, 0.92, color=COLOR[v]))
        ax.text(xi + .46, yi + .46, {"R": "✓", "U": "✗", "E": "∅", "T": "T", "?": "·"}[v],
                ha="center", va="center", color="white", fontsize=9)
ax.set_xlim(0, len(H)); ax.set_ylim(0, len(insts))
ax.set_xticks([xi + .46 for xi in range(len(H))])
ax.set_xticklabels([NAME[x] for x in H], fontsize=9)
ax.set_yticks([yi + .46 for yi in range(len(insts))])
ax.set_yticklabels(short, fontsize=7)
ax.xaxis.set_ticks_position("top"); ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
handles = [plt.Rectangle((0, 0), 1, 1, color=COLOR[k]) for k in ["R", "U", "E", "T"]]
ax.legend(handles, [MARK[k] for k in ["R", "U", "E", "T"]], loc="upper center",
          bbox_to_anchor=(0.5, -0.03), ncol=4, fontsize=8, frameon=False)
ax.set_title(f"Per-instance outcome ({N} SWE-bench Verified × 5 harnesses, strata_iq3s)", fontsize=11)
fig.tight_layout(); fig.savefig(f"{out}/matrix.png", bbox_inches="tight"); plt.close(fig)
print("charts done")
for x in H:
    print(x, R["harnesses"][x]["resolved"], "resolved")
