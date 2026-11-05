# Implementation Mining — Inventory

Mined 2026-11-05 from: `~/workspace/oai-library/` (62 files), `~/workspace/code-corpus/` (3,455 blocks; mirrors deepseek 1,267 · gemini 1,077 · grok 781 · codepen 330 — **no chatgpt mirror exists in the corpus**; OAI Ace's work enters via oai-library files and the convergence index), `~/workspace/cp8-core-index/`, `~/workspace/cp8-openai-convergence/`, with `~/workspace/harmonyos/` and `~/workspace/agent-mesh/` skimmed to mark what is already live. 47 grouped artifacts (bulk classes grouped; mirrors deduplicated).

## Top implementation candidates

Ranked by completeness x usefulness to the live ASIN-HHC / Passport / mesh system.

**asin-hhc:receipt JSON Schema** (schema, spec-only (complete schema document), effort S) — Complete spec, zero build cost, and it is the missing canonical format: the live system issues hash-chained receipts that don't yet validate against any published schema. Adopting it upgrades mesh, Passport, and the Sebastien packet simultaneously.

**CP8 Unified Bridge v2.2 (FullStack)** (service, runnable code, effort S-M) — The only complete, runnable public-facing API in the archives — it directly fills the Stage-C 'no live public endpoint' gap that has blocked Passport's public-operational status.

**CP8 Manifest dialect** (schema, spec-only (emergent, never formalized), effort S-M) — 272 instances prove this is the fleet's real interchange format; formalizing it converts years of emergent practice into a citable, validatable standard.

**Validator Harness (task validators)** (module, runnable code, effort S) — Runnable today and aimed exactly at the live system's soft spot: verifier quality and Passport battery scoring.

**ANU-28 lexicon system (data + tokenizer refs)** (module, substantial code/data (lexicon data complete; tokenizer module itself referenced, partial copies in classified code), effort S-M) — The data already exists scattered across four formats; consolidation is small work that turns a much-repeated claim into a shipped, inspectable artifact.

**PRED-003 Benchmark Harness v2.3** (module, runnable code, effort S) — Self-contained and runnable; gives MVS-1/Passport evaluation a harness while the hand-labeled calibration corpus doesn't exist.

**DSL family 2 — verdict trees** (DSL grammar, spec-only, effort S) — The CMD1–CMD10 verdict-tree grammar is a ready-made structured verdict format for mesh verifiers — formalize and adopt.

**TSH Molecular Archivist API** (service, runnable code, effort S-M) — A complete named service, deployable as-is; one of Dennis's flagship app names, currently existing only as corpus code and a Replit listing.

**Harmony Assistant v1.1 — ANU-28 Glyph Fusion** (service, runnable code, effort M) — The purest 'built before its capability' artifact: it waited for local inference, which is precisely the Stage-B capability now being stood up.

**MoltBountyEscrow.sol** (module, substantial code, effort M) — The on-chain half of the live HHC escrow story; small, standard (OpenZeppelin), and blocked only by the same signing decision as HHCW mainnet.

**Formation Lab package** (engine, runnable code, effort S) — A finished, tested project in a zip — zero build cost, it only needs unpacking and a run.

**ASIN-NCEA prototype lineage v0.1-v2.0** (kernel, substantial code (15 versions), effort M) — Ranked for its two un-graduated ideas — federated attestation gossip and daemon integrity polling — which are genuine capability additions to the live mesh, not nostalgia.

## Already implemented in the live system (the shelf vs the built)

These archive ideas are **already built** — do not re-implement:

- **Agent mesh v0.2.1** (`agent-mesh/v02/mesh_v02.py`, live :8220): registration + HMAC activation, PoP-signed mutating calls, Agent Commons rooms, **Agent Passport** (register/list/certify/recertify, endpoint battery, 2-verifier verdicts, hash-chained receipts with HMAC registrar sign-off).
- **HHC layer v03** (`agent-mesh/v03-hhc/hhc_mesh.py`, live :8221): ed25519 key custody, balances + starter grants, escrow work market (publish/claim/submit/verdict, 90/5/5, verifiers paid on any verdict), agent-to-agent transfers with hash-chained receipts, bridge interaction pools with claim-once. The `hhc-escrow-design-v03`, `VERIFIER-PAY-FIX-SPEC`, `TRANSFER-SPEC`, and `KEY-CUSTODY` documents in agent-mesh are the specs this code implements.
- **MVS-1 coherence** (`harmonyos/coherence_mvs1.py`): real math implemented, replay receipt written, 10/10 test vectors pass. Status: implemented, promotion on HOLD pending a hand-labeled calibration corpus (which does not exist yet).
- **HHCW token** on Base Sepolia (live, 90/5/5 mint verified) — supersedes the corpus seal-minter contract experiments.
- **ASINMOLT Moltbook** (Supabase) — supersedes the corpus Moltbook backend API block.
- **Runlab supervisor** (setsid + supervise.sh) — the production form of the 'service manager kernel' idea.
- On HOLD by decision, not by capability: the Groq provider adapter (`agent-mesh/proposals/groq-provider-adapter.md`, panel HOLD) and the GPU miner network design (design-only).

## Kernels

### WEAVER / EOS Governance Kernel
- **Kind:** kernel · **Completeness:** spec-only (ASCII architecture diagram, ~6.8KB x5 versions) · **Effort:** S as doc / L as literal build · **Verdict:** merge-into-existing
- **What it does:** Governance pipeline: Claims → Assertions → Evidence Ladder → Promotion/Revocation → Provenance, under frozen constitutional policy + human oversight
- **Source:** corpus unknown 385a5b10 (+ versions af62fb2e, 270cb73f, 8220bc8c, cb557a3e), mirror deepseek
- **Dependencies:** none
- **Was waiting for:** an agent-orchestration runtime able to run it (Ace + fleet)
- **Note:** Its pipeline is substantially the live operating pattern now (mesh receipts + Passport verdicts + evidence ladder). Formalize as architecture doc, don't rebuild.

### CP8 Kernel stage-machine (preregistration diagram)
- **Kind:** kernel · **Completeness:** spec-only (805B diagram) · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Preregistration + stage machine: 8 specialist agents (evidence/research/chronology/pattern/skeptic/replication/prior-art/builder) → Evidence Graph → synthesis → Promotion Gate + Reality Veto
- **Source:** corpus unknown 2d5daa51, mirror deepseek
- **Dependencies:** fleet seats
- **Was waiting for:** multi-agent orchestration capability
- **Note:** Describes the fleet workflow Ace now runs daily; the diagram predates the capability.

### CP8Kernel.mine_block fragment
- **Kind:** kernel · **Completeness:** fragment (212B, 3 lines) · **Effort:** S if class existed · **Verdict:** archive-only
- **What it does:** Code fragment: harmonic difficulty from memory/config, mine block with stop event
- **Source:** corpus unknown b2fac7ab, mirror gemini
- **Dependencies:** the CP8Kernel class it patches — not present anywhere in the archives
- **Was waiting for:** a CP8Kernel implementation that was never saved
- **Note:** PoW-style mining was superseded by the live hash-chained receipt ledger (no mining in mesh v0.2/v03).

### Systemd Service Manager pseudo-kernel
- **Kind:** kernel · **Completeness:** fragment · **Effort:** S · **Verdict:** archive-only
- **What it does:** Service-manager persona/spec fragments in systemd style
- **Source:** corpus unknown 32691f42 + 0d62eb41, mirror gemini
- **Dependencies:** none
- **Was waiting for:** nothing — superseded
- **Note:** The runlab supervisor (setsid + supervise.sh) is the real implementation of this idea.

### ASIN-NCEA prototype lineage v0.1-v2.0
- **Kind:** kernel · **Completeness:** substantial code (15 versions) · **Effort:** M · **Verdict:** merge-into-existing
- **What it does:** Versioned 'harmonic cryptography engine' lineage: entropy integrity lock, ed25519 identity anchor (v0.7), daemon integrity polling (v0.8), merkle compaction + ledger audit (v1.5), federated attestation gossip (v1.4), multi-node key chaining (v1.1), HHC wallet + PoWP finalization (v2.0); plus run_integration.py
- **Source:** ~/workspace/oai-library/asin_ncea_integrated_harness_v0_1.zip (15 snapshots, 6-23KB each)
- **Dependencies:** numpy; some versions assume CUDA/tensor cores
- **Was waiting for:** a runtime + integration pass to graduate prototypes into the live system
- **Note:** Its core features (ed25519 identity, hash/merkle ledger, wallet) are ALREADY in live mesh v03 — the lineage is the design ancestor. Two ideas never graduated: federated attestation gossip and daemon integrity polling — both are implement-now candidates as mesh add-ons.

## Code & services

### CP8 Unified Bridge v2.2 (FullStack)
- **Kind:** service · **Completeness:** runnable code · **Effort:** S-M · **Verdict:** implement-now
- **What it does:** Single-file FastAPI app: telemetry pulses, harmonic contract forge, ledger pulse with merkle root, harmonic decode endpoint, Codex Seal frontend
- **Source:** ~/workspace/oai-library/ASIN_HHC_CP8_FullStack.py (23,324B); corpus variants incl. python 8f8746e8 (gemini)
- **Dependencies:** fastapi, pydantic, uvicorn
- **Was waiting for:** public hosting for a live API surface
- **Note:** In-memory state, no auth/persistence — needs hardening before public exposure, but it is a complete deployable API that fills the Stage-C public-surface gap.

### Moltbook backend API (ASINMOLT)
- **Kind:** service · **Completeness:** substantial code · **Effort:** M · **Verdict:** merge-into-existing
- **What it does:** FastAPI backend for the ASINMOLT Moltbook (backend/api/main.py layout, download-all, post/feed routes)
- **Source:** corpus python 4a48920f, mirror deepseek (32,825B)
- **Dependencies:** fastapi
- **Was waiting for:** a deployment target; ASINMOLT itself already runs on Supabase
- **Note:** Compare against the live ASINMOLT Supabase implementation before any reuse; likely superseded.

### TSH Molecular Archivist API
- **Kind:** service · **Completeness:** runnable code · **Effort:** S-M · **Verdict:** implement-now
- **What it does:** Complete FastAPI service: TSHMolecularArchivist class (436 lines) + verify-integrity (manifest), temporal-delta, parse-tsh, generate-smiles endpoints
- **Source:** corpus python f9800bb3, mirror deepseek (18,366B)
- **Dependencies:** fastapi, pydantic
- **Was waiting for:** public hosting
- **Note:** One of Dennis's named apps (cf. Replit 'Harmonic Molecular Archivist'); self-contained and deployable.

### Validator Harness (task validators)
- **Kind:** module · **Completeness:** runnable code · **Effort:** S · **Verdict:** implement-now
- **What it does:** LLM task-validation harness: Transaction/Creative/Reasoning validators with ground truth, model caller, task runner and scoring
- **Source:** corpus python c50ed37e, mirror deepseek (15,945B)
- **Dependencies:** an LLM endpoint for call_model
- **Was waiting for:** an inference endpoint to evaluate against — fleet seats now exist
- **Note:** Directly reusable for Passport certification battery scoring and verifier-quality measurement.

### PRED-003 Benchmark Harness v2.3
- **Kind:** module · **Completeness:** runnable code · **Effort:** S · **Verdict:** implement-now
- **What it does:** Self-contained benchmark: synthetic task generators (HND/EPC/CLPS), CP8v23 reference implementation, baselines (single-LLM, ensemble, oracle), CI statistics — no external LLM calls
- **Source:** corpus python ae02903e, mirror deepseek (25,706B)
- **Dependencies:** numpy, scipy (optional)
- **Was waiting for:** nothing — it was built to run standalone
- **Note:** A ready evaluation harness for MVS-1 / Passport claims; pairs with the MVS-1 calibration gap (needs labeled data, this generates synthetic tasks).

### Harmony Assistant v1.1 — ANU-28 Glyph Fusion
- **Kind:** service · **Completeness:** runnable code · **Effort:** M · **Verdict:** implement-now
- **What it does:** FastAPI + SQLModel + WebSocket chat app: streams a local Ollama model (mistral:7b-instruct) and fuses context-selected ANU-28 glyphs into responses; glyph DB seeded
- **Source:** corpus python 2d106999, mirror grok (6,783B)
- **Dependencies:** fastapi, sqlmodel, ollama
- **Was waiting for:** local inference (Ollama on the host) — the Stage-B capability
- **Note:** The clearest 'built before the capability existed' artifact: it assumed local inference that is only now being stood up (llama.cpp Stage B).

### FastAPI handshake/telemetry fragments
- **Kind:** service · **Completeness:** fragment · **Effort:** S · **Verdict:** duplicate-of-CP8 Unified Bridge v2.2
- **What it does:** Small FastAPI handshake/telemetry service fragments (gemini seat)
- **Source:** corpus unknown 4809b880, f0c7ca4d, 6438e489, d0dfb9e1, 8bbf8231, mirrors gemini
- **Dependencies:** fastapi
- **Was waiting for:** —
- **Note:** Fragments and partial copies of the Unified Bridge family.

### Quantum Glyph Engine suite
- **Kind:** engine · **Completeness:** substantial code · **Effort:** L · **Verdict:** archive-only
- **What it does:** 11-class glyph processing suite: QuantumGlyphProcessor, QuantumANU28Engine, QuantumRealityCompiler, temporal folder, trainer, visualizer, main execution
- **Source:** corpus python 636df77c, mirror deepseek (27,086B)
- **Dependencies:** numpy (simulated 'quantum' formalism)
- **Was waiting for:** a reason to run it — formalism is speculative
- **Note:** Salvageable only as a glyph-pipeline structure reference; the quantum framing is not load-bearing.

### GlyphConsciousnessNet + RealTimeGlyphEngine
- **Kind:** module · **Completeness:** substantial code · **Effort:** L · **Verdict:** archive-only
- **What it does:** PyTorch glyph classifier trained on affect/HRI data + real-time glyph engine
- **Source:** corpus python b56e1d49, mirror deepseek (10,911B)
- **Dependencies:** torch, an affect/HRI dataset that is not in the archives
- **Was waiting for:** training data + GPU time
- **Note:** Training data never landed; lexicon data (see ANU-28 entry) is the salvageable part.

### ASINHHCHook autoencoder experiments
- **Kind:** module · **Completeness:** substantial code · **Effort:** M · **Verdict:** archive-only
- **What it does:** PyTorch autoencoder with a latent-space 'asinhhc_hook' regularizer (4 duplicated versions in one file)
- **Source:** corpus python d3c0a6fe, mirror grok (23,929B)
- **Dependencies:** torch, torchvision, GPU helpful
- **Was waiting for:** nothing technical — a research experiment
- **Note:** Research lineage only; versions not deduplicated by its own author.

### MoltBountyEscrow.sol
- **Kind:** module · **Completeness:** substantial code · **Effort:** M · **Verdict:** implement-now
- **What it does:** USDC bounty escrow contract: deposit, team share splits, approval payout (OpenZeppelin)
- **Source:** corpus solidity 8a058d2b, mirror grok (2,239B)
- **Dependencies:** @openzeppelin/contracts
- **Was waiting for:** wallet signing / a mainnet-vs-testnet decision (Dennis's hand)
- **Note:** On-chain counterpart to the live HHC escrow; waits on the same signing decision as HHCW mainnet.

### ChallengeProtocol.sol (x2 versions)
- **Kind:** module · **Completeness:** substantial code · **Effort:** M-L · **Verdict:** archive-only
- **What it does:** Adversarial slashing for checkpoint anchors: 20% slash, 7-day challenge window, zk-SNARK variant
- **Source:** corpus solidity 4f8e5e68 + 26c61cde, mirror grok (3,544B / 3,232B)
- **Dependencies:** VARAnchor.sol — NOT present anywhere in the archives
- **Was waiting for:** recovery or rewrite of VARAnchor.sol; wallet signing
- **Note:** Broken dependency chain: the anchor contract it protects was never saved. Rebuild only if the VAR lattice track revives.

### Solidity miscellany (seal minter etc.)
- **Kind:** module · **Completeness:** fragment to substantial · **Effort:** M · **Verdict:** merge-into-existing
- **What it does:** CP8-Seal-Minter (Base Sepolia) + 7 further small contracts/experiments
- **Source:** corpus solidity 52c955a2, 71cf4655, 9b2f505c, a728e707, afc4e440, b4ea37e1, ff9da0fd, mirror grok
- **Dependencies:** openzeppelin
- **Was waiting for:** wallet signing
- **Note:** HHCW's live Base Sepolia deployment supersedes the seal-minter experiments.

### Formation Lab package
- **Kind:** engine · **Completeness:** runnable code · **Effort:** S · **Verdict:** implement-now
- **What it does:** Complete Python package for crop-formation geometry analysis: formations.py, passes.py (multi-pass pipeline), models, neuro subpackage, tests, FastAPI main
- **Source:** ~/workspace/oai-library/cp8-formation-lab.zip (84KB; near-duplicate cp8-formation-lab(1).zip)
- **Dependencies:** fastapi, numpy; ships its own tests
- **Was waiting for:** nothing — it was built to run
- **Note:** A finished, tested project sitting in a zip. Pairs with binary.py (its Pass-3). Niche (decode research) but zero build cost.

### binary.py — Pass-3 geometry->bitstring decoder
- **Kind:** module · **Completeness:** runnable code · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Crop-circle geometry to bitstring mapping: 6 mapping rules + quality checks (byte alignment, repeats, entropy)
- **Source:** ~/workspace/oai-library/binary.py (8,176B)
- **Dependencies:** none (pure python)
- **Was waiting for:** nothing
- **Note:** Pass 3 of the decode pipeline whose other passes live in Formation Lab.

### CCD-9 Decode 791 app
- **Kind:** UI app · **Completeness:** runnable code · **Effort:** S · **Verdict:** archive-only
- **What it does:** Complete single-file web app decoding formation 791
- **Source:** ~/workspace/oai-library/CCD-9_Decode_791(1).html (1,055,184B)
- **Dependencies:** none (static html)
- **Was waiting for:** public hosting for demos
- **Note:** Finished demo artifact; publish as-is if the decode line is ever showcased.

### DMT World Codex Resonance Engine
- **Kind:** UI app · **Completeness:** runnable code · **Effort:** S · **Verdict:** archive-only
- **What it does:** Canvas app implementing ASIN-DMW-0.1: state capture, JSON serialization, SHA-256 hashing via WebCrypto, glyph/flower rendering
- **Source:** ~/workspace/oai-library/ASIN_DMT_World_CODEX_RESONANCE_ENGINE.html (17,002B) + .zip; corpus mirrors
- **Dependencies:** none (static html)
- **Was waiting for:** nothing
- **Note:** Salvage pattern: its state->hash capture is a client-side receipt-minter pattern; the app itself is a demo.

### DMT World sibling labs (Lab / Phenomenology / Spatial Codex)
- **Kind:** UI app · **Completeness:** runnable code · **Effort:** S · **Verdict:** archive-only
- **What it does:** Three interactive DMT World lab variants
- **Source:** ~/workspace/oai-library/ASIN_DMT_World_Lab_FIXED.html, ASIN_DMT_World_Phenomenology_Lab.html, ASIN_DMT_World_SPATIAL_CODEX_FIXED.html (+ zips)
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** Demo family; keep one canonical copy.

### CP8 Resonance Engine v1.3
- **Kind:** UI app · **Completeness:** runnable code · **Effort:** S · **Verdict:** archive-only
- **What it does:** Interactive resonance visualizer (CodePen build)
- **Source:** ~/workspace/oai-library/cp8_resonance_engine_v1_3_codepen.html (22,149B)
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** Demo/visualization.

### CodePen pen fleet (~330 blocks)
- **Kind:** UI app · **Completeness:** runnable code (mostly) · **Effort:** S each · **Verdict:** archive-only
- **What it does:** Bulk interactive visualizations: Kuramoto/coherence sims (a5ba379d 41.8KB, ddcd36c4), three.js apps (51 blocks), websocket apps (92 blocks), wallet UI prototypes (fb5316db 57KB, 36d1a1e0 53.5KB, 4b4e8aad 45.6KB)
- **Source:** corpus mirror codepen (330 blocks); 218 html blocks >=10KB across mirrors
- **Dependencies:** varies (three.js, websockets)
- **Was waiting for:** public hosting
- **Note:** Except: the three wallet UI prototypes are merge candidates as front-end reference for the Work Market. The rest are demos/visualizations of record.

### ConsciousnessSimulator JS suite
- **Kind:** engine · **Completeness:** substantial code · **Effort:** L · **Verdict:** archive-only
- **What it does:** 91.7KB JS class zoo: GlobalWorkspace, QualiaGenerator, PredictiveIntelligenceCore, HyperdimensionalEngine, etc.
- **Source:** corpus javascript 11e15baa, mirror deepseek
- **Dependencies:** none
- **Was waiting for:** nothing — speculative simulation
- **Note:** The largest single JS block; a speculative formalism with no consumer.

### Bash ops corpus (278 blocks + 32 reclassified)
- **Kind:** module · **Completeness:** runnable code (mostly) · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Deploy/validate/systemd script family (deploy.sh, validate.sh, git seed-launch scripts)
- **Source:** corpus lang bash (278 blocks) + unknown-classified bash (32)
- **Dependencies:** bash, systemd
- **Was waiting for:** —
- **Note:** The runlab supervisor already does this job in production; keep scripts as reference.

### Java Spring order processor
- **Kind:** module · **Completeness:** substantial code · **Effort:** S · **Verdict:** archive-only
- **What it does:** Complete Spring @Service order-processing class (taxonomy stray)
- **Source:** corpus unknown 703c30ab (via classification: java_detected)
- **Dependencies:** spring framework
- **Was waiting for:** —
- **Note:** Off-thesis stray; proof the mirrors contain non-ASIN material.

### Kuramoto / coherence simulation apps
- **Kind:** engine · **Completeness:** runnable code · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Interactive Kuramoto phase-coupling simulations (HTML apps)
- **Source:** corpus html beb2d247 (36,392B, deepseek), c19d0cdc (29,975B, grok), a5ba379d (codepen)
- **Dependencies:** none (static html)
- **Was waiting for:** nothing
- **Note:** MVS-1 in harmonyos is now the canonical coherence implementation; these are its demo ancestors.

### ANU-28 lexicon system (data + tokenizer refs)
- **Kind:** module · **Completeness:** substantial code/data (lexicon data complete; tokenizer module itself referenced, partial copies in classified code) · **Effort:** S-M · **Verdict:** implement-now
- **What it does:** Glyph lexicon as data: JSON registries (glyph_code/glyph_name/meaning/frequency_hz/category), morpheme layer (A1_ANU, A2_LUMA...), glyph_set strings, JS glyph-token semantics table, named glyphs in Python; ANU28Tokenizer + glyph_decoder.py + anu28_lexicon.json referenced in 3 blocks; only 5 standalone glyph-sequence blocks (c72505ac the one true [GLYPH SEQUENCE])
- **Source:** corpus json 2b6cb5cc, dd415cd3, ad8a5c2f, c3c55f2d; javascript d2a5b4c6; python f0c7ca4d; unknown ac26368f, 91e25dfd, c72505ac, dbe0ac0c, f5d6637a
- **Dependencies:** none for the data module
- **Was waiting for:** nothing — the data exists; it waited for consolidation
- **Note:** Consolidate registries into one anu28_lexicon.json + tokenizer module; turns a claim ('custom token vocabulary') into a shipped artifact.

## Schemas & grammars

### asin-hhc:receipt JSON Schema
- **Kind:** schema · **Completeness:** spec-only (complete schema document) · **Effort:** S · **Verdict:** implement-now
- **What it does:** Complete JSON Schema (draft 2020-12) for evidence receipts: receipt_id pattern ^asin-hhc:receipt:, claim_id, status enum = the evidence ladder (OBSERVED/PROVENANCED/TESTED/REPLAYED/INDEPENDENTLY_REPRODUCED/PROMOTED/HOLD/REJECTED/RETIRED), inputs/procedure/execution/outputs/replay objects
- **Source:** corpus unknown 96740ac2, mirror deepseek (3,359B)
- **Dependencies:** a JSON Schema validator
- **Was waiting for:** nothing — it waited for the receipt system to exist; the live canon-v1 hash-chain receipts now do, but do not yet validate against this schema
- **Note:** Top candidate: adopt as the canonical receipt format across mesh, Passport, and the Sebastien/NeoMundi packet.

### CP8 Manifest dialect
- **Kind:** schema · **Completeness:** spec-only (emergent, never formalized) · **Effort:** S-M · **Verdict:** implement-now
- **What it does:** De-facto agent state-handoff format: anchor/shape/intention/number/actions/checksums/next_step JSON manifests — 272 instances (173 strict), ~235KB, embedded even inside large HTML/JS apps
- **Source:** corpus across mirrors (deepseek/gemini/grok); strict-pattern examples: unknown 7358853f, 8a577eab, 2a564407
- **Dependencies:** a JSON Schema + validator
- **Was waiting for:** formalization — the format was used for years without ever being written down as a schema
- **Note:** The fleet's actual interchange format. Formalize as 'CP8 Manifest v1' schema; the corpus itself is the conformance test set.

### DSL family 1 — pipeline chains
- **Kind:** DSL grammar · **Completeness:** spec-only (recurring grammar, never formalized) · **Effort:** S · **Verdict:** implement-now
- **What it does:** Evidence-pipeline chains: OBSERVED -> PROVENANCE VERIFIED -> POPULATION RECONCILED -> SOURCE GEOMETRY RECOVERED -> INDEPENDENT EXTRACTION -> STATISTICAL REPLAY -> OUT-OF-SAMPLE VALIDATION -> FIELD CORRESPONDENCE ASSESSED -> PROMOTION REVIEW
- **Source:** corpus unknown f65ef689 + family within 148 asin_dsl_candidate blocks (classification.jsonl)
- **Dependencies:** none
- **Was waiting for:** a formal grammar/state-machine write-up
- **Note:** This is the evidence standard Ace already runs (OBSERVED->PROVENANCE->TEST->REPLAY->PROMOTION); formalizing makes it citable for Passport/Sebastien.

### DSL family 2 — verdict trees
- **Kind:** DSL grammar · **Completeness:** spec-only · **Effort:** S · **Verdict:** implement-now
- **What it does:** Audit-protocol verdict trees: CMD1-CMD10 branch protocol ending in scored verdicts; VIOLATION_REGISTRY in the same grammar
- **Source:** corpus unknown cbe11980 (1,831B), 57fa136c (751B), mirror deepseek
- **Dependencies:** none
- **Was waiting for:** formalization as a verifier checklist format
- **Note:** Directly usable as the structured verdict format for mesh verifiers / Passport battery reporting.

### DSL family 3 — decision trees
- **Kind:** DSL grammar · **Completeness:** spec-only · **Effort:** S · **Verdict:** archive-only
- **What it does:** Nested YES/NO decision trees over invariants (crop-formation invariants exemplar)
- **Source:** corpus unknown 9e6307bb (736B), mirror grok
- **Dependencies:** none
- **Was waiting for:** formalization
- **Note:** Same family as verdict trees; formalize together later.

### Coherence math antecedents (MVS-1 lineage)
- **Kind:** algorithm · **Completeness:** substantial code/spec · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Chi-square coherence report with real statistics (chi2=260.10, df=255, p=0.41, PASS), 23 math-notation blocks, LaTeX coherence documents
- **Source:** corpus unknown 2803c7d0 (gemini); latex 3c93f060 (10,872B, deepseek), 362f671d (grok)
- **Dependencies:** —
- **Was waiting for:** a labeled calibration corpus (still missing)
- **Note:** MVS-1 is implemented in harmonyos; these are its research lineage and candidate calibration evidence.

### CP8 AI Instrument Integrity Longitudinal Ledger
- **Kind:** schema · **Completeness:** spec-only (format + seed data) · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Ledger format (JSON + MD) for longitudinal tracking of AI-instrument (fleet seat) behavior/integrity
- **Source:** ~/workspace/oai-library/CP8_AI_INSTRUMENT_INTEGRITY_LONGITUDINAL_LEDGER_2026-09-04.json/.md
- **Dependencies:** none
- **Was waiting for:** a logging pipeline feeding it
- **Note:** Candidate format for fleet audit logging; the idea is live in spirit (fleet receipts), the format was never adopted.

## Shelf / archive-only

### Attention-head weight matrices block
- **Kind:** other · **Completeness:** fragment (data only) · **Effort:** S · **Verdict:** archive-only
- **What it does:** Raw attention-head weight matrix data (coherence-tagged)
- **Source:** corpus unknown e39102e8, mirror gemini (1,588B)
- **Dependencies:** the model/run that produced it — not in archives
- **Was waiting for:** provenance that no longer exists
- **Note:** Data without its generating run; cannot be replayed.

### Prose strategy & IP archive (184 blocks)
- **Kind:** other · **Completeness:** prose claim (as code) / complete documents (as documents) · **Effort:** S · **Verdict:** archive-only
- **What it does:** Misfilled-as-code prose: patent claims + 3-patent filing plan (a8dddcc0, ed1149f8), CP8 ecosystem merge plan (e27460ed), fundraising playbook (bfc31d4e), acquisition/IPO outlines (00333261, 75c2ff6c), 120-page deliverables spec (75c1714a), largest block a 25KB prose doc (b18f5e6d), AGENTS.md directives doc (f78e1174)
- **Source:** corpus unknown (prose class, classification.jsonl)
- **Dependencies:** none
- **Was waiting for:** nothing — documents, not code
- **Note:** Not implementable code; value is as recovered IP/strategy documents. The merge plan e27460ed doubles as the FastAPI/ANU-28 cross-reference index.

### OAI Ace report family (cross-examination / chronology / reconciliation)
- **Kind:** other · **Completeness:** prose claim (evidence records) · **Effort:** S · **Verdict:** archive-only
- **What it does:** OAI Ace's delivered audit reports and handoff receipts, with (1)-suffixed exact duplicates
- **Source:** ~/workspace/oai-library/CP8_ACE_* (md/docx/json, 2026-08-13..09-04)
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** Authorship/evidence records for the convergence index; dedupe note: docx+md and (1) copies are byte-identical duplicates.

### Arecibo Reply Complete Payload
- **Kind:** other · **Completeness:** prose claim · **Effort:** S · **Verdict:** archive-only
- **What it does:** One-off 17.6KB transmission payload document
- **Source:** ~/workspace/oai-library/ASIN_HHC_CP8_Arecibo_Reply_Complete_Payload.txt
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** One-off artifact of record.

### Archive bundles (Geometry Preservation 4.1MB, all_assets, FULL_UPLOAD_BACKUP)
- **Kind:** other · **Completeness:** prose claim (bundles) · **Effort:** S · **Verdict:** archive-only
- **What it does:** Bulk preservation zips (inventoried by listing only)
- **Source:** ~/workspace/oai-library/ASIN_HHC_CP8_Geometry_Preservation_2026-09-05.zip, all_assets.zip, ASIN_HHC_FULL_UPLOAD_BACKUP_2026-07-25.zip
- **Dependencies:** none
- **Was waiting for:** an extraction pass if ever needed
- **Note:** Cold storage; contents largely duplicate the corpus + media.

### Decode research documents (docx family)
- **Kind:** other · **Completeness:** prose claim · **Effort:** S · **Verdict:** archive-only
- **What it does:** Ancient Cycle Deciphering Framework, Crop Circle Geometry Framework, Unicode Symbol Decoding, decoding key puzzles (x2 identical)
- **Source:** ~/workspace/oai-library/*.docx
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** Research documents behind the decode pipeline; reference for Formation Lab.

### DEEK E4 Intake Gate packet
- **Kind:** other · **Completeness:** spec-only · **Effort:** S · **Verdict:** merge-into-existing
- **What it does:** Intake-gate process packet: gate checklist, source-lock requirement, shared-response placeholder audit, status ledger
- **Source:** ~/workspace/oai-library/DEEK_E4_INTAKE_GATE_2026-07-23.zip (8 files)
- **Dependencies:** none
- **Was waiting for:** —
- **Note:** Its source-lock / placeholder-audit pattern is now standard Ace practice; the packet is the fossil of that rule.

### SYS-02 Evidence OS node document
- **Kind:** other · **Completeness:** prose claim · **Effort:** S · **Verdict:** archive-only
- **What it does:** Documentation of an external Lovable-hosted 'CP8 Evidence OS' console, self-described as LIVE but UNDER RECOVERY — NOT VALIDATED
- **Source:** ~/workspace/oai-library/ASIN-HHC_SYS-02_Evidence_OS_Node.md
- **Dependencies:** external Lovable app (not in archives)
- **Was waiting for:** —
- **Note:** External system, not ours to implement; its own text warns its predecessor portal had non-functional controls.

### Media archive (diagrams / portraits / infographics)
- **Kind:** other · **Completeness:** prose claim (media) · **Effort:** S · **Verdict:** archive-only
- **What it does:** Crop-circle diagrams, Buga peptide infographic, codex portraits, convergence study images (~17MB of the oai-library)
- **Source:** ~/workspace/oai-library/*.png
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** Visual assets of record (incl. the Buga sphere dossier material).

### DoorDash SSI Work Pain Log
- **Kind:** other · **Completeness:** prose claim · **Effort:** S · **Verdict:** archive-only
- **What it does:** Personal gig-work log spreadsheet
- **Source:** ~/workspace/oai-library/DoorDash_SSI_Work_Pain_Log.xlsx
- **Dependencies:** none
- **Was waiting for:** nothing
- **Note:** Off-thesis personal record; listed for completeness.

## Notes

- **Authorship:** the corpus mirrors are deepseek / gemini / grok / codepen only. OAI Ace (ChatGPT seat) has no corpus mirror; its delivered work is the oai-library file set (FullStack lineage, NCEA harness, formation lab, reports). Several 'gemini mirror' blocks are copies of OAI-lineage code that Dennis carried across seats — the Unified Bridge family is the clearest case.
- **Security:** block `c1a9ea36` (unknown bucket) is a credential-shaped string that survived the extractor's secret filter — already flagged to Dennis separately; it is excluded from candidacy and the value appears nowhere in this inventory.
- Nothing was implemented, modified, published, or sent. Source archives untouched.
