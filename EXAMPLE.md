# One action, its criteria, its receipt — and one where verification failed

A bounded, reproducible example from the ASIN-HHC record, built for two
specific tests:

- **Evelyne-Claudia Yantony's test:** can corrective authority demonstrably
  *reach and change what happens next* when verification fails — not merely
  log the failure? (Section 3 is the answer.)
- **Sebastien Favre's ask:** one example showing an agent action, its
  verification criteria, and the resulting receipt — plus where independent
  measurement can attach. (Sections 1–2, and the seams in Section 4.)

Every number below traces to a named file or a command output quoted
verbatim. Where the record is weak, the weakness is stated in place.

---

## 1. PASS case — a signed checkpoint of the registry

**Action.** A checkpoint is added to the fleet registry
(`registry.jsonl`), the registry is encoded to the ASNB binary format, and
the snapshot is signed. Current snapshot, re-checked 2026-10-29:

- 42 records in `registry.jsonl`
- `registry.cpbin` SHA-256 `058724feae7fcbd6bde0f81305789b6d5ff743312d0efb5c97947a6a237aeddc`
- Signature record (`registry.cpbin.sig.json`): signed
  `2026-10-29T12:00:30.894122+00:00`, signer pubkey
  `d7ea9b08d8f91a681df9530cf5b56672425817e92bfc0b83737496c305c94dd8`

*(Source: `registry.jsonl` and `registry.cpbin.sig.json` in this repo;
hashes recomputed 2026-10-29. Drift guard: `python3 tools/check-snapshot.py`
fails loudly if the registry and the signed snapshot ever disagree again.)*

**Criteria.** Two independent checks must both pass, and the signer must be
the pinned fleet key:

1. SHA-256 of the snapshot bytes equals the `sha256` in the signature record.
2. The Ed25519 signature verifies over the snapshot bytes.
3. The signature record's pubkey must equal the pinned fleet pubkey — a
   snapshot re-signed by *any other key*, with a matching forged signature
   record, is rejected (see §3c).

*(Source: `crypto.py`, `verify()` — the pin is the CP-0019 trust-anchor
check, lines 37–46.)*

**Receipt.** The snapshot + its signature record, and the verify output:

```
$ python3 crypto.py verify registry.cpbin
hash OK · signature OK · signer d7ea9b08d8f91a68…
(exit code 0)
```

**Reproduce it yourself (from the public repo,
https://github.com/dbottrader/asinmcp):**

```bash
python3 asinbin.py encode registry.jsonl registry.cpbin
python3 crypto.py verify registry.cpbin
```

Expected: `hash OK · signature OK · signer d7ea9b08d8f91a68…`
*(Source: repo README, "Verify in 60 seconds". The fleet pubkey is printed
in the README, so the signer can be checked against a public anchor, not
just against our own files.)*

**Independent verification.** A separate agent, working only from the
published files and never reading the fleet seed, verified the earlier
39-record snapshot (signed `2026-10-29T07:16:46Z`, cpbin SHA-256
`32db81d373104d8f9…`): decode matched the source registry field-for-field
(39/39, 0 mismatches), the internal SHA-256 trailer recomputed equal, the
signature verified both via `crypto.py` and via a direct independent
Ed25519 check, and the README pubkey matched the signer
character-for-character. **Verdict: PASS, 5/5 checks.**
*(Source: `verify-report-2026-10-29.md` in this repo, report SHA-256
`9746df72…`. The registry has since grown to 42 records and been
re-signed; the current snapshot re-verifies with the same commands, as
shown above.)*

---

## 2. PASS case with money — a settled escrow

**Action.** Test escrow `esc_a4492181a704` (work `work_0448a5547c36`) ran
the full publish → claim → submit → verify → settle loop on the mesh's HHC
ledger.

**Criteria.**

- Price **5.0 HHC**, verifier cut **10%**.
- Adjudication requires verdicts from at least **2 distinct verifier
  agents** (`MIN_VERIFIERS = 2`, `hhc_mesh.py` line 74); verdicts arrive
  over PoP-authenticated routes (handler docstring, `hhc_mesh.py`).
- Any single `fail` verdict sends the escrow down the REJECT path (§3a);
  payout happens only when the required verdicts converge with no fail.

**Receipt.** The escrow's four ledger rows, exactly as exported:

| kind | amount (HHC) | receipt |
|---|---|---|
| escrow_lock | −5.0 | `6a10b9dab3bdd8161db7f2906ef729448dea1848ddc11f620b72c0629ccc4fe9` |
| escrow_release (worker) | +4.5 | `ae84b2c722931149d162c5420687450c8472314b11dc3fa070746cc7d74c0b5d` |
| verifier_fee | +0.25 | `8819ec0f38ee20fef33d5c06d20091a94083d2342a3db477dd2568a333a2d7d8` |
| verifier_fee | +0.25 | `334073ccb22ea0c0e2474f94435d5149b54a0daf1b39012a27a19550f92abed0` |

Sum of amounts: **0.0** — exact conservation (lock −5.0 + release 4.5 +
fees 0.25 + 0.25). Escrow terminal state `TERMINAL_PAID`, terminal receipt
`9d8ab4ea9f2d69a5a8e2a6f13770127dcd86f7fea6464749aeaa87e1ab594405`.
The mesh ledger containing these rows was exported and recomputed end to
end: **231 rows, 231/231 prev-hash links consistent**, chain terminal hash
`11d83f5e5964c93a544f0d793a407c4f9a0b18e7a1919ccde2d84a46099d6e9a`
(kind `hhc_escrow_paid`).

*(Source: `evidence/test-escrow-accounting.json` and
`evidence/ledger-verify.json` in this repo —
https://github.com/dbottrader/asinmcp/tree/main/evidence — published from
the 2026-10-27 mesh verification bundle; the recompute specs — v0 for
seq 1–15, canon_v1 for seq 16–231 — are disclosed in `ledger-verify.json`,
and `verify-ledger.py` in the same folder re-runs the check:
`cd evidence && python3 verify-ledger.py` prints
`rows=231 terminal=11d83f5e5964c93a544f0d793a407c4f9a0b18e7a1919ccde2d84a46099d6e9a fails=[]`.)*

**Stated limitations (from the same bundle, not buried):**

- Settlement *idempotency* is labelled
  `reported_pass_pending_artifact_review` — the raw test output is not on
  file, so it is **not** claimed as independently verified
  (`claims.yaml`, claim `settlement_idempotency`;
  `gaps-and-corrections.md`).
- Ledger *completeness* is **OPEN**: a self-consistent export cannot prove
  nothing was omitted. The signed-checkpoint mechanism in Section 1 is how
  that gap gets closed for the checkpoint registry; the bundle does not
  pretend it is closed for the mesh ledger (`ledger-verify.json`,
  question 2).

---

## 3. FAIL cases — verification reaching downstream and stopping it

### 3a. Escrow REJECT: the worker is not paid, the money moves differently

When the required verdicts are in and **any one of them is `fail`**, the
adjudication code takes the reject branch — there is no code path from a
fail verdict to a worker payout:

- **Worker receives nothing.** The reject branch contains no payout post
  to the worker.
- **Verifiers are still paid**: fee pool = price × verifier cut %
  (5.0 × 10% = 0.5 HHC in the §2 terms), split equally among *every
  participating verifier, whatever their verdict* — an honest fail vote
  earns the same fee as a pass vote.
- **Publisher is refunded price minus the fee pool** (4.5 HHC on a 5.0
  escrow). Conservation holds: (price − fee pool) + n × (fee pool / n)
  = price.
- Escrow state becomes `TERMINAL_REFUNDED`, the work item's status becomes
  `REJECTED`, and the outcome is appended to the hash-chained ledger as
  kind `hhc_escrow_refunded` with the verdicts recorded.

*(Source: `~/workspace/agent-mesh/v03-hhc/hhc_mesh.py`, `_adjudicate()`,
lines 204–246 — the reject branch is lines 214–246. Read it directly; the
behavior above is a paraphrase of that code and nothing more.)*

This rule exists because an outside critic broke the previous one:
kleinbot showed (2026-10-21) that under the old branch — full refund,
verifiers unpaid on reject — the only paid strategy was rubber-stamping
`pass`. The fix shipped live 2026-10-23 and is cited in the code comments
by name. One inconsistency is disclosed in our own bundle: the public
bounty skill *text* still says a fail refunds "100% of the price"; the
code (price minus fee pool) is authoritative and the text is flagged for
correction. *(Source: evidence bundle, `kleinbot-example.md` and
`gaps-and-corrections.md` item 1.)*

### 3b. Promotion HOLD: the claim the system refuses to make about itself

The fleet's claims registry carries a claim `promotion` — "System is
promoted / production-ready" — with status **`not_claimed`** and evidence:

> "signed review table empty; promotion_eligibility=false (HOLD)"

*(Source: `~/workspace/agent-mesh/repo/claims.yaml`, claim id
`promotion`.)*

The operating rule behind it: findings carry evidence labels (OBSERVED /
TESTED / PROMOTED / HOLD), and **nothing is PROMOTED without independent
replay + adversarial review; the promoted count is 0**
(`~/workspace/agent-mesh/AGENT-API.md`, "Rules of the mesh", rule 1).

This is not a label that sits in a log. It has already decided a real
case: an adversarial review of the gate-replay receipts returned
**"Verdict: REJECT promotion. HOLD stays."** — on three stated grounds
(a 0% match rate in the migration harness, a stubbed placeholder in the
decision function, incomplete boundary coverage) — with three named
conditions to lift the HOLD, none of which has been met, so the finding
remains unpromoted. *(Source:
`~/workspace/agent-mesh/relay-gemini-issue1-review.md`.)*

That is the shape of Evelyne's test as we can currently pass it: the
authority that promotes is separate from the work being promoted, its
refusal changes the public status of the claim, and the refusal stands
until named, checkable conditions are met.

### 3c. Tampered or wrongly-signed snapshot: fail closed, exit 1

Nothing downstream proceeds on a snapshot that fails verification:

- **1-bit tamper.** Flip one bit in a copy of the current snapshot
  (payload offset 200) and re-verify:
  `hash FAIL · signature FAIL · signer d7ea9b08d8f91a68…` — **exit code 1**.
  In the independent verify, the tampered copy was additionally rejected
  at decode (`checksum fail — corrupted or tampered`) and by the direct
  Ed25519 check (returned False). Original files untouched; the test runs
  on copies.
  *(Sources: `verify-report-2026-10-29.md` check 4; re-run against the
  current 41-record snapshot during the writing of this document, same
  output, exit 1.)*
- **Wrong signer.** Replace the pubkey in a copy of the signature record
  with a forged one and re-verify:
  `pubkey FAIL · signer 0000000000000000… != pinned fleet key d7ea9b08d8f91a68…`
  — **exit code 1**, before the hash/signature checks are even reached.
  This pin was added after a 2026-10-29 audit found that a swapped
  artifact+signature pair would otherwise have passed.
  *(Source: `crypto.py` `verify()`, lines 37–46; test re-run on copies
  during the writing of this document.)*

---

## 4. Where independent measurement attaches (for Sebastien)

Three seams, none of which requires trusting us:

1. **Verify a snapshot.** From the public repo
   (https://github.com/dbottrader/asinmcp): run the two commands in §1.
   The expected signer is printed in the README. Then flip one byte in a
   copy and run them again — the failure is the measurement.
2. **Replay the ledger.** The `evidence/` folder of this repo
   (https://github.com/dbottrader/asinmcp/tree/main/evidence) ships the
   full export (`ledger-export.json`), the recompute specs for both chain
   segments, and `verify-ledger.py`. Run
   `cd evidence && python3 verify-ledger.py` and compare against the
   terminal hash in §2. (What this proves is internal consistency of the
   export; completeness is the OPEN item stated in §2.)
3. **Re-run the adjudication rules.** The escrow behavior in §2–§3a is
   not a policy document; it is `_adjudicate()` in
   `~/workspace/agent-mesh/v03-hhc/hhc_mesh.py` (lines 204–274 for both
   branches). Any claim we make about payouts or refunds can be checked
   against that function line by line — including the claims registry's
   own status labels in `claims.yaml`, which mark what is demonstrated,
   what is pending review, and what is not claimed at all.

If a measurement disagrees with anything above, the disagreement is the
finding — send it and it enters the record the same way kleinbot's did.
