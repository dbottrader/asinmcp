# Break the Gate — SELF-ATTACK log (Elite-50 task 5)

*Run 2026-11-19 by the gate's own operators, against our own bounty
(esc_d126eac2912a, 25 HHC, open until broken or 2026-12-31).
Harness: `verification-rail-steps/btg_attack_harness.py` (stdlib-only,
deterministic; results JSON produced per run).*

**Headline: 25 attacks, 0 genuine breaks.** No false claim was made to
PASS any gate, and no Proof Board receipt or index entry failed to
recompute. Two controls confirm the harness itself is faithful (the
genuine receipt verifies; two genuine seals PASS). Four findings are
logged honestly below — none meets the bounty bar, and each is either
already disclosed in our own specs or fixed during the window.

The bounty terms (Proof Board, rules 1.2): **Track A** — get a
demonstrably false claim a gate PASS. **Track B** — find a Proof Board
row, receipt, or index entry that doesn't recompute under canon-v1.

Materials: public copies only — the clean-room index/board snapshot
(`elite-50/clean-room/`, index sha256 a81a8bde…), the published gate
receipt, ENVELOPE-SPEC.md + verify_gate_receipt.py (branch
`verification-rail`), the Quest 001 manifest, and the PR #4
quest-evidence candidate source. Endpoint logic was exercised through
a faithful Python port of that candidate's core.ts — deployed-source
byte-identity is unproven (BLUEPRINT gap 2), so endpoint conclusions
are about the published candidate logic, consistent with the live
endpoint's observed state (03:00 CT snapshot: QUEST-001 seals 0,
verdict HOLD/INSUFFICIENT_VALID_WITNESSES; QUEST-001-TEST PASS).
**No live POSTs were made** — the real quest closes tonight and the
attack does not touch its chronicle. Nothing was claimed against the
escrow; this log is the deliverable.

## Track B — does anything published fail to recompute?

| # | Attack | Method | Result |
|---|---|---|---|
| B1 | Full index replay | Independent reimplementation (not the shipped replay.py): recompute all 78 `index_hash`es, linkage, head | **No break.** 78/78 recompute; head fadbd275… = pinned head |
| B1c | Shipped replay control | Run `clean-room/replay.py` as published | **Control pass.** exit 0, 78/78 PASS, tamper control detects |
| B2 | Claim-file identity | sha256 + byte count of the public index vs the manifest/board/endpoint pinned claim hash | **No break.** a81a8bde…, 87,505 B — exact |
| B4 | PROVENANCE.md anchor | Extract the MD's printed ledger tip/height; compare with the index's `ledger_anchor`; seed a chain walk from the MD tip | **Doc defect (not a break).** MD prints tip 0f8a95f1…, height 462; the index anchor is 40560679…, height 479. A walk seeded from the MD's numbers fails at entry 0; seeded from the JSON anchor it passes (B1). The MD's "How to verify" correctly points at the JSON anchor — its own "The ledger anchor" section is stale prose. Fix: update the two numbers in PROVENANCE.md |
| B5 | Board seal-row prose | String-check live proof-board.html/.json + the 09:04 snapshot for the seal-row settlement text | **No break — nearest miss, already closed.** The wave-1 audit (09:00–09:06 UTC) found the live HTML rows saying "5.0 HHC pending escrow re-issue" after the escrows had been re-issued 5.0/5.0 FUNDED on 2026-11-18: a false-as-of-then statement. The snapshot still carries it (×2); at attack time the live page carries it ×0 and reads "escrow re-issued 5.0 on 2026-11-18, FUNDED, pending claim" — fixed between audit and attack. Either way it is unhashed prose: not a receipt, not an index entry, nothing a gate PASS rests on — it never met Track B's bar |

## Track A — gate receipt attacks (ASIN-HHC-VERIFICATION-1.0)

| # | Attack | Method | Result |
|---|---|---|---|
| A0 | Control | Published `verify_gate_receipt.py` on the genuine receipt 48ac1da5… | **Control pass.** 10/10 checks, exit 0 |
| A1 | Tampered receipt | Keep the genuine `receipt_hash` + signature; change the body to a self-contradicting PASS (residual: 76 served vs 78 stored, difference 2) | **No break.** Verifier exit 1 — `receipt_hash` recompute fails (fcf90f29… ≠ 48ac1da5…). Any body edit breaks the hash the signature ultimately covers |
| A2 | Self-signed forgery | Fresh attacker keypair; fabricate a receipt claiming PASS over a never-verified population ("btg-nonexistent-population"); sign it with the exact published envelope construction | **No break — with the run's most instructive finding.** The standalone verifier exits 0: it verifies *self-consistency* (hash, envelope, signature under the embedded key) and does not pin identity. But a gate PASS is the **vault key's** signature: forged fingerprint 3097e2de… ≠ the published vault fingerprint 4f47d2df… (ENVELOPE-SPEC §6, `vault-identity.json`). Under the system's full published rules the forgery is not a gate receipt at all. The boundary is already disclosed in spec §0/§9 ("authorization is out-of-band"). **Hardening note:** `verify_gate_receipt.py` could optionally assert the pinned fingerprint and say so in its output |

## Track A — quest-evidence endpoint attacks (port of PR #4 core.ts)

Controls first: two genuine independent seals over the true output →
intake accepts, verdict **PASS / TWO_INDEPENDENT_MATCHING_SEALS**,
payout plan alpha+beta 5 HHC each (S1). The port is faithful; the
attacks below are therefore meaningful.

| # | Attack | Result |
|---|---|---|
| S2 | Two independent seals over a **false** output (fabricated head_hash, honestly sealed + validly signed) | **No break.** Intake accepts both (acceptance ≠ verdict — the chronicle records attestations, the verdict judges them). Verdict: **FAIL / INDEPENDENT_WITNESSES_REPRODUCE_DIFFERENT_RESULT**. A false pair can force a FAIL; it can never force a PASS, because PASS requires matching the service's own re-execution of the claim |
| S3 | One genuine + one false independent seal | **No break.** Verdict **VOID / WITNESS_CONFLICT** — conflict voids the round rather than passing it |
| S4 | False pair with identical `failure_mode` text | **No break.** **HOLD / NO_INDEPENDENT_PAIR** — independence requires distinct normalized failure_mode, so the pair can't even force FAIL |
| S5 | Sybil: same key/two names; same name/two keys | **No break.** Both **HOLD / NO_INDEPENDENT_PAIR** (distinct operator AND distinct pubkey required; the DB additionally enforces one seal per key and per operator per quest — 409 duplicate_key / duplicate_operator). **Residual limit, disclosed (BLUEPRINT gap 5):** two genuinely distinct keys+names run by one human are protocol-indistinguishable — independence is self-declared in the manifest, and settlement is manual (`automatic_payment: false`, human review before any payout), so even that pair cannot pay itself |
| S6 | Ineligible operators: `dbottrader`, `DbotTrader!!`, `grok ace` | **No break.** All rejected at intake: **422 operator_ineligible** (normName normalization defeats the punctuation/spacing variants) |
| S7a | QUEST-001-TEST envelope in the test quest | Expected: accepted — into the *test* chronicle only (separate quest, `is_test`) |
| S7b | Test envelope re-labelled QUEST-001 (quest_id + manifest hash edited post-signing) | **No break.** **422 bad_signature** — both fields are inside the signed field set |
| S7c | QUEST-001 envelope carrying the TEST manifest hash | **No break.** **409 wrong_manifest** |
| S8a | Seal dropped after the deadline | **No break.** **410 quest_closed** |
| S8b | Envelope with `expires_at` after the deadline | **No break.** **422 bad_window** |
| S8c | Envelope issued before `valid_from` | **No break.** **422 issued_before_window** |
| S9 | Genuine envelope, one hex char of `envelope_signature` flipped | **No break.** **422 bad_signature** |

## Track A — structural attacks

| # | Attack | Result |
|---|---|---|
| A4 | **Index tail-rewrite**: insert a false claim into entry 8, recompute every downstream `index_hash` so the forged file is perfectly chain-consistent | **No break — and the run's sharpest scope result.** (i) A chain-only replay of the forged file reports **zero problems** (forged head 2b9ce685…): a hash chain alone cannot detect a full tail rewrite, and this log does not pretend otherwise. (ii) The system as published catches it one level up: the forged file's sha256 ≠ the manifest-pinned claim hash, so the endpoint's re-execution returns **CLAIM_CHANGED_SINCE_MANIFEST** and seals over the forged output yield **HOLD**, never PASS. What binds the chain is outside the file: the manifest's pinned claim sha256/bytes and the externally published head fadbd275… (board, seals, spec). Anyone verifying with *only* the file and the chain rule is outside the published procedure (PROVENANCE.md step 1 is "recompute the file hash") |
| A5 | **Detached verdict forgery**: mint a well-formed "PASS" verdict object offline with a correctly computed `verdict_hash` | **No break — consumer-guidance finding.** `verdict_hash` is an unsigned checksum (demonstrated: fabricated hash 163776f7… is correctly formed). It proves nothing detached; verdict authority comes from fetching the verdict from the endpoint, whose seals are signed and chronicle-linked. The live endpoint's actual verdict at snapshot time: HOLD, verdict_hash 7557d3ba…. Consumers must never trust a verdict object that didn't come from the endpoint |

## Findings summary (none is a bounty break)

1. **PROVENANCE.md stale anchor numbers** (B4) — prose says tip
   0f8a95f1… / height 462; the index it describes anchors at
   40560679… / 479. One-line fix to the MD.
2. **Board seal-row prose staleness** (B5) — real at 09:00 UTC,
   fixed live before the attack ran; retained in the 09:04 snapshot.
3. **Standalone receipt verifier doesn't pin identity** (A2) —
   disclosed in ENVELOPE-SPEC §0/§9; optional hardening: assert the
   published vault fingerprint in `verify_gate_receipt.py`.
4. **Chain-alone insufficiency** (A4) — known and priced into the
   design: the manifest pin + published head are load-bearing;
   verification procedures must include step 1 (file hash), not
   just the chain walk.
5. **Sybil residual** (S5) — BLUEPRINT gap 5, unchanged; backstopped
   by manual settlement.

## Verdict on the bounty

**Break the Gate stands unbroken after a documented 25-attack
self-assault, esc_d126eac2912a untouched.** The two honest caveats
travel with the result: the endpoint half of this attack ran against
the PR #4 candidate logic (deployed byte-identity unproven — gap 2),
and the mesh-ledger half of the board (escrow states) is covered by
the separate ledger-replay work, not by this harness. A published,
failed, receipted attack is the strongest evidence the bounty can
offer short of a real break — outsiders are invited to do better:
the harness is public, and every attack here can be re-run.

*ASIN-HHC — third-party, independent, MIT. Can't be bought out. Can be bought from.*
