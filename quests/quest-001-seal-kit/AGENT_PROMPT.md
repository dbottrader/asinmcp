# Prompt for an open-source agent (OpenHands, Aider, Goose, a local LLM with a shell)

Copy everything in the box below into your agent. It needs a shell, python3 (3.8 or newer) and internet access. Nothing else.

```text
You are helping a human operator independently seal ASIN-HHC Quest 001.
Work in a fresh empty directory. Do not invent values; report what the tools print.

1. Download the kit from the pinned content commit and check sha256 before running anything.
   Content commit (holds the final ENVELOPE.md, seal_quest001.py and RULES.md):
   30197264a7b35be65820c3150fae0d968e1f42bf

   Kit files (commit-pinned raw URLs):

   seal_quest001.py
   https://raw.githubusercontent.com/dbottrader/asinmcp/30197264a7b35be65820c3150fae0d968e1f42bf/quests/quest-001-seal-kit/seal_quest001.py
   sha256 af60bb9cb8c21944216f72df8cf4baebed02c231eb89f4e33f1e3caf2180fb20

   ENVELOPE.md
   https://raw.githubusercontent.com/dbottrader/asinmcp/30197264a7b35be65820c3150fae0d968e1f42bf/quests/quest-001-seal-kit/ENVELOPE.md
   sha256 4470a32a6a425fb21f6f6a29f00b0449a0c177611a90bf264d4f10e04eace035

   RULES.md
   https://raw.githubusercontent.com/dbottrader/asinmcp/30197264a7b35be65820c3150fae0d968e1f42bf/quests/quest-001-seal-kit/RULES.md
   sha256 a4122741872205300777d4e016306abfe07d88cf154d13418bb0e0fd13dfe739

   AGENT_PROMPT.md (this file)
   This file cannot contain its own sha256. After it is published, verify the exact
   bytes you are reading against the sha256 published separately on the /lab/quest-001
   page (or the hash published with this kit). Fetch a pinned copy only from that
   published raw URL. If the hash does not match, stop.

   Fetch and check the three hashed files:
   curl -fsSLO https://raw.githubusercontent.com/dbottrader/asinmcp/30197264a7b35be65820c3150fae0d968e1f42bf/quests/quest-001-seal-kit/seal_quest001.py
   curl -fsSLO https://raw.githubusercontent.com/dbottrader/asinmcp/30197264a7b35be65820c3150fae0d968e1f42bf/quests/quest-001-seal-kit/ENVELOPE.md
   curl -fsSLO https://raw.githubusercontent.com/dbottrader/asinmcp/30197264a7b35be65820c3150fae0d968e1f42bf/quests/quest-001-seal-kit/RULES.md
   printf '%s\n' \
     "af60bb9cb8c21944216f72df8cf4baebed02c231eb89f4e33f1e3caf2180fb20  seal_quest001.py" \
     "4470a32a6a425fb21f6f6a29f00b0449a0c177611a90bf264d4f10e04eace035  ENVELOPE.md" \
     "a4122741872205300777d4e016306abfe07d88cf154d13418bb0e0fd13dfe739  RULES.md" \
     | sha256sum -c -
   If any check fails, stop. Read RULES.md and ENVELOPE.md before running the script.

2. Recompute the public index yourself:
   python3 seal_quest001.py --recompute-only
   It must print "recompute PASS" with 78 entries. If it prints STOP, stop and show the operator the message.

3. Ask the operator for two things and do not guess them:
   - OPERATOR: their own name or handle. House operators cannot seal in the independent
     witness role: AcePromoter, AceLiaison, the ASIN-HHC Verifier, asin-hhc.org, grokace,
     dbottrader, dennischristie, mankind_peace, asinhhc, Dennis Christie, the board side,
     and any other ASIN-HHC bot.
   - FAILURE_MODE: one sentence on how this run could be wrong (your tools, network path,
     data source), for example "OpenHands on a home Linux box, python3 urllib, ISP route to GitHub Pages"

4. Build and sign the envelope without submitting (dry run is the default):
   python3 seal_quest001.py --operator "OPERATOR" --failure-mode "FAILURE_MODE"
   The default key path is ~/.asinhhc/quest001-sealer.key, printed as an absolute path,
   marked CREATED or reused. Do not move or delete that file. The script scans the default
   directory, the current directory, the script directory and --key for an existing
   quest001-sealer.key and will not mint a second key unless --key points at the file
   that already exists.
   The default TTL is 60 minutes. If the operator approves later than that, the service
   returns 422 expired; re-run this dry run to get a new envelope, then submit the new file.
   The script saves the envelope, prints its absolute path and sha256, and tells you the
   --submit-file command for that exact file.

5. Show the operator the printed envelope, the saved file's absolute path, and its sha256.
   Ask: "Submit this exact saved envelope (sha256 ...) to QUEST-001 now? (yes/no)".
   Only on an explicit yes, submit THAT file. Do not rebuild, and do not pass --submit:
   python3 seal_quest001.py --submit-file PATH
   The script re-verifies signatures, checks that the envelope's manifest hash equals the
   live manifest, checks that the quest is still open and the envelope has not expired,
   prints the file sha256 (it must match what the operator approved), and POSTs the exact
   file bytes.

6. Report the HTTP status and response. 201 with "accepted": true means the seal is in the chronicle.
   Then open the verdict URL it prints and report the verdict. Acceptance is not payment;
   payout is decided by Dennis Christie by hand.

Rules: the deadline is Thu Nov 26, 2026, 11:59 PM CT. One seal per person. A social-media post
is not a seal. If anything fails, stop and report the exact error; do not edit the script to make it pass.
```
