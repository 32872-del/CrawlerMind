# Handoff: Scrapling Executor Routing And Acceptance

Employee: LLM-2026-000
Date: 2026-05-14
Status: complete

## Summary

Supervisor mainline completed the Scrapling-first runtime integration after
workers delivered the static/parser adapter, browser/session/proxy adapter, and
docs/source-tracking audit.

Scrapling is now a real executor backend path through `engine="scrapling"`,
not only a design plan.

## Code Changes

- `autonomous_crawler/agents/planner.py`
  - Planner advisor engine preference allowlist now includes `scrapling`.
- `autonomous_crawler/agents/strategy.py`
  - Strategy advisor engine allowlist now includes `scrapling`.
  - `preferred_engine="scrapling"` generates a Scrapling-first strategy.
- `autonomous_crawler/agents/executor.py`
  - Added Scrapling runtime request construction.
  - Routes static/http Scrapling work to `ScraplingStaticRuntime.fetch()`.
  - Routes browser Scrapling work to `ScraplingBrowserRuntime.render()`.
  - Runs `ScraplingParserRuntime.parse()` for selector evidence.
  - Normalizes runtime output into `raw_html`, `visited_urls`,
    `engine_result`, `runtime_events`, `proxy_trace`, and structured failures.
- `autonomous_crawler/tests/test_scrapling_executor_routing.py`
  - Added executor routing, failure, planner, and strategy tests.

## Acceptance Completed

- LLM-2026-001 Scrapling Static + Parser Adapter accepted.
- LLM-2026-002 Scrapling Browser + Session + Proxy Runtime accepted.
- LLM-2026-004 Scrapling Runtime Docs + Source Tracking accepted.
- Supervisor Scrapling Executor Routing accepted.

Acceptance docs:

```text
docs/team/acceptance/2026-05-14_scrapling_static_parser_adapter_ACCEPTED.md
docs/team/acceptance/2026-05-14_scrapling_browser_session_proxy_runtime_ACCEPTED.md
docs/team/acceptance/2026-05-14_scrapling_runtime_docs_source_tracking_ACCEPTED.md
docs/team/acceptance/2026-05-14_scrapling_executor_routing_ACCEPTED.md
```

## Docs Updated

- `README.md`
- `PROJECT_STATUS.md`
- `docs/team/TEAM_BOARD.md`
- `docs/runbooks/README.md`
- `docs/runbooks/SCRAPLING_FIRST_RUNTIME.md`
- `docs/runbooks/ACCESS_LAYER.md`
- `docs/runbooks/ADVANCED_DIAGNOSTICS.md`
- `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md`
- `docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md`
- `docs/plans/2026-05-14_SCRAPLING_FIRST_RUNTIME_PLAN.md`
- `docs/governance/CRAWLING_GOVERNANCE.md`

Capability docs now focus on engineering capability, runtime shape, maturity,
training needs, and next development tasks. Governance/use-policy language has
been moved to `docs/governance/CRAWLING_GOVERNANCE.md`.

## Verification

Focused:

```text
python -m unittest autonomous_crawler.tests.test_scrapling_executor_routing autonomous_crawler.tests.test_scrapling_static_runtime autonomous_crawler.tests.test_scrapling_parser_runtime autonomous_crawler.tests.test_scrapling_browser_runtime_contract autonomous_crawler.tests.test_scrapling_proxy_runtime_contract autonomous_crawler.tests.test_runtime_protocols -v
Ran 162 tests
OK
```

Full:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1273 tests in 68.160s
OK (skipped=4)
```

Compile:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py clm.py
OK
```

## Next Recommended Assignment Batch

1. Real Scrapling runtime training:
   - static ecommerce/list page
   - real SPA page
   - compare `engine="scrapling"` vs httpx/Playwright/fnspider
2. Scrapling spider/checkpoint adapter into BatchRunner.
3. JS AST + hook/sandbox MVP for signature-function localization.
4. Real proxy provider adapter template and BatchRunner proxy metrics.
5. VisualRecon/OCR MVP on persisted screenshots.
