# Audit: API Pagination / Cursor QA Design

Employee: LLM-2026-002
Date: 2026-05-09

## Scope

Read-only audit of api_candidates, browser_network_observer, strategy, executor,
and planner. Goal: design pagination capability acceptance boundaries and risk
inventory. No code changes.

## Current Architecture Summary

```
Planner → max_items (from user goal)
  ↓
Recon → api_candidates (from DOM hints or browser network observation)
  ↓
Strategy → pagination: {type, param} + api_endpoint + api_post_data
  ↓
Executor → fetch_json_api() ONCE → extract_records_from_json() → normalize_api_records(max_items)
```

**Critical gap:** Executor ignores `strategy["pagination"]` entirely. It fetches
one page and extracts records. `max_items` only limits records from that single
page. There is no multi-page fetch loop.

## Findings

### F-P001: No pagination loop exists (severity: medium, type: gap)

The executor's `api_intercept` path calls `fetch_json_api()` or
`fetch_graphql_api()` exactly once. The `pagination` field set by strategy is
never read by the executor.

`max_items` prevents extracting too many records from a single response, but
it cannot prevent "infinite pagination" because pagination doesn't exist yet.

**Risk:** When pagination is added, this finding becomes critical. Without
safeguards, a pagination loop could run indefinitely.

**Recommendation:** Design the pagination loop with termination guards BEFORE
implementing it. See the "Design Boundaries" section below.

### F-P002: Strategy pagination metadata is decorative (severity: low, type: gap)

Strategy outputs `"pagination": {"type": "api_offset", "param": "offset"}` for
API mode. This metadata is never consumed. It's a forward-looking design stub.

**Risk:** None today. Could mislead developers into thinking pagination works.

**Recommendation:** Add a comment in strategy noting this is future-facing.

### F-P003: POST API observed data is replayed verbatim (severity: medium, type: risk)

Flow: observer captures `post_data_preview` → strategy stores as
`api_post_data` → executor sends exact same POST body via `fetch_json_api()`.

The `post_data_preview` is truncated to 1000 chars by `_truncate()`. If the
original POST body contained pagination parameters (e.g., `{"offset": 0}`),
replaying it would always fetch page 1.

**Risk:** No pagination possible for observed POST APIs without modifying the
post body. Blindly modifying the post body is dangerous (could mutate server
state, trigger unintended actions).

**Recommendation:** POST API pagination should be explicit-strategy-only (see
Design Boundary B3).

### F-P004: No analytics/telemetry endpoint filtering (severity: medium, type: risk)

`score_network_entry()` scores API candidates by URL keywords and response
type. It does NOT filter out analytics/tracking endpoints. URLs containing
`analytics`, `tracking`, `telemetry`, `segment`, `mixpanel`, `amplitude`,
`facebook.com/tr`, `google-analytics`, `collect`, `pixel`, `beacon` are scored
normally.

If an analytics endpoint returns JSON (many do), it would be surfaced as a
high-scoring API candidate. Replaying it would send fake tracking data to the
analytics service.

**Risk:** Observed API replay could target analytics endpoints. Currently
mitigated by the fact that there's no pagination loop, so it's a single
harmless request. But with pagination, this becomes a data pollution risk.

**Recommendation:** Add analytics URL patterns to a denylist in
`_has_safe_observed_api_candidate()` or `score_network_entry()`.

### F-P005: No deduplication across pages (severity: medium, type: design gap)

`extract_records_from_json()` and `normalize_api_records()` process records
from a single response. There's no mechanism to detect duplicate records across
multiple pages.

Common duplication scenarios:
- Cursor-based APIs that return overlapping results
- Offset-based APIs where items shift between pages (new items inserted)
- APIs that return the same items when cursor is invalid

**Risk:** With pagination, duplicate records would inflate item counts and
corrupt data quality.

**Recommendation:** Design a seen-URL or seen-title dedup set for multi-page
collection.

### F-P006: No empty page / cursor-stuck termination (severity: high, type: design gap)

When pagination is added, two infinite-loop scenarios exist:

1. **Empty page loop:** API returns `{"items": []}` but includes a `next` link.
   Without an empty-page counter, the loop follows `next` forever.

2. **Cursor-stuck loop:** API returns the same cursor value (or `null` cursor
   with data). Without cursor-equality detection, the loop repeats the same
   request forever.

**Risk:** Infinite loop consuming time and resources. Not a risk today (no
pagination loop), but the HIGHEST risk for future pagination work.

**Recommendation:** Any pagination loop MUST implement:
- Empty page counter (stop after N consecutive empty pages, N=2)
- Cursor equality check (stop if cursor unchanged from previous page)
- max_pages hard cap (independent of max_items)

### F-P007: max_items scope is single-page only (severity: low, type: gap)

`normalize_api_records(records, max_items=30)` limits extraction from one
response. With multi-page pagination, `max_items` should be the total cap
across all pages. Currently it works correctly because there's only one page.

**Risk:** When pagination is added, max_items must become a running total, not
a per-page limit.

**Recommendation:** Pass max_items into the pagination loop as a remaining
budget, decrementing after each page.

### F-P008: GraphQL pagination is undefined (severity: low, type: gap)

GraphQL APIs typically use cursor-based pagination via `after` variable in the
query. The current system captures the GraphQL query as a static string. There's
no mechanism to modify GraphQL variables between pages.

**Risk:** GraphQL pagination requires modifying the `variables` dict between
requests. This is a design challenge, not a security risk.

**Recommendation:** GraphQL pagination should be explicit-strategy-only (user
provides the query template with `{{after}}` placeholder).

### F-P009: _has_safe_observed_api_candidate has no URL denylist (severity: medium, type: gap)

The safety check in strategy filters by score >= 50, status code, and kind. But
it doesn't filter by URL patterns. An analytics endpoint returning 200 JSON with
high score would pass all checks.

**Recommendation:** Add URL pattern denylist for known non-data endpoints.

## Design Boundaries for Pagination

### B1: max_items is the universal termination guard

Every pagination path MUST respect max_items as the total item budget across
all pages. If max_items is 0 (unspecified), a default max_pages cap of 10
applies.

### B2: Three pagination types need three termination strategies

| Type | Termination signal | Risk |
|---|---|---|
| **Offset/page** | Empty response OR page > max_pages | Items shift between pages |
| **Cursor/next** | Null/empty cursor OR cursor unchanged | Cursor-stuck loop |
| **hasMore boolean** | hasMore=false OR empty response | API returns hasMore=true forever |

### B3: POST JSON API pagination must be explicit-only

Observed POST APIs should NOT be automatically paginated. The post body may
contain state-mutating operations. Only explicit user strategy (via constraints
or LLM advisor) should enable POST pagination.

Rationale: GET requests are idempotent. POST requests may create, update, or
trigger actions. Automatically modifying and replaying POST bodies is unsafe.

### B4: Analytics/tracking endpoints must be denied

Any URL matching known analytics patterns should be excluded from API
candidates, or at minimum flagged as "observation-only, do not replay".

Patterns to deny:
- `analytics`, `tracking`, `telemetry`, `metrics`
- `segment.io`, `mixpanel.com`, `amplitude.com`
- `facebook.com/tr`, `google-analytics.com`
- `/collect`, `/pixel`, `/beacon`, `/event`
- `/log`, `/stats` (context-dependent)

### B5: Deduplication is required for multi-page

A seen-set of record identifiers (URL, title+source, or composite key) must
prevent duplicate records across pages. Options:
- Exact URL match (strong)
- Title + first-field hash (medium)
- Record content hash (strong but expensive)

### B6: Diagnosis-only modes must NOT paginate

The following must remain single-page observation:
- `observe_browser_network()` — observes one page load
- `_has_safe_observed_api_candidate()` — validates candidate safety
- Recon phase — discovers candidates, doesn't collect data

Pagination belongs ONLY in the executor phase, under explicit strategy control.

## Recommended Test Cases (for future implementation)

| ID | Scenario | Expected behavior |
|---|---|---|
| T-PAG-001 | API returns `{"items": [...], "next": "url"}` with max_items=30 | Fetch pages until 30 items or empty page |
| T-PAG-002 | API returns `{"items": [], "next": "url"}` on page 2 | Stop after 2 consecutive empty pages |
| T-PAG-003 | API returns `{"items": [...], "cursor": "abc"}` then same cursor | Stop when cursor unchanged |
| T-PAG-004 | API returns `{"items": [...], "hasMore": true}` forever | Stop at max_pages cap |
| T-PAG-005 | POST API observed, no explicit pagination strategy | Single fetch only, no pagination |
| T-PAG-006 | Analytics URL in api_candidates | Filtered out or flagged diagnosis-only |
| T-PAG-007 | Duplicate records across pages | Dedup set prevents duplicates |
| T-PAG-008 | max_items=0 (unspecified) | Default max_pages=10 applies |
| T-PAG-009 | GraphQL with cursor variable | Only if explicit strategy provides template |
| T-PAG-010 | Offset-based API with items shifting | Dedup catches overlaps |

## Summary

| Finding | Severity | Type |
|---------|----------|------|
| F-P001 No pagination loop exists | medium | gap |
| F-P002 Strategy pagination metadata decorative | low | gap |
| F-P003 POST API replayed verbatim | medium | risk |
| F-P004 No analytics endpoint filtering | medium | risk |
| F-P005 No cross-page dedup | medium | design gap |
| F-P006 No empty/cursor-stuck termination | **high** | design gap |
| F-P007 max_items is single-page only | low | gap |
| F-P008 GraphQL pagination undefined | low | gap |
| F-P009 No URL denylist in safety check | medium | gap |

**Highest severity: high** (F-P006). No immediate code risk today because
pagination doesn't exist. But this is the #1 risk for future pagination work:
an infinite loop with no termination guard.

## No Code Changed

This is a read-only design audit. No implementation files modified.
