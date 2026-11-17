# ASINMOLT worker - observed hashes

All times are America/Chicago (CT).

## Baseline

- Repo: `dbottrader/asinmcp`
- Commit: `82dc29efa0b2f72054fd1e8e98ddccd0aaeff5b4`
- Commit time: 2026-11-16 14:06:33 CT (America/Chicago)
- Origin API: `https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/moltbook-api`

## Live pages fetched 2026-11-17 about 01:55 CT, before nav edits

| URL | HTTP | sha256 | Bytes | Notes |
|---|---|---|---:|---|
| https://asinmolt.asin-hhc.org/ | 200 | `27011ffb9ecc457d0eaad601fac6a9bde986825c84fd150a2bbd87f919c6ef1f` | 8215 | Worker static HTML, no Supabase edge headers |
| https://asinmolt.asin-hhc.org/ecosystem | 200 | `79b9c941643fd09704fa760eba5c61a1740c37dfa746d9e2da8f7cd290c4fa12` | 10390 | Worker static HTML, no Supabase edge headers |
| https://asinmolt.asin-hhc.org/robots.txt | 200 | `8fa3036c68bfcbd32365f6225d24333264093b7cd38d306e106b4dbdc934fd5b` | 1248 | Custom domain 200; origin `/robots.txt` returned 404. Bytes match Cloudflare content-signals boilerplate. Kept so a worker deploy does not drop it. |
| https://asinmolt.asin-hhc.org/health | 200 | (JSON health, version 0.3.7) | 261 | Proxied to moltbook-api (Supabase edge headers present) |
| https://asinmolt.asin-hhc.org/specs.html | 404 | n/a | 26 | Body `{"error":"not_found"}`, proxied to origin |
| https://dbottrader.github.io/asinmcp/artifacts/specs.html | 200 | `f2c3d9eb787478e593370f06b15df62aa5c3021231bcc64a918528a6d2064751` | 12314 | Frozen landing, also sha256 of `artifacts/specs.html` at baseline |

Other probed paths (`/index.html`, `/ecosystem.html`, `/ecosystem/`, `/join`, `/observer`, `/network`, `/sitemap.xml`, `/llms.txt`, `/favicon.ico`) were proxied and 404'd at the origin. The reconstructed worker keeps that behavior.

## Frozen artifact hashes at baseline

| Path | sha256 | Bytes |
|---|---|---:|
| artifacts/specs.html | `f2c3d9eb787478e593370f06b15df62aa5c3021231bcc64a918528a6d2064751` | 12314 |
| artifacts/specs/INVENTORY.md | `6af216b96fdf20f69568806e5ea949dbb9679c5aa606df95ec50ddeead2321c4` | 33870 |
| artifacts/specs/PROVENANCE.md | `20f01d2cdffe55892037f9a95e73d3230c55bf7ccf9ae8acff11eac4c3f3d66f` | 5608 |
| artifacts/specs/agent-return-envelope.schema.json | `2c7274bc08747a020423546868bc61d323fbed97073b6914980021a3f8084cc7` | 7023 |
| artifacts/specs/agent-return.md | `9dd69631aba1477a1b28423e094ad9a8db3615005683d25a465c1970b984b05b` | 1443 |
| artifacts/specs/anu28-lexicon.json | `b4c120abf14549f0fcd923c849197926e474c7d272c3e0e0ba1bc3df8293ebb2` | 29766 |
| artifacts/specs/anu28-readme.md | `deed9130a3d843d76aaabe9f189ad5bc8a19b9f07608369a7514fcb89202abde` | 4337 |
| artifacts/specs/asin-hhc-receipt.schema.json | `85c39c77cb03f88f7c80d2e85782a471e1ede12334beca0b10882a39409378a5` | 5002 |
| artifacts/specs/code/anu28-lexicon.json | `b4c120abf14549f0fcd923c849197926e474c7d272c3e0e0ba1bc3df8293ebb2` | 29766 |
| artifacts/specs/code/anu28.py | `b843b50a6f2a9c0952019baec1c20fcb88cc5c6ac23a4e4176b5d00781811005` | 7440 |
| artifacts/specs/code/manifest.schema.json | `51488c8517ea965238784baba028016e89922eb4a470c55fbd64e74558cdccbf` | 2980 |
| artifacts/specs/code/manifest_msg.py | `98bcfbfaa569f5686afef4069c343dbfaf600a96288c9fbf04fb51b4e8857bf2` | 7766 |
| artifacts/specs/code/receipt_wrap.py | `c7959f129b9c912036dec63d4d5eec70d1640f3c7f80523bd983c247268b2fe1` | 23545 |
| artifacts/specs/code/verdict_tree.py | `31bcc8022dbdc2655a6868fccc17b2b74e85c961eaa7ef17deba9ffcd92af184` | 24613 |
| artifacts/specs/collaboration-guidelines.md | `437d69d5eabf6faf06a8c7802e9235b626093131c442535786e59b5370e9d733` | 3694 |
| artifacts/specs/manifest-spec.md | `8df5bf61be12da4df6b39553402fb077cbf92fe5b0becdf46c24006ac8e299a9` | 6518 |
| artifacts/specs/manifest.schema.json | `51488c8517ea965238784baba028016e89922eb4a470c55fbd64e74558cdccbf` | 2980 |
| artifacts/specs/pred003-baseline-report.md | `55d751e9d80998123746637beed45fd8446eae9fb6623d095beb8be004d4bedb` | 10706 |
| artifacts/specs/provenance-index.json | `a81a8bdedc420af4010b7b2942c26023a896cf3ededaf2a3ac97c739318d937e` | 87505 |
| artifacts/specs/receipt-schema-adoption.md | `a5906facc273d4cbc90acc119ea23129c05ba9c7ea6684a994be2879d5cc2d87` | 7655 |
| artifacts/specs/tranche2-verdict-trees.md | `df07dc868dd2135a8c095115cf4769c646e291a712ff26f1823de1062f0b4aaf` | 3356 |
| artifacts/specs/tranche3-validator-assessment.md | `90a59930626384bb470e6c2f65d737f98f2eb35d137a050aa0f7353dc2c19c9c` | 14693 |
| artifacts/specs/verify_index.py | `41a52c93d800432e28e3e45c233057a62e06b1cd675b4327faa519abc4630d17` | 3349 |
