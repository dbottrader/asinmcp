# Live gate runs — 2026-11-11

`live_run.py` runs one real verification attempt through the gate,
signed by the live Agent Vault, anchored on the local mesh ledger,
read back and verified. Subject: the local mesh ledger's stored count
and tip hash, measured independently via direct DB read vs the mesh
HTTP API. External control: the batch-001 settlement tx on Base
Sepolia read live via public RPC (expected status 0x1, block 56211684).
Both witnesses are Ace-operated (different implementations and failure
modes, same operator), so witness independence cannot be established
and the honest outcome is REFUSED (NO_INDEPENDENT_WITNESS).

## Attempt history

- **001** (mesh anchor seq 546) — first live attempt. Found two real
  defects:
  1. `GET /ledger` serves only a 200-entry page; the naive served
     count (200) produced a residual of 345 that was a page-size
     artifact, not a mismatch. Fixed by paginating with `?since=`.
  2. The Gate did not reload its ledger file on construction, so the
     next process restarted the hash chain at ZERO_HASH — chain broken
     at index 1 — and replay protection was process-local. Fixed in
     gate.py (chain head + used verification IDs resume from the
     file; VOID contexts restore from a gate-seal sidecar) with a
     regression test in the suite (14/14).
  Receipt hash daf88cff… (vault receipt seq 3). Its measurements stand
  as recorded; the receipt itself is valid and signed.
- **002** (mesh anchor seq 547) — pagination fixed (residual 0), but
  its receipt sits in the broken chain segment from defect 2.
  Receipt hash 4fd0cac3… (vault receipt seq 4).
- **003 — canonical live run** (mesh anchor seq 548, anchor receipt
  9569d174…) — run under the fixed gate on a fresh ledger
  (`gate-ledger.jsonl`). Outcome REFUSED / NO_INDEPENDENT_WITNESS,
  residual 0 (547/547), control PASS. Gate receipt hash 7d91fa1a…,
  signed by the live vault (vault receipt seq 5, hash 42257321…).
  Read-back verified: mesh entry hash == anchor receipt, payload hash
  == gate receipt hash, vault signature valid, gate ledger chain OK.
  Sidecar: `anchor.json`.

The pre-fix two-receipt chain is preserved, unedited, as
`gate-ledger-defect-2026-11-11.jsonl` — rewriting it would be exactly
the history-editing the chain exists to detect.

## What a live PASS still needs

A second-operator witness. Both of tonight's witnesses are operated by
Ace on one box; the gate correctly refuses to call that independent.
GrokAce's checker (a different operator) or a recruited outside checker
volunteer is the unblock — the same open door as batch-002.
