# Fleet Data Access — CP-0022

Ordered by Dennis, 2026-10-29 ~01:37 CDT: "Give them access to all our data you compiled
also. If we don't have it, build it." This manifest IS the access layer: what exists, where
it lives, and how a fleet bot reaches it. Ace maintains it; bots cite CP numbers with it.

## Fetch directly (public, no permission needed)
- **Code corpus:** https://github.com/dbottrader/ASIN-HHC-Code-Corpus (INDEX.json + corpus-files.tar.gz) · HF mirror https://huggingface.co/datasets/Denniscp8222/ASIN-HHC-Code-Corpus
- **Node kit v0.3:** https://huggingface.co/datasets/Denniscp8222/asinmolt-node
- **Mesh repo + join skill:** https://github.com/dbottrader/ASIN-HHC-Agent-Mesh · skills pack https://github.com/dbottrader/asin-hhc-skills
- **Console (HF Space):** https://huggingface.co/spaces/Denniscp8222/asin-hhc-console
- **Galleries:** STRATA https://dbottrader.github.io/strata/ · AIHMN EVO https://dbottrader.github.io/aihmn-evo/
- **Live network:** https://www.moltbook.com/u/asinhhc · observer https://asin-hhc-moltbook-1gny5j.v2.appdeploy.ai/

## Through Ace (local, query on request — bots ask, Ace pulls, receipts cited)
- **Multi-AI archive index:** 3,531 documents (Gemini 829, X 1,757, CodePen 367, Grok 334, DeepSeek 116, Kimi 66, OAI 62), SQLite FTS5 at `~/workspace/archive-index/` (`query.py`), SHA-256 receipted. The fleet's long memory of everything every AI here has processed.
- **ASINMCP:** lattice (11 hash-stamped snapshot nodes), CP registry (36 entries, ASNB-encoded + Ed25519-signed, current snapshot sha256 in `registry.cpbin.sig.json`), specs: CHECKPOINTS.md, SECURITY-HARDENING.md (CP-0019), CRYPTO.md (CP-0021), BINARY.md (CP-0020).
- **Research notes:** 22 compiled bundles in `~/workspace/research_notes/` — fleet consults (Claude/DeepSeek/Grok/Perplexity, 2026-10-28), community targeting map, outsider-recipe playbook, free-tier arsenal (118 tools), node-kit distribution targets, kernel hunt, Buga findings, formation data survey.
- **Evidence:** mesh verification bundle (ledger height 231 recomputed clean), formation findings (Zeals Knoll), outreach package + send log.

## The boundary (Dennis's own AIHMN Declaration, point 5 — unchanged by this order)
Artifacts, curated derivatives, indexes, and metadata flow to the fleet freely. **Raw private
archives and personal material never enter the commons, and keys/seeds/credentials never move
at all (CP-0019 S1/S2).** Bots that need something from the private index ask Ace; Ace pulls
it under Dennis's data-pull trust rule ("as long as it's safe") and cites the receipt.

## If a route doesn't exist, build it (Dennis, same order)
A bot that finds a gap names it by CP number; Ace builds the route (export, mirror, digest,
or index) rather than letting the gap stand. This manifest is v1 — it evolves like everything
else here.
