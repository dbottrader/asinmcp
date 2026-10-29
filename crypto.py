#!/usr/bin/env python3
"""Fleet crypto core v1 (CP-0021) — Ed25519 signing for ASNB snapshots & checkpoints.
Reuses the kit's audited-style pure-python ed25519 (~/workspace/asinmolt-node/ed25519.py).
Seed lives ONLY in asinmcp/keys/ (dir 0700, file 0600). Public key is publishable.
Usage: python3 crypto.py genkey | sign <file> | verify <file>
"""
import sys, os, json, hashlib, pathlib, datetime
sys.path.insert(0, str(pathlib.Path.home() / "workspace/asinmolt-node"))
import ed25519

BASE = pathlib.Path(__file__).parent
KEYS = BASE / "keys"
SEED = KEYS / "ace-lattice.seed"
PUBF = KEYS / "ace-lattice.pub"

def genkey():
    KEYS.mkdir(exist_ok=True); os.chmod(KEYS, 0o700)
    if SEED.exists():
        print("key already exists:", PUBF.read_text().strip()); return
    seed_hex, pub_hex = ed25519.generate_keypair()
    SEED.write_text(seed_hex); os.chmod(SEED, 0o600)
    PUBF.write_text(pub_hex)
    print("pubkey:", pub_hex)

def sign(path):
    data = pathlib.Path(path).read_bytes()
    sig = ed25519.sign(SEED.read_text().strip(), data)
    out = {"artifact": pathlib.Path(path).name, "sha256": hashlib.sha256(data).hexdigest(),
           "pubkey": PUBF.read_text().strip(), "signature": sig,
           "signed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    pathlib.Path(str(path) + ".sig.json").write_text(json.dumps(out, indent=1))
    print(f"signed {out['artifact']} sha256 {out['sha256'][:16]}… sig {sig[:16]}…")

def verify(path):
    meta = json.loads(pathlib.Path(str(path) + ".sig.json").read_text())
    data = pathlib.Path(path).read_bytes()
    # CP-0019 trust-anchor pin: the signer must be THE fleet pubkey, not
    # merely whoever signed the accompanying .sig.json (audit 2026-10-29).
    if PUBF.exists():
        pinned = PUBF.read_text().strip()
        if meta.get("pubkey") != pinned:
            print(f"pubkey FAIL · signer {str(meta.get('pubkey'))[:16]}… != pinned fleet key {pinned[:16]}…")
            sys.exit(1)
    ok_hash = hashlib.sha256(data).hexdigest() == meta["sha256"]
    ok_sig = ed25519.verify(meta["pubkey"], data, meta["signature"])
    print(f"hash {'OK' if ok_hash else 'FAIL'} · signature {'OK' if ok_sig else 'FAIL'} · signer {meta['pubkey'][:16]}…")
    sys.exit(0 if (ok_hash and ok_sig) else 1)

if __name__ == "__main__":
    {"genkey": lambda: genkey(), "sign": lambda: sign(sys.argv[2]), "verify": lambda: verify(sys.argv[2])}[sys.argv[1]]()
