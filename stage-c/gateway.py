#!/usr/bin/env python3
"""stage_c_gateway.py — ASIN-HHC Stage C public endpoint (v1).

A thin, allowlist-only proxy + read surface in front of the local mesh
(:8220) and HHC escrow service (:8221). The gateway stores NO ledger or
escrow state of its own: every read is fetched live from the local
services, every write is forwarded to them. The local mesh remains the
single source of truth (V03-SPEC C4/C8); this process is transport +
the P0-AUTH approval gate, nothing more.

Public surface:
  READ (no credential):
    GET /v1/health            gateway + upstream health
    GET /v1/bounties          published board merged with LIVE escrow states
    GET /v1/ledger/head       ledger height + head hash (live from the mesh)
    GET /v1/ledger/checkpoint (height, head_hash) signed with the fleet key
    GET /v1/registry          asinmcp CP-registry snapshot info, sig verified
    GET /v1/escrow/<id>       one escrow, live
    GET /hhc/health           passthrough (claim-client `list`)
    GET /hhc/escrow/<id>      passthrough (claim-client `list`)
  IDENTITY (proxied; upstream PoP auth applies; moves no value):
    POST /agents/register  /agents/activate  /agents/heartbeat  /agents/rotate
  ESCROW WRITES (P0-AUTH gate: upstream PoP credential AND a one-use,
  action-scoped, operator-issued approval token in X-Approval-Token):
    POST /hhc/work/publish
    POST /hhc/work/<id>/claim | submit | verdict | cancel
  Everything else: 404. In particular /hhc/mint, /hhc/transfer,
  /hhc/keys/register, /ledger/append and all social/mesh mutations are
  NOT exposed.

Approval tokens live in approvals.json next to this file (SHA-256 hashes
only; minted by approve.py). A token is RESERVED (marked used) atomically
at validation time, under the same lock that validates it — one token can
never pass validation twice, however many requests race (pressure test
F1, fixed 2026-10-29). If the upstream call then returns a definitive
rejection (any 4xx: the action provably did not happen), the reservation
is released so a rejected attempt never burns an approval. On success,
or on an ambiguous upstream outcome (5xx / unreachable), the token stays
consumed — fail-closed.

Rate limiting (pressure test F5, fixed 2026-10-29): per-client token
buckets, reads and writes separately; over-limit gets HTTP 429. Client
identity is the X-Forwarded-For first hop when present (the gateway is
only reachable through the tunnel, which sets it) else the socket peer.
Known limitation: behind a tunnel all traffic arrives via one local
peer, so without a forwarded header the buckets degenerate to global
ones — still a hard cap on amplification, just not per-user fairness.

Bind: 127.0.0.1:8222 by default — public exposure is via the tunnel in
front of it, never a raw public bind. Standard library only.
"""
import hashlib, json, os, re, sys, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
APPROVALS_PATH = os.path.join(HERE, "approvals.json")
BOUNTIES_FILE = os.path.expanduser("~/workspace/proof-of-pay/bounties.json")
ASINMCP = os.path.expanduser("~/workspace/asinmcp")
MESH = os.environ.get("STAGE_C_MESH", "http://127.0.0.1:8220").rstrip("/")
HHC = os.environ.get("STAGE_C_HHC", "http://127.0.0.1:8221").rstrip("/")
PORT = int(os.environ.get("STAGE_C_PORT", "8222"))

sys.path.insert(0, os.path.expanduser("~/workspace/asinmolt-node"))
import ed25519  # noqa: E402  (the fleet's audited pure-python module)

_lock = threading.Lock()

# ---------------------------------------------------------------- helpers --

def sha_hex(b):
    if isinstance(b, str):
        b = b.encode()
    return hashlib.sha256(b).hexdigest()


def up(base, method, path, body=None, headers=None, timeout=20):
    """One call to a local upstream service. Returns (status, parsed|raw)."""
    data = body
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    r = urllib.request.Request(base + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode())
            except Exception:
                return resp.status, {"raw": raw.decode(errors="replace")}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode())
        except Exception:
            return e.code, {"raw": raw.decode(errors="replace")}
    except Exception as e:
        return -1, {"error": {"code": "UPSTREAM_UNREACHABLE", "message": str(e)}}


def load_approvals():
    try:
        with open(APPROVALS_PATH) as f:
            return json.load(f)
    except Exception:
        return {"tokens": {}}


def save_approvals(store):
    tmp = APPROVALS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, APPROVALS_PATH)


def reserve_approval(token, scope, work_id):
    """Validate AND consume an approval token atomically (FIX A / F1).

    Validation and the used-mark happen inside ONE lock acquisition, so
    under any concurrency exactly one request can reserve a given token;
    every other racer sees used_at already set and gets already_used.
    Returns (ok, reason_or_hash). On success the token is consumed unless
    the caller later calls release_approval() after a definitive upstream
    rejection (see do_POST). Sequential error taxonomy is unchanged:
    missing / unknown / already_used / revoked / expired /
    scope_mismatch / work_mismatch."""
    if not token:
        return False, "missing"
    h = sha_hex(token)
    with _lock:
        store = load_approvals()
        rec = store["tokens"].get(h)
        if not rec:
            return False, "unknown"
        if rec.get("used_at"):
            return False, "already_used"
        if rec.get("revoked"):
            return False, "revoked"
        if time.time() > rec.get("expires_at", 0):
            return False, "expired"
        if rec.get("scope") != scope:
            return False, "scope_mismatch"
        if rec.get("work_id") and work_id and rec["work_id"] != work_id:
            return False, "work_mismatch"
        rec["used_at"] = time.time()
        rec["used_note"] = "reserved: %s %s" % (scope, work_id or "")
        save_approvals(store)
    return True, h


def finalize_approval(h, note):
    """Stamp the reservation with the completed action (success path)."""
    with _lock:
        store = load_approvals()
        rec = store["tokens"].get(h)
        if rec:
            rec["used_note"] = note
            save_approvals(store)


def release_approval(h):
    """Undo a reservation after a DEFINITIVE upstream rejection (any 4xx:
    the action provably created nothing). Never called on success or on
    ambiguous outcomes (5xx/unreachable) — those stay consumed."""
    with _lock:
        store = load_approvals()
        rec = store["tokens"].get(h)
        if rec and rec.get("used_at"):
            rec["used_at"] = None
            rec["used_note"] = "released after definitive upstream rejection"
            save_approvals(store)


# --------------------------------------------------------- rate limiting --

class _Bucket:
    """Token bucket: `cap` burst, refills at `rate` tokens/second."""
    __slots__ = ("cap", "rate", "tokens", "ts")

    def __init__(self, cap, rate):
        self.cap, self.rate = float(cap), float(rate)
        self.tokens, self.ts = float(cap), time.monotonic()

    def take(self):
        now = time.monotonic()
        self.tokens = min(self.cap, self.tokens + (now - self.ts) * self.rate)
        self.ts = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


# Sane public limits: a human/agent browsing the read surface will never
# notice these; a flood trips them in the first second.
_buckets = {}
_buckets_lock = threading.Lock()
READ_CAP, READ_RATE = 40, 1.0      # burst 40 reads, then 60/min sustained
WRITE_CAP, WRITE_RATE = 20, 0.2    # burst 20 writes, then 12/min sustained


def rate_ok(client, write):
    key = (client, "w" if write else "r")
    with _buckets_lock:
        b = _buckets.get(key)
        if b is None:
            b = _Bucket(WRITE_CAP, WRITE_RATE) if write else _Bucket(READ_CAP, READ_RATE)
            _buckets[key] = b
        return b.take()


# ------------------------------------------------------------ read views --

def view_health():
    st_h, hhc = up(HHC, "GET", "/hhc/health")
    st_m, mesh = up(MESH, "GET", "/health")
    return 200, {"ok": st_h == 200 and st_m == 200, "gateway": "stage-c/1",
                 "ts": time.time(), "hhc": hhc if st_h == 200 else {"unreachable": True},
                 "mesh": mesh if st_m == 200 else {"unreachable": True},
                 "trust_note": "reads are live from the local mesh; the mesh "
                               "ledger is the only source of truth"}


_bounties_cache = {"ts": 0.0, "val": None}
BOUNTIES_TTL = 5.0  # seconds; escrow states move on human timescales


def view_bounties():
    """Board + live escrow states, cached & coalesced (FIX B / F5).

    The refresh runs while holding _lock, so a burst of concurrent
    requests shares ONE upstream fan-out instead of each doing its own:
    30 rapid calls now cost ~5 upstream GETs (one per board row), not 150.
    Staleness is bounded by BOUNTIES_TTL and disclosed in the payload."""
    with _lock:
        if _bounties_cache["val"] is not None and \
                time.time() - _bounties_cache["ts"] < BOUNTIES_TTL:
            return _bounties_cache["val"]
        try:
            with open(BOUNTIES_FILE) as f:
                board = json.load(f)
        except Exception as e:
            return 500, {"error": {"code": "BOARD_UNREADABLE", "message": str(e)}}
        out = []
        for e in board:
            row = dict(e)
            st, esc = up(HHC, "GET", "/hhc/escrow/" + e["escrow_id"])
            if st == 200:
                row["live_state"] = esc["state"]
                row["live_worker"] = esc.get("worker")
            else:
                row["live_state"] = "UNKNOWN (escrow service unreachable)"
                row["live_worker"] = None
            out.append(row)
        val = (200, {"bounties": out,
                     "source": "published board + live escrow states "
                               "(gateway cache, max %ds old)" % BOUNTIES_TTL})
        _bounties_cache["ts"] = time.time()
        _bounties_cache["val"] = val
        return val


_head_cache = {"ts": 0.0, "val": None}
HEAD_TTL = 2.0


def ledger_head():
    with _lock:
        if _head_cache["val"] is not None and \
                time.time() - _head_cache["ts"] < HEAD_TTL:
            return _head_cache["val"]
    st, h = up(MESH, "GET", "/health")
    if st != 200:
        return None
    height = h["ledger_height"]
    st2, led = up(MESH, "GET", "/ledger?since=%d" % (height - 1))
    head_hash, head_kind, head_ts = None, None, None
    if st2 == 200 and led.get("entries"):
        e = led["entries"][-1]
        head_hash, head_kind, head_ts = e["hash"], e["kind"], e["ts"]
    val = {"height": height, "head_hash": head_hash,
           "head_kind": head_kind, "head_ts": head_ts}
    with _lock:
        _head_cache["ts"] = time.time()
        _head_cache["val"] = val
    return val


def view_ledger_head():
    head = ledger_head()
    if head is None:
        return 502, {"error": {"code": "UPSTREAM_UNREACHABLE",
                               "message": "mesh service unreachable"}}
    return 200, head


_checkpoint_cache = {"key": None, "val": None}
_fleet_keypair = {}


def _fleet_keys():
    if "seed" not in _fleet_keypair:
        _fleet_keypair["seed"] = open(
            os.path.join(ASINMCP, "keys", "ace-lattice.seed")).read().strip()
        _fleet_keypair["pub"] = open(
            os.path.join(ASINMCP, "keys", "ace-lattice.pub")).read().strip()
    return _fleet_keypair["seed"], _fleet_keypair["pub"]


def view_checkpoint():
    """Signed checkpoint, signed ONCE per ledger head (FIX B / F5).

    The Ed25519 sign is pure-Python and slow; previously it ran on every
    request. A checkpoint is a statement about (height, head_hash), so the
    signed response is cached keyed by exactly that pair and re-signed
    only when the head actually moves."""
    head = ledger_head()
    if head is None or not head["head_hash"]:
        return 502, {"error": {"code": "UPSTREAM_UNREACHABLE",
                               "message": "mesh service unreachable"}}
    key = (head["height"], head["head_hash"])
    with _lock:
        if _checkpoint_cache["key"] == key:
            return _checkpoint_cache["val"]
    seed, pub = _fleet_keys()
    cp = {"height": head["height"], "head_hash": head["head_hash"],
          "issued_at": time.time(), "issuer": "asinmcp stage-c gateway",
          "note": "gateway-issued signed checkpoint over the live mesh head; "
                  "the mesh-native checkpoints table is currently empty"}
    canon = json.dumps(cp, sort_keys=True, separators=(",", ":")).encode()
    sig = ed25519.sign(seed, canon)
    val = (200, {"checkpoint": cp, "signature": sig, "pubkey": pub,
                 "canonicalization": "json sort_keys, separators (',',':'), utf-8"})
    with _lock:
        _checkpoint_cache["key"] = key
        _checkpoint_cache["val"] = val
    return val


# The fleet signing pubkey, PINNED. Registry snapshot verification must
# use this constant — never the pubkey that ships inside the sig file
# itself (pressure test F8): a swapped (snapshot, sig, pubkey) triple
# would otherwise verify against its own key and report valid.
PINNED_FLEET_PUBKEY = "d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8"


def view_registry():
    reg = os.path.join(ASINMCP, "registry.jsonl")
    cpbin = os.path.join(ASINMCP, "registry.cpbin")
    sigf = cpbin + ".sig.json"
    with open(reg) as f:
        records = sum(1 for ln in f if ln.strip())
    raw = open(cpbin, "rb").read()
    meta = json.load(open(sigf))
    sig_ok = False
    try:
        sig_ok = bool(ed25519.verify(PINNED_FLEET_PUBKEY, raw, meta["signature"]))
    except Exception:
        sig_ok = False
    return 200, {"records": records, "snapshot": {
        "artifact": meta.get("artifact"), "sha256": sha_hex(raw),
        "sha256_matches_sigfile": sha_hex(raw) == meta.get("sha256"),
        "pubkey": meta.get("pubkey"),
        "pubkey_matches_pin": meta.get("pubkey") == PINNED_FLEET_PUBKEY,
        "signed_at": meta.get("signed_at"),
        "signature_valid": sig_ok,
        "verified_against": "pinned fleet pubkey (not the sig file's own)"}}


# --------------------------------------------------------------- handler --

GATED = [
    (re.compile(r"^/hhc/work/publish$"), "publish", None),
    (re.compile(r"^/hhc/work/(work_[0-9a-f]+)/claim$"), "claim", 1),
    (re.compile(r"^/hhc/work/(work_[0-9a-f]+)/submit$"), "submit", 1),
    (re.compile(r"^/hhc/work/(work_[0-9a-f]+)/verdict$"), "verdict", 1),
    (re.compile(r"^/hhc/work/(work_[0-9a-f]+)/cancel$"), "cancel", 1),
]
IDENTITY_POSTS = {"/agents/register", "/agents/activate",
                  "/agents/heartbeat", "/agents/rotate"}
FORWARD_HEADERS = ("Authorization", "X-PoP-Timestamp", "X-PoP-Nonce",
                   "X-PoP-Signature", "Content-Type")


class GW(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quiet; never log headers/credentials
        sys.stderr.write("stage-c %s %s\n" % (self.command, self.path))

    def _send(self, status, obj):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _err(self, status, code, message):
        self._send(status, {"error": {"code": code, "message": message,
                                      "errors_version": "stage-c-1"}})

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _client(self):
        fwd = self.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
        return self.client_address[0]

    def _rate_gate(self, write):
        if rate_ok(self._client(), write):
            return True
        self._err(429, "RATE_LIMITED",
                  "too many requests from this client; slow down "
                  "(reads and writes are limited separately)")
        return False

    def _forward(self, base, method, path, raw):
        hdrs = {h: self.headers[h] for h in FORWARD_HEADERS if h in self.headers}
        return up(base, method, path, body=raw or None, headers=hdrs)

    # -- GET --
    def do_GET(self):
        if not self._rate_gate(write=False):
            return
        p = self.path.split("?")[0]
        if p == "/v1/health":
            return self._send(*view_health())
        if p == "/v1/bounties":
            return self._send(*view_bounties())
        if p == "/v1/ledger/head":
            return self._send(*view_ledger_head())
        if p == "/v1/ledger/checkpoint":
            return self._send(*view_checkpoint())
        if p == "/v1/registry":
            return self._send(*view_registry())
        m = re.match(r"^/v1/escrow/(esc_[0-9a-f]+)$", p)
        if m:
            st, obj = up(HHC, "GET", "/hhc/escrow/" + m.group(1))
            return self._send(st if st > 0 else 502, obj)
        if p == "/hhc/health":
            st, obj = up(HHC, "GET", "/hhc/health")
            return self._send(st if st > 0 else 502, obj)
        m = re.match(r"^/hhc/escrow/(esc_[0-9a-f]+)$", p)
        if m:
            st, obj = up(HHC, "GET", "/hhc/escrow/" + m.group(1))
            return self._send(st if st > 0 else 502, obj)
        return self._err(404, "NOT_EXPOSED",
                         "Stage C exposes a fixed allowlist; %s is not on it" % p)

    # -- POST --
    def do_POST(self):
        if not self._rate_gate(write=True):
            return
        p = self.path.split("?")[0]
        raw = self._read_body()
        if p in IDENTITY_POSTS:
            st, obj = self._forward(HHC, "POST", p, raw)
            return self._send(st if st > 0 else 502, obj)
        for rx, scope, grp in GATED:
            m = rx.match(p)
            if m:
                work_id = m.group(grp) if grp else None
                token = self.headers.get("X-Approval-Token")
                ok, why = reserve_approval(token, scope, work_id)
                if not ok:
                    return self._err(
                        403, "APPROVAL_" + why.upper(),
                        "escrow mutations require a one-use, operator-issued "
                        "approval token (P0-AUTH): scope=%s%s. Reading is "
                        "open; acting needs the operator's go for this exact "
                        "action. Request one via the bounty board post."
                        % (scope, (" work=" + work_id) if work_id else ""))
                st, obj = self._forward(HHC, "POST", p, raw)
                if st == 200:
                    finalize_approval(why, "%s %s" % (scope, work_id or ""))
                elif 400 <= st < 500:
                    # Definitive rejection: upstream created nothing, so
                    # the approval was not spent. 5xx/unreachable stay
                    # consumed (fail-closed: the outcome is unknowable).
                    release_approval(why)
                return self._send(st if st > 0 else 502, obj)
        return self._err(404, "NOT_EXPOSED",
                         "Stage C exposes a fixed allowlist; %s is not on it" % p)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), GW)
    print("stage-c gateway on 127.0.0.1:%d (mesh %s, hhc %s)" % (PORT, MESH, HHC),
          flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
