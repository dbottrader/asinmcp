#!/usr/bin/env python3
"""Recompute the ASIN-HHC mesh ledger from ledger-export.json.
v0-compat rows (seq 1-15): old spec, default JSON separators.
v1 rows (seq 16+): canon_v1, no-whitespace separators, ASCII-escaped.
Linkage (prev_hash) is checked for every row. Usage: python3 verify-ledger.py
"""
import json, hashlib, sys
def sha_old(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
def sha_v1(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
rows = json.load(open("ledger-export.json"))
prev, fails = "0" * 64, []
for r in rows:
    body = {"ts": r["ts"], "actor": r["actor"], "kind": r["kind"], "payload": r["payload"], "prev_hash": r["prev_hash"]}
    if r["prev_hash"] != prev:
        fails.append((r["seq"], "link"))
    calc = sha_v1(body) if r["canon"] == "v1" else sha_old(body)
    if calc != r["hash"]:
        fails.append((r["seq"], "hash"))
    prev = r["hash"]
print(f"rows={len(rows)} terminal={rows[-1]['hash']} fails={fails}")
sys.exit(1 if fails else 0)
