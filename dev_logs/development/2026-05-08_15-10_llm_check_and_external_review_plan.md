# 2026-05-08 15:10 LLM Check And External Review Plan

## Summary

Implemented the first P0 usability improvement after reviewing external
feedback: a simple LLM provider diagnostics command.

## Changes

- Added `OpenAICompatibleAdvisor.check_connection()`.
- Added `OpenAICompatibleAdvisor.endpoint` property.
- Added `python run_simple.py --check-llm`.
- Updated README and Chinese quick-start docs.
- Added tests for endpoint resolution, provider check path, CLI arg parsing,
  disabled config, and successful fake provider check.
- Added external review action plan:
  `docs/plans/2026-05-08_EXTERNAL_REVIEW_ACTION_PLAN.md`.

## Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 192 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK

python run_simple.py --check-llm
Connection: ok
```

## Notes

The next P0 item should be structured error codes. P1 should focus on dynamic
page capability tests, site zoo expansion, and comparing local MCP crawler
capabilities for possible reuse.
