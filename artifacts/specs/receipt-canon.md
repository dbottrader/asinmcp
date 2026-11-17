# Receipt Canon — ASIN-HHC Verification Receipts, Published

- **Published:** 2026-11-17 (P1 receipt-canon publication; code-red ship).
- **Closes:** clean-room verifier gaps **G1** (index serialization), **G2**
  (gate-receipt object/formula), **G3** (witness seals).
- **Gate receipt:** `48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38`
  (`live-2026-11-12-provindex-001`), first live gate PASS, 2026-11-12.
- **Companion files (this directory):**
  - `gate-receipt-48ac1da5.json` — the full receipt object, verbatim.
  - `witness-seals-48ac1da5.json` — seal values, both witnesses, GrokAce
    witness signature + pubkey.
  - `verify-receipt-canon.py` — stdlib-only test vectors: recompute the index
    head, the receipt hash, and the seal from public data.
  - `provenance-index.json` — the 78-entry index this receipt seals.
- **Sources:** `verifier-bot/gate.py` (`receipt_hash_of`, `seal`),
  `verifier-bot/live-run/gate-ledger.jsonl` line 2 (receipt object),
  `verifier-bot/live-run/live_run_provindex.py` (GrokAce witness signature +
  pubkey), `independent-verifier/RESULTS.md` (2026-11-13 clean-room findings).

## 0. Verification record

- **2026-11-14 — fresh verification against the live public index.**
  78 entries; 78/78 prev-hash linkage; head
  `fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6` matches;
  `index_hash` recomputes 0/78 under published canon-v1 (compact separators)
  and 78/78 under Python default separators. Index file sha256
  `a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e`
  (87,505 bytes). Ledger anchor: tip
  `405606790463f4af2f401bf2770a825ce852c10c730d41b82427556d4109ed46`,
  height 479.
- **2026-11-15 — signature re-verification, ALL PASS.** Receipt hash
  recomputes from the published object; Agent Vault Ed25519 signature valid
  (via `vault.py` verify, envelope path); GrokAce witness Ed25519 signature
  valid; seal recomputed matches both witnesses.
- **2026-11-17 — pre-publication re-check.** The receipt object published
  here is byte-identical (as JSON) to the local gate-ledger record; the
  receipt hash and the seal both recompute from it.

## 1. The exact index serialization (canon-pyjson-v1)

This is the serialization the index was actually built with, now pinned for
publication. It reproduces the head hash from the live index.

**Rules:**

- Hash: SHA-256, input UTF-8 encoded, output lowercase hex.
- Canon per entry: the entry object **minus `index_hash`**, including `index`
  and `prev_index_hash`.
- Serialization: `json.dumps(canon, sort_keys=True, ensure_ascii=False)` —
  Python's **default separators `(', ', ': ')`** (a space after `:` and after
  `,`), keys sorted lexicographically (plain Python `sort_keys`), non-ASCII
  emitted as raw UTF-8 (no `\uXXXX` escapes). `.encode()` (UTF-8), then
  SHA-256 hex.
- Chain: entry 0's `prev_index_hash` is the mesh ledger tip hash published in
  the index document's `ledger_anchor.tip_hash`
  (`405606790463f4af2f401bf2770a825ce852c10c730d41b82427556d4109ed46`, height
  479). Each entry's `prev_index_hash` equals the previous entry's
  `index_hash`. Head hash = last entry's `index_hash`:
  `fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6`.

**Runnable snippet (stdlib only) — reproduces the head hash from the live
index** (also in `verify-receipt-canon.py`):

```python
import hashlib, json, urllib.request

INDEX_URL = "https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json"

with urllib.request.urlopen(INDEX_URL, timeout=30) as r:
    idx = json.load(r)

entries = idx["entries"]
prev = idx["ledger_anchor"]["tip_hash"]
assert entries[0]["prev_index_hash"] == prev, "entry 0 does not hang off the ledger tip"
for e in entries:
    assert e["prev_index_hash"] == prev, f"linkage break at entry {e['index']}"
    canon = {k: e[k] for k in sorted(e) if k != "index_hash"}
    recomputed = hashlib.sha256(
        json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert recomputed == e["index_hash"], f"index_hash mismatch at entry {e['index']}"
    prev = e["index_hash"]
assert prev == idx["head_hash"] == "fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6"
print(f"PASS: {len(entries)} entries, head {idx['head_hash']}")
```

Verified: **78/78 entries recompute, 78/78 linkage, head matches.**

## 2. The canon-v1 gap — one line

Published canon-v1 said compact separators (`,` / `:` with no spaces); the
index was actually built with Python default separators (`', '` / `': '`) —
an outsider following the published canon gets 0/78. This document corrects
the published rule to the actual build serialization (§1); it does not
rebuild the index.

## 3. Gate receipt `48ac1da5…ea38` — object and formula

### 3.1 The formula (from `verifier-bot/gate.py`, `receipt_hash_of`)

```python
def canonical_json(obj) -> bytes:
    """Canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")

def receipt_hash_of(receipt: dict) -> str:
    """sha256 of the canonical receipt excluding the receipt_hash and
    signature fields (exactly those two keys)."""
    body = {k: v for k, v in receipt.items()
            if k not in ("receipt_hash", "signature")}
    return hashlib.sha256(canonical_json(body)).hexdigest()
```

Note the two serializations are different by design and must not be
conflated: the **index** uses Python-default separators (§1,
`canon-pyjson-v1`); the **gate receipt** uses compact separators (this
section).

### 3.2 The receipt object

The full receipt object is published verbatim as
[`gate-receipt-48ac1da5.json`](gate-receipt-48ac1da5.json)
(`verification_id` `live-2026-11-12-provindex-001`). Applying §3.1 to that
object (minus `receipt_hash` and `signature`) reproduces the published hash
exactly:

```
stored:     48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38
recomputed: 48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38
match: True
```

### 3.3 What this does and does not mean — stated honestly

- The receipt hash **does recompute** from the published object. Before this
  publication it did not recompute from public data alone — that was the
  clean-room verifier's CANNOT-RECOMPUTE verdict, now closed by publishing
  the object.
- The receipt's `signature` is an Ed25519 signature by the Agent Vault over
  the `receipt_hash` bytes, verifiable against the `signer.pubkey` carried in
  the object itself. Re-verified valid 2026-11-15 (see §0).
- `instrument_independence.review_status` is `ASSESSED_INDEPENDENT` while
  `declared` is `false`: independence is self-declared metadata, assessed in
  the gate run, not proven by the receipt itself.
- `snapshot_hash` (`3cc15904…`) is the hash of the index snapshot the gate
  sealed at run time; the snapshot file itself is not published, so an
  outsider cannot re-derive it.
- The receipt's `prev_receipt_hash` chains to the prior local receipt
  (`7d91fa1a…`, mesh-ledger run 003); the chain is local
  (`gate-ledger.jsonl`), not public.

## 4. Witness seals

**Seal formula** (`gate.py`, `seal`): `sha256(canonical_json(output))`,
where `canonical_json` is sorted keys, compact separators,
`ensure_ascii=False`, UTF-8. The sealed output for this run is
`{"count": 78, "head_hash":
"fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6"}`.

**Seal values (both witnesses sealed the identical output):**

| witness | operator | sealed_output | verdict |
|---|---|---|---|
| `w-ace-curl` | ace | `69616c863e4c1ad1d6508ac8b0db86435aa37bbc1cf69aeea6ebc46a28d00d22` | AGREE |
| `w-grokace-provindex` | grokace | `69616c863e4c1ad1d6508ac8b0db86435aa37bbc1cf69aeea6ebc46a28d00d22` | AGREE |

Recomputed: `sha256(canonical_json({"count": 78, "head_hash":
"fadbd275…fd85f6"}))` = `69616c86…d00d22` — matches both witnesses.
Residual 0 (78/78) is the agreement of two independent reads of the same
served index.

**GrokAce witness signature** (Ed25519 over the `sealed_output` bytes,
verified against `witness.sealed_output.encode("utf-8")`; full record in
[`witness-seals-48ac1da5.json`](witness-seals-48ac1da5.json)):

- signature:
  `4c2fae879dcf04246936c75d37c37c6c6a3e23ce79d8b4bc39126771f2f6e377a1122dfd191ecdfeae8bb9dfd660c1ff5237f5e04994f7043973e95f0fa9b201`
- pubkey:
  `0e31880c3d1560c082d3d7bcbe47e66d61297bb5e3e0664d68ebb34d3c0340c4`
- GrokAce's witness seed is fresh and held by GrokAce; only the signature
  and pubkey are published here. Ace's witness keypair was derived in-run
  from the deterministic seed `sha256(b"live-w-ace-curl-provindex")` — a test
  keypair whose seed is already in the repo, not a production credential.

Blind-witness character: GrokAce read blind, Ace withheld his read; the gate
solver re-executed blind a third way.

## 5. What remains unrecomputable even after this publication

- **G4 — mesh ledger anchor (seq 599).** The receipt is recorded as anchored
  on the local mesh ledger at seq 599. The mesh ledger has no public read
  endpoint, so an outsider cannot verify the anchor. Needs a public ledger
  read or published ledger snapshot.
- **G5 — ledger tip seed (height 479).** Entry 0 hangs off the published tip
  hash, but the tip itself is attested, not verifiable — the ledger snapshot
  the tip is computed over is not public. Same fix as G4.
- **G6 — 33/78 entries cite local-only files; 6 entries have no
  `file_sha256`.** Those entries' file hashes cannot be re-derived by an
  outsider; they are attested, not reproducible, until the files are
  published.
- **G7 — no integrity anchor over `proof-board.json` itself.** No hash or
  signature pins the board file anywhere public.

## 6. Honesty notes

- ASNB is an encoding, not encryption; it plays no role in this canon and
  nothing here claims otherwise.
- The index chain is internally consistent (78/78 linkage, head match) but
  contradicted its own published canon (0/78 compact). Both facts are stated
  together; neither is hidden.
- HHC is a utility credit for verified work. Nothing here is an investment
  claim, a price claim, or a promise of returns.
