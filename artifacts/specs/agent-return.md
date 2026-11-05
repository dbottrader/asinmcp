# CP8-AGENT-RETURN-v1 — agent return envelope

The fleet return standard for ASIN-HHC/CP8 delegated work, adopted from the
frozen protocol `CP8_PARALLEL_AGENT_HANDOFF_2026-08-17.md`
(SHA-256 `3ffb47b3ebfbd8cade9c60437d6828aaa63ce8da1f319b74df1f2c4a7ac28b9e`;
receipt `CP8-INF8-HANDOFF-RECEIPT-v1`, 2026-08-17).

Every delegated seat — GrokAce, Kimi, OAI Ace, subagents, browser tasks —
returns its work in this envelope: what it **observed** (with source,
method, and a T0–T4 timestamp class), what it **tested** (PASS/FAIL/BLOCKED
with evidence), the **contradictions** it preserved (never resolved by
agent majority vote), what remains **unverified** (with the exact missing
evidence), its **proposals**, one smallest reversible next action, and a
**promotion** gate state (HOLD|E1|E2|E3) that the coordinator must earn at
intake — a self-declared level never earns itself. A prose-only return is
unverified by definition.

- Schema (JSON Schema, draft 2020-12):
  [agent-return-envelope.schema.json](agent-return-envelope.schema.json)
- The envelope is the return half of the INF8 loop
  (FREEZE → DELEGATE → CHALLENGE → RECONCILE → PATCH → VERIFY → RECEIPT →
  PROMOTE/HOLD), capped at three challenge/repair passes per version
  before HOLD and human review.
- Companion standard: the [asin-hhc:receipt schema](asin-hhc-receipt.schema.json)
  is the settlement-evidence half; this envelope is the agent-work half.
