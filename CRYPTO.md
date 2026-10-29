# Crypto System — CP-0021 (fleet-built)

Ordered by Dennis, 2026-10-29 ~01:34 CDT: "these bots need to build the crypto system also."
His framing, same message: his short directives are **seeds** — the system is *evolving,
not stagnant*. Each seed (Lattice → CP numbers → security → ASNB binary) grows into built,
tested pieces; nothing sits as a static plan.

## What already exists (do not rebuild)
- Mesh agents self-generate **Ed25519** keypairs; receipts/statements PoP-signed; ledger hash-chained (SHA-256, height 231 verified, CP-0201).
- Primitives are standard and audited-style: Ed25519, ChaCha20-Poly1305, HKDF, SHA-256 (2026-10-11 verdict: no crypto team, no miners needed; gates = professional audit before real money, coherence math, legal wrapper).
- HHC token contract compiled, **undeployed** (deployment is Dennis's hand only).

## Shipped tonight — crypto core v1 (Ace)
`asinmcp/crypto.py` — Ed25519 signing for fleet artifacts, reusing the kit's ed25519 module:
- Fleet signing key generated: pubkey `d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8` (public). Seed in `asinmcp/keys/` only — dir 0700, file 0600, never published (CP-0019 S2).
- `registry.cpbin` signed → `registry.cpbin.sig.json` (artifact hash + signature + signer).
- Verified live: sign → verify **OK**; one-byte tamper → hash FAIL, signature FAIL, exit 1. Tamper-evidence is real, not claimed.

## Bots' build queue (delegated, judged on artifacts)
1. **GrokAce:** independent verifier — reimplement ASNB decode + Ed25519 verify of `registry.cpbin` from the specs alone (independent reimplementation = the verification, same doctrine as Ryan's ledger recompute).
2. **GrokAce:** ASNB v2 design — signature embedded in the format trailer (sig over header+records), version byte bump, backward-compat decode of v1.
3. **Fleet (design first):** mesh key-custody upgrade — real seed custody per agent (closes the old P3 "pubkey is actually a seed" defect class), backup/rotation story per node, no operator-held keys.
4. **Fleet:** signed checkpoints — every CP-02xx state anchor gets a signed snapshot; lattice nodes hash-linked to the previous signed snapshot (chain of custody for memory itself).
5. **Held by design:** token deployment, any real-money movement — Dennis's explicit per-action approval only; professional security audit before real money flows (2026-10-11 gate stands).

## Doctrine
Standard primitives, openly specified, keys closed (CP-0019). Custom invention lives in the
*composition* (ASNB, lattice, CP registry, receipt chains) — never in homebrew ciphers.

## Reuse-first rule (Dennis, 2026-10-29 ~01:35 CDT)
Reference all open-source data and all data already processed by AI before writing anything
new — it saves time and inherits verification already done. Build order for every job:
1. **Our processed data first:** the 3,531-doc multi-AI archive + index, the HF code corpus,
   `research_notes/` (incl. the four 2026-10-28 fleet consults merged into V03-SPEC), the mesh
   and kit source, Ryan's audit, the lattice/CP registry itself.
2. **Open source second:** audited primitives and reference implementations (the kit's
   ed25519 module is tonight's example — crypto core v1 reused it instead of rewriting it).
3. **New code last, and only for the delta** — the part that is actually ours to invent.
