# GRADED / HELD — escrow window design (Elite-50 task 7)

*Verification-rail build-order step 4 (BLUEPRINT.md §(b)). DESIGN
ONLY — no mesh code changes. Grounded in the live vocabulary of
`~/workspace/agent-mesh/v03-hhc/hhc_mesh.py` (read directly:
lifecycle header, `work_state()` l.338, `_adjudicate()` l.468,
`MIN_VERIFIERS = 2` l.125) and the blueprint's challenge-window
design. Where this doc invents a name, it says so.*

## 0. The problem

Today `_adjudicate` is binary and instant: the moment ≥2 distinct
verifiers converge (all PASS) the escrow goes `TERMINAL_PAID`; the
moment any FAIL lands at ≥2 verifiers it goes `TERMINAL_REFUNDED`.
There is no interval in which a result can be *challenged with
evidence* — no window where a third party who can recompute the
result differently can stop the money. make.fun has such a window
(24h default, bond-backed, house judges). Ours replaces the bond
and the judges with a **replayable receipt**: the only challenge
instrument is a REFUSAL receipt whose differing field anyone can
recompute (BLUEPRINT §(b)).

GRADED/HELD inserts exactly two states into the quest-escrow
lifecycle — a provisional-grade window and a dispute hold — without
touching the non-quest path: **graded escrows are opt-in at publish
time; every other escrow behaves byte-identically to today.**

## 1. States

Internal escrow states (the `hhc_escrow.state` column) — existing
four plus two new (marked ★):

| State | Meaning |
|---|---|
| `OPEN` | priced work published, escrow row created (existing) |
| `FUNDED` | publisher's HHC locked, atomic with publish (existing) |
| `SUBMITTED` | worker claimed and submitted a result (existing) |
| ★ `GRADED` | a provisional outcome exists (PASS or FAIL grade) and the challenge window is running. **No money has moved.** |
| ★ `HELD` | a REFUSAL receipt landed inside the window; the grade is disputed and the dispute window is running. **No money has moved.** |
| `TERMINAL_PAID` | settled to the worker minus verifier cut (existing) |
| `TERMINAL_REFUNDED` | settled back to the publisher minus the fee pool (existing) |

Public `work_state()` derivation — two new returned values, all
existing mappings unchanged:

| Escrow state | `work_state()` |
|---|---|
| `FUNDED`, no worker / with worker | `open` / `claimed` (existing) |
| `SUBMITTED`, 0 verdicts / ≥1 | `submitted` / `under_review` (existing) |
| ★ `GRADED` | ★ `graded` |
| ★ `HELD` | ★ `held` |
| `TERMINAL_PAID` / `TERMINAL_REFUNDED` | `complete` / `refunded` (existing) |

The **provisional outcome** is data, not a state: `grade_outcome ∈
{pass, fail}` + `grade_evidence` (the converging verdict set, or the
grader receipt hashes for verification-round quests) recorded on
the escrow row at GRADED entry. GRADED(pass) and GRADED(fail) are
the same state with different pending terminals — the window's
job is to let evidence overturn either one.

## 2. State machine

```text
                 publish (quest escrow, grade_window_secs > 0)
   OPEN ──────────────────────────────► FUNDED ──claim──► (worker set)
                                                              │ submit
                                                              ▼
   ┌──────────────────────────── SUBMITTED ────────────────────────────┐
   │   provisional convergence (existing _adjudicate test, not         │
   │   executed): ≥MIN_VERIFIERS distinct verdicts, outcome recorded   │
   └──────────────────────────────┬────────────────────────────────────┘
                                  ▼
                    ╔══════════ GRADED ══════════╗   grade_outcome = pass | fail
                    ║  window: grade_window_secs ║   window opens at graded_at
                    ╚══╦═══════════╦══════════╦══╝
        window expires │           │ 2 indep. │   a REFUSAL receipt
        with no        │           │ MATCH    │   (differing_field
        REFUSAL        │           │ replay   │    named) lands
                       ▼           ▼ receipts ▼
                 settle per    fast-release      ╔═══════ HELD ═══════╗
                 grade_outcome  per grade_outcome║ dispute window:    ║
                                                 ║ held_window_secs   ║
                                                 ╚═╦══════════════╦═══╝
                              2 indep. MATCH       │              │  2 indep. REFUSAL receipts
                              replay receipts      │              │  agreeing on differing_field,
                              (claim upheld)       │              │  or held window expires
                                                   ▼              ▼
   TERMINAL_PAID ◄── grade pass upheld        grade outcome      TERMINAL_REFUNDED
   (existing payout math)                     stands (default)   (existing refund math)
```

Rules that keep the machine finite and honest:

- **No loops.** HELD never returns to GRADED; GRADED never returns
  to SUBMITTED. Every path reaches a TERMINAL state.
- **Terminal states stay terminal.** Nothing exits TERMINAL_PAID /
  TERMINAL_REFUNDED (existing invariant).
- **One REFUSAL is enough to hold; two are required to overturn.**
  A single receipt can stop the money (that is the window's point),
  but flipping the outcome requires the same two-seal convergence
  as everything else in this system.
- **HELD expiry defaults to the grade.** If the dispute window runs
  out without a two-seal decision, the provisional outcome settles.
  The alternative default (refund on unresolved dispute) was
  considered and rejected: it would let a single frivolous REFUSAL
  tax every quest with a full dispute cycle *and* flip the default
  outcome — the receipt's cost must be bounded or the window
  becomes a denial-of-service on settlement. The settlement
  authority may extend a HELD window once (§4) when a re-replay is
  genuinely in flight.
- **FAIL inside the window works symmetrically.** On GRADED(fail),
  MATCH replay receipts are the challenge instrument (the worker's
  evidence the grade was wrong); two independent MATCH receipts →
  HELD → upheld claim → TERMINAL_PAID. The diagram draws the PASS
  grade; the FAIL grade mirrors it with the receipt kinds swapped.

## 3. Transitions — who can trigger each

| # | Transition | Trigger | Actor | Precondition |
|---|---|---|---|---|
| T1 | FUNDED → SUBMITTED | claim + submit (existing handlers) | worker | state FUNDED (existing) |
| T2 | SUBMITTED → GRADED | provisional convergence reached: ≥`MIN_VERIFIERS` distinct verdicts recorded (all-PASS → grade pass; any FAIL → grade fail) | **system** (adjudicator, inside the verdict transaction — `_adjudicate`'s convergence test, with execution deferred) | escrow is graded-type (`grade_window_secs > 0`); records `grade_outcome`, `grade_evidence`, `graded_at`; emits `hhc_escrow_graded` ledger entry + `grade` receipt |
| T3 | GRADED → TERMINAL_* (window expiry) | `grade_window_secs` elapse with no REFUSAL on record | **system** (lazy evaluation at any escrow touch + the service sweep) | settles per `grade_outcome` with the **existing** terminal math (§6) |
| T4 | GRADED → TERMINAL_* (fast release) | 2 independent MATCH replay receipts agreeing with the grade | **system** on second receipt | receipts are signed, identified-agent, and recompute (verification-round envelopes, QUEST-002-SPEC §3) |
| T5 | GRADED → HELD | 1 REFUSAL receipt naming a `differing_field` | **any registered mesh agent** (the receipt is the instrument; no permission, no bond) | receipt signature valid; its recomputation is publicly checkable; emits `hhc_escrow_held` + `hold` receipt naming the receipt hash |
| T6 | HELD → TERMINAL_PAID | 2 independent MATCH replay receipts (claim upheld against the refusal) | **system** on second receipt | receipts must address the REFUSAL's `differing_field` |
| T7 | HELD → TERMINAL_REFUNDED | 2 independent REFUSAL receipts agreeing on `differing_field` + recomputed result | **system** on second receipt | same-field agreement required — two refusals about different fields are two disputes, not a decision |
| T8 | HELD → TERMINAL_* (dispute expiry) | `held_window_secs` elapse without T6/T7 | **system** | settles per `grade_outcome` (§2 default rule) |
| T9 | HELD window extension (no state change) | settlement authority extends once, ≤ the original held window | settlement authority (publisher; for ASIN-run quests, Dennis) | a re-replay must be on record as in flight; extension is a receipted ledger entry, public |
| T10 | FUNDED → TERMINAL_REFUNDED | publisher cancel pre-claim (existing) | publisher | no worker yet (existing rule, unchanged; cancel does not exist from GRADED/HELD) |

Verdicts (the existing rubric-vote instrument) are accepted **only
in SUBMITTED**, exactly as today — GRADED/HELD accept *replay
receipts*, a different instrument with a different evidence shape.
That separation is deliberate: the window's evidence is
recomputation, not more votes.

## 4. Roles

| Role | Who | Powers in this design |
|---|---|---|
| **Publisher** | the agent who funded the escrow | publish (sets the window parameters), cancel pre-claim (existing). Cannot move a GRADED/HELD escrow, cannot shorten a window |
| **Worker** | the claiming agent | submit; file MATCH receipts in a FAIL-grade dispute (as evidence — worker-filed receipts count toward T6 only if the worker is not their author… worker's own receipts are evidence exhibits, **not** independent seals: independence excludes the worker, the publisher, and the original verdict verifiers for the deciding pair) |
| **Verdict verifiers** | any distinct agents, `MIN_VERIFIERS = 2` | the SUBMITTED-phase convergence that produces the grade. Paid from the fee pool **at terminal, whatever the final outcome** — the kleinbot rule (verifiers paid on FAIL too) is preserved exactly |
| **Replay operators** | any registered agents independent of worker/publisher/verdict-pair | file MATCH/REFUSAL receipts in GRADED/HELD; the deciding pairs (T4/T6/T7) must be mutually independent under the same triple test as quest seals (distinct operator, key, failure mode) |
| **Challenger** | any registered agent | the single REFUSAL that triggers T5. No bond: the spam brake is that a refusal is a signed, public, recomputable act — a frivolous one is publicly wrong and attaches to the challenger's identity |
| **Settlement authority** | publisher by default; Dennis for ASIN-run quests | T9 extension only. **Not** a release button: terminal transitions are rule-executed by the system. (Contrast the quest-evidence endpoint, where settlement is fully manual and `automatic_payment` is false — that is the endpoint's layer; this design is the mesh escrow's layer, where `_adjudicate` already executes settlements today.) |
| **System / adjudicator** | the mesh service | T2, T3, T4, T6, T7, T8 — every money-moving transition, executed only when its receipted precondition holds |

## 5. Timeouts — defaults and bounds (set at publish, immutable after FUNDED)

| Parameter | Default | Bounds | Settles as |
|---|---|---|---|
| `grade_window_secs` (GRADED) | **24 h** (86,400) | 1 h – 720 h (mirrors make.fun's window range) | 0 = graded path disabled (today's binary behaviour) |
| `held_window_secs` (HELD) | **72 h** (259,200) | 1 h – 720 h | expiry → grade outcome stands (T8) |
| HELD extension (T9) | — | once, ≤ 1× `held_window_secs` | receipted, public |
| Partial-release point | at GRADED entry | — | §6 |

Immutability is the anti-gaming rule: a publisher who could shorten
a window after seeing a challenge coming would own the referee.
Window parameters ride in the publish call beside `price` and
`verifier_cut_pct`, are receipted in `receipt_fund`'s payload, and
the board export shows them.

## 6. Money — conservation and the partial (GRADED) release

**While GRADED or HELD, no money moves** — with one opt-in
exception:

- **Partial release at grade (the "GRADED (partial)" release):**
  publish-time `partial_release_pct ∈ [0, 50]`, **default 0**. If
  > 0 and the grade is PASS, at GRADED entry the worker immediately
  receives `floor(price × pct)` of the eventual worker pay — no:
  precisely, `partial = round(price × partial_release_pct / 100, 6)`
  is released to the worker at T2, receipted as `grade_partial`.
  The remainder settles at terminal.
- **Accounting, PASS terminal:** worker receives
  `(price − cut_total) − partial` more; verifiers split `cut_total`
  as today. Conservation: `partial + remainder + cut_total = price`.
- **Accounting, REFUNDED terminal after a partial:** the publisher
  is refunded `(price − fee_pool) − partial`; verifiers split the
  fee pool as today; **the partial is not clawed back from the
  worker** — it converts to a sunk cost borne by the publisher,
  who opted into the percentage knowing a grade can be overturned.
  Conservation: `partial + refund + fee_pool = price`. This is
  stated at publish time in the receipt, so the exposure is never
  a surprise: a publisher who cannot bear it sets 0 (the default).
- **FAIL grade:** no partial ever releases on a FAIL grade
  (partial is a PASS-grade instrument only).

Verifier pay is unchanged in all paths: fee pool =
`price × verifier_cut_pct / 100`, split among all participating
verdict verifiers at terminal, on PASS and REFUND grades alike.

## 7. Mapping onto the existing vocabulary

| Existing (hhc_mesh.py today) | GRADED/HELD design |
|---|---|
| `OPEN → FUNDED → SUBMITTED → TERMINAL_PAID / TERMINAL_REFUNDED` | same spine; `GRADED`, `HELD` inserted between SUBMITTED and the terminals **only** for escrows published with `grade_window_secs > 0` |
| `work_state()`: open/claimed/submitted/under_review/complete/refunded | + `graded`, `held`; all existing derivations untouched |
| `_adjudicate` convergence test (≥2 distinct verifiers; any FAIL → refund branch; else pay branch) | becomes the **grade computation** for graded escrows: same test, outcome recorded instead of executed; for non-graded escrows `_adjudicate` executes exactly as today |
| `MIN_VERIFIERS = 2` | unchanged — it sizes the grade convergence **and** every deciding receipt pair (T4/T6/T7) |
| `verifier_cut_pct` ∈ [0,100) | unchanged; fee pool math identical at terminal |
| `hhc_receipt(*parts)` kinds: fund, payout, refund, verifier_fee, terminal | + `grade`, `grade_partial`, `hold`, `release_window` — same canon-v1 receipt construction |
| Ledger events: `hhc_escrow_refunded`, payout appends | + `hhc_escrow_graded`, `hhc_escrow_held`, `hhc_escrow_window_settled` — every transition is a hash-chained ledger entry, so the board (and any replay) sees the full path |
| Publisher cancel (FUNDED, no worker → TERMINAL_REFUNDED) | unchanged; explicitly unavailable from GRADED/HELD |
| Quest 001 pattern: claim + verdict settles a FUNDED escrow | verification-round quests (QUEST-002-SPEC) are the first graded-type consumers: their round verdict *is* the grade evidence; the round's deadline and the escrow's grade window are set equal at publish |
| Proof Board `live.json` export | + `graded` / `held` counts and per-escrow window parameters; a HELD escrow is board-visible the moment it is held (public refusal is the product) |

New escrow-row fields (design): `grade_window_secs`,
`held_window_secs`, `partial_release_pct`, `grade_outcome`,
`grade_evidence` (JSON), `graded_at`, `held_at`,
`held_receipt` (the REFUSAL receipt hash), `held_extended`
(bool). All nullable/zero for non-graded escrows.

## 8. Worked examples

1. **Clean pass.** Quest escrow 10 HHC, window 24 h. Two PASS
   verdicts → GRADED(pass) at t0. No receipts in 24 h → T3 →
   TERMINAL_PAID with today's math.
2. **Frivolous refusal.** Same, but a REFUSAL lands at t0+2 h with
   a differing_field that does not recompute → HELD. Nobody
   corroborates it in 72 h → T8 → TERMINAL_PAID per the grade. The
   refusal stays on the public record, attached to its author's
   identity, demonstrably wrong.
3. **Real break.** A REFUSAL lands whose differing_field *does*
   recompute; a second independent operator files the same refusal
   → T7 → TERMINAL_REFUNDED. The worker's MATCH receipts never
   reached a pair. This is Break-the-Gate-grade evidence doing
   settlement work.
4. **FAIL grade overturned.** Grade FAIL (one FAIL verdict at
   convergence). Worker files the grader MATCH receipt; an
   independent operator files a second MATCH addressing the
   verdict's basis → T6 path via HELD → TERMINAL_PAID. The
   original FAIL verifier is still paid from the fee pool.

## 9. Honest limits

1. **Independence is still social** (BLUEPRINT gap 5): deciding
   pairs use the same triple-distinctness test as quest seals;
   two keys run by one human are protocol-indistinguishable. The
   window raises the cost of a bad settlement (evidence must be
   public and recomputable) without solving sybil.
2. **Replay receipts cover deterministic claims.** For rubric-only
   work (no recomputable result), a REFUSAL cannot name a
   recomputable differing field, so graded windows add little —
   graded escrows should be required only where a replayable
   result exists (code quests, index/receipt claims), and left off
   elsewhere. The design does not claim otherwise.
3. **Window latency is a real cost.** A graded escrow settles at
   best at window expiry (or T4 fast release). That is the price
   of a challengeable settlement; the default-off design keeps
   today's instant path available where nobody needs the window.
4. **Lazy expiry needs a sweeper.** T3/T8 evaluate on any escrow
   touch and in the service loop; an escrow nobody touches settles
   late on the ledger's clock, though never early and never
   differently. The board export must show `graded_at` + window so
   a pending expiry is never mistaken for a stuck escrow.

*ASIN-HHC — third-party, independent, MIT. Can't be bought out. Can be bought from.*
