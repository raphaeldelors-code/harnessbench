#!/usr/bin/env python3
"""Validate data files against JSON schemas; also validate harness CLI version pinning."""

from __future__ import annotations

import glob
import json
import sys

from jsonschema import Draft7Validator

CHECKS = [
    ("data/hardware.json", "schemas/hardware.schema.json"),
    ("site/public/data/site.json", "schemas/site.schema.json"),
    ("site/public/data/tuning.json", "schemas/tuning.schema.json"),
]


def validate(path: str, schema_path: str) -> list[str]:
    with open(schema_path) as fh:
        schema = json.load(fh)
    with open(path) as fh:
        data = json.load(fh)
    errors = sorted(Draft7Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message[:120]}" for e in errors]


def main() -> int:
    fails = 0
    for path, schema_path in CHECKS:
        errs = validate(path, schema_path)
        status = "ok" if not errs else "FAIL"
        print(f"[schema] {path}: {status}")
        for e in errs[:8]:
            print(f"   - {e}")
            fails += 1
    for manifest in sorted(glob.glob("runs/*/run.json")):
        errs = validate(manifest, "schemas/run_manifest.schema.json")
        print(f"[schema] {manifest}: {'ok' if not errs else 'FAIL'}")
        for e in errs[:8]:
            print(f"   - {e}")
            fails += 1
    # cross-file: every run must reference a rig that exists in data/hardware.json
    with open("data/hardware.json") as fh:
        hw = json.load(fh)
    rig_ids = {hw["id"]} if isinstance(hw, dict) else {h["id"] for h in hw}
    for manifest in sorted(glob.glob("runs/*/run.json")):
        with open(manifest) as fh:
            m = json.load(fh)
        if m.get("hardware") not in rig_ids:
            print(f"[rig-ref] {manifest}: hardware '{m.get('hardware')}' not in {sorted(rig_ids)}")
            fails += 1
        if not glob.glob(manifest.replace("run.json", "data/versions.json")):
            print(f"[rig-ref] {manifest}: missing data/versions.json (reproducibility contract)")
            fails += 1
    print("validate_data:", "OK" if fails == 0 else f"{fails} ERRORS")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
