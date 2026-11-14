#!/usr/bin/env bash
# QUEST-001 "Seal the Index" — reference witness verifier (bash).
# Implements quest001/QUEST-001-SPEC.md. Needs: bash, curl, jq >= 1.6,
# sha256sum (or shasum -a 256), python3 (stdlib only, for the index
# chain rule which uses Python's default ", " / ": " separators).
#
# Usage:
#   verify_quest001.sh [CLAIM_URL_OR_FILE] [EXPECTED_CLAIM_SHA256 EXPECTED_BYTES]
# Prints one JSON object: {output:{count,head_hash}, sealed_output, observed:{...}}
# Exit 0 = recomputed values consistent with the claim's declared values,
# 2 = inconsistent (still prints what was observed), 3 = claim error.
#
# Pitfall fixed vs the old script: `jq -r` appends "\n" to every string it
# prints, so hashing its output hashes one extra byte. Every hash here is
# taken over exact bytes with NO trailing newline (jq -j / printf '%s').
set -euo pipefail

CLAIM="${1:-https://dbottrader.github.io/asinmcp/artifacts/specs/provenance-index.json}"
EXP_SHA="${2:-}"
EXP_BYTES="${3:-}"

die() { printf 'CLAIM ERROR: %s\n' "$*" >&2; exit 3; }
sha256() { if command -v sha256sum >/dev/null; then sha256sum | cut -c1-64; else shasum -a 256 | cut -c1-64; fi; }
for t in curl jq python3; do command -v "$t" >/dev/null || die "missing tool: $t"; done

TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT
if [[ "$CLAIM" =~ ^https?:// ]]; then
  curl -fsSL --proto '=https' -H 'Cache-Control: no-cache' -o "$TMP" "$CLAIM" || die "fetch failed: $CLAIM"
else
  cp -- "$CLAIM" "$TMP" || die "cannot read $CLAIM"
fi

FILE_SHA="$(sha256 < "$TMP")"
FILE_BYTES="$(wc -c < "$TMP" | tr -d ' ')"
if [[ -n "$EXP_SHA" ]]; then
  [[ "$FILE_SHA" == "$EXP_SHA" && "$FILE_BYTES" == "$EXP_BYTES" ]] || \
    die "claim changed since manifest: sha256 $FILE_SHA bytes $FILE_BYTES (expected $EXP_SHA / $EXP_BYTES) — do not seal"
fi

jq -e . "$TMP" >/dev/null 2>&1 || die "claim is not valid JSON"
# Null / type checks: .entries must be a non-empty array of objects.
jq -e '(.entries | type) == "array" and (.entries | length) > 0 and all(.entries[]; type == "object")' "$TMP" >/dev/null \
  || die ".entries is null, missing, empty or not an array of objects"
TIP="$(jq -j '.ledger_anchor.tip_hash // empty' "$TMP")"
[[ "$TIP" =~ ^[0-9a-f]{64}$ ]] || die ".ledger_anchor.tip_hash missing or not 64-hex"

COUNT="$(jq -j '.entries | length' "$TMP")"
# First-entry seal, two independent canonicalizers that must agree:
#   jq -j -c -S  (sorted keys, compact, raw UTF-8, no trailing LF)
#   python json.dumps(sort_keys, (",",":"), ensure_ascii=False)
FIRST_JQ="$(jq -j -c -S '.entries[0]' "$TMP" | sha256)"
FIRST_PY="$(python3 -c 'import sys,json,hashlib;d=json.load(open(sys.argv[1],encoding="utf-8"));sys.stdout.write(hashlib.sha256(json.dumps(d["entries"][0],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest())' "$TMP")"
[[ "$FIRST_JQ" == "$FIRST_PY" ]] || die "canonicalizer disagreement on entry 0: jq $FIRST_JQ python $FIRST_PY"

# Chain walk (provenance-index rule): entry hash = sha256(json.dumps(entry
# minus index_hash, sort_keys=True, ensure_ascii=False)) with DEFAULT
# separators; prev of entry 0 = .ledger_anchor.tip_hash.
read -r HEAD PROBLEMS < <(python3 - "$TMP" <<'PY'
import sys, json, hashlib
d = json.load(open(sys.argv[1], encoding="utf-8"))
prev = d["ledger_anchor"]["tip_hash"]; bad = 0
for e in d["entries"]:
    if e.get("prev_index_hash") != prev: bad += 1
    h = hashlib.sha256(json.dumps({k: e[k] for k in sorted(e) if k != "index_hash"},
                                  sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if h != e.get("index_hash"): bad += 1
    prev = h
print(prev, bad)
PY
)
[[ "$HEAD" =~ ^[0-9a-f]{64}$ ]] || die "chain walk failed"

# Witness output and its seal: canonical JSON {"count":N,"head_hash":"..."}
# exactly — keys sorted, no spaces, no trailing newline.
OUTPUT="$(printf '{"count":%d,"head_hash":"%s"}' "$COUNT" "$HEAD")"
SEALED="$(printf '%s' "$OUTPUT" | sha256)"

DECL_COUNT="$(jq -j '.entry_count // "null"' "$TMP")"
DECL_HEAD="$(jq -j '.head_hash // "null"' "$TMP")"
CONSISTENT=true
[[ "$PROBLEMS" == "0" && "$DECL_COUNT" == "$COUNT" && "$DECL_HEAD" == "$HEAD" ]] || CONSISTENT=false

jq -n -S --argjson output "$OUTPUT" --arg sealed "$SEALED" --arg fsha "$FILE_SHA" \
  --argjson fbytes "$FILE_BYTES" --arg first "$FIRST_JQ" --argjson ok "$CONSISTENT" \
  --argjson chainprob "$PROBLEMS" \
  '{output:$output, sealed_output:$sealed, observed:{claim_sha256:$fsha, claim_bytes:$fbytes, first_entry_seal:$first}, consistent_with_declared:$ok, chain_problems:$chainprob}'
[[ "$CONSISTENT" == true ]] && exit 0 || exit 2
