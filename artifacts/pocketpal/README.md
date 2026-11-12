# PocketPal Pack — ASIN-HHC on your phone

This pack puts our mesh-pinned model on your phone, running fully offline in
PocketPal (a free Android app that runs GGUF models locally — no account, no
cloud, nothing leaves the phone).

## What's in the pack

| File | What it is |
|---|---|
| `asin-qwen0.5b-q4_k_m.gguf` | The model file (GGUF) |
| `SYSTEM-PROMPT.md` | The system prompt to paste into PocketPal |
| `README.md` | This file |

## The model

- **Model:** Qwen2.5-0.5B-Instruct, Q4_K_M quantization — the exact model pinned
  on the ASIN-HHC mesh (Ollama name `asin-qwen0.5b`).
- **File size:** 491,400,032 bytes (~491 MB / 469 MiB)
- **SHA-256:** `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`
- **Ollama manifest digest:** `29ef26c5cf7d3d68a20fdeb8664ef48f1f32386d2ba09ddb4b19f4c7dc89d5de`
  — the manifest's model layer is the blob above, originally imported from
  `qwen2.5-0.5b-instruct-q4_k_m.gguf`. Same file the mesh workers and checkers
  run, so answers on the phone come from the same weights the mesh verifies with.

Because it's a 0.5B model at Q4_K_M, it runs on basically any modern Android
phone and leaves plenty of room to spare. It's small — good for quick answers,
drafts, and ASIN explainers on the go, not a replacement for a big model.

## Load steps

1. **Install PocketPal** from the Google Play Store (free, by the PocketPal AI
   team — "PocketPal AI"). Open it once so it creates its folders.
2. **Copy the model onto the phone:** get `asin-qwen0.5b-q4_k_m.gguf`
   (~491 MB) onto the phone — USB cable, Google Drive, or any file transfer.
   Remember which folder you put it in (e.g. `Download`).
3. **Import the model in PocketPal:** open PocketPal → Models (or the model
   picker) → add / import a local model → browse to
   `asin-qwen0.5b-q4_k_m.gguf` and select it. PocketPal copies it into its own
   storage; after the import finishes you can delete your transfer copy.
4. **Load it:** select the imported model and let it load (a few seconds —
   it needs roughly 0.6 GB of free RAM while running).
5. **Create the pal:** create a new Pal / assistant, name it **ASIN-HHC**,
   open `SYSTEM-PROMPT.md` from this pack, copy everything below the line,
   and paste it into the pal's **system prompt** field. Save.
6. **Chat:** open the ASIN-HHC pal and talk. Try: "What is ASIN-HHC?" and
   "How does Proof of Pay work?" — the answers should give you the
   open-alternative line, the worker + two-verifier + escrow shape, and call
   settlement testnet.

## Notes

- Everything runs offline after setup. Airplane mode is fine.
- The system prompt's rules are deliberate: HHC is a utility credit, never
  money or an investment, and settlement is Base Sepolia **testnet** — the pal
  is written to say so every time it comes up.
- If you ever re-download the model instead of using this file, check the
  SHA-256 above against your copy before loading it. Receipts over stories
  applies to files too.
