"""All machine-specific knobs live here, sourced from the environment.

Tracked source never contains personal paths. Configure via env vars
(see .env.example) — this is the dependency-injection seam for the backend:

  HB_BACKEND_URL          OpenAI/Anthropic-compatible base URL of the LLM backend.
                          Point it at an existing llama-swap (http://host:8080) or at
                          the llama-swap container started by docker compose.
  HB_CONTAINER_BACKEND_URL  same URL as seen from inside harness eval containers
                          (defaults to HB_BACKEND_URL; use a LAN IP or
                          host.docker.internal when the backend runs elsewhere).
  HB_MODEL                model id served by the backend (default strata_iq3s).
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


HOME = _env_path("HB_HOME", REPO_ROOT)
WORK = HOME / "work"
OUT = HOME / "out"
REPOS = HOME / "repos"

# portable node runtime mounted read-only into every harness container
RUNTIME_DIR = _env_path("HB_RUNTIME_DIR", Path.home() / ".harnessbench" / "runtime")
CTR_RUNTIME = "/opt/hb"
NODE_PATH = f"{CTR_RUNTIME}/node/bin:{CTR_RUNTIME}/npm/bin"

# backend (dependency injection point)
BACKEND_URL = os.environ.get("HB_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/")
CONTAINER_BACKEND_URL = os.environ.get("HB_CONTAINER_BACKEND_URL", BACKEND_URL)
MODEL = os.environ.get("HB_MODEL", "strata_iq3s")

DATASET = str(_env_path("HB_DATASET", REPO_ROOT / "data" / "instances" / "sb40_new.json"))
RUN_TIMEOUT = int(os.environ.get("HB_TIMEOUT", "2700"))

# python interpreter that has the swebench + minisweagent packages installed
EVAL_PYTHON = os.environ.get("HB_EVAL_PYTHON", "python3")
# where official swebench eval JSON reports are written/read
RESULTS_DIR = _env_path("HB_RESULTS_DIR", HOME)

# mini-swe-agent legacy lane: directory containing its config (swebench.yaml etc.)
MINI_DIR = _env_path("HB_MINI_DIR", Path.home() / ".harnessbench" / "mini")
