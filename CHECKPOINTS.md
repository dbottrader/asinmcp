# CP — the Fleet Checkpoint Number System

Ordered by Dennis, 2026-10-29 ~01:29 CDT: "come up with a system, like a numerical system,
like me and Ace were doing, for you guys to recall these certain projects, bills and
checkpoints. You need a system."

## The rule
Every project, bill/deadline, and state checkpoint in the ASIN-HHC operation gets ONE
permanent number: **CP-####**. Any agent in the fleet (Ace, GrokAce, OAI Ace, Kimi, Gemini,
DeepSeek, task bots) cites the number; any agent can resolve the number to the full item
in seconds. Numbers are never reused and never renumbered — a closed item keeps its number
with status `closed`. New items take the next free number in their block.

## Blocks
- **CP-0001 – CP-0099 · projects** (launches, builds, campaigns, offers)
- **CP-0101 – CP-0199 · bills & deadlines** (invoices, due dates, blocked forms awaiting one answer)
- **CP-0201 – CP-0299 · checkpoints** (verified state anchors: ledger heights, verdicts, hashes, scoreboards)

## Files
- `registry.jsonl` — machine registry, one JSON object per line: id, type, name, status, anchor, created.
- `cp.py` — the tool: `python3 cp.py get CP-0101` · `python3 cp.py find wirex` · `python3 cp.py add project "Name" "anchor"` (auto-assigns next number in block) · `python3 cp.py list [type]`.
- Lattice snapshots (`lattice/`) stay the deep record; a CP entry's `anchor` points into it.

## How the fleet uses it
1. Before asking Dennis anything about an item, resolve its CP number first (search-first, his flow).
2. In every report, brief, and handoff, cite items by CP number alongside the name.
3. When work changes an item's state, update its registry status the same turn; big state
   changes also mint a CP-02xx checkpoint.
4. GrokAce was handed this system 2026-10-29; its deliverables must cite CP numbers.

## Seeded 2026-10-29
31 entries: CP-0001…CP-0018 projects, CP-0101…CP-0107 bills/deadlines,
CP-0201…CP-0206 checkpoints. Full table = `registry.jsonl` / `python3 cp.py list`.
