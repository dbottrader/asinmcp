-- PROPOSAL ONLY - NOT APPLIED. Needs Dennis Christie's approval.
-- Extends QUEST-001-TEST (is_test, no reward) to the QUEST-001 v2 deadline so
-- seal_quest001.py --test-quest can be accepted live. QUEST-001 is not touched.
-- The chronicle is append-only (trigger quest_chronicle_append_only), so the
-- second statement is permanent. Precondition: QUEST-001-TEST tip is seq 6,
-- record_hash da32c4b54cd7f60d684b365f543c6cc70e3a30f6848fa2d4d3b2acf1be45acb7 (true as of Mon Nov 23, 2026 2:03 AM CT).
-- new test manifest sha256 c22d7db6a392be5f80e72695a990e1c43b9d18335aac71be93be4961c46e401a; new chronicle record_hash ada62b25dd3db9542054f946adc97949d753b40b7765b4ea400628a9fc335593
begin;
do $$ begin
  if (select record_hash from public.quest_chronicle where quest_id='QUEST-001-TEST' order by seq desc limit 1) <> 'da32c4b54cd7f60d684b365f543c6cc70e3a30f6848fa2d4d3b2acf1be45acb7'
  then raise exception 'QUEST-001-TEST tip moved; regenerate this proposal'; end if;
end $$;
update public.quest_manifests
   set version = 2, manifest_text = $m${
  "claim": {
    "bytes": 87505,
    "media_type": "application/json",
    "sha256": "a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e",
    "url": "https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json"
  },
  "deadline": "2026-11-26T23:59:00-06:00",
  "deadline_epoch": 1795759140,
  "deadline_utc": "2026-11-27T05:59:00Z",
  "endpoints": {
    "manifest": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test/manifest",
    "quest": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test",
    "replay": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test/replay",
    "seal_drop": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/seal-drop",
    "verdict": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test/verdict"
  },
  "envelope_schema": "ASIN-HHC-QUEST-SEAL-1.0",
  "independence": {
    "distinct": [
      "operator",
      "pubkey",
      "failure_mode"
    ],
    "human_review": "operator independence is self-declared; Dennis Christie confirms separate operators, hosts and credentials before any settlement",
    "ineligible_operators": [
      "ineligible-probe"
    ],
    "min_witnesses": 2
  },
  "is_test": true,
  "quest_id": "QUEST-001-TEST",
  "schema": "ASIN-HHC-QUEST-MANIFEST-1.0",
  "settlement": {
    "authority": "Dennis Christie",
    "automatic_payment": false,
    "state": "awaiting_human_authorization"
  },
  "signature_rules": {
    "algorithm": "Ed25519 (RFC 8032)",
    "envelope_signature": "over canonical_json of all envelope fields except signature and envelope_signature",
    "key_id": "sha256 of the 32 raw public-key bytes",
    "signature": "over UTF-8 bytes of the sealed_output hex string"
  },
  "spec": {
    "path": "quest001/QUEST-001-SPEC.md",
    "sha256": "c0b701e6c7ce917d99a714133a977d78de1afd783a258a7ba6277b95b15b1af4"
  },
  "title": "TEST ONLY - seal-drop negative suite (no reward)",
  "valid_from": "2026-11-14T15:00:00Z",
  "version": 2,
  "witness_output": {
    "count": "number of elements in .entries (non-empty array of objects)",
    "fields": [
      "count",
      "head_hash"
    ],
    "head_hash": "last hash of the recomputed index chain: entry hash = sha256(json.dumps(entry without index_hash, sort_keys=True, ensure_ascii=False)) with default separators; entry 0 links to .ledger_anchor.tip_hash",
    "sealed_output": "sha256(canonical_json(output)); canonical_json = sorted keys, separators (',',':'), UTF-8, ensure_ascii=False, no trailing newline"
  }
}$m$, manifest = $m${
  "claim": {
    "bytes": 87505,
    "media_type": "application/json",
    "sha256": "a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e",
    "url": "https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json"
  },
  "deadline": "2026-11-26T23:59:00-06:00",
  "deadline_epoch": 1795759140,
  "deadline_utc": "2026-11-27T05:59:00Z",
  "endpoints": {
    "manifest": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test/manifest",
    "quest": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test",
    "replay": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test/replay",
    "seal_drop": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/seal-drop",
    "verdict": "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001-test/verdict"
  },
  "envelope_schema": "ASIN-HHC-QUEST-SEAL-1.0",
  "independence": {
    "distinct": [
      "operator",
      "pubkey",
      "failure_mode"
    ],
    "human_review": "operator independence is self-declared; Dennis Christie confirms separate operators, hosts and credentials before any settlement",
    "ineligible_operators": [
      "ineligible-probe"
    ],
    "min_witnesses": 2
  },
  "is_test": true,
  "quest_id": "QUEST-001-TEST",
  "schema": "ASIN-HHC-QUEST-MANIFEST-1.0",
  "settlement": {
    "authority": "Dennis Christie",
    "automatic_payment": false,
    "state": "awaiting_human_authorization"
  },
  "signature_rules": {
    "algorithm": "Ed25519 (RFC 8032)",
    "envelope_signature": "over canonical_json of all envelope fields except signature and envelope_signature",
    "key_id": "sha256 of the 32 raw public-key bytes",
    "signature": "over UTF-8 bytes of the sealed_output hex string"
  },
  "spec": {
    "path": "quest001/QUEST-001-SPEC.md",
    "sha256": "c0b701e6c7ce917d99a714133a977d78de1afd783a258a7ba6277b95b15b1af4"
  },
  "title": "TEST ONLY - seal-drop negative suite (no reward)",
  "valid_from": "2026-11-14T15:00:00Z",
  "version": 2,
  "witness_output": {
    "count": "number of elements in .entries (non-empty array of objects)",
    "fields": [
      "count",
      "head_hash"
    ],
    "head_hash": "last hash of the recomputed index chain: entry hash = sha256(json.dumps(entry without index_hash, sort_keys=True, ensure_ascii=False)) with default separators; entry 0 links to .ledger_anchor.tip_hash",
    "sealed_output": "sha256(canonical_json(output)); canonical_json = sorted keys, separators (',',':'), UTF-8, ensure_ascii=False, no trailing newline"
  }
}$m$::jsonb,
       manifest_sha256 = 'c22d7db6a392be5f80e72695a990e1c43b9d18335aac71be93be4961c46e401a', deadline = '2026-11-26T23:59:00-06:00'
 where quest_id = 'QUEST-001-TEST' and manifest_sha256 = 'ed1b02ac9eb264fab11460fd69802bbc2c7b6d7eb553b0ffdfcc2b41bfb333af';
insert into public.quest_chronicle (quest_id, seq, event, payload, prev_hash, record_hash, created_at, is_test)
values ('QUEST-001-TEST', 7, 'manifest_superseded', $p${"claim_bytes": 87505, "claim_sha256": "a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e", "claim_url": "https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json", "deadline": "2026-11-26T23:59:00-06:00", "is_test": true, "manifest_sha256": "c22d7db6a392be5f80e72695a990e1c43b9d18335aac71be93be4961c46e401a", "reason": "test window extended to match QUEST-001 v2 so the seal kit can be tested live", "spec_sha256": "c0b701e6c7ce917d99a714133a977d78de1afd783a258a7ba6277b95b15b1af4", "superseded_manifest_sha256": "ed1b02ac9eb264fab11460fd69802bbc2c7b6d7eb553b0ffdfcc2b41bfb333af"}$p$::jsonb, 'da32c4b54cd7f60d684b365f543c6cc70e3a30f6848fa2d4d3b2acf1be45acb7', 'ada62b25dd3db9542054f946adc97949d753b40b7765b4ea400628a9fc335593', '2026-11-23T08:00:00.000Z', true);
do $$ begin
  if exists (select 1 from public.quest_manifests where encode(sha256(convert_to(manifest_text, 'UTF8')), 'hex') <> manifest_sha256)
  then raise exception 'manifest_text bytes do not match manifest_sha256'; end if;
end $$;
commit;
