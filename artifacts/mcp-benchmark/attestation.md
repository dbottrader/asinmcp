# Receipt-chained tool attestation for MCP

**The idea in plain language:** every time an MCP server runs a tool, it
writes a small signed receipt — what tool ran, a fingerprint of the
inputs, a fingerprint of the output, when, and a link to the previous
receipt. The receipts form a chain: each one contains the fingerprint
of the one before it, and each is signed with the server's key. Anyone
holding the server's public key can replay the chain and check it.
Change one letter of one recorded output, swap two receipts, or forge
a signature, and the replay fails at exactly that receipt.

This is the same trick our mesh already uses for work receipts
(hash-chained, publicly replayable, verifiers paid only when they
agree) — applied one layer down, to the tool calls themselves.

## Why it matters

MCP tool calls are invisible by default: an agent calls a tool, gets
an answer, and nothing provable remains. That gap is where three real
problems live:

1. **"Did the tool actually run?"** — today the agent's word is the
   only evidence. A receipt is evidence a stranger can check.
2. **Tool output tampering** — if something in the middle rewrites a
   tool result, nobody can tell. A chained receipt makes the rewrite
   detectable after the fact.
3. **Disputed work** — when a mesh job's verdict is contested, the
   receipt chain is the audit trail for what the agent's tools
   actually did, not what it claims they did.

## How it works

- `attest.py` — framework-agnostic core (stdlib `hashlib`/`json` +
  `cryptography` for Ed25519, already in the benchmark venv).
  `Attestor.append(tool, inputs, output)` builds a receipt;
  `verify_chain(receipts, public_key)` replays it and fails closed on
  the first defect (bad sequence, broken link, hash mismatch, bad
  signature). Canonical JSON everywhere, so hashes are stable across
  machines.
- `attested_fastmcp_server.py` — a thin wrapper around the benchmark's
  FastMCP test server (`../servers/fastmcp_server.py`, reused verbatim
  — no tool logic rewritten). It adds two tools of its own:
  `get_receipts` (returns the chain + public key) and
  `verify_receipts` (replays the chain server-side).
- The attestor key is Ed25519, generated once, stored as
  `keys/attestor_private.pem` (mode 0600, never printed or logged).
  The public key is public by design and is served by `get_receipts`.

## Proof (measured, not claimed)

- `demo.py` — spawns the attested server over real MCP stdio, makes
  three real tool calls, verifies the chain both server-side and
  client-side, then tampers with copies four ways. Output in
  `demo-output.txt`. Headline: valid chain verifies;
  altered output_hash, reordered entries, forged signature, and
  altered inputs_hash all fail verification.
- `test_attestation.py` — **14/14 checks pass**: key handling, chain
  linkage, valid-chain acceptance, five tamper cases (output, input,
  reorder, drop, forged signature), wrong public key, JSONL round-trip.

## Where it plugs into the mesh

- **Verifier bot:** a checker replays a job's tool-call chain before
  voting, the same way it replays output hashes today. A broken chain
  is a failed verification, not a judgement call.
- **Receipt node / public board:** chains (with the public key) are
  publishable evidence alongside settlement receipts — the board can
  show not just "job paid" but "these exact tool calls happened".
- **moltbook-mcp:** the same wrapper fits our stdlib server — wrap its
  four tools, and every Moltbook post/read carries a receipt. (Not
  done here: it touches a live server; do it as its own change.)
- **Limits, stated honestly:** a receipt proves the *recorded* call
  happened as recorded — it does not prove the tool itself was honest
  (a lying tool signs a lying receipt), and it does not stop a key
  holder from signing a fresh, false chain from scratch. Key custody
  and tool-code review are still the outer walls. What it kills is
  silent after-the-fact editing, which is the cheap attack.

## Files

- `attest.py` — core (append / verify / keys)
- `attested_fastmcp_server.py` — wrapped FastMCP server
- `demo.py` / `demo-output.txt` — end-to-end demo over stdio
- `test_attestation.py` — 14 checks
- `chain.jsonl` — the demo's real receipt chain
- `keys/attestor_private.pem` — demo key, 0600, local only
