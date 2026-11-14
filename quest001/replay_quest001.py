#!/usr/bin/env python3
"""Independent replay of a quest's public evidence. Trusts nothing the
service says: re-fetches seals + chronicle, recomputes every record_hash
and the prev_hash links, every envelope_sha256, every seal and both
Ed25519 signatures, re-executes the claim itself, and recomputes the
verdict with the SPEC §6 rules. Never pays anything.

  replay_quest001.py [quest-001|quest-001-test] [--base URL]
Exit 0 if the chronicle verifies and the local verdict equals the service's.
"""
import argparse, json, sys, urllib.request, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_quest001 as v  # noqa: E402

BASE = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence"
SIGNED = v.SIGNED_FIELDS


def get(url):
    return json.loads(v.fetch_bytes(url).decode("utf-8"))


def norm(s):
    return "".join(c for c in s.lower() if c.isalnum())


def fm(s):
    return " ".join(s.strip().lower().split())


def local_verdict(manifest, envs):
    raw = v.fetch_bytes(manifest["claim"]["url"])
    if v.sha256_hex(raw) != manifest["claim"]["sha256"] or len(raw) != manifest["claim"]["bytes"]:
        return "HOLD", "CLAIM_CHANGED_SINCE_MANIFEST"
    expected = v.compute_evidence(raw)["sealed_output"]
    valid = [e for e in envs if not v.check_envelope(e)]
    if len(valid) < 2:
        return "HOLD", "INSUFFICIENT_VALID_WITNESSES"
    ind = lambda a, b: norm(a["operator"]) != norm(b["operator"]) and a["pubkey"] != b["pubkey"] and fm(a["failure_mode"]) != fm(b["failure_mode"])
    agree = [e for e in valid if e["sealed_output"] == expected]
    dis = [e for e in valid if e["sealed_output"] != expected]
    pas = any(ind(a, b) for a in agree for b in agree if a is not b)
    conflict = any(ind(a, b) for a in agree for b in dis)
    fail = any(ind(a, b) and a["sealed_output"] == b["sealed_output"] for i, a in enumerate(dis) for b in dis[i + 1:])
    if pas and not conflict:
        return "PASS", "TWO_INDEPENDENT_MATCHING_SEALS"
    if conflict:
        return "VOID", "WITNESS_CONFLICT"
    if fail:
        return "FAIL", "INDEPENDENT_WITNESSES_REPRODUCE_DIFFERENT_RESULT"
    return "HOLD", "NO_INDEPENDENT_PAIR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quest", nargs="?", default="quest-001")
    ap.add_argument("--base", default=BASE)
    a = ap.parse_args()
    q = get(f"{a.base}/{a.quest}")
    mraw = v.fetch_bytes(f"{a.base}/{a.quest}/manifest")
    manifest = json.loads(mraw)
    problems = []
    if v.sha256_hex(mraw) != q["manifest_sha256"]:
        problems.append("served manifest bytes != manifest_sha256")
    prev = "0" * 64
    for i, r in enumerate(sorted(q["chronicle"], key=lambda r: r["seq"])):
        if r["seq"] != i:
            problems.append(f"seq gap at {i}")
        if r["prev_hash"] != prev:
            problems.append(f"seq {r['seq']}: prev_hash does not link")
        h = v.seal({k: r[k] for k in ("quest_id", "seq", "event", "payload", "prev_hash", "created_at")})
        if h != r["record_hash"]:
            problems.append(f"seq {r['seq']}: record_hash does not recompute")
        prev = r["record_hash"]
    by_seq = {r["seq"]: r for r in q["chronicle"]}
    envs = []
    for s in q["seals"]:
        e = s["envelope"]
        envs.append(e)
        if v.seal(e) != s["envelope_sha256"]:
            problems.append(f"seal {s['id']}: envelope_sha256 does not recompute")
        r = by_seq.get(s["chronicle_seq"])
        if not r or r["payload"].get("envelope_sha256") != s["envelope_sha256"]:
            problems.append(f"seal {s['id']}: not anchored in chronicle")
    verdict, reason = local_verdict(manifest, envs)
    served = get(f"{a.base}/{a.quest}/verdict")
    if (served["verdict"], served["reason"]) != (verdict, reason):
        problems.append(f"verdict mismatch: service {served['verdict']}/{served['reason']} vs local {verdict}/{reason}")
    if served.get("automatic_payment") is not False or served.get("settlement_state") != "awaiting_human_authorization":
        problems.append("service verdict is not in awaiting_human_authorization / automatic_payment=false")
    print(json.dumps({"quest": q["quest_id"], "is_test": q["is_test"], "chain_length": len(q["chronicle"]),
                      "chain_tip": prev, "seals": len(envs), "local_verdict": verdict, "reason": reason,
                      "service_verdict_hash": served.get("verdict_hash"), "replay_ok": not problems,
                      "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
