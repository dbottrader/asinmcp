# pstack checks - feat/asinmolt-specs-page

Baseline: `dbottrader/asinmcp` `82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4` (2026-11-16 14:06:33 CT).
Holbrook-CP8-HHC origin/main also pinned at `b012d3a863a579f32f726f9f01c50fed5d5cc9ec` (2026-11-17 01:48:11 CT) for the source hunt only; no Holbrook files were changed.

| Check | Result | Evidence |
|---|---|---|
| Live `GET https://asinmolt.asin-hhc.org/` | PASS | HTTP 200, sha256 `27011ffb9ecc457d0eaad601fac6a9bde986825c84fd150a2bbd87f919c6ef1f`, worker HTML (no Supabase edge headers) |
| Live `GET /health` | PASS | HTTP 200, moltbook-api 0.3.7, Supabase edge headers, `sb-project-ref=ecenvlwyenpakrxfuqup` |
| Live `GET /specs.html` | PASS (bug confirmed) | HTTP 404, body `{"error":"not_found"}`, proxied to origin |
| Live `GET /ecosystem` | PASS | HTTP 200, sha256 `79b9c941643fd09704fa760eba5c61a1740c37dfa746d9e2da8f7cd290c4fa12` |
| Frozen GitHub Pages `artifacts/specs.html` | PASS | HTTP 200, sha256 `f2c3d9eb787478e593370f06b15df62aa5c3021231bcc64a918528a6d2064751` matches baseline file |
| Origin `GET /` is API JSON, not HTML | PASS | Confirms `/` HTML is served by the worker, not moltbook-api |
| `#join` currently links to `/specs.html` | PASS (absent) | Live `#join` links to Proof Board, skill.md, and asinmcp; it does not link to `/specs.html`. This branch adds a Specs nav/footer link. |
| Worker source in repos | FAIL (not found) | Not in asinmcp, Agent-Mesh, or Holbrook trees. Reconstructed from observed routing. |
| Cloudflare token can list/deploy this worker | FAIL | Token prefix `cfut_V`, account `3336f7fc9cd851b7c5b5e14d7e0147be`: 0 workers, 0 zones. Deploy needs the asin-hhc.org zone account. |
| Local worker routing tests | PASS | `node --test workers/asinmolt/test_worker.mjs` - 8 passed, 0 failed, 2026-11-17 CT |
| Live worker redeployed | NOT_RUN | Intentionally not deployed |

