# MCP Python Tools Benchmark — 2026-11-10 (measured on this VM)

Defensive evaluation only. No sandbox-escape, covert-channel, or exploit
work was done. No paid APIs, no new accounts, no credentials anywhere.
Nothing was published or submitted.

## Environment
- VM: Python 3.12.3, 4 vCPU, ~8 GB RAM. Fresh venv per framework where noted.
- PyPI reachable only through the VM's egress proxy (60 s CONNECT cap);
  every install needed retries (`RemoteDisconnected`) but all six PyPI
  installs eventually succeeded — except where noted below.
- Identical test server in every framework where feasible: three tools —
  `echo(text)`, `add(a, b)`, `read_file(path)` sandboxed to `scratch/`
  (rejects `..` and absolute paths outside the dir). The server treats
  instruction-like text in arguments/file contents as inert data.
- Harness: `harness.py` drives the server over stdio JSON-RPC, 20 timed
  `add` calls; cold start = spawn → first `initialize` response;
  peak RSS = VmHWM. Clean runs (no concurrent pip) are the reported
  numbers; the first FastMCP run was taken while pip was installing and
  is kept in `results/fastmcp.json` for comparison.

## Measured comparison table

| Tool | Role (real) | Version | Install from PyPI | Server LOC (total / code) | Cold start | add latency median (20 calls) | Peak RSS | Deterministic evals E1–E3 |
|---|---|---|---|---|---|---|---|---|
| **FastMCP** | server framework | 4.1.7 | OK (with retries) | 41 / 24 | **3,232 ms** | **3.23 ms** | **92 MB** | 3/3 PASS |
| **stdlib baseline** (our moltbook-mcp style, no framework) | server framework | — (stdlib) | n/a | 93 / 74 | **72 ms** | **0.09 ms** | **12 MB** | 3/3 PASS |
| **mcp-use** | client/agent library | 1.7.1 | OK (with retries) | n/a — client-only, cannot build a server | unmeasured as server | 1.05 ms median as **client** calling the stdlib server (connect 112 ms) | unmeasured | n/a (traversal refused through client: yes) |
| **mcp-agent** | agent framework | 0.2.6 | OK (with retries) | n/a — client/agent only | **unmeasured — hangs** | unmeasured | unmeasured | unmeasured |
| **ContextForge** (gateway) | gateway | — | **FAILED** — no `mcpgateway` distribution on PyPI; `contextforge` 1.0.4 on PyPI is an unrelated "code prompt generator", not the gateway | n/a | unmeasured | unmeasured | unmeasured | unmeasured |
| **MCP-Scan** | security scanner | 0.4.3 → snyk-agent-scan 0.6.11 | OK (redirect package) | n/a | n/a | n/a | n/a | see §3 |
| **mcp-eval** | eval framework | PyPI 0.0.1 = stub; real: mcpevals 0.1.10 from GitHub | PyPI copy is a stub (see §4) | n/a | n/a | n/a | n/a | agent evals: run 1: 3/3, run 2: 1/3 (see §4) |

"Unmeasured" means the measurement could not be taken in this environment
for the stated reason — not zero, not estimated.

## 1. FastMCP vs stdlib — the only true server comparison
- FastMCP cuts server code ~3× (24 vs 74 code lines for the same three
  tools) and gives typed schemas, validation, and error surfacing for free.
- It costs ~45× cold start (3,232 ms vs 72 ms), ~36× per-call latency
  (3.23 ms vs 0.09 ms), and ~8× memory (92 MB vs 12 MB). In absolute
  terms 3 ms/call is fine for our workloads; the 3.2 s cold start only
  matters for short-lived or frequently restarted servers.
- Both servers pass all deterministic evals (E1 correctness, E2 traversal
  refusal, E3 injection-inert). The security properties live in the tool
  code, not the framework — FastMCP adds no defence by itself.
- **Dependency conflict found:** installing mcp-agent into the same venv
  pulls `mcp` 1.30.0, which **breaks FastMCP 4.1.7 at import**
  (`ModuleNotFoundError: mcp.server.request_state`; FastMCP needs the
  `mcp` 2.x line it ships as fastmcp-slim). FastMCP and mcp-agent
  **cannot coexist in one venv**. A clean FastMCP-only venv
  (`venv-fastmcp/`, 116 MB) reproduces all numbers above.

## 2. The other four are not server frameworks
- **mcp-use 1.7.1** is client-side. As a client it works: connects to the
  stdlib server in 112 ms, median call 1.05 ms (about 1 ms of client
  overhead over the server's 0.09 ms), and the server's traversal refusal
  holds through it. Its agent features need an LLM key; only the raw
  session calls were measured here.
- **mcp-agent 0.2.6** could not be measured at all in this environment:
  (a) its `MCPAggregator.list_tools()` hangs indefinitely against our
  stdlib server (probed with a 30 s timeout, twice; the connection itself
  comes up fine); (b) against the FastMCP server it fails with the
  `mcp.server.request_state` import error above; (c) its `MCPApp`
  startup crashes unless the VM's `NO_PROXY` env var (which contains
  bare `[::1]` entries) is unset — httpx cannot parse it. Agent
  workflows additionally need a paid LLM key. Verdict: not usable here
  without upstream fixes or a pinned `mcp` SDK version.
- **ContextForge** (the gateway) is not installable from PyPI. The
  `mcpgateway` name has no distribution; `contextforge` 1.0.4 is a
  different tool entirely. The real gateway is distributed via Docker /
  GitHub and was not installed (out of scope for a PyPI benchmark).
- **MCP-Scan**: see §3. **mcp-eval**: see §4.

## 3. MCP-Scan against moltbook-mcp
- `mcp-scan` 0.4.3 on PyPI is a redirect package that installs
  `snyk-agent-scan` 0.6.11. Its `inspect` subcommand works offline and
  enumerated moltbook-mcp's 4 tools (`moltbook_connect`, `moltbook_post`,
  `moltbook_read`, `moltbook_identities`).
- The full `scan` analysis **refuses to run without `SNYK_TOKEN`** — a
  Snyk account and API token. No new account was created, so **no
  automated scan result exists**.
- Manual review instead — full write-up in
  [moltbook-mcp-security-review.md](sandbox://workspace/mcp-benchmark/moltbook-mcp-security-review.md).
  Headline: no tool-poisoning payload in any tool description (clean
  baseline). Three operational fixes owed, all server-side, none needing
  a framework change:
  1. (medium) `moltbook_connect` returns the bearer token in plain tool
     output — return a handle instead.
  2. (low) `KNOWN_ROOMS` exists but is never enforced — validate the room
     before calling the API.
  3. (low) no content-length or rate cap on `moltbook_post`.

## 4. mcp-eval
- **PyPI `mcp-eval` 0.0.1 is a stub** — its entire program prints
  "Hello from mcp-eval!". The real framework is `mcpevals` 0.1.10
  (lastmile-ai/mcp-eval on GitHub), installed from git; it works and is
  pytest-based with `ToolWasCalled`, `ResponseContains`, etc.
- Evals written: `evals/test_bench_mcpeval.py` (3 agent-driven tests) plus
  the framework-free deterministic suite `evals/run_evals.py` (E1–E3).
- Agent-driven evals ran on the **local Ollama model asin-qwen0.5b**
  (free, no API key) via mcp-agent's Ollama provider. Results are
  **not reproducible with this model**: run 1 passed 3/3, run 2 passed
  1/3 — the agent twice returned empty responses and never called a tool
  (`ToolWasCalled: expected >= 1, got 0`). The server is not at fault:
  the deterministic evals pass 3/3 on both servers, repeatably.
  Conclusion: agent-driven evals need a ≥7B model to be stable (a 7B Q4
  fits a P106-100 from the GPU fleet). Also note mcp-eval's own summary
  and pytest's summary disagree when teardown errors occur — read the
  mcp-eval table, not the pytest line.
- Teardown noise: mcp-agent logs "Connection closed" errors when the
  stdio server exits; cosmetic only.

## 5. Costs observed
- Combined venv with all six tools: **859 MB** on disk. FastMCP-only
  venv: 116 MB. Stdlib server: 0 bytes of dependencies.
- Every pip install needed multiple retries through the egress proxy
  (`RemoteDisconnected`); nothing failed permanently except the
  ContextForge name lookup.

## Recommendation
**Use FastMCP for new Python MCP servers, keep the stdlib pattern for
the ones already working.** FastMCP is the only one of the six that is
actually a server framework, it cuts server code ~3×, its measured cost
(3.2 s start, 3.2 ms/call, 92 MB) is acceptable for our long-lived
servers, and it is the framework mcp-eval's own ecosystem is built
around. Keep moltbook-mcp on stdlib — it is already written, tested,
and dependency-free, and a rewrite buys nothing. Do not adopt mcp-agent
or mcp-use as server frameworks (they are not); use mcp-use only if a
raw MCP client session is needed, and skip it otherwise. Do not adopt
ContextForge until there is a real gateway need and a Docker-based
install path. For evals, keep the deterministic `evals/run_evals.py`
suite as the gate (it is repeatable and needs no model); use the real
mcp-eval only with a ≥7B local model, and fix the three moltbook-mcp
items in §3 before any registry publish. One venv per framework family:
never install mcp-agent alongside FastMCP.

## Files
- `servers/fastmcp_server.py`, `servers/stdlib_server.py` — identical test servers
- `harness.py` — stdio benchmark harness
- `clients/mcp_use_bench.py`, `clients/mcp_agent_bench.py`, `clients/mcp_agent_config.yaml` — client benchmarks (mcp-agent: unmeasured, hangs)
- `evals/run_evals.py` — deterministic E1–E3 suite; `evals/test_bench_mcpeval.py` + `evals/pytest.ini` — mcp-eval agent tests
- `results/` — raw JSON results and `mcp-eval-run.log`
- `moltbook-mcp-security-review.md` — manual moltbook-mcp review
- `mcp_agent.config.yaml` — eval-run agent config (local Ollama only)
- `install.log`, `contextforge-install.log`, `mcp-eval-git-install.log` — install evidence
