# Register QUEST-001 manifest v3 (Dennis's call)

Prep only. This file documents the exact command that would register
manifest v3. **Do not run the apply step unless Dennis Christie authorizes
it.** This branch does not register the manifest, does not merge, and does
not touch escrows or payouts.

v3 changes two things that v2 left unfinished:

1. Pins the revised `QUEST-001-SPEC.md` (deadline
   `2026-11-26T23:59:00-06:00` = `2026-11-27T05:59:00Z` = Unix `1795759140`).
2. Expands `independence.ineligible_operators` so Dennis's own nodes and
   agents, and the ASIN-HHC Verifier's seal operator, are refused at intake.

Decided values kept from v2: 10 HHC total, 5/5 to two matching independent
verifiers, `min_witnesses` 2, distinct `operator` / `pubkey` / `failure_mode`,
deadline `2026-11-26T23:59:00-06:00`. Escrow ids and funded amounts are
unchanged. Intake code is unchanged; only the `quest_manifests` row and a
chronicle `manifest_superseded` event would change.

Because 0 seals exist, a revision now invalidates nothing. If any seal
appears before apply, stop.

## Hashes

| Item | Value |
|---|---|
| SPEC (`quest001/QUEST-001-SPEC.md`) | `8971ddd88ee2ab28229acef973daa0940a88a3f36ead7f2a50b02c08248a216f` |
| Manifest v3 (`quest001/manifest.json`, no trailing LF) | `d79d2d5ae94087c89f9d857560133d9b2aaed614c349b60ac08828dbfc1be731` |
| Supersedes (live v2) | `422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa` |
| Prior v1 (already superseded 2026-11-19) | `50cefe6ad4090de76f6bdc02654e533261f08ec661b2ba7df98cba1e9c7548a1` |

The Verifier's operator name, as used in its QUEST-001 confirmation
witness (`/workspace/launch/lab/receipts-src/witness.json`, operator
`asin-hhc.org`, implementation `ASIN-HHC Verifier: ...`), is on the list.
After `normName` (lowercase, alphanumerics only) that becomes
`asinhhcorg`, which is distinct from `asinhhc`. The proof-board string
`Ace (ASIN-HHC LLC, founder Dennis Christie)` is also listed, because it
does not normalize to `ace`.

Intentional same-norm pairs: `asinhhc` / `asin-hhc`; `asinhhcverifier` /
`ASIN-HHC Verifier`. `ace` and `muse` are short common names; they are
included as requested and match only exactly after `normName`, so
`ace-lab`, `the-muse`, and `museum` are not blocked.

## Exact command

From a checkout of this branch, with network access for the read-only
preflight. The emitter only prints SQL. It does not apply anything.

```bash
# 1. Re-check live state (read only). Stop if seals is not empty
#    or the manifest sha is no longer the v2 hash.
M=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001/manifest
Q=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001
curl -fsS "$M" | sha256sum
# must be 422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa
curl -fsS "$Q" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("seals", len(d.get("seals") or [])); print("deadline", d.get("deadline")); c=d.get("chronicle") or []; tip=max(c, key=lambda r: r["seq"]); print("tip", tip["seq"], tip["record_hash"])'

# 2. Confirm local v3 bytes and emit the guarded apply SQL.
#    Re-run this immediately before apply so created_at, seq and prev_hash
#    match the live tip. Expected tip, if unchanged since v2, is seq 1,
#    record_hash 70c73e9af773e3aea24f065bad7a8bf16e6fda4b8031f57a5d1053f9f1631b20
#    (next seq would be 2).
sha256sum quest001/QUEST-001-SPEC.md quest001/manifest.json
python3 quest001/register_v3.py --emit-sql > /tmp/quest001-v3-apply.sql

# 3. ONLY after Dennis authorizes registration, apply as service_role /
#    postgres (one transaction; rollback on any exception). Example:
# psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f /tmp/quest001-v3-apply.sql
```

Step 3 is the registration. It is not authorized by this branch. Leave
the `psql` line commented until Dennis says to apply.

The emitted SQL:

- refuses unless the current row is still QUEST-001 v2 at
  `422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa`
- refuses if any row exists in `quest_seals` for QUEST-001
- updates that single row to version 3, the v3 `manifest_text` bytes, and
  the same Nov 26 deadline
- checks `sha256(manifest_text)` equals `manifest_sha256`
- appends `manifest_superseded` via `quest_append` (compare-and-swap on
  the tip; `p_seal` is null)

No function deploy. No change to QUEST-001-TEST. No escrow or payout
statement.

## Post-apply checks (only after a future authorized apply)

- `GET .../quest-001/manifest` is 200, body sha256 and `X-Manifest-SHA256`
  both equal `d79d2d5ae94087c89f9d857560133d9b2aaed614c349b60ac08828dbfc1be731`,
  no trailing LF.
- Manifest `version` is 3, `spec.sha256` is
  `8971ddd88ee2ab28229acef973daa0940a88a3f36ead7f2a50b02c08248a216f`,
  `supersedes.manifest_sha256` is
  `422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa`.
- Verdict is still HOLD with 0 seals. Chronicle tip is the new
  `manifest_superseded` record, and the chain still verifies.
