# Refusal-Aware Verification Gate — built

Node-side implementation of the refusal-aware verification gate in
[SPEC.md](SPEC.md) design v2 (which merged the Verification Gate
Specification proposal, [VERIFICATION-GATE-PROPOSAL.md](VERIFICATION-GATE-PROPOSAL.md)).
Built 2026-11-11 on Dennis's order. Hub-side quorum counting, reputation
and payout gating are GrokAce's and are **not** built here.

## Files

| File | What it is |
|---|---|
| `gate.py` | The gate: outcome state machine, the seven mandatory checks, ASIN-HHC-VERIFICATION-1.0 receipt emission, hash-chained receipt ledger, signer interface (TestSigner + VaultSigner). Stdlib only, no network. |
| `test_gate.py` | Adversarial suite: all ten SPEC v2 cases (expected outcome declared before each run) + clean PASS + ledger tamper detection + ephemeral-vault signer round-trip. |
| `demo_gate.py` | Four attempts end-to-end against an ephemeral vault — PASS, FAIL, VOID resolved by a third placement, REFUSED — with every receipt printed and a final chain verification. |
| `ci/verify-gate.yml` | GitHub Actions workflow that runs the suite + demo on push. Drop-in file only; **not pushed anywhere**. |

## Run it

```
python3 test_gate.py    # 14/14 cases, exit 0 (takes ~2 min, see Limits)
python3 demo_gate.py    # prints 5 receipts, ends "Chain verify ... OK"
```

## How the gate decides

Every attempt measures all seven mandatory checks first, then the first
matching rule decides:

1. Residual (stored vs independently retrieved counts) — always computed
   and recorded on the receipt.
2. Precondition freshness — stale → **VOID** (`STALE_PRECONDITIONS`);
   a `verification_id` may be used exactly once, so replaying a
   verification (expired or not) raises `ReplayRejected` and emits no
   receipt.
3. Independent control — a control that fails its known expected result
   → **REFUSED** (`CONTROL_FAILURE`): the instrument cannot be trusted,
   so no claim is produced.
4. Tampered evidence (a witness output that no longer hashes to its
   seal) → **FAIL** (`SEAL_MISMATCH`).
5. Witness validity — a missing/invalid Ed25519 witness signature makes
   that witness invalid; fewer than two valid witnesses → **REFUSED**
   (`INSUFFICIENT_VALID_WITNESSES`).
6. Instrument independence — assessed from measured metadata: two valid
   witnesses count as independent only if they differ in **both**
   failure mode **and** operator. No independent pair → **REFUSED**
   (`NO_INDEPENDENT_WITNESS`). The assessment (`ASSESSED_INDEPENDENT` /
   `ASSESSED_NOT_INDEPENDENT` / `INSUFFICIENT_WITNESSES`) is written on
   the receipt.
7. Discriminating condition — with no control, or a control that cannot
   distinguish the claim, a zero residual proves nothing → **REFUSED**
   (`NO_DISCRIMINATING_CONDITION`). A nonzero residual is itself
   discriminating evidence → **FAIL** (`RESIDUAL_MISMATCH`).
8. Conflict — independent witnesses disagreeing → **VOID**
   (`WITNESS_CONFLICT`), preserved until an independent third placement
   resolves 2-of-3 to PASS or FAIL via `Gate.resolve()`. A failed
   placement (bad signature, tampered, not independent) leaves it VOID.
   Unanimous disagreement with the gate's blind re-execution → **FAIL**.

Blindness is by construction: an attempt never receives the claimant's
claimed output. The gate runs the solver callable itself (job params
must carry temperature 0 + a fixed seed) and seals its output — sha256
over the canonical form — **before** any witness seal is compared.

REFUSED is terminal: the transition table gives REFUSED (and PASS/FAIL)
no outgoing transitions, resolution is only possible from a
witness-conflict VOID, and reusing an attempt's `verification_id`
raises. A new attempt is a new id with its own receipt.

## Receipts

Every attempt — PASS, FAIL, VOID and REFUSED alike — emits exactly one
signed receipt conforming to ASIN-HHC-VERIFICATION-1.0 (the SPEC fields,
plus `prev_receipt_hash`, `signature`, `signer`, `attempted_at`,
`resolution_of`). Canonical JSON = sorted keys, compact separators.
`receipt_hash` = sha256 of the canonical receipt excluding exactly the
`receipt_hash` and `signature` fields. Receipts chain: each carries the
previous receipt's hash (genesis = 64 zeros), optionally appended as
JSONL to a ledger file. `chain_verify` / `chain_verify_file` recompute
hashes, linkage and signatures and detect later edits — demonstrated
by the ledger-tamper test case. `external_anchor` is null: mesh-ledger
anchoring of gate receipts is the documented next step, not built here.

## Signing

`Gate` takes any signer implementing `meta() / sign(bytes) -> dict /
verify(bytes, dict) -> bool`:

- **VaultSigner** (used by the demo and one test case) shells out to
  `~/workspace/agent-vault/vault.py` — action `doc.sign` under the
  vault's default policy — signing the receipt hash; the vault's ts,
  nonce and its own receipt hash ride in the signature dict so
  verification rebuilds the vault envelope exactly. Tests and demo
  create **ephemeral vaults in temp dirs** with a throwaway secret;
  `~/workspace/agent-vault/live/` is never touched.
- **TestSigner** is an HMAC-SHA256 signer for the offline suite
  (verification key == signing key — a test convenience, not custody).

Witness signatures are Ed25519 over the witness's sealed output, using
the same vendored pure-Python implementation the vault uses
(`~/workspace/asinmcp/ed25519.py`, imported read-only).

## Decisions the SPEC left open (made here, flagged)

- **VOID resolution emits a second receipt** sharing the
  `verification_id`, with `resolution_of` pointing at the VOID
  receipt's hash. "Every attempt emits exactly one receipt" is read as
  one receipt per submission; a resolution is a new submission.
- **Replay = reused verification_id.** There is no separate replay
  channel in a node-side library; id reuse is the replay, and expiry is
  what makes the SPEC's case a *replay of an expired verification*.
- **A nonzero residual FAILs even without a control**: the residual
  check is itself a discriminating condition. The REFUSED-for-no-control
  rule applies to the zero-residual case, exactly as the SPEC's
  adversarial list words it.
- **Third-placement independence** is assessed against *both* original
  witnesses (failure mode and operator must differ from each).

## Honest limits

- **Independence assessment is metadata-based.** The gate compares the
  operator / failure-mode / implementation / data-source strings a
  witness declares. It cannot detect two "different" witnesses secretly
  run by one operator on one stack — that is exactly the correlated-
  failure gap the SPEC's evidence boundary names. Placement integrity
  and operator honesty are hub/process problems, not solved here.
  Sharpened by an independent Grok review (2026-11-11): the criterion
  is self-referential — the suite and the live run demonstrate internal
  consistency with the rule as implemented; they do not demonstrate
  that the rule resists collusion by a single controlling party (one
  host holding the vault, the ledger, and both witnesses is precisely
  tonight's live configuration, and the gate's answer to it was
  REFUSED, not a claimed PASS). Treat any future PASS as "independent
  as declared and assessed," never as proof against masquerade.
- **A quorum of re-executions proves agreement, not truth.** All
  witnesses run the same solver; a wrong solver passes unanimously.
- **The near-miss path (SPEC rule 4)** — a semantic second check when
  hashes differ — is represented only by the third-placement mechanism;
  no semantic judge is implemented.
- **External anchoring is demonstrated, not built into the library**:
  gate.py leaves `external_anchor` null in the signed receipt (a
  receipt cannot name its anchor before the anchor exists); the
  live-run script anchors the receipt hash on the mesh ledger and
  records the anchor in a sidecar (see live-run/). Local chain
  verification alone is tamper-evident, not tamper-proof (same limit
  the vault README states: a host attacker can rewrite a whole chain;
  only an externally anchored head defeats that).
- **Chain state resumes across processes** — chain head, used
  verification IDs, and open VOID contexts are reloaded from the
  ledger file on construction. The first version did not do this and
  the first live run broke its chain at index 1; the defect, its fix,
  and the preserved broken chain are documented in live-run/README.md
  and covered by a regression test.
- **Performance**: the suite takes ~2 minutes and the demo ~45 seconds,
  almost all of it pure-Python Ed25519 witness signatures and the
  vault's 200k-iteration PBKDF2 per signing call. Fine for a checker
  node; not a hot path.
- **Nothing here proves production security.** This is a working,
  test-covered implementation of the specified state machine and
  receipt discipline — per the SPEC's evidence boundary, passing our
  own tests demonstrates only the properties tested, under the
  conditions recorded.
- Settlement context unchanged: Base Sepolia **testnet**, always
  labeled; verifiers are paid from the fee pool on any verdict
  (hub-side, GrokAce); failed verification of a job = refund minus the
  10% fee pool.
