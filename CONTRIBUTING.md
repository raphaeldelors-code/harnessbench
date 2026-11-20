# Contributing

Thanks for making the harness arena bigger 🙌

## Add a harness (~20 lines)

1. **Registry entry in `hb.py`** — add to `HARNESSES`: binary path under the portable
   runtime (`/opt/hb`), the headless argv template, and env vars that point its API
   base at llama-swap. Copy an existing entry (e.g. `codex`) — the OpenAI-compatible
   ones are the easiest template.
2. **Install it into the portable runtime** (`setup_hb.sh` pattern: npm/binary install →
   `/home/rapha/hb`) and create its home dir under `hb/homes/<name>` with pinned config
   (`setup_hb_configs.sh`). Pin the version explicitly.
3. **Smoke:** `python3 hb.py smoke --harness <name>` must exit 0 with a non-empty patch.
4. **Run + grade:** `python3 hb.py run --harness <name>` then `eval`. The runner writes
   `versions.json` automatically — commit it with the results.
5. `python3 site/build.py` and push — the dashboard picks the new harness up.

## Add a model

1. Add/enable the model in llama-swap (`/opt/llama-swap-config/config.yaml`).
2. Pin every harness's home config to the new model id, or pass `--model <llamaswap-id>`.
3. Name the run `runs/<date>-<model>-sbNN-<n>way/` and run `scripts/consolidate_new.py`
   + `python3 site/build.py`.

## Reproducibility contract (required for every merged run)

- `runs/<id>/data/versions.json` must list: model + model_args, strata/llama-swap/engine
  versions, per-harness versions, dataset, runner workers/timeout.
- One model per run; harnesses are the only variable.
- Grading only via the official grader (`hb.py eval`), never harness self-report.
- Keep `results.json` schema stable (harnesses/instances/mcnemar) — the site reads it.

## Style

- Runner code: stdlib only. Site: no framework, no CDN (vendored assets).
- Data files under 2 MB uncompressed, else gzip before commit.
