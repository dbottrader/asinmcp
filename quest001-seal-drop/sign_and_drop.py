#!/usr/bin/env python3
"""Quest 001 seal-drop — witness tool (Python 3, standard library only).

Re-executes the quest claim (the 78-entry provenance index) from its public
URL, recomputes the full hash chain, and — only if every link recomputes —
signs and drops a seal envelope (ASIN-HHC-QUEST-SEAL-1.0) at the
quest-evidence endpoint. Your keypair is generated locally and saved next to
this script; nobody else ever sees the secret key.

Usage:
  python3 sign_and_drop.py --operator YOUR_NAME \
      --failure-mode "how your run could have failed / what you checked" \
      --implementation "how you recomputed (tool, language, host)"

Options:
  --quest QUEST-001        (default; QUEST-001-TEST is the practice quest)
  --keyfile PATH           (default ./seal-key.json; created if missing)
  --dry-run                build and self-verify the envelope, do not POST
"""
import argparse, hashlib, json, os, sys, urllib.request
from datetime import datetime, timezone

BASE = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence"

# ---------------- ed25519 (RFC 8032), pure Python ----------------
_b = 256
_q = 2**255 - 19
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
_By = (4 * _inv(5)) % _q
_B = (_xrecover(_By), _By)
def _edwards(P, Q):
    x1, y1 = P; x2, y2 = Q
    den = _inv(1 + _d * x1 * x2 * y1 * y2 % _q)
    x3 = (x1 * y2 + x2 * y1) * den % _q
    den2 = _inv(1 - _d * x1 * x2 * y1 * y2 % _q)
    y3 = (y1 * y2 + x1 * x2) * den2 % _q
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
    x, y = P
    bits = [(y >> i) & 1 for i in range(_b - 1)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(_b // 8))
def _bit(h, i): return (h[i // 8] >> (i % 8)) & 1
def _publickey(seed32):
    h = _H(seed32)
    a = 2**(_b - 2) + sum(2**i * _bit(h, i) for i in range(3, _b - 2))
    return _encodepoint(_scalarmult(_B, a)), a, h
def _Hint(m): return int.from_bytes(_H(m), "little")
def _sign(seed32, msg):
    pub, a, h = _publickey(seed32)
    r = _Hint(h[_b // 8:_b // 4] + msg) % _l
    R = _scalarmult(_B, r)
    S = (r + _Hint(_encodepoint(R) + pub + msg) * a) % _l
    return pub, _encodepoint(R) + _encodeint(S)
def _decodeint(s): return int.from_bytes(s, "little")
def _decodepoint(s):
    y = sum(2**i * _bit(s, i) for i in range(0, _b - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1): x = _q - x
    return (x, y)
def _verify(pub, msg, sig):
    if len(sig) != 64: return False
    R = _decodepoint(sig[:32]); A = _decodepoint(pub)
    S = _decodeint(sig[32:])
    if S >= _l: return False
    h = _Hint(sig[:32] + pub + msg) % _l
    return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))

def selftest():
    # Test vector produced by the reference `cryptography` implementation
    # (OpenSSL Ed25519): seed = bytes 00..1f, empty message. The pure-Python
    # implementation above must reproduce it exactly (it also cross-verified
    # byte-identical signatures with the reference on random keys).
    seed = bytes(range(32))
    pub, sig = _sign(seed, b"")
    assert pub.hex() == "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8", pub.hex()
    assert sig.hex() == ("9ca53579530654d5c3df77089ef45eda613e2fedf670e96bedac4639504e5845"
                         "ef4b95d5793077233dd16817b2532e9c5525872a73a4ad74b759369a9e05c102"), sig.hex()
    assert _verify(pub, b"", sig)
    print("ed25519 self-test: reference vector OK")

# ---------------- quest evidence (port of QUEST-001-SPEC) ----------------
def canon(v): return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
def py_dumps(v): return json.dumps(v, sort_keys=True, ensure_ascii=False)
def seal(v): return hashlib.sha256(canon(v).encode()).hexdigest()

def fetch(url):
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers

def recompute(manifest):
    claim = manifest["claim"]
    raw, _ = fetch(claim["url"])
    file_sha = hashlib.sha256(raw).hexdigest()
    if file_sha != claim["sha256"] or len(raw) != claim["bytes"]:
        raise SystemExit(f"CLAIM CHANGED: sha {file_sha} bytes {len(raw)} != manifest")
    doc = json.loads(raw)
    entries = doc["entries"]
    prev = doc["ledger_anchor"]["tip_hash"]
    for i, e in enumerate(entries):
        if e["prev_index_hash"] != prev:
            raise SystemExit(f"entry {i}: prev_index_hash does not link")
        c = {k: v for k, v in e.items() if k != "index_hash"}
        h = hashlib.sha256(py_dumps(c).encode()).hexdigest()
        if h != e["index_hash"]:
            raise SystemExit(f"entry {i}: index_hash does not recompute")
        prev = h
    output = {"count": len(entries), "head_hash": prev}
    if doc["entry_count"] != output["count"] or doc["head_hash"] != output["head_hash"]:
        raise SystemExit("declared count/head do not match recomputation")
    return output, {
        "claim_sha256": file_sha, "claim_bytes": len(raw),
        "first_entry_seal": seal(entries[0]),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--operator", required=True)
    ap.add_argument("--failure-mode", required=True)
    ap.add_argument("--implementation", required=True)
    ap.add_argument("--quest", default="QUEST-001")
    ap.add_argument("--keyfile", default="seal-key.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    selftest()
    slug = args.quest.lower()
    raw, hdrs = fetch(f"{BASE}/{slug}/manifest")
    manifest = json.loads(raw)
    manifest_sha = hdrs.get("X-Manifest-SHA256")
    output, observed = recompute(manifest)
    sealed_output = seal(output)
    print(f"recomputed: count={output['count']} head={output['head_hash']}")
    print(f"sealed_output={sealed_output}")

    if os.path.exists(args.keyfile):
        seed = bytes.fromhex(json.load(open(args.keyfile))["seed_hex"])
        print(f"loaded key from {args.keyfile}")
    else:
        seed = os.urandom(32)
        json.dump({"seed_hex": seed.hex()}, open(args.keyfile, "w"))
        print(f"generated NEW keypair, saved to {args.keyfile} (keep this file)")
    pub, _a, _h = _publickey(seed)
    key_id = hashlib.sha256(pub).hexdigest()

    import uuid
    now = datetime.now(timezone.utc)
    env = {
        "schema": "ASIN-HHC-QUEST-SEAL-1.0",
        "quest_id": manifest["quest_id"],
        "manifest_sha256": manifest_sha,
        "request_id": str(uuid.uuid4()),
        "nonce": os.urandom(32).hex(),
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": manifest["deadline"],
        "key_id": key_id,
        "pubkey": pub.hex(),
        "operator": args.operator,
        "failure_mode": args.failure_mode,
        "implementation": args.implementation,
        "output": output,
        "sealed_output": sealed_output,
        "observed": observed,
    }
    _p, sig1 = _sign(seed, sealed_output.encode())
    env["signature"] = sig1.hex()
    signed = {k: env[k] for k in (
        "schema", "quest_id", "manifest_sha256", "request_id", "nonce", "issued_at",
        "expires_at", "key_id", "pubkey", "operator", "failure_mode", "implementation",
        "output", "sealed_output", "observed")}
    _p, sig2 = _sign(seed, canon(signed).encode())
    env["envelope_signature"] = sig2.hex()

    # local verification, mirroring the endpoint's checks
    assert _verify(pub, sealed_output.encode(), sig1)
    assert _verify(pub, canon(signed).encode(), sig2)
    assert seal(output) == sealed_output
    assert hashlib.sha256(pub).hexdigest() == key_id
    print("envelope built and self-verified")

    if args.dry_run:
        print(json.dumps(env, indent=2))
        return
    data = json.dumps(env).encode()
    req = urllib.request.Request(f"{BASE}/seal-drop", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("HTTP", r.status)
            print(r.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code)
        print(e.read().decode())
        sys.exit(1)

if __name__ == "__main__":
    main()
