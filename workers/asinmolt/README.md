# ASINMOLT Cloudflare Worker

Public front door for `https://asinmolt.asin-hhc.org`.

This directory is a reconstruction of the live worker plus a new `/specs.html`
page. The live worker source was not found in `dbottrader/asinmcp`,
`ASIN-HHC-Agent-Mesh`, or `Holbrook-CP8-HHC`. Observed routing on 2026-11-17
(CT) was:

- `GET /` and `GET /ecosystem` return static HTML from the worker
- every other path is proxied to
  `https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api`
- `GET /specs.html` was falling through to the origin and returning 404

The current homepage `#join` section does not link to `/specs.html`. This
branch adds the page and puts a Specs link in the `/` and `/ecosystem` nav
and footer. The specs page cites frozen files from `asinmcp` commit
`82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4` and does not invent new spec text.

`$HHC` is a utility credit for verified work, never an investment.

## Do not deploy from the box token

The Cloudflare API token at `/workspace/.secrets/cloudflare_api_token`
(prefix `cfut_V`, account `3336f7fc9cd851b7c5b5e14d7e0147be`) is active, but
it listed 0 workers and 0 zones. It cannot publish this site. Use a token
on the Cloudflare account that holds the `asin-hhc.org` zone.

## Exact deploy command (Dennis only, after review)

From a checkout of this branch:

```bash
cd workers/asinmolt
CLOUDFLARE_API_TOKEN=<token-for-the-asin-hhc.org-zone-account> npx wrangler deploy
```

If the custom domain is not already bound to the `asinmolt` worker after
that deploy, add the route explicitly:

```bash
cd workers/asinmolt
CLOUDFLARE_API_TOKEN=<token-for-the-asin-hhc.org-zone-account> npx wrangler deploy --routes "asinmolt.asin-hhc.org/*"
```

Do not run either command until Dennis has reviewed this branch. A deploy
overwrites the live front door. Confirm the live worker has no unpublished
routes beyond `/`, `/ecosystem`, and `/robots.txt` before replacing it.

## Local checks

```bash
node --test workers/asinmolt/test_worker.mjs
```

The test stubs `fetch` and does not call Cloudflare or the live origin.
