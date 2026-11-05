# Tranche 3 — Validator Harness (task validators): assessment

**Date:** 2026-11-05 · **Status:** STAGED + TEST-PROVEN. Live services
were **not** edited and **not** restarted; no live data was written.
Cutover is a separate gated step (see recommendation).

**Live-file safety proof:** SHA-256 of both live code files is identical
before and after this build ([`output/live-hashes-before.txt`](output/live-hashes-before.txt),
[`output/live-hashes-after.txt`](output/live-hashes-after.txt)):

| Live file | SHA-256 (unchanged) |
|---|---|
| `agent-mesh/v02/mesh_v02.py` | `7f04f74c98cb7097f11e71bce18450df0daeb8c521838450ecf96e833f2cacce` |
| `agent-mesh/v03-hhc/hhc_mesh.py` | `905e602e0a4521842db7c015027a59b1ff22f4d720fa1bf448a93e61073b81c1` |

All integration testing ran against [`data/mesh_copy.db`](data/mesh_copy.db),
a SQLite backup of the live DB taken through a read-only (`mode=ro`)
connection. The adapters open even that copy read-only.

---

## 1. What the mined source actually is

Source: corpus `python c50ed37e`, deepseek mirror, 15,945 B —
[`original/c50ed37e.py`](original/c50ed37e.py) (SHA-256
`c50ed37ebc6717c784fdf8c0cd0bda20630f91d171ab266ee7adbc4a3adaa77d`).

An LLM task-validation benchmark harness:

- Three deterministic validators behind a `Validator` base class and a
  `get_validator(task_type, ground_truth)` factory, each returning
  `{success, failures, score, confidence}`:
  - **TransactionValidator** — checks per-user totals appear in the
    response text and that no negative amount appears.
  - **CreativeValidator** — required-element IoU ≥ 0.85, length window,
    outline format, plus a creativity score (lexical diversity +
    vivid-keyword density + theme-word entropy, pass ≥ 3.0/5).
  - **ReasoningValidator** — Einstein-riddle specific: final-answer
    match, ≥ 95 % clue coverage, and a quality score from step count,
    an entity-graph DAG check (networkx), and TF-IDF cosine progression
    between consecutive steps (numpy).
- **Model caller** — OpenAI Responses API (`gpt-4.1-mini` default).
- **Task runner** — `run_task()` (call → validate → rich result dict)
  and `build_tasks()`: 6 tasks = baseline vs "ASINHHC" symbolic-prompt
  variants of the 3 task types. This is a prompt-format A/B benchmark,
  not a general-purpose verifier service.

### Inventory claims vs reality

| Inventory claim | Reality (evidence) |
|---|---|
| "Runnable code" | **False as archived.** The file does not parse: `SyntaxError` at line 32 (`if f"{uid}": not in ...`). Reproduce: `python3 -m py_compile original/c50ed37e.py`. One colon-placement fix makes it compile. |
| "Transaction/Creative/Reasoning validators with ground truth, model caller, task runner and scoring" | **True** — all present and, after the syntax fix, functional (tests below). |
| "Dependencies: an LLM endpoint for call_model" | **Incomplete.** Also hard-requires `openai` and `networkx` at import time (neither is installed in the fleet's system python; `openai` construction at module level additionally raises when `OPENAI_API_KEY` is unset). Only the validators' numpy dependency was satisfiable out of the box. |
| "Directly reusable for Passport certification battery scoring and verifier-quality measurement" | **Overstated.** Nothing in the source knows about passports, escrows, or verdicts. Reuse is real but indirect: the `{success, failures, score, confidence}` result shape is a good verdict-evidence shape, and the deterministic-validator pattern is the right tool for objective work types. The mapping to live shapes is new code — [`live_adapters.py`](live_adapters.py) in this tranche. Similarly, the live Passport endpoint battery (mesh_v02.py `_passport_probe_endpoint`, 4 scenarios: identity / scope_refusal / spend_limit / instruction_following) is already deterministic code with recorded raw results; the harness adds nothing to it directly. |

## 2. What was staged

| File | Role |
|---|---|
| [`validator_harness.py`](validator_harness.py) | The mined module with exactly 4 minimal adaptations (full diff: [`validator_harness.diff`](validator_harness.diff), 30 changed lines). **A1** line-32 colon fix (source does not parse otherwise). **A2** `networkx` import made lazy (only ReasoningValidator needs it). **A3** OpenAI client constructed lazily (module-level construction raised without a key and made the validators unimportable without the SDK). **A4** `run_task()` gains an optional `model_caller` parameter (default preserves original behaviour) so the runner works against any endpoint — or a stub — not only OpenAI. No validator logic was changed. |
| [`live_adapters.py`](live_adapters.py) | New wrapper layer (the only new logic): `validation_to_verdict_body()` (harness result → live HHC verdict body), `score_passport_checks()` (deterministic re-score of recorded passport `checks` JSON in harness shape), `verifier_agreement_report()` (read-only verifier-agreement / pass-rate stats from a DB copy), `LedgerFooterValidator` + `has_machine_footer()` (new validator in the harness's own pattern for the machine-footer format observed in live `hhc_escrow.result_ref`), and read-only extractors for result refs and certifications. |
| [`tests/test_validator_harness.py`](tests/test_validator_harness.py) | 16 unit tests — [`output/unit-tests.txt`](output/unit-tests.txt): **16/16 pass**. |
| [`tests/test_integration.py`](tests/test_integration.py) | 5 integration tests against the DB copy — [`output/integration-tests.txt`](output/integration-tests.txt): **5/5 pass**. |
| [`data/mesh_copy.db`](data/mesh_copy.db) | Read-only backup copy of the live mesh DB (43 escrows, 36 verdicts, 2 passport certifications at copy time). |
| [`vendor/`](vendor) | `networkx 3.7` installed with `pip --target` (18 MB) so the reasoning validator could be exercised; the staged module does not depend on this directory (A2 makes the import lazy). |

## 3. What works (measured)

- **All three validators execute** and behave deterministically.
  Transaction: pass/fail on totals present/missing. Reasoning: a
  programmatically generated compliant 15-step response passes at
  score 5.0; wrong final answer and too-few-steps fail with the
  expected failure strings. Creative: deterministic checks (IoU,
  length, format, coherence) behave as coded.
- **Runner end-to-end without an LLM endpoint**: `run_task()` with a
  stub caller returns the full result dict with token accounting —
  this is the seam a fleet-seat caller would plug into at cutover.
- **Import hygiene after A2/A3**: the module imports in a subprocess
  with no `openai`, no `networkx`, and no API key (unit test
  `test_importable_without_openai_networkx_or_api_key`).
- **Verifier-quality measurement on real data** (the use the inventory
  promised): on the DB copy, 36 verdicts cover 18 escrows, all with
  ≥ 2 verifiers; **agreement 15/18 = 83.3 %**, 3 disagreements. The two
  busiest verifiers lean opposite ways (7 verdicts each; pass rates
  2/7 ≈ 0.29 and 3/7 ≈ 0.43, vs 25/36 ≈ 0.69 overall) — exactly the
  kind of signal worth surfacing before verdicts move money.
- **Passport re-scoring reproduces the live system exactly**: for both
  recorded certifications, `score_passport_checks()` reproduces the
  recorded per-slice verdict split (cert v1: reachability fail /
  consistency pass → score 0.5, tier Registered; cert v2: both pass →
  1.0, tier Provisional). The adapter is a faithful offline oracle for
  the live `_passport_verdicts` slices.
- **Machine-footer validation on real results**: 2 of 18 live
  `result_ref`s carry the footer format; both are internally
  consistent (entry_count = seq_hi − seq_lo + 1, as_of_height ≥
  seq_hi) and both belong to TERMINAL_PAID escrows. Tampering the
  entry_count is caught.

## 4. What's broken (in the source; documented, deliberately not
## silently fixed)

1. **Syntax error** (line 32) — the archived file never ran as-is.
   Fixed in staging (A1); the fix is unambiguous.
2. **TransactionValidator can never pass the output format its own
   benchmark demands.** The per-user check searches for the literal
   `1:` / `3:`, which quoted JSON keys (`"1":`) never contain — yet
   the baseline task prompt in the same file orders "Output JSON
   only." Measured: correct totals as quoted JSON → both users
   reported missing; the same totals unquoted or as `user 1: …` lines
   → pass. Any historical benchmark result from this harness scored
   JSON responses as failures for a formatting artefact.
   (`test_transaction_FLAW_quoted_json_keys_always_fail`)
3. **TransactionValidator fails correct audit logs.** The blanket
   regex `-\d+\.\d+` fails any response that *mentions* a filtered
   negative amount, even when the filtering itself is correct.
   (`test_transaction_FLAW_correct_filter_log_is_failed`)
4. **CreativeValidator's creativity gate is miscalibrated.** A story
   satisfying every stated requirement (all 9 elements, length,
   format, coherence) scores **2.9/5** and fails overall solely on the
   creativity gate, whose vivid-keyword-density sub-score
   (vivid words ÷ total words) natural prose cannot push high enough
   to reach the 3.0 mean threshold. The deterministic checks are
   usable; the creativity score, as calibrated, is not.
   (`test_creative_CALIBRATION_compliant_story_still_fails_creativity_gate`)
5. **ReasoningValidator is a single-puzzle instrument.** Entity regex,
   step format, and clue format are hard-coded to the Einstein riddle;
   `num_clues` ground truth in `build_tasks()` (15) contradicts the
   baseline prompt's own text ("20 clues"). It generalises as a
   pattern, not as code.
6. **Ground-truth coupling.** Every validator needs a ground-truth
   dict. Live HHC work items carry free-text task bodies and
   `result_ref`s with no structured ground truth, so the mined
   validators cannot score arbitrary live work — only work types whose
   publisher supplies machine-checkable expectations (as the footer
   format does organically).

## 5. Integration points (exact, for a future gated cutover)

1. **HHC verdict path — advisory evidence only.**
   `agent-mesh/v03-hhc/hhc_mesh.py`, `_h_hhc_verdict` (def at line 814):
   after the existing verdict-tree rendering block and before the
   `hhc_verdicts` INSERT, a harness validation of the escrow's
   `result_ref` (validator chosen from the work item's declared type)
   could be attached to `verdict_payload` alongside the existing
   `verdict_tree` / `verdict_rollup` keys (payload built at lines
   ~883–890), and folded into `reasoning` via
   `live_adapters.validation_to_verdict_body()`. The binary verdict
   must remain the human/agent verifier's (or the tree roll-up's) —
   the harness block is evidence, not a vote. Note the handler reads
   only `verdict`, `reasoning`, and `verdict_tree` from the request
   body today; the adapter's extra `harness` key would be ignored by
   the handler, which is why the adapter also folds the detail into
   `reasoning` (capped at the handler's 4000 chars). Import seam:
   follow the tranche-2 pattern — `sys.path` already includes the v02
   dir in hhc_mesh.py (verdict_tree import at lines 82–88); place
   `validator_harness.py` beside it and import guarded the same way.
2. **Verifier-quality reporting — offline, zero live risk.**
   `verifier_agreement_report()` can run against the periodic DB
   backup and feed the ops scoreboard (agreement rate, per-verifier
   pass rates, disagreement list). No live-code change at all.
3. **Passport certification — offline oracle / regression check.**
   `score_passport_checks()` against `passport_certifications.checks`
   reproduces `_passport_verdicts` (mesh_v02.py line 1071) slices; run
   it in CI against recorded certifications to catch scoring drift
   when the live slices change. Do not wire it into the live certify
   path — it would duplicate logic that already exists there.
4. **Deterministic work types — where the mined validators earn
   their keep.** If the work market gains task types with declared
   ground truth (transaction-audit being the natural first one, after
   fixing flaw §4.2/§4.3), `get_validator()` + `run_task(...,
   model_caller=<fleet seat>)` gives a ready runner. The footer
   validator shows the pattern for organically checkable formats.

## 6. Risks

- **Acting on harness verdicts for money movement.** The transaction
  flaws (§4.2, §4.3) would fail correct work; the creative gate
  (§4.4) would fail almost all work. Any cutover that lets harness
  output influence settlement before those are fixed and re-baselined
  risks wrongful refunds. The advisory-only seam (§5.1) contains this.
- **Dependency weight.** ReasoningValidator needs `networkx`;
  `call_model` needs `openai`. The live services are stdlib-only
  today (verdict_tree is stdlib-only). Lazy imports (A2/A3) keep the
  module import-safe, but a cutover should vendor or drop these paths
  rather than add service dependencies — numpy is already a new
  dependency the live code does not currently take.
- **Snapshot staleness.** Integration counts (36 verdicts, 83.3 %
  agreement, 2 certifications, 2 footers) are properties of the
  2026-11-05 DB copy; the integration tests assert them exactly and
  will (correctly) fail against a refreshed copy until re-measured.
- **Score semantics.** Harness `score` scales differ per validator
  (0/1 transaction, 0–5 creative/reasoning). The adapter carries them
  through verbatim; any cross-type comparison at cutover must
  normalise first.

## 7. Recommendation: **GO-WITH-CHANGES**

- **Go now (no live change):** adopt `verifier_agreement_report()` as
  an offline ops measurement and `score_passport_checks()` as a CI
  oracle. Both are proven against real data in this tranche and carry
  no settlement risk.
- **Go after changes (gated cutover):** the advisory-evidence seam in
  `_h_hhc_verdict` (§5.1), only after (a) TransactionValidator flaws
  §4.2/§4.3 are fixed with tests flipped from FLAW-documenting to
  behaviour-asserting, (b) the creative creativity gate is
  recalibrated against a labelled sample or dropped to advisory, and
  (c) dependencies are resolved stdlib-only or vendored.
- **No-go:** the mined validators as autonomous verdicts on live
  escrows, and `call_model` in its current OpenAI-only form (the fleet
  has its own seats; A4's injectable caller is the right shape).

## Reproduce

```bash
cd ~/workspace/implementation-mining/tranche3
python3 tests/test_validator_harness.py   # 16/16
python3 tests/test_integration.py         # 5/5
diff -u original/c50ed37e.py validator_harness.py | less
```
