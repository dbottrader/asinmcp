# pstack checks - feat/bnt-0001-verifier-rule

Baseline: `dbottrader/asinmcp` `82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4` (2026-11-16 14:06:33 CT).
Also searched `ASIN-HHC-Agent-Mesh` main `ff94b6358e63d579e6ec64d694a821a9dc13edef` and `docs/hhc-economic-clarification`, and `Holbrook-CP8-HHC` `b012d3a863a579f32f726f9f01c50fed5d5cc9ec`.

| Check | Result | Evidence |
|---|---|---|
| Published skill.md requires 2+ independent verifiers | PASS | https://github.com/dbottrader/ASIN-HHC-Agent-Mesh/blob/main/skill.md : "2+ independent verifiers must converge", worker 90%, verifiers split 10% |
| asinmcp `claim/SKILL.md` already matches 2+ rule | PASS | "Your submission is judged by **at least 2 independent verifiers**" |
| Frozen specs landing already says two verifiers / 90/5/5 | PASS | `artifacts/specs.html` sha256 `f2c3d9eb787478e593370f06b15df62aa5c3021231bcc64a918528a6d2064751` |
| Original single-verifier draft located | FAIL | Not in `/workspace/artifacts/asinhhc-first-bounty/` (missing dir), not in the three repos or Google Drive search. Reconciled draft written as `BNT-0001-SPEC.md`. |
| `verify_full.py` present with recorded hash | FAIL | NOT_FOUND, no hash |
| Bounty `replay.sh` present with recorded hash | FAIL | NOT_FOUND (Ace v1 `replay.sh` is unrelated) |
| `inputs/deploy-manifest.raw` present with recorded hash | FAIL | NOT_FOUND, no hash |
