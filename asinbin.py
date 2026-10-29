#!/usr/bin/env python3
"""ASNB — ASIN Binary, the fleet's own binary format (invented 2026-10-29, Dennis's order).
Layout: magic 'ASNB' | ver u8=1 | count u32le | records | sha256 trailer (32B over all prior bytes).
Record: 6 fields (id,type,name,status,anchor,created), each u16le length + utf8 bytes.
Encoding is NOT encryption — integrity comes from the checksum; secrecy stays with keys (CP-0019).
Usage: python3 asinbin.py encode registry.jsonl registry.cpbin | decode registry.cpbin
"""
import sys, json, struct, hashlib, pathlib

FIELDS = ["id", "type", "name", "status", "anchor", "created"]

def encode(rows):
    out = bytearray(b"ASNB" + struct.pack("<BI", 1, len(rows)))
    for r in rows:
        for f in FIELDS:
            b = str(r.get(f, "")).encode()
            out += struct.pack("<H", len(b)) + b
    out += hashlib.sha256(bytes(out)).digest()
    return bytes(out)

def decode(data):
    assert data[:4] == b"ASNB", "bad magic — not ASNB"
    assert hashlib.sha256(data[:-32]).digest() == data[-32:], "checksum fail — corrupted or tampered"
    ver, count = struct.unpack_from("<BI", data, 4)
    assert ver == 1, f"unsupported version {ver}"
    pos, rows = 9, []
    for _ in range(count):
        r = {}
        for f in FIELDS:
            (n,) = struct.unpack_from("<H", data, pos); pos += 2
            r[f] = data[pos:pos+n].decode(); pos += n
        rows.append(r)
    return rows

if __name__ == "__main__":
    if sys.argv[1] == "encode":
        rows = [json.loads(l) for l in pathlib.Path(sys.argv[2]).read_text().splitlines() if l.strip()]
        blob = encode(rows)
        pathlib.Path(sys.argv[3]).write_bytes(blob)
        print(f"encoded {len(rows)} records -> {sys.argv[3]} ({len(blob)} bytes, sha256 {hashlib.sha256(blob).hexdigest()[:16]}…)")
    elif sys.argv[1] == "decode":
        rows = decode(pathlib.Path(sys.argv[2]).read_bytes())
        print(json.dumps(rows, indent=1)[:600]); print(f"… {len(rows)} records, checksum verified")
