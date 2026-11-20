#!/usr/bin/env python3
"""Add 11-way McNemar (old 5 + new 6, identical 40 instances) as charts + table in the new run.md."""
import json, math, itertools, os
os.chdir("/home/rapha/harnessbench")
RUN = "runs/2026-11-19-strata-iq3s-sb40-6way-new"

old = json.load(open("runs/2026-11-18-strata-iq3s-sb40-5way/data/results.json"))
new = json.load(open(f"{RUN}/data/results.json"))
res = {h: set(v["resolved_ids"]) for h, v in old["harnesses"].items()}
res.update({h: set(v["resolved_ids"]) for h, v in new["harnesses"].items()})
NAME = {"claude-code": "Claude Code", "deepseek-harness": "DeepSeek TUI", "mini": "mini-swe-agent",
        "opencode": "OpenCode", "pi": "Pi", "codex": "Codex", "qwen-code": "Qwen Code",
        "kimi-code": "Kimi Code", "grok": "Grok Build", "openclaw": "OpenClaw", "hermes-agent": "Hermes Agent"}
order = sorted(res, key=lambda h: (-len(res[h]), NAME[h]))

def p_exact(aonly, bonly):
    n = aonly + bonly
    if n == 0: return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(aonly, bonly) + 1)) / 2 ** n)

cells, rows_md = {}, []
for a in order:
    row = []
    for b in order:
        if a == b: row.append("–")
        else:
            p = p_exact(len(res[a] - res[b]), len(res[b] - res[a]))
            cells[(a, b)] = p
            row.append(f"{p:.3f}" if p >= 0.001 else "<.001")
    rows_md.append(f"| **{NAME[a]}** ({len(res[a])}/40) | " + " | ".join(row) + " |")
sig = [(a, b, cells[(a, b)]) for a, b in itertools.combinations(order, 2) if cells[(a, b)] < 0.05]

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
labels = [NAME[h] for h in order]
M = np.array([[cells.get((a, b)) if a != b else np.nan for b in order] for a in order])
fig, ax = plt.subplots(figsize=(10, 8.2))
cmap = matplotlib.colors.LinearSegmentedColormap.from_list("p", ["#b71c1c", "#ef9a9a", "#fdd835", "#9ccc65", "#2e7d32"])
im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1)
ax.set_xticks(range(11), labels, rotation=60, ha="right", fontsize=9)
ax.set_yticks(range(11), labels, fontsize=9)
for i in range(11):
    for j in range(11):
        if i == j: ax.text(j, i, "–", ha="center", va="center", color="#999", fontsize=8)
        else:
            p = M[i, j]
            ax.text(j, i, f"{p:.2f}" if p >= 0.01 else "<.01", ha="center", va="center",
                    fontsize=7.5, color="white" if (p < 0.04 or p > 0.9) else "black",
                    weight="bold" if p < 0.05 else "normal")
ax.set_title("Exact paired McNemar p (symmetric) — all 11 harnesses, same 40 instances.\nBold red = the pair differs significantly (direction: higher solved count wins)", fontsize=10)
fig.colorbar(im, shrink=0.8)
fig.tight_layout()
fig.savefig(f"{RUN}/charts/mcnemar_11way.png", dpi=130)

S = np.array([[len(res[a] & res[b]) if a != b else len(res[a]) for b in order] for a in order])
fig, ax = plt.subplots(figsize=(10, 8.2))
im = ax.imshow(S, cmap="viridis")
ax.set_xticks(range(11), labels, rotation=60, ha="right", fontsize=9)
ax.set_yticks(range(11), labels, fontsize=9)
for i in range(11):
    for j in range(11):
        ax.text(j, i, str(S[i, j]), ha="center", va="center", fontsize=7.5,
                color="white" if S[i, j] > 20 else "black")
ax.set_title("Solved in common (diag = own solved count) — all 11 harnesses × 40", fontsize=10)
fig.colorbar(im, shrink=0.8)
fig.tight_layout()
fig.savefig(f"{RUN}/charts/solved_matrix_11way.png", dpi=130)

md = open(f"{RUN}/run.md").read()
sec = ["\n## Paired significance — full 11-way matrix\n",
       "Same 40 instances as the 2026-11-18 five-way run, same model → every pair across both runs is directly comparable.\n",
       "| Row harness (solved) | " + " | ".join(NAME[h] for h in order) + " |",
       "|" + "---|" * 12] + rows_md + [
       "",
       "**Pairs with p < 0.05:** " + "; ".join(f"{NAME[a]} vs {NAME[b]} (p={p:.3f})" for a, b, p in sorted(sig, key=lambda x: x[2])) + ".",
       "",
       "![McNemar 11-way](charts/mcnemar_11way.png)", "", "![Solved matrix 11-way](charts/solved_matrix_11way.png)", ""]
anchor = "\n## Caveats"
md = md.replace(anchor, "\n".join(sec) + anchor)
open(f"{RUN}/run.md", "w").write(md)
print("11WAY_DONE", len(sig), "significant pairs")
