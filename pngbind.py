#!/usr/bin/env python3
"""pngbind — CP-0023 geometric-memory BIND, in-file.

Embeds a signed binding record into a PNG's own tEXt chunks so the artifact
carries its provenance with it: any holder of the file can verify, without
trusting any external index, (1) the image content is the content that was
bound (SHA-256 over the concatenated IDAT data — stable across metadata
edits), and (2) the binding was issued by the pinned fleet key (Ed25519).

Chunks written (before IEND):
  asinmcp:binding      canonical JSON binding record
  asinmcp:binding.sig  hex Ed25519 signature over the exact binding bytes

The original file is never modified (STORE rule): bind writes a new file.
Re-binding a bound file is refused — a re-bind is a SPLIT event and must be
issued as a new binding version referencing the shed one, never an edit.

Usage:
  python3 pngbind.py bind <in.png> <out.png> <snapshot_id> <release_class>
  python3 pngbind.py verify <file.png>
"""
import sys, os, json, hashlib, struct, zlib, pathlib, datetime
sys.path.insert(0, str(pathlib.Path.home() / "workspace/asinmolt-node"))
import ed25519

BASE = pathlib.Path(__file__).parent
KEYS = BASE / "keys"
SEED = KEYS / "ace-lattice.seed"
PUBF = KEYS / "ace-lattice.pub"
SIG8 = b"\x89PNG\r\n\x1a\n"

# The fleet signing pubkey is PUBLIC — it is printed in the repo README.
# Strangers verifying a glyph never have keys/ace-lattice.pub (the keys/
# directory is never published), so verify falls back to this published
# constant for the signer pin check. The seed is never published, ever.
FLEET_PUBKEY = "d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8"


def pinned_pubkey():
    """Pinned fleet pubkey: local keys/ace-lattice.pub when present,
    otherwise the pubkey published in the README."""
    try:
        return PUBF.read_text().strip()
    except OSError:
        return FLEET_PUBKEY


def read_chunks(data):
    if not data.startswith(SIG8):
        raise ValueError("not a PNG")
    pos, out = 8, []
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8].decode("latin-1")
        payload = data[pos + 8:pos + 8 + ln]
        out.append((typ, payload, pos, pos + 12 + ln))
        pos += 12 + ln
        if typ == "IEND":
            break
    return out


def text_chunk(keyword, text):
    payload = keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")
    crc = zlib.crc32(b"tEXt" + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + b"tEXt" + payload + struct.pack(">I", crc)


def content_hash(chunks):
    h = hashlib.sha256()
    for typ, payload, _, _ in chunks:
        if typ == "IDAT":
            h.update(payload)
    return h.hexdigest()


def bind(inp, outp, snapshot_id, release_class):
    if not SEED.exists() or not PUBF.exists():
        print("cannot bind: the fleet signing key (keys/ace-lattice.seed) is not "
              "present on this machine. Binding is an operator action; verifying "
              "works anywhere with the published fleet pubkey.")
        sys.exit(1)
    try:
        data = pathlib.Path(inp).read_bytes()
    except OSError:
        print(f"cannot bind: no readable file at {inp}")
        sys.exit(1)
    chunks = read_chunks(data)
    for typ, payload, _, _ in chunks:
        if typ == "tEXt" and payload.startswith(b"asinmcp:binding\x00"):
            print("REFUSED: already bound — a re-bind is a SPLIT event; issue a new version instead")
            sys.exit(1)
    binding = {
        "scheme": "asinmcp-pngbind/1",
        "artifact": pathlib.Path(inp).name,
        "snapshot_id": snapshot_id,
        "release_class": release_class,
        "content_sha256": content_hash(chunks),
        "origin_file_sha256": hashlib.sha256(data).hexdigest(),
        "pubkey": PUBF.read_text().strip(),
        "bound_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    raw = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
    sig = ed25519.sign(SEED.read_text().strip(), raw)
    iend_start = next(s for t, _, s, _ in chunks if t == "IEND")
    out = data[:iend_start] + text_chunk("asinmcp:binding", raw.decode()) \
        + text_chunk("asinmcp:binding.sig", sig) + data[iend_start:]
    pathlib.Path(outp).write_bytes(out)
    print(f"bound {outp}: content {binding['content_sha256'][:16]}… snapshot {snapshot_id} class {release_class}")


def verify(path):
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError:
        print(f"cannot verify: no readable file at {path}")
        sys.exit(1)
    try:
        chunks = read_chunks(data)
    except ValueError:
        print(f"cannot verify: {path} is not a PNG file")
        sys.exit(1)
    texts = {}
    for typ, payload, _, _ in chunks:
        if typ == "tEXt" and b"\x00" in payload:
            k, v = payload.split(b"\x00", 1)
            texts[k.decode("latin-1")] = v
    raw = texts.get("asinmcp:binding")
    sig = texts.get("asinmcp:binding.sig")
    if raw is None or sig is None:
        print("binding FAIL · no asinmcp:binding chunks present")
        sys.exit(1)
    binding = json.loads(raw.decode("latin-1"))
    pinned = pinned_pubkey()
    ok_pin = binding.get("pubkey") == pinned
    ok_content = content_hash(chunks) == binding.get("content_sha256")
    ok_sig = ed25519.verify(binding["pubkey"], raw, sig.decode("latin-1"))
    print(f"content {'OK' if ok_content else 'FAIL'} · signature {'OK' if ok_sig else 'FAIL'} · "
          f"signer {'OK (pinned fleet key)' if ok_pin else 'FAIL (not the pinned fleet key)'} · "
          f"snapshot {binding.get('snapshot_id')} · class {binding.get('release_class')}")
    sys.exit(0 if (ok_pin and ok_content and ok_sig) else 1)


if __name__ == "__main__":
    if sys.argv[1] == "bind":
        bind(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif sys.argv[1] == "verify":
        verify(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)
