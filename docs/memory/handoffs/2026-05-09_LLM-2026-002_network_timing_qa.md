# Handoff: Network Timing QA

Employee: LLM-2026-002
Date: 2026-05-09

## What Was Done

Audited `observe_browser_network()` timing behavior. Identified root cause of
HN Algolia training failure: default `wait_until="domcontentloaded"` returns
before SPA hydration, missing all XHR/fetch requests.

## Root Cause

The `on_response` callback is registered correctly before `goto`. The problem
is that `goto` with `domcontentloaded` returns at DOM parse, before the SPA
framework initializes and fires data requests. The observer stops collecting
at that point.

## Recommended Code Change

In `autonomous_crawler/tools/browser_network_observer.py`:

1. Change default `wait_until` parameter from `"domcontentloaded"` to
   `"networkidle"` in `observe_browser_network()`.
2. Add `render_time_ms: int = 0` parameter.
3. After `goto` + optional `wait_for_selector`, if `render_time_ms > 0`:
   `page.wait_for_timeout(render_time_ms)`.

Do NOT change `fetch_rendered_html()` — its `domcontentloaded` default is
correct for HTML rendering use case.

## Files Created

- `docs/team/audits/2026-05-09_LLM-2026-002_NETWORK_TIMING_QA.md`
- `dev_logs/2026-05-09_12-00_network_timing_qa.md`
- `docs/memory/handoffs/2026-05-09_LLM-2026-002_network_timing_qa.md`

## No Code Changed

This was a read-only audit. No implementation or test files modified.

## For Supervisor

The fix is small and low-risk. After applying it, re-run the HN Algolia
browser-network observation scenario to verify XHR capture. The local XHR
smoke test (`test_browser_network_observer_captures_xhr_api_candidate`) should
continue to pass — it uses `wait_selector` which already provides adequate
timing.
