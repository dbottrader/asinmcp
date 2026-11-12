# ASIN-HHC — Verification Gate Specification (PROPOSAL — filed, not adopted)

Received: Dennis pasted this into the main chat 2026-11-11 20:52 CST with no
framing or instruction. Provenance unconfirmed (his own draft or another
seat's). Filed verbatim per the relayed-content rule; scope decision is
Dennis's. Status on the document itself: "Proposed specification."

Relation to the existing design (~/workspace/verifier-bot/SPEC.md, v1,
2026-11-07): overlaps on deterministic re-execution, seal-before-comparison,
2-of-3 quorum, public receipts. Genuinely new: the four-outcome state machine
(PASS / FAIL / VOID / REFUSED), precondition freshness/expiry, independent
controls outside the tested population, witness independence assessed by
failure mode (not just distinct machines), the canonical
ASIN-HHC-VERIFICATION-1.0 receipt schema, and the adversarial test suite.

---

ASIN-HHC — Verification Gate Specification

Proposal: Refusal-Aware, Independent Verification

Status: Proposed specification
Purpose: Integrate into the existing HOS / DAR-P verification architecture.

1. Core Principle

A verification system must be capable of refusing to produce a result.

A test that cannot fail is not evidence. A test that cannot distinguish competing hypotheses must not report verification.

The system must distinguish between:

- A claim supported by independent evidence.
- A claim contradicted by valid evidence.
- Conflicting evidence.
- Insufficient conditions to evaluate the claim.

2. Four Verification Outcomes

Status| Meaning| Required action
PASS| Independent verification agrees| Accept result
FAIL| Valid evidence contradicts claim| Reject result
VOID| Witnesses conflict or preconditions are invalid| Request another independent placement
REFUSED| No discriminating condition exists| Produce no verification claim

These states must never be collapsed into a generic success/failure boolean.

3. Mandatory Verification Checks

Every verification attempt must evaluate:

1. Residual calculation: Compare stored population counts against independently retrieved records.
2. Precondition freshness: Record when preconditions were established and expire stale conditions.
3. Independent controls: Use control records outside the tested population.
4. Instrument independence: Require two witnesses with meaningfully different failure modes.
5. Blind deterministic re-execution: Reproduce the computation without relying on the original solver's claimed result.
6. Seal-before-comparison: Cryptographically seal outputs before comparing them.
7. Conflict resolution: Preserve unresolved results until an independent third placement establishes a 2-of-3 quorum.

4. Required Receipt Schema

Every verification attempt must generate a structured, signed receipt.

{
  "schema": "ASIN-HHC-VERIFICATION-1.0",
  "verification_id": "UUID",
  "test_id": "STRING",
  "test_version": "STRING",
  "population_id": "STRING",
  "snapshot_hash": "SHA256",
  "residual": {
    "stored_count": 0,
    "served_count": 0,
    "difference": 0
  },
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
  "instrument_independence": {
    "declared": false,
    "review_status": "PENDING"
  },
  "outcome": "REFUSED",
  "reason": "NO_DISCRIMINATING_CONDITION",
  "receipt_hash": "SHA256",
  "external_anchor": null
}

All fields must contain actual measured values or explicit null/unknown states. Example values above are schema placeholders, not test results.

5. Adversarial Test Suite

The implementation must demonstrate correct behavior under:

- Zero residual with no discriminating control.
- Stale preconditions.
- Control failure.
- Identical failure modes between witnesses.
- Conflicting independent results.
- Modified evidence after sealing.
- Replay of an expired verification.
- Manipulated population counts.
- Missing witness signatures.
- Failed third-placement resolution.

Expected behavior must be specified before each test executes.

6. Integration Targets

Integrate into existing repositories and modules:

Component| Responsibility
Holbrook-CP8-HHC| Coordination and provenance
HOS Runtime| Canonical packets and signed receipts
DAR-P| Verification outcomes and evidence gates
GPU Mesh| Independent checker execution
Agent Vault| Signing authority and policy enforcement

Do not create a competing verification framework.

7. Acceptance Criteria

The implementation is not considered complete until:

- All four outcomes are represented explicitly.
- REFUSED cannot accidentally become PASS.
- Stale preconditions invalidate verification.
- Controls are demonstrably external to the tested population.
- Witness independence is assessed rather than merely declared.
- Conflicting witnesses remain VOID until resolved.
- Receipt integrity is independently verifiable.
- External anchoring can detect subsequent local receipt modification.
- Adversarial tests demonstrate expected behavior.
- CI reproduces the results.

8. Evidence Boundary

A passing test demonstrates only the specific property tested under its recorded conditions.

Deterministic re-execution does not automatically establish independent verification. Shared implementations, dependencies, data sources and infrastructure can create correlated failures.

A quorum is meaningful only when witness independence and placement integrity are established.

No implementation should claim production-grade security or independent verification solely because its own tests pass.

9. Engineering Directive

Implement the refusal-aware verification gate within the existing ASIN-HHC architecture.

Prioritize:

1. Formal outcome state machine.
2. Canonical receipt schema.
3. Precondition expiration.
4. Independent control validation.
5. Witness independence assessment.
6. Adversarial test suite.
7. External receipt anchoring.
8. CI integration.

Governing principle:

A trustworthy verifier must be able to demonstrate that a claim is true, demonstrate that it is false, identify unresolved contradictions, and explicitly refuse to claim knowledge when the evidence cannot distinguish the alternatives.

No evidence, no PASS. No independent witness, no independent verification. No discriminating condition, REFUSED.
