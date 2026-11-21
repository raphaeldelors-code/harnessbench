#!/usr/bin/env python3
"""Aggregate every runs/<id>/ into site/public/data/site.json for the dashboard.

Two lanes share runs/. A manifest's optional `kind` picks the lane; absent means
"harness" (every run merged before the model lane existed), and an "m-" id prefix
is the fallback, so a model run can never leak into the 6-way harness grids.

Harness run: run.json (manifest), data/results.json, data/windows_*.jsonl,
data/versions.json. McNemar pairs are recomputed from per-instance grids when
missing, so every run always has a populated significance chart.

Model run: run.json (kind "model"), data/model_results.json. Rows are grouped
into input-size cells with per-leg medians; warm-up legs feed tables only.
"""

from __future__ import annotations

import datetime
import gzip
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "public" / "data" / "site.json"
UNRECORDED = "unrecorded"


def _open(path: Path):
    gz = Path(str(path) + ".gz")
    p = gz if gz.exists() else path
    if not p.exists():
        return None
    return gzip.open(p, "rt") if p.suffix == ".gz" else open(p, encoding="utf-8")


def load(path: Path):
    fh = _open(path)
    if fh is None:
        return None
    with fh:
        return json.load(fh)


def read_jsonl(path: Path):
    fh = _open(path)
    if fh is None:
        return []
    with fh:
        return [json.loads(line) for line in fh if line.strip()]


def mcnemar_pairs(grid: dict[str, dict[str, str]], instances: list[str]) -> dict:
    """Exact McNemar discordant counts (a_only, b_only) for every harness pair."""
    names = sorted(grid)
    pairs = {}
    for a, b in itertools.combinations(names, 2):
        a_only = sum(1 for i in instances if grid[a].get(i) == "R" and grid[b].get(i) != "R")
        b_only = sum(1 for i in instances if grid[b].get(i) == "R" and grid[a].get(i) != "R")
        pairs[f"{a}|{b}"] = {"a_only": a_only, "b_only": b_only}
    return pairs


def windows_for(data: Path, name: str) -> list[dict]:
    # One row per instance: wall time sums ALL recorded windows (crash/retry
    # restarts included). Recording raw windows let ~0 s crashed starts pollute
    # p10/median (codex/grok medians read ~0 min with 40 real runs out of 80 rows).
    totals: dict[str, float] = {}
    for w in read_jsonl(data / f"windows_{name}.jsonl"):
        inst = w.get("instance_id") or w.get("inst") or w.get("instance")
        wall = w.get("wall_s")
        if wall is None and w.get("t0") is not None and w.get("t1") is not None:
            wall = w["t1"] - w["t0"]
        if inst and wall is not None:
            totals[inst] = totals.get(inst, 0.0) + wall
    return [{"inst": inst, "wall_s": wall} for inst, wall in totals.items()]


def kind_of(manifest: dict, run_id: str) -> str:
    """Which bench lane a run directory belongs to."""
    kind = manifest.get("kind")
    if kind in ("harness", "model"):
        return kind
    return "model" if run_id.startswith("m-") else "harness"


def median(values: list) -> float | int | None:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def is_warm(leg: str) -> bool:
    """Warm-up legs (warm, warm2, warm-a) are cold-load artifacts: never charted,
    never averaged into a median — they only belong in the raw-row table."""
    return leg.startswith("warm")


def cell_label(in_tok) -> str:
    """Input-size bucket for a row, by nearest thousand tokens."""
    return UNRECORDED if in_tok is None else f"{max(1, int(in_tok / 1000 + 0.5))}k"


def model_cells(rows: list[dict]) -> list[dict]:
    """Per input-size cell, the median pp/tps of each non-warm leg (the rep count
    tells the reader how much of the noise floor rule that cell actually meets)."""
    buckets: dict[str, dict] = {}
    for row in rows:
        leg = row.get("leg") or ""
        if is_warm(leg):
            continue
        bucket = buckets.setdefault(cell_label(row.get("in_tok")), {"in_tok": [], "legs": {}})
        if row.get("in_tok") is not None:
            bucket["in_tok"].append(row["in_tok"])
        bucket["legs"].setdefault(leg, []).append(row)
    cells = []
    for label, bucket in buckets.items():
        legs = {}
        for leg, group in bucket["legs"].items():
            legs[leg] = {
                "n": len(group),
                "pp": median([r.get("pp") for r in group]),
                "tps": median([r.get("tps") for r in group]),
            }
        cells.append({"cell": label, "in_tok": median(bucket["in_tok"]), "legs": legs})
    cells.sort(key=lambda c: (c["cell"] == UNRECORDED, c["in_tok"] if c["in_tok"] is not None else 10**12))
    return cells


def model_run(run_dir: Path, manifest: dict) -> dict | None:
    data = load(run_dir / "data" / "model_results.json")
    if not data:
        return None
    rows = data.get("rows", [])
    legs: list[str] = []
    for row in rows:
        leg = row.get("leg") or ""
        if not is_warm(leg) and leg not in legs:
            legs.append(leg)
    return {
        "id": run_dir.name,
        "kind": "model",
        "date": manifest.get("date", run_dir.name[2:12]),
        "title": manifest.get("title", run_dir.name),
        "model": manifest.get("model", {}),
        "engine": manifest.get("engine", ""),
        "verdict": manifest.get("verdict", "INFO"),
        "hardware": manifest.get("hardware", "bench-rig-01"),
        "notes": manifest.get("notes", ""),
        "n_rows": len(rows),
        "n_warm": sum(1 for r in rows if is_warm(r.get("leg") or "")),
        "legs": legs,
        "rows": rows,
        "cells": model_cells(rows),
    }


def model_summaries(model_runs: list[dict]) -> list[dict]:
    """Per served model: median decode/prefill over every non-warm row of its
    rounds, plus one verdict entry per round (so the site can show each round's
    delta against the medians of its sibling rounds)."""
    by_slug: dict[str, dict] = {}
    for mr in model_runs:
        slug = mr["model"].get("slug") or mr["id"]
        entry = by_slug.setdefault(
            slug,
            {"quant": "", "family": "", "engine": "", "tps": [], "pp": [], "rounds": []},
        )
        entry["quant"] = entry["quant"] or mr["model"].get("quant", "")
        entry["family"] = entry["family"] or mr["model"].get("family", "")
        entry["engine"] = entry["engine"] or mr.get("engine", "")
        measured = [r for r in mr["rows"] if not is_warm(r.get("leg") or "")]
        entry["tps"].extend(r.get("tps") for r in measured if r.get("tps") is not None)
        entry["pp"].extend(r.get("pp") for r in measured if r.get("pp") is not None)
        entry["rounds"].append(
            {
                "id": mr["id"],
                "date": mr["date"],
                "verdict": mr["verdict"],
                "tps": median([r.get("tps") for r in measured]),
                "pp": median([r.get("pp") for r in measured]),
                "n_rows": len(measured),
                "legs": mr["legs"],
            }
        )
    summaries = []
    for slug, entry in by_slug.items():
        rounds = sorted(entry["rounds"], key=lambda r: (r["date"], r["id"]))
        summaries.append(
            {
                "slug": slug,
                "quant": entry["quant"],
                "family": entry["family"],
                "engine": entry["engine"],
                "n_runs": len(rounds),
                "tps": median(entry["tps"]),
                "pp": median(entry["pp"]),
                "tps_range": [min(entry["tps"]), max(entry["tps"])] if entry["tps"] else None,
                "verdicts": rounds,
            }
        )
    summaries.sort(key=lambda m: m["tps"] if m["tps"] is not None else float("-inf"), reverse=True)
    return summaries


def build():
    runs = []
    model_runs = []
    for run_dir in sorted((ROOT / "runs").iterdir()):
        manifest = load(run_dir / "run.json") or {}
        if kind_of(manifest, run_dir.name) == "model":
            entry = model_run(run_dir, manifest)
            if entry:
                model_runs.append(entry)
            continue
        data = run_dir / "data"
        results = load(data / "results.json")
        if not results:
            continue
        grid = {name: h.get("per_instance", {}) for name, h in results["harnesses"].items()}
        mcn = results.get("mcnemar") or mcnemar_pairs(grid, results["instances"])
        harnesses = {}
        windows = {}
        for name, h in results["harnesses"].items():
            harnesses[name] = {k: v for k, v in h.items() if k != "resolved_ids"}
            wins = windows_for(data, name)
            if wins:
                windows[name] = wins
        versions = load(data / "versions.json") or {}
        runs.append(
            {
                "id": run_dir.name,
                "date": manifest.get("date", run_dir.name[:10]),
                "model": manifest.get("model", versions.get("model", "strata_iq3s")),
                "hardware": manifest.get("hardware", "bench-rig-01"),
                "rig_id": manifest.get("hardware", "bench-rig-01"),
                "dataset": manifest.get("dataset", {}),
                "seed": manifest.get("seed"),
                "workers": manifest.get("workers"),
                "n_instances": len(results["instances"]),
                "instances": results["instances"],
                "harnesses": harnesses,
                "windows": windows,
                "mcnemar": mcn,
                "versions": versions,
                "notes": manifest.get("notes", ""),
            }
        )
    hardware = load(ROOT / "data" / "hardware.json") or {}
    payload = {
        "generated": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "hardware": hardware,
        "runs": runs,
        "model_runs": model_runs,
        "models": model_summaries(model_runs),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(runs)} harness + {len(model_runs)} model runs)")


if __name__ == "__main__":
    sys.exit(build())
