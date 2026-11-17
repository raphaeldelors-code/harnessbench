# harnessbench

Which coding harness is most efficient **for the same local model**?

`harnessbench` fixes the model, the tasks, and the grading, and varies only the
agent harness around them. It is a local, reproducible take on the
[harness-leaderboard](https://huggingface.co/spaces/joelniklaus/harness-leaderboard)
methodology ("ethos" section):

* **one model** — served by llama-swap on the rig (`strata_iq3s` today);
* **N harnesses** as the only variable — currently `claude-code`, `pi`,
  `deepseek-harness` (dsh), `mini-swe-agent`, `opencode`;
* **identical task text** for every harness (a shared task template); each
  harness keeps its own internal system prompt and tools — that is exactly what
  is being measured;
* **the same environment** — every harness runs headless *inside the official
  SWE-bench `sweb.eval` container* for that instance, via a portable runtime
  (`/opt/hb`: node 22, claude/pi/dsh npm builds, musl-wrapped opencode binary)
  mounted read-only. The harness can run the project's real tests in its turn
  loop, like a human would;
* **grading outside the harness** — the `git diff` the harness leaves in the
  working tree is extracted after the run and graded by the official swebench
  grader in a *fresh* container (FAIL_TO_PASS / PASS_TO_PASS), so a harness
  cannot fake success inside its own session;
* **cost measured outside the harness** — the llama-swap activity metrics API
  (calls, input/output/cache tokens, prefill/decode tps) is polled during each
  window; wall time and timeouts are recorded by the runner;
* **contamination checks** — non-bench-model traffic or absurd request
  durations inside a phase mark it contaminated (run again).

## Layout

```
hb.py                runner (prep / smoke / run / eval / report)
setup_hb.sh          portable runtime: node22 + npm harnesses -> /home/rapha/hb
setup_hb_configs.sh  per-harness homes (pi models.json, dsh cordis.patch, ...)
repos/             bare-ish clones of the instance repos (blob:none)
work/<instance>/     per-instance git worktree (mounted as /testbed) + out/
out/<harness>/       preds.json, windows.jsonl, activity.jsonl
```

## Harness invocation parity (leaderboard commands)

| harness  | version     | headless invocation |
|----------|-------------|---------------------|
| claude-code | 2.1.326  | `printf %s "$TASK" \| claude --verbose --output-format=stream-json --permission-mode=bypassPermissions --print` (ANTHROPIC_BASE_URL→llama-swap `/v1/messages`, native) |
| pi       | 1.5.2       | `pi --print --mode json --provider rig --model rig/strata_iq3s --thinking off -- "$TASK"` |
| deepseek-harness | 0.2.2-rc.3 | `dsh headless --json --permission-mode danger-full-access -- "$TASK"` |
| opencode | 2.3.0     | `opencode run --model llamaswap/strata_iq3s --format json --auto -- "$TASK"` |
| mini-swe-agent | 2.4.6 | swebench mode (`minisweagent.run.benchmarks.swebench`), 40 steps, 8192 max_tokens, T=0 |

## Tasks

SWE-bench Verified (10-instance set shared with the agentswe runs: requests×5,
flask, pytest×2, pylint×2), identical problem statements via one template,
base commit checked out in a worktree.

## Metrics per harness

* resolved / 10 (official grader) + partial credit (F2P pass-rate)
* empty-patch rate, timeouts
* wall time per instance, GPU-seconds, resolved per GPU-hour
* API calls, input/output/cache tokens, prefill/decode tps (llama-swap)

## Pitfalls learned while building

* `opencode-ai` on npm and `latest`/`beta` on GHCR are **stale v1**; the v2
  npm name is unpublished — extract the binary from the container image.
* The v2 binary is musl-linked: ship Alpine's `ld-musl-x86_64.so.1`,
  `libstdc++.so.6.0.34`, `libgcc_s.so.1`, `libz.so.1.3.2` beside it and exec
  through the loader (`/opt/hb/npm/bin/opencode` wrapper does this).
* `claude` npm install needs its install scripts (native binary); do **not**
  use `--ignore-scripts` for it. `@deepseek-ai/dsh` only publishes prereleases
  (`@0.2.2-rc.3` explicitly).
* llama-swap answers Anthropic `/v1/messages` natively — no bridge needed for
  claude-code.
* Containers mount the portable runtime read-only at `/opt/hb`; harness state
  (login/onboarding/config) lives in bind-mounted per-harness homes
  (`/home/rapha/hb/homes/<harness>` → `/root`).

## Runbook

```bash
python3 hb.py prep                       # clone repos, fetch base commits
python3 hb.py smoke  --harness pi        # toy fix inside an eval container
python3 hb.py run    --harness pi        # 10-instance sweep (+telemetry)
python3 hb.py eval   --harness pi        # official grading of out/pi/preds.json
python3 hb.py report                     # leaderboard-style table
```
