#!/usr/bin/env python3
"""Standalone outsider verifier for the CP8 gate receipt's vault signature.

Implements ENVELOPE-SPEC.md (ASIN-HHC vault envelope, Agent Vault v1)
using ONLY:
  * the published gate receipt object (which carries signer.pubkey), and
  * the spec's two canonicalizations + the vault envelope construction.

No vault access, no private key, no network. Python 3 standard library
only (pure-Python Ed25519 verify, RFC 8032).

Usage:
  python3 verify_gate_receipt.py RECEIPT.json
  python3 verify_gate_receipt.py RECEIPT.jsonl   # picks verification_id
                                                 # live-2026-11-12-provindex-001
  python3 verify_gate_receipt.py POST.md         # extracts the ```json
                                                 # receipt block
  python3 verify_gate_receipt.py                 # default local copies

Exit code 0 iff every check passes.
"""
import hashlib
import json
import re
import sys

# --------------------------------------------------------------------------
# Ed25519 verify (RFC 8032), pure Python — same construction as
# ~/workspace/quest001-seal-drop/sign_and_drop.py (cross-checked there
# byte-for-byte against the reference `cryptography` implementation).
# --------------------------------------------------------------------------
_b = 256
_q = 2**255 - 19
_l = 2**252 + 27742317777372353535851937790883648493


def _H(m):
    return hashlib.sha512(m).digest()


def _inv(x):
    return pow(x, _q - 2, _q)


_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(_d * y * y + 1) % _q
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = (4 * _inv(5)) % _q
_B = (_xrecover(_By), _By)


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    den = _inv(1 + _d * x1 * x2 * y1 * y2 % _q)
    x3 = (x1 * y2 + x2 * y1) * den % _q
    den2 = _inv(1 - _d * x1 * x2 * y1 * y2 % _q)
    y3 = (y1 * y2 + x1 * x2) * den2 % _q
    return (x3, y3)


def _scalarmult(P, e):
    Q = (0, 1)
    while e > 0:
        if e & 1:
            Q = _edwards(Q, P)
        P = _edwards(P, P)
        e >>= 1
    return Q


def _bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def _decodeint(s):
    return int.from_bytes(s, "little")


def _decodepoint(s):
    y = sum(2**i * _bit(s, i) for i in range(0, _b - 1))
    x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1):
        x = _q - x
    return (x, y)


def _Hint(m):
    return int.from_bytes(_H(m), "little")


def ed25519_verify(pub, msg, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    R = _decodepoint(sig[:32])
    A = _decodepoint(pub)
    S = _decodeint(sig[32:])
    if S >= _l:
        return False
    h = _Hint(sig[:32] + pub + msg) % _l
    return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))


# --------------------------------------------------------------------------
# The two canonicalizations (ENVELOPE-SPEC.md §2 — they are NOT the same)
# --------------------------------------------------------------------------
def canon_gate(obj):
    """Gate receipt canon (gate.py canonical_json):
    sort_keys, separators (',', ':'), ensure_ascii=False, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canon_vault(obj):
    """Vault canon (vault.py canon):
    sort_keys, separators (',', ':'), ensure_ascii=True, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------
# Receipt loading
# --------------------------------------------------------------------------
def load_receipt(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".md"):
        m = re.search(r"```json\n(\{.*?\})\n```", text, re.S)
        if not m:
            raise SystemExit("no ```json receipt block found in %s" % path)
        return json.loads(m.group(1))
    if path.endswith(".jsonl"):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("verification_id") == "live-2026-11-12-provindex-001":
                return obj
        raise SystemExit("target receipt not found in %s" % path)
    return json.loads(text)


# --------------------------------------------------------------------------
# Verification (ENVELOPE-SPEC.md §5)
# --------------------------------------------------------------------------
def verify_receipt(receipt):
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))
        return bool(ok)

    sig_block = receipt.get("signature") or {}
    signer = receipt.get("signer") or {}

    # 1. receipt_hash recomputes over the body (object minus the
    #    receipt_hash and signature keys), gate canon.
    body = {k: v for k, v in receipt.items()
            if k not in ("receipt_hash", "signature")}
    recomputed = sha256_hex(canon_gate(body))
    check("receipt_hash recomputes (gate canon, body minus "
          "receipt_hash/signature)",
          recomputed == receipt.get("receipt_hash"), recomputed)

    # 2. Signer identity derivations.
    pub_hex = signer.get("pubkey", "")
    try:
        pub = bytes.fromhex(pub_hex)
    except ValueError:
        pub = b""
    check("signer.pubkey is 32 bytes hex", len(pub) == 32, pub_hex[:16] + "…")
    fingerprint = sha256_hex(pub) if pub else ""
    check("fingerprint == sha256(raw pubkey bytes)",
          fingerprint == signer.get("fingerprint"), fingerprint)
    check("vault_id == 'vlt_' + fingerprint[:16]",
          signer.get("vault_id") == "vlt_" + fingerprint[:16],
          signer.get("vault_id", ""))
    check("signature.kind and signer.kind are 'agent-vault-ed25519'",
          sig_block.get("kind") == "agent-vault-ed25519"
          and signer.get("kind") == "agent-vault-ed25519")

    # 3. The signed payload, for a gate receipt, is the receipt_hash
    #    hex string as UTF-8 bytes (gate.py VaultSigner). The vault
    #    hashes those payload bytes into the envelope.
    payload = receipt["receipt_hash"].encode("utf-8")
    payload_sha256 = sha256_hex(payload)
    check("payload_sha256 == sha256(receipt_hash as UTF-8) "
          "(derivable from the receipt alone)", True, payload_sha256)

    # 4. Rebuild the vault envelope exactly (vault.py envelope()):
    #    amount/dest are JSON null for doc.sign gate signatures —
    #    VaultSigner passes no --amount/--dest, so vault.py defaults
    #    them to None. ts/nonce/action ride in the receipt's
    #    signature block, copied from the vault's sign output.
    envelope = {
        "action": sig_block.get("action"),
        "payload_sha256": payload_sha256,
        "amount": None,
        "dest": None,
        "ts": sig_block.get("ts"),
        "nonce": sig_block.get("nonce"),
    }
    msg = canon_vault(envelope)
    check("envelope rebuilt (vault canon)", True,
          msg.decode("utf-8"))

    # 5. Ed25519-verify signature.value over the envelope bytes
    #    under signer.pubkey.
    try:
        sig = bytes.fromhex(sig_block.get("value", ""))
    except ValueError:
        sig = b""
    check("signature is 64 bytes hex", len(sig) == 64)
    ok = ed25519_verify(pub, msg, sig) if pub and sig else False
    check("Ed25519 signature verifies over the vault envelope", ok)

    # 6. Negative control: the same signature must NOT verify over a
    #    tampered envelope (guards against a verifier that always
    #    returns true).
    tampered = dict(envelope)
    tampered["nonce"] = "0" * 16
    check("negative control: tampered-nonce envelope does NOT verify",
          not ed25519_verify(pub, canon_vault(tampered), sig))

    return checks


def main(argv):
    if len(argv) > 1:
        path = argv[1]
    else:
        path = "~/workspace/autogen-7609-reply-final-2026-11-18.md"
        import os
        path = os.path.expanduser(path)
    receipt = load_receipt(path)
    print("source: %s" % path)
    print("verification_id: %s" % receipt.get("verification_id"))
    print("receipt_hash: %s" % receipt.get("receipt_hash"))
    checks = verify_receipt(receipt)
    all_ok = True
    for name, ok, detail in checks:
        all_ok = all_ok and ok
        print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                             (" — " + detail) if detail else ""))
    print("RESULT: %s" % ("PASS — gate receipt signature is "
                          "outsider-verifiable under ENVELOPE-SPEC.md"
                          if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
