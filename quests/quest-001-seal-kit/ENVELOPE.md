# Quest 001 seal-drop envelope - exact format

Every rule below is read from the code that is deployed as the Supabase edge function `quest-evidence` (project `ecenvlwyenpakrxfuqup`). The deployed `index.ts` and `core.ts` were compared byte for byte with branch `feat/quest001-functional` at `97c80b9` on Mon Nov 23, 2026 at 2:00 AM CT and are identical. Those files and `QUEST-001-SPEC.md` did not change between `787ad43` and `97c80b9`, so either commit gives the same line numbers.

Short names used below:

- `core.ts` = [`quest001/supabase/functions/quest-evidence/core.ts`](https://github.com/dbottrader/asinmcp/blob/97c80b9e6ec402b24e02234873f13fdc9f850cd8/quest001/supabase/functions/quest-evidence/core.ts)
- `index.ts` = [`quest001/supabase/functions/quest-evidence/index.ts`](https://github.com/dbottrader/asinmcp/blob/97c80b9e6ec402b24e02234873f13fdc9f850cd8/quest001/supabase/functions/quest-evidence/index.ts)
- `SPEC` = [`quest001/QUEST-001-SPEC.md`](https://github.com/dbottrader/asinmcp/blob/97c80b9e6ec402b24e02234873f13fdc9f850cd8/quest001/QUEST-001-SPEC.md)
- `manifest.json` = [`quest001/manifest.json`](https://github.com/dbottrader/asinmcp/blob/97c80b9e6ec402b24e02234873f13fdc9f850cd8/quest001/manifest.json) (v2, sha256 `422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa`)

## 1. Endpoints

Base: `https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence` (index.ts:122-123 strips everything up to `/api/v1/evidence`).

| Method | Path | What it returns | Code |
|---|---|---|---|
| GET | `/` | list of quests with manifest hash and deadline | index.ts:130-133 |
| GET | `/quest-001/manifest` | exact manifest bytes, header `X-Manifest-SHA256` | index.ts:138-143 |
| POST | `/seal-drop` | submit one envelope (POST only, else 405) | index.ts:125-128, 67-117 |
| GET | `/quest-001` | public seals, the append-only chronicle, chain check (the "chronicle" route) | index.ts:145-150 |
| GET | `/quest-001/verdict` | verdict recomputed from stored seals | index.ts:151-152 |
| GET | `/quest-001/replay` | server-side re-check of chain, envelope hashes and verdict | index.ts:153-170 |

Use `quest-001-test` in place of `quest-001` for the test quest `QUEST-001-TEST` (no reward). The quest id in the URL is upper-cased to find the quest (index.ts:31, 136). No auth header is needed (the function is deployed with `verify_jwt: false`), and CORS allows any origin (index.ts:21-25).

## 2. Two canonical forms

| Name in this kit | Used for | Rule | Code |
|---|---|---|---|
| `canon-pyjson-v1` (index chain form) | each provenance-index entry hash | Python `json.dumps(entry_without_index_hash, sort_keys=True, ensure_ascii=False)` with the **default** separators `", "` and `": "` | core.ts:69-77 (`pyDumpsDefault`), core.ts:105-107; SPEC lines 38-42 |
| `canonical_json` (gate.py form) | `sealed_output`, `envelope_signature`, envelope and chronicle hashes | `json.dumps(o, sort_keys=True, separators=(",",":"), ensure_ascii=False)`, UTF-8, integers only, no trailing newline | core.ts:59-67 (`canonicalJson`), core.ts:42-57; SPEC lines 32-37 |

`canon-pyjson-v1` is the label this kit and the ASIN-HHC check records use. The service code does not use that name; it calls the function `pyDumpsDefault`. Keys sort by code point (core.ts:37-40). Floats and integers beyond 2^53 - 1 are refused (core.ts:47). `seal(o) = sha256(canonical_json(o))` as lowercase hex (core.ts:79).

## 3. Recomputing the claim

From core.ts:94-125 (`computeEvidence`) and SPEC lines 49-63:

1. Fetch the manifest, `manifest_sha256 = sha256(exact bytes)`.
2. Fetch `manifest.claim.url` (`https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json`). Stop if `sha256(body) != claim.sha256` (`a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e`) or `len(body) != claim.bytes` (87505).
3. `.entries` must be a non-empty array of objects (core.ts:96-97, 103).
4. `prev = .ledger_anchor.tip_hash` (core.ts:98-99). For each entry: its `prev_index_hash` must equal `prev` (core.ts:104); `h = sha256(canon-pyjson-v1(entry minus index_hash))` must equal its `index_hash` (core.ts:105-108); then `prev = h` (core.ts:109).
5. `output = {"count": len(entries), "head_hash": prev}` (core.ts:111). The file's declared `entry_count` and `head_hash` must match (core.ts:112-113).
6. `sealed_output = seal(output)` (core.ts:116).
7. `observed = {"claim_sha256", "claim_bytes", "first_entry_seal": seal(entries[0])}` (core.ts:117-121).

The index declares 78 entries and head `fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6`. A sealer must re-derive both; `seal_quest001.py` refuses to seal if its own recompute disagrees with the file in any way.

## 4. Envelope fields

Exactly these 17 keys, no more and no fewer (core.ts:12-17, 158-159). Schema `ASIN-HHC-QUEST-SEAL-1.0` (core.ts:7, 160).

| Field | Type and rule | Code |
|---|---|---|
| `schema` | `"ASIN-HHC-QUEST-SEAL-1.0"` | core.ts:160 |
| `quest_id` | `"QUEST-001"` (or `"QUEST-001-TEST"`) | core.ts:161-162 |
| `manifest_sha256` | 64 lowercase hex, must equal the current manifest hash | core.ts:163-164 |
| `request_id` | lowercase UUID, fresh per submission | core.ts:178 |
| `nonce` | 64 lowercase hex (32 random bytes), never reused on any quest | core.ts:165-166; index.ts:108 |
| `issued_at` | ISO-8601 with seconds and `Z` or `+hh:mm` | core.ts:142-147, 185-186 |
| `expires_at` | same format | core.ts:185-186 |
| `key_id` | sha256 of the 32 raw public-key bytes, 64 hex | core.ts:183 |
| `pubkey` | Ed25519 public key, 64 lowercase hex | core.ts:165-166 |
| `operator` | 1-80 printable chars, not on `independence.ineligible_operators` after normalizing (lowercase, a-z0-9 only) | core.ts:179, 81-83, 195-197 |
| `failure_mode` | 1-400 printable chars: how this witness could be wrong | core.ts:180 |
| `implementation` | 1-400 printable chars: software, version, host type | core.ts:181 |
| `output` | exactly `{"count": int >= 0, "head_hash": 64 hex}` | core.ts:168-172 |
| `sealed_output` | `seal(output)`, 64 hex | core.ts:165-166, 182 |
| `observed` | exactly `{"claim_sha256": 64 hex, "claim_bytes": int, "first_entry_seal": 64 hex}` | core.ts:173-177 |
| `signature` | Ed25519, 128 lowercase hex, over the UTF-8 bytes of the `sealed_output` hex string | core.ts:199 |
| `envelope_signature` | Ed25519, 128 lowercase hex, over `canonical_json` of the 15 fields above (everything except the two signatures) | core.ts:200-204 |

Signing payloads, precisely:

```text
signature          = Ed25519_sign(seed, utf8(sealed_output))                       # 64 ASCII bytes
envelope_signature = Ed25519_sign(seed, canonical_json({k: env[k] for k in SIGNED}))
SIGNED = [schema, quest_id, manifest_sha256, request_id, nonce, issued_at, expires_at,
          key_id, pubkey, operator, failure_mode, implementation, output, sealed_output, observed]
```

The service verifies with `@noble/ed25519@2.1.0` (index.ts:6, 17-19). The body must be at most 16 KiB (index.ts:69).

Time window (core.ts:187-193): `now <= deadline`; `issued_at <= now + 5 min` (core.ts:11); `issued_at >= valid_from` (`2026-11-14T15:00:00Z`); `issued_at < expires_at`; `expires_at > now`; `expires_at <= deadline`. The QUEST-001 deadline is `2026-11-26T23:59:00-06:00`, Thu Nov 26, 2026, 11:59 PM CT (manifest.json:8).

## 5. Submitting

```bash
curl -sS -X POST -H 'Content-Type: application/json' --data @envelope.json \
  https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/seal-drop
```

or `python3 seal_quest001.py --submit ...`, which does the same POST.

## 6. Response codes

Checks run in this order; the first failure wins (core.ts:157-204, index.ts:67-117). Every rejection says `"accepted": false` and `"state_changed": false`.

| HTTP | `code` | Meaning | Code |
|---|---|---|---|
| 201 | (`accepted: true`) | written to the chronicle together with the seal; body has `envelope_sha256`, the `chronicle` record and `receipt`. Acceptance is not a verdict and pays nothing. | index.ts:99-103 |
| 413 | `too_large` | over 16 KiB | index.ts:69 |
| 400 | `bad_json` | body is not a JSON object | index.ts:71; core.ts:157 |
| 400 | `missing_field` / `unknown_field` | not exactly the 17 keys | core.ts:158-159 |
| 400 | `bad_schema` | wrong `schema` | core.ts:160 |
| 404 | `unknown_quest` | quest id not registered | core.ts:161-162 |
| 409 | `wrong_manifest` | `manifest_sha256` is not the current manifest | core.ts:164 |
| 422 | `bad_hash_format` | a hash, key or signature is not lowercase hex of the right length | core.ts:163, 165-166, 172, 176 |
| 422 | `bad_output` / `bad_observed` | wrong keys or types | core.ts:169-177 |
| 422 | `bad_request_id` / `bad_operator` / `bad_failure_mode` / `bad_implementation` | format | core.ts:178-181 |
| 422 | `seal_mismatch` | `sealed_output != seal(output)` | core.ts:182 |
| 422 | `bad_key_id` | `key_id != sha256(pubkey bytes)` | core.ts:183 |
| 422 | `bad_timestamp` | timestamp format | core.ts:186 |
| 410 | `quest_closed` | the deadline has passed | core.ts:188 |
| 422 | `issued_in_future` / `issued_before_window` / `bad_window` / `expired` | time window | core.ts:189-193 |
| 422 | `operator_ineligible` | operator on the ineligible list | core.ts:195-197 |
| 422 | `bad_signature` | either signature fails | core.ts:199, 204 |
| 422 | `bad_envelope` | signed fields cannot be canonicalized | core.ts:203 |
| 409 | `replayed_nonce` / `duplicate_request_id` / `duplicate_key` / `duplicate_operator` | already used for this quest (nonce: any quest) | index.ts:107-113 |
| 500 | `db_error` | database problem | index.ts:83, 114 |
| 503 | `chain_busy` | three chain conflicts in a row, retry | index.ts:116 |

Intake does not compare your answer with the expected one (SPEC lines 115-116). A wrong but correctly signed seal is accepted and then counts against the claim in the verdict. That is why `seal_quest001.py` refuses to seal when its own recompute fails.

## 7. Checking the result

- Chronicle: `GET .../quest-001`. Your seal appears in `seals` and as a `seal_accepted` record whose `payload.envelope_sha256` equals the `envelope_sha256` you got back (index.ts:76-80, 145-150). `chain.ok` must be `true`. Each record's `record_hash = seal({quest_id, seq, event, payload, prev_hash, created_at})` and seq 0 links to 64 zeros (core.ts:213-229).
- Verdict: `GET .../quest-001/verdict` (core.ts:236-306). `HOLD` until two valid seals exist; `PASS` with reason `TWO_INDEPENDENT_MATCHING_SEALS` when two independent seals match the service's own re-execution and none disagree; `VOID` (`WITNESS_CONFLICT`) when independent seals disagree; `FAIL` when an independent pair agrees on a different answer. Independent means different normalized operator, different pubkey and different normalized `failure_mode` (core.ts:254-256). The service's own answer is withheld until two valid seals exist (core.ts:253, 293-297). Every verdict carries `settlement_state: "awaiting_human_authorization"` and `automatic_payment: false` (core.ts:302-303).
- Replay: `GET .../quest-001/replay` must show `replay_ok: true` (index.ts:153-170).
