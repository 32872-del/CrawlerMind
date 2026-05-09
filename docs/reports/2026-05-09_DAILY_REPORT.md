# 2026-05-09 Daily Report

## Summary

Today Crawler-Mind moved further toward open-source readiness and started the
next crawl-capability layer: browser network observation. The main theme was
making the project easier for outside contributors to run while preserving the
supervisor/worker workflow for multi-LLM development.

## Completed

### Open-Source CI And Contributor Basics

Accepted from `LLM-2026-001`.

- Added GitHub Actions workflow for Python 3.11 and 3.12.
- Added compile check and standard unit-test run in CI.
- Added `CONTRIBUTING.md`.
- Added GitHub issue templates:
  - bug report
  - feature request
  - crawl target / training report
- Kept CI deterministic: no API keys and no Playwright browser smoke required.

Acceptance record:

```text
docs/team/acceptance/2026-05-09_open_source_ci_ACCEPTED.md
```

### Browser Network Observation

Implemented and accepted as an opt-in Recon capability.

New module:

```text
autonomous_crawler/tools/browser_network_observer.py
```

Current capability:

- uses Playwright response events when explicitly enabled
- captures XHR/fetch/API/GraphQL-like responses
- redacts sensitive request/response headers
- stores bounded JSON and post-data previews
- scores API candidates for later Strategy use
- gracefully reports failure when Playwright is missing or navigation fails
- integrates into Recon only when `constraints.observe_network=true`

Safety boundary:

- this is observation only
- it does not bypass login, CAPTCHA, Cloudflare, or access controls
- hostile anti-bot targets remain diagnosis-only unless an authorized workflow
  is explicitly built

QA from `LLM-2026-002` expanded the focused test file to 55 tests.

During supervisor audit, duplicate API candidate merging was tightened so the
same URL/method keeps the higher-score observation instead of the first
encountered one.

### Open-Source Docs And Onboarding Audit

Accepted from `LLM-2026-004`.

Findings:

- repository onboarding is now much easier for GitHub contributors
- Windows/Linux/macOS setup paths are present
- no-key mock path is visible
- remaining issues were mostly documentation drift

Supervisor cleanup applied:

- refreshed Worker Delta memory state
- marked the 2026-05-08 stage/blueprint analysis as historical context
- updated the team board date and renamed the mixed multi-day accepted section
  from "Accepted Work Today" to "Recent Accepted Work Log"

Acceptance record:

```text
docs/team/acceptance/2026-05-09_open_source_docs_audit_ACCEPTED.md
```

### Real-Site Training Round 4

Supervisor direct work.

Training targets:

- DummyJSON products public API
- Hacker News Algolia front page API
- GitHub CPython issues API
- Quotes to Scrape API
- Hacker News Algolia browser-network observation probe

Initial run:

- 2/5 completed
- failures exposed JSON anti-bot false positives and missing common API shapes

Fixes applied:

- JSON payloads no longer trigger HTML challenge detection just because their
  content mentions words such as `captcha`.
- `hits` and `quotes` JSON response shapes are now extracted.
- API normalization now maps common fields:
  - `points`, `num_comments`, `comments`, `rating` -> `hot_score`
  - `description`, `text`, `body`, `story_text` -> `summary`
  - `html_url` -> `link`

Final run:

- 4/5 completed
- all direct public JSON/API scenarios passed with 10 items each
- the remaining failure is the browser-network observation probe, which now
  becomes the next dynamic-page training target

Report:

```text
docs/reports/2026-05-09_REAL_SITE_TRAINING_ROUND4.md
```

### Controlled XHR-Backed SPA Network Smoke

Supervisor direct work.

Added an optional browser smoke test that serves a local SPA and a local JSON
API:

- page route: `/`
- API route: `/api/products?page=1`
- browser action: page JavaScript calls `fetch()`
- observer action: `observe_browser_network()` captures the real XHR response
  and promotes it to a JSON API candidate

This closes the gap between mocked network-observer tests and a real browser
network path. It does not depend on external sites and remains skipped in the
normal suite unless `AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1` is set.

### Rendered DOM Selector Training

Accepted from `LLM-2026-001`.

- Added HN Algolia-style rendered DOM fixtures:
  - `mock://hn-algolia`
  - `mock://hn-algolia-variant`
- Improved `infer_dom_structure()` support for:
  - CSS module class names
  - `data-testid` title/link signals
  - bare-text score patterns such as `123 points`
  - `<time datetime>` date extraction
- Added 15 focused tests in
  `autonomous_crawler/tests/test_hn_algolia_dom.py`.

Acceptance record:

```text
docs/team/acceptance/2026-05-09_rendered_dom_selector_training_ACCEPTED.md
```

### Browser Network Observation Timing QA

Accepted from `LLM-2026-002`.

The audit identified why the public HN Algolia browser-network observation
probe captured only the document response:

- `observe_browser_network()` defaults to `wait_until="domcontentloaded"`
- many SPAs fire XHR after DOMContentLoaded during hydration
- when no `wait_selector` is supplied, the observer can return before XHR
  events occur

Recommended next implementation:

- change observation default to `networkidle`
- add optional `render_time_ms` post-load delay
- leave `fetch_rendered_html()` default unchanged

Acceptance record:

```text
docs/team/acceptance/2026-05-09_network_timing_qa_ACCEPTED.md
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
Ran 55 tests
OK
```

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py run_training_round1.py run_training_round2.py run_training_round3.py
OK
```

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 336 tests
OK (skipped=4)
```

Additional training verification:

```text
python -m unittest autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_api_intercept -v
Ran 28 tests
OK

python run_training_round4.py
4 completed, 1 failed

AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
Ran 4 tests
OK

python -m unittest autonomous_crawler.tests.test_hn_algolia_dom -v
Ran 15 tests
OK
```

## Current Capability Snapshot

- Level 1 HTML pipeline: MVP complete.
- Level 2 browser rendering: MVP complete for local deterministic SPA smoke.
- Public JSON and GraphQL API collection: MVP usable.
- Optional LLM Planner/Strategy: usable from CLI and FastAPI with
  deterministic fallback.
- Browser network observation: skeleton complete, tested with mocks, and proven
  through a controlled local XHR-backed SPA smoke.
- Public JSON/API normalization: broader after round 4, including `hits`,
  `quotes`, GitHub issue links/comments, HN points, product ratings, and text
  summaries.
- Open-source onboarding: basic structure complete.

## Current Gaps

- Network observation has not yet produced API candidates on a public dynamic
  site, although it now works end-to-end on a controlled XHR-backed SPA. Timing
  QA points to `domcontentloaded` returning too early.
- API pagination/cursor handling is still shallow.
- Virtualized lists and infinite scroll still need training targets.
- Cloudflare/CAPTCHA/login-required targets remain diagnosis-only.
- FastAPI job registry is still in-memory.
- No frontend UI yet.
- Employee memory is file-based and not automatically retrieved by tooling.

## Next Recommended Work

1. Implement the observer timing fix: `networkidle` default for observation and
   optional post-load delay.
2. Retry the HN Algolia browser-network observation probe with improved timing
   and rendered DOM selector inference.
3. Continue real-site training from the ladder: dynamic pages, virtualized
   lists, then tougher anti-bot diagnosis cases.
4. Add `SECURITY.md`, PR template, and an open-source release checklist pass
   before public announcement.
5. Later P1/P2: design durable job registry and a simple frontend for API
   configuration, task submission, result viewing, and example upload.
