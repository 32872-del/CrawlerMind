# Dev Log - 2026-05-04 17:16 - HTTP Executor MVP

## Goal

Move the skeleton from mock-only execution toward a real HTTP crawl loop while
keeping deterministic local tests.

## What changed

### 1. Executor now performs real HTTP fetches

- Updated `autonomous_crawler/agents/executor.py`.
- Added `httpx.Client` based GET support for `http://` and `https://` URLs.
- Added browser-like default headers and redirect following.
- HTTP failures now set `status="failed"` and append details to `error_log`.

### 2. Deterministic fixture mode

- Added `mock://products` support in the executor.
- This keeps the workflow testable without depending on network availability or
  target site markup.

### 3. Planner handles basic Chinese field keywords

- Updated `autonomous_crawler/agents/planner.py`.
- Chinese goals that mention title, price, and image now map to:
  `["title", "price", "image"]`.

### 4. Extractor confidence is bounded

- Updated `autonomous_crawler/agents/extractor.py`.
- Confidence is now calculated only from requested fields and capped at `1.0`.
- System fields such as `url`, `index`, and `link` no longer inflate the score.

### 5. Added project dependencies and tests

- Added `requirements.txt`.
- Added `autonomous_crawler/tests/test_workflow_mvp.py`.
- Tests cover:
  - Chinese field parsing
  - mock fixture execution
  - bounded extractor confidence
  - full LangGraph run with `mock://products`

## Verification

```text
python -m compileall autonomous_crawler run_skeleton.py
OK

python -m unittest discover autonomous_crawler\tests
Ran 4 tests in 0.029s
OK

python run_skeleton.py "<Chinese product title and price goal>" mock://products
Final Status: completed
Extracted 2 items
Confidence: 1.00
```

## Real HTTP smoke test

```text
python run_skeleton.py "<Chinese page title and price goal>" https://example.com
```

Result:
- Executor fetched `https://example.com` successfully: HTTP 200, 528 chars.
- Extraction failed because strategy still uses hardcoded product selectors.
- Validator retried 3 times and ended with `status="failed"`.

This is expected for now and is useful: the workflow no longer reports a fake
success for pages that do not match the current extraction strategy.

## Next recommended step

Implement Recon MVP selector inference:

1. Fetch/render page HTML.
2. Detect obvious framework and hydration markers.
3. Identify repeated DOM card-like structures.
4. Generate candidate selectors for title, price, image, and link.
5. Feed those selectors into `strategy_node` instead of hardcoded
   `.product-item` selectors.
