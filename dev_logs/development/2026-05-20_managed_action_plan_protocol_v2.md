# 2026-05-20 Managed Action Plan Protocol v2

## Scope

Implemented Step 2 of `AI Managed Crawl Loop v2`: a structured action-plan protocol that turns LLM output into validated executable actions.

## What Changed

- Expanded the managed action tool space with canonical intent names:
  - `analyze_site`
  - `select_catalog`
  - `resolve_fields`
  - `switch_runtime`
  - `patch_profile`
  - `patch_selector`
  - `promote_xhr_to_api`
  - `apply_replay_runtime`
  - `run_test`
  - `rerun_failed`
  - `export_results`
- Added a protocol versioned plan shape: `managed-action-plan/v2`.
- Added strict alias mapping from canonical intent names to executable backend actions.
- Added bounded validation for:
  - action names
  - priorities
  - runtime mode
  - `wait_until`
  - export format
  - field lists
  - selector strings
  - profile patches
- Added `patch_profile` as an executable action so validated AI output can directly produce safe profile overrides.
- Added protocol validation metadata on `ManagedActionPlan`:
  - accepted / rejected records
  - fallback usage
  - accepted parameter keys
- Updated the managed action LLM prompt to request structured output against the unified managed crawl context.
- Updated the managed actions API path to pass `managed_state` and `managed_llm_context` to the advisor.
- Added tests covering:
  - canonical alias acceptance
  - unsafe action rejection
  - bounded profile patch sanitization
  - multi-action plan validation trace
  - API wiring of unified managed state into the LLM advisor

## Result

The LLM layer no longer sees a loose bag of fields. It now receives the unified managed crawl packet and must produce a bounded action plan that the backend can validate before execution.

## Verification

Ran:

```text
python -B -m unittest autonomous_crawler.tests.test_managed_actions -v
python -B -m unittest autonomous_crawler.tests.test_product_workflow_api -v
python -B -m unittest autonomous_crawler.tests.test_openai_compatible_llm -v
python -B -m compileall autonomous_crawler -q
```

Result: OK.

## Notes

This is still not the executor layer yet. It is the protocol gate that makes the next step safe: action execution, failure repair, and rerun wiring.
