#!/usr/bin/env python3
"""Consolidate harnessbench sb40 sweep outputs into one JSON for report rendering."""
import json, glob, os, itertools
os.chdir("/home/rapha/harnessbench")
RUN_ID = "2026-11-18-strata-iq3s-sb40-5way"
WSINCE = 1794900000  # sweep50 era only (skip the sb10 run windows in same files)
out = {"run_id": RUN_ID, "harnesses": {}}
instances = sorted(d["instance_id"] for d in json.load(open("data/instances/sb40_new.json")))
out["instances"] = instances
for h in ["mini", "claude-code", "pi", "deepseek-harness", "opencode"]:
    od = f"out/{h}"
    e = json.load(open(f"openai__strata_iq3s.hb_{h}.json"))
    wall = 0.0
    try:
        for line in open(f"{od}/windows.jsonl"):
            w = json.loads(line)
            if w["t0"] >= WSINCE: wall += w["t1"] - w["t0"]
    except FileNotFoundError:
        pass
    calls = tin = tout = tc = 0
    seen = set()
    try:
        for line in open(f"{od}/activity.jsonl"):
            try: snap = json.loads(line)
            except Exception: continue
            for rowd in snap.get("data", snap if isinstance(snap, list) else []):
                if rowd.get("model") != "strata_iq3s": continue
                ts = rowd.get("timestamp", "")
                rid = rowd.get("id")
                if rid in seen: continue
                seen.add(rid)
                t = rowd.get("tokens") or {}
                tin += t.get("input_tokens") or 0
                tout += t.get("output_tokens") or 0
                tc += t.get("cache_tokens") or 0
                calls += 1
    except FileNotFoundError:
        pass
    preds = json.load(open(f"{od}/preds.json"))
    per = {}
    resolved = set(e.get("resolved_ids", [])); empty = set(e.get("empty_patch_ids", []))
    for i in instances:
        if i in resolved: per[i] = "R"
        elif i in empty: per[i] = "E"
        elif i in preds and preds[i].get("model_patch", "").strip(): per[i] = "U"
        else: per[i] = "?"
    out["harnesses"][h] = {
        "resolved": len(resolved), "empty": len(empty), "wall_s": round(wall),
        "calls": calls, "input_tokens": tin, "output_tokens": tout,
        "cache_tokens": tc, "resolved_per_gpu_h": round(len(resolved) / (wall / 3600), 2) if wall else None,
        "per_instance": per, "resolved_ids": sorted(resolved),
    }
# McNemar pairwise on paired outcomes
hs = list(out["harnesses"])
mc = {}
for a, b in itertools.combinations(hs, 2):
    ra = set(out["harnesses"][a]["resolved_ids"]); rb = set(out["harnesses"][b]["resolved_ids"])
    mc[f"{a}|{b}"] = {"a_only": len(ra - rb), "b_only": len(rb - ra)}
out["mcnemar"] = mc
json.dump(out, open("/tmp/hb_sweep_results40.json", "w"), indent=1)
print("OK", {h: v["resolved"] for h, v in out["harnesses"].items()})
print("MCNEMAR", mc)
