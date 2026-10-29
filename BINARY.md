# ASNB — ASIN Binary (the fleet's own invention)

Ordered by Dennis, 2026-10-29 ~01:33 CDT: "Binary — y'all's own invention — binary."
Implemented same night by Ace: `asinbin.py` (stdlib only), first payload = the CP registry.

## Format v1
- Header: magic `ASNB` (4 bytes) · version `u8 = 1` · record count `u32 LE`
- Record: fixed field order (id, type, name, status, anchor, created); each field = `u16 LE` length + raw UTF-8 bytes. No field names on the wire — the schema is the spec.
- Trailer: SHA-256 (32 bytes) over every preceding byte. Decode verifies magic, version, and checksum before parsing; any tamper or corruption fails closed.

## First artifact
`registry.cpbin` — all 33 CP registry records: **6,932 B JSONL → 4,765 B ASNB (~31% smaller)**,
round-trip decode verified byte-identical, checksum `fca0ac3378e428b4…`.

## Honest limits (per CP-0019)
ASNB is an **encoding, not encryption**. It buys compactness, a format that's ours, and
tamper-evidence via the checksum. It does not hide content from anyone who reads this spec —
and this spec is open. Secrecy lives in keys, never in the format.

## Fleet use
Agents exchange `.cpbin` snapshots machine-to-machine (registry today; lattice index and
mesh state next); the human layer stays JSON/Markdown. Any fleet agent with `asinbin.py`
can read or write it — GrokAce handed the spec 2026-10-29 (feeds CP-0020).
