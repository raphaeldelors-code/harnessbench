"""Grading and reporting: official swebench F2P/P2P grading, the legacy
mini-swe-agent lane, and leaderboard aggregation."""

from __future__ import annotations

import glob
import json
import os
import subprocess
import threading
import time

from bench import config as C
from bench import harnesses as H
from bench import runner as R
from bench.util import read_json, write_json


def cmd_eval(a):
    od = str(C.OUT / a.harness)
    cmd = [
        C.EVAL_PYTHON,
        "-m",
        "swebench.harness.run_evaluation",
        "-d",
        C.DATASET,
        "-s",
        "test",
        "-p",
        os.path.join(od, "preds.json"),
        "-id",
        f"hb_{a.harness}",
        "--max_workers",
        "2",
        "-t",
        "900",
    ]
    print(" ".join(cmd))
    subprocess.run(cmd)


def cmd_run_mini(a):
    """Legacy lane: mini-swe-agent drives its own swebench integration from the host."""
    tag = "mini"
    od = str(C.OUT / tag)
    os.makedirs(od, exist_ok=True)
    sel = R.load_instances(a.inst or None)
    filt = "^(" + "|".join(sorted(sel)) + ")$"
    cmd = [
        C.EVAL_PYTHON,
        "-m",
        H.MINI_PKG,
        "-o",
        str(C.MINI_DIR / "out_mini"),
        "-m",
        "openai/" + C.MODEL,
        "-c",
        "swebench.yaml",
        "-c",
        "bench_local.yaml",
        "--subset",
        "verified",
        "--split",
        "test",
        "--filter",
        filt,
        "-w",
        str(max(1, getattr(a, "workers", 1))),
    ]
    stop = threading.Event()
    threading.Thread(target=lambda: R._telemetry_poller(od, stop), daemon=True).start()
    t0 = int(time.time())
    subprocess.run(cmd, cwd=str(C.MINI_DIR))
    t1 = int(time.time())
    with open(os.path.join(od, "windows.jsonl"), "a") as fh:
        fh.write(json.dumps({"harness": tag, "instance_id": "ALL", "t0": t0, "t1": t1}) + "\n")
    src = str(C.MINI_DIR / "out_mini" / "preds.json")
    if os.path.exists(src):
        dstp = os.path.join(od, "preds.json")
        merged = read_json(dstp) if os.path.exists(dstp) else {}
        merged.update(read_json(src))
        write_json(dstp, merged)
    stop.set()


def _telemetry_totals(od: str) -> tuple[int, int, int, int]:
    calls = tin = tout = tcache = 0
    seen = set()
    try:
        with open(os.path.join(od, "activity.jsonl")) as lines:
            for line in lines:
                try:
                    snap = json.loads(line)
                except Exception:
                    continue
                for row in snap.get("data", snap if isinstance(snap, list) else []):
                    rid = row.get("id")
                    if rid in seen:
                        continue
                    seen.add(rid)
                    t = row.get("tokens", {})
                    tin += t.get("input_tokens", 0) or 0
                    tout += t.get("output_tokens", 0) or 0
                    tcache += t.get("cache_tokens", 0) or 0
                    calls += 1
    except FileNotFoundError:
        pass
    return calls, tin, tout, tcache


def cmd_report(_a=None):
    try:
        n_inst = len(read_json(C.DATASET))
    except Exception:
        n_inst = 0
    rows = []
    for h in list(H.HARNESSES) + ["mini"]:
        od = str(C.OUT / h)
        if not os.path.isdir(od):
            continue
        resolved = empty = "?"
        for f in glob.glob(str(C.RESULTS_DIR / f"openai__*.hb_{h}*.json")):
            try:
                r = read_json(f)
                resolved = f"{len(r.get('resolved_ids', []))}/{n_inst}"
                empty = str(len(r.get("empty_patch_ids", [])))
            except Exception:
                pass
        wall = 0.0
        try:
            with open(os.path.join(od, "windows.jsonl")) as lines:
                for line in lines:
                    w = json.loads(line)
                    wall += w["t1"] - w["t0"]
        except (FileNotFoundError, KeyError):
            pass
        calls, tin, tout, tcache = _telemetry_totals(od)
        rows.append((h, resolved, empty, round(wall / 3600, 2), calls, tin, tout, tcache))
    print("| harness | resolved | empty patches | wall h | api calls | input tok | output tok | cached tok |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        gh = r[3]
        rr = r[1]
        rgh = f"{int(rr.split('/')[0]) / gh:.2f}/GPUh" if gh and rr != "?" else "?"
        print("|", " | ".join(map(str, r[:8])), "| resolved_per_GPUh:", rgh)
