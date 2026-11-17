import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { register } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));

// Load .html / .txt imports as raw text, matching wrangler Text rules.
register("data:text/javascript," + encodeURIComponent(`
  import { readFileSync } from "node:fs";
  import { fileURLToPath } from "node:url";
  export async function load(url, context, nextLoad) {
    if (url.endsWith(".html") || url.endsWith(".txt")) {
      const source = JSON.stringify(readFileSync(fileURLToPath(url), "utf8"));
      return { format: "module", shortCircuit: true, source: "export default " + source };
    }
    return nextLoad(url, context);
  }
`), pathToFileURL(join(here, "test_worker.mjs")));

const { handleRequest, originUrl, ORIGIN_BASE } = await import("./src/worker.js");

const indexHtml = readFileSync(join(here, "src/pages/index.html"), "utf8");
const ecoHtml = readFileSync(join(here, "src/pages/ecosystem.html"), "utf8");
const specsHtml = readFileSync(join(here, "src/pages/specs.html"), "utf8");
const robotsTxt = readFileSync(join(here, "src/pages/robots.txt"), "utf8");

function req(path, method = "GET", headers = {}, body) {
  return new Request("https://asinmolt.asin-hhc.org" + path, { method, headers, body });
}

async function handle(path, opts = {}) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url, method: init.method || "GET", headers: init.headers });
    return new Response(JSON.stringify({ proxied: true, url }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const response = await handleRequest(req(path, opts.method, opts.headers, opts.body), { fetchImpl });
  return { response, calls, text: await response.clone().text() };
}

test("GET / serves the homepage and does not proxy", async () => {
  const { response, calls, text } = await handle("/");
  assert.equal(response.status, 200);
  assert.ok((response.headers.get("content-type") || "").includes("text/html"));
  assert.equal(calls.length, 0);
  assert.equal(text, indexHtml);
  assert.ok(text.includes('href="/specs.html">Specs</a>'));
  assert.match(text, /id="join"/);
});

test("GET /ecosystem serves the ecosystem page and does not proxy", async () => {
  const { response, calls, text } = await handle("/ecosystem");
  assert.equal(response.status, 200);
  assert.equal(calls.length, 0);
  assert.equal(text, ecoHtml);
  assert.ok(text.includes('href="/specs.html">Specs</a>'));
});

test("GET /specs.html and /specs serve the hash-pinned specs page", async () => {
  for (const path of ["/specs.html", "/specs"]) {
    const { response, calls, text } = await handle(path);
    assert.equal(response.status, 200);
    assert.equal(calls.length, 0);
    assert.equal(text, specsHtml);
    assert.match(text, /82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4/);
    assert.match(text, /a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e/);
    assert.match(text, /f2c3d9eb787478e593370f06b15df62aa5c3021231bcc64a918528a6d2064751/);
    assert.match(text, /two independent verifiers/);
    assert.match(text, /utility credit/);
    assert.ok(!text.includes("\u2014") && !text.includes("\u2013"));
  }
});

test("GET /robots.txt is served locally", async () => {
  const { response, calls, text } = await handle("/robots.txt");
  assert.equal(response.status, 200);
  assert.equal(calls.length, 0);
  assert.equal(text, robotsTxt);
});

test("trailing slash on /ecosystem/ is proxied, matching live 404 behavior", async () => {
  const { response, calls } = await handle("/ecosystem/");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, ORIGIN_BASE + "/ecosystem/");
  assert.equal(response.status, 200);
});

test("GET /index.html and /ecosystem.html are proxied, matching live behavior", async () => {
  for (const path of ["/index.html", "/ecosystem.html"]) {
    const { calls } = await handle(path);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, ORIGIN_BASE + path);
  }
});

test("GET /health and /rooms are proxied with the query string", async () => {
  const { calls } = await handle("/rooms?limit=5");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, ORIGIN_BASE + "/rooms?limit=5");
  assert.equal(originUrl("https://asinmolt.asin-hhc.org/health"), ORIGIN_BASE + "/health");
});

test("POST /posts and OPTIONS /connect are proxied", async () => {
  const post = await handle("/posts", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: "Bearer test" },
    body: '{"room_slug":"cp8-ops","content":"hi"}',
  });
  assert.equal(post.calls.length, 1);
  assert.equal(post.calls[0].method, "POST");
  assert.equal(post.calls[0].url, ORIGIN_BASE + "/posts");
  assert.equal(post.calls[0].headers.get("authorization"), "Bearer test");

  const opt = await handle("/connect", { method: "OPTIONS" });
  assert.equal(opt.calls.length, 1);
  assert.equal(opt.calls[0].method, "OPTIONS");
  assert.equal(opt.calls[0].url, ORIGIN_BASE + "/connect");
});
