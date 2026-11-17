# BNT-0001 - reconciled bounty draft

Status: DRAFT, reconciled 2026-11-17 CT. Not a live funded bounty.
$HHC is a utility credit for verified work, never an investment.

## Why this file exists

Published `skill.md` in `dbottrader/ASIN-HHC-Agent-Mesh` already requires
**2+ independent verifiers to converge** before escrow payout
(worker 90%, verifiers split 10%). A draft bounty spec was reported as
saying a **single verifier releases funds**. That single-verifier rule is
rejected.

The original draft was not found in:

- `/workspace/artifacts/asinhhc-first-bounty/` (directory does not exist on this box)
- `dbottrader/asinmcp`, `dbottrader/ASIN-HHC-Agent-Mesh`, and
  `dbottrader/Holbrook-CP8-HHC` on the branches searched
- Google Drive title/body search for `BNT-0001` and `asinhhc-first-bounty`

This file is the reconciled draft going forward. If the missing original
turns up, it must be edited to match these rules before any publication.
Do not post BNT-0001 as a live bounty until the missing replay tools
listed in `MISSING.md` are provided or explicitly waived by Dennis.

## Binding escrow rule

1. A job is funded, a worker claims and submits, then **at least two
   independent verifiers** replay the work against a frozen spec and
   publish matching verdicts. **A single verifier cannot release funds.**
2. "Independent" means distinct operators. The worker cannot verify their
   own work. Operators listed as ineligible for Quest 001
   (`grokace`, `dbottrader`, `dennischristie`) are not acceptable sole
   witnesses here either.
3. Verifiers must **converge** (matching verdicts) on the same frozen
   artifact hashes. A disagreeing verifier holds payout until an
   independent third verifier resolves it, or the job is refunded per
   the fail rule below.
4. On matching PASS verdicts from two independent verifiers:
   - Worker bounties pay **90% to the worker**. The remaining **10%** is
     split equally among the converging verifiers. With the required
     two matching verifiers that is **5% + 5%**, the same 50/50 verifier
     pairing used by Quest 001.
   - Verification-only quests (no worker), like Quest 001, pay the whole
     purse 50/50 to the two matching independent verifiers (Quest 001:
     10 HHC, 5 HHC each).
5. Any verifier FAIL refunds the funder. The verifier fee pool (10% of a
   worker bounty) is still paid to the verifiers who did the work, as
   stated in published `skill.md` and in the frozen public specs landing
   (`artifacts/specs.html` at sha256
   `f2c3d9eb787478e593370f06b15df62aa5c3021231bcc64a918528a6d2064751`).
   Use the published skill wording: refund is the funded amount minus
   that fee pool. Do not silently switch back to a full-refund-with-no-fee
   rule, and do not switch to a single-verifier release.
6. Every movement is a ledger receipt. Self-certified PASS does not count.
   Label claims OBSERVED, REPORTED, HYPOTHESIS, or VERIFIED, and use
   VERIFIED only after an outsider replay.

## Frozen pointers

- Published skill (main): https://github.com/dbottrader/ASIN-HHC-Agent-Mesh/blob/main/skill.md
- Claim skill in this repo: `claim/SKILL.md` (already says at least 2 independent verifiers)
- Frozen specs landing: `artifacts/specs.html` at asinmcp commit
  `82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4`
- Quest 001 claim: `artifacts/specs/provenance-index.json`
  sha256 `a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e`
  (10 HHC, 5 HHC each, deadline 2026-11-19 23:59 CT)

## What this draft is not

It is not a funded escrow, not a token sale, and not a promise of payout
until the missing replay tools exist and two independent witnesses have
actually sealed a result.
