# Profile Draft Training Smoke (Round 3)

Date: 2026-05-15
Worker: LLM-2026-001

## Summary

End-to-end smoke test: browser evidence → profile_draft → SiteProfile →
profile_ecommerce runner. All 10 browser training evidence entries produce
loadable, runner-compatible profile drafts.

## Changes

| File | Change |
|---|---|
| `run_profile_draft_training_2026_05_15.py` | New training script |
| `dev_logs/training/2026-05-15_profile_draft_training.json` | Evidence output |

## Results

| Source | Loadable | Runner Compatible | Selectors | Fields |
|---|---|---|---|---|
| Infinite Scroll Fixture | OK | OK | 3 | 2 |
| Virtualized List Fixture | OK | OK | 2 | 1 |
| Mobile Viewport Fixture | OK | OK | 3 | 1 |
| React Virtuoso | OK | OK | 0 | 0 |
| Vue Examples | OK | OK | 2 | 1 |
| React Learn | OK | OK | 2 | 1 |
| TanStack Virtual | OK | OK | 1 | 0 |
| ScrapeThisSite AJAX | OK | OK | 1 | 1 |
| DummyJSON Products | OK | OK | 0 | 0 |
| ScrapeThisSite Countries | OK | OK | 3 | 1 |

**10/10 loadable, 10/10 runner compatible**

## Test Results

```
python -m unittest discover -s autonomous_crawler/tests
# 2057 tests OK (5 skipped)

python -m compileall autonomous_crawler run_profile_draft_training_2026_05_15.py -q
# Clean
```

## Evidence

`dev_logs/training/2026-05-15_profile_draft_training.json`

## Remaining Risks

1. initial_requests_generated is 0 — draft profiles don't configure seed URLs
2. Draft selectors are best-effort — production profiles need manual review
3. No automatic profile persistence — callers must save explicitly
