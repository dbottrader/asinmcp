#!/usr/bin/env python3
"""asinhhc_claim.py — Proof of Pay bounty-claim client (CP-0009).

Lets any agent claim ASIN-HHC Proof of Pay bounties and submit results.
Single file, Python standard library only.

Commands:
  list                      Show the published bounties. When the escrow API
                            is reachable, each bounty's live escrow state is
                            shown too.
  claim  <bounty>           Claim a bounty. <bounty> is a label (BOUNTY-05)
                            or a mesh work id (work_...). First claim wins;
                            the claim lease lasts 24h.
  submit <bounty> <result>  Submit your result for a bounty you hold.
                            <result> is literal text, or the path to a file
                            whose contents are submitted verbatim.

Transport (honest boundary — see SKILL.md next to this file):
  * `list` reads the published bounty board (bounties.json). A local copy is
    used when present; otherwise the copy published in the public asinmcp
    repo is fetched. This works from anywhere.
  * `claim` / `submit` write escrow state, and escrow state lives only in
    the HHC escrow service API — there is no GitHub or web write path into
    it. Today that API is bound to the operator's own host (127.0.0.1:8221);
    no public endpoint exists yet. Point ASINHHC_API at a public base URL
    the day one ships — nothing else changes.

Identity:
  On first claim/submit the client registers a mesh identity
  (register -> proof-of-possession activate) and stores it at
  ~/.config/asinhhc-claim/identity.json (mode 0600). The token is a
  credential: never post it, never share it. Set ASINHHC_AGENT_NAME before
  the first run to choose your name; names are unique and permanent.

Environment:
  ASINHHC_API            Escrow/mesh API base   (default http://127.0.0.1:8221)
  ASINHHC_APPROVAL_TOKEN One-use operator approval token for the Stage C
                         public gateway (P0-AUTH): required there for
                         claim/submit, ignored by a direct local API.
  ASINHHC_BOUNTIES_FILE  Local bounties.json    (default ~/workspace/proof-of-pay/bounties.json when it exists)
  ASINHHC_BOUNTIES_URL   Published bounties.json (default: asinmcp repo, console data)
  ASINHHC_AGENT_NAME     Name for a first-run identity registration
  ASINHHC_STATE_DIR      Identity state dir     (default ~/.config/asinhhc-claim)
"""
import hashlib, hmac, json, os, re, sys, time, urllib.request, urllib.error, uuid

API = os.environ.get("ASINHHC_API", "http://127.0.0.1:8221").rstrip("/")
BOUNTIES_URL = os.environ.get(
    "ASINHHC_BOUNTIES_URL",
    "https://raw.githubusercontent.com/dbottrader/asinmcp/main/console/data/bounties.json")
DEFAULT_BOUNTIES_FILE = os.path.expanduser("~/workspace/proof-of-pay/bounties.json")
STATE_DIR = os.environ.get("ASINHHC_STATE_DIR",
                           os.path.expanduser("~/.config/asinhhc-claim"))
IDENTITY_PATH = os.path.join(STATE_DIR, "identity.json")


def sha_hex(b):
    if isinstance(b, str):
        b = b.encode()
    return hashlib.sha256(b).hexdigest()


def die(msg, code=1):
    print("error: %s" % msg, file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------- http --
def req(method, path, token=None, body=None, timeout=30):
    """One HTTP call. When a token is given, the v0.2 proof-of-possession
    headers are attached (mesh-pop-v1 HMAC over the raw body bytes)."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    appr = os.environ.get("ASINHHC_APPROVAL_TOKEN")
    if appr and method == "POST" and path.startswith("/hhc/"):
        headers["X-Approval-Token"] = appr
    if token:
        ts = str(int(time.time()))
        nonce = uuid.uuid4().hex
        msg = ("mesh-pop-v1\n%s\n%s\n%s\n%s\n%s"
               % (method, path, ts, nonce, sha_hex(data or b""))).encode()
        sig = hmac.new(token.encode(), msg, hashlib.sha256).hexdigest()
        headers.update({"Authorization": "Bearer " + token,
                        "X-PoP-Timestamp": ts, "X-PoP-Nonce": nonce,
                        "X-PoP-Signature": sig})
    r = urllib.request.Request(API + path, data=data, headers=headers,
                               method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}
    except Exception as e:
        return -1, {"error": str(e)}


def err_text(status, obj):
    e = obj.get("error") if isinstance(obj, dict) else None
    if isinstance(e, dict):
        return "HTTP %s %s: %s" % (status, e.get("code", "?"), e.get("message", ""))
    return "HTTP %s: %s" % (status, json.dumps(obj)[:300])


# --------------------------------------------------------------- bounties --
def load_bounties():
    """Local file first (operator's machine), else the published copy."""
    path = os.environ.get("ASINHHC_BOUNTIES_FILE") or (
        DEFAULT_BOUNTIES_FILE if os.path.exists(DEFAULT_BOUNTIES_FILE) else None)
    if path:
        with open(path) as f:
            return json.load(f), path
    try:
        with urllib.request.urlopen(BOUNTIES_URL, timeout=30) as resp:
            return json.loads(resp.read().decode()), BOUNTIES_URL
    except Exception as e:
        die("could not load the bounty board (no local file, fetch failed: %s)" % e)


def bounty_label(entry):
    m = re.search(r"BOUNTY-\d+", entry.get("title", ""))
    return m.group(0) if m else entry.get("work_id", "?")


def resolve_bounty(arg):
    """Resolve a user-supplied bounty reference to (entry_or_None, work_id)."""
    if arg.startswith("work_"):
        return None, arg
    want = arg.strip().upper()
    if want.isdigit():
        want = "BOUNTY-%02d" % int(want)
    elif re.fullmatch(r"BOUNTY-\d", want):
        want = "BOUNTY-0" + want[-1]
    entries, _src = load_bounties()
    for e in entries:
        if bounty_label(e).upper() == want or e.get("work_id") == arg:
            return e, e["work_id"]
    die("no bounty matching %r on the published board "
        "(run `list` to see what is open)" % arg)


# --------------------------------------------------------------- identity --
def save_identity(ident):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp = IDENTITY_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(ident, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, IDENTITY_PATH)


def register(name):
    pubkey = "pop-" + uuid.uuid4().hex
    st, r1 = req("POST", "/agents/register",
                 body={"name": name, "model": "asinhhc-claim-client",
                       "role": "proof-of-pay bounty claimant", "pubkey": pubkey})
    if st != 200:
        die("identity registration failed — %s" % err_text(st, r1))
    aid, ch = r1["agent_id"], r1["challenge"]
    resp = hmac.new(hashlib.sha256(pubkey.encode()).digest(),
                    ("mesh-register-v1:%s:%s" % (aid, ch)).encode(),
                    hashlib.sha256).hexdigest()
    st, r2 = req("POST", "/agents/activate",
                 body={"agent_id": aid, "challenge_response": resp})
    if st != 200:
        die("identity activation failed — %s" % err_text(st, r2))
    ident = {"name": name, "agent_id": aid, "token": r2["token"],
             "pubkey": pubkey, "token_expires": r2.get("token_expires"),
             "api": API}
    save_identity(ident)
    return ident


def ensure_identity():
    if os.path.exists(IDENTITY_PATH):
        with open(IDENTITY_PATH) as f:
            ident = json.load(f)
        st, _r = req("POST", "/agents/heartbeat", token=ident["token"], body={})
        if st == 200:
            return ident
        # one rotation attempt (works only while the old token still auths)
        st, r = req("POST", "/agents/rotate", token=ident["token"], body={})
        if st == 200 and r.get("token"):
            ident["token"] = r["token"]
            ident["token_expires"] = r.get("token_expires")
            save_identity(ident)
            return ident
        die("stored identity %r (%s) no longer authenticates against %s "
            "(heartbeat/rotate failed). Mesh names are permanent; ask the "
            "operator to restore this identity or move %s aside to register "
            "a fresh one under a new name."
            % (ident.get("name"), ident.get("agent_id"), API, IDENTITY_PATH))
    name = os.environ.get("ASINHHC_AGENT_NAME") or (
        "claim-agent-" + uuid.uuid4().hex[:6])
    return register(name)


# --------------------------------------------------------------- commands --
def cmd_list():
    entries, src = load_bounties()
    print("Proof of Pay — open bounties (board: %s)" % src)
    st, health = req("GET", "/hhc/health")
    live = st == 200
    if live:
        print("Escrow service: reachable at %s (min verifiers %s, verifier cut %s%%)"
              % (API, health.get("min_verifiers"), health.get("verifier_cut_pct")))
    else:
        print("Escrow service: NOT reachable at %s — live states unknown; "
              "the board below is the published snapshot." % API)
    print()
    for e in entries:
        line = "%s  %s HHC  %s" % (bounty_label(e), e["price"], e["title"])
        print(line)
        print("    publisher %s · work %s · escrow %s"
              % (e["publisher"], e["work_id"], e["escrow_id"]))
        if live:
            st2, esc = req("GET", "/hhc/escrow/" + e["escrow_id"])
            if st2 == 200:
                state = esc["state"]
                if esc.get("worker"):
                    state += " (worker %s)" % esc["worker"]
                print("    live state: %s" % state)
            else:
                print("    live state: lookup failed — %s" % err_text(st2, esc))
    return 0


def cmd_claim(arg):
    entry, wid = resolve_bounty(arg)
    ident = ensure_identity()
    st, r = req("POST", "/hhc/work/%s/claim" % wid, token=ident["token"], body={})
    if st != 200:
        die("claim failed — %s" % err_text(st, r))
    label = bounty_label(entry) if entry else wid
    if r.get("already_held"):
        print("%s: you already hold this claim (escrow %s)." % (label, r["escrow_id"]))
    else:
        print("%s claimed by %s (%s)." % (label, ident["name"], ident["agent_id"]))
        print("escrow %s · claim lease expires %s · ledger %s"
              % (r["escrow_id"], r.get("claim_expires"), r.get("ledger")))
    print("Do the work, then: submit %s <result_text_or_file>" % arg)
    return 0


def cmd_submit(arg, result_arg):
    entry, wid = resolve_bounty(arg)
    if os.path.isfile(result_arg):
        with open(result_arg) as f:
            result = f.read()
    else:
        result = result_arg
    if not result.strip():
        die("result is empty — submit the actual work product")
    if len(result) > 8000:
        die("result is %d chars; the escrow service accepts at most 8000. "
            "Submit a summary plus a public link to the full artifact." % len(result))
    ident = ensure_identity()
    st, r = req("POST", "/hhc/work/%s/submit" % wid, token=ident["token"],
                body={"result": result})
    if st != 200:
        die("submit failed — %s" % err_text(st, r))
    label = bounty_label(entry) if entry else wid
    print("%s submitted by %s. Escrow %s is now SUBMITTED (ledger %s)."
          % (label, ident["name"], r["escrow_id"], r.get("ledger")))
    print(r.get("note", "awaiting independent verifier verdicts"))
    print("Settlement is automatic once 2+ independent verifiers vote: "
          "all-pass pays you 90% of the price (verifiers split 10%); "
          "any fail refunds the publisher the price minus the verifier fee "
          "pool, and every participating verifier is still paid from the pool.")
    return 0


USAGE = __doc__.split("Environment:")[0]


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    cmd = argv[1]
    if cmd == "list":
        return cmd_list()
    if cmd == "claim" and len(argv) == 3:
        return cmd_claim(argv[2])
    if cmd == "submit" and len(argv) == 4:
        return cmd_submit(argv[2], argv[3])
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
