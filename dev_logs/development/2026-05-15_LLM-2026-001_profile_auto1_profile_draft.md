# PROFILE-AUTO-1: Browser Evidence to SiteProfile Draft

Date: 2026-05-15
Worker: LLM-2026-001

## Summary

New module `autonomous_crawler/runners/profile_draft.py` that converts browser/API
evidence into SiteProfile draft dicts. Supports static DOM list/detail, observed
API pagination, and mixed SSR + hydration patterns.

## Changes

| File | Change |
|---|---|
| `autonomous_crawler/runners/profile_draft.py` | New module: `draft_profile_from_evidence()` |
| `autonomous_crawler/runners/__init__.py` | Added `draft_profile_from_evidence` export |
| `autonomous_crawler/tests/test_profile_draft.py` | 39 new tests |

## Design

### Entry Point

`draft_profile_from_evidence(evidence: dict, site_name: str = "") -> dict`

Takes structured evidence (from browser training, scout_page, or recon) and
produces a SiteProfile-compatible dict.

### Inference Modules

- `_draft_selectors()` — from selector_matches, field_candidates, explicit selectors
- `_draft_api_hints()` — from captured XHR (JSON endpoints), scout_page api_hints
- `_draft_pagination_hints()` — from scroll_events (infinite_scroll), XHR params (page/offset/cursor)
- `_draft_quality_expectations()` — from rendered_item_count, html_chars, URL category inference
- `_draft_target_fields()` — from known field names in selectors + field_candidates
- `_draft_training_notes()` — from stop_reason, failure_classification, item counts

### SiteProfile Compatibility

Draft output is directly loadable via `SiteProfile.from_dict()` and compatible
with `make_ecommerce_profile_callbacks()` and `initial_requests_from_profile()`.

## Test Results

```
python -m unittest autonomous_crawler.tests.test_profile_draft -v
# 39 tests OK (5 test classes: SelectorInference, ApiHints, PaginationHints,
#   QualityExpectations, TargetFields, TrainingNotes, DraftProfileRoundTrip, DomainName)
```

## Remaining Risks

1. Selector inference is generic — complex pages may need manual refinement
2. API hints only capture GET JSON endpoints — POST/GraphQL not yet supported
3. Category inference is URL-based — may miss content-level signals
