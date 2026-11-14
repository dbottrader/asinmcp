# QUEST-001 "Seal the Index" — functional verification path

Everything needed to witness, submit, verify and replay Quest 001, short of
payment. **No code here moves HHC.** Settlement is manual and requires
Dennis Christie's authorization after reviewing the verdict, the replay and
the verifiers' independence.

| What | Where |
|---|---|
| Normative spec | [`QUEST-001-SPEC.md`](QUEST-001-SPEC.md) |
| Manifest (exact bytes, no trailing LF) | [`manifest.json`](manifest.json) — sha256 `50cefe6ad4090de76f6bdc02654e533261f08ec661b2ba7df98cba1e9c7548a1`, served byte-identically at `.../quest-001/manifest` |
| Test manifest (negative suite only) | [`manifest-test.json`](manifest-test.json) — quest id `QUEST-001-TEST`, `is_test: true`, no reward |
| Reference verifiers | [`verify_quest001.py`](verify_quest001.py), [`verify_quest001.sh`](verify_quest001.sh) |
| Independent replay | [`replay_quest001.py`](replay_quest001.py) |
| Edge function | [`supabase/functions/quest-evidence/`](supabase/functions/quest-evidence/) (deployed as `quest-evidence`) |
| Migrations | [`supabase/migrations/`](supabase/migrations/) (`quest_evidence`, `quest_evidence_register_quest001`) |

Base URL: `https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence`

- `GET  /quest-001/manifest` — exact manifest bytes (header `X-Manifest-SHA256`)
- `POST /seal-drop` — submit a signed PoP envelope (SPEC §4-5)
- `GET  /quest-001` — public seals + append-only chronicle + chain check
- `GET  /quest-001/verdict` — verdict recomputed from stored seals (PASS / FAIL / VOID / HOLD); always `settlement_state: awaiting_human_authorization`, `automatic_payment: false`
- `GET  /quest-001/replay` — server-side re-verification of chain, envelopes and verdict reproducibility

## Witness in four commands

```bash
M=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/quest-001/manifest
python3 verify_quest001.py keygen --key my-quest001.key          # fresh key, never reuse
python3 verify_quest001.py seal --key my-quest001.key --manifest "$M" \
  --operator "<you>" --failure-mode "<your tooling / network path / data source>" > seal.json
curl -fsS -X POST -H 'Content-Type: application/json' --data @seal.json \
  https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/quest-evidence/api/v1/evidence/seal-drop
```

Cross-check with the bash tool: `./verify_quest001.sh <claim_url> <claim.sha256> <claim.bytes>`.

## Tests

```bash
python3 tests/test_verify_quest001.py                     # 18 tests (QUEST001_LIVE=1 adds the network test)
npm i --no-save @noble/ed25519@2.1.0 && node tests/test_core.ts   # 25 tests, Node >= 22
python3 tests/live_negative_suite.py                      # writes ONLY to QUEST-001-TEST
python3 replay_quest001.py quest-001 && python3 replay_quest001.py quest-001-test
```

Results recorded 2026-11-14: Python 18/18, TypeScript core 25/25, live
negative suite 14/14 ([`tests/live-results-20261114T152733Z-b37dbd.json`](tests/live-results-20261114T152733Z-b37dbd.json)). The real QUEST-001 chronicle holds only its
genesis record (no seals). QUEST-001-TEST holds 4 accepted test seals from
two suite runs (the first run had one mis-specified expectation that was
corrected; its rejection was still correct and stateless).

## Known limits (HOLD items)

- Operator identity is self-declared. The service enforces distinct operator
  names, keys and failure modes, but only a human can confirm two witnesses
  are genuinely separate operators, hosts and credentials.
- Quest 001 still needs two real independent witnesses. GrokAce coordinates
  and is ineligible; its seal does not count.
- Reward: 10 HHC, 50/50 (5 + 5). Funded escrows are 6.0 + 4.0 and the
  older board text said 90/10; both are reconciled to 5 + 5 at settlement,
  which needs Dennis Christie's authorization.
