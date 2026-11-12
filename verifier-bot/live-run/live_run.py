#!/usr/bin/env python3
"""Live verification run — ASIN-HHC verification gate, 2026-11-11.

One real attempt through the gate, signed by the LIVE Agent Vault
(~/workspace/agent-vault/live/, action doc.sign — already in policy),
then the receipt hash is anchored on the local mesh ledger as
ace-vault-live and read back and verified.

Subject (real, measured at run time):
  Claim: the local mesh ledger's stored entry count and tip hash agree
  across two independent retrieval paths (direct DB read vs the mesh
  HTTP API), and the gate's blind re-execution reproduces them.
  Witnesses: BOTH are operated by Ace tonight (different implementations
  and failure modes, same operator) — so witness independence cannot be
  established and the honest outcome is REFUSED. A PASS claimed on
  same-operator witnesses would violate the spec's evidence boundary.
Control (external to the tested population): the batch-001 settlement
  tx on Base Sepolia, read live via public RPC; expected status 0x1,
  block 56211684 (verified repeatedly since 2026-11-08).

No secrets are printed: the mesh token is read from its 0600 file and
used only to build PoP headers.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.expanduser("~/workspace/verifier-bot"))
import gate as G  # noqa: E402

MESH_DB = os.path.expanduser("~/workspace/agent-mesh/mesh.db")
MESH_URL = "http://127.0.0.1:8220"
LIVE_VAULT = os.path.expanduser("~/workspace/agent-vault/live")
TOKEN_FILE = os.path.join(LIVE_VAULT, "mesh-token")
RUN_DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER_PATH = os.path.join(RUN_DIR, "gate-ledger.jsonl")
BATCH001_TX = "0x3195dd5692aa622e62471e0b68667b83d9d029d7f8daa34585e905244810014d"


def db_read():
    c = sqlite3.connect(MESH_DB)
    try:
        n = c.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        tip = c.execute(
            "SELECT hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()[0]
        return n, tip
    finally:
        c.close()


def http_entries(since=0):
    """All ledger entries with seq > since, paginating the API's
    200-entry page cap (attempt 001 measured the cap itself: a single
    GET /ledger serves only the newest page window — its residual of
    345 was a page-size artifact, kept on that receipt as measured)."""
    out = []
    while True:
        with urllib.request.urlopen(
                MESH_URL + "/ledger?since=%d" % since, timeout=15) as r:
            data = json.loads(r.read())
        if isinstance(data, str):
            data = json.loads(data)
        page = data["entries"]
        out.extend(page)
        if len(page) < 200:
            return out
        since = page[-1]["seq"]


def http_read():
    entries = http_entries()
    return len(entries), entries[-1]["hash"]


def control_actual():
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": "eth_getTransactionReceipt",
                       "params": [BATCH001_TX]})
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", "-X", "POST",
         "https://base-sepolia-rpc.publicnode.com",
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, text=True)
    res = json.loads(out.stdout)["result"]
    return {"status": res["status"], "block": int(res["blockNumber"], 16)}


def main():
    now_dt = datetime.now(timezone.utc)
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    expires = (now_dt + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    stored_count, _ = db_read()

    def retrieve_served():
        n, _ = http_read()
        return n

    def solver(params):
        n, tip = db_read()
        return {"count": n, "head_hash": tip}

    w1_out = {"count": db_read()[0], "head_hash": db_read()[1]}
    n2, tip2 = http_read()
    w2_out = {"count": n2, "head_hash": tip2}
    w1 = G.build_witness(
        "w-ace-db", "ace", "python3-sqlite3", "mesh.db direct file read",
        "local-db-read", w1_out, hashlib.sha256(b"live-w1-ace-db").digest())
    w2 = G.build_witness(
        "w-ace-api", "ace", "mesh-http-api", "http://127.0.0.1:8220/ledger",
        "service-api-read", w2_out, hashlib.sha256(b"live-w2-ace-api").digest())

    control = G.Control(
        control_id="base-sepolia-batch001-tx",
        expected={"status": "0x1", "block": 56211684},
        actual=control_actual)

    signer = G.VaultSigner(LIVE_VAULT)
    gate = G.Gate(signer, ledger_path=LEDGER_PATH)
    receipt = gate.attempt(
        test_id="mesh-ledger-count-and-tip",
        test_version="1.0",
        population_id="local-mesh-ledger",
        stored_count=stored_count,
        retrieve_served=retrieve_served,
        preconditions=G.Preconditions(established_at=now, expires_at=expires),
        witnesses=[w1, w2],
        solver=solver,
        job_params={"temperature": 0, "seed": 545,
                    "subject": "local-mesh-ledger"},
        now=now,
        control=control,
        verification_id="live-2026-11-11-mesh-ledger-003")

    print("GATE OUTCOME:", receipt["outcome"], "| reason:", receipt["reason"])
    print("gate receipt_hash:", receipt["receipt_hash"])
    print("vault receipt seq:", receipt["signature"]["vault_receipt_seq"],
          "| vault receipt hash:", receipt["signature"]["vault_receipt_hash"])
    print("residual:", receipt["residual"], "| control:", receipt["control"])
    print("independence:", receipt["instrument_independence"])

    # --- anchor the receipt hash on the mesh ledger -------------------
    with open(TOKEN_FILE, "r", encoding="utf-8") as fh:
        token = json.load(fh)["token"]
    payload = {
        "gate_receipt_hash": receipt["receipt_hash"],
        "verification_id": receipt["verification_id"],
        "schema": receipt["schema"],
        "outcome": receipt["outcome"],
        "reason": receipt["reason"],
        "vault_receipt_seq": receipt["signature"]["vault_receipt_seq"],
        "vault_receipt_hash": receipt["signature"]["vault_receipt_hash"],
    }
    body = json.dumps({"kind": "verification_gate_receipt",
                       "payload": payload}).encode()
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    msg = ("mesh-pop-v1\nPOST\n/ledger/append\n%s\n%s\n%s"
           % (ts, nonce, hashlib.sha256(body).hexdigest())).encode()
    sig = hmac.new(token.encode(), msg, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        MESH_URL + "/ledger/append", data=body, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "X-PoP-Timestamp": ts, "X-PoP-Nonce": nonce,
                 "X-PoP-Signature": sig, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        anchor = json.loads(r.read())
    print("mesh anchor: seq", anchor["seq"], "| receipt", anchor["receipt"])

    # --- read back and verify ------------------------------------------
    page = http_entries(since=anchor["seq"] - 1)
    entry = next(e for e in page if e["seq"] == anchor["seq"])
    ep = entry["payload"]
    if isinstance(ep, str):
        ep = json.loads(ep)
    checks = {
        "entry_hash_matches_anchor_receipt": entry["hash"] == anchor["receipt"],
        "payload_gate_hash_matches": ep.get("gate_receipt_hash")
        == receipt["receipt_hash"],
        "kind": entry.get("kind"),
        "gate_receipt_signature_valid": G.verify_receipt(receipt, signer),
        "gate_ledger_chain_ok": G.chain_verify_file(LEDGER_PATH, signer)[0]
        if isinstance(G.chain_verify_file(LEDGER_PATH, signer), tuple)
        else G.chain_verify_file(LEDGER_PATH, signer),
    }
    print("READ-BACK CHECKS:", json.dumps(checks, indent=1))

    sidecar = {"gate_receipt_hash": receipt["receipt_hash"],
               "verification_id": receipt["verification_id"],
               "outcome": receipt["outcome"], "reason": receipt["reason"],
               "mesh_anchor_seq": anchor["seq"],
               "mesh_anchor_receipt": anchor["receipt"],
               "readback": checks, "anchored_at": now}
    with open(os.path.join(RUN_DIR, "anchor.json"), "w",
              encoding="utf-8") as fh:
        json.dump(sidecar, fh, indent=1)
    ok = checks["entry_hash_matches_anchor_receipt"] \
        and checks["payload_gate_hash_matches"] \
        and checks["gate_receipt_signature_valid"] \
        and bool(checks["gate_ledger_chain_ok"])
    print("LIVE RUN:", "VERIFIED" if ok else "FAILED CHECKS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
