# Data inventory & gap analysis

Generated 2026-11-20 from the actual files in `runs/*/` (3 harness runs); usage matrix refreshed
2026-11-21 (failure-mix + calls-per-resolved charts, comparability line, Decode speed removed).
"On site" = currently rendered in a chart, table or panel at
https://raphaeldelors-code.github.io/harnessbench/.

`runs/` holds **two lanes**. A `<date>-…` dir is a *harness* run (coding-harness comparison on a
fixed model); an `m-<date>-…` dir is a *model* run (engine/quantization tuning round of one local
model). The manifest's optional `kind` decides; when it is absent the `m-` id prefix is the
fallback and anything else is `harness`, so every run merged before the lane existed still
aggregates unchanged. They share the directory shape but not the data files — see
[Model-bench layer](#model-bench-layer) below. This file is the *what*; the *why* —
verdict vocabulary, the noise-floor rule, and what neither lane is allowed to claim — is in
[METHODOLOGY.md](METHODOLOGY.md).

## Cleanup sweep (2026-11-21)

Removed, each after grepping every reference in tracked files (docs, Makefile, CI, `bench/`,
`site/`, `tools/`, `scripts/`) and finding none:

| Removed | Why it was dead |
|---|---|
| `charts/leaderboard.png`, `charts/leaderboard_efficiency.png` | PNGs emitted by the retired matplotlib publish pipeline (`scripts/publish_std.py`, `render_charts*.py`, deleted in `cbedfb7`); the site renders the same numbers live from `site.json` and nothing referenced the images |
| `data/instances/new30.txt` | 30-instance id list for the deleted `scripts/sweep50*.sh` sweeps; the live dataset is `data/instances/sb40_new.json`, which `bench/config.py` points at |

Also ignored from now on: `/seed/` (raw engine-bench output handed over for import — never a
tracked input, no tracked file may read from it) and `.cc_run.log`.

Kept on purpose: `runs/*/data/eval_<h>.json` (raw grading provenance for the 2026-11-17 run even
though nothing renders it), `data/instances/sb40_new.json`, `docker/`, `scripts/setup_hb*.sh`
(referenced by README/CONTRIBUTING), `bench/` package, `Makefile`, `.github/workflows/ci.yml`.

## Files captured per harness run (`runs/<id>/data/`)

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
| output_tokens | results.json | ❌ | — (Decode speed chart removed from the site, so output_tokens is no longer rendered) |
| resolved_per_gpu_h | results.json | ✅ | Throughput chart, cross-run throughput |
| mcnemar pairs | results.json (recomputed at build) | ✅ | pairwise significance matrix |
| model, model_args | versions.json | ✅ | run versions panel, hero |
| harness_versions | versions.json | ✅ | run versions panel |
| gpu / engine / strata / llama-swap / dataset / workers / timeout | versions.json | ✅ | run versions panel, rig tab |
| **hardware / rig id** | run.json + data/hardware.json | ✅ (new) | hero line, rig tab, schema cross-check in `validate_data.py` |
| t0, t1 raw timestamps | windows jsonl | ⚠️ derived only | used to derive wall; raw timeline unused |
| **empty** (empty-patch count) | results.json | ✅ | failure-mix stacked bar (E segment — counted from `per_instance` R/E/T/U, not from the roll-up field) |
| **calls** (LLM requests per harness) | results.json | ✅ | calls-per-resolved bar (tooltip also shows the total calls) |
| seed, workers | run.json | ✅ | run versions panel — comparability line (seed · workers · rig id) |
| resolved_ids | results.json | ❌ (redundant with per_instance) | — |
| model_patch (full diff text) | preds json.gz | ❌ (kept for re-evaluation) | — |
| eval_<h>.json detail | 2026-11-17 run only | ❌ | — |

## Model-bench layer

A model run answers a different question: *did this engine/quantization setting make the served
model faster?* One round = several **legs** (baseline vs treatment, labelled exactly as the raw
capture labelled them) measured over a few input-size **cells**. No harnesses, no instances, no
grading — the metric is prefill speed (`pp`, input tok/s) and decode speed (`tps`, output tok/s).

| File | What it holds |
|---|---|
| `run.json` | model-run manifest: `schema_version` (`hb-modelrun-v1`), `id` (`m-<date>-<slug>`), `kind:"model"`, `date`, `title`, `model{slug,quant,family}`, `engine`, `verdict` (INFO / KEEP / CONFIRM-KEEP / REVERT / UNDO), `hardware` (rig id), `notes` (provenance) — schema: `schemas/modelrun.schema.json` |
| `data/model_results.json` | `{"rows":[{leg, tag, in_tok, out_tok, pp, tps, draft, draft_acc}]}` — one record per measurement; `tag` is the raw capture label, `leg` the group it belongs to (schema: `schemas/model_results.schema.json`) |

Leg/tag convention (mechanical, never invented): a row tagged `warm` keeps leg `warm`; every other
tag's leg is its prefix before the first `-` (`a-1` → `a`, `a2-3` → `a2`, bare `1` → `1`). Warm-up
rows stay in the tables and are excluded from charts and medians — they are cold-load artifacts, not
comparable measurements. **Leg meanings are not recorded in the source capture**, so the site shows
leg names without interpreting them as flag settings.

`tools/validate_data.py` dispatches on that lane too: a model manifest is validated against
`schemas/modelrun.schema.json` and must ship `data/model_results.json` (validated against
`schemas/model_results.schema.json`), while `data/versions.json` stays a harness-lane requirement.

What `site/build.py` derives for this lane (both keys live next to `runs` in `site.json`):

| site.json key | Contents |
|---|---|
| `model_runs[]` | manifest fields (`kind:"model"`, `verdict`, `model{…}`, …) + `n_rows`, `n_warm`, `legs[]` + every `rows` record + `cells[]`: per input-size bucket (`1k`/`2k`/`4k`, or `unrecorded` when the capture stored no `in_tok`) the median `in_tok` and, per non-warm leg, the median `pp`/`tps` with its rep count |
| `models[]` | per `model.slug`: `quant`/`family`/`engine`, `n_runs`, median decode `tps` and prefill `pp` over all non-warm rows of that model's rounds (`tps_range` gives spread), plus `verdicts[]` — one entry per round: id, date, verdict, that round's medians, row count and legs |

Fields **not captured** for model runs today, and not to be back-filled by inference: the engine
flags each leg changed (only the round title and verdict survive), GPU-side stats for the tuning
rounds (VRAM, queue depth, TTFT), and any quality/task score for the quantization — the tuning
rounds of this lane measure speed only.

### Agentic showdown rounds (`agentic` block)

Fifteen of the model runs are not tuning ladders: they ran mini-swe-agent once over the 10
SWE-bench Verified instances on one served build and were graded by the official eval container.
Their outcome tally lives in the optional `agentic` block of the manifest
(`schemas/modelrun.schema.json`), and `site/build.py` copies that block — including its `perf`
sub-object — into `site.json` verbatim, computing nothing.

`agentic.perf` holds the agent-phase capture of the round: request count, token totals, prefill and
decode speed (mean and median), KV-cache hit share, MTP draft acceptance, longest single response,
over-length response counters, non-200 responses, window length, the `max_tokens` cap the round was
configured with, and served VRAM where the comparison table measured it.

What is populated in this checkout, and what is not:

| field group | state | source |
|---|---|---|
| `cap_tokens` | every round | run4/run5/run6/run7 state it in their own notes (`max_tokens 4096` / `8192`); final2 states it in its write-up |
| `vram_gib` | `strata_iq3s` 10.5, `strata_iq3_xxs` 15.5, `strata_ud_q3_k_xl` 22.3 | the run5 build comparison; every other build, `qwen3.8-27b` included, has no recorded figure and stays `null` |
| `encode_med` / `decode_med` / `cache_pct` on the two final2 rounds | populated | the prose medians the round write-up quotes — not an agent-phase window statistic, and the site labels them as quoted figures (the final2 manifests' own notes already say why no speed row was recorded) |
| everything else (`requests`, `in_tokens`, `out_tokens`, averages, `max_out`, the two over-length counters, `errors`, `phase_wall_s`, `mtp_acc_pct`) | `null` in all fifteen manifests | the run-level perf tables (`artifacts/agentswe/perf_tables.json`) are not present in this checkout — the read-only artifact drop is empty — and these numbers are not re-derived from other fields |

`null` in this block means **the capture did not record it**, never zero, and never a value inferred
from a neighbouring field. The same rule is why the existing `agent_phase` row of
`data/model_results.json` is never mapped onto `encode_med`/`decode_med`: the published figures are
not labelled as which of the two statistics they are, so copying them across would be a guess. The
site renders each unrecorded field as "not recorded" and drops a performance chart to a plain
sentence when no round recorded that figure at all.

## Gap analysis — unused harness fields worth leveraging

1. **`calls` → API efficiency.** `calls / resolved` gives "LLM requests per solved instance"
   (codex ≈ 63 vs hermes-agent ≈ 145 on run 3 — a real cost-per-win signal). Implemented
   2026-11-21 as the calls-per-resolved bar (`#cCalls`, runs tab); the resolved% vs calls scatter
   is still open.
2. **`empty` → failure taxonomy.** resolved / empty-patch / timeout / ungraded split is already
   in `per_instance` (R/E/T/U) but only shown as grid cells. A stacked failure-mix bar per
   harness would answer "why did it lose?" not just "did it lose?". Implemented 2026-11-21 as
   the failure-mix stacked bar (`#cFail`, runs tab).
3. **`t0/t1` → concurrency & scheduling views.** Raw epochs allow a Gantt/timeline of one run
   (instances overlapping at `workers=2`) and a throughput-over-time curve. Useful to show the
   queue isn't the bottleneck; also exposes pathological stalls (e.g. the 61-min mini window).
4. **`model_patch` → patch-size statistics.** Diff line counts per harness (added/removed), and
   patch size vs resolution (do verbose agents produce worse patches?). Patches are also the
   reproducibility contract: any third party can re-grade them with the official SWE-bench
   harness without re-running the agents.
5. **`seed` / `workers` → comparability badge.** Same rig + same seed + same workers =
   apples-to-apples; display in the run versions panel. Implemented 2026-11-21: `build.py`
   passes both through to `site.json`, and the run versions panel shows a `comparability`
   line (seed · workers · rig id).
6. **`output_tokens` (raw)** is unused on the site again — the Decode speed chart was removed;
   an input/output ratio would expose context-verbosity differences between harnesses.

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
- Model-run manifests carry the same `"hardware"` field and are checked the same way;
  `schemas/modelrun.schema.json` pins it to `bench-rig-01`. `data/versions.json` is a
  harness-lane requirement (per-harness component pins) — model runs record their engine and
  quantization in the manifest itself instead.
- For a hardware change: add/replace a rig record (e.g. `data/rigs/bench-rig-02.json`), new
  runs reference the new id — old runs keep pointing at `bench-rig-01`, so cross-run charts
  always know what machine produced each number.
