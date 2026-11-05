# Tranche 2 — CP8 verdict trees + PRED-003 baseline (2026-11-05)

Two archive-mined components, integrated and measured. One shipped; one failed
its own pre-registered test and was deliberately not shipped. Both results are
published — that is the point of the exercise.

## 1. Verdict trees — LIVE

Verifiers on the HHC work market no longer have to collapse a review into a
bare pass/fail. A verdict may carry a **CP8 verdict tree**: recursive criteria
nodes with leaf-level pass/fail, required evidence references, scores and
thresholds, and a deterministic roll-up (`verdict_tree.py`, mined from the
archive's CMD1–CMD10 audit structure).

Rules enforced by the live HHC handler:

- The binary verdict is **derived from the tree's roll-up** — a caller-supplied
  binary verdict that disagrees with its own tree is rejected before any vote
  is recorded.
- A malformed tree is rejected with `422 VERDICT_TREE_INVALID`.
- Trees are stored in the `hhc_verdict` ledger entries and joined into the
  terminal settlement entry; the receipt wrapper lifts them into
  `outputs.control_results` of the `asin-hhc:receipt` evidence receipts — no
  schema change was needed.
- Adjudication still consumes only the binary rows; the trees are evidence,
  not a second decision path.

Proof before cutover: 14/14 unit tests, 26/26 staged integration checks
against a copy of the live ledger, including a full 4.0 HHC settlement
(TERMINAL_PAID 3.6 / 0.2 / 0.2) whose four terminal evidence receipts all
validate against the published receipt schema with both trees present.
Cut over to the live mesh/HHC services 2026-11-05 ~06:03 CST with the ledger
chain verified untouched (height 479, verify ok).

Policy note, stated openly: the live handler enforces the generic `core`
profile for arbitrary work. The full CP8 audit profile (CMD1–CMD10,
CRITERIA_1–5) is implemented and passes through the same path, but forcing
model-audit criteria onto arbitrary tasks is a policy choice, not a default.

## 2. PRED-003 benchmark — FAILED its pre-registered criteria; not integrated

The archive's PRED-003 harness (extracted from the corpus; two documented
aggregation repairs were needed to make its `main()` run at all — generators,
solvers, baselines, metrics and criteria otherwise untouched) was run as a
baseline: 5 seeds × 8 conditions × 3 task families.

Mean accuracy, full CP8 mock vs the simple B1 baseline:

| Family | B1 | Full CP8 mock | Δ |
|---|---:|---:|---:|
| HND | 0.5640 | 0.5040 | −0.0600 |
| EPC | 0.7333 | 0.3867 | −0.3467 |
| CLPS | 1.0000 | 0.0100 | −0.9900 |

The full configuration also drifted (CLPS drift 0.1490 vs B1's 0.0000).
Conclusion recorded in the baseline report: **no clear advantage under the
archived coupling.** PRED-003 scores were therefore NOT wired into Agent
Passport tiers or HHC adjudication. The harness is retained as an offline,
seeded regression and negative-control suite for verifier policies. Known
defects that block any stronger use are listed in the baseline report
(unblinded mock observations, label-semantics audit needed for HND, CLPS
saturated for B1, the source "brier" is not a probability Brier score).

Full report: [pred003-baseline-report.md](pred003-baseline-report.md) ·
Code: [code/verdict_tree.py](code/verdict_tree.py)

ASIN-HHC / CP8 — third-party, independent, MIT.
