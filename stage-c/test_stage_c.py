#!/usr/bin/env python3
"""test_stage_c.py — end-to-end proof for the Stage C gateway.

Phases (all against the REAL local services, via the gateway on :8222):
  A. Public read surface: health, bounties w/ live states, ledger head
     cross-checked against the mesh API, signed checkpoint verified
     against the pinned fleet pubkey, registry snapshot verified.
  B. Token separation (P0-AUTH spec section 4): a Supabase SOCIAL token
     must not be able to mutate escrow — (a) via the gateway without an
     approval token, (b) via the gateway WITH one (upstream PoP rejects;
     the approval is NOT consumed), (c) directly against the escrow
     service. Plus (d): a valid mesh PoP credential without an approval
     token is refused by the gate and escrow state does not move.
  C. Gated write path: the operator's stored publisher/worker/verifier
     identities (proof-of-pay/keys.json) act through the gateway;
     publish -> claim -> submit -> verdict x2 on a 0.5 HHC TEST item
     settles TERMINAL_PAID with exact amounts; token misuse (reuse,
     wrong work) is refused.

Run:  python3 test_stage_c.py [--base http://127.0.0.1:8222]
Exit code 0 = all non-skipped checks passed. Skips are reported, never
silently counted as passes.
"""
import hashlib, hmac, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

GW = "http://127.0.0.1:8222"
if "--base" in sys.argv:
    GW = sys.argv[sys.argv.index("--base") + 1].rstrip("/")
HHC = "http://127.0.0.1:8221"
MESH = "http://127.0.0.1:8220"
SUPA = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser("~/workspace/asinmolt-node"))
import ed25519  # noqa: E402

PASS, FAIL, SKIP = [], [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail))


def skip(name, why):
    SKIP.append(name)
    print("SKIP %s (%s)" % (name, why))


def call_raw(base, method, path, body=None, headers=None, raw_headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if raw_headers:
        hdrs.update(raw_headers)
    r = urllib.request.Request(base + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except Exception as e:
        return -1, {"error": str(e)}


def call(base, method, path, body=None, headers=None, raw_headers=None):
    """call_raw + polite retry on the gateway's own 429 rate limiter
    (burst 20 writes, then 12/min — a real client backs off; refusal
    checks below assert the FINAL code once the limiter lets the
    request through to the gate). Direct-upstream calls don't retry."""
    st, obj = call_raw(base, method, path, body, headers, raw_headers)
    if base == GW:
        for _ in range(24):
            if st != 429:
                break
            time.sleep(5)
            st, obj = call_raw(base, method, path, body, headers, raw_headers)
    return st, obj


def pop_headers(token, method, path, body_obj):
    data = json.dumps(body_obj).encode() if body_obj is not None else b""
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    msg = ("mesh-pop-v1\n%s\n%s\n%s\n%s\n%s"
           % (method, path, ts, nonce, hashlib.sha256(data).hexdigest())).encode()
    sig = hmac.new(token.encode(), msg, hashlib.sha256).hexdigest()
    return {"Authorization": "Bearer " + token, "X-PoP-Timestamp": ts,
            "X-PoP-Nonce": nonce, "X-PoP-Signature": sig}


def register(base, name):
    pubkey = "pop-" + uuid.uuid4().hex
    st, r1 = call(base, "POST", "/agents/register",
                  {"name": name, "model": "stage-c-test", "role": "stage-c e2e test",
                   "pubkey": pubkey})
    assert st == 200, ("register", name, st, r1)
    aid, ch = r1["agent_id"], r1["challenge"]
    resp = hmac.new(hashlib.sha256(pubkey.encode()).digest(),
                    ("mesh-register-v1:%s:%s" % (aid, ch)).encode(),
                    hashlib.sha256).hexdigest()
    st, r2 = call(base, "POST", "/agents/activate",
                  {"agent_id": aid, "challenge_response": resp})
    assert st == 200, ("activate", name, st, r2)
    return {"name": name, "agent_id": aid, "token": r2["token"]}


def signed(base, ident, method, path, body=None, extra=None):
    hdrs = pop_headers(ident["token"], method, path, body)
    if extra:
        hdrs.update(extra)
    return call(base, method, path, body, headers=hdrs)


def mint(scope, work=None, ttl=3600):
    cmd = ["python3", os.path.join(HERE, "approve.py"), "mint",
           "--scope", scope, "--ttl", str(ttl), "--note", "stage-c e2e test"]
    if work:
        cmd += ["--work", work]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip().splitlines()[0]


def token_used(tok):
    h = hashlib.sha256(tok.encode()).hexdigest()
    with open(os.path.join(HERE, "approvals.json")) as f:
        rec = json.load(f)["tokens"].get(h, {})
    return bool(rec.get("used_at"))


RAND = uuid.uuid4().hex[:6]

# ------------------------------------------------------------------ A ----
print("== A. public read surface ==")
st, h = call(GW, "GET", "/v1/health")
check("A1 health ok", st == 200 and h.get("ok") is True, "mesh=%s" % h.get("mesh", {}).get("mesh"))
st, b = call(GW, "GET", "/v1/bounties")
states = {e["escrow_id"]: e.get("live_state") for e in b.get("bounties", [])}
check("A2 bounties carry live states", st == 200 and len(states) >= 5
      and all(s not in (None, "UNKNOWN (escrow service unreachable)") for s in states.values()),
      str(states))
st, head = call(GW, "GET", "/v1/ledger/head")
stm, mh = call(MESH, "GET", "/health")
st2, led = call(MESH, "GET", "/ledger?since=%d" % (mh["ledger_height"] - 1))
real_head = led["entries"][-1]["hash"] if led.get("entries") else None
check("A3 ledger head matches mesh", st == 200 and head["height"] == mh["ledger_height"]
      and head["head_hash"] == real_head, "height=%s head=%s" % (head.get("height"), str(head.get("head_hash"))[:12]))
st, cp = call(GW, "GET", "/v1/ledger/checkpoint")
canon = json.dumps(cp["checkpoint"], sort_keys=True, separators=(",", ":")).encode()
pinned = open(os.path.expanduser("~/workspace/asinmcp/keys/ace-lattice.pub")).read().strip()
check("A4 checkpoint signature verifies vs pinned fleet key",
      st == 200 and cp["pubkey"] == pinned and ed25519.verify(cp["pubkey"], canon, cp["signature"]),
      "height=%s" % cp["checkpoint"]["height"])
st, reg = call(GW, "GET", "/v1/registry")
check("A5 registry snapshot verified", st == 200 and reg["snapshot"]["signature_valid"]
      and reg["snapshot"]["sha256_matches_sigfile"] and reg["records"] >= 42,
      "records=%s" % reg.get("records"))
st, esc = call(GW, "GET", "/v1/escrow/esc_bcc31cb52fcf")
check("A6 BOUNTY-05 escrow read", st == 200 and esc["state"] == "FUNDED", esc.get("state", ""))

# ------------------------------------------------------- setup for B/C ----
# Registration through the gateway is proven separately (the claim
# client's register flow is path-identical), but the mesh's 5/hour/IP
# registration burst limit is saturated by live fleet traffic, so the
# settlement phases use the operator's stored identities from
# proof-of-pay/keys.json (publisher / worker / two verifiers) — the same
# identities that fund and verify the real bounties.
print("== setup: operator identities + test item via gateway ==")
KEYS = json.load(open(os.path.expanduser("~/workspace/proof-of-pay/keys.json")))


def load_ident(name):
    k = KEYS[name]
    return {"name": name, "agent_id": k.get("id") or k.get("agent_id"),
            "token": k["token"]}


pub = load_ident("asinhhc-bounties")     # publisher (3.0 HHC)
wrk = load_ident("asinmolt-bridge")      # worker
v1 = load_ident("bounty-verifier-1")     # verifier 1
v2 = load_ident("bounty-verifier-2")     # verifier 2
hb_ok = True
for ident in (pub, wrk, v1, v2):
    st, _r = signed(GW, ident, "POST", "/agents/heartbeat", {})
    if st != 200:
        time.sleep(5)
        st, _r = signed(GW, ident, "POST", "/agents/heartbeat", {})
    hb_ok = hb_ok and st == 200
check("S0 stored identities authenticate through gateway", hb_ok)

tok_pub = mint("publish")
st, r = signed(GW, pub, "POST", "/hhc/work/publish",
               {"kind": "task", "title": "STAGE-C TEST ITEM (not a bounty)",
                "body": "Stage C gateway end-to-end test item. No real work.",
                "price": 0.5, "evidence_refs": []},
               extra={"X-Approval-Token": tok_pub})
check("S1 gated publish works", st == 200 and r.get("state") == "FUNDED", json.dumps(r)[:160])
WID, ESC = r["work_id"], r["escrow_id"]
check("S2 publish approval consumed on success", token_used(tok_pub))

# ------------------------------------------------------------------ B ----
print("== B. token separation ==")
st, before = call(GW, "GET", "/v1/escrow/" + ESC)
st, r = signed(GW, wrk, "POST", "/hhc/work/%s/claim" % WID, {})
err = (r.get("error") or {}).get("code", "")
check("B1 PoP claim without approval token refused", st == 403 and err.startswith("APPROVAL"),
      "st=%s code=%s" % (st, err))
st, after = call(GW, "GET", "/v1/escrow/" + ESC)
check("B2 escrow unmoved by refused claim", before["state"] == after["state"] == "FUNDED"
      and after.get("worker") is None)

social = None
try:
    stc, rc = call(SUPA, "POST", "/connect",
                   {"handle": "stagecsep" + RAND, "display_name": "Stage C Separation Test",
                    "platform": "test"})
    social = (rc.get("credential") or {}).get("token")
except Exception as e:
    print("connect error:", e)
if social:
    st, r = call(GW, "POST", "/hhc/work/%s/claim" % WID, {},
                 headers={"Authorization": "Bearer " + social})
    err = (r.get("error") or {}).get("code", "")
    check("B3 social token, no approval -> gate refuses", st == 403 and err.startswith("APPROVAL"),
          "st=%s code=%s" % (st, err))
    tok_b = mint("claim", WID)
    st, r = call(GW, "POST", "/hhc/work/%s/claim" % WID, {},
                 headers={"Authorization": "Bearer " + social,
                          "X-Approval-Token": tok_b})
    check("B4 social token + valid approval -> upstream rejects (not 200)",
          st != 200, "st=%s" % st)
    check("B5 approval NOT consumed by rejected attempt", not token_used(tok_b))
    st, r = call(HHC, "POST", "/hhc/work/%s/claim" % WID, {},
                 headers={"Authorization": "Bearer " + social})
    check("B6 social token vs escrow service directly -> rejected", st != 200, "st=%s" % st)
else:
    for n in ("B3", "B4", "B5", "B6"):
        skip(n, "could not obtain a Supabase social token")

# ------------------------------------------------------------------ C ----
print("== C. gated write path end-to-end ==")
tok_claim = mint("claim", WID)
st, r = signed(GW, wrk, "POST", "/hhc/work/%s/claim" % WID, {},
               extra={"X-Approval-Token": tok_claim})
check("C1 gated claim works", st == 200, json.dumps(r)[:160])
st, r = signed(GW, wrk, "POST", "/hhc/work/%s/claim" % WID, {},
               extra={"X-Approval-Token": tok_claim})
err = (r.get("error") or {}).get("code", "")
check("C2 approval token reuse refused", st == 403 and err == "APPROVAL_ALREADY_USED",
      "st=%s code=%s" % (st, err))

tok_wrong = mint("submit", "work_000000000000")
st, r = signed(GW, wrk, "POST", "/hhc/work/%s/submit" % WID, {"result": "x"},
               extra={"X-Approval-Token": tok_wrong})
err = (r.get("error") or {}).get("code", "")
check("C3 wrong-work approval refused", st == 403 and err == "APPROVAL_WORK_MISMATCH",
      "st=%s code=%s" % (st, err))

tok_sub = mint("submit", WID)
st, r = signed(GW, wrk, "POST", "/hhc/work/%s/submit" % WID,
               {"result": "Stage C test result: gateway write path exercised end to end."},
               extra={"X-Approval-Token": tok_sub})
check("C4 gated submit works", st == 200, json.dumps(r)[:160])

for v, nm in ((v1, "C5"), (v2, "C6")):
    tok_v = mint("verdict", WID)
    st, r = signed(GW, v, "POST", "/hhc/work/%s/verdict" % WID,
                   {"verdict": "pass", "reasoning": "stage-c e2e test verdict"},
                   extra={"X-Approval-Token": tok_v})
    check(nm + " gated verdict works", st == 200, json.dumps(r)[:120])

st, esc = call(GW, "GET", "/v1/escrow/" + ESC)
check("C7 escrow TERMINAL_PAID", st == 200 and esc["state"] == "TERMINAL_PAID", esc["state"])
st, wh = call(HHC, "GET", "/hhc/" + wrk["agent_id"])
rel = [x for x in wh["hhc_history"] if x["kind"] == "escrow_release"]
check("C8 worker paid exactly 0.45 (90% of 0.5)", len(rel) == 1 and abs(rel[0]["amount"] - 0.45) < 1e-9,
      str(rel))
st, vh = call(HHC, "GET", "/hhc/" + v1["agent_id"])
fees = [x for x in vh["hhc_history"] if x["kind"] == "verifier_fee"]
check("C9 verifier paid exactly 0.025 from fee pool", len(fees) == 1 and abs(fees[0]["amount"] - 0.025) < 1e-9,
      str(fees))
check("C10 terminal receipt present", bool(esc.get("receipt_terminal")), str(esc.get("receipt_terminal"))[:16])

print("\n== SUMMARY: %d pass, %d fail, %d skip ==" % (len(PASS), len(FAIL), len(SKIP)))
if FAIL:
    print("failed:", FAIL)
sys.exit(1 if FAIL else 0)
