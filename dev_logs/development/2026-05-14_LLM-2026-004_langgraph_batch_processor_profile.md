# 2026-05-14 LLM-2026-004 LangGraph Batch Processor And Site Profile Schema

## Summary

- Added `SiteProfile` as an explicit CLM site/crawl profile schema with JSON load/save support.
- Added `LangGraphBatchProcessor` so `BatchRunner` can execute the existing LangGraph crawl workflow through the long-running runner contract.
- Exported both additions from `autonomous_crawler.runners`.
- Added deterministic tests for profile round-trip, profile-to-state injection, pause/resume through `BatchRunner`, and retryable LangGraph failure mapping.

## Files Changed

- `autonomous_crawler/runners/site_profile.py`
- `autonomous_crawler/runners/langgraph_processor.py`
- `autonomous_crawler/runners/__init__.py`
- `autonomous_crawler/tests/test_spider_runner.py`

## Adapter Design

- `LangGraphBatchProcessor` accepts `user_goal`, optional `SiteProfile` or `profile_path`, retry configuration, and an optional graph object for deterministic tests.
- For each frontier item it builds a LangGraph state with `user_goal`, `target_url`, retry fields, `recon_report`, and `crawl_preferences`.
- If a profile is present, the profile injects selectors, target fields, API/pagination/access/rate/quality hints, and training notes into explicit state fields.
- The final LangGraph state is converted back into `ItemProcessResult`, preserving workflow status, validation result, messages, task id, and profile metadata.

## Verification

- `python -m unittest autonomous_crawler.tests.test_spider_runner -v` passed: 10 tests.
- `python -m unittest discover -s autonomous_crawler/tests` passed: 1725 tests, 5 skipped.
- `python -m compileall autonomous_crawler` passed.

## Notes

- The pause/resume test uses a deterministic fake graph with HTTP URLs so it stays offline while still exercising `URLFrontier -> BatchRunner -> LangGraphBatchProcessor`.
- Real ecommerce integration still needs profile-driven record builders, detail/list selectors, and output evidence. This is now covered by the Round 2 assignment.
