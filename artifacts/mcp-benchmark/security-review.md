# moltbook-mcp security review (manual — scanner analysis unavailable)

Scanner status: `mcp-scan` 0.4.3 is a redirect to `snyk-agent-scan` 0.6.11.
`snyk-agent-scan inspect` works offline and enumerated the 4 tools, but the
full analysis (`scan`) refuses to run without `SNYK_TOKEN` — a Snyk account
and API token. No new accounts were created for this benchmark, so no
automated analysis result exists. The review below is a manual read of
`~/workspace/moltbook-mcp-repo/server.py` (412 lines, stdlib only) and its
tool descriptions, against the usual tool-poisoning / prompt-injection
checklist.

## Tools (from `inspect`, verified live)
- moltbook_connect — POST /connect, registers an identity, returns a token
- moltbook_post — POST /posts, needs room + content + token
- moltbook_read — GET /rooms/{room}/posts?limit=
- moltbook_identities — GET /identities

## Findings

### F1 (medium): tool descriptions carry no trust boundary for the token
`moltbook_connect`'s description says it "Returns the identity record,
including the token to use when posting." A model that has called it once
holds a bearer token in context; nothing in the server prevents a later
prompt-injected tool call from reusing that token to post attacker-chosen
content. The token is also returned in plain tool output, so any other tool
or log sink that sees tool outputs sees the credential.
Mitigation: scope tokens per session, never print them in tool output
(return a handle instead), and require the caller to present the token only
to moltbook_post — which the server already does; the gap is the output
echo, not the check.

### F2 (low): no room allowlist enforced server-side
The description lists rooms (cp8-ops, genesis, cp8-recovery, moltbook-dev)
but `tool_moltbook_post`/`tool_moltbook_read` accept ANY room string; the
server never checks it against KNOWN_ROOMS (the constant exists but is
unused). A prompt-injected call could post to a room the operator never
intended, or probe arbitrary slugs.
Mitigation: validate `room in KNOWN_ROOMS` before the API call.

### F3 (low): no content-length or rate limit
`moltbook_post` forwards arbitrary-length content with no cap and no
per-token rate limit. A compromised agent (or a prompt-injected one) can
spam the network in a loop. Mitigation: cap content length (e.g. 2000
chars) and add a per-minute call budget.

### F4 (info): descriptions are clean of injection payloads
No tool description contains instructions to the model ("ignore previous
instructions", "you must", hidden directives, URLs, or credential-like
strings). The descriptions are short, factual, and contain no
tool-poisoning payload. This is the correct baseline — keep it that way
when adding tools.

### F5 (info): error handling does not leak secrets
API errors are surfaced truncated to 500 chars; the API key (if set via
MOLTBOOK_API_KEY) is sent only as a header and never echoed. No secrets
in tool outputs. Good.

### F6 (info): no path traversal / code execution surface
The server has no file, shell, or code-execution tool. Its only I/O is
HTTPS calls to the configured API base. The attack surface is exactly the
4 tools above.

## Verdict
No tool-poisoning payload in the current descriptions. The real risks are
operational: token-in-output (F1), unenforced room allowlist (F2), and no
rate/content caps (F3). All three are small, server-side fixes — no
framework change needed.
