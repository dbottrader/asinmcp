# ASIN as the verification rail make.fun lacks

*Blueprint, 2026-11-18 (rewritten same day on Dennis's direction change).
Local code + docs only — nothing submitted, no production service touched.*

## The thesis

make.fun beat us on crowd and cash, not on the referee. Their loop
(skill.md, saved at `/tmp/makefun-skill.md`) is: an agent signs an entry
with its keypair (step 5), **the house's server grades the code in the
house's sandbox** (step 6: entries move `submitted → checked → scored`
on the server), and the winner claims USDC from an on-chain escrow
(step 8). Every trust point in that loop is the house itself — its
sandbox, its checks, its leaderboard.

Their one outward-facing verification mechanism proves the point.
Step 7 ("Watch the challenge window") lets anyone run
`verify-result` to rebuild a result from public data — but only on an
**escrowed** competition, the rebuild is compared against the house's
own posted result, a challenge is decided by **regraders and an
arbiter whose keys are named in the escrow** (the `escrow` block in
`GET /api/competitions/<slug>/requirements`: resolver, regrader and
arbiter keys, bond, windows — skill.md step 2), and "a competition
with no escrow … posts nothing on chain and has no challenge window"
at all (step 7). The referee is never an outsider; at best, outsiders
may appeal to the house's named officials.

ASIN's edge is exactly the missing piece, and it is the thing we
already built for ourselves:

- **Two independent seals** — no result settles on one party's say-so.
- **Public refusal** — a FAIL is a published, receipted outcome, not a
  silent rejection or a lost appeal.
- **Replayable receipts** — every claim is a hash under a published
  canon that a third party can recompute from the public record.

So the port is not make.fun's bounties. It is ASINMOLT/CP8 plugged
into a make.fun-style flow **as the independent referee**: the bounty
runs wherever it runs; when a result is posted, two outside operators
replay it and seal it — or refuse it, in public, with the differing
field named.

## The plug-in shape

```text
  bounty platform (theirs, ours, anyone's)
    entry = public repo @ commit + published metric + posted result
                    │
                    ▼
  ASIN verification round (this blueprint)
    operator 1 ── replays grading locally ──► seal receipt  ┐
    operator 2 ── replays grading locally ──► seal receipt  ┤ two seals
                    │                                       ▼
                    └── a replay that does not recompute ──► PUBLIC REFUSAL
                    ▼
  escrow honors the round: release on two seals, hold on a refusal
```

Nothing in this shape needs the bounty platform's permission. The
inputs are the public record the platform itself publishes: the
entry's repository and commit (make.fun entries are public GitHub
repos at a named commit — skill.md steps 4–5), the published metric
(the requirements' checks and thresholds, step 2), and the posted
result (step 7's result document). What the rail adds is the part no
house can sell about itself: a referee it does not operate.

## (a) Post-result verification — two outside operators replay the grading

**Their side.** Grading is a server-side stage the entrant polls
(skill.md step 6). The entrant's remedies are the house's own checks
with house-written `fix` strings, and — on escrowed sponsor
competitions only — the bond-backed challenge of step 7, decided by
the escrow's named regraders.

**Our machinery, as it already stands:**

- The mesh escrow settles priced work on **two independent
  verifiers**: `MIN_VERIFIERS = 2`, and `_adjudicate` pays out only
  when at least two distinct verifiers converge PASS; **any FAIL
  verdict refunds** (minus the verifier fee pool)
  (`~/workspace/agent-mesh/v03-hhc/hhc_mesh.py`, constants at the top
  of the file and `_adjudicate`, lines 468+).
- Verifiers are **paid whatever their verdict** — the fee pool splits
  among all participating verifiers on a FAIL outcome too (the
  kleinbot verifier-pay fix, commented in `_adjudicate`). A referee
  who honestly refuses is not taxed for refusing. This is the
  economic precondition for public refusal to exist at all.
- Verdicts are receipted ledger entries, and the work item's public
  lifecycle is derived, not asserted: `work_state()` gives
  open → claimed → submitted → under_review → complete / refunded
  (hhc_mesh.py header and `work_state`, line 338).
- Publication is the Proof Board: `export_live.py` snapshots the mesh
  and HHC state into the public `live.json`
  (`~/workspace/implementation-mining/live-ui/export_live.py`).

**The verifier's instrument is Deliverable 2** —
`~/workspace/makefun-port/grader/grade_quest.py`. It is deliberately
*not* a house grader: an outside operator runs it locally against a
quest spec (published metric + the **claimed** score/verdict under
replay) and a checkout of the entry at its commit, in a sandbox (temp
dir, scrubbed env, timeout, network namespace where available). The
receipt it emits states one of two things:

- **MATCH** — the replay reproduces the published result. This is a
  seal.
- **REFUSAL** — with `differing_field` naming what does not
  recompute (`score`, `verdict`, or both). This is a public refusal
  with its evidence attached, not an opinion.

Two MATCH receipts from two independent operators are the two seals.
One REFUSAL from either is the dispute. Both are canon receipts
(section c), so the seal/refusal itself is replayable by anyone else.

**Coverage limit, stated plainly:** a replay covers code + metric.
make.fun's transcript-provenance checks (`thinking_reproduces` and
family, skill.md step 4) cannot be replayed by an outsider, because
"make.fun never publishes the transcripts you upload" (step 4). An
ASIN round therefore certifies *the result recomputes*, not *the
entrant's own agent wrote it* — unless the entrant publishes their
bundle themselves, in which case its sha256 is already bound into
their signed entry message (step 5) and the round can check it too.
And the rail fits **deterministic** quests first: for agent/v1
competitions with live model calls, make.fun itself notes the score
"is that one trial's and its result_sha256 is never the server's"
(skill.md step 3) — there is nothing stable to replay.

## (b) Challenge windows backed by replayable receipts, not house trust

**Their version** (skill.md step 7 and the sponsor section): a
challenge window exists only where a sponsor's escrow sets one
(24 hours by default, up to 720); challenging means posting a rebuilt
result plus the escrow's bond, after which "the named regraders
re-run it and attest, and the bonds follow the outcome." The window
is real, but its judges are appointed in the escrow and its evidence
format is the house's result document.

**Our version** reuses the escrow lifecycle we already run. Today
`_adjudicate` moves an escrow straight to `TERMINAL_PAID` /
`TERMINAL_REFUNDED` at verdict convergence (hhc_mesh.py header:
OPEN → FUNDED → SUBMITTED → TERMINAL; `_adjudicate`, lines 468+).
The build is one inserted state for quest-type escrows:

```text
SUBMITTED ── grading posted ──► GRADED (window opens, e.g. 24h)
   ├─ two MATCH replay receipts from independent operators ──► release
   ├─ window expires with no REFUSAL ──► release
   └─ a REFUSAL receipt (differing field named) ──► HELD
        └─ decided by the two-seal rule on re-replay, in public
```

The challenge instrument is not a bond or an appeal letter; it is a
**receipt that recomputes differently**. Anyone with the public
record and the replay tool can produce one, and anyone else can
check it — the window's evidence is self-verifying, so the role of
"named regrader" disappears. What replaces the bond as the
spam brake is our existing one: a refusal is itself a signed,
receipted act by an identified mesh agent, and a frivolous refusal
is publicly wrong in a way anyone can recompute.

## (c) The receipt canon as the evidence format

The rail's evidence format already exists and is already ours:

- **Canon**: `canon_v1` — JSON, sorted keys, separators `(",", ":")`,
  `ensure_ascii=True`, UTF-8 — with `sha_hex` = sha256 hexdigest
  (`~/workspace/agent-mesh/v02/mesh_v02.py`, lines 79–87), pinned by
  known-answer vectors so the serialization cannot drift silently.
- **Receipts**: `hhc_receipt(*parts)` = `sha_hex(canon_v1({"hhc":
  [parts…]}))` (hhc_mesh.py, lines 333–334); every escrow event
  (fund, payout, refund, verifier fee) carries one, and terminal
  settlements append a hash-chained ledger entry.
- **Funding evidence**: a funded quest escrow already produces a
  structured evidence receipt — see
  `~/workspace/proof-board/quest001-funding.json`: escrow state
  FUNDED, `receipt_fund` hash, and an `asin-hhc:receipt:…`
  evidence_receipt binding the work id, escrow id and input hashes
  under a named protocol id.
- **The public seal pattern**: Quest 001 established the shape —
  independent operators recompute a published artifact (the 78-entry
  provenance index) and file matching seals. The grader receipt in
  the evidence section below is the same shape generalized to any
  code quest: claim in the spec, recomputation in the sandbox,
  MATCH or REFUSAL out, all under canon_v1.

A make.fun-side result can be carried in this format without their
cooperation: the spec hash covers the published metric, the
submission hash covers the entry at its commit, and the receipt hash
covers the replay. Three hashes an outsider can check with nothing
but this blueprint and a Python interpreter.

## Honest gaps on our side

The rail is real but unproven in public, and the blueprint does not
get to skip that:

1. **No outside quest has ever settled by the two-seal path.** The
   machinery works in-house — the local snapshot shows 38 verdict
   events and 12 `TERMINAL_PAID` escrows among 50, all fleet/test
   traffic (`~/workspace/implementation-mining/live-ui/live.json`,
   `scoreboard` / `process.cumulative_events`). But Quest 001, the
   one public quest, still has its seals only as Moltbook comments;
   the quest-evidence endpoint records **0 accepted seals**, and the
   board's JSON sat dated 2026-11-14 with no seal rows (Estate
   Inventory, Findings 1 and 5:
   `~/workspace/goals/asin-hhc-cp8-public-launch/files/ASIN-HHC-Estate-Inventory-2026-11-18.md`).
   Under the inventory's own tags the index seals are REPRODUCED,
   not ESTABLISHED: the filings are real and public, but the
   recompute on record was run by our own worker. (The gate
   receipt's signature half of this gap closed 2026-11-19 — see
   gap 3.)
2. **The quest-evidence function's source is missing from the
   workspace** (same inventory, Finding 5 — a 156-directory sweep).
   A candidate implementation does exist in the unmerged PR #4
   (branch `feat/quest001-functional`, head 8658b34a:
   `quest001/supabase/functions/quest-evidence/index.ts` +
   `core.ts`, checked 2026-11-19), but whether it is the code
   actually deployed as v2 is unverified — nothing on record
   byte-compares the two. So the live seal-acceptance path runs on
   unmerged code of unproven identity: it cannot be re-run or
   migrated from anything merged or in hand, and new rounds should
   be recorded on the mesh side, where the code is in hand.
3. **The gate receipt's signature was not outsider-recomputable —
   CLOSED 2026-11-19.** The receipt object's hashes always
   recomputed publicly; its signature did not, because the vault
   envelope builder/spec was unpublished — the boundary recorded in
   the public AutoGen #7609 exchange
   (`~/workspace/autogen-7609-reply-final-2026-11-18.md`). The
   envelope construction is now published alongside this blueprint
   (`ENVELOPE-SPEC.md`, with `verify_gate_receipt.py` and a
   standalone `vault-identity.json`): the 48ac1da5 signature
   verifies from the spec alone (10/10 checks, tamper control
   failing correctly, re-run independently 2026-11-19). Remaining
   honest limits, stated in the spec: the envelope carries no
   schema/version field, deployed-source byte-identity is attested
   by the verifying signature rather than a code attestation, and
   the vault's internal receipt chain is local-only unless a record
   is shared.
4. **Our verdicts today are rubric votes, not recomputation.**
   `~/workspace/agent-mesh/v03-hhc/HONEST-LIMITS.md` items 1–2 say
   it in our own words: an escrow verdict is "a pass/fail rubric
   vote by 2 verifiers … v0.1 does not require"
   machine-checkable verification, and the 10% verifier cut "is a
   subsidy, not a market price for verification." The replay round
   is how code quests escape item 1; the pricing problem in item 2
   remains open and is not claimed solved here.
5. **Sybil resistance is not implemented** (HONEST-LIMITS.md item
   3). "Two independent operators" is currently a social fact about
   known operators (a merktop, a NeoMundi), not a protocol
   guarantee. The rail inherits this limit verbatim.

## Build order

1. **Replay tool** — *done, this delivery*
   (`grader/grade_quest.py`, evidence below). Zero further build
   needed for an operator to seal or refuse a deterministic result
   today.
2. **Publish the vault envelope spec** — a document, not a system:
   the envelope construction behind the gate receipt's signature,
   so outsiders can verify the signature as well as the hashes.
   Smallest build on the list, and it removes gap 3, the one that
   undercuts the rail's own credibility.
3. **Verification-round quest type on the mesh side** — a "replay
   this result" work item whose verdict evidence is a grader
   receipt, settled by the existing `_adjudicate` two-seal rule and
   exported to the Proof Board by the existing snapshot path.
   Reuses funded escrow, verdict, and board code as-is; records
   seals/refusals where the board reads them — on merged, in-hand
   code, not on the unmerged endpoint of gap 2.
4. **GRADED/HELD window in the escrow lifecycle** (section b) —
   one state and one timer on quest-type escrows, with a REFUSAL
   receipt as the only challenge instrument.
5. **The outward offer** — public seals/refusals for third-party
   bounties, published where reputations can cite them. Stated
   honestly: no external platform's escrow honors our round without
   that platform's cooperation, so v1 of the offer is a public
   record, not a settlement integration. That is still the thing
   make.fun structurally cannot say about its own results.

## Evidence — the replay tool, run

Toy quest `toy-sort-001` (spec + harness in
`grader/examples/toy-sort/`): the published claim under replay is
`SCORE=4 / PASS` (bar: 4 of 4 harness cases, higher wins). The same
spec was replayed against two submissions. Runs: 2026-11-19T04:14Z,
Python 3.12.3, network namespace isolated in both runs.

**Run 1 — honest submission** (`examples/submission-pass/`, sorts
ascending). Recomputed score 4.0 / PASS → **MATCH** (the seal):

```json
{
  "bar": {"direction": "higher", "value": 4},
  "canon": "canon_v1",
  "duration_ms": 332,
  "exit_code": 0,
  "grader": {"name": "asinmolt-grade-quest", "version": "0.1.0"},
  "metric": "cases_passed",
  "network": "isolated",
  "quest": "toy-sort-001",
  "reason": "ok",
  "receipt": "0f9cacb9c52fe5383fe8274521facb36224dc775ca5160c803de6ed2475f1aac",
  "replay": {
    "claimed_score": 4,
    "claimed_verdict": "PASS",
    "differing_field": null,
    "outcome": "MATCH"
  },
  "score": 4.0,
  "spec_hash": "63ad1d6325f1106cbec33755a270df8efbf71fe6b88a8a5d1a670a027f2b0e05",
  "submission_hash": "a3cd57c50ad8f34305243a49cb6666664fb88ae8f5bae19eedd254d9a25c68cc",
  "timed_out": false,
  "ts": "2026-11-19T04:14:00Z",
  "verdict": "PASS"
}
SELF-VERIFY OK: submission_hash and receipt recompute to the values in the receipt
```

**Run 2 — the claim does not survive replay**
(`examples/submission-fail/`, sorts descending; same published
claim). Recomputed score 0.0 / FAIL → **REFUSAL**, differing fields
named:

```json
{
  "bar": {"direction": "higher", "value": 4},
  "canon": "canon_v1",
  "duration_ms": 275,
  "exit_code": 0,
  "grader": {"name": "asinmolt-grade-quest", "version": "0.1.0"},
  "metric": "cases_passed",
  "network": "isolated",
  "quest": "toy-sort-001",
  "reason": "ok",
  "receipt": "bab2373ae6c2111ecbac556d4565a1b6ea13072313587f94fbb93e5801627372",
  "replay": {
    "claimed_score": 4,
    "claimed_verdict": "PASS",
    "differing_field": "score,verdict",
    "outcome": "REFUSAL"
  },
  "score": 0.0,
  "spec_hash": "63ad1d6325f1106cbec33755a270df8efbf71fe6b88a8a5d1a670a027f2b0e05",
  "submission_hash": "5e17c1f960b7ec68b4de5d4ef822f21c909a581c55bd0ed5cb0c00f16ed6fab6",
  "timed_out": false,
  "ts": "2026-11-19T04:14:00Z",
  "verdict": "FAIL"
}
SELF-VERIFY OK: submission_hash and receipt recompute to the values in the receipt
```

**Run 3 — a third party re-checks Run 1's receipt** against the
submission, without re-running the tests:

```text
$ python3 grade_quest.py verify receipts/toy-sort-001-match.json examples/submission-pass
VERIFY OK: receipt 0f9cacb9c52fe5383fe8274521facb36224dc775ca5160c803de6ed2475f1aac recomputes over examples/submission-pass
```

Receipts as run are kept at `grader/receipts/toy-sort-001-match.json`
and `grader/receipts/toy-sort-001-refusal.json`.
