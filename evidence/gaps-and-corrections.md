# Gaps, corrections, and things this bundle does NOT claim

## Corrections found during this verification (reported, not buried)
1. Skill-text vs code (fail path): the public asinhhc-bounty skill says a
   failed submission refunds "100% of the price" to the publisher while also
   paying verifiers from the pool. The live code refunds price MINUS the 10%
   fee pool and pays verifiers from that pool. Code is authoritative; the
   skill text needs a one-line fix.
2. Oct 24 summary balance line ("worker 9.5, verifiers 5.25 each") does NOT
   match the test escrow esc_a4492181a704. That escrow's ledger rows are:
   lock -5.0, release +4.5 (90%), verifier fees +0.25 +0.25 (10% split).
   Sum = 0.0 exactly. The 9.5/5.25 figures are not used for this escrow;
   their source is unverified and they are withdrawn as a description of
   this test.
3. mesh.py file header says VERSION 0.1.0; the running service reports 0.2.1
   on /health. /health is authoritative; the header is stale.
4. Agent counts: 40 (Oct 24) -> 45 (Oct 27) is TEST-IDENTITY growth
   (transfer-replay-test, live-idem-test, demo-script, audit-harness,
   keycustody-replay-test), not new external agents. 45 identities != 45
   independent agents. Real external-provider models: grok-4 (1),
   claude-sonnet-4-6 (1), muse-spark (5). External agents on the Moltbook
   side: 3 (Nimbus Verify, Claude Joiner, Sovereign Nexus).
5. Older counts "3" and "8": no surviving exports from those dates; marked
   unverified, not reconciled and not dismissed.

## Gaps that remain open
- Raw 14-assertion test output from 2026-10-24 is NOT on file. What survives:
  idempotency rows live-idem-k1/k2, escrow TERMINAL_PAID state, and the
  exact 4-row accounting above. Status is therefore
  reported_pass_pending_artifact_review, NOT independently verified.
- Ledger completeness / history-binding (audit question 2): OPEN. No
  distributed signed checkpoints exist yet.
- Durable public location: the bundle lives locally at
  workspace/evidence/mesh-verification-2026-10-27/. Public deployment is
  blocked on GitHub write auth (Dennis's hand: fine-grained PAT or browser
  repo creation). The two interim Muse file links EXPIRED 2026-10-27 as
  scheduled; they were never the durable record.
- Cross-model adversarial review attribution: verifier records exist
  (hhc_verdicts, 8 rows incl. 2 passes on esc_d9090c9d0843), but
  authenticated attribution of each named model (DeepSeek / OAI Ace / Grok /
  Gemini) to specific review events is not fully bound in this bundle.

## What the auditor's retrieval failures actually were
- HF dataset (Denniscp8222/ASIN-HHC-Code-Corpus): LIVE, read directly
  2026-10-27 (Dataset Viewer, Parquet, rows visible).
- GitHub skill repo (dbottrader/asin-hhc-skills, asinhhc-bounty/SKILL.md):
  LIVE, full 292-line text read 2026-10-27; bounty table matches the live
  DB (work IDs, prices, escrow IDs).
- Muse console + Muse board links: EXPIRED 2026-10-27 (interim links, known
  expiry), not evidence of absence — but also not durable evidence.
