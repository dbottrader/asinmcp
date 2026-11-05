# asin-hhc:receipt — adoption & validation against the live system

**Date:** 2026-11-05 (Implementation Mining, Tranche 1)
**Source schema:** corpus block `96740ac2` (`schemas/evidence-receipt.schema.json`,
draft 2020-12), extracted verbatim to
[`asin-hhc-receipt.schema.orig.json`](asin-hhc-receipt.schema.orig.json).
**Adopted schema:** [`asin-hhc-receipt.schema.json`](asin-hhc-receipt.schema.json)
— identical to the original except Adjustment A1 below.
**Validator:** [`validate_receipts.py`](validate_receipts.py) (jsonschema 4.10.3,
Draft 2020-12, format checking on). Full per-file results:
[`validation-results.json`](validation-results.json). Samples were exported
read-only from the live DB (`~/workspace/agent-mesh/mesh.db`) by
[`export_samples.py`](export_samples.py) into [`samples/`](samples/).

## Headline result

| Family | What it is | n | Pass vs original | Pass vs adopted |
|---|---|---:|---:|---:|
| A_ledger | Mesh main-ledger hash-chain entries (escrow paid/refunded/funded, transfers, verdicts, work_complete) | 50 | 0 | 0 |
| B_hhc | HHC ledger posting rows carrying a `receipt` hash | 18 | 0 | 0 |
| C_passport | Passport hash-chain events, passport_128b6bb4a882 (all 9) | 9 | 0 | 0 |
| D_sebastien | Sebastien/NeoMundi packet `receipt.json` | 1 | 0 | 0 |
| Z_synthetic | Synthetic positive control (not a real receipt) | 1 | **1** | **1** |

**Every real receipt the live system issues fails the schema — 0 of 78.**
The schema and validator are sound (both compile as valid Draft 2020-12;
the conforming positive control passes both). The failures are structural,
not incidental: the schema describes an *evidence receipt* (claim,
procedure, execution, outputs, replay), and no live emitter produces that
shape. Details per family below; the judgment calls are stated, not hidden.

Error totals (adopted schema, 78 real receipts): 684 missing-required errors
(every real receipt lacks most of the 9 required fields), 78
additionalProperties errors, 18 status-enum errors (all of family B).

## The one schema adjustment

**Adjustment A1 — optional `chain` object (schema side, clearly stale).**
The original schema sets `additionalProperties: false` and provides no place
for hash-chain metadata. But hash-chaining is the constitutive property of
every receipt in this system — canon-v1 ledger entries and Passport events
alike carry `seq` / `prev_hash` / `hash` ( / `canon`). A receipt schema for
ASIN-HHC that makes every real receipt invalid *for carrying its chain
position* is stale relative to the system's founding practice. The adopted
schema therefore adds one **optional** top-level property:

```json
"chain": { "seq": int, "prev_hash": sha256-hex, "hash": sha256-hex, "canon": string }
```

Nothing else was changed. Note honestly: A1 changes **zero** current
validation outcomes (raw live rows don't nest their chain fields under
`chain`, and they fail on missing evidence fields regardless). It exists so
that a wrapped receipt (see Adoption path) *can* be valid.

**Adjustments considered and rejected** (documented so the restraint is
visible): relaxing `additionalProperties`; accepting epoch-float timestamps
alongside date-time; adding operational statuses (`POSTED`, ledger `kind`
values) to the evidence-ladder enum. Each would have bent the schema toward
live-system habits that are the actual problem (see Live-system gaps).

## Divergences by family

### A — Mesh main-ledger entries (50 sampled of 462)
Shape: `{seq, ts, actor, kind, payload(JSON), prev_hash, hash, canon}`.

1. **No `receipt_id` / `claim_id`.** Identity is `(seq, hash)`; the claim a
   receipt speaks to (work/escrow id) is buried inside `payload`.
2. **`ts` is an epoch float** (e.g. `1793869075.18`); the schema requires an
   RFC 3339 `created_at` string. Type + field-name mismatch.
3. **No `status`.** The nearest analog, `kind` (`hhc_escrow_paid`,
   `work_complete`, …), is an operational event vocabulary, not the
   evidence ladder.
4. **No evidence structure.** `inputs` / `procedure` / `execution` /
   `outputs` / `replay` exist only as free-form content inside `payload`
   (e.g. settlement deltas). Procedure and replay instructions are not
   captured at issuance at all.
5. All 8 native fields are additional properties under the schema.

### B — HHC ledger rows (18 sampled of 202)
Shape: `{id, agent, amount, kind, work_id, escrow_id, receipt, status, created}`.

1. **`status` exists but is the wrong vocabulary**: value is `POSTED`,
   which is not in the evidence-ladder enum — all 18 status-enum errors
   come from this family.
2. **`receipt` is a bare hash string** — a pointer to the main-ledger entry,
   not a receipt object. A B row alone is a posting record, not a receipt.
3. No evidence fields at all; `created` is again an epoch float.

### C — Passport events (all 9 for passport_128b6bb4a882)
Shape: `{seq, id, passport_id, seq_in_passport, kind, actor, payload,
created, prev_hash, hash}`.

1. Structurally the closest family to a receipt (hash-chained, identified,
   payload-bearing) — and still missing all 9 required evidence fields.
2. `created` is an epoch float; `kind` (`registered`, certification kinds)
   is not the evidence ladder.
3. The evidence content the schema wants *does exist* for certification
   events — checks, evidence URLs, content hashes — but trapped inside the
   free-form `payload`, unshaped and unvalidated.

### D — Sebastien packet receipt.json (1)
The only sample that is an evidence receipt *in intent*: template hash,
engine identity + binary hashes, four run-log hashes, byte-identical
findings hashes, a verdict, and a receipt-hash formula. It still fails on
every formal axis:

1. Ad-hoc field names throughout (`receipt_hash` where the schema wants
   `outputs.result_hash`; run data under `original_runs_2026_11_05`).
2. No `receipt_id` / `claim_id` / ladder `status`; the verdict is prose
   ("PASS — template triggers on …"), not an enum.
3. No timestamps in the object (dates live in key names and prose).
4. Replay instructions exist — but in the packet's README, not the receipt.

It would need the least restructuring of any family to conform.

## Live-system gaps (stated plainly)

These are places where the live system, not the schema, is on the wrong
side — the schema was **not** bent to accommodate them:

1. **No emitter produces evidence-structured receipts.** The schema's
   `procedure`, `execution`, and `replay` content is either absent (A, B),
   trapped in free-form payloads (C), or in ad-hoc JSON (D).
2. **Epoch-float timestamps everywhere.** A published receipt format should
   carry RFC 3339 strings; emitters should render them at export.
3. **Three incompatible status vocabularies** (ledger `kind`, HHC
   `POSTED`, Passport `kind`/tier), none of them the evidence ladder.
4. **Family B's `receipt` is a hash pointer** — fine as an index, but it
   means the HHC ledger by itself cannot present a receipt.

## Adoption path (documented, not performed here)

A conforming receipt can be produced by *wrapping* a chain entry without
altering the live system: `receipt_id` = `asin-hhc:receipt:` + hash prefix;
`claim_id` from the payload's work/escrow/certification id; `status` mapped
from the terminal event kind; `created_at` rendered from `ts`; `inputs` /
`procedure` / `execution` / `outputs` lifted from the payload and the
documented protocol (mesh v0.2 escrow rules; canon-v1 chain recompute as
`replay.instructions`); and the chain position under `chain` (Adjustment
A1). Building that emitter is a follow-on task — Tranche 1 delivers the
schema, the validator, and this map.
