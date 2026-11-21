# Methodology

One rig, **two bench lanes**, one generated site. They share a machine, a rig record and a
repository layout, and they answer different questions — so they are kept in separate lanes from
the manifest onwards, and no number is ever mixed between them.

| | harness lane | model lane |
|---|---|---|
| question | how much does the *agent harness* matter when the model is fixed? | did this *engine / quantization* setting make the served model faster? |
| unit of comparison | harness vs harness on byte-identical instances | leg vs leg inside one input-size cell |
| metrics | resolved %, input/output/cache tokens, wall time, calls per resolved | prefill `pp` (input tok/s), decode `tps` (output tok/s) |
| run dir | `runs/<date>-<model>-sbNN-<n>way/` | `runs/m-<date>-<slug>/` |
| data files | `data/results.json`, `windows_*.jsonl`, `preds_*.json.gz`, `versions.json` | `data/model_results.json` |
| verdict | none — the leaderboard *is* the result | written by hand: INFO / KEEP / CONFIRM-KEEP / REVERT / UNDO |

File-level detail (every field, who reads it) lives in [DATA_INVENTORY.md](DATA_INVENTORY.md).

## Harness lane

- **Model fixed; the harness is the only variable.** Identical task text, repo snapshot and base
  commit for every harness; each keeps its own internal system prompt and tools — that is exactly
  what is being measured.
- **Clean isolation.** Each harness runs headless inside the official `sweb.eval.*` image with the
  portable runtime mounted read-only; harness state lives in a per-harness home. No shared state
  between harnesses.
- **Grading outside the harness.** The `git diff` left in the worktree is re-applied and graded by
  the official swebench grader in a fresh container (FAIL_TO_PASS / PASS_TO_PASS). A harness cannot
  fake success inside its own session.
- **Deterministic dataset.** A fixed instance subset per cohort. Only cohorts built from the same
  subset are directly comparable — the site's cohort map and comparability line make that explicit.
- **Significance.** Pairwise exact two-sided McNemar on discordant resolved counts between harness
  pairs on identical instances. Displayed as p-label bands (`p<.001`, `p<.01`, `p=X.XX`, `ns`) —
  never a bare `0.00`.
- **Reproducibility.** Every run carries `run.json` + `data/versions.json` (exact component
  versions and config), and raw patches are gzip-persisted so a third party can re-grade without
  re-running the agents.

## Model bench lane

### What a model run is

A **round** is one tuning experiment on the served model: change something in the inference engine
(a quantization, a KV/cache setting, a thread or batch knob), measure, compare against a baseline,
then decide whether to keep the change. A round is a directory `runs/m-<date>-<slug>/` with a
`kind:"model"` manifest and one data file, `data/model_results.json`, whose `rows[]` hold one
record per measurement:

```
{"leg","tag","in_tok","out_tok","pp","tps","draft","draft_acc"}
```

There are no harnesses, no instances and no grading in this lane. The measured quantities are
**prefill speed** (`pp`, input tok/s) and **decode speed** (`tps`, output tok/s). Rows are bucketed
into input-size **cells** (`1k` / `2k` / `4k`, or `unrecorded` when the capture stored no
`in_tok`), because prompt length dominates both numbers: comparing a 1k-prompt leg against a
4k-prompt leg is meaningless.

### Legs

A **leg** is one arm of the round (baseline, treatment, sometimes a second treatment). Legs come
out of the raw capture *mechanically*, never by inference:

- a row tagged `warm` (or `warm2`, `warm3`, …) keeps leg `warm*`;
- every other leg is the tag's prefix before its first `-` (`a-1` → `a`, `a2-3` → `a2`, `1` → `1`);
- the original capture label survives unchanged in `tag`, so any row can be traced back.

**Leg meanings are not recorded in the source capture.** The site shows leg names as they were
recorded and never presents them as flag settings; the engine flags each leg changed are one of the
fields this project does *not* have and will not back-fill by guessing. The `draft` / `draft_acc`
columns are the capture's own speculative-decoding counters, shown raw and undocumented for the
same reason.

Warm-up rows are cold-load artifacts (model load, first-touch KV allocation), not comparable
measurements: they are excluded from every chart, cell and median, and stay in the raw row table
(dimmed) so nothing is hidden.

### Verdicts

`verdict` is the round's decision, and it is **manual**. The pipeline copies the first token of the
capture's `verdict.txt` into the manifest and validates it against the enum; it never computes,
scores or suggests one. A round whose capture carries no verdict is recorded as `INFO` — measured,
no decision — rather than being defaulted to something that looks like a result.

| verdict | meaning |
|---|---|
| `INFO` | measured only; no decision recorded (including: no verdict in the capture) |
| `KEEP` | the setting is better and was adopted |
| `CONFIRM-KEEP` | a later round reproduced an earlier `KEEP`; provisional becomes confirmed |
| `REVERT` | the setting was adopted and then taken back out |
| `UNDO` | the setting was never adopted; the measurement argued against it |

`KEEP` alone is provisional — a single round can be inside the noise. The vocabulary therefore
distinguishes a first positive measurement (`KEEP`) from one a later round reproduced
(`CONFIRM-KEEP`), and the two negative flavours differ in *when* the change was undone.

### Noise floor

A round is only citable if it clears this bar:

1. **Median over ≥3 reps per cell.** A bar in a per-cell chart is the median of at least three
   repeats of that leg in that input-size cell — never a single sample.
2. **Warm rows out** of every median and chart, as above.
3. **Both directions must move together or be explained.** A decode gain with a prefill regression is
   a trade-off to state, not a win to claim.
4. **Verdicts stay manual**, and a decision that survives is expected to be re-measured by a later
   round (`KEEP` → `CONFIRM-KEEP`).

The seeded rounds do **not** all clear that bar, and the site says so rather than smoothing it over:

| round | what it holds | what is citable |
|---|---|---|
| `m-…-iq4b` | 3 measured rows, no `in_tok` recorded at all | round-level medians only; its rows share one unlabelled `unrecorded` cell |
| `m-…-iq4c`, `m-…-iq4d` | 3 rows, each a *different* input size | round-level medians; **no cell holds two legs**, so no per-cell leg-vs-leg delta exists |
| `m-…-iq4e`, `m-…-iq4f`, `m-…-iq4g` | 3 legs × 3 cells, **1 rep per leg per cell** | round-level medians over 9 rows clear the ≥3 bar; the individual cell bars are single measurements and are labelled with their rep count in the tooltip |

Rounds that cannot support a cell-level comparison get an explicit note above the charts
(`#cellNote` in the site) instead of a grouped bar chart implying a match the capture does not
contain. Across all six seeded rounds, 12 of 48 rows are warm-up.

### What this lane does **not** claim

- **Nothing about quality or task correctness.** A faster quantization may be worse at the tasks;
  this lane has no measurement of that and its verdicts are speed decisions only.
- **No cross-model comparability of harness scores.** The harness lane's resolved-% numbers belong
  to one fixed served model. A model round cannot be used to re-rank harnesses, and harness results
  measured on one model cannot be compared with results from another. The `models[]` overview bars
  index each slug's own rounds — they are not a model leaderboard.
- **No comparability with the harness lane's numbers.** `tps`/`pp` measure a bench harness driving
  the engine directly; harness-lane tokens are counted through llama-swap under agent load with
  concurrent workers. Different measurement path, different concurrency, different prompt mix.
- **No engine attribution.** Without recorded flag names, a round shows *that* a leg was faster,
  not *why*. Nothing in this repo names the flags a leg changed.
- **One rig, one engine.** Every seeded round names `bench-rig-01` and
  `strata (llama.cpp fork) via llama-swap`; a number from another machine is a different
  experiment, not a repeat of this one.

### How to add a model round

See [CONTRIBUTING.md](../CONTRIBUTING.md) — "Add a model bench round".

## Gates

Both lanes are gated in CI (`.github/workflows/ci.yml`): `tools/validate_data.py` validates every
manifest against its lane's schema (`schemas/run_manifest.schema.json` for harness runs,
`schemas/modelrun.schema.json` + `schemas/model_results.schema.json` for model runs) and cross-checks
the rig id; `site/build.py` rebuilds `site.json`; `tools/smoke.py` drives a headless browser at
1280 px and 390 px and requires every registered canvas in `CANVASES` to contain pixels, both lanes
to hydrate, and zero console errors.
