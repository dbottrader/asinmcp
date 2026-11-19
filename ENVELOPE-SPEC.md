# ASIN-HHC Vault Envelope Spec — how a gate receipt's signature is built and verified

*Draft, 2026-11-19. Blueprint build-order step 2
(`~/workspace/makefun-port/BLUEPRINT.md`, gap 3). Nothing in this
document was published by writing it; it is the publication candidate.
Sources of truth, all read directly for this draft:*

- *Agent Vault v1 signer: `~/workspace/agent-vault/vault.py`
  (`canon`, `envelope`, `cmd_sign`, `cmd_verify`, `cmd_init`).*
- *Gate signer adapter: `~/workspace/verifier-bot/gate.py`
  (`VaultSigner`, `canonical_json`, `receipt_hash_of`,
  `verify_receipt`).*
- *Ed25519 primitive: `~/workspace/asinmcp/ed25519.py` (pure-Python
  RFC 8032, vendored; the same module the vault and the gate import).*
- *The worked example: gate receipt
  `48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38`,
  verification_id `live-2026-11-12-provindex-001`.*

## 0. What this closes

The gate receipt's hashes have always recomputed publicly. Its
signature did not verify publicly, because the signed message is not
the receipt and not its hash — it is a **vault envelope** whose
construction existed only inside `vault.py`. This spec publishes that
construction. With it, an outsider holding nothing but a gate receipt
can verify its signature end-to-end (§7), because the receipt carries
its signer's public key inside itself (§6).

What a valid signature proves, and only this: the holder of the vault
identity key signed this receipt's hash, under the action, timestamp
and nonce in the receipt's `signature` block, at signing time.
Whether that key was *authorized* then is an out-of-band question —
the same boundary stated in the AutoGen #7609 reply of 2026-11-18.

## 1. The two layers

A signed gate receipt is two constructions stacked:

```text
gate receipt (ASIN-HHC-VERIFICATION-1.0 object)
  receipt_hash = sha256( canon_gate( receipt minus receipt_hash, signature ) )
  payload      = receipt_hash as a UTF-8 hex string          (64 bytes)
        │
        ▼   gate.py VaultSigner hands payload to the vault as a file
vault envelope (Agent Vault v1)
  payload_sha256 = sha256( payload bytes )
  envelope       = { action, payload_sha256, amount, dest, ts, nonce }
  message        = canon_vault( envelope )
  signature      = Ed25519_sign( vault identity key, message )
        │
        ▼
receipt.signature.value = signature (hex)
receipt.signer          = { kind, fingerprint, pubkey, vault_id }
```

The signature is **two hops** from the receipt: it signs the envelope;
the envelope names the hash of the payload; the payload *is* the
receipt hash. There is no direct signature over the receipt body or
over the receipt hash bytes-as-hex-decoded — the hex *string* is the
payload, and it is hashed again inside the envelope.

## 2. The two canonicalizations — they differ

Both are Python `json.dumps` with sorted keys and compact separators,
UTF-8 encoded. They differ in exactly one parameter:

| canon | used for | `ensure_ascii` |
|---|---|---|
| `canon_gate` | receipt_hash (§3) | `False` |
| `canon_vault` | vault envelope (§4), vault receipt chain (Appendix A) | `True` |

```python
canon_gate(obj)  = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8")
canon_vault(obj) = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True).encode("utf-8")
```

Consequences an implementer must match:

- Keys sort by Unicode code point (Python string order).
- Separators are exactly `,` and `:` — no spaces anywhere.
- `null`, `true`, `false` render as JSON literals; numbers render as
  Python's `json` renders them (integers plainly; floats in Python
  repr style). The gate envelope in practice carries `amount: null`
  (§4), so float rendering does not arise for gate receipts.
- Under `canon_vault`, non-ASCII strings are `\uXXXX`-escaped; under
  `canon_gate` they are raw UTF-8. For the worked example every string
  in the envelope is ASCII, so the two canons coincide on the
  envelope bytes — they do **not** coincide in general, and using the
  wrong one on a non-ASCII receipt body changes the receipt_hash.

## 3. receipt_hash (gate layer)

From `gate.py` (`receipt_hash_of`, `VaultSigner.sign`):

```text
body         = the receipt object with the keys "receipt_hash" and
               "signature" removed (all other keys kept, including
               "signer" and "prev_receipt_hash")
receipt_hash = sha256_hex( canon_gate(body) )
payload      = receipt_hash.encode("utf-8")     # the 64-char hex string
```

`sha256_hex` is the lowercase hex digest. This is the recompute rule
already published with the receipt canon on 2026-11-17 (asinmcp
PR #6) and restated in the AutoGen #7609 reply.

## 4. The vault envelope (the previously unpublished part)

From `vault.py`:

```python
def envelope(action, payload_sha256, amount, dest, ts, nonce) -> bytes:
    return canon({
        "action": action,
        "payload_sha256": payload_sha256,
        "amount": amount,
        "dest": dest,
        "ts": ts,
        "nonce": nonce,
    })
```

where `canon` is `canon_vault` (§2). Fields:

| field | type | construction |
|---|---|---|
| `action` | string | The vault policy action being exercised. Gate receipts use `"doc.sign"` (the `VaultSigner` default). Carried in the receipt at `signature.action`. |
| `payload_sha256` | string, 64 lowercase hex | `sha256_hex(payload_file_bytes)`. The vault reads the payload from a file and hashes its raw bytes; it never sees the payload's meaning. For gate receipts the payload file contains exactly the 64 ASCII bytes of `receipt_hash` (§3), so `payload_sha256 = sha256_hex(receipt_hash.encode("utf-8"))` — derivable from the receipt alone. |
| `amount` | number (float) or `null` | `null` unless the sign call passes an amount. `VaultSigner` passes no amount, so gate envelopes always carry `null`. |
| `dest` | string or `null` | `null` unless the sign call passes a destination. Gate envelopes always carry `null`. |
| `ts` | string | Signing timestamp, generated by the vault at sign time: UTC, `datetime.now(timezone.utc).isoformat(timespec="seconds")` — e.g. `2026-11-12T12:45:12+00:00` (seconds precision, `+00:00` offset, never `Z`). Carried in the receipt at `signature.ts`. |
| `nonce` | string, 16 lowercase hex | Fresh per signature: `os.urandom(8).hex()` — 8 random bytes, hex-encoded. Carried in the receipt at `signature.nonce`. |

The signed message is exactly `canon_vault(envelope_object)` — the
bytes of the JSON object above with its six keys sorted
(`action, amount, dest, nonce, payload_sha256, ts`).

**Not in the envelope:** the policy hash, the vault id, and the
fingerprint are *not* signed. Policy binding (the vault refuses to
sign if `policy.json` no longer hashes to the sealed `policy_hash`)
is enforced by the vault at sign time and attested only in the
vault's own receipt log (Appendix A) — an outsider verifying the
envelope learns nothing about which policy governed the signature
beyond what the separate vault receipt records.

## 5. The signature

- Algorithm: **Ed25519, RFC 8032**, as implemented by the vendored
  pure-Python `asinmcp/ed25519.py` (standard construction: SHA-512
  seed expansion, clamping, `R = r·B`, `S = r + H(R‖A‖M)·a`).
- Key: the vault's single identity keypair. The seed is 32 bytes,
  generated at `vault.py init` and stored only sealed (at-rest
  sealing is out of scope for verification; see the vault README).
  The public key is the standard RFC 8032 derivation from the seed.
- Signature size: 64 bytes, carried lowercase-hex (128 hex chars) at
  `signature.value` in the gate receipt.
- Verification is the standard RFC 8032 equation
  `[S]B = R + [H(R‖A‖M)]A` over `M = canon_vault(envelope)`,
  `A` = the 32 public-key bytes decoded from `signer.pubkey` hex.

## 6. Signer identity: fingerprint, vault_id, and where the key lives

From `vault.py cmd_init`:

```text
fingerprint = sha256_hex( raw 32 public-key bytes )     # hex of the
                                                        # decoded pubkey,
                                                        # NOT of its hex text
vault_id    = "vlt_" + fingerprint[:16]
```

(The same sha256-of-raw-pubkey formula is the `key_id` of the
Quest 001 seal envelope, ASIN-HHC-QUEST-SEAL-1.0.)

For the live vault: fingerprint
`4f47d2df9dbd9260a48eebe80dc472442b73cf43e78f4c895cf6abd9cb7a8835`,
vault_id `vlt_4f47d2df9dbd9260`. This spec deliberately does not
reproduce the public key's hex in a second place — it is carried,
authoritatively, in the two locations below, and the fingerprint
above is the check that a copy is the right key.

**Where the public key is published:**

1. **Inside every gate receipt**, at `signer.pubkey` (with
   `signer.fingerprint`, `signer.vault_id`, `signer.kind =
   "agent-vault-ed25519"`). This is the operative publication: a
   receipt is self-contained for verification. The 48ac1da5 receipt
   was published in full — object, `signer` and `signature` blocks
   included — in the AutoGen issue #7609 reply of 2026-11-18
   (verbatim local copy:
   `~/workspace/autogen-7609-reply-final-2026-11-18.md`; the same
   object is line 2 of
   `~/workspace/verifier-bot/live-run/gate-ledger.jsonl`).
2. Locally, in the vault's `identity.json`
   (`~/workspace/agent-vault/live/identity.json`, mode 0644):
   `{pubkey, fingerprint, vault_id, created_at, policy_hash}`.

**No standalone public key file or registry URL was found** — no
`identity.json` (or equivalent) is published on the asinmcp GitHub
Pages artifacts or elsewhere in the workspace as of 2026-11-19. The
Proof Board cites the receipt hash only. A standalone publication
(e.g. the vault's `identity.json` alongside the Proof Board) is the
obvious completion, but it does not exist yet and this draft does
not create it: until it exists, the receipt-embedded key in item 1
is the publication of record, and the fingerprint in this section
is the cross-check against any other copy.

## 7. Outsider verification procedure

Inputs: one gate receipt object (§6, item 1) and this spec. No vault
access, no private key, no network.

1. **Recompute the hash.** Remove `receipt_hash` and `signature`
   from the object; `sha256_hex(canon_gate(body))` must equal the
   stated `receipt_hash`.
2. **Check the signer block.** Decode `signer.pubkey` from hex
   (32 bytes); `sha256_hex` of those raw bytes must equal
   `signer.fingerprint`, and `signer.vault_id` must equal
   `"vlt_" + fingerprint[:16]`. `signer.kind` and `signature.kind`
   must both be `"agent-vault-ed25519"`.
3. **Derive the payload hash.** `payload_sha256 =
   sha256_hex(receipt_hash.encode("utf-8"))`.
4. **Rebuild the envelope.** Object: `action` from
   `signature.action`, `payload_sha256` from step 3,
   `amount: null`, `dest: null`, `ts` from `signature.ts`,
   `nonce` from `signature.nonce`. Message = `canon_vault(object)`.
5. **Verify.** RFC 8032 Ed25519-verify `signature.value` (hex-decoded,
   64 bytes) over the step-4 message under the step-2 public key.

All five steps passing means the signature is genuine for this
receipt under the vault key whose fingerprint the receipt names.

Reference implementation: `~/workspace/makefun-port/verify_gate_receipt.py`
(stdlib only, self-contained Ed25519 verify).

## 8. Worked example — receipt 48ac1da5…ea38

From the published object (`verification_id
live-2026-11-12-provindex-001`, signed 2026-11-12):

```text
signature.action = "doc.sign"
signature.ts     = "2026-11-12T12:45:12+00:00"
signature.nonce  = "97f5284c478a8907"
signer           = { kind: "agent-vault-ed25519",
                     vault_id: "vlt_4f47d2df9dbd9260",
                     fingerprint: 4f47d2df…a8835 }   (§6)

step 1  receipt_hash recomputed
        = 48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38  ✓ matches
step 3  payload_sha256 = sha256("48ac1da5…ea38" as UTF-8)
        = 30d5a27d34ff7ad751ebd942125f74794156de136484abe840268a0fd345ad83
step 4  envelope bytes (exactly, 191 bytes):
        {"action":"doc.sign","amount":null,"dest":null,"nonce":"97f5284c478a8907","payload_sha256":"30d5a27d34ff7ad751ebd942125f74794156de136484abe840268a0fd345ad83","ts":"2026-11-12T12:45:12+00:00"}
step 5  Ed25519 verify of signature.value
        00647e8446e697f5…c98f19c570d  over the step-4 bytes
        under signer.pubkey  →  VALID
```

Proof run, 2026-11-19 (`verify_gate_receipt.py`, run against both
the AutoGen-post copy and the gate-ledger copy of the object —
identical objects, both runs exit 0):

```text
[PASS] receipt_hash recomputes (gate canon, body minus receipt_hash/signature)
[PASS] signer.pubkey is 32 bytes hex
[PASS] fingerprint == sha256(raw pubkey bytes)
[PASS] vault_id == 'vlt_' + fingerprint[:16]
[PASS] signature.kind and signer.kind are 'agent-vault-ed25519'
[PASS] payload_sha256 == sha256(receipt_hash as UTF-8)
[PASS] envelope rebuilt (vault canon)
[PASS] signature is 64 bytes hex
[PASS] Ed25519 signature verifies over the vault envelope
[PASS] negative control: tampered-nonce envelope does NOT verify
RESULT: PASS
```

Cross-checks run the same day: the vendored `asinmcp/ed25519.py`
(the production implementation) independently verifies the same
envelope/signature pair and rejects a tampered message; and the
derived `payload_sha256` equals the `payload_sha256` recorded in the
vault's own receipt seq 6 — the vault-side record of this signature
(Appendix A). The last check uses the local vault log and is
internal corroboration, not part of the outsider procedure in §7.

## 9. What verification does not cover

- **Authorization.** A valid signature proves key control at signing
  time, not that the key was authorized for this receipt (§0).
- **The vault receipt pointer.** `signature.vault_receipt_hash` and
  `signature.vault_receipt_seq` point into the vault's local,
  mode-0600 receipt log. An outsider cannot recompute that hash
  without the log (Appendix A gives the construction for when the
  log entry is shared).
- **Policy.** Which policy governed the sign is attested only by
  the vault receipt (§4), not by the envelope signature.
- **Receipt-internal claims.** Witness blocks, snapshot hashes, and
  `prev_receipt_hash` linkage inside the gate receipt are covered
  by the receipt_hash (any edit breaks step 1), but their truth is
  the gate's, not the signature's, question — the disclosed limits
  in the receipt itself (`snapshot_hash` not re-derivable,
  `prev_receipt_hash` chaining to a local-only ledger) stand.

## 10. UNDETERMINED

Marked rather than guessed, per drafting instructions:

1. **Envelope version marker.** The envelope object carries no
   schema or version field, and no name for the format exists in
   the code. "Agent Vault v1" is the vault's product version
   (`policy.version = 1` is a policy field, not an envelope field).
   Whether a future envelope v2 will be distinguished by new field
   shapes alone is UNDETERMINED.
2. **Standalone key publication.** No public URL for the vault's
   `identity.json` was found (§6). Whether/when one will be
   published is UNDETERMINED; the receipt-embedded key is the
   current publication of record.
3. **Deployed-source identity.** This construction was determined
   from the workspace copies of `vault.py`, `gate.py`, and
   `ed25519.py`. That the §7 procedure verifies the 2026-11-12
   signature is strong evidence these are the constructions that
   ran, but no byte-identity attestation of the signing-time code
   exists — UNDETERMINED in the same sense as blueprint gap 2.
4. **Non-null amount rendering.** Gate envelopes always carry
   `amount: null`. For vault actions that carry amounts
   (`hhc.transfer`), the amount enters the envelope as a Python
   float and renders per §2's `json` rules; no gate receipt
   exercises this, and float edge cases (e.g. `5.0` vs `5`) follow
   Python semantics rather than a separately pinned rule —
   determined-by-interpreter, not separately specified.

## Appendix A. The vault's own receipt (corroboration when shared)

Each `vault.py sign` appends one record to the vault's
`receipts.jsonl`, hash-chained:

```text
record fields: ts, kind ("sign"), action, payload_sha256, amount,
               dest, sig, nonce, policy_hash,   ← body
               seq, prev_hash, hash              ← chain fields
hash = sha256_hex( canon_vault( record minus "hash" ) )
seq  = previous seq + 1 (first record: 1)
prev_hash = previous record's hash (first record: 64 zero hex chars)
```

The gate receipt's `signature.vault_receipt_seq` /
`signature.vault_receipt_hash` name this record. For the worked
example: seq 6, `ts 2026-11-12T12:45:12+00:00`, `action doc.sign`,
`nonce 97f5284c478a8907`, `sig` identical to the gate receipt's
`signature.value`, `payload_sha256 30d5a27d…ad83` (matching §8
step 3), `policy_hash
bb42430a73915cffd8f07f9bfb931cd512e54e0502acf595fdcb9d7a144f3a7b`,
record hash recomputing to
`f2ce88361485f3b871b70d8b7088bf51a0d502fd8f54aa9ad710ad643a2b92a2`
— verified 2026-11-19, along with the full 16-record chain. The
vault log itself is local-only (mode 0600); this appendix lets an
outsider check a record *if one is ever shared*, it does not make
the log public.
