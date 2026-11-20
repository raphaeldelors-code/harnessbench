"""Harness registry: one entry per coding agent.

Each harness is pinned to a version and gets its env from bench.config, so
pointing every harness at a different backend is a single env change
(HB_BACKEND_URL / HB_CONTAINER_BACKEND_URL) — no source edits.
"""

from __future__ import annotations

from bench import config as C

_V1 = C.CONTAINER_BACKEND_URL + "/v1"

HARNESSES: dict[str, dict] = {
    "claude-code": {
        "version": "2.1.326",
        "homes": True,
        "cmd": lambda task: (
            'printf %s "$HB_TASK" | claude --verbose --output-format=stream-json '
            "--permission-mode=bypassPermissions --print"
        ),
        "env": {
            "ANTHROPIC_BASE_URL": C.CONTAINER_BACKEND_URL,
            "ANTHROPIC_API_KEY": "***",
            "ANTHROPIC_AUTH_TOKEN": "***",
            "IS_SANDBOX": "1",
            "ANTHROPIC_MODEL": C.MODEL,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
        },
    },
    "pi": {
        "version": "1.5.2",
        "homes": True,
        "cmd": lambda task: (
            "pi --print --mode json --provider rig --model rig/" + C.MODEL + ' --thinking off -- "$HB_TASK"'
        ),
        "env": {},
        "home_config": "pi",  # provider config pre-seeded under the harness home
    },
    "deepseek-harness": {
        "version": "0.2.2-rc.3",
        "homes": True,
        "cmd": lambda task: 'dsh headless --json --permission-mode danger-full-access -- "$HB_TASK"',
        "env": {
            "OPENAI_API_KEY": "***",
            "OPENAI_BASE_URL": _V1,
            "DEEPSEEK_API_KEY": "***",
        },
    },
    "opencode": {
        "version": "2.3.0",
        "homes": True,
        "cmd": lambda task: f'opencode run --model llamaswap/{C.MODEL} --format json --auto -- "$HB_TASK"',
        "env": {},
        "home_config": "opencode",
    },
    "codex": {
        "version": "0.170.0",
        "homes": True,
        "cmd": lambda task: (
            'printf %s "$HB_TASK" | codex exec --json --dangerously-bypass-approvals-and-sandbox'
        ),
        "env": {"OPENAI_API_KEY": "***"},
        "home_config": "codex",
    },
    "qwen-code": {
        "version": "0.28.0",
        "homes": True,
        "cmd": lambda task: 'qwen -y -p "$HB_TASK"',
        "env": {
            "OPENAI_API_KEY": "***",
            "OPENAI_BASE_URL": _V1,
            "OPENAI_MODEL": C.MODEL,
            "QWEN_CODE_SUPPRESS_YOLO_WARNING": "1",
        },
    },
    "kimi-code": {
        "version": "2.6.3",
        "homes": True,
        "cmd": lambda task: 'kimi -p "$HB_TASK" --output-format stream-json',
        "env": {},
        "home_config": "kimi-code",
    },
    "grok": {
        "version": "1.0.89",
        "homes": True,
        "cmd": lambda task: 'grok -p "$HB_TASK" --always-approve --output-format json --disable-web-search',
        "env": {},
        "home_config": "grok",
    },
    "openclaw": {
        "version": "2026.6.35",
        "homes": True,
        "cmd": lambda task: (
            'openclaw agent --local --json --timeout 2100 --session-id "hb-$(date +%s%N)" -m "$HB_TASK"'
        ),
        "env": {},
        "home_config": "openclaw",
    },
    "hermes-agent": {
        "version": "0.23.1",
        "homes": True,
        "image": "nousresearch/hermes-agent:latest",
        "wd": "/testbed",
        "cmd": lambda task: '/opt/hermes/bin/hermes -z "$HB_TASK" --yolo',
        "env": {"HERMES_HOME": "/root", "HERMES_WRITE_SAFE_ROOT": "/testbed"},
    },
}

# mini-swe-agent runs on the host through its own swebench integration
MINI_PKG = "minisweagent.run.benchmarks.swebench"
