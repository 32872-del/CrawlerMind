# Acceptance: API GraphQL Training And Native Long-Run Metrics

Date: 2026-05-15

Employee: `LLM-2026-002`

Assignments:

- `SCRAPLING-HARDEN-1`
- `SCRAPLING-HARDEN-4`

Status: accepted

## Verdict

Accepted. The native async/API side now has GraphQL fixtures, 50+ item
pagination fixtures, reverse replay-risk evidence, and long-run metrics flowing
into spider summaries.

## Accepted Evidence

- `SpiderRunSummary` now carries async, proxy, backpressure, and concurrency
  metrics while preserving backward-compatible defaults.
- Native long-run stress verifies 1,000 URL execution and checkpoint summary
  roundtrip.
- GraphQL mock fixtures cover nested fields, cursor pagination, error
  responses, and rate-limit responses.
- API pagination fixtures cover page, offset, and cursor styles with 50+
  records.
- Strategy evidence now reports API/GraphQL replay blockers for signature,
  token, timestamp, nonce, encrypted payload, and rate-limit clues.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_async_runtime autonomous_crawler.tests.test_api_intercept autonomous_crawler.tests.test_graphql_training autonomous_crawler.tests.test_native_longrun_stress -v
Ran 136 tests
OK

python run_api_graphql_training_2026_05_15.py
GraphQL scenarios: 4/4 passed
API 50+ pagination: 3/3 meet threshold
Reverse evidence: 4 with replay risk, 4 with blockers
Async metrics: 100/100 succeeded

python run_native_longrun_stress_2026_05_15.py --count 1000
Succeeded: 1000
Failed: 0
Checkpoint roundtrip OK: True
Credential leak: none
```

## Follow-Up

- Add persistent async client pooling and DNS reuse.
- Add adaptive concurrency based on response health.
- Add real public GraphQL/API training cases.

