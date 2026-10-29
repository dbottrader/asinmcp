# VERIFY Report — asinmcp signed registry snapshot

- **Date:** 2026-10-29 (verified ~07:21 UTC, snapshot signed 2026-10-29T07:16:46Z)
- **Verifier role:** independent external-style VERIFY (Proof of Pay task class), derived from files only; fleet seed never read (only `keys/ace-lattice.pub` and the public signature record used).
- **Artifacts:** `registry.jsonl` (source), `registry.cpbin` (ASNB v1 snapshot, 6,166 bytes), `registry.cpbin.sig.json` (Ed25519 signature record)

## Check 1 — Decode matches source exactly: **PASS**

- `asinbin.decode(registry.cpbin)` returned **39 records**; `registry.jsonl` contains **39 records**.
- Field-by-field comparison over all 6 ASNB fields (`id, type, name, status, anchor, created`) for every record: **exact match, 0 mismatches**; record IDs identical and in the same order.
- First decoded record: `{"id": "CP-0001", "type": "project", "name": "ASIN-HHC / CP8 public launch", "status": "active", "anchor": "goal_8b2c8ae56717", "created": "2026-10-29"}`
- File hashes: `registry.jsonl` sha256 `e02b2426dc87ed292edd5ed989325095841186deffdc422dda2901dfbb964df1`; `registry.cpbin` sha256 `32db81d373104d8f95982db3ec7fe228aee9e49f81f36b734d4349c08245bb2d` — identical to the `sha256` field in the signature record.

## Check 2 — Signature verification (`crypto.py verify`): **PASS**

Exact tool output (exit code 0):

```
hash OK · signature OK · signer d7ea9b08d8f91a68…
```

- Signature record: signer pubkey `d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8`, signature `cb50dd2d1794d563ff30d962d9f754d79103217f65dddadedf34e4aa83113ee43acf35a15e02c9047b1a7e683dc4e7f9f746241e680f757f489554e8389f5b03`, signed_at `2026-10-29T07:16:46.332061+00:00`.
- Cross-check independent of `crypto.py`: direct `ed25519.verify(pubkey_from_pub_file, cpbin_bytes, signature)` returned **True**; the pub file `keys/ace-lattice.pub` matches the signature record's pubkey exactly.

## Check 3 — Internal SHA-256 trailer validates: **PASS**

- Header: magic `ASNB`, version byte `1`.
- Independently recomputed `sha256(cpbin[:-32])` = `fb798aa31db1e929100541f741789a49edab1a19ac0e8c65ff3f1514b0b5718c`, equal to the stored 32-byte trailer `fb798aa31db1e929100541f741789a49edab1a19ac0e8c65ff3f1514b0b5718c`. (`asinbin.decode` also asserts this internally and did not raise.)

## Check 4 — Tamper test (copy in /tmp): **PASS**

- Copied `registry.cpbin` + `.sig.json` to `/tmp/tamper.cpbin`; flipped one bit at payload offset 200 (`0x70` → `0x71`).
- `asinbin.decode` on the tampered copy: **rejected** — `checksum fail — corrupted or tampered`.
- `crypto.py verify /tmp/tamper.cpbin` exact output (exit code 1): `hash FAIL · signature FAIL · signer d7ea9b08d8f91a68…`
- Independent `ed25519.verify` on the tampered bytes returned **False**.
- Original files untouched (tamper performed only on the /tmp copy).

## Check 5 — Public GitHub pubkey matches signer: **PASS**

- Fetched `https://raw.githubusercontent.com/dbottrader/asinmcp/main/README.md` (public repo, crawled 2026-10-29 07:21 UTC).
- README prints: "Fleet signing pubkey: `d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8`"
- This is character-for-character identical to the signature record's `pubkey` and to `keys/ace-lattice.pub`.

## Verdict

**PASS — 5/5 checks.** The ASNB snapshot decodes to exactly the source registry (39/39 records), its internal SHA-256 trailer validates, the Ed25519 signature verifies against the fleet public key published in the public asinmcp repo, and a 1-bit payload tamper is rejected at both the checksum and signature layers. The signed snapshot is authentic and untampered as of verification time.

---
Report SHA-256 (of the report body above, before this line): 9746df7284e8e608bd4be5a23393297977d08048bf7c9612b6644be34f60b16d
