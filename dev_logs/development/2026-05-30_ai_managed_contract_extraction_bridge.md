# 2026-05-30 AI Managed Contract Extraction Bridge

## Summary

Moved `extract_from_contract` from a backend-only managed action into the AI
managed crawl loop.

## Changes

- `autonomous_crawler/llm/openai_compatible.py`
  - Added `extract_from_contract` to the managed action system prompt.
  - Prompt now tells the model to use it when a known extraction contract and
    matching evidence are available.
- `autonomous_crawler/runners/managed_actions.py`
  - Deterministic action planning now creates `extract_from_contract` when
    `extra_context` includes `extraction_contract` plus `extraction_evidence`.
  - Execution now hydrates missing contract/evidence/source URL/max item params
    from `extra_context`, so the LLM does not need to echo large HTML or JSON.
- `autonomous_crawler/runners/managed_state.py`
  - Added `extraction_context` to managed state and compact LLM context.
  - State now summarizes available extraction contracts and latest extraction
    result without dumping large evidence blobs.
- `autonomous_crawler/api/routers/runs.py`
  - Managed action LLM context now merges extraction contract/evidence summaries
    from request `extra_context`.
- `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md`
  - Documented `extract_from_contract` and frontend `extra_context` usage.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_openai_compatible_llm -v
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_ecommerce_extractors -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests -v
python -m compileall autonomous_crawler run_simple.py run_skeleton.py run_results.py
```

All passed.

## Result

The AI managed loop can now see that contract extraction is available, choose
`extract_from_contract`, and let the backend execute it using evidence supplied
through `extra_context`. The result is stored in `managed_actions`, visible via
events/status, and summarized in `managed_state.extraction_context`.

## Next

- Frontend should render `extraction_context` and extracted item samples.
- Backend should continue generating extraction contracts automatically from
  site analysis / access probes, not only from training fixtures.
