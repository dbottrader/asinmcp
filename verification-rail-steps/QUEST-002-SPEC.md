# QUEST-002 — the verification-round quest type (SPEC)

*Elite-50 task 6 · Verification-rail build-order step 3
(`~/workspace/makefun-port/BLUEPRINT.md`). SPEC ONLY — nothing is
deployed, no endpoint code changes, no quest is registered by this
document. Sources: BLUEPRINT.md §§(a)–(c) + build order step 3;
ENVELOPE-SPEC.md (vault envelope, for the gate-receipt claim type);
the Quest 001 manifest (`ASIN-HHC-QUEST-MANIFEST-1.0`) and the PR #4
quest-evidence candidate (core.ts / index.ts) whose routes and rules
this type composes with.*

## 0. What a verification-round quest is

Quest 001's work product was a *recomputation*: witnesses re-executed
one pinned claim (the 78-entry provenance index) and sealed what they
got. QUEST-002 generalizes the shape into a reusable quest **type**:

> **A verification-round quest's work product is an independent
> verification round over an existing claim set.** The claim set is
> published first (by anyone — us, a bounty platform, a third party).
> Operators independently replay it and file **signed verdict
> envelopes**: MATCH (my replay reproduces the claim) or REFUSAL
> (it does not, and here is the field that differs). The round
> settles on the two-seal rule, and either outcome is public and
> receipted — a refusal is a published result, not a failed quest.

This is the rail the blueprint describes: the bounty runs wherever it
runs; the round is the part no house can sell about itself — a
referee it does not operate. The Proof Board already carries the
first instance's funding call (QUEST-002 row: `POOL_OPEN`, 25 HHC
pool threshold, "opens when funded"); this spec is the type that
gets instantiated when a pool funds.

Two round kinds are defined, differing in what the service itself
can re-execute:

- **`replay-index`** — the claim is a hash-chained artifact (index,
  ledger snapshot, receipt chain). The service re-executes exactly
  as in Quest 001 (`computeEvidence`). Full service-side oracle.
- **`replay-result`** — the claim is a *result bundle* for a
  deterministic code quest: {spec, submission, claimed result}, each
  hash-pinned in the manifest. The service re-executes the bundle's
  hash bindings and internal consistency (it does not run foreign
  code — see §7's honest limit); the operators' replays run the
  published grader (blueprint deliverable 2, `grade_quest.py`) and
  their envelopes carry the grader receipt hash as evidence. The
  two-seal agreement over the same recomputed result is the oracle,
  exactly as the blueprint specifies.

## 1. Schemas

| Object | Schema | Notes |
|---|---|---|
| Quest manifest | `ASIN-HHC-QUEST-MANIFEST-1.0` (extended) | Adds `quest_type`, `round`, `claim_bundle` (§2). Same top-level shape as Quest 001's manifest, so the existing registration path (`quest_manifests` row: quest_id, manifest text, manifest_sha256, valid_from, deadline, is_test) is unchanged |
| Verdict envelope | `ASIN-HHC-QUEST-SEAL-2.0` (new) | §3. The 1.0 envelope's `output` is hard-shaped `{count, head_hash}` in the candidate's validator, so a round envelope needs its own schema version; the signing construction is inherited unchanged |
| Verdict | `ASIN-HHC-QUEST-VERDICT-1.0` (extended reasons) | §4 adds round reason codes; body shape unchanged |
| Chronicle record | unchanged | `seal_accepted` events, hash-chained per quest, as in Quest 001 |

## 2. Manifest fields

Base fields are Quest 001's, verbatim in meaning: `schema`,
`quest_id` (`QUEST-002`, then `QUEST-003`… per instance), `version`,
`title`, `valid_from`, `deadline` / `deadline_utc` / `deadline_epoch`,
`claim` {url, sha256, bytes, media_type}, `envelope_schema`
(`ASIN-HHC-QUEST-SEAL-2.0`), `signature_rules` (unchanged: Ed25519;
`signature` over the sealed_output hex string; `envelope_signature`
over canonical_json of the signed field set; `key_id` = sha256 of
the raw pubkey bytes), `independence` (§5), `reward` (§6),
`settlement` {authority, automatic_payment: false, state:
awaiting_human_authorization}, `spec` {path, sha256} pointing at
this document.

Round-specific fields:

```json
"quest_type": "verification-round",
"round": {
  "kind": "replay-index | replay-result",
  "subject": "what is being verified, in one line",
  "grader": {                      // replay-result only
    "name": "asinmolt-grade-quest", "version": "0.1.0",
    "tool_url": "…", "tool_sha256": "…"
  },
  "metric": "cases_passed",        // replay-result: the published metric
  "bar": {"value": 4, "direction": "higher"},
  "refusal_fields": ["score", "verdict", "claim_hash", "chain"]
},
"claim_bundle": {                  // replay-result only; for
  "spec":       {"url": "…", "sha256": "…", "bytes": 0},
  "submission": {"url": "…", "sha256": "…", "ref": "commit or archive id"},
  "claimed":    {"score": 4, "verdict": "PASS"}
}
```

For `replay-result`, the manifest's top-level `claim` is the
**bundle document** itself (a small JSON at `claim.url` whose
sha256/bytes are pinned as usual); the bundle names the
spec/submission/claimed hashes above, and the service's
re-execution verifies the bundle recomputes and that the files it
points at hash to the pinned values. For `replay-index`,
`claim_bundle` is omitted and `claim` is the chained artifact, as
in Quest 001.

`witness_output` is replaced by `round_output` (§3) in the spec
block of the manifest.

## 3. The verdict envelope (ASIN-HHC-QUEST-SEAL-2.0)

Signed field set = the 1.0 set with `output`/`observed` reshaped
(signing rules unchanged — both signatures, same canon):

```json
{
  "schema": "ASIN-HHC-QUEST-SEAL-2.0",
  "quest_id": "QUEST-002",
  "manifest_sha256": "…",
  "request_id": "uuid", "nonce": "64 hex",
  "issued_at": "…", "expires_at": "… (= manifest deadline)",
  "key_id": "…", "pubkey": "…",
  "operator": "…", "failure_mode": "…", "implementation": "…",
  "output": {
    "claim_sha256": "…",          // the claim/bundle file I replayed
    "verdict": "MATCH | REFUSAL",
    "result_hash": "…",           // sha256(canonical_json(recomputed_result))
    "differing_field": null       // REFUSAL only: one of round.refusal_fields
  },
  "sealed_output": "sha256(canonical_json(output))",
  "observed": {
    "claim_sha256": "…", "claim_bytes": 0,
    "evidence_seal": "…"          // replay-index: seal(first entry);
                                  // replay-result: the grader receipt hash
  },
  "signature": "…", "envelope_signature": "…"
}
```

`recomputed_result` — what `result_hash` covers — is kind-specific:
`replay-index`: `{count, head_hash}` (Quest 001's output, so a 2.0
round over an index is directly comparable to a 1.0 seal);
`replay-result`: `{score, verdict}` as recomputed by the grader.
A MATCH envelope asserts `result_hash == the claim's result hash`
(for `replay-result`, the hash of the manifest's `claimed` object);
a REFUSAL asserts a different recomputed result and MUST name
exactly one `differing_field`.

Intake validation = the candidate's `validateEnvelope` with three
deltas: (a) schema string; (b) `output`/`observed` shapes above;
(c) a REFUSAL with `differing_field: null`, or a MATCH with a
non-null one, is `422 bad_output`. Everything else — field set
strictness, manifest binding, key_id derivation, timestamp window,
eligibility, both signature checks, DB uniqueness (one seal per
key / operator / nonce / request per quest) — is inherited
unchanged.

## 4. Verdict rules (how a round settles)

Computed by the same deterministic shape as `computeVerdict`:
an envelope is **valid** iff both signatures verify and
`seal(output) == sealed_output`. **Independence** is the existing
triple test: distinct normalized operator, distinct pubkey,
distinct normalized failure_mode — plus manifest ineligibility.
Let *agree* = valid MATCH envelopes whose `result_hash` equals the
service re-execution's; *refuse* = valid REFUSAL envelopes whose
`result_hash` + `differing_field` agree with each other.

| Outcome | Rule | Reason code |
|---|---|---|
| **PASS** | an independent pair in *agree*, and no independent MATCH/REFUSAL conflict pair | `TWO_INDEPENDENT_MATCHING_SEALS` |
| **FAIL** (round refuses the claim) | an independent pair in *refuse* (same `result_hash`, same `differing_field`), and no conflict pair | `TWO_INDEPENDENT_MATCHING_REFUSALS` (new) |
| **VOID** | an independent pair split across *agree* and *refuse* | `WITNESS_CONFLICT` |
| **HOLD** | anything else: <2 valid, no independent pair, or re-execution unavailable (incl. `CLAIM_CHANGED_SINCE_MANIFEST`) | `INSUFFICIENT_VALID_WITNESSES` / `NO_INDEPENDENT_PAIR` / re-execution reason |

As in Quest 001: the service's expected `sealed_output` is withheld
from the verdict body until ≥2 valid seals exist (no answer oracle);
`payout_plan` is emitted only on PASS (alpha = earlier accepted
matching seal, beta = later; §6); on FAIL the payout plan is empty
and the *claim* is what stands refused — the refusal, its differing
field, and both envelopes are the public record. `settlement_state`
remains `awaiting_human_authorization`, `automatic_payment: false`,
in every outcome: **the endpoint never pays**; settlement executes
on the mesh side under the settlement authority named in the
manifest.

## 5. Independence and eligibility

Inherited from Quest 001 without change: `min_witnesses: 2`;
`distinct: [operator, pubkey, failure_mode]`; per-manifest
`ineligible_operators` (coordinator/publisher-side names — for
QUEST-002: grokace, dbottrader, dennischristie, plus the claim's
author/submitter named per instance); `human_review` note
(independence is self-declared; the settlement authority confirms
separate operators/hosts/credentials before settlement). The sybil
limit is inherited verbatim and stated in the manifest, not hidden
(BLUEPRINT gap 5; self-attack S5, 2026-11-19).

## 6. Escrow shape

Mesh-side, exactly the Quest 001 pattern (the endpoint holds no
funds and moves no HHC):

```json
"reward": {
  "currency": "HHC",
  "total_hhc": 25,
  "per_verifier_hhc": 12.5,
  "split": "50/50",
  "recipients": "the two matching independent verifiers of the PASS pair: alpha (earlier accepted seal) and beta (later)",
  "funded_escrows": [{"escrow_id": "…", "funded_hhc": "…"}],
  "reconciliation": "funded escrows are reconciled to per_verifier_hhc x2 at settlement"
}
```

- One funded escrow per paid seal (Quest 001 precedent: work item +
  escrow per recipient, FUNDED before the round opens — a round
  never opens unfunded).
- On PASS: settlement = claim + verdict on each escrow (mesh
  `_adjudicate` path), paying alpha/beta.
- On FAIL (claim refused): the seals were honest work — the
  blueprint's verifier-pay rule applies: verifiers are paid for a
  refusal outcome too, from the fee pool of the *underlying work's*
  escrow where one exists; where the round is standalone (our own
  claim), a FAIL round pays the refusing pair from the round pool
  at the manifest's `refusal_pay_hhc` (template default: same
  per-verifier amount — a referee who honestly refuses is not taxed
  for refusing). This is a manifest choice, stated up front, never
  improvised at settlement.
- On VOID/HOLD at deadline: escrows stay FUNDED; settlement
  authority decides (re-run with a fresh round instance, or cancel
  → TERMINAL_REFUNDED per the mesh cancel path). No automatic
  movement, ever.

## 7. Deadline and 410 behaviour

Identical to Quest 001, enforced in the same places:

- The round's window is [`valid_from`, `deadline`]; the claim is
  frozen at registration (its sha256 is in the manifest; a changed
  claim file yields re-execution `CLAIM_CHANGED_SINCE_MANIFEST` →
  HOLD, never a PASS against a moved target).
- Envelope `expires_at` must equal-or-precede the deadline and
  follow `issued_at`; `issued_at` must be ≥ `valid_from` and ≤
  now + 5 min skew.
- **After the deadline, POST /seal-drop for the quest returns
  `410 quest_closed`** (the intake `nowMs > deadline` check), and
  GET verdict/replay keep serving the final state — the record
  stays readable after the window shuts.
- A round that reaches deadline in HOLD is closed as HOLD; a new
  round over the same claim is a new quest instance (new manifest,
  new quest_id), never a reopened one.

## 8. Composition with the existing endpoint routes

No route changes. QUEST-002 is a new row in `quest_manifests` +
its own chronicle; the existing routes serve it by quest_id:

| Route | Behaviour for a round quest |
|---|---|
| `GET /api/v1/evidence` | lists QUEST-002 alongside QUEST-001 (quest_id, manifest_sha256, deadline, is_test) |
| `GET /api/v1/evidence/quest-002` | quest state: manifest summary, seals, chronicle, chain verification |
| `GET /api/v1/evidence/quest-002/manifest` | the manifest text, `X-Manifest-SHA256` header |
| `POST /api/v1/evidence/seal-drop` | dispatches on `envelope.schema`: `ASIN-HHC-QUEST-SEAL-1.0` → existing validator; `ASIN-HHC-QUEST-SEAL-2.0` → round validator (§3). Same 16 KiB cap, same acceptance receipt shape ("Accepted into the chronicle. Acceptance is not a verdict…") |
| `GET /api/v1/evidence/quest-002/verdict` | §4 rules; body shape = `ASIN-HHC-QUEST-VERDICT-1.0` + `quest_type`, `round.kind`, and per-seal `matches_reexecution` as today |
| `GET /api/v1/evidence/quest-002/replay` | chain + envelope-hash + linkage checks, verdict computed twice and compared — unchanged |

Implementation deltas in the candidate code (for the future build,
not this spec): `validateEnvelope` gains a schema-dispatched
output/observed shape check; `computeVerdict` gains the refuse-set
and the `TWO_INDEPENDENT_MATCHING_REFUSALS` branch; `reexecute`
gains the bundle mode. Quest 001's code paths are untouched —
a 1.0 quest behaves byte-identically.

**Deployment caveat, inherited and stated plainly:** the live
endpoint runs code whose byte-identity with the PR #4 candidate is
unproven (BLUEPRINT gap 2), and per blueprint build-order step 3
the mesh side is the preferred home for new rounds until that gap
closes. This spec is written against the endpoint's published
contract (manifest + observed behaviour) so it survives either
home: on the mesh side, the same manifest, envelope, and verdict
rules map onto work items whose verdict evidence is the round
envelope, settled by `_adjudicate`'s two-seal convergence.

## 9. Worked shape — the first instance

QUEST-002 (first round instance, per the board's POOL_OPEN row):
pool threshold 25 HHC funds two escrows of 12.5; kind
`replay-result` over a named third-party deterministic result (or
`replay-index` over a named partner index); two independent
operators replay with the published grader and drop 2.0 envelopes;
verdict per §4; settlement per §6 under Dennis Christie's authority.
The announcement draft is Elite-50 task 52, held until Quest 001
closes and the pool funds.

## 10. Honest limits

1. **Service oracle strength differs by kind.** `replay-index`
   rounds are fully service-verified. `replay-result` rounds are
   verified by operator agreement over hash-pinned inputs; the
   service checks bindings, not the foreign computation (it does
   not run graders). Stated in the manifest's `round.kind`, never
   blurred.
2. **Deterministic claims only.** Non-deterministic results (live
   model calls) have nothing stable to replay (blueprint §a) and
   are out of scope for this quest type.
3. **Sybil resistance is not implemented** (§5) — two-seal
   independence is a social fact about known operators, backstopped
   by manual settlement.
4. **Transcript provenance is not certified** — a round certifies
   the result recomputes, not who produced it (blueprint §a),
   unless the submitter publishes their bundle, whose hash the
   manifest then pins.

*ASIN-HHC — third-party, independent, MIT. Can't be bought out. Can be bought from.*
