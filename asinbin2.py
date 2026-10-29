#!/usr/bin/env python3
"""ASNB v2 — ASIN Binary with a signed trailer (extends asinbin.py v1, CP-0020/CP-0021).

Layout v2: magic 'ASNB' | ver u8=2 | count u32le | records | trailer (96B).
Record: identical to v1 — 6 fields (id,type,name,status,anchor,created),
each u16le length + utf8 bytes. No field names on the wire.
Trailer v2: SHA-256 (32B) over every preceding byte, followed by an Ed25519
signature (64B) over those same preceding bytes. The version byte selects the
trailer length: v1 = 32B (hash only), v2 = 96B (hash + signature).

Decode handles BOTH versions and fails closed: bad magic, unsupported version,
truncated data, trailing garbage, hash mismatch, missing pubkey for v2, or an
invalid signature all raise AsnbError — nothing is returned on partial trust.

Signing reuses the fleet's pure-python ed25519 (same module crypto.py uses).
Key handling follows crypto.py's pattern — seed in a 0600 file inside a 0700
dir — but this tool NEVER defaults to the fleet key in asinmcp/keys/: the seed
and pubkey files are always passed explicitly (--seed-file / --pub-file).

Encoding is NOT encryption (CP-0019): v2 adds tamper-evidence AND origin
proof; secrecy still lives in keys, never in the format.

Usage:
  python3 asinbin2.py genkey <dir>                          # throwaway or fleet keypair into <dir>
  python3 asinbin2.py encode <in.jsonl> <out.cpbin2> --seed-file <dir/seed>
  python3 asinbin2.py decode <file.cpbin|file.cpbin2> [--pub-file <dir/pub>]
"""
import sys, os, json, struct, hashlib, pathlib

sys.path.insert(0, str(pathlib.Path.home() / "workspace/asinmolt-node"))
import ed25519

FIELDS = ["id", "type", "name", "status", "anchor", "created"]
HEADER_LEN = 9            # magic(4) + version(1) + count u32le(4)
TRAILER_LEN = {1: 32, 2: 96}


class AsnbError(Exception):
    """Raised on any integrity, format, or trust failure. Decode fails closed."""


def _parse_records(data, count, end):
    pos, rows = HEADER_LEN, []
    try:
        for _ in range(count):
            r = {}
            for f in FIELDS:
                if pos + 2 > end:
                    raise AsnbError("truncated data — field length past payload end")
                (n,) = struct.unpack_from("<H", data, pos); pos += 2
                if pos + n > end:
                    raise AsnbError("truncated data — field bytes past payload end")
                r[f] = data[pos:pos + n].decode(); pos += n
            rows.append(r)
    except (UnicodeDecodeError, struct.error) as e:
        raise AsnbError(f"unparseable records: {e}") from e
    if pos != end:
        raise AsnbError(f"trailing garbage — records end at {pos}, payload ends at {end}")
    return rows


def encode(rows, seed_hex):
    """Encode rows as ASNB v2, signed with the given Ed25519 seed (hex)."""
    out = bytearray(b"ASNB" + struct.pack("<BI", 2, len(rows)))
    for r in rows:
        for f in FIELDS:
            b = str(r.get(f, "")).encode()
            if len(b) > 0xFFFF:
                raise AsnbError(f"field {f!r} too long for u16 length: {len(b)} bytes")
            out += struct.pack("<H", len(b)) + b
    pre = bytes(out)
    sig = bytes.fromhex(ed25519.sign(seed_hex, pre))
    return pre + hashlib.sha256(pre).digest() + sig


def decode(data, pubkey_hex=None):
    """Decode an ASNB v1 or v2 blob. v2 requires pubkey_hex to check the
    signature; without it, v2 decode fails closed. Any mismatch raises."""
    if len(data) < HEADER_LEN + 32:
        raise AsnbError("truncated data — shorter than header + smallest trailer")
    if data[:4] != b"ASNB":
        raise AsnbError("bad magic — not ASNB")
    ver, count = struct.unpack_from("<BI", data, 4)
    if ver not in TRAILER_LEN:
        raise AsnbError(f"unsupported version {ver}")
    tlen = TRAILER_LEN[ver]
    if len(data) < HEADER_LEN + tlen:
        raise AsnbError(f"truncated data — v{ver} needs at least {HEADER_LEN + tlen} bytes")
    pre, trailer = data[:-tlen], data[-tlen:]
    if hashlib.sha256(pre).digest() != trailer[:32]:
        raise AsnbError("hash fail — corrupted or tampered")
    if ver == 2:
        if pubkey_hex is None:
            raise AsnbError("v2 decode requires a pubkey to verify the signature — failing closed")
        if not ed25519.verify(pubkey_hex, pre, trailer[32:].hex()):
            raise AsnbError("signature fail — not signed by this key, or tampered")
    return _parse_records(data, count, len(data) - tlen)


def genkey(dirpath):
    """crypto.py-style keypair: dir 0700, seed file 0600, pub file alongside."""
    d = pathlib.Path(dirpath)
    d.mkdir(parents=True, exist_ok=True); os.chmod(d, 0o700)
    seed_f, pub_f = d / "asnb2.seed", d / "asnb2.pub"
    if seed_f.exists():
        print("key already exists:", pub_f.read_text().strip()); return
    seed_hex, pub_hex = ed25519.generate_keypair()
    seed_f.write_text(seed_hex); os.chmod(seed_f, 0o600)
    pub_f.write_text(pub_hex)
    print("pubkey:", pub_hex)


def _opt(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "genkey":
        genkey(sys.argv[2])
    elif cmd == "encode":
        seed_f = _opt("--seed-file")
        if not seed_f:
            sys.exit("encode requires --seed-file <path> (no default key — see docstring)")
        rows = [json.loads(l) for l in pathlib.Path(sys.argv[2]).read_text().splitlines() if l.strip()]
        blob = encode(rows, pathlib.Path(seed_f).read_text().strip())
        pathlib.Path(sys.argv[3]).write_bytes(blob)
        print(f"encoded {len(rows)} records -> {sys.argv[3]} ({len(blob)} bytes, sha256 {hashlib.sha256(blob).hexdigest()[:16]}…)")
    elif cmd == "decode":
        pub_f = _opt("--pub-file")
        pub = pathlib.Path(pub_f).read_text().strip() if pub_f else None
        try:
            rows = decode(pathlib.Path(sys.argv[2]).read_bytes(), pub)
        except AsnbError as e:
            print(f"REJECTED: {e}"); sys.exit(1)
        print(json.dumps(rows, indent=1)[:600]); print(f"… {len(rows)} records, integrity verified")
    else:
        sys.exit(f"unknown command {cmd!r} — genkey | encode | decode")
