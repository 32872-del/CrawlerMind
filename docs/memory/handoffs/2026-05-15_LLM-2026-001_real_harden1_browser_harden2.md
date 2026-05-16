# Handoff: REAL-HARDEN-1 + BROWSER-HARDEN-2

Date: 2026-05-15
Worker: LLM-2026-001
Status: Complete

## REAL-HARDEN-1: Real Public Dynamic Browser Training

Extended harness with 3 real public SPA/doc-site targets. All produce usable evidence.

| Target | Items | HTML | Status |
|---|---|---|---|
| Vue.js Examples | 57 | 103k | OK |
| React.dev Learn | 51 | 283k | OK |
| TanStack Virtual | 2 | 256k | OK |
| React Virtuoso | 0 | 0 | FAIL (404 URL) |

Evidence: `dev_logs/training/2026-05-15_real_site_training.json`

Files changed:
- `run_browser_scenario_training_2026_05_15.py` — added 3 real target scenarios
- `autonomous_crawler/tests/test_browser_scenario_training.py` — +8 tests

## BROWSER-HARDEN-2: Profile Health Persistence / Decay

Advanced BrowserProfileHealth to windowed/decay scoring.

Key additions:
- `WindowedHealthRecord` — timestamped record for windowed scoring
- `health_score` now uses windowed records (default 300s window)
- `health_summary()` — compact summary for run reports
- `BrowserProfileHealthStore` — JSON persistence adapter
- `BrowserProfileRotator.health_summaries()` — per-profile summaries

Files changed:
- `autonomous_crawler/runtime/browser_pool.py` — windowed scoring, summary, persistence
- `autonomous_crawler/runtime/__init__.py` — added `BrowserProfileHealthStore` export
- `autonomous_crawler/tests/test_browser_pool.py` — +17 tests

## Combined Test Results

```
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_browser_scenario_training -v
# 192 tests OK

python -m compileall autonomous_crawler run_browser_scenario_training_2026_05_15.py -q
# Clean
```

## Follow-up

- Virtuoso demo URL 404 — find current URL or replace target
- Window duration (300s) may need tuning per use case
- SQLite persistence adapter for production scale
- No automatic persistence — callers must explicitly save
