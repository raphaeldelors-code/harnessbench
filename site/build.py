#!/usr/bin/env python3
"""Aggregate every runs/<id>/data/ into site/public/data/site.json for the dashboard."""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "public" / "data" / "site.json"


def load(path: Path):
    gz = Path(str(path) + ".gz")
    p = gz if gz.exists() else path
    if not p.exists():
        return None
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt") as fh:
        return json.load(fh)


def read_jsonl(path: Path):
    gz = Path(str(path) + ".gz")
    p = gz if gz.exists() else path
    if not p.exists():
        return []
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def build():
    runs = []
    for run_dir in sorted((ROOT / "runs").iterdir()):
        data = run_dir / "data"
        results = load(data / "results.json")
        if not results:
            continue
        harnesses = {}
        windows = {}
        for name, h in results["harnesses"].items():
            harnesses[name] = {k: v for k, v in h.items() if k not in ("resolved_ids",)}
            wins = read_jsonl(data / f"windows_{name}.jsonl")
            if wins:
                windows[name] = [
                    {"inst": w.get("inst") or w.get("instance"), "wall_s": w.get("wall_s"),
                     "ec": w.get("ec")}
                    for w in wins
                ]
        versions = load(data / "versions.json") or {}
        runs.append({
            "id": run_dir.name,
            "date": run_dir.name[:10],
            "model": versions.get("model", "strata_iq3s"),
            "n_instances": len(results["instances"]),
            "instances": results["instances"],
            "harnesses": harnesses,
            "windows": windows,
            "mcnemar": results.get("mcnemar", {}),
            "versions": versions,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated": str(pd_today()), "runs": runs}, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(runs)} runs)")


def pd_today():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


if __name__ == "__main__":
    sys.exit(build())
