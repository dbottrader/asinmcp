# PRED-003 Benchmark Harness — baseline report

**Date:** 2026-11-05  
**Source:** corpus block `ae02903e` (`corpus/python/ae02903e.py`)  
**Extracted bench:** [`pred003_bench.py`](pred003_bench.py)  
**Structured runner:** [`run_pred003.py`](run_pred003.py)  
**Machine-readable results:** [`output/pred003/baseline-results.json`](output/pred003/baseline-results.json)  
**Raw CLI output:** [`output/pred003/cli-full-suite.txt`](output/pred003/cli-full-suite.txt)

## Extraction status

The corpus file was copied byte-for-byte first (SHA-256
`ae02903ef79b5ff4fff98157e2a9d814cae1e44e3e56eb5ef09c4bd995d39222`).
Its harness core runs, but its original `main()` did **not**: the first
five-seed aggregation raised

```text
AttributeError: 'collections.defaultdict' object has no attribute 'append'
```

because `all_metrics` was built as
`defaultdict(lambda: defaultdict(list))` and then indexed by a tuple key.
A second aggregation defect followed from the first: baseline
`convergence_speed=None` values would have been passed to `mean_ci`.

The extracted bench therefore carries exactly two documented repairs,
both in multi-run aggregation only (see
[`pred003-extraction.diff`](pred003-extraction.diff)):

1. `defaultdict(lambda: defaultdict(list))` → `defaultdict(list)`.
2. Skip `None` metrics before averaging.

No generator, solver, baseline, metric, seed, or pre-registered criterion
was changed. Extracted bench SHA-256 after repair:
`17feb106851e68902310dbbe18bae9570824bc5b1100aa05263636196a498fca`.

Environment: Python 3.12.3, NumPy 1.26.4, SciPy 1.11.4.

## What was run

- Extracted CLI: `python3 pred003_bench.py` — the source's full suite:
  8 conditions × 3 task families × 5 seeds (seeds 0–4). Completed with
  exit 0; shell wall time **2 s** (one-second resolution).
- Structured runner: `python3 run_pred003.py` — same five
  `run_harness(seed)` calls, with generator/oracle sanity checks and
  JSON aggregation. **21/21 sanity checks passed.** Harness time after
  imports: **0.202 s total**, 0.027–0.041 s per seed.
- Focused unit tests: `python3 tests/test_pred003.py` — **4/4 passed**
  (generator shapes, EPC missing-marker invariant, one-seed condition
  set + oracle bound, `mean_ci` known values). Captured in
  [`output/pred003/unit-tests.txt`](output/pred003/unit-tests.txt).

## Task families (per seed: 100 tasks)

| Family | n | Generator | Ground truth |
|---|---:|---|---|
| HND — Hierarchical Noisy Deduction | 50 | 3–5 binary premises; each premise flips a latent base value with 30% probability | Boolean: whether a majority of premises still equal the latent base |
| EPC — Epistemic Pattern Completion | 30 | Period-3 symbol pattern, sequence length 6–9, one position replaced by `-1`, plus an uncertainty marker in [0, 0.5) | Missing symbol (0–4) |
| CLPS — Closed-Loop Prediction Stability | 20 trajectories × 8 steps | Latent binary outcome; observations are latent + Normal(0, 0.2), clipped to [0, 1] | Final latent value (0/1) |

Conditions: **B1** mock single-LLM (majority of 5 heuristic
perturbations), **B2** 3-heuristic ensemble, **A1** CP8 without
scale-space, **A2** feed-forward only, **A3** independent modalities,
**A4** coupling disabled, **Full** mock CP8v23, **Oracle** ground truth.

Metrics: accuracy; the source's `brier` field; CP8-only convergence
speed (trajectory length); CLPS-only oscillation count and sigma drift.
All aggregate values below are mean ± Student-t 95% CI half-width over
the 5 seeds, computed with the bench's own `mean_ci`.

> **Metric caveat:** for EPC the source's “brier” is squared error
> between integer class labels, so it can exceed 1 (up to 16). It is not
> a probability Brier score and must not be compared with the binary
> HND/CLPS values.

## Accuracy results (mean ± 95% CI, 5 seeds)

| Condition | HND (n=50) | EPC (n=30) | CLPS (n=20) |
|---|---:|---:|---:|
| B1 single-LLM mock | 0.5640 ± 0.0849 | **0.7333 ± 0.0878** | **1.0000 ± 0.0000** |
| B2 ensemble | 0.5640 ± 0.0849 | 0.1800 ± 0.1039 | **1.0000 ± 0.0000** |
| A1 no scale-space | 0.5040 ± 0.0867 | 0.2800 ± 0.0907 | 0.0500 ± 0.0621 |
| A2 feed-forward only | 0.5040 ± 0.0867 | 0.1467 ± 0.0628 | 0.0100 ± 0.0278 |
| A3 independent modalities | 0.4600 ± 0.0465 | 0.2200 ± 0.0555 | 0.0100 ± 0.0278 |
| A4 no coupling | 0.5200 ± 0.1054 | 0.2133 ± 0.0370 | 0.0100 ± 0.0278 |
| **Full CP8v23 mock** | 0.5040 ± 0.0867 | 0.3867 ± 0.1422 | 0.0100 ± 0.0278 |
| Oracle | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |

Selected secondary metrics:

| Condition | HND “brier” | EPC “brier” (squared class error) | CLPS “brier” | CLPS drift |
|---|---:|---:|---:|---:|
| B1 | 0.4360 ± 0.0849 | 1.1933 ± 0.5089 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| B2 | 0.4360 ± 0.0849 | 5.3800 ± 1.5079 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |
| Full | 0.4960 ± 0.0867 | 2.5067 ± 0.9655 | 0.9900 ± 0.0278 | 0.1490 ± 0.0016 |
| Oracle | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 | 0.0000 ± 0.0000 |

CP8-family convergence speed is constant by construction: 5.0
iterations on HND and 3.0 on EPC for Full and every ablation. CLPS
oscillation count is 0.0000 for every condition (the source counts sign
changes in epsilon, which never changes sign), so that metric currently
discriminates nothing.

## Pre-registered criteria — FAILED, as designed to be reportable

| Comparison | Difference (Full − B1) | Criterion |
|---|---:|---|
| HND accuracy | −0.0600 | Full must beat B1 by > 0.03 — **failed** |
| EPC accuracy | −0.3467 | Full must beat B1 by > 0.03 — **failed** |
| CLPS accuracy | −0.9900 | context only |
| CLPS drift | Full 0.1490 vs B1 0.0000 | stability flag — **raised** |

Bench's own conclusion, reproduced in the CLI output:

```text
Accuracy criterion FAILED.
Stability criterion: Full shows higher oscillation/drift than B1 -> FLAG.
RESULT: No clear advantage under current coupling. Do not proceed to Option B without refactor.
```

This is a useful negative result, not a validation of CP8v23. The
Oracle scoring 1.0000 on all 15 seed/task combinations proves the
labels and scoring path are aligned; it does not rescue the mock.

## Validity limits found while wiring it (read before citing scores)

1. **The mock CP8 solvers are not blinded.** The harness passes
   `answer`/`latent` inside the observation dict, and CP8v23 reads it:
   HND computes agreement against the answer and updates feedback from
   correctness; EPC and CLPS likewise compare against the hidden label
   during iteration. The baselines mostly ignore those fields, and the
   Oracle uses them by definition. PRED-003 as shipped is therefore a
   *simulation/regression harness*, not a blinded candidate evaluation.
2. **HND's label is not the latent conclusion.** The generator sets
   `answer = (majority of premises == latent base)`, while B1/B2 predict
   the majority premise value itself. When the latent base is 0 those
   are different questions, which mechanically drives non-oracle HND
   accuracy toward chance. The family needs a label-semantics audit
   before it can grade a verifier.
3. **CLPS is saturated for simple baselines.** Clipping makes latent-0
   observations pile up at 0 and latent-1 observations stay high, so
   B1's last-3 moving average is perfect on all 5 seeds. The family
   currently discriminates “is the CP8 mock's coupling broken?” (yes)
   better than it ranks competent solvers.
4. **EPC's B2 is not a serious ensemble.** Two of its three heuristics
   are constants (`0` and `2`), so its 0.1800 is a straw baseline. B1 is
   the meaningful comparator.

## How this plugs the MVS-1 / verifier-quality gap — and where it doesn't

What it genuinely provides today:

- A **repeatable, seeded, no-LLM-call regression suite** (100 tasks per
  seed, ~0.04 s per seed) with an oracle bound and CI statistics. Any
  future verifier policy or coupling change can be run against the
  identical suite and compared number-for-number.
- A **negative control**: it already caught that the archived CP8v23
  mock coupling underperforms a trivial baseline on all three families.
  That is exactly the kind of failure a verifier-quality gate exists to
  surface before trust is granted.

What it does **not** do:

- It does **not** satisfy MVS-1's P6 calibration requirement. MVS-1
  promotion needs a frozen corpus of ≥500 hand-labeled artifact *pairs*
  judged on a declared similarity surface. PRED-003 labels are
  generator ground truth for deduction/pattern/stability tasks, not
  similarity judgments, and its tasks are not artifact pairs.
  `compute_delta(surface, a, b)` has no clean input mapping from a
  PRED-003 task dict — **that seam does not fit and was not forced.**
- It does **not** yet grade live mesh verifiers or Passport candidates,
  because they are not importable `predict(task) -> label` callables
  and the harness is not blinded (validity limit 1).

## Exact proposed integration seam (for the gated cutover phase)

**Passport — clean sibling seam, not a decoration.** In
`mesh_v02.py`, `_h_passport_certify` obtains `checks` from either
`_passport_probe_endpoint(passport, endpoint_url)` or
`_passport_fetch_evidence(...)`, then passes `checks` to
`_passport_verdicts(checks, verifiers)` and records it in the
`evidence_checks` Passport event. The honest plug point is a third
sibling, `_passport_probe_pred003(...)`, returning the **same `checks`
shape** (`mode`, per-task `results`, a passed flag), with a matching
`mode == "pred003"` branch in `_passport_verdicts`. Prerequisites
before that branch may influence a tier:

1. A blinded adapter: the candidate receives a sanitized task copy
   (no `answer`/`latent` fields); labels are joined only by the scorer.
2. A typed endpoint contract for structured tasks — the current
   Passport endpoint contract (`{scenario, instruction}` in, free text
   out) cannot encode an EPC sequence or parse a typed prediction.
3. A label-semantics fix or replacement for the HND family.

Until those exist, the correct operational use is **offline**:
run `run_pred003.py` as a pre-qualification/regression report for a
verifier policy, and record its bench SHA-256 + aggregate JSON hash as
evidence alongside — never inside — an HHC adjudication. There is no
seam in `_adjudicate` for synthetic benchmark scores, and none should
be added: settlement must keep consuming only the two recorded
verdicts.

## Reproduce

```bash
cd ~/workspace/implementation-mining/tranche2
python3 pred003_bench.py        # full CLI suite, 5 seeds
python3 run_pred003.py          # structured JSON + sanity checks
python3 tests/test_pred003.py   # 4 focused tests
```
