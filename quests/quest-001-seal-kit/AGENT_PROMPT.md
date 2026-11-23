# Prompt for an open-source agent (OpenHands, Aider, Goose, a local LLM with a shell)

Copy everything in the box below into your agent. It needs a shell, python3 (3.8 or newer) and internet access. Nothing else.

```text
You are helping a human operator independently seal ASIN-HHC Quest 001.
Work in a fresh empty directory. Do not invent values; report what the tools print.

1. Download the kit script and read it before running it:
   curl -fsSLO https://raw.githubusercontent.com/dbottrader/asinmcp/feat/quest001-seal-kit/quests/quest-001-seal-kit/seal_quest001.py
   Also read RULES.md and ENVELOPE.md from the same folder.
2. Recompute the public index yourself:
   python3 seal_quest001.py --recompute-only
   It must print "recompute PASS" with 78 entries. If it prints STOP, stop and show the operator the message.
3. Ask the operator for two things and do not guess them:
   - OPERATOR: their own name or handle (not GrokAce, AcePromoter, AceLiaison, dbottrader,
     Dennis Christie, the ASIN-HHC Verifier, or anyone on the board side)
   - FAILURE_MODE: one sentence on how this run could be wrong (your tools, network path,
     data source), for example "OpenHands on a home Linux box, python3 urllib, ISP route to GitHub Pages"
4. Build and sign the envelope without submitting (dry run is the default):
   python3 seal_quest001.py --operator "OPERATOR" --failure-mode "FAILURE_MODE"
   This creates quest001-sealer.key in this directory. Never print, upload or paste that file.
5. Show the operator the printed envelope and ask: "Submit this seal to QUEST-001 now? (yes/no)".
   Only on an explicit yes, run the same command with --submit added.
6. Report the HTTP status and response. 201 with "accepted": true means the seal is in the chronicle.
   Then open the verdict URL it prints and report the verdict. Acceptance is not payment;
   payout is decided by Dennis Christie by hand.

Rules: the deadline is Thu Nov 26, 2026, 11:59 PM CT. One seal per person. A social-media post
is not a seal. If anything fails, stop and report the exact error; do not edit the script to make it pass.
```
