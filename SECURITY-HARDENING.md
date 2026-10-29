# Security Hardening Program — CP-0019

Ordered by Dennis, 2026-10-29 ~01:32 CDT: "beef up security even though it's open source —
even obfuscated."

## Principle
**Open code, closed keys.** The system must stay secure when everything except the keys is
public — including after deobfuscation. Obfuscation is camouflage, not a control: assume any
obfuscated blob is decoded within minutes. If reading the code (plain or obfuscated) yields a
secret, that secret is already public. Security comes from cryptography, scope, and
enforcement outside the agent — never from hiding.

## Baseline sweep — 2026-10-29 ~01:33 CDT (CP-0207, verified by Ace)
- Key files all `0600` (both Moltbook credential files, proof-of-pay keys, X tokens); `~/.ssh` `0700`. ✅
- All 8 local services (mesh 8220, HHC 8221, receipt 8211, formation 8100, harmony 8101, bridge 8102, visual 8110, gateway 8230) bind **127.0.0.1 only**. ✅
- Node kit v0.3 zip ships **no** key/wallet/secret files — operators generate their own keys. ✅
- Public trees (asinmolt-node, agent-mesh/repo, publish/): **zero** token/private-key values,
  **zero** long encoded blobs. Word-level hits are key-*handling* code (ed25519, signing) — open by design. ✅

## Rules (fleet-wide)
- **S1 · No secret values in public trees, in ANY encoding** — plaintext, base64, hex, split, or obfuscated. Plaintext + blob scans run before every publish.
- **S2 · Keys live in 0600 files / Secure Vault only.** Kits and repos ship zero keys; every node generates its own.
- **S3 · Localhost binds stay.** Any future public endpoint (Stage C) ships with auth, scoped tokens, and signed checkpoints — never raw mesh ports.
- **S4 · P0-AUTH (CP-0004) is the onboarding gate:** one canonical pinned skill, hash-check before execution, paste = READ only, per-action human go, URL allowlist, enforcement outside the agent. Token-separation test (a social token must fail claim/submit) passes before any public-join push.
- **S5 · Settlement integrity:** exactly-once + atomicity tests with dated receipts (closes Ryan F07); signed reviewer identities (closes F05); bridge concentration named honestly, signed external checkpoints (F08).
- **S6 · Verifier independence:** operator exclusion graph ships before scale (cognitor's open defect) — a verifier must not be able to quietly be the publisher.
- **S7 · Fleet hygiene:** no broad third-party OAuth (Skillzy rule stands); emailed links are human-tapped; passwords vault-only; any credential that ever appeared in an archive gets rotated before reliance (Atomic Bot Telegram bot credential rule).
- **S8 · Obfuscation rule:** obfuscate cosmetics if useful; never rely on it for keys, auth logic, or settlement logic. Reviewers review the deobfuscated truth.

## Owners
Ace: scans, registry, enforcement tests. GrokAce: adversarial review (CP-0004 feeds CP-0019).
Ryan's audit (CP-0202) remains the outside acceptance bar.
