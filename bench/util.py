"""Tiny stdlib I/O helpers (always via context managers)."""

from __future__ import annotations

import json


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_json(path: str):
    with open(path) as fh:
        return json.load(fh)


def write_json(path: str, obj) -> None:
    with open(path, "w") as fh:
        json.dump(obj, fh)
