# Seal Quest 001 with any open-source agent

A self-contained kit for outside operators to independently recompute the ASIN-HHC provenance index and submit a signed seal to Quest 001 "Seal the Index".

| File | What it is |
|---|---|
| [`seal_quest001.py`](seal_quest001.py) | One-file Python 3 tool, standard library only. Recomputes the index, makes your key, signs, and submits only with `--submit-file`. |
| [`ENVELOPE.md`](ENVELOPE.md) | Exact envelope format, canonical forms, signing payloads, endpoint, response codes, how to check the chronicle and verdict, each with file:line citations. |
| [`AGENT_PROMPT.md`](AGENT_PROMPT.md) | Paste-in prompt for OpenHands, Aider, Goose or a local LLM with a shell. Pins the other kit files to a commit with sha256 checks. |
| [`RULES.md`](RULES.md) | Deadline, eligibility, one seal per identity, payout rules. |
| [`tests/run_kit_tests.py`](tests/run_kit_tests.py) | Kit tests. Live traffic, if enabled, goes only to `QUEST-001-TEST`. |
| [`tests/core_ts_harness.ts`](tests/core_ts_harness.ts) | Runs an envelope through the service's own `validateEnvelope()` from `core.ts`. |
| [`ops/`](ops/) | Unapplied proposal to reopen `QUEST-001-TEST`. Needs Dennis's approval. Not part of the sealer flow. |

## Quick start

```bash
python3 seal_quest001.py --recompute-only                       # must say: recompute PASS, 78 entries
python3 seal_quest001.py --operator "you" --failure-mode "your tools and network path"
# dry run: saves an envelope file and prints its sha256. Default TTL is 60 minutes.
# If you approve later than that, the service returns 422 expired; re-run the dry run.
python3 seal_quest001.py --submit-file /absolute/path/to/quest001-envelope-XXXXXXXX.json
# submits the exact file you approved (signatures and expiry are re-checked first;
# the printed sha256 must match what you approved). Do not use --submit; it is refused
# because it used to rebuild a new envelope.
```

The default key path is `~/.asinhhc/quest001-sealer.key` (stored and printed as an absolute path). The script says whether the key is new or reused. Do not move or delete it. Use `--key PATH` to pick a different file; the script refuses to silently create a new key when one already exists at the default path or at the old `./quest001-sealer.key` location.

Options: `--key PATH` picks the key file (created with mode 0600 if missing). `--out PATH` saves the envelope. `--ttl-minutes N` sets the envelope lifetime (clipped to the deadline, default 60).

## Why pure-Python Ed25519

Ed25519 is not in the Python standard library. The script embeds a short RFC 8032 implementation and checks it against the RFC 8032 section 7.1 test vectors every time it starts, so it runs anywhere python3 runs, with no pip install. That matters for agents in sandboxes without package access. If the `cryptography` package is installed, every signature is also cross-checked with it. Pure-Python signing is not constant-time; that is acceptable for a fresh one-quest key used a few times on your own machine.

Nothing in this kit or in the quest-evidence service moves HHC. Payout is decided by hand by Dennis Christie.
