# Development Log: Strategy JS Evidence Advisory

Date: 2026-05-12 15:37

Owner: `LLM-2026-000`

## Goal

Make Strategy consume the new JS evidence path without letting weak JS string
signals override stronger deterministic crawl evidence.

## Work Completed

- Added `_attach_js_evidence_hints()` in `agents/strategy.py`.
- Added bounded hint extraction:
  - top endpoint strings;
  - suspicious call clues;
  - keyword categories;
  - high-score JS sources.
- Added advisory warning for challenge/fingerprint/anti-bot categories.
- Added conservative endpoint fill only when Strategy is already in
  `api_intercept` mode and lacks an endpoint.
- Added `tests/test_strategy_js_evidence.py`.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_strategy_js_evidence autonomous_crawler.tests.test_api_intercept autonomous_crawler.tests.test_access_diagnostics -v
python -m unittest discover -s autonomous_crawler/tests
```

Final result:

```text
Ran 763 tests in 50.649s
OK (skipped=4)
```

## Capability Impact

This advances:

- `CAP-5.1`: Strategy now reasons over structured evidence rather than only DOM/API heuristics.
- `CAP-2.1`: JS reverse-engineering clues become visible to downstream planning.
- `CAP-5.4`: suspicious JS categories become warnings instead of silent metadata.

## Next Step

Let QA verify that advisory hints never override stronger evidence, then tune
real-site thresholds after browser-interception training.
