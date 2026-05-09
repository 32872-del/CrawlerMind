# Audit: Browser Network Observation Timing QA

Employee: LLM-2026-002
Date: 2026-05-09
Assignment: Network Timing QA

## Problem Statement

Training Round 4 HN Algolia browser-network observation captured only the
document response (1 entry, 0 API candidates). The SPA's XHR/fetch requests
were missed entirely.

```text
[Recon] Network observation status=ok, entries=1, api_candidates=0
```

## Root Cause

`observe_browser_network()` uses `wait_until="domcontentloaded"` by default.
The execution flow:

```
1. page.on("response", on_response)     ← callback registered
2. page.goto(url, wait_until="domcontentloaded")
3. DOMContentLoaded fires                ← goto returns HERE
4. wait_selector="" → skipped
5. return(entries)                        ← only document captured
```

The SPA hydrates *after* DOMContentLoaded. Its fetch/XHR calls fire during
hydration (React useEffect, Vue mounted, etc.), but the observer already
returned at step 3.

The `on_response` callback itself is correct — it would capture XHR if still
listening. The issue is purely that we stop collecting too early.

## Answering the 4 Questions

### Q1: Should observer support render_time / post-load wait?

**Yes, but with nuance.**

A flat `render_time` sleep (like `browser_fetch.py`'s `render_time` parameter)
is the simplest fix and works for known-delay SPAs. But it's a blind wait —
too short misses XHR, too long wastes time.

Better: use `wait_selector` (already supported) as the primary post-load
mechanism. The observer already supports it but the caller didn't provide one.

Recommended: add `render_time_ms` as an optional post-goto/post-selector delay.
Default 0. This handles the "SPA needs ~500ms after networkidle to fire
requests" case without forcing callers to know a selector.

### Q2: Should we listen to request, response, requestfinished?

**`response` alone is sufficient for the current use case.**

- `request` fires when the request is sent — no response data yet, no
  status code, no content-type. Useful for knowing *what was requested* but
  not *what came back*.
- `response` fires when response headers arrive — has status, headers, URL.
  This is what we need for scoring and candidate building.
- `requestfinished` fires when the response body is fully loaded — same data
  as `response` but guaranteed body is available. Useful if we want to
  guarantee `response.json()` works.

Adding `request` would let us detect API URLs even if the response hasn't
arrived yet (e.g., long-polling, streaming). But for the scoring/candidate
pipeline, `response` is the right event.

**Recommendation:** Keep `response` only. Add `requestfinished` only if we
need guaranteed body access for JSON preview. Do NOT add `request` — it would
add entries without response data, breaking the scoring model.

### Q3: Should networkidle be the default for observe_network?

**Yes, for observation specifically.**

Three options compared:

| wait_until | Behavior | SPA XHR capture | Speed |
|---|---|---|---|
| `domcontentloaded` | Returns at DOM parse | Misses post-hydration XHR | Fast |
| `load` | Returns at all resources loaded | May catch some XHR | Medium |
| `networkidle` | Returns after 500ms no activity | Catches hydration XHR | Slow |

For `observe_browser_network`, the purpose is *discovering* API calls. Missing
them defeats the purpose. `networkidle` is the right default.

For `fetch_rendered_html`, `domcontentloaded` is fine — the caller just wants
rendered HTML and uses `wait_selector` for SPA content.

**Recommendation:** Change `observe_browser_network` default from
`domcontentloaded` to `networkidle`. Keep `fetch_rendered_html` on
`domcontentloaded`.

### Q4: Minimal code change for SPA failure?

**Two-line change + one parameter addition:**

1. Change default `wait_until` from `"domcontentloaded"` to `"networkidle"`.
2. Add optional `render_time_ms: int = 0` parameter. After `goto` (and after
   optional `wait_for_selector`), sleep `render_time_ms` milliseconds if > 0.

This would have caught the HN Algolia XHR because `networkidle` waits for the
SPA's fetch to complete (500ms of no new network activity).

The `render_time_ms` parameter handles edge cases where even after networkidle,
the SPA fires another wave of requests (e.g., cascading data loading).

## Detailed Findings

### F-T001: Default wait_until is wrong for observation (severity: medium)

`observe_browser_network` defaults to `domcontentloaded`. This is correct for
HTML rendering but wrong for network observation. Any SPA that hydrates after
DOMContentLoaded will have its XHR missed.

**Impact:** Real-site training Round 4 HN Algolia failure. Any React/Vue/Angular
SPA with async data loading will produce 0 API candidates.

**Fix:** Change default to `"networkidle"`.

### F-T002: No render_time parameter (severity: low)

Some SPAs have cascading data loads: initial fetch → render → second fetch.
Even `networkidle` may return after the first fetch, missing the second.

**Impact:** Edge case. Most SPAs do a single data fetch on load.

**Fix:** Add `render_time_ms` parameter (default 0).

### F-T003: wait_for_selector timing is correct (severity: info)

When `wait_selector` is provided, the observer waits for it after `goto`. This
gives the SPA time to hydrate and fire XHR. The `on_response` callback
continues collecting during this wait. This is correct behavior.

The HN Algolia case didn't provide a `wait_selector`, so this path wasn't used.

**Recommendation:** Document that callers should provide `wait_selector` for
SPAs when possible. It's more reliable than `networkidle` alone.

### F-T004: on_response callback registration timing is correct (severity: info)

The callback is registered before `goto`, so it captures all responses including
the initial document. No issue here.

### F-T005: Local XHR SPA smoke test passes (severity: info)

`test_real_browser_smoke.py::test_browser_network_observer_captures_xhr_api_candidate`
uses a local SPA with `wait_selector=".product-card"`. It passes because the
`wait_selector` gives the SPA time to fire its XHR. This confirms the observer
works correctly when timing is adequate.

## Summary

| Finding | Severity | Fix |
|---------|----------|-----|
| F-T001 Default wait_until wrong for observation | medium | Change default to networkidle |
| F-T002 No render_time parameter | low | Add render_time_ms parameter |
| F-T003 wait_for_selector timing correct | info | none |
| F-T004 on_response timing correct | info | none |
| F-T005 Local XHR smoke passes | info | none |

**Highest severity: medium.** The default `wait_until` causes SPA XHR to be
missed. Fix is a one-line default change + optional parameter addition.

## Recommended Minimal Code Change

```python
def observe_browser_network(
    url: str,
    wait_selector: str = "",
    wait_until: str = "networkidle",  # was "domcontentloaded"
    timeout_ms: int = 30000,
    max_entries: int = 50,
    capture_json_preview: bool = True,
    render_time_ms: int = 0,  # new parameter
) -> NetworkObservationResult:
    ...
    page.goto(url, wait_until=wait_until, timeout=timeout_ms)
    if wait_selector:
        page.wait_for_selector(wait_selector, timeout=timeout_ms)
    if render_time_ms > 0:
        page.wait_for_timeout(render_time_ms)
    ...
```
