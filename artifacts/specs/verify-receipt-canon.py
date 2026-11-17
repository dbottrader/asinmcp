#!/usr/bin/env python3
"""Test vectors for the ASIN-HHC receipt canon (receipt-canon.md).

Recomputes, from public data, the three published facts:
  1. The provenance index head hash under canon-pyjson-v1 (78 entries).
  2. The gate receipt hash 48ac1da5...ea38 from the published receipt object.
  3. The witness seal 69616c86...d00d22 from the sealed output, and that both
     witnesses' sealed_output values match it.

Stdlib only. No network is needed for checks 2 and 3 when run next to the
published JSON files; check 1 fetches the live public index by default.

Usage:
    python3 verify-receipt-canon.py                  # local files + live index
    python3 verify-receipt-canon.py --live           # fetch receipt + seals
                                                     # from dbottrader.github.io
    python3 verify-receipt-canon.py --receipt PATH --seals PATH --index PATH|URL
"""
import argparse
import hashlib
import json
import sys
import urllib.request

INDEX_URL = "https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json"
RECEIPT_URL = "https://dbottrader.github.io/asinmcp/artifacts/specs/gate-receipt-48ac1da5.json"
SEALS_URL = "https://dbottrader.github.io/asinmcp/artifacts/specs/witness-seals-48ac1da5.json"

EXPECTED_HEAD = "fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6"
EXPECTED_RECEIPT_HASH = "48ac1da5e752bbce04d744a45774cbb1e713c8b600d7b588ad7d0eb50ba9ea38"
EXPECTED_SEAL = "69616c863e4c1ad1d6508ac8b0db86435aa37bbc1cf69aeea6ebc46a28d00d22"


def load_json(source):
    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=30) as r:
            return json.load(r)
    with open(source, "r", encoding="utf-8") as f:
        return json.load(f)


def canonical_json(obj) -> bytes:
    """Gate-receipt canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def receipt_hash_of(receipt: dict) -> str:
    body = {k: v for k, v in receipt.items()
            if k not in ("receipt_hash", "signature")}
    return hashlib.sha256(canonical_json(body)).hexdigest()


def check_index(source):
    idx = load_json(source)
    entries = idx["entries"]
    prev = idx["ledger_anchor"]["tip_hash"]
    assert entries[0]["prev_index_hash"] == prev, "entry 0 not on ledger tip"
    for e in entries:
        assert e["prev_index_hash"] == prev, f"linkage break at {e['index']}"
        canon = {k: e[k] for k in sorted(e) if k != "index_hash"}
        recomputed = hashlib.sha256(
            json.dumps(canon, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        assert recomputed == e["index_hash"], f"index_hash mismatch at {e['index']}"
        prev = e["index_hash"]
    assert prev == idx["head_hash"] == EXPECTED_HEAD, "head hash mismatch"
    return len(entries)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", default=INDEX_URL)
    ap.add_argument("--receipt", default="gate-receipt-48ac1da5.json")
    ap.add_argument("--seals", default="witness-seals-48ac1da5.json")
    ap.add_argument("--live", action="store_true",
                    help="fetch receipt + seals from the published URLs")
    args = ap.parse_args()
    receipt_src = RECEIPT_URL if args.live else args.receipt
    seals_src = SEALS_URL if args.live else args.seals

    results = []
    try:
        n = check_index(args.index)
        results.append((f"index head: {n}/{n} entries, head matches", True))
    except Exception as exc:  # noqa: BLE001
        results.append((f"index head: FAIL ({exc})", False))

    try:
        receipt = load_json(receipt_src)
        recomputed = receipt_hash_of(receipt)
        ok = recomputed == receipt["receipt_hash"] == EXPECTED_RECEIPT_HASH
        results.append((f"receipt hash recomputes: {recomputed[:12]}...", ok))
    except Exception as exc:  # noqa: BLE001
        results.append((f"receipt hash: FAIL ({exc})", False))

    try:
        seals = load_json(seals_src)
        sealed = seals["sealed_output"]
        recomputed = hashlib.sha256(canonical_json(sealed)).hexdigest()
        ok = (recomputed == seals["seal"] == EXPECTED_SEAL
              and all(w["sealed_output"] == EXPECTED_SEAL
                      for w in seals["witnesses"]))
        results.append((f"witness seal recomputes: {recomputed[:12]}..., "
                        f"{len(seals['witnesses'])} witnesses agree", ok))
    except Exception as exc:  # noqa: BLE001
        results.append((f"witness seal: FAIL ({exc})", False))

    for label, ok in results:
        print(("PASS: " if ok else "FAIL: ") + label)
    print("ALL PASS" if all(ok for _, ok in results) else "FAILURES PRESENT")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
