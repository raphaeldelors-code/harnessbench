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

## Add a model to the harness lane

1. Serve it via the backend DI seam: add it to your llama-swap config
   (`docker/config/llama-swap.yaml` for Option A) or point `HB_BACKEND_URL` /
   `HB_MODEL` at any endpoint that speaks OpenAI/Anthropic-compatible APIs.
2. Pin every harness home config to the new model id (`scripts/setup_hb_configs.sh`).
3. Name the run `runs/<date>-<model>-sbNN-<n>way/`, write its `run.json`
   manifest, `make build`.

## Add a model bench round

A model round is an engine/quantization tuning experiment on one served model — see
[docs/METHODOLOGY.md](docs/METHODOLOGY.md), "Model bench lane". No runner is involved: you
import a capture you already measured.

1. **Run dir + id:** `runs/m-<date>-<slug>/` — the `m-` prefix is the lane marker (`kind` below is
   what actually decides it; the prefix is the fallback and keeps the two lanes unambiguous in
   listings). Ids are `m-YYYY-MM-DD-<slug>`, one dir per round; never overwrite a previous round.
2. **`run.json`** — model-run manifest (`schemas/modelrun.schema.json`): `schema_version`
   `hb-modelrun-v1`, `id`, `kind:"model"`, `date`, `title`, `model{slug,quant,family}`, `engine`,
   `verdict`, `hardware` (rig id, `bench-rig-01`), `notes` (provenance: where the raw capture came
   from and when it was captured).
3. **`data/model_results.json`** (`schemas/model_results.schema.json`) —
   `{"rows":[{leg, tag, in_tok, out_tok, pp, tps, draft, draft_acc}]}`, one record per measurement.
   Copy the capture's own labels: keep `tag` verbatim, derive `leg` mechanically (a `warm*` tag keeps
   leg `warm*`, otherwise the prefix before the first `-`). **Never invent leg names, leg meanings or
   flag settings** — if the capture does not say what a leg changed, the round simply does not know,
   and `notes` should say so.
4. **`verdict`** is yours to write, by hand, from the enum `INFO / KEEP / CONFIRM-KEEP / REVERT /
   UNDO`. The pipeline never computes one; a capture with no decision recorded is `INFO`. It only
   counts as a citable decision if the round clears the noise floor (median over ≥3 reps per cell,
   warm rows excluded) — record what the round actually holds if it doesn't.
5. `make build && make validate && make smoke` — `build.py` folds the round into `model_runs[]` /
   `models[]`, and a new round needs no site code: the tab, banners, charts and tables are derived.

## Reproducibility contract (required for every merged run)

Harness lane:

- `runs/<id>/run.json` — manifest validated against `schemas/run_manifest.schema.json`.
- `runs/<id>/data/versions.json` — model + model_args, inference stack versions,
  per-harness versions, dataset, runner workers/timeout.
- One model per run; harnesses are the only variable.
- Grading only via the official grader (`hb eval`), never harness self-report.
- Keep `results.json` schema stable (harnesses/instances/mcnemar) — the site reads it.

Model lane (no `versions.json` — the manifest carries the pins instead):

- `runs/m-<id>/run.json` with `kind:"model"`, `model{slug,quant,family}`, `engine`, `verdict`.
- `runs/m-<id>/data/model_results.json` with the capture's rows and mechanically-derived legs.
- Provenance in `notes`, and the raw capture stays out of the repo (import it, don't commit it).

## Style & gates

- Runner code: stdlib only; `ruff` clean (check + format, enforced pre-commit/CI).
- Site: no framework, no CDN (vendored assets); every chart must render at 390px
  (`make smoke` fails otherwise).
- No personal absolute paths (`/home/x`, `/Users/x`) in tracked files — a
  pre-commit hook enforces this; use the `HB_*` env vars.
- Data files under 2 MB uncompressed, else gzip before commit.
