#!/usr/bin/env python3
"""QUEST-001 "Seal the Index" — reference witness verifier (Python).

Implements quest001/QUEST-001-SPEC.md. Standard library only; uses the
`cryptography` package for Ed25519 when installed, else the vendored
pure-python RFC 8032 implementation at the repo root (../ed25519.py).

Subcommands
  compute  [--claim-url URL | --claim-file PATH] [--manifest PATH_OR_URL]
           Fetch the claim, check it against the manifest, recompute
           {count, head_hash} and print the evidence as JSON.
  keygen   --key PATH          Create a new Ed25519 seed file (0600).
  seal     --key PATH --manifest PATH_OR_URL --operator NAME
           --failure-mode TEXT [--implementation TEXT] [--ttl-hours N]
           Compute evidence and emit a signed PoP envelope on stdout.
  check-envelope PATH          Verify an envelope's seal and signatures offline.

Nothing here submits anything; you POST the envelope yourself.
"""
import argparse
import hashlib
import json
import os
import secrets
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

ENVELOPE_SCHEMA = "ASIN-HHC-QUEST-SEAL-1.0"
HEX = set("0123456789abcdef")


# --------------------------------------------------------------------------
# Canonical forms (SPEC §2)
# --------------------------------------------------------------------------

def canonical_json(obj) -> bytes:
    """gate.py canonical form: sorted keys, compact separators, UTF-8,
    no ASCII escaping, NO trailing newline."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(obj) -> str:
    return sha256_hex(canonical_json(obj))


def index_entry_hash(entry: dict) -> str:
    """Provenance-index chain rule (artifacts/specs/verify_index.py):
    sha256 over json.dumps(entry minus index_hash, sort_keys=True,
    ensure_ascii=False) with Python's DEFAULT separators (", " / ": ")."""
    canon = {k: entry[k] for k in sorted(entry) if k != "index_hash"}
    return sha256_hex(json.dumps(canon, sort_keys=True,
                                 ensure_ascii=False).encode("utf-8"))


def is_hex(s, n) -> bool:
    return isinstance(s, str) and len(s) == n and set(s) <= HEX


# --------------------------------------------------------------------------
# Evidence (SPEC §3)
# --------------------------------------------------------------------------

class ClaimError(Exception):
    pass


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "asin-hhc-quest001-verifier/1.0",
        "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise ClaimError(f"HTTP {r.status} for {url}")
        return r.read()


def compute_evidence(raw: bytes) -> dict:
    """Recompute the witness output from the exact claim bytes."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ClaimError(f"claim is not UTF-8 JSON: {e}")
    if not isinstance(doc, dict):
        raise ClaimError("claim root is not an object")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ClaimError(".entries is null, missing, empty or not an array")
    if any(not isinstance(e, dict) for e in entries):
        raise ClaimError(".entries contains a non-object")
    anchor = doc.get("ledger_anchor") or {}
    prev = anchor.get("tip_hash")
    if not is_hex(prev, 64):
        raise ClaimError(".ledger_anchor.tip_hash missing or not 64-hex")
    problems = []
    for i, e in enumerate(entries):
        if e.get("prev_index_hash") != prev:
            problems.append(f"entry {i}: prev_index_hash does not link")
        h = index_entry_hash(e)
        if h != e.get("index_hash"):
            problems.append(f"entry {i}: index_hash does not recompute")
        prev = h
    output = {"count": len(entries), "head_hash": prev}
    if doc.get("entry_count") != output["count"]:
        problems.append("declared entry_count != counted entries")
    if doc.get("head_hash") != output["head_hash"]:
        problems.append("declared head_hash != recomputed chain head")
    return {
        "output": output,
        "sealed_output": seal(output),
        "observed": {
            "claim_sha256": sha256_hex(raw),
            "claim_bytes": len(raw),
            "first_entry_seal": seal(entries[0]),
        },
        "consistent_with_declared": not problems,
        "problems": problems,
    }


def load_manifest(src: str):
    raw = fetch_bytes(src) if src.startswith(("http://", "https://")) \
        else open(src, "rb").read()
    return json.loads(raw.decode("utf-8")), sha256_hex(raw)


def evidence_for_manifest(manifest: dict, claim_file=None) -> dict:
    claim = manifest["claim"]
    raw = open(claim_file, "rb").read() if claim_file \
        else fetch_bytes(claim["url"])
    got = sha256_hex(raw)
    if got != claim["sha256"] or len(raw) != claim["bytes"]:
        raise ClaimError(
            f"claim changed since manifest: sha256 {got} bytes {len(raw)} "
            f"(manifest: {claim['sha256']} / {claim['bytes']}) — do not seal")
    return compute_evidence(raw)


# --------------------------------------------------------------------------
# Ed25519 (cryptography if present, vendored RFC 8032 otherwise)
# --------------------------------------------------------------------------

def _vendored():
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(here))
    import ed25519  # noqa: E402
    return ed25519


def pubkey_from_seed(seed: bytes) -> str:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import \
            Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization as s
        k = Ed25519PrivateKey.from_private_bytes(seed)
        return k.public_key().public_bytes(s.Encoding.Raw,
                                           s.PublicFormat.Raw).hex()
    except ImportError:
        return _vendored().pubkey_from_seed(seed).hex()


def ed_sign(seed: bytes, msg: bytes) -> str:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import \
            Ed25519PrivateKey
        return Ed25519PrivateKey.from_private_bytes(seed).sign(msg).hex()
    except ImportError:
        return _vendored().sign(seed.hex(), msg)


def ed_verify(pub_hex: str, msg: bytes, sig_hex: str) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import \
            Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex)) \
                .verify(bytes.fromhex(sig_hex), msg)
            return True
        except (InvalidSignature, ValueError):
            return False
    except ImportError:
        try:
            return _vendored().verify(pub_hex, msg, sig_hex)
        except Exception:
            return False


# --------------------------------------------------------------------------
# PoP envelope (SPEC §4)
# --------------------------------------------------------------------------

SIGNED_FIELDS = ("schema", "quest_id", "manifest_sha256", "request_id",
                 "nonce", "issued_at", "expires_at", "key_id", "pubkey",
                 "operator", "failure_mode", "implementation", "output",
                 "sealed_output", "observed")


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        raise ValueError("timestamp without offset")
    return dt


def envelope_signing_bytes(env: dict) -> bytes:
    return canonical_json({k: env[k] for k in SIGNED_FIELDS})


def build_envelope(seed: bytes, manifest: dict, manifest_sha: str,
                   evidence: dict, operator: str, failure_mode: str,
                   implementation: str, ttl_hours: float = 24.0,
                   now: datetime | None = None, nonce: str | None = None,
                   request_id: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    deadline = parse_iso(manifest["deadline"])
    expires = min(now + timedelta(hours=ttl_hours), deadline)
    pub = pubkey_from_seed(seed)
    env = {
        "schema": ENVELOPE_SCHEMA,
        "quest_id": manifest["quest_id"],
        "manifest_sha256": manifest_sha,
        "request_id": request_id or str(uuid.uuid4()),
        "nonce": nonce or secrets.token_hex(32),
        "issued_at": iso_z(now),
        "expires_at": iso_z(expires),
        "key_id": sha256_hex(bytes.fromhex(pub)),
        "pubkey": pub,
        "operator": operator,
        "failure_mode": failure_mode,
        "implementation": implementation,
        "output": evidence["output"],
        "sealed_output": evidence["sealed_output"],
        "observed": evidence["observed"],
    }
    env["signature"] = ed_sign(seed, env["sealed_output"].encode("utf-8"))
    env["envelope_signature"] = ed_sign(seed, envelope_signing_bytes(env))
    return env


def check_envelope(env: dict) -> list:
    """Offline structural + cryptographic check. Returns problems."""
    p = []
    for k in SIGNED_FIELDS + ("signature", "envelope_signature"):
        if k not in env:
            p.append(f"missing {k}")
    if p:
        return p
    if seal(env["output"]) != env["sealed_output"]:
        p.append("sealed_output != sha256(canonical_json(output))")
    if not is_hex(env["pubkey"], 64):
        p.append("pubkey not 64-hex")
    elif env["key_id"] != sha256_hex(bytes.fromhex(env["pubkey"])):
        p.append("key_id != sha256(pubkey bytes)")
    if not ed_verify(env["pubkey"], env["sealed_output"].encode(),
                     env["signature"]):
        p.append("signature invalid")
    if not ed_verify(env["pubkey"], envelope_signing_bytes(env),
                     env["envelope_signature"]):
        p.append("envelope_signature invalid")
    return p


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compute")
    c.add_argument("--claim-url")
    c.add_argument("--claim-file")
    c.add_argument("--manifest")
    k = sub.add_parser("keygen")
    k.add_argument("--key", required=True)
    s = sub.add_parser("seal")
    s.add_argument("--key", required=True)
    s.add_argument("--manifest", required=True)
    s.add_argument("--operator", required=True)
    s.add_argument("--failure-mode", required=True)
    s.add_argument("--implementation",
                   default="asinmcp quest001/verify_quest001.py (Python "
                   f"{sys.version.split()[0]})")
    s.add_argument("--claim-file")
    s.add_argument("--ttl-hours", type=float, default=24.0)
    e = sub.add_parser("check-envelope")
    e.add_argument("path")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "compute":
            if a.manifest:
                m, msha = load_manifest(a.manifest)
                ev = evidence_for_manifest(m, a.claim_file)
                ev["manifest_sha256"] = msha
            else:
                raw = open(a.claim_file, "rb").read() if a.claim_file \
                    else fetch_bytes(a.claim_url)
                ev = compute_evidence(raw)
            print(json.dumps(ev, indent=2, sort_keys=True))
            return 0 if ev["consistent_with_declared"] else 2
        if a.cmd == "keygen":
            if os.path.exists(a.key):
                print(f"refusing to overwrite {a.key}", file=sys.stderr)
                return 1
            fd = os.open(a.key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            seed = secrets.token_bytes(32)
            os.write(fd, seed.hex().encode())
            os.close(fd)
            print(json.dumps({"pubkey": pubkey_from_seed(seed),
                              "key_id": sha256_hex(bytes.fromhex(
                                  pubkey_from_seed(seed)))}))
            return 0
        if a.cmd == "seal":
            seed = bytes.fromhex(open(a.key).read().strip())
            m, msha = load_manifest(a.manifest)
            ev = evidence_for_manifest(m, a.claim_file)
            env = build_envelope(seed, m, msha, ev, a.operator,
                                 a.failure_mode, a.implementation,
                                 a.ttl_hours)
            print(json.dumps(env, indent=2, sort_keys=True))
            if not ev["consistent_with_declared"]:
                print("WARNING: claim inconsistent with its declared values: "
                      + "; ".join(ev["problems"]), file=sys.stderr)
            return 0
        if a.cmd == "check-envelope":
            env = json.load(open(a.path))
            p = check_envelope(env)
            print(json.dumps({"ok": not p, "problems": p}))
            return 0 if not p else 1
    except ClaimError as ex:
        print(f"CLAIM ERROR: {ex}", file=sys.stderr)
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
