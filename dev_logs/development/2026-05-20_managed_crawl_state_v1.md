# 2026-05-20 Managed Crawl State v1

## Scope

Implemented the first concrete step of `AI Managed Crawl Loop v2`:
`ManagedCrawlState`.

Goal: turn scattered job/profile/evidence/runtime information into one unified
state packet that both the frontend and future AI action planners can consume.

## What Changed

- Added `autonomous_crawler/runners/managed_state.py`.
  - `ManagedCrawlState`
  - `build_managed_crawl_state(job)`
  - `compact_managed_state_for_llm(state)`
- Exported the new helpers from `autonomous_crawler/runners/__init__.py`.
- Extended `autonomous_crawler/api/app.py`:
  - `/runs/{task_id}/status` now returns `managed_state` and
    `managed_llm_context`
  - added `/runs/{task_id}/managed-state`
- Added focused tests in
  `autonomous_crawler/tests/test_product_workflow_api.py`.

## What The State Contains

- task / user input / workflow summary
- input snapshot
- profile snapshot
- progress summary
- evidence pack
- quality context
- runtime context
- decision context
- action context
- repair context
- export context
- event timeline

## Verification

Ran:

```text
python -B -m unittest autonomous_crawler.tests.test_product_workflow_api autonomous_crawler.tests.test_api_replay_runtime autonomous_crawler.tests.test_replay_diagnostics autonomous_crawler.tests.test_managed_actions -v
python -B -m compileall autonomous_crawler -q
```

Result: OK.

## Notes

This is not a new crawler path. It is a state consolidation layer for the
existing managed workflow. The next steps are action-plan protocol and action
executor wiring.
