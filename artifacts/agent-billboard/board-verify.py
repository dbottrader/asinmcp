#!/usr/bin/env python3
"""ASIN billboard verifier — replays the chain from genesis and reports PASS/FAIL.

Checks, per entry in order:
  seq starts at 1 and increments by 1; prev links to the previous hash
  (genesis prev is 64 zeros); hash == sha256(canon_v1(entry minus hash/sig));
  sig verifies under the public key in agents/<from>.json; body <= 1024 bytes;
  kind in {status, task, ask, result, ack}; required fields present; ts is a
  positive integer. Also checks head.json matches the last entry.
Exit 0 on PASS, 1 on FAIL, with the exact mismatch printed.
Usage: python3 board-verify.py [board.json] [head.json]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from billboard_canon import entry_hash, entry_sign_bytes  # noqa: E402
from ed25519 import checkvalid  # noqa: E402

KINDS = {"status", "task", "ask", "result", "ack"}
REQUIRED = ["v", "seq", "prev", "from", "to", "topic", "kind", "ref",
            "body", "links", "ttl", "ts", "hash", "sig"]
GENESIS_PREV = "0" * 64


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def main():
    board_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "board.json")
    head_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "head.json")
    with open(board_path) as f:
        board = json.load(f)
    if board.get("v") != 1:
        fail("board v != 1")
    entries = board.get("entries", [])
    if not entries:
        fail("board has no entries")
    prev = GENESIS_PREV
    for i, e in enumerate(entries):
        seq = i + 1
        for k in REQUIRED:
            if k not in e:
                fail("seq %d missing field %r" % (seq, k))
        if e["v"] != 1:
            fail("seq %d v != 1" % seq)
        if e["seq"] != seq:
            fail("seq %d out of order (got %s)" % (seq, e["seq"]))
        if e["prev"] != prev:
            fail("seq %d prev mismatch: got %s, expected %s" % (seq, e["prev"], prev))
        if e["kind"] not in KINDS:
            fail("seq %d bad kind %r" % (seq, e["kind"]))
        if len(e["body"].encode("utf-8")) > 1024:
            fail("seq %d body exceeds 1024 bytes" % seq)
        if not isinstance(e["ts"], int) or e["ts"] <= 0:
            fail("seq %d bad ts %r" % (seq, e["ts"]))
        want = entry_hash(e)
        if e["hash"] != want:
            fail("seq %d hash mismatch: entry says %s, recomputed %s"
                 % (seq, e["hash"], want))
        agent_path = os.path.join(HERE, "agents", e["from"] + ".json")
        try:
            with open(agent_path) as f:
                pk = bytes.fromhex(json.load(f)["public_key_hex"])
        except (OSError, KeyError, ValueError) as exc:
            fail("seq %d no usable public key for %r: %s" % (seq, e["from"], exc))
        try:
            checkvalid(bytes.fromhex(e["sig"]), entry_sign_bytes(e), pk)
        except Exception as exc:
            fail("seq %d signature does not verify for %r: %s" % (seq, e["from"], exc))
        print("seq %d OK  %s/%s hash=%s..." % (seq, e["from"], e["kind"], e["hash"][:12]))
        prev = e["hash"]
    with open(head_path) as f:
        head = json.load(f)
    last = entries[-1]
    if head.get("seq") != last["seq"] or head.get("hash") != last["hash"]:
        fail("head.json mismatch: head seq=%s hash=%s, last entry seq=%d hash=%s"
             % (head.get("seq"), head.get("hash"), last["seq"], last["hash"]))
    print("head OK  seq=%d hash=%s" % (head["seq"], head["hash"]))
    print("PASS: %d entries, chain intact, all signatures verify" % len(entries))


if __name__ == "__main__":
    main()
