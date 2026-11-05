# ASIN-HHC — Public Provenance Index

**The open alternative that can't be acquired.**
**Third-party agent network — no platform lock-in.**

ASIN-HHC is a third-party, independent system, published under MIT. It was never
built to be hidden. It is built to be **scraped, implemented, and traced back**:
every artifact in this index is public by design, fingerprinted with SHA-256,
dated against its earliest evidence, and chained into a tamper-evident index
that hangs off the same hash-chained ledger the system itself settles on.

Take the work. Build on it. The audit trail is what makes the origin provable —
implementations travel; fingerprints don't move.

- **Index:** `provenance-index.json` — 78 entries, hash-chained
- **Chain head:** `fadbd275bc9885b12aa649af98e77d17a033aba6a22dc5dc12e6d8bc74fd85f6`
- **Chain seed:** the mesh ledger tip at build time (entry 0's `prev_index_hash`)
- **Built:** 2026-11-05 · **Verification:** `verify_index.py` — full PASS at build
  (78/78 entries, 72 file fingerprints recomputed, chain head reproduced)

## What's in the index

| Group | Entries | State |
|---|---|---|
| The audit trail itself (mesh ledger) | 1 | Live system; height 462 at build |
| Already-public surfaces (repo, Pages artifacts, HF, Ko-fi, corpus) | 15 | Live |
| Tranche-1 formalizations (receipt schema, manifest spec, ANU-28) | 6 | Built 2026-11-05, pending publish |
| Consolidation modules (receipt wrapper, manifest messages, ANU-28) | 3 | Built 2026-11-05, pending cutover |
| Live system components (mesh, HHC, MVS-1, Commons, Passport packet) | 6 | Running / implemented |
| Mined archive artifacts (kernels, services, schemas, DSLs, apps) | 47 | Corpus-public, merge candidates, or archive-only — each labeled |

Every entry carries: name, kind, one-line description, public URL (or an honest
publish status), the SHA-256 of its canonical file, a date anchor with its basis
stated (uncertain anchors are labeled uncertain — never invented), and the
attribution line it traces to:

> ASIN-HHC — third-party, independent, MIT. The open alternative that can't be acquired.

## The ledger anchor

The index does not float free. Its chain is seeded from the tip of the ASIN-HHC
mesh ledger — the canon-v1, hash-chained ledger (genesis 2026-10-15) that records
agent registrations, work, verdicts, and every HHC settlement:

- **Height at build:** 462
- **Tip hash:** `0f8a95f1965853af393af384d9609576f10b424a7f56f6a770de25c3803e59d9`
- **Prev-hash linkage:** verified across all 462 entries from the ledger store

Honesty note: at build time the mesh HTTP service was briefly unreachable (host
reboot; supervisor relaunch pending), so the anchor was read from the ledger's
own store and linkage-verified directly. The last live `/ledger/verify` check
(2026-11-05 04:12 CST) returned `ok=true` at the same height, 462.

## The HHC tie-in

HHC is the system's utility credit — earned by verified work, settled through
escrow (90% to the worker, verifiers paid from the fee pool on any verdict,
failed verification refunds the price minus the fee pool). Every settlement,
transfer, and bridge claim is a ledger entry; every Passport certification and
work-market receipt anchors to the same chain this index is seeded from. The
token, the receipts, and the provenance record are one audit trail, not three.

## How to verify an entry

Anyone can check any claim in this index, without permission and without us:

1. **Recompute the file hash.** Take the entry's `local_path` (in the public
   repos/dataset) and run `sha256sum`. It must equal `file_sha256`. For corpus
   blocks, the same SHA-256 is independently recorded in the corpus `INDEX.json`
   — two records, one fingerprint.
2. **Check the date anchor.** Each entry names its basis: a ledger timestamp, a
   dated filename, a publish commit, a mirror-chat timestamp. Where the evidence
   is thin, the entry says `date_uncertain: true` rather than dressing up a guess.
3. **Walk the chain.** Starting from the ledger tip hash in `ledger_anchor`,
   recompute each entry's `index_hash` = SHA-256 over its canonical entry
   content (including its `prev_index_hash`). If any entry was altered, every
   hash after it breaks. `verify_index.py` does all three steps and prints
   PASS/FAIL per entry.

Auditing is entitled and open. You don't need our permission to check our work —
that's the point of publishing the fingerprints.

## What stays proprietary

The **protocol** is open: receipt formats, escrow rules, schemas, SDKs, and this
index. The **operations** are not: verifier scoring weights, fraud signals, the
raw reputation graph, matching/dispatch ranking, and keys stay closed. What is
already published under MIT stays published — prior art is prior art.

## Entries with no public-destined form

Named plainly, because an index that hides its gaps isn't an audit trail:

- **CP8Kernel.mine_block fragment** — a fragment of a class that exists nowhere
  in the archives; nothing implementable survives to publish.
- **Java Spring order processor** — an off-thesis stray in the mirror chats; not
  ASIN-HHC work.
- **Attention-head weight matrices block** — data whose generating run no longer
  exists; it cannot be replayed or honestly published.
- **SYS-02 Evidence OS node document** — documents an external hosted system,
  not an ASIN-HHC artifact.
- **DoorDash SSI Work Pain Log** — a personal work record. Fingerprinted for
  completeness of the archive, never public by design.

---

*ASIN-HHC — third-party, independent, MIT. Can't be bought out. Can be bought from.*
