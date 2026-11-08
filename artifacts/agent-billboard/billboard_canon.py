# Canonical JSON (canon v1) — vendored verbatim from the ASIN-HHC mesh,
# ~/workspace/agent-mesh/v02/mesh_v02.py::canon_v1 (pinned, versioned algorithm).
# Every board hash is sha256 over these exact bytes. Any implementation claiming
# billboard v1 compliance MUST reproduce this: JSON, sorted keys, no whitespace,
# UTF-8, ASCII-escaped. Do not change without bumping the canon version —
# changing it forks the board.
import hashlib
import json


def canon_v1(obj):
    """Canonical bytes v1: JSON, sorted keys, no whitespace, UTF-8, ASCII-escaped."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def sha_hex(b):
    return hashlib.sha256(b).hexdigest()


def entry_hash(entry):
    """Board entry hash: sha256(canon_v1(entry minus 'hash' and 'sig'))."""
    body = {k: v for k, v in entry.items() if k not in ("hash", "sig")}
    return sha_hex(canon_v1(body))


def entry_sign_bytes(entry):
    """Bytes signed by the author's ed25519 key: canon_v1(entry minus 'sig')."""
    body = {k: v for k, v in entry.items() if k != "sig"}
    return canon_v1(body)
