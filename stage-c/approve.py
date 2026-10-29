#!/usr/bin/env python3
"""approve.py — operator tool for Stage C one-use approval tokens (P0-AUTH).

Minting a token IS the operator's per-action "go": each token authorizes
exactly one escrow mutation (scope + optional work_id) through the Stage C
gateway, expires, and is consumed only on a successful upstream call.

Only the SHA-256 hash of each token is stored (approvals.json, mode 0600);
the plaintext is printed once at mint time and never saved.

Usage:
  python3 approve.py mint --scope claim --work work_abc123 [--ttl 3600] [--note "..."]
  python3 approve.py mint --scope publish [--ttl 3600]
  python3 approve.py list
  python3 approve.py revoke <hash-prefix>
"""
import argparse, hashlib, json, os, secrets, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "approvals.json")
SCOPES = ("publish", "claim", "submit", "verdict", "cancel")


def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except Exception:
        return {"tokens": {}}


def save(store):
    tmp = PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, PATH)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint")
    m.add_argument("--scope", required=True, choices=SCOPES)
    m.add_argument("--work", default=None, help="work_id to bind (claim/submit/verdict/cancel)")
    m.add_argument("--ttl", type=int, default=3600)
    m.add_argument("--note", default="")
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("prefix")
    a = ap.parse_args()

    store = load()
    if a.cmd == "mint":
        token = "appr_" + secrets.token_hex(24)
        h = hashlib.sha256(token.encode()).hexdigest()
        store["tokens"][h] = {"scope": a.scope, "work_id": a.work,
                              "created_at": time.time(),
                              "expires_at": time.time() + a.ttl,
                              "used_at": None, "revoked": False,
                              "note": a.note}
        save(store)
        print(token)
        print("scope=%s work=%s ttl=%ss hash=%s..." % (a.scope, a.work, a.ttl, h[:12]),
              file=sys.stderr)
        return 0
    if a.cmd == "list":
        now = time.time()
        for h, rec in sorted(store["tokens"].items(),
                             key=lambda kv: kv[1]["created_at"]):
            state = ("USED" if rec.get("used_at") else
                     "REVOKED" if rec.get("revoked") else
                     "EXPIRED" if now > rec["expires_at"] else "LIVE")
            print("%s  %-8s work=%-18s %s  %s" % (
                h[:12], rec["scope"], rec.get("work_id") or "-", state,
                rec.get("note", "")))
        return 0
    if a.cmd == "revoke":
        hit = [h for h in store["tokens"] if h.startswith(a.prefix)]
        if len(hit) != 1:
            print("prefix matches %d tokens; be specific" % len(hit), file=sys.stderr)
            return 1
        store["tokens"][hit[0]]["revoked"] = True
        save(store)
        print("revoked", hit[0][:12])
        return 0


if __name__ == "__main__":
    sys.exit(main())
