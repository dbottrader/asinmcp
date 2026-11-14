# QUEST-001 "Seal the Index" — Canonical Witness Specification v1

Status: LIVE intake, verdict computed by machine, **settlement manual only**.
Rule: Reality retains veto. No receipt = no promotion. No self-grading.

This document is normative. Where the old cold hand-off, the old
`verify_quest001.sh`, or any dashboard disagrees with it, this document wins.

## 1. The claim

| Item | Value |
|---|---|
| Claim URL | `https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json` |
| Claim file SHA-256 / size | published in the manifest (`claim.sha256`, `claim.bytes`) |
| Manifest | `GET https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001/manifest` (byte-identical copy: `quest001/manifest.json`) |
| Deadline | `2026-11-19T23:59:00-06:00` = `2026-11-20T05:59:00Z` = Unix `1795154340` |

The claim is the index's own declaration that it holds `entry_count` entries
whose hash chain ends at `head_hash`. A witness re-derives both values from
the bytes; it never copies them from the file's header fields, from the
manifest, or from another witness.

`demo.asin-hhc.com` does not exist and is not part of this quest. Earlier
figures such as "6,848 entries" and the head hash beginning `63b5160e` do not
describe this claim.

## 2. Exact bytes (the newline rule)

All hashes are lowercase hex SHA-256, 64 characters, never truncated.

* **Claim file hash** — SHA-256 over the exact HTTP response body bytes.
* **Canonical JSON** (gate.py `canonical_json`) — keys sorted by code point,
  separators `,` and `:` with no spaces, UTF-8, non-ASCII characters emitted
  raw (not `\uXXXX`-escaped), integers only, **no trailing newline**.
  Python: `json.dumps(o, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()`;
  jq: `jq -j -c -S` (note `-j`, not `-r`).
* **Seal** — `seal(o) = sha256(canonical_json(o))`.
* **Index chain rule** (inherited from `artifacts/specs/verify_index.py`) —
  for each entry, `sha256(json.dumps(entry_without_index_hash, sort_keys=True, ensure_ascii=False).encode())`
  using Python's **default** separators `", "` and `": "`. Entry 0's
  `prev_index_hash` must equal `.ledger_anchor.tip_hash`; each later entry's
  `prev_index_hash` must equal the previous recomputed hash.

`jq -r` appends `\n` to its output. Hashing `jq -r` output hashes one extra
byte (`0x0a`) and produces a different, wrong digest. Two honest witnesses
using `-r` vs `-j` would disagree; this spec makes `-j`/exact bytes mandatory.
`tests/fixtures/` pins both digests so the pitfall is detectable.

## 3. Witness procedure

1. Fetch the manifest; record `manifest_sha256 = sha256(exact manifest bytes)`.
2. Fetch the claim URL yourself (`curl -fsSL` or equivalent; no caches, no
   copies from other witnesses). If `sha256(body) != claim.sha256` or
   `len(body) != claim.bytes`, stop: the claim changed, do not seal.
3. Parse as UTF-8 JSON. `.entries` must be a non-empty array of objects
   (null/missing is an error, not zero).
4. `count = len(.entries)`.
5. Walk the chain (§2) from `.ledger_anchor.tip_hash`; `head_hash` = the
   last recomputed entry hash. Use the recomputed value even if a link breaks.
6. `output = {"count": count, "head_hash": head_hash}` — exactly these two keys.
7. `sealed_output = seal(output)`.
8. Also record `observed = {"claim_sha256", "claim_bytes", "first_entry_seal"}`
   where `first_entry_seal = seal(.entries[0])`.

Reference implementations (they must, and do, agree): `verify_quest001.py`
(stdlib; Ed25519 via `cryptography` or the vendored RFC 8032 `ed25519.py`)
and `verify_quest001.sh` (bash + curl + jq + python3 stdlib).

## 4. Proof-of-Possession envelope (schema `ASIN-HHC-QUEST-SEAL-1.0`)

```json
{
  "schema": "ASIN-HHC-QUEST-SEAL-1.0",
  "quest_id": "QUEST-001",
  "manifest_sha256": "<64 hex>",
  "request_id": "<lowercase UUID, fresh per submission>",
  "nonce": "<64 hex, 32 random bytes, never reused>",
  "issued_at": "<ISO-8601 with offset>",
  "expires_at": "<ISO-8601 with offset, <= deadline>",
  "key_id": "<sha256 of the 32 raw Ed25519 public-key bytes, 64 hex>",
  "pubkey": "<Ed25519 public key, 64 hex>",
  "operator": "<who runs this witness; 1-80 printable chars>",
  "failure_mode": "<how this witness could be wrong: tooling, network path, data source; 1-400 chars>",
  "implementation": "<software + version + host type; 1-400 chars>",
  "output": {"count": 0, "head_hash": "<64 hex>"},
  "sealed_output": "<seal(output)>",
  "observed": {"claim_sha256": "<64 hex>", "claim_bytes": 0, "first_entry_seal": "<64 hex>"},
  "signature": "<Ed25519 over the UTF-8 bytes of the sealed_output hex string, 128 hex>",
  "envelope_signature": "<Ed25519 over canonical_json(all fields above except the two signatures), 128 hex>"
}
```

`signature` is the gate.py witness signature (same as `verifier-bot/gate.py`
`build_witness`). `envelope_signature` binds the quest, manifest, nonce,
timing and identity fields so a captured seal cannot be replayed under a new
nonce or quest. No other fields are allowed.

`verify_quest001.py seal --key K --manifest M --operator O --failure-mode F`
builds and signs this envelope; `keygen` makes a fresh key. Use a key created
for this quest only.

## 5. Intake rules (`POST .../api/v1/evidence/seal-drop`)

A seal is rejected with **no state change** unless all hold:
quest exists and is open; `manifest_sha256` matches; every hash field is 64
lowercase hex (signatures 128); `output` has exactly `count`,`head_hash`;
`sealed_output == seal(output)`; `key_id == sha256(pubkey)`;
`valid_from <= issued_at <= now + 5 min`; `now < expires_at <= deadline`;
operator not on the manifest's `ineligible_operators` list; both Ed25519
signatures verify; nonce, request_id, pubkey and normalized operator
(lowercase, alphanumerics only) are each unused for this quest (nonces are
unique across all quests). Accepted seals are written together with an
append-only chronicle record in one transaction.

Intake does **not** compare a seal with the expected answer. Wrong-but-honest
seals are accepted and then counted against the claim in the verdict.

## 6. Verdict (`GET .../api/v1/evidence/quest-001/verdict`)

Recomputed on every request from stored envelopes plus the service's own
re-execution of the claim (fetch, check `claim.sha256`, §3 steps 3-7):

* re-execution impossible (claim unreachable or changed) → **HOLD**
* fewer than 2 valid seals → **HOLD** `INSUFFICIENT_VALID_WITNESSES`
* an independent pair matching the re-execution, and no independent valid
  seal disagreeing → **PASS**
* matching and disagreeing independent seals both present → **VOID** `WITNESS_CONFLICT`
* an independent pair agreeing with each other but not with the
  re-execution → **FAIL**
* otherwise → **HOLD** `NO_INDEPENDENT_PAIR`

Independent = different normalized operator **and** different public key
**and** different normalized `failure_mode` (gate.py rule plus key
distinctness). Operators are self-declared: before settlement a human must
confirm that Alpha and Beta are genuinely separate operators, hosts and
credentials. GrokAce (coordinator) and the index publisher are ineligible;
their seals are refused at intake and never count.

Every verdict carries `settlement_state: "awaiting_human_authorization"`
and `automatic_payment: false`, plus `verdict_hash = seal(verdict body)`.

## 7. Reward and settlement

10 HHC total, split 50/50: **5 HHC to each of the two matching independent
verifiers** (Alpha = the earlier accepted seal of the passing pair, Beta = the
later). The funded escrows are `esc_0e020c419a0b` (6.0 HHC) and
`esc_6cb8dcae818c` (4.0 HHC); they are reconciled to 5 + 5 at settlement.
Settlement is performed by hand only after Dennis Christie inspects the
verdict, the chronicle replay and the operators' independence, and
authorizes it. No code path in this quest moves HHC.

## 8. Chronicle and replay

Each quest has its own append-only chain in `quest_chronicle`:
`record_hash = seal({quest_id, seq, event, payload, prev_hash, created_at})`,
`prev_hash` of seq 0 = 64 zeros. Updates and deletes are blocked by trigger.
`GET .../quest-001` returns seals and chronicle; `GET .../quest-001/replay`
re-verifies the chain and verdict server-side; `replay_quest001.py`
re-verifies both from the public JSON with no trust in the service.
Test traffic uses the separate quest id `QUEST-001-TEST` (`is_test: true`)
and never touches the QUEST-001 chain.
