# 2026-05-07 16:20 - LLM Phase B/C Merge Hardening

## Goal

Harden Planner and Strategy advisor merge behavior before adding a real LLM
provider adapter.

## Changes

- Updated `autonomous_crawler/agents/planner.py`:
  - Added value-level validation for advisor output.
  - Allowed task types are `product_list` and `ranking_list`.
  - Target fields must be known extraction fields.
  - `max_items` must be a positive integer.
  - Constraints must contain scalar values.
  - Crawl preferences are limited to safe engine hints.
  - Safe `crawl_preferences` now merge into top-level state so Strategy can
    read them.

- Updated `autonomous_crawler/agents/strategy.py`:
  - Added conservative merge layer after schema validation.
  - Advisor selectors can fill missing selectors.
  - Advisor selectors can replace known fallback selectors.
  - Strong deterministic recon selectors are preserved.
  - Deterministic `max_items` is preserved on conflict.
  - Browser mode cannot be downgraded to HTTP by advisor output.
  - `llm_decisions` now records final accepted/rejected merge results.

- Updated `autonomous_crawler/tests/test_llm_advisors.py`:
  - Added Planner validation tests.
  - Added Strategy merge-priority tests.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_llm_advisors -v
Ran 41 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 142 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Next Step

Add an OpenAI-compatible provider adapter and an opt-in real LLM smoke path.
