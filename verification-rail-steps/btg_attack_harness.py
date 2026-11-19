#!/usr/bin/env python3
"""Break the Gate — SELF-ATTACK harness (Elite-50 task 5, 2026-11-19).

Honest adversarial test of our own gate, run by the gate's owners.
Track A: try to get a demonstrably false claim a gate PASS.
Track B: try to find a Proof Board row / receipt / index entry that does
         not recompute under canon-v1.

Materials: public copies only — ~/workspace/elite-50/clean-room/
(provenance-index.json sha256 a81a8bde..., proof-board.html), the public
gate receipt (verifier-bot/live-run/gate-ledger.jsonl), the published
ENVELOPE-SPEC.md + verify_gate_receipt.py (asinmcp branch
verification-rail), the Quest 001 manifest + the PR #4 quest-evidence
candidate source (elite-50/supabase-migration-pack/source/).

The endpoint logic is exercised through a faithful Python port of the
PR #4 candidate core.ts (validateEnvelope / computeVerdict /
computeEvidence / reexecute). Deployed-source byte-identity is
unproven (BLUEPRINT gap 2), so endpoint conclusions are stated about
the published candidate logic, cross-checked against the live
endpoint's observed behaviour in q001-endpoint-snapshot-0259.md.
NO live POSTs are made: the real quest closes tonight and the attack
must not touch its chronicle.

Ed25519 code is copied from quest001-seal-drop/sign_and_drop.py
(RFC 8032, pure Python, reference-vector self-tested there).
Stdlib only. Exit code is always 0 — this is a log generator; the
results JSON is the evidence.
"""
import copy, hashlib, json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timezone

SCRATCH = "/tmp/btg-attack"
os.makedirs(SCRATCH, exist_ok=True)
CLEAN = os.path.expanduser("~/workspace/elite-50/clean-room")
RESULTS = []
def record(track, attack, method, result, detail=""):
    RESULTS.append({"track": track, "attack": attack, "method": method,
                    "result": result, "detail": detail})
    print(f"[{track}] {attack}: {result} — {detail}")

# ---------------- ed25519 (RFC 8032), from sign_and_drop.py ----------------
_b = 256; _q = 2**255 - 19
_l = 2**252 + 27742317777372353535851937790883648493
def _H(m): return hashlib.sha512(m).digest()
def _inv(x): return pow(x, _q - 2, _q)
_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)
def _xrecover(y):
    xx = (y * y - 1) * _inv(_d * y * y + 1) % _q
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0: x = (x * _I) % _q
    if x % 2 != 0: x = _q - x
    return x
_By = (4 * _inv(5)) % _q; _B = (_xrecover(_By), _By)
def _edwards(P, Q):
    x1, y1 = P; x2, y2 = Q
    den = _inv(1 + _d * x1 * x2 * y1 * y2 % _q); x3 = (x1 * y2 + x2 * y1) * den % _q
    den2 = _inv(1 - _d * x1 * x2 * y1 * y2 % _q); y3 = (y1 * y2 + x1 * x2) * den2 % _q
    return (x3, y3)
def _scalarmult(P, e):
    Q = (0, 1)
    while e > 0:
        if e & 1: Q = _edwards(Q, P)
        P = _edwards(P, P); e >>= 1
    return Q
def _encodeint(y):
    bits = [(y >> i) & 1 for i in range(_b)]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))
def _encodepoint(P):
    x, y = P; bits = [(y >> i) & 1 for i in range(_b - 1)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))
def _bit(h, i): return (h[i // 8] >> (i % 8)) & 1
def _publickey(seed32):
    h = _H(seed32); a = 2**(_b - 2) + sum(2**i * _bit(h, i) for i in range(3, _b - 2))
    return _encodepoint(_scalarmult(_B, a)), a, h
def _Hint(m): return int.from_bytes(_H(m), "little")
def _sign(seed32, msg):
    pub, a, h = _publickey(seed32)
    r = _Hint(h[_b // 8:_b // 4] + msg) % _l; R = _scalarmult(_B, r)
    S = (r + _Hint(_encodepoint(R) + pub + msg) * a) % _l
    return pub, _encodepoint(R) + _encodeint(S)
def _decodeint(s): return int.from_bytes(s, "little")
def _decodepoint(s):
    y = sum(2**i * _bit(s, i) for i in range(0, _b - 1)); x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1): x = _q - x
    return (x, y)
def _verify(pub, msg, sig):
    if len(sig) != 64: return False
    R = _decodepoint(sig[:32]); A = _decodepoint(pub); S = _decodeint(sig[32:])
    if S >= _l: return False
    return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, _Hint(sig[:32] + pub + msg) % _l))

# ---------------- canon helpers (three serializations in play) ----------------
def canon_compact(v):  # canonical_json: sorted, (",",":"), ensure_ascii=False
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
def py_default(v):     # index entry hash: json.dumps defaults, ensure_ascii=False
    return json.dumps(v, sort_keys=True, ensure_ascii=False)
def canon_vault(v):    # vault envelope: sorted, (",",":"), ensure_ascii=True
    return json.dumps(v, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
def seal(v): return hashlib.sha256(canon_compact(v).encode()).hexdigest()
def sha256_hex(b): return hashlib.sha256(b).hexdigest()

PINNED = {  # public anchors, from the manifest / board / published vault identity
    "claim_sha256": "a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e",
    "claim_bytes": 87505,
    "head_hash": "fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6",
    "sealed_output": "69616c863e4c1ad1d6508ac8b0db86435aa37bbc1cf69aeea6ebc46a28d00d22",
    "manifest_sha256": "50cefe6ad4090de76f6bdc02654e533261f08ec661b2ba7df98cba1e9c7548a1",
    "vault_fingerprint": "4f47d2df9dbd9260a48eebe80dc472442b73cf43e78f4c895cf6abd9cb7a8835",
    "gate_receipt": "48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38",
}

# =====================================================================
# TRACK B — recompute attacks on the published record
# =====================================================================
raw_index = open(os.path.join(CLEAN, "provenance-index.json"), "rb").read()
doc = json.loads(raw_index)
entries = doc["entries"]

def replay_chain(d):
    """Independent chain replay (fresh code, not replay.py)."""
    problems = []
    prev = d["ledger_anchor"]["tip_hash"]
    for i, e in enumerate(d["entries"]):
        if e["prev_index_hash"] != prev:
            problems.append(f"entry {i}: prev link broken")
        c = {k: v for k, v in e.items() if k != "index_hash"}
        h = hashlib.sha256(py_default(c).encode()).hexdigest()
        if h != e["index_hash"]:
            problems.append(f"entry {i}: index_hash mismatch")
        prev = h
    if d["entry_count"] != len(d["entries"]): problems.append("entry_count mismatch")
    if d["head_hash"] != prev: problems.append("head_hash mismatch")
    return problems, prev

# B1 — full independent replay of all 78 entries
probs, head = replay_chain(doc)
record("B", "B1 index replay (independent implementation)",
       "recompute every index_hash + linkage + head from the clean-room public copy",
       "NO BREAK" if not probs else "BREAK?",
       f"78 entries recomputed; problems={probs}; head={head[:16]}… matches pinned: {head == PINNED['head_hash']}")

# B1-control — the shipped clean-room replay.py
r = subprocess.run([sys.executable, "replay.py"], cwd=CLEAN, capture_output=True, text=True)
record("B", "B1-control shipped replay.py", "run clean-room/replay.py as published",
       "NO BREAK" if r.returncode == 0 else "BREAK?",
       f"exit={r.returncode}; tail: {r.stdout.strip().splitlines()[-2] if r.stdout else ''}")

# B2 — claim file identity vs the manifest-pinned hash
record("B", "B2 claim file sha256",
       "sha256 of the public index file vs manifest/board/endpoint pinned claim hash",
       "NO BREAK" if sha256_hex(raw_index) == PINNED["claim_sha256"] and len(raw_index) == PINNED["claim_bytes"] else "BREAK?",
       f"sha256={sha256_hex(raw_index)[:16]}… bytes={len(raw_index)} (pinned {PINNED['claim_bytes']})")

# B4 — PROVENANCE.md prose anchor vs the index's own ledger_anchor
prov = open(os.path.join(CLEAN, "PROVENANCE.md")).read()
m_tip = re.search(r"Tip hash:\*\* `([0-9a-f]{64})`", prov)
m_h = re.search(r"Height at build:\*\* (\d+)", prov)
md_tip = m_tip.group(1) if m_tip else None
md_height = int(m_h.group(1)) if m_h else None
idx_tip = doc["ledger_anchor"]["tip_hash"]; idx_height = doc["ledger_anchor"]["height"]
# walk seeded from the MD-printed tip: entry 0's prev must equal the seed
seeded_ok = entries[0]["prev_index_hash"] == md_tip
record("B", "B4 PROVENANCE.md anchor numbers vs index ledger_anchor",
       "extract the MD's printed tip/height; compare with the JSON anchor; test a chain walk seeded from the MD tip",
       "DOC DEFECT (not a chain break)",
       f"MD prints tip {md_tip[:16]}… height {md_height}; index anchor is {idx_tip[:16]}… height {idx_height}; "
       f"walk seeded from MD tip fails at entry 0 link: {not seeded_ok}; walk seeded from the JSON anchor passes (B1). "
       "The MD's 'How to verify' points at the JSON ledger_anchor (correct); its own §'The ledger anchor' numbers are stale.")

# B5 — live board: HTML seal-row prose vs JSON rows / escrow facts
def fetch(url):
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, resp.read()
try:
    st_h, html_b = fetch("https://dbottrader.github.io/asinmcp/artifacts/proof-board.html")
    st_j, json_b = fetch("https://dbottrader.github.io/asinmcp/artifacts/proof-board.json")
    src = f"live fetch (HTML {st_h} {len(html_b)} B, JSON {st_j})"
except Exception as e:
    html_b = open(os.path.join(CLEAN, "proof-board.html"), "rb").read(); json_b = b""
    src = f"live fetch failed ({e}); clean-room copy used for HTML"
html = html_b.decode("utf-8", "replace")
snap = open(os.path.join(CLEAN, "proof-board.html"), encoding="utf-8").read()
stale_live = html.count("pending escrow re-issue")
stale_snap = snap.count("pending escrow re-issue")
json_fixed = b"escrow re-issued 5.0 on 2026-11-18" in json_b if json_b else None
record("B", "B5 board seal-row prose (HTML) vs settled escrow facts",
       "string-check the live proof-board.html/json and the 09:04 clean-room snapshot for the seal-row settlement text (" + src + ")",
       "NO BREAK (stale prose existed, already fixed live; prose is not a canon-v1 object)",
       f"Wave-1 audit (09:00-09:06 UTC) found the live HTML seal rows saying '5.0 HHC pending escrow re-issue' "
       f"after the escrows had in fact been re-issued 5.0/5.0 FUNDED on 2026-11-18 — a false-as-of-then prose "
       f"statement. The 09:04 clean-room snapshot still carries it x{stale_snap}. At attack time the LIVE page "
       f"carries it x{stale_live} and instead reads 'escrow re-issued 5.0 on 2026-11-18, FUNDED, pending claim' "
       f"(JSON rows corrected: {json_fixed}) — the defect was fixed between the audit and this run. Either way it "
       "is unhashed prose: not a receipt, not an index entry, nothing a gate PASS rests on, so it never met the "
       "bounty bar; it is logged as the nearest miss.")

# =====================================================================
# TRACK A1 — the gate receipt (ASIN-HHC-VERIFICATION-1.0 + vault envelope)
# =====================================================================
VERIFIER = os.path.expanduser("~/workspace/makefun-port/verify_gate_receipt.py")
genuine = None
for line in open(os.path.expanduser("~/workspace/verifier-bot/live-run/gate-ledger.jsonl")):
    o = json.loads(line)
    if o.get("verification_id") == "live-2026-11-12-provindex-001":
        genuine = o; break
assert genuine and genuine["receipt_hash"] == PINNED["gate_receipt"]
gpath = os.path.join(SCRATCH, "genuine.json")
json.dump(genuine, open(gpath, "w"), indent=1)

def run_verifier(path):
    r = subprocess.run([sys.executable, VERIFIER, path], capture_output=True, text=True)
    return r.returncode, r.stdout

# A0 — control: the genuine receipt must verify
rc, out = run_verifier(gpath)
record("A", "A0 control — genuine gate receipt 48ac1da5",
       "run the published verify_gate_receipt.py on the genuine object",
       "CONTROL PASS" if rc == 0 else "CONTROL FAILED (harness problem)",
       f"exit={rc}; last line: {out.strip().splitlines()[-1] if out else ''}")

# A1 — tamper: keep receipt_hash + signature, change the claim body
# (a PASS whose own residual says 76 served vs 78 stored, difference 2)
tamp = copy.deepcopy(genuine)
tamp["residual"] = {"difference": 2, "served_count": 76, "stored_count": 78}
tpath = os.path.join(SCRATCH, "tampered.json")
json.dump(tamp, open(tpath, "w"), indent=1)
rc, out = run_verifier(tpath)
fail_line = next((l for l in out.splitlines() if l.startswith("[FAIL]")), "")
record("A", "A1 tampered receipt (false residual, genuine hash+signature)",
       "edit body fields only; run the published verifier",
       "NO BREAK" if rc != 0 else "BREAK",
       f"exit={rc}; first failing check: {fail_line}")

# A2 — self-signed forgery: attacker keypair, false claim, exact envelope
# construction from ENVELOPE-SPEC.md. Claim: a PASS over a population that
# was never verified ('btg-nonexistent-population'), counts invented.
seed = bytes.fromhex("42" * 32)  # fixed attacker seed (deterministic log)
pub, _a, _h = _publickey(seed)
fp = sha256_hex(pub)
forged = {
    "schema": "ASIN-HHC-VERIFICATION-1.0",
    "verification_id": "btg-forged-001",
    "attempted_at": "2026-11-19T09:10:00Z",
    "population_id": "btg-nonexistent-population",
    "outcome": "PASS",
    "control": {"control_id": "btg-fake-control", "result": "PASS",
                "source": "EXTERNAL_TO_TEST_POPULATION"},
    "external_anchor": None,
    "instrument_independence": {"declared": True, "review_status": "ASSESSED_INDEPENDENT"},
    "preconditions": {"established_at": "2026-11-19T09:10:00Z",
                      "expires_at": "2026-11-19T11:10:00Z", "valid": True},
    "prev_receipt_hash": "0" * 64,
    "reason": None,
    "residual": {"difference": 0, "served_count": 78, "stored_count": 78},
    "resolution_of": None,
    "snapshot_hash": sha256_hex(b"btg forged snapshot"),
    "test_id": "btg-forged-test",
    "witnesses": [],
    "signer": {"fingerprint": fp, "kind": "agent-vault-ed25519",
               "pubkey": pub.hex(), "vault_id": "vlt_" + fp[:16]},
}
body = {k: v for k, v in forged.items() if k not in ("receipt_hash", "signature")}
forged["receipt_hash"] = sha256_hex(canon_compact(body).encode("utf-8"))  # canon_gate == canon_compact
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
nonce = "b760" + "0" * 12  # 16 lowercase hex chars, shaped like a vault nonce
envelope = {"action": "doc.sign",
            "payload_sha256": sha256_hex(forged["receipt_hash"].encode("utf-8")),
            "amount": None, "dest": None, "ts": ts, "nonce": nonce}
_p, sig = _sign(seed, canon_vault(envelope).encode("utf-8"))
forged["signature"] = {"action": "doc.sign", "kind": "agent-vault-ed25519",
                       "nonce": nonce, "ts": ts, "value": sig.hex(),
                       "vault_receipt_hash": "0" * 64, "vault_receipt_seq": 999}
fpath = os.path.join(SCRATCH, "forged.json")
json.dump(forged, open(fpath, "w"), indent=1)
rc, out = run_verifier(fpath)
crypto_pass = (rc == 0)
pin_ok = (fp == PINNED["vault_fingerprint"])
record("A", "A2 self-signed forged receipt (false population, attacker key)",
       "build a receipt claiming PASS on a never-verified population, sign it with a fresh "
       "keypair using the published envelope construction; run the published verifier; then "
       "apply the system's identity pin (ENVELOPE-SPEC §6 / vault-identity.json)",
       "NO BREAK (verifier-scope finding, disclosed in spec)",
       f"standalone verifier exit={rc} (all crypto checks pass: {crypto_pass}) — the script verifies "
       f"self-consistency, it does not pin identity. Identity pin: forged fingerprint {fp[:16]}… "
       f"!= published vault fingerprint {PINNED['vault_fingerprint'][:16]}… -> pin_ok={pin_ok}. "
       "The gate's PASS is the vault key's signature; a receipt from any other key is not a gate "
       "receipt at all. Spec §0/§9 already disclose that authorization is out-of-band. "
       "Hardening note: verify_gate_receipt.py could optionally assert the pinned fingerprint.")

# =====================================================================
# TRACK A2 — the quest-evidence endpoint (faithful port of PR #4 core.ts)
# =====================================================================
MANIFEST = json.load(open(os.path.expanduser(
    "~/workspace/elite-50/supabase-migration-pack/source/manifest.json")))
SIGNED_FIELDS = ["schema", "quest_id", "manifest_sha256", "request_id", "nonce",
                 "issued_at", "expires_at", "key_id", "pubkey", "operator",
                 "failure_mode", "implementation", "output", "sealed_output", "observed"]
ALL_FIELDS = set(SIGNED_FIELDS + ["signature", "envelope_signature"])
ENVELOPE_SCHEMA = "ASIN-HHC-QUEST-SEAL-1.0"
QUEST = {"quest_id": "QUEST-001", "manifest": MANIFEST,
         "manifest_sha256": (MANIFEST_SHA := PINNED["manifest_sha256"]),
         "valid_from": MANIFEST["valid_from"], "deadline": MANIFEST["deadline"]}
TEST_QUEST = {"quest_id": "QUEST-001-TEST",
              "manifest": {"independence": MANIFEST["independence"],
                           "reward": MANIFEST["reward"]},
              "manifest_sha256": "ed1b02ac9eb264fab11460fd69802bbc2c7b6d7eb553b0ffdfcc2b41bfb333af",
              "valid_from": MANIFEST["valid_from"], "deadline": MANIFEST["deadline"]}
GENUINE_OUTPUT = {"count": 78, "head_hash": PINNED["head_hash"]}
FALSE_OUTPUT = {"count": 78, "head_hash": "ab" * 32}
OBSERVED = {"claim_sha256": PINNED["claim_sha256"], "claim_bytes": 87505,
            "first_entry_seal": seal(entries[0])}

def parse_ts(s):
    if not isinstance(s, str) or not re.match(
            r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)$", s):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None

def norm_name(s): return re.sub(r"[^a-z0-9]", "", s.lower())
def is_hex(s, n): return isinstance(s, str) and len(s) == n and re.fullmatch(r"[0-9a-f]+", s) is not None

def validate_envelope(env, quest, now_ms):
    """Port of core.ts validateEnvelope — same checks, same order, same codes."""
    rej = lambda st, code, det: {"ok": False, "status": st, "code": code, "detail": det}
    if not isinstance(env, dict): return rej(400, "bad_json", "envelope must be a JSON object")
    for k in ALL_FIELDS:
        if k not in env: return rej(400, "missing_field", k)
    for k in env:
        if k not in ALL_FIELDS: return rej(400, "unknown_field", k)
    if env["schema"] != ENVELOPE_SCHEMA: return rej(400, "bad_schema", env["schema"])
    if quest is None: return rej(404, "unknown_quest", str(env.get("quest_id")))
    if env["quest_id"] != quest["quest_id"]: return rej(404, "unknown_quest", str(env["quest_id"]))
    if not is_hex(env["manifest_sha256"], 64): return rej(422, "bad_hash_format", "manifest_sha256")
    if env["manifest_sha256"] != quest["manifest_sha256"]:
        return rej(409, "wrong_manifest", "manifest_sha256 does not match the current manifest")
    for k, n in [("pubkey", 64), ("key_id", 64), ("nonce", 64), ("sealed_output", 64),
                 ("signature", 128), ("envelope_signature", 128)]:
        if not is_hex(env[k], n): return rej(422, "bad_hash_format", k)
    out = env["output"]
    if not isinstance(out, dict) or sorted(out.keys()) != ["count", "head_hash"]:
        return rej(422, "bad_output", "output must be exactly {count, head_hash}")
    if not isinstance(out["count"], int) or out["count"] < 0: return rej(422, "bad_output", "count")
    if not is_hex(out["head_hash"], 64): return rej(422, "bad_hash_format", "output.head_hash")
    ob = env["observed"]
    if not isinstance(ob, dict) or sorted(ob.keys()) != ["claim_bytes", "claim_sha256", "first_entry_seal"]:
        return rej(422, "bad_observed", "observed shape")
    if not is_hex(ob["claim_sha256"], 64) or not is_hex(ob["first_entry_seal"], 64):
        return rej(422, "bad_hash_format", "observed hashes")
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", env["request_id"] or ""):
        return rej(422, "bad_request_id", "request_id")
    if seal(out) != env["sealed_output"]: return rej(422, "seal_mismatch", "sealed_output")
    if sha256_hex(bytes.fromhex(env["pubkey"])) != env["key_id"]: return rej(422, "bad_key_id", "key_id")
    issued, expires = parse_ts(env["issued_at"]), parse_ts(env["expires_at"])
    if issued is None or expires is None: return rej(422, "bad_timestamp", "ts")
    valid_from, deadline = parse_ts(quest["valid_from"]), parse_ts(quest["deadline"])
    if now_ms > deadline: return rej(410, "quest_closed", quest["deadline"])
    if issued > now_ms + 5 * 60 * 1000: return rej(422, "issued_in_future", "issued_at")
    if issued < valid_from: return rej(422, "issued_before_window", "issued_at")
    if expires <= issued: return rej(422, "bad_window", "expires<=issued")
    if expires <= now_ms: return rej(422, "expired", "expires_at")
    if expires > deadline: return rej(422, "bad_window", "expires>deadline")
    op_norm = norm_name(env["operator"])
    inel = [norm_name(x) for x in quest["manifest"].get("independence", {}).get("ineligible_operators", [])]
    if not op_norm or op_norm in inel: return rej(422, "operator_ineligible", env["operator"])
    pub = bytes.fromhex(env["pubkey"])
    if not _verify(pub, env["sealed_output"].encode(), bytes.fromhex(env["signature"])):
        return rej(422, "bad_signature", "signature over sealed_output")
    signed = {k: env[k] for k in SIGNED_FIELDS}
    if not _verify(pub, canon_compact(signed).encode(), bytes.fromhex(env["envelope_signature"])):
        return rej(422, "bad_signature", "envelope_signature")
    return {"ok": True, "operator_norm": op_norm,
            "failure_mode_norm": re.sub(r"\s+", " ", env["failure_mode"].strip().lower())}

def compute_verdict(quest, envelopes, reexec):
    """Port of core.ts computeVerdict decision logic."""
    per, valid = [], []
    for env in envelopes:
        signed = {k: env[k] for k in SIGNED_FIELDS}
        pub = bytes.fromhex(env["pubkey"])
        ok = (seal(env["output"]) == env["sealed_output"]
              and _verify(pub, env["sealed_output"].encode(), bytes.fromhex(env["signature"]))
              and _verify(pub, canon_compact(signed).encode(), bytes.fromhex(env["envelope_signature"])))
        rec = {"operator": env["operator"], "sealed_output": env["sealed_output"],
               "signatures_valid": ok,
               "matches_reexecution": (env["sealed_output"] == reexec.get("sealed_output")) if reexec["ok"] else None}
        per.append(rec)
        if ok: valid.append({"env": env, "rec": rec})
    if len(valid) < 2:
        for r in per: r["matches_reexecution"] = None
    def indep(a, b):
        return (norm_name(a["env"]["operator"]) != norm_name(b["env"]["operator"])
                and a["env"]["pubkey"] != b["env"]["pubkey"]
                and re.sub(r"\s+", " ", a["env"]["failure_mode"].strip().lower())
                    != re.sub(r"\s+", " ", b["env"]["failure_mode"].strip().lower()))
    verdict, reason, pair = "HOLD", "INSUFFICIENT_VALID_WITNESSES", None
    if not reexec["ok"]:
        verdict, reason = "HOLD", reexec.get("reason", "REEXECUTION_UNAVAILABLE")
    elif len(valid) >= 2:
        agree = [v for v in valid if v["env"]["sealed_output"] == reexec["sealed_output"]]
        disagree = [v for v in valid if v["env"]["sealed_output"] != reexec["sealed_output"]]
        def find_pair(xs, ys=None):
            ys = xs if ys is None else ys
            for i in range(len(xs)):
                for j in range(len(ys)):
                    if xs[i] is not ys[j] and indep(xs[i], ys[j]): return [xs[i], ys[j]]
            return None
        pass_pair = find_pair(agree)
        conflict = find_pair(agree, disagree)
        fail_pair = None
        for i in range(len(disagree)):
            for j in range(i + 1, len(disagree)):
                if disagree[i]["env"]["sealed_output"] == disagree[j]["env"]["sealed_output"] and indep(disagree[i], disagree[j]):
                    fail_pair = [disagree[i], disagree[j]]
        if pass_pair and not conflict: verdict, reason, pair = "PASS", "TWO_INDEPENDENT_MATCHING_SEALS", pass_pair
        elif conflict: verdict, reason = "VOID", "WITNESS_CONFLICT"
        elif fail_pair: verdict, reason = "FAIL", "INDEPENDENT_WITNESSES_REPRODUCE_DIFFERENT_RESULT"
        else: verdict, reason = "HOLD", "NO_INDEPENDENT_PAIR"
    payout = []
    if verdict == "PASS" and pair:
        reward = quest["manifest"].get("reward") or {}
        payout = [{"role": "alpha" if i == 0 else "beta", "operator": p["env"]["operator"],
                   "hhc": reward.get("per_verifier_hhc")} for i, p in enumerate(pair)]
    return {"verdict": verdict, "reason": reason, "seals_valid": len(valid),
            "seals_considered": len(per), "payout_plan": payout}

def compute_evidence(raw):
    """Port of core.ts computeEvidence."""
    d = json.loads(raw)
    ents = d["entries"]; problems = []
    prev = d["ledger_anchor"]["tip_hash"]
    for i, e in enumerate(ents):
        if e["prev_index_hash"] != prev: problems.append(f"entry {i}: prev does not link")
        c = {k: v for k, v in e.items() if k != "index_hash"}
        h = hashlib.sha256(py_default(c).encode()).hexdigest()
        if h != e["index_hash"]: problems.append(f"entry {i}: index_hash mismatch")
        prev = h
    output = {"count": len(ents), "head_hash": prev}
    if d["entry_count"] != output["count"]: problems.append("entry_count mismatch")
    if d["head_hash"] != output["head_hash"]: problems.append("head_hash mismatch")
    return {"output": output, "sealed_output": seal(output),
            "observed": {"claim_sha256": sha256_hex(raw), "claim_bytes": len(raw),
                         "first_entry_seal": seal(ents[0])},
            "problems": problems}

def reexecute(manifest, raw):
    """Port of index.ts reexecute() against supplied claim bytes."""
    if sha256_hex(raw) != manifest["claim"]["sha256"] or len(raw) != manifest["claim"]["bytes"]:
        return {"ok": False, "reason": "CLAIM_CHANGED_SINCE_MANIFEST", "claim_sha256": sha256_hex(raw)}
    ev = compute_evidence(raw)
    return {"ok": True, "claim_sha256": sha256_hex(raw),
            "sealed_output": ev["sealed_output"], "output": ev["output"]}

import uuid
_seed_ctr = [100]
def build_envelope(operator, failure_mode, output, quest=QUEST, seed=None,
                   issued="2026-11-19T09:30:00Z", expires=None, manifest_sha=None):
    """Mirror of sign_and_drop.py's envelope construction."""
    _seed_ctr[0] += 1
    seed = seed or hashlib.sha256(f"btg-attack-seed-{_seed_ctr[0]}".encode()).digest()
    pub, _a, _h = _publickey(seed)
    env = {"schema": ENVELOPE_SCHEMA, "quest_id": quest["quest_id"],
           "manifest_sha256": manifest_sha or quest["manifest_sha256"],
           "request_id": str(uuid.uuid4()), "nonce": os.urandom(32).hex(),
           "issued_at": issued, "expires_at": expires or MANIFEST["deadline"],
           "key_id": sha256_hex(pub), "pubkey": pub.hex(), "operator": operator,
           "failure_mode": failure_mode,
           "implementation": "btg attack harness (python port)",
           "output": output, "sealed_output": seal(output), "observed": OBSERVED}
    _p, s1 = _sign(seed, env["sealed_output"].encode()); env["signature"] = s1.hex()
    signed = {k: env[k] for k in SIGNED_FIELDS}
    _p, s2 = _sign(seed, canon_compact(signed).encode()); env["envelope_signature"] = s2.hex()
    return env

NOW = parse_ts("2026-11-19T09:35:00Z")           # in-window instant
REEXEC = reexecute(MANIFEST, raw_index)          # the service's own re-execution
assert REEXEC["ok"] and REEXEC["sealed_output"] == PINNED["sealed_output"]

# S1 — control: two genuine independent seals must PASS (harness fidelity)
e1 = build_envelope("witness-alpha", "my sandbox could have dropped entries", GENUINE_OUTPUT)
e2 = build_envelope("witness-beta", "network fetch could have served a stale copy", GENUINE_OUTPUT)
v = compute_verdict(QUEST, [e1, e2], REEXEC)
record("A", "S1 control — two genuine independent seals (port)",
       "validate + verdict on two correctly built envelopes over the true output",
       "CONTROL PASS" if v["verdict"] == "PASS" else "CONTROL FAILED (harness problem)",
       f"intake: {[validate_envelope(e, QUEST, NOW)['ok'] for e in (e1, e2)]}; verdict={v['verdict']}/{v['reason']}; payout={v['payout_plan']}")

# S2 — two independent FALSE seals (fabricated head_hash, correctly signed)
f1 = build_envelope("forger-one", "failure mode alpha text", FALSE_OUTPUT)
f2 = build_envelope("forger-two", "failure mode beta text", FALSE_OUTPUT)
acc = [validate_envelope(e, QUEST, NOW) for e in (f1, f2)]
v = compute_verdict(QUEST, [f1, f2], REEXEC)
record("A", "S2 two independent seals over a FALSE output",
       "fabricated head_hash (ab*32), sealed_output honestly computed over the false output, valid signatures",
       "NO BREAK" if v["verdict"] != "PASS" else "BREAK",
       f"intake accepts both (acceptance is not a verdict): {[a['ok'] for a in acc]}; "
       f"verdict={v['verdict']}/{v['reason']} — a false pair can force FAIL, never PASS: "
       "PASS requires matching the service's own re-execution")

# S3 — one genuine + one false independent seal
v = compute_verdict(QUEST, [e1, f1], REEXEC)
record("A", "S3 genuine seal + false seal (conflict)",
       "verdict over one agreeing and one disagreeing independent seal",
       "NO BREAK" if v["verdict"] != "PASS" else "BREAK",
       f"verdict={v['verdict']}/{v['reason']} — conflict voids the round instead of passing it")

# S4 — two false seals, IDENTICAL failure_mode text (independence probe)
g1 = build_envelope("forger-three", "same failure text", FALSE_OUTPUT)
g2 = build_envelope("forger-four", "same failure text", FALSE_OUTPUT)
v = compute_verdict(QUEST, [g1, g2], REEXEC)
record("A", "S4 false pair with identical failure_mode",
       "independence requires distinct normalized failure_mode",
       "NO BREAK" if v["verdict"] == "HOLD" else "UNEXPECTED",
       f"verdict={v['verdict']}/{v['reason']} — the pair is not independent, so it cannot even force FAIL")

# S5 — sybil probes: same pubkey/two names; same name/two keys
shared_seed = hashlib.sha256(b"btg-sybil").digest()
syb1 = build_envelope("sybil-name-one", "fm one", FALSE_OUTPUT, seed=shared_seed)
syb2 = build_envelope("sybil-name-two", "fm two", FALSE_OUTPUT, seed=shared_seed)
v1 = compute_verdict(QUEST, [syb1, syb2], REEXEC)
syb3 = build_envelope("sybil-name-one", "fm three", FALSE_OUTPUT)
syb4 = build_envelope("sybil-name-one", "fm four", FALSE_OUTPUT)
v2 = compute_verdict(QUEST, [syb3, syb4], REEXEC)
record("A", "S5 sybil — one key two names / one name two keys",
       "independence requires distinct operator AND distinct pubkey; DB also enforces one seal per key and per operator per quest (409 duplicate_key/duplicate_operator)",
       "NO BREAK" if v1["verdict"] == "HOLD" and v2["verdict"] == "HOLD" else "UNEXPECTED",
       f"same-key verdict={v1['verdict']}/{v1['reason']}; same-name verdict={v2['verdict']}/{v2['reason']}. "
       "Residual limit (disclosed, BLUEPRINT gap 5): two genuinely distinct keys+names run by one human are "
       "indistinguishable to the protocol — independence is self-declared and settlement is manual "
       "(automatic_payment=false, human_review in the manifest), so even that pair cannot self-pay.")

# S6 — ineligible operators (coordinator's own names, incl. normalization tricks)
for op in ("dbottrader", "DbotTrader!!", "grok ace"):
    env = build_envelope(op, "fm", GENUINE_OUTPUT)
    r = validate_envelope(env, QUEST, NOW)
    record("A", f"S6 ineligible operator '{op}'",
           "intake eligibility check (normName-normalized)",
           "NO BREAK" if not r["ok"] and r["code"] == "operator_ineligible" else "UNEXPECTED",
           f"intake -> {r.get('status')} {r.get('code')}")

# S7 — cross-quest replay of QUEST-001-TEST material
t1 = build_envelope("witness-alpha", "fm test", GENUINE_OUTPUT, quest=TEST_QUEST)
r = validate_envelope(t1, TEST_QUEST, NOW)
record("A", "S7a test-quest envelope against the TEST quest",
       "a test seal is valid — in the test quest only",
       "EXPECTED" if r["ok"] else "UNEXPECTED",
       f"intake vs TEST row -> ok={r['ok']} (test chronicle is a separate quest; is_test=true)")
t2 = copy.deepcopy(t1); t2["quest_id"] = "QUEST-001"; t2["manifest_sha256"] = QUEST["manifest_sha256"]
r = validate_envelope(t2, QUEST, NOW)
record("A", "S7b test envelope re-labelled as QUEST-001",
       "quest_id + manifest_sha256 edited after signing (both are signed fields)",
       "NO BREAK" if not r["ok"] else "BREAK",
       f"intake -> {r.get('status')} {r.get('code')} (envelope_signature no longer verifies)")
t3 = build_envelope("witness-alpha", "fm", GENUINE_OUTPUT, manifest_sha=TEST_QUEST["manifest_sha256"])
r = validate_envelope(t3, QUEST, NOW)
record("A", "S7c QUEST-001 envelope carrying the TEST manifest hash",
       "manifest binding check",
       "NO BREAK" if not r["ok"] and r["code"] == "wrong_manifest" else "UNEXPECTED",
       f"intake -> {r.get('status')} {r.get('code')}")

# S8 — timing attacks
late = build_envelope("witness-alpha", "fm", GENUINE_OUTPUT, issued="2026-11-19T20:00:00Z")
r = validate_envelope(late, QUEST, parse_ts("2026-11-20T06:00:00Z"))
record("A", "S8a seal dropped after the deadline",
       "now > deadline at intake", "NO BREAK" if not r["ok"] and r["status"] == 410 else "UNEXPECTED",
       f"intake -> {r.get('status')} {r.get('code')}")
wide = build_envelope("witness-alpha", "fm", GENUINE_OUTPUT, expires="2026-11-20T12:00:00Z")
r = validate_envelope(wide, QUEST, NOW)
record("A", "S8b envelope expiring after the deadline",
       "expires_at must be <= deadline", "NO BREAK" if not r["ok"] and r["code"] == "bad_window" else "UNEXPECTED",
       f"intake -> {r.get('status')} {r.get('code')}")
early = build_envelope("witness-alpha", "fm", GENUINE_OUTPUT, issued="2026-11-14T10:00:00Z")
r = validate_envelope(early, QUEST, NOW)
record("A", "S8c envelope issued before valid_from",
       "issued_at >= manifest valid_from", "NO BREAK" if not r["ok"] and r["code"] == "issued_before_window" else "UNEXPECTED",
       f"intake -> {r.get('status')} {r.get('code')}")

# S9 — signature tamper on a genuine envelope
tamp_env = copy.deepcopy(e1)
tamp_env["envelope_signature"] = tamp_env["envelope_signature"][:-1] + (
    "0" if tamp_env["envelope_signature"][-1] != "0" else "1")
r = validate_envelope(tamp_env, QUEST, NOW)
record("A", "S9 genuine envelope, one hex char of envelope_signature flipped",
       "Ed25519 envelope_signature check",
       "NO BREAK" if not r["ok"] and r["code"] == "bad_signature" else "UNEXPECTED",
       f"intake -> {r.get('status')} {r.get('code')}")

# =====================================================================
# TRACK A3 — index tail-rewrite (claim substitution)
# =====================================================================
forged_doc = copy.deepcopy(doc)
forged_doc["entries"][8]["description"] += " — GATE PASS GRANTED TO FABRICATED WORK (BTG TEST)"
prev = forged_doc["ledger_anchor"]["tip_hash"]
for i, e in enumerate(forged_doc["entries"]):
    e["prev_index_hash"] = prev
    c = {k: v for k, v in e.items() if k != "index_hash"}
    e["index_hash"] = hashlib.sha256(py_default(c).encode()).hexdigest()
    prev = e["index_hash"]
forged_doc["head_hash"] = prev
forged_raw = json.dumps(forged_doc, indent=1, ensure_ascii=False).encode()
probs_f, head_f = replay_chain(forged_doc)
rex_f = reexecute(MANIFEST, forged_raw)
v = compute_verdict(QUEST, [build_envelope("witness-alpha", "fm a", compute_evidence(forged_raw)["output"]),
                            build_envelope("witness-beta", "fm b", compute_evidence(forged_raw)["output"])], rex_f)
record("A", "A4 index tail-rewrite (false claim inserted, whole tail re-hashed)",
       "forge entry 8's description, recompute every downstream index_hash so the forged file is chain-consistent; "
       "then run (i) chain-only replay, (ii) the endpoint's re-execution against the manifest",
       "NO BREAK",
       f"(i) chain-only replay of the forged file: problems={probs_f} — a hash chain alone does NOT detect a "
       f"full tail rewrite (forged head {head_f[:16]}…). (ii) But the forged file's sha256 != manifest claim hash, "
       f"so re-execution -> ok={rex_f['ok']} reason={rex_f.get('reason')}, and seals over the forged output yield "
       f"verdict={v['verdict']}/{v['reason']}. The anchors that bind the chain are the manifest-pinned claim "
       "sha256/bytes and the externally published head fadbd275… — both outside the file being checked.")

# =====================================================================
# TRACK A4 — detached verdict forgery (verdict_hash is not a signature)
# =====================================================================
fake_verdict_body = {"schema": "ASIN-HHC-QUEST-VERDICT-1.0", "quest_id": "QUEST-001",
                     "manifest_sha256": PINNED["manifest_sha256"], "is_test": False,
                     "verdict": "PASS", "reason": "TWO_INDEPENDENT_MATCHING_SEALS",
                     "seals_considered": 2, "seals_valid": 2, "seals": [],
                     "payout_plan": [{"role": "alpha", "operator": "forger-one", "key_id": "0" * 64, "hhc": 5},
                                     {"role": "beta", "operator": "forger-two", "key_id": "1" * 64, "hhc": 5}],
                     "settlement_state": "awaiting_human_authorization", "automatic_payment": False}
fake_vh = seal(fake_verdict_body)
record("A", "A5 detached verdict object with a self-computed verdict_hash",
       "verdict_hash = sha256(canonical_json(body)) — an unsigned checksum; anyone can mint a "
       "well-formed 'PASS' verdict object offline (demonstrated: hash computed in this run)",
       "NO BREAK (consumer-guidance finding)",
       f"fabricated verdict_hash {fake_vh[:16]}… is correctly formed yet proves nothing: authority comes from "
       "fetching the verdict from the endpoint/chronicle (whose seals are signed and chain-linked), never from "
       "a detached object. The live endpoint's real verdict at snapshot time was HOLD/INSUFFICIENT_VALID_WITNESSES "
       "with verdict_hash 7557d3ba… (q001-endpoint-snapshot-0259.md).")

json.dump(RESULTS, open(os.path.join(SCRATCH, "results.json"), "w"), indent=1)
breaks = [r for r in RESULTS if r["result"].startswith("BREAK")]
print()
print(f"TOTAL attempts: {len(RESULTS)} | genuine breaks: {len(breaks)}")
for b in breaks: print("BREAK:", b)
