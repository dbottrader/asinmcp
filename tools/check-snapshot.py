#!/usr/bin/env python3
"""check-snapshot — drift alarm for the signed registry snapshot.

Re-encodes registry.jsonl in memory and compares the result, byte for
byte, against (a) the sha256 attested in registry.cpbin.sig.json and
(b) registry.cpbin on disk when present. If the registry has grown or
changed since the snapshot was signed, this fails LOUDLY (exit 1) —
the failure the 2026-10-29 stranger test hit, where the published
signature attested a 41-record snapshot while registry.jsonl held 42.

Run it after every registry.jsonl change, before every push:

    python3 tools/check-snapshot.py

Exit 0 = snapshot and signature are in sync with registry.jsonl.
Exit 1 = DRIFT: re-encode and re-sign (see README, "Verify in 60 seconds").
"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import asinbin  # noqa: E402


def main():
    jsonl = ROOT / "registry.jsonl"
    sig_path = ROOT / "registry.cpbin.sig.json"
    cpbin_path = ROOT / "registry.cpbin"

    rows = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    blob = asinbin.encode(rows)
    fresh_sha = hashlib.sha256(blob).hexdigest()

    problems = []
    if not sig_path.exists():
        problems.append("registry.cpbin.sig.json is MISSING — the snapshot is unsigned.")
    else:
        attested = json.loads(sig_path.read_text()).get("sha256")
        if attested != fresh_sha:
            problems.append(
                "registry.cpbin.sig.json attests sha256 "
                f"{attested} but registry.jsonl now encodes to {fresh_sha} "
                f"({len(rows)} records). The signed snapshot is STALE."
            )
    if cpbin_path.exists():
        disk_sha = hashlib.sha256(cpbin_path.read_bytes()).hexdigest()
        if disk_sha != fresh_sha:
            problems.append(
                f"registry.cpbin on disk has sha256 {disk_sha}, which does not "
                f"match registry.jsonl ({fresh_sha})."
            )

    if problems:
        print("SNAPSHOT DRIFT DETECTED — do not publish:")
        for p in problems:
            print(f"  FAIL: {p}")
        print("Fix: python3 asinbin.py encode registry.jsonl registry.cpbin "
              "&& python3 crypto.py sign registry.cpbin")
        sys.exit(1)

    print(f"snapshot OK · {len(rows)} records · sha256 {fresh_sha} · "
          "signature record in sync with registry.jsonl")
    sys.exit(0)


if __name__ == "__main__":
    main()
