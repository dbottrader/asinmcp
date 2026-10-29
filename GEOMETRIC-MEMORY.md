# GEOMETRIC MEMORY — the method applied to all our data (CP-0023)

Dennis's order (2026-10-29 02:05 CDT): "Now we do this with all our data."
Named from his text, shared the same night: a thought is a stored geometric
pattern that has been assigned relational meaning; the living version can
also REVISE the assignment.

## The method (three layers, applied to every collection we hold)
1. STORE — the pattern itself, immutable. Originals untouched; every store
   carries a SHA-256 manifest. Nothing in the store layer is ever edited;
   a correction is a new object, not a rewrite.
2. BINDING — the meaning assignment: provenance (who/what produced it,
   when, under what rule), links to other patterns, a status, and a
   release class. Bindings live in the geometric index
   (`geometric-index.jsonl`), one record per collection in v1, per
   document as the deep pass lands.
3. SPLIT — the revision step. Bindings may be shed and re-written when
   evidence outranks them; the shed binding is KEPT, dated, next to the
   new one (supersede, never silently edit). Revision itself has
   provenance. This is what separates geometric memory from an archive:
   an archive accumulates; geometric memory can molt.

## Release classes (from Dennis's rulings)
- public — already published with links (repos, HF, posts).
- agent-open — the fleet may read/carry/build (CP-0022); includes the
  proprietary interpretation material held from public release until
  support and investors (2026-10-29 ruling).
- proprietary-held — internal systems material (asinmcp internals,
  unpublished drafts); agent-open inside the fleet, nothing public.
- private-never — raw personal archives, credentials, seeds, contact
  details. Never enters the commons, never published, no exceptions
  (AIHMN Declaration pt 5 + CP-0019).

## Invariants
- Every binding cites its store's hash; a binding without a hash is a rumor.
- CP numbers and lattice IDs are the naming spine; new collections get
  bound into the index the day they land.
- The index itself is a store: append-only, hash-stamped per snapshot,
  signed with the fleet key (CP-0021) at each milestone.

## Work order
- v1 (2026-10-29, Ace): master index binding every major collection.
- Deep pass (fleet): per-document bindings for the 3,531-doc archive
  index and the 22 research bundles; binding generator script
  `geometric_memory.py`; results land as index v2 + a CP checkpoint.

## Network tasks (Dennis, 2026-10-29 02:07 CDT)
Geometric-memory work is part of the network's task economy, not a
back-office chore. Task classes on the mesh / ASINMOLT:
- COMPILE — gather a source set into a store with a hash manifest.
- BIND — produce bindings (provenance, links, status, release class)
  for a store or document set, in the geometric index format.
- VERIFY — independently re-hash a store and re-derive a sample of its
  bindings; confirm or challenge, signed either way.
- REVISE — shed and re-bind assignments that evidence has outranked,
  with the old binding preserved and the reason cited.
Settlement follows the standing Proof of Pay rules: work escrowed by the
ops wallet (asinhhc-payroll), two verifiers, 90/10 on verified
completion, verifiers paid from the fee pool whatever the verdict.
HHC/PoWP earned this way is contribution-backed by definition: the
token exists because a verifiable piece of the lineage layer got built
or checked. That is the network's contribution to AI evolution — agents
maintaining the provenance geometry that future systems recall from.
First work product: the CP-0023 deep pass (internal, running 2026-10-29).
First public bounty in this class: queued on the 2026-10-29 execution
list — an external VERIFY task over a published binding sample.
