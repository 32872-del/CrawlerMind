# Handoff: REAL-HARDEN-4 + PROFILE-AUTO-1 + Profile Draft Training Smoke

Date: 2026-05-15
Worker: LLM-2026-001
Status: Complete

## REAL-HARDEN-4: Dynamic/Virtual List Training Enhancement

Extended harness with 3 new public dynamic list targets and `stop_reason` field.

| Target | Type | Items | HTML | stop_reason |
|---|---|---|---|---|
| ScrapeThisSite AJAX | Click-driven AJAX | 6 | 15k | completed |
| DummyJSON Products | SSR product list | 0 | 44k | no_items_matched |
| ScrapeThisSite Countries | Static list | 250 | 205k | completed |

Evidence: `dev_logs/training/2026-05-15_real_harden4_dynamic_list_training.json`

Files changed:
- `run_browser_scenario_training_2026_05_15.py` — stop_reason, 3 new scenarios
- `autonomous_crawler/tests/test_browser_scenario_training.py` — +8 tests

## PROFILE-AUTO-1: Browser Evidence → SiteProfile Draft

New module converting browser/API evidence to SiteProfile draft dicts.

Supports: static DOM list/detail, observed API pagination, mixed SSR + hydration.

Files changed:
- `autonomous_crawler/runners/profile_draft.py` — new module
- `autonomous_crawler/runners/__init__.py` — added export
- `autonomous_crawler/tests/test_profile_draft.py` — +39 tests

## Profile Draft Training Smoke

End-to-end: browser evidence → profile_draft → SiteProfile → profile_ecommerce runner.

**10/10 loadable, 10/10 runner compatible**

Files changed:
- `run_profile_draft_training_2026_05_15.py` — new training script
- `dev_logs/training/2026-05-15_profile_draft_training.json` — evidence

## Combined Test Results

```
python -m unittest discover -s autonomous_crawler/tests
# 2057 tests OK (5 skipped)

python -m compileall autonomous_crawler run_profile_draft_training_2026_05_15.py -q
# Clean
```

## Follow-up

- DummyJSON Products selectors need adjustment (client-side rendering)
- React Virtuoso 404 persists (documented in prior handoff)
- Draft profiles don't configure seed URLs (initial_requests=0)
- Category inference is URL-based — could use content-level signals
- API hints only capture GET JSON — POST/GraphQL not yet supported
