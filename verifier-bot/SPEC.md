# Verifier Bot — secure verification system for the GPU mesh

Status: design v2, 2026-11-11. Merges the refusal-aware Verification Gate
Specification (filed verbatim at VERIFICATION-GATE-PROPOSAL.md; Dennis ordered
the merge 2026-11-11 20:53 CST) into the v1 design of 2026-11-07 ~23:47 CST.
Dennis's direction: the checker becomes a verifier bot — a secure system in
the ecosystem. muse-checker is the first one. Dennis's bar: reliable,
sovereign, secure, sellable — not "slop".

## The role

A verifier bot ONLY verifies. It never runs the original job. Any node can opt
into verifier duty; the hub assigns verification jobs to nodes that did not do
the work. Payout goes to the verifier's address.

## Core principle (v2)

A verification system must be capable of refusing to produce a result.

A test that cannot fail is not evidence. A test that cannot distinguish
competing hypotheses must not report verification. The system distinguishes:
a claim supported by independent evidence; a claim contradicted by valid
evidence; conflicting evidence; and insufficient conditions to evaluate.

## The four outcomes (v2 — never collapsed into a boolean)

| Outcome  | Meaning                                            | Required action                                  |
|----------|----------------------------------------------------|--------------------------------------------------|
| PASS     | Independent verification agrees                    | Accept result                                    |
| FAIL     | Valid evidence contradicts the claim               | Reject result                                    |
| VOID     | Witnesses conflict, or preconditions are invalid   | Request another independent placement            |
| REFUSED  | No discriminating condition exists                 | Produce NO verification claim                    |

REFUSED is terminal for an attempt: a REFUSED attempt can never be converted
into a PASS. A new attempt is a new verification_id with its own receipt.
No evidence, no PASS. No independent witness, no independent verification.
No discriminating condition, REFUSED.

## The rules

1. **Deterministic re-execution.** Worker and verifier both run temperature 0
   plus the job's fixed seed. Agreement must be checkable, not a coin flip.
   The re-execution is blind: it reproduces the computation without relying
   on the original solver's claimed result.
   (v1 failure that motivated this: sampled text almost never matches — both
   of muse-checker's first verifications came back `disagree_sampling`.)
2. **Compare canonical hashes, not words.** sha256 of the normalized output.
   Exact match = agree.
3. **Seal-before-comparison (v2).** Outputs are cryptographically sealed
   before they are compared. Evidence modified after sealing is detectable
   and the attempt cannot PASS.
4. **Near-miss path.** Hashes differ → a second independent check (a semantic
   judge, or a second model) decides agree/disagree, and the reason is written
   on the receipt.
5. **Quorum.** 2-of-3 independent verifiers must agree before settlement.
   No single verifier can pass or fail a job alone. Conflicting witnesses
   stay VOID until an independent third placement resolves them.
6. **Pay from the fee pool on ANY verdict (corrected in v2).** Verifiers are
   paid for the verification work whatever the outcome — the kleinbot fix,
   live since 2026-10-23. (v1's "pay only on agreement with the quorum" line
   was superseded by that fix and is removed.) Reputation still tracks
   agreement with the quorum over time and gates which jobs a verifier gets.
   Failed verification of a job = refund minus the 10% fee pool.
7. **Public receipts.** Every verification attempt — including REFUSED and
   VOID — generates a structured, signed receipt (schema below), stays public
   on the board, and is replayable by anyone. Receipts are hash-chained and
   externally anchored (mesh ledger) so later local modification is
   detectable.

## Mandatory checks on every attempt (v2)

1. **Residual calculation.** Stored population counts are compared against
   independently retrieved records; the counts and their difference go on
   the receipt.
2. **Precondition freshness.** When preconditions were established is
   recorded, with an expiry. Stale preconditions invalidate the attempt
   (VOID); a replayed expired verification is rejected.
3. **Independent controls.** Each attempt runs control records from outside
   the tested population, with a known expected result. A failing control
   means the instrument cannot be trusted for this attempt.
4. **Instrument independence.** Two witnesses are required with meaningfully
   different failure modes. Independence is *assessed* (operator,
   implementation, data source, infrastructure), not merely declared —
   two instances of the same stack on the same operator are one witness
   for independence purposes, and the receipt says so.
5. **Blind deterministic re-execution** (rule 1).
6. **Seal-before-comparison** (rule 3).
7. **Conflict resolution.** Unresolved results are preserved as VOID until
   an independent third placement establishes a 2-of-3 quorum.

## Receipt schema (v2): ASIN-HHC-VERIFICATION-1.0

Every attempt emits one receipt. All fields carry actual measured values or
explicit null/unknown states — never placeholder values presented as results.

    {
      "schema": "ASIN-HHC-VERIFICATION-1.0",
      "verification_id": "UUID",
      "test_id": "STRING",
      "test_version": "STRING",
      "population_id": "STRING",
      "snapshot_hash": "SHA256",
      "residual": { "stored_count": 0, "served_count": 0, "difference": 0 },
      "control": {
        "control_id": "STRING",
        "source": "EXTERNAL_TO_TEST_POPULATION",
        "result": "PASS"
      },
      "preconditions": {
        "established_at": "ISO-8601",
        "expires_at": "ISO-8601",
        "valid": true
      },
      "witnesses": [],
      "instrument_independence": { "declared": false, "review_status": "PENDING" },
      "outcome": "REFUSED",
      "reason": "NO_DISCRIMINATING_CONDITION",
      "receipt_hash": "SHA256",
      "external_anchor": null
    }

Signing authority: the Agent Vault (live v1, 2026-11-11) signs receipts under
its policy; the receipt hash is anchored on the mesh ledger
(`external_anchor` carries the ledger sequence + anchor receipt once placed).

## Adversarial test suite (v2)

Expected behavior is specified BEFORE each test executes:

- Zero residual with no discriminating control → REFUSED.
- Stale preconditions → VOID (verification invalid).
- Control failure → REFUSED (instrument untrusted; reason CONTROL_FAILURE).
- Identical failure modes between witnesses → REFUSED
  (NO_INDEPENDENT_WITNESS — independence not established).
- Conflicting independent results → VOID; third placement resolves to
  PASS or FAIL by quorum.
- Modified evidence after sealing → FAIL (seal mismatch; tamper on receipt).
- Replay of an expired verification → rejected.
- Manipulated population counts → residual ≠ 0 → FAIL.
- Missing witness signatures → witness invalid; if fewer than two valid
  witnesses remain → REFUSED.
- Failed third-placement resolution → remains VOID.

## Acceptance criteria (v2)

- All four outcomes represented explicitly in code and receipts.
- REFUSED cannot accidentally become PASS.
- Stale preconditions invalidate verification.
- Controls demonstrably external to the tested population.
- Witness independence assessed, not merely declared.
- Conflicting witnesses remain VOID until resolved.
- Receipt integrity independently verifiable (hash + vault signature).
- External anchoring detects subsequent local receipt modification.
- Adversarial tests demonstrate the expected behavior above.
- CI reproduces the results.

## Evidence boundary (v2)

A passing test demonstrates only the specific property tested under its
recorded conditions. Deterministic re-execution does not automatically
establish independent verification: shared implementations, dependencies,
data sources and infrastructure can create correlated failures. A quorum is
meaningful only when witness independence and placement integrity are
established. No claim of production-grade security or independent
verification is made solely because our own tests pass. Settlement to date
is Base Sepolia TESTNET and is always labeled as such.

## Integration targets (v2)

| Component        | Responsibility                              |
|------------------|---------------------------------------------|
| Holbrook-CP8-HHC | Coordination and provenance                 |
| HOS Runtime      | Canonical packets and signed receipts       |
| DAR-P            | Verification outcomes and evidence gates    |
| GPU Mesh         | Independent checker execution               |
| Agent Vault      | Signing authority and policy enforcement    |

No competing verification framework: this gate extends the existing
architecture.

## Split

- Hub-side (GrokAce — he owns the hub code): deterministic job params, quorum
  counting, reputation tracking, payout gating.
- Node-side (Ace): the gate itself — outcome state machine, mandatory checks,
  receipt emission/signing/anchoring, deterministic execution flags,
  verifier-duty mode for the node.

## Live proof so far

- muse-checker (node_5c320db4a517) registered 2026-11-07, payout
  0x2D49700fc13B5BAFBF789a7d09c799a858b8B423.
- Verification 1: job_15c06d933b6a (parent job_faeec6a7ebda), receipt seq 8,
  verdict disagree_sampling, 2 credits on hold.
- Verification 2: job_045c2c24bb0d, receipt seq 11, verdict disagree_sampling,
  2 credits on hold.
- First settlement under the two-checker rule: batch-001 parent
  job_38ad69a042f5, verified by muse-checker + the GitHub Actions checker
  (independent machines, exact output-hash match), settled on Base Sepolia
  testnet, tx 0x3195dd5692aa622e62471e0b68667b83d9d029d7f8daa34585e905244810014d,
  block 56211684, 20,000 testnet HHCW split 90/5/5.
- Agent Vault v1 live 2026-11-11 (signing under policy, hash-chained
  receipts, chain head anchored at mesh ledger seq 545).
- Verification gate v1 IMPLEMENTED 2026-11-11 (gate.py in this
  directory): four-outcome state machine, all mandatory checks,
  ASIN-HHC-VERIFICATION-1.0 receipts signed via the Agent Vault.
  Adversarial suite 14/14 PASS (independently re-run). First live run
  (attempt live-2026-11-11-mesh-ledger-003): residual 0, external
  control PASS, outcome REFUSED / NO_INDEPENDENT_WITNESS — both
  witnesses were Ace-operated, so no PASS was claimable. Receipt
  7d91fa1a… anchored at mesh seq 548, read back verified. Detail:
  live-run/README.md. A live PASS still needs a second-operator
  witness.
