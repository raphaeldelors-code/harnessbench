#!/usr/bin/env python3
"""Consolidate harnessbench sweep outputs into one JSON for report rendering."""
import json, glob, os
os.chdir("/home/rapha/harnessbench")
out = {"run_id": "2026-11-17-strata-iq3s-sb10-5way", "harnesses": {}}
instances = sorted(d["instance_id"] for d in json.load(open("/home/rapha/agentswe/sb10_new.json")))
out["instances"] = instances
for h in ["mini", "claude-code", "pi", "deepseek-harness", "opencode"]:
    od = f"out/{h}"
    e = json.load(open(f"openai__strata_iq3s.hb_{h}.json"))
    wall = 0.0
    try:
        for line in open(f"{od}/windows.jsonl"):
            w = json.loads(line); wall += w["t1"] - w["t0"]
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
    # per-instance outcome: R resolved / U unresolved (patch, not resolved) / E empty / T timeout
    preds = json.load(open(f"{od}/preds.json"))
    per = {}
    resolved = set(e.get("resolved_ids", [])); empty = set(e.get("empty_patch_ids", []))
    for i in instances:
        if i in resolved: per[i] = "R"
        elif i in empty: per[i] = "E"
        elif i in preds and preds[i].get("model_patch", "").strip(): per[i] = "U"
        else: per[i] = "?"
    # timeouts: ec files
    for f in glob.glob(f"work/*/out/{h}/ec"):
        iid = f.split("/")[2 - 1]  # work/<iid>/out/<h>/ec
        iid = f.split("/")[1]
        try:
            if open(f).read().strip() == "124": per[iid] = "T"
        except Exception: pass
    out["harnesses"][h] = {
        "resolved": len(resolved), "empty": len(empty), "wall_s": round(wall),
        "calls": calls, "input_tokens": tin, "output_tokens": tout,
        "cache_tokens": tc, "resolved_per_gpu_h": round(len(resolved) / (wall / 3600), 2) if wall else None,
        "per_instance": per,
        "resolved_ids": sorted(resolved),
    }
json.dump(out, open("/tmp/hb_sweep_results.json", "w"), indent=1)
print("OK", {h: v["resolved"] for h, v in out["harnesses"].items()})
