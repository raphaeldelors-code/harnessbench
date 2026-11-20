#!/usr/bin/env python3
"""Fail if source files hardcode personal home paths (/home/<user> or /Users/<user>).

The project must stay machine-agnostic: everything user-specific belongs in
environment variables (see bench/config.py) or .env, never in tracked source.
Dataset payloads under data/ are third-party content and are excluded.
"""

from __future__ import annotations

import re
import sys

PATTERN = re.compile(r"/home/[a-z0-9._-]+|/Users/[a-z0-9._-]+")


def main(paths: list[str]) -> int:
    bad = False
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for n, line in enumerate(fh, 1):
                    if PATTERN.search(line):
                        print(f"{path}:{n}: personal path found: {line.strip()[:120]}")
                        bad = True
        except OSError:
            continue
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
