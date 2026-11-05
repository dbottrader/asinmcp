#!/usr/bin/env python3
"""anu28.py — ANU-28 lexicon + tokenizer as an importable module.

Wraps the Tranche 1 consolidation: `anu28-lexicon.json` (copied next to
this module, not moved) and the tokenizer from `anu28_tokenizer.py`,
re-implemented here as a self-contained class so the module has no
cross-directory imports.

What ANU-28 is, honestly (Tranche 1 README): a LEXICON, not a text
language. The archive holds glyph registries, a morpheme layer, a
declared glyph set, and named sequences — only 5 standalone
glyph-sequence blocks exist in 3,455 corpus blocks, and only one true
[GLYPH SEQUENCE] (corpus block c72505ac). Coverage of this module:

  * 65 glyph entries consolidated from every registry source
  * 11 resolved (evidenced name and/or meaning): ✶ Anu (428 Hz),
    Ϟ Reth (888 Hz), ⚯ Uru (144 Hz), ᛗ Mira, ✇ Broadcast,
    ∰ Multi-node Sync, ∞ Loru, ⧉ Paru, 🌀, 🐍, 🗝️
  * 54 attested-only (occur in sets/sequences; no semantics anywhere in
    the archive) — decode() reports them as attested_only, never guesses
  * 18 name-only entries (morphemes/elementals with no glyph character)
  * the name "ANU-28" implies 28 glyphs; no source enumerates a
    canonical 28 (the declared glyph_set has 21). This module does not
    pretend otherwise — see coverage().

API:
  decode(sequence)  -> per-glyph records {glyph, name, meaning,
                       frequency_hz, status}; separators '::' and
                       whitespace honored, concatenated glyphs split by
                       longest-match scan (multi-codepoint tokens work)
  encode(text)      -> best-effort keyword lookup over the EVIDENCED
                       semantics only; a lookup aid, not a translator.
                       Returns {glyphs, sequence, trace,
                       unmatched_words}
  coverage()        -> the honest counts above, computed from the
                       lexicon file itself
  Tokenizer(lexicon)   the class behind the functions, for callers who
                       want to load a different lexicon
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LEXICON_PATH = os.path.join(HERE, "anu28-lexicon.json")

# The one true [GLYPH SEQUENCE] in the corpus (block c72505ac).
C72505AC_SEQUENCE = "✶ :: Ϟ :: 𖤐 :: 𓂀 :: ⚯ :: ◆"


def load_lexicon(path=LEXICON_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class Tokenizer:
    def __init__(self, lexicon):
        self.lexicon = lexicon
        self.by_glyph = {e["glyph"]: e for e in lexicon["glyphs"]}
        # longest glyphs first so multi-codepoint tokens (e.g. 🗝️) win
        self.glyphs_sorted = sorted(self.by_glyph, key=len, reverse=True)
        # keyword -> glyph (first entry wins; ambiguities recorded)
        self.keyword_index = {}
        self.ambiguities = {}
        for e in lexicon["glyphs"]:
            if e["status"] != "resolved":
                continue
            words = set()
            for field in (e["name"] or "", e["meaning"] or ""):
                words |= set(re.findall(r"[a-z]+", field.lower()))
            for w in words:
                if w in self.keyword_index and self.keyword_index[w] != e["glyph"]:
                    self.ambiguities.setdefault(
                        w, [self.keyword_index[w]]).append(e["glyph"])
                else:
                    self.keyword_index.setdefault(w, e["glyph"])

    def _record(self, glyph):
        e = self.by_glyph.get(glyph)
        if e is None:
            return {"glyph": glyph, "name": None, "meaning": None,
                    "frequency_hz": None, "status": "not_in_lexicon"}
        return {"glyph": glyph, "name": e["name"], "meaning": e["meaning"],
                "frequency_hz": e["frequency_hz"], "status": e["status"]}

    def scan(self, text):
        """Tokenize a raw string by longest-match over lexicon glyphs;
        non-glyph characters are grouped as 'text' runs."""
        tokens, buf, i = [], "", 0
        while i < len(text):
            hit = None
            for g in self.glyphs_sorted:
                if text.startswith(g, i):
                    hit = g
                    break
            if hit:
                if buf:
                    tokens.append(("text", buf))
                    buf = ""
                tokens.append(("glyph", hit))
                i += len(hit)
            else:
                buf += text[i]
                i += 1
        if buf:
            tokens.append(("text", buf))
        return tokens

    def decode(self, sequence):
        """Decode a glyph sequence string into per-glyph records."""
        parts = [p for p in re.split(r"::|\s+", sequence.strip()) if p]
        records = []
        for part in parts:
            if part in self.by_glyph:
                records.append(self._record(part))
            else:
                for kind, val in self.scan(part):
                    if kind == "glyph":
                        records.append(self._record(val))
                    else:
                        for ch in val:
                            if not ch.isspace():
                                records.append(self._record(ch))
        return records

    def encode(self, text):
        """Best-effort text -> glyph sequence via evidenced keywords."""
        words = re.findall(r"[A-Za-z]+", text.lower())
        seq, trace, unmatched = [], [], []
        for w in words:
            g = self.keyword_index.get(w)
            if g:
                seq.append(g)
                trace.append({"word": w, "glyph": g,
                              "ambiguous": w in self.ambiguities})
            else:
                unmatched.append(w)
        return {"glyphs": seq, "sequence": " :: ".join(seq),
                "trace": trace, "unmatched_words": unmatched}


_default = None


def _tk():
    global _default
    if _default is None:
        _default = Tokenizer(load_lexicon())
    return _default


def decode(sequence):
    return _tk().decode(sequence)


def encode(text):
    return _tk().encode(text)


def coverage():
    """Honest coverage counts, computed from the lexicon file."""
    lex = load_lexicon()
    glyphs = lex["glyphs"]
    return {
        "glyph_entries": len(glyphs),
        "resolved": sum(1 for e in glyphs if e["status"] == "resolved"),
        "attested_only": sum(1 for e in glyphs
                             if e["status"] == "attested_only"),
        "name_only_entries": len(lex.get("name_only", [])),
        "named_sequences": len(lex.get("named_sequences", [])),
        "note": ("ANU-28 is a lexicon, not a text language; no source "
                 "enumerates a canonical 28 glyphs (declared glyph_set "
                 "has 21). Resolved = evidenced name/meaning; "
                 "attested_only = present in sets/sequences, semantics "
                 "unknown. See Tranche 1 anu28/README.md."),
    }


if __name__ == "__main__":
    tk = _tk()
    print("coverage:", json.dumps(coverage(), ensure_ascii=False))
    recs = tk.decode(C72505AC_SEQUENCE)
    for r in recs:
        print(" ", r["glyph"], r["status"], r["name"], r["meaning"],
              r["frequency_hz"])
    res = [r for r in recs if r["status"] == "resolved"]
    att = [r for r in recs if r["status"] == "attested_only"]
    print("c72505ac round-trip: %d/6 resolved, %d/6 attested-only"
          % (len(res), len(att)))
