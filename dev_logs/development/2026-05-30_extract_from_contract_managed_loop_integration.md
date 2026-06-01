# 2026-05-30 extract_from_contract Managed Loop Integration

**Employee**: 001
**Task**: Wire `extract_from_contract` into the real AI managed crawl loop

## Summary

Completed the integration of `extract_from_contract` into the AI managed crawl
loop. The action was already partially wired (in SUPPORTED_ACTIONS, EXECUTABLE_ACTIONS,
ACTION_ALLOWED_PARAMS, _execute_extract_from_contract, and the LLM system prompt).
This change closes the remaining gaps: managed state hints and end-to-end test
coverage proving the full LLM→execute→result pipeline works.

## What Was Already Done (prior sessions)

- `extract_from_contract` in `SUPPORTED_ACTIONS`, `EXECUTABLE_ACTIONS`, `ACTION_ALLOWED_PARAMS`
- `_execute_extract_from_contract` handler in `managed_actions.py`
- `_hydrate_extract_from_contract_action` for extra_context hydration
- Deterministic plan builder includes `extract_from_contract` when `extra_context` has contract+evidence
- LLM system prompt `_MANAGED_ACTIONS_SYSTEM_PROMPT` includes `extract_from_contract` in action meanings
- Param validation for `contract` (must be dict), `evidence` (str/dict/list), `source_url`, `max_items`
- Basic tests: protocol acceptance, fixture execution, unknown strategy, missing evidence

## What This Change Adds

### Files Modified

1. **`autonomous_crawler/runners/managed_state.py`**
   - Added `_has_extraction_context(job)` helper: checks if job has extraction
     contract in `extra_context` or previous extraction results in `managed_actions`
   - Updated `_next_expected_steps()`: suggests `extract_from_contract` when
     extraction context is available

2. **`autonomous_crawler/tests/test_managed_actions.py`**
   - `test_fake_advisor_extract_from_contract_accepted_and_executed`: Simulates LLM
     outputting extract_from_contract via ManagedActionPlan.from_dict (same path as
     real LLM output). Verifies protocol acceptance, execution, and 3 extracted items.
   - `test_extraction_result_flows_into_managed_state`: Wraps execution result in a
     managed action record (same as _execute_managed_actions_for_job) and verifies
     extraction_result is accessible with correct schema, site, parser_strategy,
     item_count, and evidence.
   - `test_extract_from_contract_rejects_non_dict_contract`: contract="not a dict"
     produces validation error at protocol level.
   - `test_extract_from_contract_rejects_invalid_evidence_type`: evidence=12345
     produces validation error at protocol level.
   - `test_extract_from_contract_empty_contract_rejected_at_execution`: Empty contract
     dict passes validation but fails at execution with "missing extraction contract".

## Data Flow (end-to-end)

```
Frontend POST /runs/{id}/managed-actions
  → _execute_managed_actions_for_job
    → _build_managed_action_plan_for_job
      → advisor.choose_managed_actions (LLM)
        → LLM returns {actions: [{action: "extract_from_contract", params: {contract, evidence, ...}}]}
      → ManagedActionPlan.from_dict (validates against EXECUTABLE_ACTIONS + ACTION_ALLOWED_PARAMS)
    → execute_managed_action_plan
      → _execute_extract_from_contract
        → extract_items_from_contract(evidence, contract)
        → returns {ok: True, extracted_items: [...], overrides: {extraction_result: {...}}}
    → result appended to job["managed_actions"]
  → response includes extraction_result in run_overrides
```

## Test Results

```
python -m unittest autonomous_crawler.tests.test_managed_actions -v
→ 23 tests, all OK

python -m unittest discover -s autonomous_crawler/tests
→ 2526 tests, OK (skipped=11)

python -m compileall autonomous_crawler run_simple.py run_skeleton.py run_results.py
→ clean
```

## Coverage Matrix

| Requirement | Test | Status |
|---|---|---|
| AI action plan outputs extract_from_contract accepted | test_fake_advisor_extract_from_contract_accepted_and_executed | PASS |
| Execute Superdry fixture → 3 items | test_fake_advisor_extract_from_contract_accepted_and_executed | PASS |
| Result enters managed state | test_extraction_result_flows_into_managed_state | PASS |
| Invalid contract rejected | test_extract_from_contract_rejects_non_dict_contract | PASS |
| Invalid evidence rejected | test_extract_from_contract_rejects_invalid_evidence_type | PASS |
| Empty contract rejected at execution | test_extract_from_contract_empty_contract_rejected_at_execution | PASS |
| Missing evidence rejected | test_extract_from_contract_requires_evidence | PASS |
| Unknown strategy rejected | test_extract_from_contract_reports_unknown_strategy | PASS |
| Deterministic plan with contract | test_deterministic_plan_uses_available_extraction_contract | PASS |
| Real fixture extraction | test_execute_extract_from_contract_uses_real_superdry_fixture | PASS |

## Risks

- **Large evidence payloads**: HTML evidence can be large (15KB+ for Superdry).
  The sanitization caps at 500KB for string evidence. Production LLM context
  windows may struggle with large evidence in the action params. Mitigation:
  pass evidence via extra_context, not inline in the action plan.
- **Contract drift**: If fixture contracts change format, the extraction will
  fail at runtime. Mitigation: the error is surfaced in the action result.
- **LLM reliability**: The LLM must correctly populate contract + evidence in
  the action params. In practice, the deterministic plan builder is more
  reliable since it reads from extra_context. The LLM path is best used when
  the managed state already contains the contract.

## Next Steps

1. Wire `extract_from_contract` into the workbench frontend action timeline
   so users can see extraction results in the UI.
2. Add Nike and M&S fixture tests to `test_managed_actions.py` for the other
   two extractor patterns.
3. Connect extraction results to the export pipeline so extracted items can
   be directly exported without a full crawl run.
4. Consider auto-injecting extraction contracts from the site profile when
   the managed state has a known parser_strategy.
