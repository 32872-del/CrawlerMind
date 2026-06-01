# 2026-05-20 Supervisor Memory - Backend Replay

## Saved Context

Agentmemory MCP returned `Transport closed` twice, so this file is the local
fallback memory for the current supervisor thread.

CLM/Crawler-Mind milestone:

- POST/GraphQL replay v1 is implemented and verified.
- Native browser XHR capture preserves replay-safe request headers and bounded
  POST body previews.
- `api_replay_promotion` detects POST JSON/GraphQL product listing calls and can
  emit:
  - `api_hints.method=POST`
  - `api_hints.format=graphql`
  - `api_hints.kind=graphql`
  - `api_hints.post_json`
  - `api_hints.headers`
  - `api_hints.items_path`
  - `api_hints.field_mapping`
  - JSON body pagination hints.
- `profile_ecommerce` can create POST JSON API seed requests and increment JSON
  body pagination such as `variables.currentPage` while keeping endpoint URL
  stable.
- API patch allowlist accepts `api_hints.headers/post_json` and
  `pagination_hints.json_*` paths.

Verified:

```text
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_native_browser_runtime -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api -v
python -m unittest autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_profile_longrun autonomous_crawler.tests.test_profile_draft -v
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

Next major backend block:

- Dynamic token / signature / session replay.
- Detect volatile headers/body/query params.
- Preserve or refresh browser session state.
- Produce replay diagnostics and repair hints for signed APIs.
