#!/usr/bin/env python3
"""publish_snapshot.py — render the Stage C public READ snapshot.

Pulls the gateway's live views (:8222) and writes static JSON files that
the operator publishes to the asinmcp repo (served by GitHub Pages).
Snapshots are DERIVED VIEWS ONLY (the mesh's own doctrine, /snapshot/
status): the ledger on the operator's mesh is canonical. Every snapshot
carries generated_at + the signed checkpoint, so a reader can detect
staleness (older than snapshot_max_age_s, or height below a checkpoint
they trust) and verify authenticity against the pinned fleet pubkey
d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8.

Usage: python3 publish_snapshot.py <output_dir>
Writes: index.json, bounties.json, ledger-head.json, checkpoint.json,
        registry.json
"""
import json, os, sys, time, urllib.request

GW = os.environ.get("STAGE_C_GW", "http://127.0.0.1:8222").rstrip("/")


def get(path):
    with urllib.request.urlopen(GW + path, timeout=20) as r:
        return json.loads(r.read().decode())


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    files = {
        "bounties.json": get("/v1/bounties"),
        "ledger-head.json": get("/v1/ledger/head"),
        "checkpoint.json": get("/v1/ledger/checkpoint"),
        "registry.json": get("/v1/registry"),
    }
    for name, obj in files.items():
        with open(os.path.join(out, name), "w") as f:
            json.dump(obj, f, indent=1)
    cp = files["checkpoint.json"]["checkpoint"]
    index = {
        "surface": "ASIN-HHC Stage C public read snapshot",
        "generated_at": time.time(),
        "ledger_height": cp["height"],
        "head_hash": cp["head_hash"],
        "snapshot_max_age_s": 3600,
        "staleness_rule": "STALE if generated_at older than snapshot_max_age_s "
                          "or ledger_height below the live height",
        "verify": "checkpoint.json carries an Ed25519 signature by the fleet "
                  "key d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8 "
                  "over the canonical checkpoint JSON",
        "files": sorted(files),
        "note": "derived view; the mesh ledger is the canonical source of truth. "
                "Escrow writes go through the Stage C gateway (P0-AUTH gated) — "
                "see DESIGN.md in asinmcp/stage-c/.",
    }
    with open(os.path.join(out, "index.json"), "w") as f:
        json.dump(index, f, indent=1)
    print("snapshot written to %s (height %s)" % (out, cp["height"]))


if __name__ == "__main__":
    main()
