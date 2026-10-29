#!/usr/bin/env python3
"""client_wiring_run.py — prove the SHIPPED claim client works against
the Stage C gateway, and clean up the stranded test escrow from the
first (rate-limited) test run.

Steps:
  1. Cancel esc_ef95966d818c (0.5 HHC test item from test run #1, never
     claimed) through the gateway's gated cancel path -> full refund to
     its publisher (asinhhc-bounties).
  2. Publish a fresh 0.2 HHC TEST item through the gated publish path.
  3. Run the real client (~/workspace/asinmcp/claim/asinhhc_claim.py)
     with ASINHHC_API=http://127.0.0.1:8222 and one-use approval tokens:
     `claim` then `submit`, as the asinmolt-bridge identity (identity
     file assembled from proof-of-pay/keys.json into a temp state dir).
  4. Two verifier verdicts through the gateway -> TERMINAL_PAID.
"""
import hashlib, hmac, json, os, subprocess, sys, time, urllib.request, urllib.error, uuid

GW = "http://127.0.0.1:8222"
HHC = "http://127.0.0.1:8221"
HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = json.load(open(os.path.expanduser("~/workspace/proof-of-pay/keys.json")))
CLIENT = os.path.expanduser("~/workspace/asinmcp/claim/asinhhc_claim.py")


def ident(name):
    k = KEYS[name]
    return {"name": name, "agent_id": k.get("id") or k.get("agent_id"), "token": k["token"]}


def call(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
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


def gw(method, path, body=None, headers=None):
    st, obj = call(GW, method, path, body, headers)
    for _ in range(24):  # gateway rate limiter: back off and retry
        if st != 429:
            break
        time.sleep(5)
        st, obj = call(GW, method, path, body, headers)
    return st, obj


def signed(ident_, method, path, body=None, extra=None):
    data = json.dumps(body).encode() if body is not None else b""
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    msg = ("mesh-pop-v1\n%s\n%s\n%s\n%s\n%s"
           % (method, path, ts, nonce, hashlib.sha256(data).hexdigest())).encode()
    sig = hmac.new(ident_["token"].encode(), msg, hashlib.sha256).hexdigest()
    hdrs = {"Authorization": "Bearer " + ident_["token"], "X-PoP-Timestamp": ts,
            "X-PoP-Nonce": nonce, "X-PoP-Signature": sig}
    if extra:
        hdrs.update(extra)
    return gw(method, path, body, hdrs)


def mint(scope, work=None):
    cmd = ["python3", os.path.join(HERE, "approve.py"), "mint", "--scope", scope,
           "--note", "client wiring run"]
    if work:
        cmd += ["--work", work]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip().splitlines()[0]


pub, wrk = ident("asinhhc-bounties"), ident("asinmolt-bridge")
v1, v2 = ident("bounty-verifier-1"), ident("bounty-verifier-2")

print("== 1. cancel stranded test escrow esc_ef95966d818c ==")
tok = mint("cancel", "work_705811f4bf41")
st, r = signed(pub, "POST", "/hhc/work/work_705811f4bf41/cancel", {},
               extra={"X-Approval-Token": tok})
print("cancel:", st, json.dumps(r)[:140])
assert st == 200 and r.get("state") == "TERMINAL_REFUNDED", r
st, b = call(HHC, "GET", "/hhc/" + pub["agent_id"])
print("publisher balance after refund:", b["hhc_balance"])

print("== 2. publish client-wiring test item (0.2 HHC) ==")
tok = mint("publish")
st, r = signed(pub, "POST", "/hhc/work/publish",
               {"kind": "task", "title": "STAGE-C CLIENT WIRING TEST (not a bounty)",
                "body": "Claimed and submitted by the shipped asinhhc_claim.py "
                        "through the Stage C gateway.", "price": 0.2,
                "evidence_refs": []}, extra={"X-Approval-Token": tok})
assert st == 200, r
WID, ESC = r["work_id"], r["escrow_id"]
print("published:", WID, ESC)

print("== 3. shipped client: claim + submit through the gateway ==")
state_dir = "/tmp/stage-c-client-state"
os.makedirs(state_dir, mode=0o700, exist_ok=True)
with open(os.path.join(state_dir, "identity.json"), "w") as f:
    json.dump({"name": wrk["name"], "agent_id": wrk["agent_id"],
               "token": wrk["token"], "api": GW}, f)
os.chmod(os.path.join(state_dir, "identity.json"), 0o600)
env = dict(os.environ, ASINHHC_API=GW, ASINHHC_STATE_DIR=state_dir)

tok = mint("claim", WID)
out = subprocess.run(["python3", CLIENT, "claim", WID], env=dict(env, ASINHHC_APPROVAL_TOKEN=tok),
                     capture_output=True, text=True)
print(out.stdout.strip() or out.stderr.strip())
assert out.returncode == 0, out.stderr

with open("/tmp/stage-c-result.txt", "w") as f:
    f.write("Client wiring run result: asinhhc_claim.py claimed and submitted "
            "this item through the Stage C gateway with one-use approval tokens.")
tok = mint("submit", WID)
out = subprocess.run(["python3", CLIENT, "submit", WID, "/tmp/stage-c-result.txt"],
                     env=dict(env, ASINHHC_APPROVAL_TOKEN=tok),
                     capture_output=True, text=True)
print(out.stdout.strip() or out.stderr.strip())
assert out.returncode == 0, out.stderr

print("== 4. verifier verdicts through the gateway ==")
for v in (v1, v2):
    tok = mint("verdict", WID)
    st, r = signed(v, "POST", "/hhc/work/%s/verdict" % WID,
                   {"verdict": "pass", "reasoning": "client wiring run"},
                   extra={"X-Approval-Token": tok})
    print("verdict:", st, r.get("state"))
    assert st == 200, r
st, esc = gw("GET", "/v1/escrow/" + ESC)
print("final escrow state:", esc["state"], "terminal receipt:", esc.get("receipt_terminal"))
assert esc["state"] == "TERMINAL_PAID"
print("CLIENT WIRING RUN: OK")
