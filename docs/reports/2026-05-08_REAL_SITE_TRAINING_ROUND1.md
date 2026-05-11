# 2026-05-08 Real-Site Training Round 1

## Source

User-provided training list:

```text
E:\爬虫Agent实战训练网站清单.md
```

## Feasibility Assessment

The list is useful and should become the project training ladder. For today's
safe training pass, targets were grouped as:

- Low risk: public JSON APIs, public GraphQL demo APIs, simple static pages.
- Medium risk: public API-backed sites and SSR/static pages with rate limits.
- High risk: login-required, CAPTCHA, Cloudflare challenge, device fingerprint,
  signature cracking, or account-risk targets.

Today we intentionally selected only low-risk public targets. Strong anti-bot,
login, CAPTCHA, and signature-breaking targets should be used for diagnosis and
strategy planning only until the project has explicit safety boundaries and
manual authorization workflows.

## Selected Scenarios

| Scenario | URL | Target Capability | Result |
|---|---|---|---|
| JSONPlaceholder posts | https://jsonplaceholder.typicode.com/posts | Direct JSON URL detection | Completed, 10 items |
| Reddit r/python JSON | https://www.reddit.com/r/python.json | Reddit-style `data.children[].data` extraction | Completed, 10 items |
| Countries GraphQL | https://countries.trevorblades.com | Explicit GraphQL POST query | Completed, 10 items |

Full machine-readable summary:

```text
dev_logs/training/2026-05-08_real_site_training_round1.json
```

## Code Changes From Training

- Added direct JSON target detection: if the fetched body starts with `{` or
  `[`, Recon marks it as an API target and Strategy selects `api_intercept`.
- Added GraphQL POST support through `fetch_graphql_api()`.
- Added explicit configured API/GraphQL Recon path. If caller supplies
  `constraints.graphql_query` or `constraints.api_endpoint`, Recon skips page
  rendering and passes the API configuration straight to Strategy.
- Extended JSON record extraction for Reddit-like `data.children[].data`.
- Added compact training runner:

```text
python run_training_round1.py
```

## Training Findings

1. Direct JSON APIs now work through the main graph, not a side path.
2. GraphQL works when the query is explicitly supplied.
3. GraphQL playground pages should not be browser-rendered when the endpoint
   and query are already known. This was fixed during training and reduced the
   Countries GraphQL scenario from about 35 seconds to about 2 seconds.
4. Reddit extraction is structurally successful, but field normalization is
   still generic. Future work should allow per-site or LLM-suggested field maps
   so noisy source fields can be reduced before validation/storage.

## Current Capability Level

- Static DOM: working from earlier milestones.
- Browser fallback: MVP exists, still needs more real dynamic-site training.
- Direct JSON API: now working on real public APIs.
- Public GraphQL API: now working when query is provided.
- Anti-bot/challenge handling: diagnosis only; no bypass implementation should
  be attempted without explicit safe scope.
- Login/session workflows: not implemented.

## Recommended Next Training

1. Bilibili ranking public API: train public API discovery and Chinese ranking
   normalization.
2. Douban Top250: train static pagination, rate-limit awareness, and fallback
   behavior if blocked.
3. A local or public SPA demo: train browser-rendered DOM extraction and XHR
   observation without touching hostile sites.
4. A virtualized-list demo: train scroll strategy and visible-window extraction.
