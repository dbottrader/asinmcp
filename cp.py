#!/usr/bin/env python3
"""CP — Fleet Checkpoint Registry tool (stdlib only).
Usage:
  python3 cp.py get CP-0101
  python3 cp.py find <text>
  python3 cp.py list [project|bill|checkpoint]
  python3 cp.py add <project|bill|checkpoint> "Name" "anchor"
"""
import json, sys, pathlib, datetime

REG = pathlib.Path(__file__).parent / "registry.jsonl"
BLOCKS = {"project": (1, 99), "bill": (101, 199), "checkpoint": (201, 299)}

def load():
    if not REG.exists():
        return []
    return [json.loads(l) for l in REG.read_text().splitlines() if l.strip()]

def fmt(e):
    return f'{e["id"]}  [{e["type"]}/{e["status"]}]  {e["name"]}  ->  {e["anchor"]}'

def main():
    a = sys.argv[1:]
    rows = load()
    if not a or a[0] == "list":
        sel = [e for e in rows if len(a) < 2 or e["type"] == a[1]]
        print("\n".join(fmt(e) for e in sel) or "no entries")
    elif a[0] == "get" and len(a) == 2:
        hit = [e for e in rows if e["id"].upper() == a[1].upper()]
        print(fmt(hit[0]) if hit else f"{a[1]} not found")
    elif a[0] == "find" and len(a) >= 2:
        q = " ".join(a[1:]).lower()
        hits = [e for e in rows if q in json.dumps(e).lower()]
        print("\n".join(fmt(e) for e in hits) or "no matches")
    elif a[0] == "add" and len(a) >= 4:
        typ, name, anchor = a[1], a[2], a[3]
        lo, hi = BLOCKS[typ]
        used = {int(e["id"].split("-")[1]) for e in rows}
        n = next(n for n in range(lo, hi + 1) if n not in used)
        e = {"id": f"CP-{n:04d}", "type": typ, "name": name, "status": "active",
             "anchor": anchor, "created": datetime.date.today().isoformat()}
        with open(REG, "a") as f:
            f.write(json.dumps(e) + "\n")
        print(fmt(e))
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
