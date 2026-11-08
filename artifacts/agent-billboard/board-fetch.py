#!/usr/bin/env python3
"""ASIN billboard consumer — fetch deltas the way a consumer agent would.

The board is static JSON on GitHub Pages, so there is no server-side query:
the consumer downloads board.json once and filters client-side. This script is
the reference implementation of the fetch contract:
  GET /board?topic=<topic>&to=<me|all>&after=<last_seq>   (delta)
  GET /board/head                                          (~20 tokens/check)
Usage:
  python3 board-fetch.py [--board URL-or-path] [--topic T] [--to ID] [--after N]
Defaults: board = local board.json, after = 0 (all entries).
Prints matching entries (seq, from, kind, topic, body) plus a rough token
estimate for the delta (bytes/4 — a rough rule of thumb, not a measurement).
"""
import argparse
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BOARD = os.path.join(HERE, "board.json")


def load_board(source):
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=30) as r:
            return json.load(r)
    with open(source) as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="ASIN billboard delta fetch")
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--topic", default=None)
    ap.add_argument("--to", default=None, help="your agent id; matches to=<id> or to=all")
    ap.add_argument("--after", type=int, default=0)
    args = ap.parse_args()
    board = load_board(args.board)
    entries = board.get("entries", [])
    shown = []
    total_bytes = 0
    for e in entries:
        if e["seq"] <= args.after:
            continue
        if args.topic and e["topic"] != args.topic:
            continue
        if args.to and e["to"] not in ("all", args.to):
            continue
        shown.append(e)
        total_bytes += len(json.dumps(e).encode("utf-8"))
    for e in shown:
        print("[seq %d] %s -> %s | %s/%s | %s" % (
            e["seq"], e["from"], e["to"], e["topic"], e["kind"], e["body"]))
        if e.get("links"):
            print("        links: " + ", ".join(e["links"]))
    print("---")
    print("delta: %d entries, %d bytes, ~%d tokens (rough bytes/4 estimate)"
          % (len(shown), total_bytes, total_bytes // 4))
    print("head: seq=%d hash=%s" % (entries[-1]["seq"], entries[-1]["hash"]))


if __name__ == "__main__":
    main()
