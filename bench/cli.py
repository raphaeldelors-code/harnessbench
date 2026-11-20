"""hb — harnessbench CLI."""

from __future__ import annotations

import argparse
import sys

from bench import config as C
from bench import grading, runner


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hb", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prep", help="clone instance repos, fetch base commits")
    p = sub.add_parser("smoke", help="toy-repo fix test inside an eval container")
    p.add_argument("--harness", required=True)
    p = sub.add_parser("run", help="one harness over the instance set")
    p.add_argument("--harness", required=True)
    p.add_argument("--inst", action="append")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--dataset")
    p = sub.add_parser("eval", help="official grading of out/<h>/preds.json")
    p.add_argument("--harness", required=True)
    p.add_argument("--dataset")
    p = sub.add_parser("run-mini", help="legacy mini-swe-agent lane")
    p.add_argument("--inst", action="append")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--dataset")
    sub.add_parser("report", help="leaderboard-style table")
    a = ap.parse_args(argv)

    if getattr(a, "dataset", None):
        C.DATASET = a.dataset
    if a.cmd == "run":
        runner.RESUME["on"] = a.resume
    actions = {
        "prep": runner.cmd_prep,
        "smoke": runner.cmd_smoke,
        "run": runner.cmd_run,
        "eval": grading.cmd_eval,
        "report": grading.cmd_report,
        "run-mini": grading.cmd_run_mini,
    }
    actions[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
