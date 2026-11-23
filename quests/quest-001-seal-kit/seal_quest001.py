#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# seal_quest001.py - "Seal Quest 001 with any open-source agent" kit, v1.2.0
# Copyright (c) 2026 Dennis Christie / ASIN-HHC (MIT, see repo LICENSE).
#
# Single file, Python 3.8+ standard library only. No pip install needed.
#
# What it does (spec: quest001/QUEST-001-SPEC.md on branch feat/quest001-functional;
# intake code: quest001/supabase/functions/quest-evidence/core.ts):
#   1. fetches the quest manifest and records sha256 of its exact bytes
#   2. fetches the public provenance index named in the manifest, checks its
#      sha256 and byte length against the manifest
#   3. recomputes every entry hash and the prev_index_hash chain, and the head
#      (fails loudly on any mismatch)
#   4. creates YOUR OWN Ed25519 key under ~/.asinhhc/ (0600, never uploaded)
#   5. builds and signs an ASIN-HHC-QUEST-SEAL-1.0 envelope, self-verifies it,
#      prints it, saves it and prints the file sha256 (default TTL 60 minutes)
#   6. submits ONLY with --submit-file PATH, which POSTs that exact saved file
#      after re-verifying signatures and expiry. --submit is refused because
#      it used to rebuild a new envelope.
#
# Ed25519 choice: Ed25519 is not in the Python standard library. This file
# embeds a small pure-Python RFC 8032 implementation (section "ED25519 CORE"
# below), checked at every start against the RFC 8032 section 7.1 test vectors,
# so the kit runs on any machine with python3 and nothing else. If the
# optional `cryptography` package happens to be installed, every signature is
# also cross-checked with it; it is never required. Pure-Python signing is not
# constant-time; that is acceptable here because the key is a fresh one-quest
# key used a few times on your own machine, but do not reuse it for anything
# of value.
#
# Payment: nothing in this kit or in the quest-evidence service moves HHC.
# Payout is a manual decision by Dennis Christie after review.

import argparse
import hashlib
import json
import os
import platform
import secrets
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

KIT_VERSION = "seal_quest001.py/1.2.0"

BASE = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence"
SEAL_DROP_URL = BASE + "/seal-drop"
QUESTS = {
    # quest slug -> (quest_id, accepted manifest sha256 pins)
    "quest-001": ("QUEST-001", ("422f2c7b26708a5e398491d3ce7d1ec9624a1c378909e541db60725edbd561aa",)),
    # test v1 (closed Nov 19 CT) and the proposed test v2 in ops/ (deadline Nov 26 CT)
    "quest-001-test": ("QUEST-001-TEST", ("ed1b02ac9eb264fab11460fd69802bbc2c7b6d7eb553b0ffdfcc2b41bfb333af",
                                          "c22d7db6a392be5f80e72695a990e1c43b9d18335aac71be93be4961c46e401a")),
}
ENVELOPE_SCHEMA = "ASIN-HHC-QUEST-SEAL-1.0"          # core.ts:7
SIGNED_FIELDS = [                                   # core.ts:12-16
    "schema", "quest_id", "manifest_sha256", "request_id", "nonce", "issued_at",
    "expires_at", "key_id", "pubkey", "operator", "failure_mode", "implementation",
    "output", "sealed_output", "observed",
]
HEX = set("0123456789abcdef")


class KitError(Exception):
    """Any condition under which the sealer must NOT seal."""


def die(msg, code=2):
    print("\n*** STOP: " + msg + " ***\n", file=sys.stderr)
    sys.exit(code)


# ===================================================================== ED25519 CORE
# Pure-Python Ed25519 (RFC 8032). Written for this kit from the RFC 8032
# section 5.1 algorithm description and the section 6 reference structure
# (extended homogeneous coordinates). Code Components extracted from IETF
# documents are available under the Simplified BSD License; this file as a
# whole is MIT. Self-tested at start-up against RFC 8032 section 7.1 TEST 1-3.

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _sha512(b):
    return hashlib.sha512(b).digest()


def _pt_add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _P
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _P
    C = 2 * P[3] * Q[3] * _D % _P
    D = 2 * P[2] * Q[2] % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _pt_mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _pt_add(Q, P)
        P = _pt_add(P, P)
        s >>= 1
    return Q


def _pt_equal(P, Q):
    if (P[0] * Q[2] - Q[0] * P[2]) % _P != 0:
        return False
    return (P[1] * Q[2] - Q[1] * P[2]) % _P == 0


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * pow(5, _P - 2, _P) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _pt_compress(P):
    zinv = pow(P[2], _P - 2, _P)
    x, y = P[0] * zinv % _P, P[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _pt_decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _secret_expand(seed):
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    h = _sha512(seed)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_key(seed):
    a, _ = _secret_expand(seed)
    return _pt_compress(_pt_mul(a, _G))


def ed25519_sign(seed, msg):
    a, prefix = _secret_expand(seed)
    A = _pt_compress(_pt_mul(a, _G))
    r = int.from_bytes(_sha512(prefix + msg), "little") % _L
    R = _pt_compress(_pt_mul(r, _G))
    h = int.from_bytes(_sha512(R + A + msg), "little") % _L
    s = (r + h * a) % _L
    return R + int.to_bytes(s, 32, "little")


def ed25519_verify(pub, msg, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    A = _pt_decompress(pub)
    R = _pt_decompress(sig[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    h = int.from_bytes(_sha512(sig[:32] + pub + msg), "little") % _L
    return _pt_equal(_pt_mul(s, _G), _pt_add(R, _pt_mul(h, A)))


_RFC8032_VECTORS = [  # RFC 8032 section 7.1, TEST 1, 2, 3 (seed, pub, msg, sig)
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


def ed25519_selftest():
    for seed, pub, msg, sig in _RFC8032_VECTORS:
        s, m = bytes.fromhex(seed), bytes.fromhex(msg)
        if ed25519_public_key(s).hex() != pub:
            raise KitError("Ed25519 self-test failed (public key)")
        if ed25519_sign(s, m).hex() != sig:
            raise KitError("Ed25519 self-test failed (signature)")
        if not ed25519_verify(bytes.fromhex(pub), m, bytes.fromhex(sig)):
            raise KitError("Ed25519 self-test failed (verify)")
        if ed25519_verify(bytes.fromhex(pub), m + b"x", bytes.fromhex(sig)):
            raise KitError("Ed25519 self-test failed (accepted a forged message)")


def cross_check_with_cryptography(pub, msg, sig):
    """Optional second opinion. Returns True/False, or None if not installed."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
    except Exception:
        return None
    try:
        Ed25519PublicKey.from_public_bytes(pub).verify(sig, msg)
        return True
    except InvalidSignature:
        return False
# ================================================================= END ED25519 CORE


# ===================================================================== CANONICAL FORMS
def canonical_json(obj):
    """gate.py canonical_json, mirrored by core.ts canonicalJson (core.ts:59-67):
    sorted keys (code point order), separators (",", ":"), UTF-8,
    ensure_ascii=False, integers only, NO trailing newline."""
    _no_floats(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canon_pyjson_v1(obj):
    """canon-pyjson-v1 = the provenance-index entry rule, mirrored by core.ts
    pyDumpsDefault (core.ts:69-77): json.dumps(sort_keys=True,
    ensure_ascii=False) with Python's DEFAULT separators (", " and ": ")."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _no_floats(o):
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return
    if isinstance(o, int):
        if abs(o) > 2 ** 53 - 1:
            raise KitError("integer outside the JS safe range (core.ts:47)")
        return
    if isinstance(o, float):
        raise KitError("floats are not allowed in canonical form (core.ts:47)")
    if isinstance(o, dict):
        for v in o.values():
            _no_floats(v)
        return
    if isinstance(o, list):
        for v in o:
            _no_floats(v)
        return
    raise KitError("unsupported type in canonical form: %r" % type(o))


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


def seal(obj):
    """seal(o) = sha256(canonical_json(o)), core.ts:79."""
    return sha256_hex(canonical_json(obj))


def is_hex(s, n):
    return isinstance(s, str) and len(s) == n and set(s) <= HEX


def norm_name(s):
    """core.ts:81-83 normName: lowercase, keep a-z0-9 only."""
    return "".join(ch for ch in s.lower() if ch in "abcdefghijklmnopqrstuvwxyz0123456789")


ROLE_INDEPENDENT = "independent"
ROLE_HOUSE = "house"

# House operators (ASIN-HHC bots, Dennis, the Verifier, the board site).
# Comparisons use norm_name, the same rule as core.ts:81-83. A future house
# tier (pending Dennis) can pass role="house" to allow these names; the
# independent witness role, which is the only role this kit submits as,
# always refuses them. There is no house submit path in this version.
HOUSE_OPERATORS = (
    "AcePromoter",
    "AceLiaison",
    "ASIN-HHC Verifier",
    "asin-hhc.org",
    "grokace",
    "dbottrader",
    "dennischristie",
    "mankind_peace",
    "asinhhc",
)


def house_operators_norm():
    return frozenset(norm_name(x) for x in HOUSE_OPERATORS)


def is_house_operator(name):
    return norm_name(name) in house_operators_norm()


def check_operator(name, role=ROLE_INDEPENDENT, manifest=None):
    """Refuse house operators in the independent witness role.

    The live manifest's ineligible_operators list is also applied in the
    independent role. role="house" is accepted so a future house tier can
    allow these names without changing HOUSE_OPERATORS; this kit does not
    expose a house submit path.
    """
    if role not in (ROLE_INDEPENDENT, ROLE_HOUSE):
        raise KitError("unknown role %r (expected %s or %s)" % (role, ROLE_INDEPENDENT, ROLE_HOUSE))
    n = norm_name(name or "")
    if not n:
        raise KitError("operator %r is empty after normName (core.ts:81-83)" % name)
    if role == ROLE_INDEPENDENT and is_house_operator(name):
        raise KitError(
            "operator %r is a house operator (normalized %s) and cannot seal in the "
            "independent witness role. House names include: %s."
            % (name, n, ", ".join(HOUSE_OPERATORS))
        )
    if manifest is not None and role == ROLE_INDEPENDENT:
        inel = [norm_name(x) for x in manifest.get("independence", {}).get("ineligible_operators", [])]
        if n in inel:
            raise KitError(
                "operator %r is ineligible for this quest (manifest independence.ineligible_operators)."
                % name
            )
    return n


# ===================================================================== NETWORK
def http(method, url, body=None):
    headers = {"User-Agent": KIT_VERSION, "Cache-Control": "no-cache"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def fetch(url):
    status, raw = http("GET", url)
    if status != 200:
        raise KitError("HTTP %d for %s" % (status, url))
    return raw


# ===================================================================== EVIDENCE
def recompute_index(raw):
    """Recompute {count, head_hash} from the exact index bytes.
    Mirrors core.ts computeEvidence (core.ts:94-125) and SPEC section 3."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise KitError("index is not UTF-8 JSON: %s" % e)
    if not isinstance(doc, dict):
        raise KitError("index root is not a JSON object")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise KitError(".entries is null, missing, empty or not an array")
    prev = (doc.get("ledger_anchor") or {}).get("tip_hash")
    if not is_hex(prev, 64):
        raise KitError(".ledger_anchor.tip_hash missing or not 64 lowercase hex")
    problems = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise KitError("entry %d is not an object" % i)
        if e.get("prev_index_hash") != prev:
            problems.append("entry %d: prev_index_hash does not link to the previous recomputed hash" % i)
        body = {k: v for k, v in e.items() if k != "index_hash"}
        h = sha256_hex(canon_pyjson_v1(body))
        if h != e.get("index_hash"):
            problems.append("entry %d: index_hash does not recompute (got %s)" % (i, h))
        prev = h
    output = {"count": len(entries), "head_hash": prev}
    if doc.get("entry_count") != output["count"]:
        problems.append("declared entry_count %r != counted %d" % (doc.get("entry_count"), output["count"]))
    if doc.get("head_hash") != output["head_hash"]:
        problems.append("declared head_hash %r != recomputed head %s" % (doc.get("head_hash"), output["head_hash"]))
    return {
        "output": output,
        "sealed_output": seal(output),
        "observed": {
            "claim_sha256": sha256_hex(raw),
            "claim_bytes": len(raw),
            "first_entry_seal": seal(entries[0]),
        },
        "problems": problems,
    }


# ===================================================================== KEY
DEFAULT_KEY_REL = "~/.asinhhc/quest001-sealer.key"
KEY_FILENAME = "quest001-sealer.key"
OLD_CWD_KEY_NAME = KEY_FILENAME  # alias kept for callers/tests


def default_key_path():
    """Stable absolute path for the one-quest sealer key."""
    return os.path.abspath(os.path.expanduser(DEFAULT_KEY_REL))


def default_key_dir():
    return os.path.dirname(default_key_path())


def script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def resolve_key_path(path):
    return os.path.abspath(os.path.expanduser(path))


def existing_sealer_keys(target=None, extra=None, script_directory=None, cwd=None,
                         default_directory=None):
    """quest001-sealer.key files in the default dir, cwd, script dir, and optional --key path.

    `target` (the path we would mint or reuse) is omitted from the result so a
    caller can ask "is there some other key?".
    """
    target = resolve_key_path(target) if target else None
    default_directory = os.path.abspath(os.path.expanduser(
        default_directory if default_directory is not None else default_key_dir()))
    cwd = os.path.abspath(cwd if cwd is not None else os.getcwd())
    script_directory = os.path.abspath(
        script_directory if script_directory is not None else script_dir())
    candidates = [
        os.path.join(default_directory, KEY_FILENAME),
        os.path.join(cwd, KEY_FILENAME),
        os.path.join(script_directory, KEY_FILENAME),
    ]
    if extra:
        candidates.append(resolve_key_path(extra))
    found = []
    seen = set()
    for p in candidates:
        p = os.path.abspath(p)
        if p in seen or (target is not None and p == target):
            continue
        seen.add(p)
        if os.path.isfile(p):
            found.append(p)
    return found


def load_or_create_key(path, script_directory=None, cwd=None, default_directory=None):
    """32-byte Ed25519 seed as 64 hex chars in a 0600 file. Never uploaded.

    Returns (absolute_path, seed, created). Refuses to mint a new key when a
    quest001-sealer.key already exists in the default directory, the cwd, the
    script directory, or a --key path, unless --key (this path) points at that
    existing file.
    """
    path = resolve_key_path(path)
    if os.path.isfile(path):
        txt = open(path, "r", encoding="ascii").read().strip()
        if not is_hex(txt, 64):
            raise KitError("key file %s is not 64 lowercase hex" % path)
        return path, bytes.fromhex(txt), False
    others = existing_sealer_keys(
        target=path, extra=path, script_directory=script_directory,
        cwd=cwd, default_directory=default_directory)
    if others:
        raise KitError(
            "refusing to create a new key at %s because a key already exists at %s. "
            "Pass --key %s to reuse it. Do not move or delete the existing key; "
            "a new key is a new identity." % (path, others[0], others[0])
        )
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, mode=0o700)
    seed = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(seed.hex() + "\n")
    return path, seed, True


def load_saved_envelope(path):
    """Read a saved envelope file as exact bytes. Returns (abspath, env, raw, sha256)."""
    path = resolve_key_path(path)
    if not os.path.isfile(path):
        raise KitError("envelope file not found: %s" % path)
    raw = open(path, "rb").read()
    try:
        env = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise KitError("envelope file %s is not valid JSON: %s" % (path, e))
    if not isinstance(env, dict):
        raise KitError("envelope file %s is not a JSON object" % path)
    return path, env, raw, sha256_hex(raw)


def quest_slug(quest_id):
    return {v[0]: k for k, v in QUESTS.items()}.get(quest_id)


def verify_saved_envelope_expiry(env, now=None):
    """Refuse a saved envelope whose expires_at has passed (would be 422 expired)."""
    now = now or datetime.now(timezone.utc)
    try:
        expires = parse_iso(env["expires_at"])
    except Exception:
        raise KitError("envelope expires_at is missing or not ISO-8601")
    if now >= expires:
        raise KitError(
            "this envelope expired at %s (now %s). The default TTL is 60 minutes; "
            "approving later than that gets HTTP 422 expired. Re-run a dry run to "
            "get a new envelope, then submit that new file with --submit-file."
            % (env.get("expires_at"), iso(now))
        )
    return now


def verify_saved_envelope_live(env, now=None, manifest_raw=None, fetch_live=True):
    """Before POST: live manifest hash must match, and now must be before the deadline."""
    now = now or datetime.now(timezone.utc)
    quest_id = env.get("quest_id")
    slug = quest_slug(quest_id)
    if not slug:
        raise KitError("envelope quest_id %r is not a known quest" % quest_id)
    if manifest_raw is None and fetch_live:
        manifest_raw = fetch("%s/%s/manifest" % (BASE, slug))
    if manifest_raw is None:
        raise KitError("no live manifest available to check envelope manifest_sha256 and deadline")
    if isinstance(manifest_raw, str):
        manifest_raw = manifest_raw.encode("utf-8")
    live_sha = sha256_hex(manifest_raw)
    env_sha = env.get("manifest_sha256")
    if env_sha != live_sha:
        raise KitError(
            "envelope manifest_sha256 %s does not match the live %s manifest sha256 %s. "
            "The manifest changed after this envelope was built. Re-run the dry run "
            "against the current manifest, then submit that new file with --submit-file."
            % (env_sha, quest_id, live_sha)
        )
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        deadline = parse_iso(manifest["deadline"])
    except Exception:
        raise KitError("live manifest is not valid JSON or its deadline is missing")
    if now >= deadline:
        raise KitError(
            "%s is closed (deadline %s, now %s). The service would answer 410 quest_closed. "
            "No seal can be accepted." % (quest_id, manifest["deadline"], iso(now))
        )
    print("[ok ] envelope manifest_sha256 matches the live %s manifest %s" % (quest_id, live_sha),
          file=sys.stderr)
    print("[ok ] quest still open (deadline %s)" % manifest["deadline"], file=sys.stderr)
    return manifest


def submit_saved_file(path, post=True, now=None, manifest_raw=None, fetch_live=True,
                      role=ROLE_INDEPENDENT):
    """Re-verify a saved envelope and optionally POST its exact file bytes.

    Local checks, all before any POST: signatures, house-operator refusal in
    the independent role, live manifest hash, now < deadline, now < expires_at.
    post=False is for tests: verify and return without POSTing.
    Returns 0 on success, or a (env, raw, digest) tuple when post is False.
    """
    path, env, raw, digest = load_saved_envelope(path)
    quest_id = env.get("quest_id")
    slug = quest_slug(quest_id)
    print("[ok ] loaded envelope %s" % path, file=sys.stderr)
    print("[ok ] envelope sha256 %s  (must match the file you approved)" % digest, file=sys.stderr)
    print("[ok ] quest_id %s  request_id %s  expires_at %s" % (
        quest_id, env.get("request_id"), env.get("expires_at")), file=sys.stderr)
    had_cc = self_verify(env)
    print("[ok ] both signatures verify locally%s" %
          (" and with `cryptography`" if had_cc else " (cryptography not installed; pure-Python only)"),
          file=sys.stderr)
    check_operator(env.get("operator"), role=role)
    verify_saved_envelope_live(env, now=now, manifest_raw=manifest_raw, fetch_live=fetch_live)
    verify_saved_envelope_expiry(env, now=now)
    print("[ok ] not expired", file=sys.stderr)
    if not post:
        return env, raw, digest
    if quest_id not in {v[0] for v in QUESTS.values()}:
        raise KitError("envelope quest_id %r is not a known quest" % quest_id)
    status, body = http("POST", SEAL_DROP_URL, raw)
    try:
        resp = json.loads(body.decode("utf-8"))
    except ValueError:
        resp = {"raw": body.decode("utf-8", "replace")[:500]}
    print("[net] POST %s -> HTTP %d  (exact file bytes, sha256 %s)" % (SEAL_DROP_URL, status, digest),
          file=sys.stderr)
    print(json.dumps({"http_status": status, "envelope_sha256": digest,
                      "request_id": env.get("request_id"), "response": resp},
                     indent=2, ensure_ascii=False))
    if status == 201 and resp.get("accepted") is True:
        print("[ok ] ACCEPTED into the %s chronicle (acceptance is not a verdict, and no payment is made).\n"
              "      chronicle: %s/%s\n      verdict:   %s/%s/verdict\n      replay:    %s/%s/replay"
              % (quest_id, BASE, slug, BASE, slug, BASE, slug), file=sys.stderr)
        return 0
    print("[err] NOT accepted: %s %s" % (resp.get("code"), resp.get("detail")), file=sys.stderr)
    return 3


# ===================================================================== ENVELOPE
def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_envelope(seed, quest_id, manifest_sha, ev, operator, failure_mode,
                   implementation, issued, expires):
    pub = ed25519_public_key(seed)
    env = {
        "schema": ENVELOPE_SCHEMA,
        "quest_id": quest_id,
        "manifest_sha256": manifest_sha,
        "request_id": str(uuid.uuid4()),
        "nonce": secrets.token_hex(32),
        "issued_at": iso(issued),
        "expires_at": iso(expires),
        "key_id": sha256_hex(pub),                      # core.ts:183
        "pubkey": pub.hex(),
        "operator": operator,
        "failure_mode": failure_mode,
        "implementation": implementation,
        "output": ev["output"],
        "sealed_output": ev["sealed_output"],
        "observed": ev["observed"],
    }
    # signature: over the UTF-8 bytes of the sealed_output hex string (core.ts:199)
    env["signature"] = ed25519_sign(seed, env["sealed_output"].encode("utf-8")).hex()
    # envelope_signature: over canonical_json of the 15 signed fields (core.ts:200-204)
    signed = {k: env[k] for k in SIGNED_FIELDS}
    env["envelope_signature"] = ed25519_sign(seed, canonical_json(signed)).hex()
    return env


def self_verify(env):
    """Offline re-run of the stateless intake checks we can do locally."""
    pub = bytes.fromhex(env["pubkey"])
    msgs = [
        ("signature", env["sealed_output"].encode("utf-8"), env["signature"]),
        ("envelope_signature", canonical_json({k: env[k] for k in SIGNED_FIELDS}),
         env["envelope_signature"]),
    ]
    for name, msg, sig in msgs:
        sigb = bytes.fromhex(sig)
        if not ed25519_verify(pub, msg, sigb):
            raise KitError("%s does not verify locally" % name)
        cc = cross_check_with_cryptography(pub, msg, sigb)
        if cc is False:
            raise KitError("%s rejected by the `cryptography` cross-check" % name)
    if seal(env["output"]) != env["sealed_output"]:
        raise KitError("sealed_output != seal(output)")
    if sha256_hex(pub) != env["key_id"]:
        raise KitError("key_id != sha256(pubkey bytes)")
    if len(json.dumps(env)) > 16384:
        raise KitError("envelope larger than the 16 KiB intake limit (index.ts:69)")
    return cross_check_with_cryptography(pub, b"", ed25519_sign(b"\x00" * 32, b"")) is not None


# ===================================================================== MAIN
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Independently recompute the ASIN-HHC Quest 001 provenance index "
                    "and build a signed seal-drop envelope. Dry run by default.")
    ap.add_argument("--operator", help="who runs this witness (1-80 printable chars); "
                    "must differ from every other sealer and not be on the manifest's "
                    "ineligible_operators list")
    ap.add_argument("--failure-mode", help="how this witness could be wrong: your tooling, "
                    "network path, data source (1-400 chars); must differ from other sealers")
    ap.add_argument("--implementation", default=None,
                    help="software + version + host type (default: auto)")
    ap.add_argument("--key", default=None,
                    help="path of your Ed25519 seed file (default: ~/.asinhhc/quest001-sealer.key, "
                         "stored as an absolute path). Created with mode 0600 if missing.")
    ap.add_argument("--ttl-minutes", type=int, default=60,
                    help="envelope lifetime; clipped to the quest deadline (default 60)")
    ap.add_argument("--out", default=None, help="where to save the envelope JSON")
    ap.add_argument("--test-quest", action="store_true",
                    help="maintainer only: target QUEST-001-TEST (closed unless Dennis reopens it; no reward)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="(default) compute, sign, print and save; do not submit")
    mode.add_argument("--submit", action="store_true",
                      help="refused: this flag used to rebuild a new envelope and POST it. "
                           "Use --submit-file PATH to POST the exact saved file you approved.")
    mode.add_argument("--submit-file", metavar="PATH",
                      help="POST this exact saved envelope file (no rebuild). Re-verifies "
                           "signatures and expiry first and prints sha256 so you can match "
                           "the file you approved.")
    mode.add_argument("--recompute-only", action="store_true",
                      help="only fetch and recompute the index; no key, no envelope")
    a = ap.parse_args(argv)

    if a.submit:
        die("do not use --submit. It used to rebuild a new envelope, so the file you "
            "approved would not be the one posted. Submit the exact saved file:\n"
            "  python3 seal_quest001.py --submit-file PATH")

    if a.submit_file:
        print("[kit] %s  mode=submit-file %s" % (KIT_VERSION, a.submit_file), file=sys.stderr)
        try:
            ed25519_selftest()
            print("[ok ] Ed25519 RFC 8032 self-test (3 vectors) passed", file=sys.stderr)
            return submit_saved_file(a.submit_file, post=True)
        except KitError as e:
            die(str(e))
        except urllib.error.URLError as e:
            die("network error: %s" % e)

    slug = "quest-001-test" if a.test_quest else "quest-001"
    quest_id, pinned_manifest = QUESTS[slug]
    print("[kit] %s  target=%s  mode=%s" % (KIT_VERSION, quest_id,
          "recompute-only" if a.recompute_only else "dry-run"),
          file=sys.stderr)

    try:
        ed25519_selftest()
        print("[ok ] Ed25519 RFC 8032 self-test (3 vectors) passed", file=sys.stderr)

        # 1. manifest
        manifest_raw = fetch("%s/%s/manifest" % (BASE, slug))
        manifest_sha = sha256_hex(manifest_raw)
        manifest = json.loads(manifest_raw.decode("utf-8"))
        if manifest.get("quest_id") != quest_id:
            raise KitError("manifest quest_id %r != %s" % (manifest.get("quest_id"), quest_id))
        if manifest_sha not in pinned_manifest:
            raise KitError("manifest sha256 %s not in pinned %s. The manifest changed; re-read "
                           "RULES.md and the quest page before sealing." % (manifest_sha, pinned_manifest))
        print("[ok ] manifest %s sha256 %s" % (quest_id, manifest_sha), file=sys.stderr)

        # 2. index bytes
        claim = manifest["claim"]
        raw = fetch(claim["url"])
        got = sha256_hex(raw)
        if got != claim["sha256"] or len(raw) != claim["bytes"]:
            raise KitError("index changed since the manifest: sha256 %s bytes %d (manifest: %s / %d). "
                           "Do not seal." % (got, len(raw), claim["sha256"], claim["bytes"]))
        print("[ok ] index %s sha256 %s bytes %d" % (claim["url"], got, len(raw)), file=sys.stderr)

        # 3. recompute
        ev = recompute_index(raw)
        if ev["problems"]:
            raise KitError("recompute MISMATCH:\n  - " + "\n  - ".join(ev["problems"]))
        print("[ok ] recompute PASS: %d entries, every index_hash and prev_index_hash link "
              "recomputes, head %s" % (ev["output"]["count"], ev["output"]["head_hash"]), file=sys.stderr)
        print("[ok ] sealed_output %s" % ev["sealed_output"], file=sys.stderr)

        if a.recompute_only:
            print(json.dumps({"quest_id": quest_id, "manifest_sha256": manifest_sha,
                              "recompute": "PASS", **{k: ev[k] for k in ("output", "sealed_output", "observed")}},
                             indent=2))
            return 0

        # 4. identity checks
        if not a.operator or not a.failure_mode:
            raise KitError("--operator and --failure-mode are required to build an envelope")
        for name, val, mx in (("operator", a.operator, 80), ("failure-mode", a.failure_mode, 400)):
            if not val.strip() or len(val) > mx or any(ord(c) < 32 or ord(c) == 127 for c in val):
                raise KitError("--%s must be 1-%d printable characters" % (name, mx))
        # Independent witness role is the only role this kit builds envelopes for.
        check_operator(a.operator, role=ROLE_INDEPENDENT, manifest=manifest)
        impl = a.implementation or ("%s; Python %s; %s %s" % (
            KIT_VERSION, platform.python_version(), platform.system(), platform.machine()))[:400]

        # 5. time window (core.ts:185-193)
        now = datetime.now(timezone.utc)
        deadline = parse_iso(manifest["deadline"])
        valid_from = parse_iso(manifest["valid_from"])
        closed = now >= deadline
        if closed:
            msg = "%s closed at %s" % (quest_id, manifest["deadline"])
            if not a.test_quest:
                raise KitError(msg + ". No seal can be accepted.")
            print("[warn] " + msg + "; the service will answer 410 quest_closed", file=sys.stderr)
        issued = now - timedelta(seconds=5)
        if issued < valid_from:
            raise KitError("too early: quest window opens %s" % manifest["valid_from"])
        expires = min(now + timedelta(minutes=a.ttl_minutes), deadline)
        if closed:
            expires = now + timedelta(minutes=a.ttl_minutes)

        # 6. key + envelope (dry run: save the exact file; do not POST)
        key_path, seed, created = load_or_create_key(a.key or default_key_path())
        print("[ok ] key %s %s (keep it private; it never leaves this machine)" %
              (key_path, "CREATED" if created else "reused"), file=sys.stderr)
        print("[ok ] do not move or delete this key file. Running from another folder "
              "used to silently mint a new key; pass --key %s if you run from somewhere else."
              % key_path, file=sys.stderr)
        env = build_envelope(seed, quest_id, manifest_sha, ev, a.operator, a.failure_mode,
                             impl, issued, expires)
        had_cc = self_verify(env)
        print("[ok ] both signatures verify locally%s" %
              (" and with `cryptography`" if had_cc else " (cryptography not installed; pure-Python only)"),
              file=sys.stderr)
        out = os.path.abspath(a.out or "quest001-envelope-%s.json" % env["request_id"][:8])
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(env, f, indent=2, ensure_ascii=False)
            f.write("\n")
        raw = open(out, "rb").read()
        digest = sha256_hex(raw)
        print("[ok ] envelope saved to %s" % out, file=sys.stderr)
        print("[ok ] envelope sha256 %s" % digest, file=sys.stderr)
        print("[ok ] default TTL is %d minutes (expires_at %s). Approving later than that "
              "gets HTTP 422 expired; re-run this dry run for a new envelope."
              % (a.ttl_minutes, env["expires_at"]), file=sys.stderr)
        print(json.dumps(env, indent=2, ensure_ascii=False))
        print("[dry] not submitted. After you approve this exact file, run:", file=sys.stderr)
        print("      python3 seal_quest001.py --submit-file %s" % out, file=sys.stderr)
        return 0
    except KitError as e:
        die(str(e))
    except urllib.error.URLError as e:
        die("network error: %s" % e)


if __name__ == "__main__":
    sys.exit(main())
