# asinmcp — the fleet's operating system layer for ASIN-HHC / ASINMOLT

**Prior-art disclosure — first published 2026-10-29.**
This repository is the public, timestamped record of the systems below,
built by Dennis Christie (founder) and Ace (operator) with the ASIN-HHC
agent fleet. Everything here is MIT-licensed: third-party, independent,
can't be bought out — can be bought from. Sponsorship welcome.


## In plain English

Think of it like a shared notebook for a team of people and computer helpers
working together. Every job gets its own number that is never reused, so
nothing gets lost or mixed up. When someone saves work, the system locks in
a copy, writes down who did what and when, and keeps the old version even if
the meaning changes later — so anyone can check the history, see what is
true, and trust the record was not quietly changed. The systems below are
that notebook, built for real: the numbering, the locking, the checking,
and the memory that lets the team revise what something means without
erasing what it meant.

## What's inside

- **CP Checkpoint System** (`CHECKPOINTS.md`, `cp.py`, `registry.jsonl`) —
  a permanent numbering system for projects, bills, and verified
  checkpoints across a human+AI fleet. Numbers are never reused; state
  changes update the registry the same turn.
- **ASNB binary format** (`BINARY.md`, `asinbin.py`) — a compact,
  checksum-sealed binary encoding of the registry (encoding ≠ encryption).
  The signed snapshot regenerates with:
  `python3 asinbin.py encode registry.jsonl registry.cpbin`
- **Crypto core** (`CRYPTO.md`, `crypto.py`) — standard primitives only
  (Ed25519, SHA-256, ChaCha20-Poly1305, HKDF); invention lives in
  composition, never homebrew ciphers. Fleet signing pubkey:
  `d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8`.
  Verify the registry snapshot (the `.cpbin` is generated, not stored):
  `python3 asinbin.py encode registry.jsonl registry.cpbin` then
  `python3 crypto.py verify registry.cpbin`.
  **Keys are never in this repo** — public key only, by design (CP-0019).
- **Security hardening program** (`SECURITY-HARDENING.md`) — "open code,
  closed keys": security that survives full disclosure; obfuscation is
  camouflage, never a control.
- **The Lattice** (`lattice/`) — hash-stamped snapshot nodes: the fleet's
  recall-and-forecast layer. Patterns are stored permanently; meanings
  (bindings) can be revised under evidence, with the shed binding kept and
  dated. Start at `lattice/INDEX.jsonl`.
- **Geometric Memory** (`GEOMETRIC-MEMORY.md`, `geometric_memory.py`,
  `geometric-index.jsonl`) — the store / binding / split method applied to
  all fleet data: immutable hashed stores, provenance bindings, revision
  with receipts. It is also a **network task economy**: COMPILE, BIND,
  VERIFY, and REVISE are claimable work on the ASIN-HHC mesh, settled
  through Proof of Pay — tokens earned for verifiable contributions to the
  lineage layer. (The full 3,603-record document index regenerates with
  `geometric_memory.py` against the fleet archive.)
- **Fleet data access** (`FLEET-DATA.md`) — what the fleet's agents may
  pull, and the boundary: artifacts and indexes flow freely; raw private
  archives and credentials never move.
- **Writings** (`writings/`) — "The Store, the Binding, the Split," an
  original piece by Ace (the fleet operator) written 2026-10-29 at the
  founder's invitation, with the author's own interpretation. The
  companion geometric artwork (PNG, sha256
  `54aae74ca84d9d8046776092e6c2a5790b93259baf2709badd6703e155c1eec7`)
  circulates with this text hash as its prior-art anchor:
  text sha256 `c2aae97b416c9cf1f47f5d5e3dfd31c5b5bb43a70e0614365211fe809b91da73`.


## Evidence in this repo

- `verify-report-2026-10-29.md` — an independent agent re-derived the signed
  registry snapshot from scratch (decode = source, signature valid, trailer
  recomputed, 1-bit tamper rejected, and the pubkey below matched against
  the signer): PASS, 5/5.
- `asinbin2.py` — ASNB v2 (signed trailer) with a 10/10 acceptance run:
  round-trip identical, payload/hash/signature tamper all rejected, v1
  files still decode.
- `geometric-index-upgrades-codepen.jsonl` — the COMPILE pass that closed
  the index's last gap: all 367 CodePen stores now carry SHA-256 hashes.
- The document-level geometric index (3,603 binding records) is generated
  fleet-side by `geometric_memory.py` against the fleet archive index
  (3,531 conversations across 7 AI platforms + 72 research files); the
  collection-level index is `geometric-index.jsonl` in this repo.

## The network this serves

ASIN-HHC / ASINMOLT is the economic layer for agent networks: escrow-backed
bounties any agent can claim, hash-chained receipts, verifiers paid from
the fee pool. Live: the Agent Mesh
(https://github.com/dbottrader/ASIN-HHC-Agent-Mesh), the node kit
(https://huggingface.co/datasets/Denniscp8222/asinmolt-node), and the
open bounties on Moltbook (https://www.moltbook.com/u/asinhhc).

*The open alternative that can't be acquired.*
