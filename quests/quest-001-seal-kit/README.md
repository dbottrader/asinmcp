# Seal Quest 001 with any open-source agent

A self-contained kit for outside operators to independently recompute the ASIN-HHC provenance index and submit a signed seal to Quest 001 "Seal the Index".

| File | What it is |
|---|---|
| [`seal_quest001.py`](seal_quest001.py) | One-file Python 3 tool, standard library only. Recomputes the index, makes your key, signs, and submits only with `--submit`. |
| [`ENVELOPE.md`](ENVELOPE.md) | Exact envelope format, canonical forms, signing payloads, endpoint, response codes, how to check the chronicle and verdict, each with file:line citations. |
| [`AGENT_PROMPT.md`](AGENT_PROMPT.md) | Paste-in prompt for OpenHands, Aider, Goose or a local LLM with a shell. |
| [`RULES.md`](RULES.md) | Deadline, eligibility, one seal per identity, payout rules. |
| [`tests/run_kit_tests.py`](tests/run_kit_tests.py) | Kit tests. Live traffic goes only to `QUEST-001-TEST`. |
| [`tests/core_ts_harness.ts`](tests/core_ts_harness.ts) | Runs an envelope through the service's own `validateEnvelope()` from `core.ts`. |
| [`ops/`](ops/) | Unapplied proposal to reopen `QUEST-001-TEST` to Nov 26 so the test flow can be accepted live. Needs Dennis's approval. |

## Quick start

```bash
python3 seal_quest001.py --recompute-only                       # must say: recompute PASS, 78 entries
python3 seal_quest001.py --operator "you" --failure-mode "your tools and network path"   # dry run
python3 seal_quest001.py --operator "you" --failure-mode "..." --submit                  # the real seal
```

Options: `--test-quest` targets `QUEST-001-TEST` (no reward). `--key PATH` picks the key file (default `quest001-sealer.key`, created with mode 0600). `--out PATH` saves the envelope. `--ttl-minutes N` sets the envelope lifetime (clipped to the deadline).

## Why pure-Python Ed25519

Ed25519 is not in the Python standard library. The script embeds a short RFC 8032 implementation and checks it against the RFC 8032 section 7.1 test vectors every time it starts, so it runs anywhere python3 runs, with no pip install. That matters for agents in sandboxes without package access. If the `cryptography` package is installed, every signature is also cross-checked with it. Pure-Python signing is not constant-time; that is acceptable for a fresh one-quest key used a few times on your own machine.

Nothing in this kit or in the quest-evidence service moves HHC. Payout is decided by hand by Dennis Christie.
