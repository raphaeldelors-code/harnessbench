# HarnessBench ⚡

**One local model. Many coding harnesses. Fully reproducible.**

HarnessBench measures how much *the agent harness* matters when the model is fixed:
the same SWE-bench Verified tasks are run through many coding agents (Claude Code,
OpenCode, Codex, Qwen Code, Kimi Code, Grok, OpenClaw, Hermes Agent, Pi, mini-swe-agent,
deepseek-harness), all pointed at **one local model served by llama-swap** on a single
RTX 3090. Every run records exact component versions so it can be reproduced on any machine.

📊 **Dashboard:** https://raphaeldelors-code.github.io/harnessbench/
(the `site/` folder — animated charts, filters, McNemar significance, per-instance grids)

## Layout

```
site/            visualization layer (static, zero framework, vendored Chart.js)
  build.py       aggregates runs/*/data → site/public/data/site.json
  public/        dashboard assets (index.html, app.js, style.css, vendor/, data/)
runs/<id>/       one folder per experiment
  data/results.json     per-harness aggregates + per-instance R/E grid + McNemar pairs
  data/windows_*.jsonl  per-instance wall times / exit codes
  data/preds_*.json.gz  generated patches (debug aid)
  data/versions.json    exact component versions + config of that run ← reproducibility
data/instances/  task datasets (SWE-bench Verified subsets)
hb.py            the runner: each harness runs isolated inside the official sweb.eval container
scripts/         consolidation, McNemar matrices, leaderboard aggregation
setup_hb.sh      portable harness runtime (node 22 + npm builds) → /home/rapha/hb
setup_hb_configs.sh  per-harness homes (API bases, model pins)
.github/         Pages deployment workflow
```

## Reproduce a run

Requirements: Linux + NVIDIA GPU (≥24 GB), Docker, llama-swap serving your model on `:8080`.

```bash
python3 hb.py prep                        # clone instance repos, fetch base commits
python3 hb.py smoke --harness opencode    # toy fix inside one eval container
python3 hb.py run   --harness opencode    # sweep (+telemetry from llama-swap activity API)
python3 hb.py eval  --harness opencode    # official F2P/P2P grading in a fresh container
python3 site/build.py                     # refresh dashboard data
```

## Methodology (short)

- **Model fixed; the harness is the only variable.** Identical task text, repo snapshot,
  base commit, 2700 s per-instance cap. Each harness keeps its own internal system
  prompt and tools — that is exactly what is measured.
- **Clean isolation:** every harness runs headless inside the official `sweb.eval.*`
  image with the portable runtime (`/home/rapha/hb`) mounted read-only; harness state
  lives in per-harness homes (`hb/homes/<harness>`). No shared state between harnesses.
- **Grading outside the harness:** the `git diff` left in the worktree is graded by the
  official swebench grader in a *fresh* container (FAIL_TO_PASS / PASS_TO_PASS).
  A harness cannot fake success inside its own session.
- **Cost measured outside the harness:** llama-swap activity metrics (calls, input/output/
  cache tokens, prefill/decode TPS); wall time by the runner; contamination checks flag
  foreign model traffic inside a phase.
- **Significance:** exact two-sided McNemar on identical instances between harness pairs.

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) — a new harness is ~20 lines in `hb.py`;
a new model is one llama-swap entry.

## Harness invocation parity

| harness | version | headless invocation |
|---|---|---|
| claude-code | 2.1.326 | `claude --print --output-format=stream-json --permission-mode=bypassPermissions` (ANTHROPIC_BASE_URL→llama-swap `/v1/messages`) |
| opencode | 2.3.0 | `opencode run --model llamaswap/strata_iq3s --format json --auto -- "$TASK"` |
| pi | 1.5.2 | `pi --print --mode json --provider rig --model rig/strata_iq3s --thinking off -- "$TASK"` |
| deepseek-harness | 0.2.2-rc.3 | `dsh headless --json --permission-mode danger-full-access -- "$TASK"` |
| mini-swe-agent | 2.4.6 | swebench mode, 40 steps, 8192 max_tokens, T=0 |
| codex | 0.170.0 | `codex exec --json "$TASK"` (OPENAI_BASE_URL→llama-swap) |
| qwen-code | 0.28.0 | `qwen --output-format json -p "$TASK"` (OPENAI base→llama-swap) |
| kimi-code | 2.6.3 | `kimi -p "$TASK"` (model pin→llama-swap) |
| grok-build | 1.0.89 | `grok -p "$TASK" --output-format json` (base→llama-swap) |
| openclaw | 2026.6.35 | `openclaw run "$TASK" --json` (apiKey model→llama-swap) |
| hermes-agent | 0.23.1 | hermes one-shot in its own Docker image (base→llama-swap) |

## Pitfalls learned while building

- `opencode-ai` on npm and `latest`/`beta` on GHCR are **stale v1**; the real v2
  image tag must be pinned explicitly; the v2 binary is musl-linked → ship Alpine's
  loader + libs beside it and exec through `ld-musl-x86_64.so.1`.
- `claude` npm install needs its install scripts (native binary); never `--ignore-scripts`.
- `@deepseek-ai/dsh` only publishes prereleases (pin `@0.2.2-rc.3` explicitly).
- llama-swap answers Anthropic `/v1/messages` **and** OpenAI `/v1/responses` natively —
  no bridge needed for claude-code or codex.
- Containers mount the portable runtime read-only at `/opt/hb`; any writable harness
  state must live in the bind-mounted per-harness home.
- Standard sweb.eval images lack `bash` in argv position 0 — entrypoint-aware argv
  in `hb.py` (`DOCKER_ARGV`) handles custom vs standard images.
- llama-swap unloads models ~idle-TTL; a harness phase with zero LLM traffic for long
  stretches is suspicious (contamination/idle detection).
