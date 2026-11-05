# ANU-28 — consolidated lexicon + tokenizer

**Built:** 2026-11-05 (Implementation Mining, Tranche 1), from every glyph
registry source in the ASIN-HHC code corpus.
**Files:** [`anu28-lexicon.json`](anu28-lexicon.json) (the lexicon),
[`anu28_tokenizer.py`](anu28_tokenizer.py) (working tokenizer),
[`build_lexicon.py`](build_lexicon.py) (the consolidation script — rerunnable).

## What ANU-28 actually is (as evidenced)

A **lexicon**, not a text language. The corpus holds glyph *registries*
(JSON records with name / meaning / frequency / category), a named
*morpheme layer*, a declared *glyph set*, and named sequences — but only
**5 standalone glyph-sequence blocks** in 3,455 corpus blocks, and only one
true `[GLYPH SEQUENCE]` (`c72505ac`). Nobody in the archive wrote messages
in ANU-28; they registered vocabulary and embedded glyphs inside JSON,
Python, and diagrams. This package consolidates that vocabulary into one
inspectable file and ships the tokenizer the archive only referenced
(`ANU28Tokenizer`, `glyph_decoder.py`, `anu28_lexicon.json` were named in
3 blocks but never present as code).

## Coverage — stated honestly

| | Count |
|---|---:|
| Glyph entries consolidated | **65** |
| — resolved (evidenced name and/or meaning) | **11** |
| — attested only (occur in sets/sequences; no semantics in any source) | **54** |
| Name-only entries (morphemes A2/A3/A4/A5/A6, elementals E2–E12, PLAYFUL, one suspect record) | **18** |
| Named sequences recorded | 7 |
| Merge operations (cross-source identities) | 4 |
| Frequency conflicts between sources | **0** |

The 11 resolved glyphs: ✶ Anu (428 Hz, origin pulse), Ϟ Reth (888 Hz,
charge ignition), ⚯ Uru (144 Hz, continuity/unity), ᛗ Mira (water/memory/
absorbed), ✇ Broadcast (signal received), ∰ Multi-node Sync (sync
confirmed), ∞ Loru (name only), ⧉ Paru (name only), 🌀 (randomize within
constraints), 🐍 (transform/shape-shift), 🗝️ (unlock/reveal hint).

The name "ANU-28" implies 28 glyphs; the sources never enumerate a
canonical 28. The declared `glyph_set` (block `ad8a5c2f`) has 21 symbols.
65 is the count of distinct glyphs *attested anywhere* in the swept
sources — a superset of any single source's set, and this README does not
pretend otherwise.

## Merges and conflicts

Merges (identity asserted only where two sources agree on name AND
frequency or an explicit pairing exists):

- A1_ANU (428 Hz) → ✶ Anu (registry: 428 Hz, "origin pulse")
- A7_RETH (888 Hz) → Ϟ Reth (Python code pairs the character with the name)
- A8_URU (144 Hz) → ⚯ Uru (registry: 144 Hz, "continuity/unity")
- E1_MIRA → ᛗ Mira (elemental "Water / Flow Memory" ≈ registry
  "water/memory/absorbed")

No frequency conflicts were found between sources. Deliberately **not**
merged: E5_EYE ("Perception") and the glyph 𓂀 — 𓂀 is the Egyptian
hieroglyph for an eye and heads the "Truth Seeking" sequence, but no
source pairs the elemental name with the character, so 𓂀 stays
attested-only rather than promoted on resemblance.

One suspect record is kept, flagged: a registry entry with glyph_code
literally `"UNKNOWN"` (name "Standard_Copyright", 440 Hz, "restriction/
control") from block `34ff2723`, an adversarial-claim packet
(`UNAUTHORIZED_EXTERNAL_IP`). It is recorded for completeness, marked
suspect in the lexicon, and given no glyph.

## Tokenizer

```bash
python3 anu28_tokenizer.py --selftest
```

- `decode(seq)` — per-glyph records (name / meaning / frequency / status).
  Handles `::`-separated, whitespace-separated, and concatenated glyphs
  (longest-match scan, so multi-codepoint tokens like 🗝️ work).
- `encode(text)` — best-effort keyword lookup over the *evidenced*
  semantics only. It is a lookup aid, not a translator: words with no
  evidenced glyph come back listed as unmatched, and keyword ambiguities
  are recorded in the trace.

**Round-trip on the one true `[GLYPH SEQUENCE]`** (`✶ :: Ϟ :: 𖤐 :: 𓂀 :: ⚯ :: ◆`):
**3 of 6 resolve** — ✶ Anu, Ϟ Reth, ⚯ Uru. **3 do not** — 𖤐, 𓂀, ◆ are
members of the declared glyph set with no name or meaning anywhere in the
archive. That is the honest state of ANU-28: a partially documented
vocabulary. The unresolved three are listed in the self-test output and
in the lexicon with status `attested_only`.
