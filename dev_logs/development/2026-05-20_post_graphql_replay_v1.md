# 2026-05-20 POST/GraphQL Replay v1

## Summary

This block extends CLM's API/XHR replay promotion from simple GET JSON
endpoints to POST JSON and GraphQL-style ecommerce listing endpoints.

The goal is backend hard capability: when the browser observes product data in
XHR/fetch traffic, CLM can preserve enough request evidence to promote that
traffic into an executable `SiteProfile`, then rerun through the product runner
without relying on DOM selectors.

## Changes

- Updated `autonomous_crawler/runtime/native_browser.py`
  - Captured XHR/fetch samples now include replay-safe request headers.
  - Captured XHR/fetch samples now include bounded `post_data_preview`.
  - Sensitive headers such as authorization are not preserved.

- Updated `autonomous_crawler/runners/api_replay_promotion.py`
  - Parses captured POST body into `api_hints.post_json`.
  - Detects GraphQL from endpoint URL or request body keys such as `query` and
    `operationName`.
  - Emits `api_hints.method=POST`, `api_hints.format=graphql`, and
    `api_hints.kind=graphql` when appropriate.
  - Preserves replay-safe request headers as `api_hints.headers`.
  - Infers JSON body pagination paths:
    - `pagination_hints.json_page_path`
    - `pagination_hints.json_page_size_path`
    - `pagination_hints.json_cursor_path`

- Updated `autonomous_crawler/runners/profile_ecommerce.py`
  - Initial API requests can now carry POST JSON and replay headers.
  - JSON body pagination keeps the endpoint URL stable and increments page
    values inside the request body.
  - Cursor pagination can replace a configured JSON cursor path from the
    previous response.

- Updated `autonomous_crawler/api/app.py`
  - Managed profile patch allowlist now accepts bounded `api_hints.headers`.
  - Managed profile patch allowlist now accepts JSON pagination paths.

- Updated evidence bridges:
  - Managed access samples preserve response preview separately from POST body.
  - Product workflow access samples preserve replay-safe request headers and POST
    body previews.

- Updated docs:
  - `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md` now documents POST/GraphQL
    replay promotion and JSON body pagination.

## Verification

Passed:

```text
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_native_browser_runtime -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api -v
python -m unittest autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_profile_longrun autonomous_crawler.tests.test_profile_draft -v
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Capability Impact

Before this block, CLM could promote product-like GET JSON XHR into API replay.
After this block, CLM can also handle a major modern ecommerce pattern:

```text
browser category page -> captured POST /graphql -> product JSON response ->
profile patch -> POST body page increment -> product runner rerun
```

This closes an important gap for Magento, headless storefronts, SPA storefronts,
and sites where pagination lives in GraphQL variables instead of URL params.

## Current Limits

- Dynamic token refresh and signed request regeneration are still separate
  reverse-engineering/runtime capabilities.
- GraphQL query rewriting is not attempted yet; CLM replays the observed body and
  only changes configured page/cursor fields.
- Header preservation is intentionally replay-safe and bounded, so some sites may
  still need a session/runtime bridge when they require volatile auth or cookies.
