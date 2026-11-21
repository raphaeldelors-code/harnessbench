#!/usr/bin/env python3
"""Aggregate every runs/<id>/ into site/public/data/site.json for the dashboard.

Reads, per run: run.json (manifest), data/results.json, data/windows_*.jsonl,
data/versions.json. McNemar pairs are recomputed from per-instance grids when
missing, so every run always has a populated significance chart.
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


def build():
    runs = []
    for run_dir in sorted((ROOT / "runs").iterdir()):
        data = run_dir / "data"
        results = load(data / "results.json")
        if not results:
            continue
        manifest = load(run_dir / "run.json") or {}
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
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(runs)} runs)")


if __name__ == "__main__":
    sys.exit(build())
