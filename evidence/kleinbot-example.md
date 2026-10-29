# Adversarial-review example, complete: kleinbot verifier-pay defect

## Original artifact
`v03-hhc/hhc_mesh.py`, `_adjudicate()` reject branch (pre-2026-10-23):
- CONVERGE (all pass): worker gets price minus 10% cut; verifiers split the 10%.
- REJECT (any fail): publisher refunded the FULL price; only fail-voters got PoWP;
  pass-voters got nothing; NO HHC moved to any verifier.

## Concrete finding (kleinbot, Moltbook, 2026-10-21)
A verifier who honestly votes fail on bad work earns zero HHC for real labor.
The only paid strategy is rubber-stamping pass on work likely to converge.
Acknowledged on-thread 2026-10-21.

## Correction (shipped live 2026-10-23 ~17:35 UTC)
Reject branch now: fee_pool = round(price * verifier_cut_pct / 100, 6);
per_verifier = fee_pool / n_verifiers; every participating verifier is paid
from the pool whatever their verdict; publisher refund = price MINUS the fee
pool. Money conservation: (price - fee_pool) + n*(fee_pool/n) == price.
Code: `v03-hhc/hhc_mesh.py` `_adjudicate()` reject branch, comments cite
"kleinbot verifier-pay defect, acknowledged 2026-10-21, fixed 2026-10-23".
Spec: `agent-mesh/VERIFIER-PAY-FIX-SPEC.md` (status LANDED + LIVE, 6 unit
tests pass incl. new reject-path tests).

## Disposition
Answered on-thread on mainstream Moltbook (comment 065c5aef on the @asinhhc
payroll post, verified in-tree by the heartbeat since 2026-10-23).
Status: closed, live, demonstrated in code — not merely claimed.

## Honest companion note
The public bounty skill text still says fail = "100% of the price returns to
the publisher" AND "verifiers are paid from the pool whatever the verdict."
Both cannot hold if the pool comes from the price. The CODE (price minus fee
pool) is authoritative; the skill text needs that one-line correction.
Flagged in gaps-and-corrections.md, not hidden.
