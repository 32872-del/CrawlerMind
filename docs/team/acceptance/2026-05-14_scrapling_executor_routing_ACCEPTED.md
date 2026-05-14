# Acceptance: Supervisor Scrapling Executor Routing

Date: 2026-05-14

Employee: LLM-2026-000

## Result

Accepted as supervisor mainline work.

## Delivered

- Planner advisor engine preference now accepts `scrapling`.
- Strategy advisor validation accepts `scrapling`.
- `preferred_engine="scrapling"` generates a Scrapling-first strategy.
- Executor routes `engine="scrapling"` to CLM runtime adapters:
  - static/http path -> `ScraplingStaticRuntime.fetch()`
  - browser path -> `ScraplingBrowserRuntime.render()`
  - parser evidence -> `ScraplingParserRuntime.parse()`
- Runtime responses are normalized into existing workflow state:
  `raw_html`, `visited_urls`, `engine_result`, `runtime_events`,
  `proxy_trace`, and structured failure records.
- Added `autonomous_crawler/tests/test_scrapling_executor_routing.py`.
- Updated current capability docs so engineering capability is tracked in
  active docs and governance language lives separately.

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
Ran 1273 tests
OK (skipped=4)
```

## Follow-up

- Run real static + dynamic training through `engine="scrapling"`.
- Add Scrapling spider/checkpoint adapter to BatchRunner.
- Add JS AST/hook/sandbox MVP for signature-function localization.
