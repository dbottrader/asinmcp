#!/usr/bin/env python3
"""Emit (do not apply) the SQL that would register QUEST-001 manifest v3.

This script never writes to the database, never touches escrows or payouts,
and never POSTs to seal-drop. Registration is Dennis Christie's call.
See REGISTER.md.

Usage (from the repo root or quest001/):
  python3 quest001/register_v3.py --emit-sql
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from verify_quest001 import seal  # noqa: E402

QUEST_URL = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001"
MANIFEST_URL = QUEST_URL + "/manifest"
EXPECTED_LIVE_SHA = "422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa"
EXPECTED_LIVE_VERSION = 2
V3_PATH = os.path.join(HERE, "manifest.json")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "asinmcp-register-v3-emit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit QUEST-001 v3 registration SQL. Does not apply it.")
    ap.add_argument("--emit-sql", action="store_true", help="print the guarded apply SQL to stdout")
    ap.add_argument("--manifest", default=V3_PATH, help="path to the v3 manifest bytes")
    ap.add_argument("--created-at", default=None, help="ISO-8601 Z timestamp used in the chronicle record")
    args = ap.parse_args()
    if not args.emit_sql:
        print("Refusing to do anything without --emit-sql. This script does not register.", file=sys.stderr)
        print("See quest001/REGISTER.md. Registration is Dennis Christie's call.", file=sys.stderr)
        return 2

    raw = open(args.manifest, "rb").read()
    if raw.endswith(b"\n"):
        print("manifest has a trailing newline; v3 bytes must not", file=sys.stderr)
        return 1
    if b"$m$" in raw or b"$p$" in raw or b"$apply$" in raw:
        print("manifest contains a dollar-quote delimiter; refusing to emit", file=sys.stderr)
        return 1
    m = json.loads(raw)
    msha = sha(raw)
    if m.get("quest_id") != "QUEST-001" or m.get("version") != 3:
        print("manifest is not QUEST-001 v3", file=sys.stderr)
        return 1
    if msha != "d79d2d5ae94087c89f9d857560133d9b2aaed614c349b60ac08828dbfc1be731":
        print(f"unexpected v3 sha256 {msha}; update REGISTER.md if this is intentional", file=sys.stderr)
        return 1

    live_manifest = get(MANIFEST_URL)
    live_sha = sha(live_manifest)
    quest = json.loads(get(QUEST_URL))
    seals = quest.get("seals") or quest.get("envelopes") or []
    chronicle = quest.get("chronicle") or []
    if chronicle:
        tip = max(chronicle, key=lambda r: r.get("seq", -1))
        prev_hash = tip["record_hash"]
        seq = tip["seq"] + 1
    else:
        prev_hash = "0" * 64
        seq = 0

    print(f"-- live manifest sha256 {live_sha}", file=sys.stderr)
    print(f"-- live seal count {len(seals) if isinstance(seals, list) else 'UNKNOWN'}", file=sys.stderr)
    print(f"-- proposed chronicle seq {seq} prev {prev_hash}", file=sys.stderr)

    created_at = args.created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    text = raw.decode("utf-8")
    payload = {
        "claim_bytes": m["claim"]["bytes"],
        "claim_sha256": m["claim"]["sha256"],
        "claim_url": m["claim"]["url"],
        "deadline": m["deadline"],
        "is_test": False,
        "manifest_sha256": msha,
        "previous_deadline": "2026-11-26T23:59:00-06:00",
        "previous_manifest_sha256": EXPECTED_LIVE_SHA,
        "reason": "spec deadline aligned to Nov 26 and ineligible_operators expanded; supersedes v2",
        "spec_sha256": m["spec"]["sha256"],
    }
    rec = {
        "created_at": created_at,
        "event": "manifest_superseded",
        "payload": payload,
        "prev_hash": prev_hash,
        "quest_id": "QUEST-001",
        "seq": seq,
    }
    record_hash = seal(rec)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    sql = f"""-- QUEST-001 manifest v3 apply. DO NOT RUN unless Dennis Christie authorizes it.
-- Prep only was committed on feat/quest001-manifest-v3. This file does not move HHC.
-- Guards: live row must still be v2 sha256 {EXPECTED_LIVE_SHA}; 0 seals; byte match after update.
-- Chronicle: seq {seq}, prev_hash {prev_hash}, created_at {created_at}, record_hash {record_hash}.
-- Re-run register_v3.py --emit-sql immediately before apply if the tip or live hash has moved.

do $apply$
declare
  v_appended jsonb;
  v_updated int;
begin
  if not exists (
    select 1 from public.quest_manifests
    where quest_id = 'QUEST-001'
      and manifest_sha256 = '{EXPECTED_LIVE_SHA}'
      and version = {EXPECTED_LIVE_VERSION}
  ) then
    raise exception 'QUEST-001 is not at the expected v2 hash; refusing to update';
  end if;
  if exists (select 1 from public.quest_seals where quest_id = 'QUEST-001') then
    raise exception 'QUEST-001 already has seals; refusing a silent manifest swap';
  end if;

  update public.quest_manifests
  set
    version = 3,
    manifest_text = $m${text}$m$,
    manifest = $m${text}$m$::jsonb,
    manifest_sha256 = '{msha}',
    deadline = '{m['deadline']}'
  where quest_id = 'QUEST-001'
    and manifest_sha256 = '{EXPECTED_LIVE_SHA}'
    and version = {EXPECTED_LIVE_VERSION};
  get diagnostics v_updated = row_count;
  if v_updated <> 1 then
    raise exception 'QUEST-001 update touched % rows, expected 1', v_updated;
  end if;

  if exists (
    select 1 from public.quest_manifests
    where encode(sha256(convert_to(manifest_text, 'UTF8')), 'hex') <> manifest_sha256
  ) then
    raise exception 'manifest_text bytes do not match manifest_sha256';
  end if;
  if not exists (
    select 1 from public.quest_manifests
    where quest_id = 'QUEST-001'
      and manifest_sha256 = '{msha}'
      and version = 3
      and deadline = '{m['deadline']}'
  ) then
    raise exception 'QUEST-001 v3 row not present after update';
  end if;

  v_appended := public.quest_append(
    'QUEST-001',
    {seq},
    'manifest_superseded',
    $p${payload_json}$p$::jsonb,
    '{prev_hash}',
    '{record_hash}',
    '{created_at}',
    null
  );
  if v_appended is null or (v_appended->>'record_hash') is distinct from '{record_hash}' then
    raise exception 'quest_append did not return the expected record_hash: %', v_appended;
  end if;
end
$apply$;
"""
    sys.stdout.write(sql)
    print(f"-- emitted record_hash {record_hash}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
