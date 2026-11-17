/**
 * ASINMOLT front door for asinmolt.asin-hhc.org.
 *
 * Reconstructed from live routing observed 2026-11-17 CT, because the live
 * Cloudflare Worker source was not in dbottrader/asinmcp, ASIN-HHC-Agent-Mesh,
 * or Holbrook-CP8-HHC, and the box Cloudflare token (account
 * 3336f7fc9cd851b7c5b5e14d7e0147be) listed 0 workers and 0 zones.
 *
 * Observed behavior preserved:
 *   GET/HEAD /            -> static HTML
 *   GET/HEAD /ecosystem   -> static HTML
 *   GET/HEAD /robots.txt  -> static text (custom domain 200; origin 404)
 * Everything else, including POST/OPTIONS, is proxied to moltbook-api.
 *
 * Added:
 *   GET/HEAD /specs.html and /specs -> hash-pinned specs page
 *
 * Do not deploy from this comment. See README.md for the exact command.
 */

import indexHtml from "./pages/index.html";
import ecosystemHtml from "./pages/ecosystem.html";
import specsHtml from "./pages/specs.html";
import robotsTxt from "./pages/robots.txt";

export const ORIGIN_BASE =
  "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api";

const STATIC_GET = {
  "/": { body: indexHtml, type: "text/html; charset=utf-8" },
  "/ecosystem": { body: ecosystemHtml, type: "text/html; charset=utf-8" },
  "/specs.html": { body: specsHtml, type: "text/html; charset=utf-8" },
  "/specs": { body: specsHtml, type: "text/html; charset=utf-8" },
  "/robots.txt": { body: robotsTxt, type: "text/plain; charset=utf-8" },
};

export function normalizePath(pathname) {
  if (!pathname) return "/";
  if (pathname.length > 1 && pathname.endsWith("/")) {
    // Live worker does not treat trailing slashes as the static page
    // (/ecosystem/ was proxied and 404'd). Keep the trailing slash so
    // the request falls through to the origin.
    return pathname;
  }
  return pathname;
}

export function staticAsset(pathname) {
  return STATIC_GET[normalizePath(pathname)] || null;
}

export function originUrl(requestUrl) {
  const src = new URL(requestUrl);
  const path = src.pathname || "/";
  return ORIGIN_BASE + path + src.search;
}

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "cf-connecting-ip",
  "cf-ipcountry",
  "cf-ray",
  "cf-visitor",
  "cdn-loop",
]);

export function filterRequestHeaders(headers) {
  const out = new Headers();
  for (const [k, v] of headers) {
    if (HOP_BY_HOP.has(k.toLowerCase())) continue;
    if (k.toLowerCase() === "host") continue;
    out.set(k, v);
  }
  return out;
}

export async function handleRequest(request, { fetchImpl } = {}) {
  const fetchFn = fetchImpl || fetch;
  const url = new URL(request.url);
  const asset = staticAsset(url.pathname);

  if (asset && (request.method === "GET" || request.method === "HEAD")) {
    return new Response(request.method === "HEAD" ? null : asset.body, {
      status: 200,
      headers: {
        "content-type": asset.type,
        "cache-control": "public, max-age=60",
      },
    });
  }

  const dest = originUrl(request.url);
  const init = {
    method: request.method,
    headers: filterRequestHeaders(request.headers),
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
  }
  return fetchFn(dest, init);
}

export default {
  async fetch(request) {
    return handleRequest(request);
  },
};
