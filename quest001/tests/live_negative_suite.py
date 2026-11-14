#!/usr/bin/env python3
"""Live negative suite against the deployed quest-evidence function.
Writes ONLY to QUEST-001-TEST (is_test=true). Throwaway keys are generated
in memory and discarded. Records results to tests/live-results-<UTC>.json.
Asserts every rejection leaves the seal count and chain tip unchanged."""
import hashlib, json, os, secrets, sys, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
Q = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, Q)
import verify_quest001 as v  # noqa: E402

BASE = os.environ.get("QUEST_BASE", "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence")
SLUG = "quest-001-test"
RUN = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def post(env):
    req = urllib.request.Request(f"{BASE}/seal-drop", data=json.dumps(env).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def state():
    q = json.loads(v.fetch_bytes(f"{BASE}/{SLUG}"))
    return len(q["seals"]), (q["chronicle"][-1]["record_hash"] if q["chronicle"] else None)


def main():
    mraw = v.fetch_bytes(f"{BASE}/{SLUG}/manifest")
    m, msha = json.loads(mraw), v.sha256_hex(mraw)
    ev = v.evidence_for_manifest(m)
    now = datetime.now(timezone.utc)
    seed = lambda: secrets.token_bytes(32)
    mk = lambda s, op, fmode, **kw: v.build_envelope(s, m, kw.pop("msha", msha), kw.pop("ev", ev), op, fmode,
                                                     f"live_negative_suite run {RUN}", now=kw.pop("now", now), **kw)
    sA, sB = seed(), seed()
    opA, opB = f"suite-alpha-{RUN}", f"suite-beta-{RUN}"
    envA = mk(sA, opA, f"suite fm alpha {RUN}")
    results = []

    def case(name, env, want_status, want_code=None, mutate_state=False):
        before = state()
        st, body = post(env)
        after = state()
        ok = st == want_status and (want_code is None or body.get("code") == want_code) and \
            ((after != before) if mutate_state else (after == before))
        results.append({"case": name, "http": st, "code": body.get("code"), "accepted": body.get("accepted"),
                        "expected": [want_status, want_code], "state_unchanged": after == before, "pass": ok,
                        **({"chronicle": body.get("chronicle")} if body.get("accepted") else {})})
        print(("PASS " if ok else "FAIL ") + f"{name}: HTTP {st} {body.get('code') or ''}")

    case("valid seal A (accepted)", envA, 201, None, mutate_state=True)
    bad = dict(envA, nonce=secrets.token_hex(32), request_id=v.uuid.uuid4().__str__())
    bad = v.build_envelope(seed(), m, msha, ev, f"bad-sig-{RUN}", "fm bad sig", "x", now=now)
    bad["signature"] = bad["signature"][:-2] + ("00" if not bad["signature"].endswith("00") else "11")
    case("bad signature", bad, 422, "bad_signature")
    case("replayed nonce (fresh key+operator, A's nonce)", mk(seed(), f"replay-{RUN}", "fm replay", nonce=envA["nonce"]), 409, "replayed_nonce")
    case("replayed envelope (A resubmitted verbatim)", envA, 409, "replayed_nonce")
    case("expired", mk(seed(), f"expired-{RUN}", "fm expired", now=now - timedelta(minutes=20), ttl_hours=0.2), 422, "expired")
    case("issued in future", mk(seed(), f"future-{RUN}", "fm future", now=now + timedelta(hours=1)), 422, "issued_in_future")
    case("wrong manifest sha", mk(seed(), f"wrongman-{RUN}", "fm wm", msha="1" * 64), 409, "wrong_manifest")
    short = mk(seed(), f"short-{RUN}", "fm short")
    short["output"] = dict(short["output"], head_hash=short["output"]["head_hash"][:16])
    case("short hash (16 hex head_hash)", short, 422, "bad_hash_format")
    case("duplicate key (A's key, new operator+nonce)", mk(sA, f"dupkey-{RUN}", "fm dupkey"), 409, "duplicate_key")
    case("duplicate operator (new key, A's operator)", mk(seed(), opA.upper(), "fm dupop"), 409, "duplicate_operator")
    case("ineligible operator", mk(seed(), "Ineligible-Probe", "fm inel"), 422, "operator_ineligible")
    case("unknown quest", dict(envA, quest_id="QUEST-999"), 404, "unknown_quest")
    sealmis = mk(seed(), f"sealmis-{RUN}", "fm sealmis")
    sealmis["output"] = dict(sealmis["output"], count=sealmis["output"]["count"] + 1)
    case("output edited after sealing", sealmis, 422, "seal_mismatch")
    case("valid seal B, independent (accepted)", mk(sB, opB, f"suite fm beta {RUN}"), 201, None, mutate_state=True)

    verdict = json.loads(v.fetch_bytes(f"{BASE}/{SLUG}/verdict"))
    replay = json.loads(v.fetch_bytes(f"{BASE}/{SLUG}/replay"))
    real = json.loads(v.fetch_bytes(f"{BASE}/quest-001"))
    out = {"run": RUN, "base": BASE, "quest": "QUEST-001-TEST", "results": results,
           "all_pass": all(r["pass"] for r in results),
           "test_verdict": {k: verdict[k] for k in ("verdict", "reason", "seals_valid", "settlement_state", "automatic_payment", "verdict_hash")},
           "test_replay": {k: replay[k] for k in ("replay_ok", "chain_length", "chain_tip", "problems")},
           "real_quest_001_untouched": {"seals": len(real["seals"]), "chain_length": len(real["chronicle"])}}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"live-results-{RUN}.json")
    open(path, "w").write(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("all_pass", "test_verdict", "test_replay", "real_quest_001_untouched")}, indent=2))
    print("results:", path)
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
