#!/bin/sh
# Stage C gateway launcher — detached (setsid) per the workspace rule:
# processes started with plain `nohup &` from an exec session are reaped
# when the session closes. Safe to re-run: exits if :8222 already answers.
if curl -s -m 3 http://127.0.0.1:8222/v1/health >/dev/null 2>&1; then
  echo "stage-c gateway already up"
  exit 0
fi
cd "$(dirname "$0")"
setsid nohup python3 gateway.py >> gateway.log 2>&1 &
echo "stage-c gateway launched"
