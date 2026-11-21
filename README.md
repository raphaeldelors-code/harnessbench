# HarnessBench ⚡

**[📊 Live dashboard →](https://raphaeldelors-code.github.io/harnessbench/)** — opens on the global aggregation: best result per harness across every run.

**One local model. Many coding harnesses. Fully reproducible.**

HarnessBench measures how much *the agent harness* matters when the model is fixed:
the same SWE-bench tasks are run through 11 coding agents (Claude Code, OpenCode,
Codex, Qwen Code, Kimi Code, Grok, OpenClaw, Hermes Agent, Pi, mini-swe-agent,
deepseek-harness), all pointed at **one local model served by llama-swap** on a
single RTX 3090. Patches are graded inside official SWE-bench eval containers.
Every run stores a manifest + exact component versions, so any number on the
dashboard can be re-produced on any machine.

The rig also runs a second lane: **model bench** rounds — engine/quantization tuning of
that same served model (A/B legs, per-prompt-size prefill/decode speed, a hand-written
KEEP/UNDO verdict). Same repo, same rig record, separate lane on the dashboard, and the
two lanes' numbers are never compared with each other.

## Quickstart

```bash
make install            # pip install -e . + pre-commit hooks
make lint               # ruff + secrets + bandit + personal-path guard (same as CI)
make build serve        # rebuild site.json and preview the dashboard
```

### Backend — dependency injection

The runner never assumes where the model endpoint lives:

| Option | How |
|---|---|
| **A — containerised llama-swap** | `docker compose --env-file .env -f docker/docker-compose.yml up -d llamaswap` (pinned llama-swap on a CUDA llama.cpp base; put a GGUF in `HB_MODEL_DIR`) |
| **B — existing endpoint** | `export HB_BACKEND_URL=http://host:8080 HB_MODEL=your-model` — no container needed |

`HB_CONTAINER_BACKEND_URL` is the URL the *eval containers* use to reach the
backend (usually `http://host.docker.internal:8080`). Copy `.env.example` → `.env`.

Because `-f docker/docker-compose.yml` makes `docker/` the Compose project dir,
Compose reads `docker/.env` (not the repo-root `.env`) and resolves relative
paths there — hence the explicit `--env-file .env`, and absolute `HB_MODEL_DIR`
/ `HB_RUNTIME_DIR` values. `HB_RUNTIME_DIR` (the portable runtime built by
`scripts/setup_hb.sh`) is required by the `bench` service and must be an
absolute host path: it is forwarded verbatim to the Docker daemon that launches
the eval containers.

### Run a bench

```bash
hb prep                       # clone instance repos, fetch base commits
hb smoke --harness opencode   # toy-repo fix test inside an eval container
hb run --harness opencode     # full cohort (--workers N, default 2)
hb eval --harness opencode    # official SWE-bench grading (per harness)
hb report                     # markdown table from out/, eval reports and windows
```

`--harness` names a key in the `HARNESSES` registry (`bench/harnesses.py`) and is
required by `smoke`, `run` and `eval`. The legacy mini-swe-agent lane is its own
command, `hb run-mini` (it has no `--harness`).

All backend/model/home paths flow through `bench/config.py` env vars — no
machine-specific paths anywhere in the repo (enforced by a pre-commit hook).

## Layout

```
bench/           the runner package
  config.py      env-driven dependency injection (HB_* vars) ← the only config seam
  harnesses.py   harness registry (pinned versions, per-harness env)
  runner.py      per-instance eval-container execution + telemetry
  grading.py     official SWE-bench grading + mini-swe-agent lane
  cli.py         `hb` entry point (prep | smoke | run | eval | run-mini | report)
docker/          Dockerfile.llamaswap + docker-compose.yml (Option A backend)
runs/<id>/       one folder per experiment — harness lane
  run.json       manifest (schema: schemas/run_manifest.schema.json)
  data/results.json     per-harness aggregates + per-instance grid + McNemar pairs
  data/windows_*.jsonl  per-instance wall-time windows
  data/preds_*.json.gz  generated patches (debug aid)
  data/versions.json    exact component versions + config ← reproducibility
runs/m-<id>/     one folder per model bench round — model lane (kind:"model")
  run.json       manifest (schema: schemas/modelrun.schema.json) — title, model{slug,quant,
                 family}, engine, verdict, provenance notes
  data/model_results.json   rows: {leg, tag, in_tok, out_tok, pp, tps, draft, draft_acc}
site/            visualization layer (static, zero framework, vendored Chart.js)
  build.py       aggregates runs/*/ + data/hardware.json → site/public/data/site.json
  public/        dashboard (two lanes — Harness: Overview / Runs / Rig / Calibration /
                 Methodology · Models: overview + one tab per round)
schemas/         JSON Schema for every published data file (validated in CI)
docs/            METHODOLOGY.md (both lanes, verdicts, noise floor) · DATA_INVENTORY.md
tools/           validate_data.py, smoke.py (headless browser, desktop+phone), hooks
scripts/         portable runtime setup (node 22 + pinned harness CLIs)
data/hardware.json  the bench rig spec (CPU, RAM, GPU, PCIe gen/lanes, board)
```

## Methodology (short)

- **Model fixed; the harness is the only variable.** Identical task text, repo
  snapshot, base commit, 2700 s per-instance cap. Each harness keeps its own
  internal system prompt and tools — that is exactly what is measured.
- **Clean isolation:** every harness runs headless inside the official
  `sweb.eval.*` image with the portable runtime mounted read-only at `/opt/hb`;
  harness state lives in per-harness homes. No shared state between harnesses.
- **Grading outside the harness:** the `git diff` left in the worktree is graded
  by the official swebench grader in a *fresh* container (FAIL_TO_PASS /
  PASS_TO_PASS). A harness cannot fake success inside its own session.
- **Cost measured outside the harness:** llama-swap activity metrics (calls,
  input/output/cache tokens); wall time by the runner; idle/contamination
  detection flags phases with no LLM traffic.
- **Significance:** exact two-sided McNemar on identical instances between
  harness pairs (heat map per run on the dashboard).
- **Model lane, separately:** a round compares engine legs inside one prompt-size cell on
  prefill/decode speed, with a hand-written KEEP/REVERT/UNDO verdict and warm-up rows kept out of
  every median. It measures speed only — no task quality, and its tok/s are not comparable to the
  harness lane's resolved %.

The long version — including the noise-floor rule (median over ≥3 reps per cell) and an explicit
list of what neither lane claims — is [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Reproducibility & quality gates

- **pre-commit**: trailing whitespace, JSON/YAML validity, large-file guard,
  private keys, `ruff check` + `ruff format`, `detect-secrets`, `bandit`, and a
  `no-personal-paths` guard (no `/home/x` or `/Users/x` in tracked files).
- **CI** (`.github/workflows/ci.yml`): lint job (same hooks), then schema-validate
  all data, rebuild the site, and run a headless-browser smoke test at 1280px and
  390px — every canvas must contain pixels, zero console errors — before Pages deploy.
- **Hardware**: [data/hardware.json](data/hardware.json) pins the rig
  (RTX 3090 24 GiB @ PCIe Gen3 x16 — the 5600G APU has no Gen4 lanes,
  GPU-side Gen4 capability never negotiates; Ryzen 5 5600G, 64 GiB DDR4-3600,
  Samsung 990 EVO Plus 2 TB NVMe @ Gen3 x4 holding models and eval images).

## Harness invocation parity

Copied from the `HARNESSES` registry in `bench/harnesses.py` — argv verbatim, plus
where each harness's endpoint comes from. Published runs cover a subset of these;
the dashboard's cohort map says who was measured on which run.

| harness | version | headless invocation | endpoint from |
|---|---|---|---|
| claude-code | 2.1.326 | `printf %s "$HB_TASK" \| claude --verbose --output-format=stream-json --permission-mode=bypassPermissions --print` | `ANTHROPIC_BASE_URL` env |
| pi | 1.5.2 | `pi --print --mode json --provider rig --model rig/$HB_MODEL --thinking off -- "$HB_TASK"` | seeded `homes/pi` provider config |
| deepseek-harness | 0.2.2-rc.3 | `dsh headless --json --permission-mode danger-full-access -- "$HB_TASK"` | `OPENAI_BASE_URL` env (`…/v1`) |
| opencode | 2.3.0 | `opencode run --model llamaswap/$HB_MODEL --format json --auto -- "$HB_TASK"` | seeded `homes/opencode` provider config |
| codex | 0.170.0 | `printf %s "$HB_TASK" \| codex exec --json --dangerously-bypass-approvals-and-sandbox` | own config under `homes/codex` (not seeded by `scripts/setup_hb_configs.sh`) |
| qwen-code | 0.28.0 | `qwen -y -p "$HB_TASK"` | `OPENAI_BASE_URL` (`…/v1`) + `OPENAI_MODEL` env |
| kimi-code | 2.6.3 | `kimi -p "$HB_TASK" --output-format stream-json` | own config under `homes/kimi-code` (not seeded by `scripts/setup_hb_configs.sh`) |
| grok | 1.0.89 | `grok -p "$HB_TASK" --always-approve --output-format json --disable-web-search` | own config under `homes/grok` (not seeded by `scripts/setup_hb_configs.sh`) |
| openclaw | 2026.6.35 | `openclaw agent --local --json --timeout 2100 --session-id "hb-$(date +%s%N)" -m "$HB_TASK"` | own config under `homes/openclaw` (not seeded by `scripts/setup_hb_configs.sh`) |
| hermes-agent | 0.23.1 | `/opt/hermes/bin/hermes -z "$HB_TASK" --yolo` in its own image (`nousresearch/hermes-agent:latest`) | `HERMES_*` env + its image config |
| mini-swe-agent | unpinned | legacy **host** lane (`hb run-mini`) driving `minisweagent.run.benchmarks.swebench` with its own `swebench.yaml` / `bench_local.yaml` in `$HB_MINI_DIR`; not an `HARNESSES` key, so not selectable with `--harness` | its own config files |

## Pitfalls learned while building

- `opencode-ai` on npm and `latest`/`beta` on GHCR are **stale v1**; the real v2
  image tag must be pinned explicitly; the v2 binary is musl-linked → ship
  Alpine's loader + libs beside it and exec through `ld-musl-x86_64.so.1`.
- `claude` npm install needs its install scripts (native binary); never `--ignore-scripts`.
- `@deepseek-ai/dsh` only publishes prereleases (pin `@0.2.2-rc.3` explicitly).
- llama-swap answers Anthropic `/v1/messages` **and** OpenAI `/v1/responses`
  natively — no bridge needed for claude-code or codex.
- Containers mount the portable runtime read-only at `/opt/hb`; any writable
  harness state must live in the bind-mounted per-harness home.
- Standard sweb.eval images lack `bash` in argv position 0 — entrypoint-aware
  argv in `bench/runner.py` handles custom vs standard images.
- llama-swap unloads models ~idle-TTL; a harness phase with zero LLM traffic for
  long stretches is suspicious (contamination/idle detection).

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) — a new harness is one registry entry in
`bench/harnesses.py`; a new model is one llama-swap entry; a new model bench round is one
`runs/m-<id>/` dir with a manifest and its captured rows (no site code involved).
