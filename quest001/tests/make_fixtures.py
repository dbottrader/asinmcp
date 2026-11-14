#!/usr/bin/env python3
"""Regenerate tests/fixtures/*. Deterministic. Pins expected digests,
including the wrong `jq -r` (trailing LF) variants, in expected.json."""
import hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.dirname(HERE))
import verify_quest001 as v  # noqa: E402

TIP = hashlib.sha256(b"fixture-ledger-tip").hexdigest()


def chain(entries, tip=TIP):
    prev = tip
    out = []
    for i, e in enumerate(entries):
        e = dict(e, index=i, prev_index_hash=prev)
        e["index_hash"] = v.index_entry_hash(e)
        prev = e["index_hash"]
        out.append(e)
    return out, prev


def doc(entries, head, count=None):
    return {"index": "fixture", "ledger_anchor": {"tip_hash": TIP},
            "entry_count": len(entries) if count is None else count,
            "head_hash": head, "entries": entries}


def write(name, obj, raw=None):
    b = raw if raw is not None else json.dumps(obj, indent=1, ensure_ascii=False).encode()
    open(os.path.join(FX, name), "wb").write(b)
    return b


def main():
    os.makedirs(FX, exist_ok=True)
    exp = {}
    ents, head = chain([{"name": "alpha", "kind": "doc", "n": 1, "tags": ["x", "y"], "url": None},
                        {"name": "beta", "kind": "doc", "n": 2, "ok": True}])
    b = write("mini-index.json", doc(ents, head))
    # Unicode: ensure_ascii=False matters (é, —, emoji, CJK) plus slash/quote escapes.
    uents, uhead = chain([{"name": "café — “quoted” \"x\" a/b ✓ 漢字 😀", "kind": "doc"},
                          {"name": "line\nbreak\ttab", "kind": "doc"}])
    ub = write("unicode-index.json", doc(uents, uhead))
    # Tampered: entry 1 content edited after hashing; declared head kept.
    tents = [dict(e) for e in ents]
    tents[1]["n"] = 999
    tb = write("tampered-index.json", doc(tents, head))
    write("null-entries.json", None, raw=b'{"ledger_anchor":{"tip_hash":"%s"},"entries":null}' % TIP.encode())
    write("empty-entries.json", None, raw=b'{"ledger_anchor":{"tip_hash":"%s"},"entries":[]}' % TIP.encode())
    for name, raw in (("mini-index.json", b), ("unicode-index.json", ub), ("tampered-index.json", tb)):
        ev = v.compute_evidence(raw)
        first = v.canonical_json(json.loads(raw)["entries"][0])
        exp[name] = {
            "claim_sha256": ev["observed"]["claim_sha256"],
            "output": ev["output"], "sealed_output": ev["sealed_output"],
            "first_entry_seal": ev["observed"]["first_entry_seal"],
            "first_entry_seal_jq_r_WRONG": hashlib.sha256(first + b"\n").hexdigest(),
            "sealed_output_with_trailing_lf_WRONG": hashlib.sha256(v.canonical_json(ev["output"]) + b"\n").hexdigest(),
            "consistent_with_declared": ev["consistent_with_declared"],
        }
    open(os.path.join(FX, "expected.json"), "w").write(json.dumps(exp, indent=2, sort_keys=True) + "\n")
    print(json.dumps(exp, indent=2))


if __name__ == "__main__":
    main()
