# 2026-05-09 12:00 Network Timing QA

## Summary

Audited `observe_browser_network()` timing behavior after Training Round 4
HN Algolia failure (1 entry, 0 API candidates).

## Root Cause

Default `wait_until="domcontentloaded"` returns before SPA hydration completes.
The observer's `on_response` callback is registered correctly but stops
collecting when `goto` returns — before the SPA fires its XHR/fetch.

## Key Findings

1. **Default wait_until is wrong for observation** (medium severity).
   `domcontentloaded` is correct for HTML rendering but wrong for discovering
   SPA XHR. `networkidle` should be the default for observation.

2. **on_response callback timing is correct** (info). Registered before goto,
   captures all responses while active. No issue.

3. **wait_for_selector works as post-load wait** (info). When provided, it
   gives SPAs time to hydrate. The local XHR smoke test passes because it uses
   `wait_selector=".product-card"`.

4. **No render_time parameter exists** (low). Edge case for cascading data
   loads. Add `render_time_ms` parameter (default 0).

## Recommended Fix

Two changes to `observe_browser_network()`:
- Change default `wait_until` from `"domcontentloaded"` to `"networkidle"`
- Add `render_time_ms: int = 0` parameter, call `page.wait_for_timeout()` if > 0

No changes to `fetch_rendered_html()` — its `domcontentloaded` default is
correct for HTML rendering.

## Deliverables

- `docs/team/audits/2026-05-09_LLM-2026-002_NETWORK_TIMING_QA.md` — audit report
- `dev_logs/audits/2026-05-09_12-00_network_timing_qa.md` — this log
- `docs/memory/handoffs/2026-05-09_LLM-2026-002_network_timing_qa.md` — handoff
