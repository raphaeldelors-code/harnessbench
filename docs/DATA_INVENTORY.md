# Data inventory & gap analysis

Generated 2026-11-20 from the actual files in `runs/*/` (3 runs). "On site" = currently
rendered in a chart, table or panel at https://raphaeldelors-code.github.io/harnessbench/.

## Files captured per run (`runs/<id>/data/`)

| File | What it holds |
|---|---|
| `run.json` (parent dir) | manifest: `schema_version`, `id`, `date`, `model`, `hardware` (rig id), `harnesses[]`, `dataset{name,instances,source}`, `workers`, `seed`, `notes` |
| `results.json` | roll-up: `instances[]`, per harness `{resolved, resolved_ids, empty, calls, wall_s, input_tokens, output_tokens, cache_tokens, resolved_per_gpu_h, per_instance{inst → R/E/T/U}}`, `mcnemar{"A|B":{a_only,b_only}}` |
| `windows_<h>.jsonl` | one record per instance attempt: `harness`, `instance_id`, `t0`, `t1` (unix epochs) |
| `preds_<h>.json.gz` | SWE-bench-style prediction records: `instance_id`, `model_name`, `model_name_or_path`, `model_patch` (full unified diff) |
| `versions.json` | `model`, `model_args`, `engine`, `strata_terminal`, `llama_swap`, `gpu`, `dataset`, `harness_versions{…}`, `runner_workers`, `per_instance_timeout_s` |
| `eval_<h>.json` | eval-harness detail (only present in the 2026-11-17 run; not produced by the current runner) |

## Field-level usage matrix

| Field | Source | On site today | Where |
|---|---|---|---|
| resolved (+ % of cohort) | results.json | ✅ | all resolved bars, cohort table, instance grid, hero, cross-run board |
| per_instance R/E/T/U | results.json | ✅ | instance grid (color-coded, tooltip) |
| wall_s (total) | results.json | ✅ | Wall time chart, wall/GPU-h, cross-run wall |
| wall_s (per instance) | windows t1−t0 | ✅ | per-instance wall chart (p10/median/p90) |
| input_tokens | results.json | ✅ | Effort chart, cross-run tokens |
| cache_tokens | results.json | ✅ | Cache use chart |
| output_tokens | results.json | ✅ (new) | Decode speed chart (output/wall) |
| resolved_per_gpu_h | results.json | ✅ | Throughput chart, cross-run throughput |
| mcnemar pairs | results.json (recomputed at build) | ✅ | pairwise significance matrix |
| model, model_args | versions.json | ✅ | run versions panel, hero |
| harness_versions | versions.json | ✅ | run versions panel |
| gpu / engine / strata / llama-swap / dataset / workers / timeout | versions.json | ✅ | run versions panel, rig tab |
| **hardware / rig id** | run.json + data/hardware.json | ✅ (new) | hero line, rig tab, schema cross-check in `validate_data.py` |
| t0, t1 raw timestamps | windows jsonl | ⚠️ derived only | used to derive wall; raw timeline unused |
| **empty** (empty-patch count) | results.json | ❌ | — |
| **calls** (LLM requests per harness) | results.json | ❌ | — |
| seed, workers | run.json | ❌ | — |
| resolved_ids | results.json | ❌ (redundant with per_instance) | — |
| model_patch (full diff text) | preds json.gz | ❌ (kept for re-evaluation) | — |
| eval_<h>.json detail | 2026-11-17 run only | ❌ | — |

## Gap analysis — unused fields worth leveraging

1. **`calls` → API efficiency.** `calls / resolved` gives "LLM requests per solved instance"
   (codex ≈ 63 vs hermes-agent ≈ 145 on run 3 — a real cost-per-win signal). Candidate chart:
   calls-per-resolved bar, or scatter resolved% vs calls.
2. **`empty` → failure taxonomy.** resolved / empty-patch / timeout / ungraded split is already
   in `per_instance` (R/E/T/U) but only shown as grid cells. A stacked failure-mix bar per
   harness would answer "why did it lose?" not just "did it lose?".
3. **`t0/t1` → concurrency & scheduling views.** Raw epochs allow a Gantt/timeline of one run
   (instances overlapping at `workers=2`) and a throughput-over-time curve. Useful to show the
   queue isn't the bottleneck; also exposes pathological stalls (e.g. the 61-min mini window).
4. **`model_patch` → patch-size statistics.** Diff line counts per harness (added/removed), and
   patch size vs resolution (do verbose agents produce worse patches?). Patches are also the
   reproducibility contract: any third party can re-grade them with the official SWE-bench
   harness without re-running the agents.
5. **`seed` / `workers` → comparability badge.** Same rig + same seed + same workers =
   apples-to-apples; display in the run versions panel.
6. **`output_tokens` (raw)** now feeds Decode speed; an input/output ratio would expose
   context-verbosity differences between harnesses.

Fields **not captured today** that would need new probes if wanted: per-request TTFT and
GPU-side stats (VRAM used, queue depth, decode tok/s at server level — llama-swap exposes
these live but they are not snapshotted per run), and per-instance token counts (only totals
are stored today; per-instance would need the harness-side counters we don't all have).

## Rig versioning (implemented 2026-11-20)

- `data/hardware.json` is the rig record with a stable `id` (`bench-rig-01`) — CPU, RAM
  (size/channels/speed), GPU (model/VRAM/PCIe gen/lanes), board, OS, probe date.
- Every `run.json` manifest carries `"hardware": "<rig id>"`; `schemas/run_manifest.schema.json`
  enforces the id pattern, and `tools/validate_data.py` fails CI if a manifest references a rig
  id that doesn't exist in `data/hardware.json` or if `data/versions.json` is missing.
- For a hardware change: add/replace a rig record (e.g. `data/rigs/bench-rig-02.json`), new
  runs reference the new id — old runs keep pointing at `bench-rig-01`, so cross-run charts
  always know what machine produced each number.
