#!/usr/bin/env python3
"""Build quest001/manifest.json (QUEST-001) and manifest-test.json
(QUEST-001-TEST, negative-suite only) as exact bytes: sorted keys,
2-space indent, UTF-8, NO trailing newline. Prints each sha256."""
import hashlib, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence"
CLAIM = "https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json"
VALID_FROM = "2026-11-14T15:00:00Z"
DEADLINE = "2026-11-19T23:59:00-06:00"
DEADLINE_UTC = "2026-11-20T05:59:00Z"
DEADLINE_EPOCH = 1795154340


def sha(b): return hashlib.sha256(b).hexdigest()


def build(quest_id, slug, title, is_test, ineligible, reward, raw_claim, spec_sha):
    m = {
        "schema": "ASIN-HHC-QUEST-MANIFEST-1.0",
        "quest_id": quest_id,
        "title": title,
        "version": 1,
        "is_test": is_test,
        "spec": {"path": "quest001/QUEST-001-SPEC.md", "sha256": spec_sha},
        "claim": {"url": CLAIM, "sha256": sha(raw_claim), "bytes": len(raw_claim),
                  "media_type": "application/json"},
        "witness_output": {
            "fields": ["count", "head_hash"],
            "count": "number of elements in .entries (non-empty array of objects)",
            "head_hash": "last hash of the recomputed index chain: entry hash = sha256(json.dumps(entry without index_hash, sort_keys=True, ensure_ascii=False)) with default separators; entry 0 links to .ledger_anchor.tip_hash",
            "sealed_output": "sha256(canonical_json(output)); canonical_json = sorted keys, separators (',',':'), UTF-8, ensure_ascii=False, no trailing newline",
        },
        "envelope_schema": "ASIN-HHC-QUEST-SEAL-1.0",
        "signature_rules": {
            "algorithm": "Ed25519 (RFC 8032)",
            "signature": "over UTF-8 bytes of the sealed_output hex string",
            "envelope_signature": "over canonical_json of all envelope fields except signature and envelope_signature",
            "key_id": "sha256 of the 32 raw public-key bytes",
        },
        "valid_from": VALID_FROM,
        "deadline": DEADLINE,
        "deadline_utc": DEADLINE_UTC,
        "deadline_epoch": DEADLINE_EPOCH,
        "independence": {
            "min_witnesses": 2,
            "distinct": ["operator", "pubkey", "failure_mode"],
            "ineligible_operators": ineligible,
            "human_review": "operator independence is self-declared; Dennis Christie confirms separate operators, hosts and credentials before any settlement",
        },
        "endpoints": {
            "manifest": f"{BASE}/{slug}/manifest",
            "seal_drop": f"{BASE}/seal-drop",
            "quest": f"{BASE}/{slug}",
            "verdict": f"{BASE}/{slug}/verdict",
            "replay": f"{BASE}/{slug}/replay",
        },
        "settlement": {
            "state": "awaiting_human_authorization",
            "automatic_payment": False,
            "authority": "Dennis Christie",
        },
    }
    if reward:
        m["reward"] = reward
    return (json.dumps(m, indent=2, sort_keys=True, ensure_ascii=False)).encode("utf-8")


def main():
    raw = open(sys.argv[1], "rb").read() if len(sys.argv) > 1 else \
        urllib.request.urlopen(CLAIM, timeout=30).read()
    spec_sha = sha(open(os.path.join(HERE, "QUEST-001-SPEC.md"), "rb").read())
    reward = {
        "currency": "HHC",
        "total_hhc": 10,
        "split": "50/50",
        "per_verifier_hhc": 5,
        "recipients": "the two matching independent verifiers of the PASS pair: alpha (earlier accepted seal) and beta (later)",
        "funded_escrows": [
            {"escrow_id": "esc_0e020c419a0b", "funded_hhc": "6.0"},
            {"escrow_id": "esc_6cb8dcae818c", "funded_hhc": "4.0"},
        ],
        "reconciliation": "funded escrows (6.0 + 4.0) are reconciled to 5 + 5 at settlement",
    }
    outs = {
        "manifest.json": build("QUEST-001", "quest-001", "Seal the Index", False,
                               ["grokace", "dbottrader", "dennischristie"], reward, raw, spec_sha),
        "manifest-test.json": build("QUEST-001-TEST", "quest-001-test",
                                    "TEST ONLY - seal-drop negative suite (no reward)", True,
                                    ["ineligible-probe"], None, raw, spec_sha),
    }
    for name, b in outs.items():
        with open(os.path.join(HERE, name), "wb") as f:
            f.write(b)
        print(f"{sha(b)}  {name}  ({len(b)} bytes)")


if __name__ == "__main__":
    main()
