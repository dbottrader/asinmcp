# Vendored 2026-10-31 from ~/workspace/asinmolt-node/ed25519.py (same
# project; byte-identical apart from this header). Pure-python RFC 8032
# Ed25519, stdlib only. No third-party license applies: the source is
# project-original code and carries no license header and no third-party
# code. Vendored so a pristine asinmcp clone verifies with stdlib only.
"""Ed25519 digital signatures (RFC 8032) — pure Python stdlib, no dependencies.

Why this exists: mesh agents need REAL keypairs. The legacy mesh /register
field called "pubkey" actually carries a shared HMAC secret (the standing P3
terminology issue) — it is not a public key and never was. Agent money
(transfers) now signs with a genuine Ed25519 keypair: the private key signs,
the public key verifies, and the two are never confused.

Self-test: run `python3 ed25519.py` — checks the two RFC 8032 test vectors
(sign + verify + pubkey derivation). Exits nonzero on failure.
"""
import hashlib

__all__ = ["generate_keypair", "sign", "verify", "pubkey_from_seed",
           "SIGNATURE_BYTES", "PUBLIC_KEY_BYTES", "SEED_BYTES"]

B = 256
Q = (1 << 255) - 19
L = (1 << 252) + 27742317777372353535851937790883648493
SEED_BYTES = 32
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _inv(x: int) -> int:
    return pow(x, Q - 2, Q)


_D = (-121665 * _inv(121666)) % Q
_I = pow(2, (Q - 1) // 4, Q)


def _xrecover(y: int):
    """Recover x from y on the Ed25519 curve: x^2 = (y^2-1)/(d*y^2+1)."""
    y2 = y * y % Q
    num = (y2 - 1) % Q
    den = (_D * y2 + 1) % Q
    a = num * _inv(den) % Q
    x = pow(a, (Q + 3) // 8, Q)          # candidate sqrt; q = 5 mod 8
    if (x * x - a) % Q != 0:
        x = x * pow(2, (Q - 1) // 4, Q) % Q   # adjust by 2^((q-1)/4)
    if (x * x - a) % Q != 0:
        raise ValueError("no x for y")
    if x & 1:          # canonical even root (matches the RFC base point)
        x = Q - x
    return x


def _edwards(P, Q_):
    """Twisted-Edwards addition for -x^2 + y^2 = 1 + d*x^2*y^2 (a = -1)."""
    x1, y1 = P
    x2, y2 = Q_
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2)
    return (x3 % Q, y3 % Q)


def _scalarmult(P, e: int):
    if e == 0:
        return (0, 1)
    Q_ = _scalarmult(P, e // 2)
    Q_ = _edwards(Q_, Q_)
    if e & 1:
        Q_ = _edwards(Q_, P)
    return Q_


def _encodepoint(P) -> bytes:
    x, y = P
    bits = [(y >> i) & 1 for i in range(B - 1)] + [x & 1]
    return bytes(sum(bits[8 * i + j] << j for j in range(8))
                 for i in range(B // 8))


_BY = 4 * _inv(5) % Q
_BX = _xrecover(_BY)
_BASE = (_BX, _BY)


def _Hint(m: bytes) -> int:
    h = _H(m)
    return sum(h[i] << (8 * i) for i in range(64))


def _decodeint(s: bytes) -> int:
    return sum(s[i] << (8 * i) for i in range(len(s)))


def _decodepoint(s: bytes):
    y = sum((s[i] >> j & 1) << (8 * i + j)
            for i in range(len(s)) for j in range(8) if 8 * i + j < B - 1)
    x = _xrecover(y)
    if (x & 1) != ((s[-1] >> 7) & 1):
        x = Q - x
    P = (x, y)
    if _scalarmult(P, L) != (0, 1):   # reject small-subgroup points
        return None
    return P


def _clamp(h: bytes) -> int:
    a = _decodeint(h[:32])
    a &= ~(1 + 2 + 4)
    a &= ~(1 << 255)
    a |= (1 << 254)
    return a


def pubkey_from_seed(seed: bytes) -> bytes:
    """Derive the 32-byte Ed25519 PUBLIC key from a 32-byte private seed."""
    if len(seed) != SEED_BYTES:
        raise ValueError("seed must be 32 bytes")
    return _encodepoint(_scalarmult(_BASE, _clamp(_H(seed))))


def generate_keypair(seed: bytes | None = None):
    """Return (seed_hex, pubkey_hex). Seed from os.urandom when not given.

    The seed IS the private key material — it must never be printed, logged,
    or stored anywhere except the agent's own private record (0600).
    """
    import os
    if seed is None:
        seed = os.urandom(SEED_BYTES)
    return seed.hex(), pubkey_from_seed(seed).hex()


def sign(seed_hex: str, message: bytes) -> str:
    """Sign message with the private seed. Returns 128-char hex signature."""
    seed = bytes.fromhex(seed_hex)
    h = _H(seed)
    a = _clamp(h)
    r = _Hint(h[32:] + message)
    R = _scalarmult(_BASE, r)
    pk = _encodepoint(_scalarmult(_BASE, a))
    S = (r + _Hint(_encodepoint(R) + pk + message) * a) % L
    return (_encodepoint(R) + S.to_bytes(32, "little")).hex()


def verify(pubkey_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify an Ed25519 signature. Never raises on bad input — returns False."""
    try:
        pk = bytes.fromhex(pubkey_hex)
        sig = bytes.fromhex(signature_hex)
        if len(pk) != PUBLIC_KEY_BYTES or len(sig) != SIGNATURE_BYTES:
            return False
        A = _decodepoint(pk)
        if A is None:
            return False
        R = _decodepoint(sig[:32])
        if R is None:
            return False
        S = _decodeint(sig[32:])
        if S >= L:
            return False
        h = _Hint(sig[:32] + pk + message)
        return _scalarmult(_BASE, S) == _edwards(R, _scalarmult(A, h))
    except (ValueError, TypeError):
        return False


def is_valid_pubkey(pubkey_hex: str) -> bool:
    """True when the hex string decodes to a real curve point in the prime-
    order subgroup. Used at key-registration time to reject garbage keys."""
    try:
        pk = bytes.fromhex(pubkey_hex)
        return len(pk) == PUBLIC_KEY_BYTES and _decodepoint(pk) is not None
    except (ValueError, TypeError):
        return False


def _selftest() -> bool:
    # RFC 8032 section 7.1 — vectors copied verbatim from the RFC text.
    # TEST 1 (empty message)
    sk1 = bytes.fromhex(
        "9d61b19deffd5a60ba844af492ec2cc4"
        "4449c5697b326919703bac031cae7f60")
    pk1 = ("d75a980182b10ab7d54bfed3c964073a"
           "0ee172f3daa62325af021a68f707511a")
    sig1 = ("e5564300c360ac729086e2cc806e828a"
            "84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46b"
            "d25bf5f0595bbe24655141438e7a100b")
    assert pubkey_from_seed(sk1).hex() == pk1, "TEST1 pubkey mismatch"
    assert sign(sk1.hex(), b"") == sig1, "TEST1 signature mismatch"
    assert verify(pk1, b"", sig1), "TEST1 verify failed"
    # TEST 2 (message 0x72)
    sk2 = bytes.fromhex(
        "4ccd089b28ff96da9db6c346ec114e0f"
        "5b8a319f35aba624da8cf6ed4fb8a6fb")
    pk2 = ("3d4017c3e843895a92b70aa74d1b7ebc"
           "9c982ccf2ec4968cc0cd55f12af4660c")
    sig2 = ("92a009a9f0d4cab8720e820b5f642540"
            "a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c"
            "387b2eaeb4302aeeb00d291612bb0c00")
    assert pubkey_from_seed(sk2).hex() == pk2, "TEST2 pubkey mismatch"
    assert sign(sk2.hex(), b"\x72") == sig2, "TEST2 signature mismatch"
    assert verify(pk2, b"\x72", sig2), "TEST2 verify failed"
    # negative: wrong message, wrong key, tampered sig
    assert not verify(pk1, b"x", sig1), "forgery accepted (message)"
    assert not verify(pk2, b"", sig1), "forgery accepted (key)"
    assert not verify(pk1, b"", sig1[:-2] + "00"), "forgery accepted (sig)"
    return True


if __name__ == "__main__":
    _selftest()
    print("ed25519 self-test: RFC 8032 vectors PASS")
