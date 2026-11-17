# BNT-0001 missing replay tools

Checked 2026-11-17 about 02:00 CT (America/Chicago) on this box, in
`dbottrader/asinmcp` at `82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4`, in
`dbottrader/ASIN-HHC-Agent-Mesh` (main `ff94b6358e63d579e6ec64d694a821a9dc13edef`
and branch `docs/hhc-economic-clarification`), and in
`dbottrader/Holbrook-CP8-HHC` at `b012d3a863a579f32f726f9f01c50fed5d5cc9ec`.

| Artifact | Result | Notes |
|---|---|---|
| `verify_full.py` | NOT_FOUND | No file with this name in those trees or under `/workspace` except unrelated searches. No hash recorded, because no bytes were found. |
| `replay.sh` | NOT_FOUND (for this bounty) | The only `replay.sh` on the box is `/workspace/ace-v1/replay.sh`, which belongs to Ace v1, not BNT-0001. No bounty `replay.sh` hash recorded. |
| `inputs/deploy-manifest.raw` | NOT_FOUND | No `deploy-manifest.raw` (or `deploy-manifest*`) in those trees or under `/workspace`. No hash recorded. |
| Original draft under `/workspace/artifacts/asinhhc-first-bounty/` | NOT_FOUND | Directory does not exist on this box. |

Owner: Dennis (`dbottrader`). Next action: provide the three artifacts
with sha256 hashes, or confirm they were never published, before anyone
treats BNT-0001 as a live, replayable bounty.
