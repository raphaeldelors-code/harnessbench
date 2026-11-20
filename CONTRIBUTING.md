# Contributing

Thanks for making the harness arena bigger 🙌

## Add a harness (~20 lines)

1. **Registry entry in `bench/harnesses.py`** — binary path under the portable
   runtime (`/opt/hb`), the headless argv template, and env vars that point its
   API base at `$HB_BACKEND_URL`. Copy an existing entry (e.g. `codex`) — the
   OpenAI-compatible ones are the easiest template. Pin the version explicitly.
2. **Install it into the portable runtime** — extend `scripts/setup_hb.sh`
   (npm/binary install into `$HB_RUNTIME_DIR`) and seed a home directory under
   `homes/<name>` in `scripts/setup_hb_configs.sh`.
3. **Smoke:** `hb smoke --harness <name>` must exit 0 with a non-empty patch.
4. **Run + grade:** `hb run --harness <name>` then `hb eval`. The runner writes
   `versions.json` automatically — commit it with the results, plus a
   `runs/<id>/run.json` manifest (schema in `schemas/`).
5. `make build && make validate && make smoke` and push — the dashboard picks
   the new harness up.

## Add a model

1. Serve it via the backend DI seam: add it to your llama-swap config
   (`docker/config/llama-swap.yaml` for Option A) or point `HB_BACKEND_URL` /
   `HB_MODEL` at any endpoint that speaks OpenAI/Anthropic-compatible APIs.
2. Pin every harness home config to the new model id (`scripts/setup_hb_configs.sh`).
3. Name the run `runs/<date>-<model>-sbNN-<n>way/`, write its `run.json`
   manifest, `make build`.

## Reproducibility contract (required for every merged run)

- `runs/<id>/run.json` — manifest validated against `schemas/run_manifest.schema.json`.
- `runs/<id>/data/versions.json` — model + model_args, inference stack versions,
  per-harness versions, dataset, runner workers/timeout.
- One model per run; harnesses are the only variable.
- Grading only via the official grader (`hb eval`), never harness self-report.
- Keep `results.json` schema stable (harnesses/instances/mcnemar) — the site reads it.

## Style & gates

- Runner code: stdlib only; `ruff` clean (check + format, enforced pre-commit/CI).
- Site: no framework, no CDN (vendored assets); every chart must render at 390px
  (`make smoke` fails otherwise).
- No personal absolute paths (`/home/x`, `/Users/x`) in tracked files — a
  pre-commit hook enforces this; use the `HB_*` env vars.
- Data files under 2 MB uncompressed, else gzip before commit.
