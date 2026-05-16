# 2026-05-15 LLM-2026-002 — SCRAPLING-HARDEN-4: API / GraphQL / Reverse Evidence Trainer

**Task**: SCRAPLING-HARDEN-4 — use training matrix GraphQL/API/JS signature evidence scenarios to strengthen CLM's API/GraphQL/reverse evidence capabilities
**Worker**: LLM-2026-002
**Status**: COMPLETE

## Summary

Added GraphQL mock fixtures (nested fields, Relay-style cursor pagination, error responses, rate-limit responses), expanded API pagination fixtures to 50+ records for all three pagination types (page/offset/cursor), enhanced reverse evidence in StrategyEvidenceReport to detect signature/timestamp/nonce/token/encrypted payload clues in API/GraphQL candidates with replay blocker and hook/sandbox suggestions, and wired async/backpressure/proxy metrics into training output.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tools/api_candidates.py` | MODIFIED | +GraphQL mock fixtures (nested, cursor pagination, error, rate-limit), +50+ record pagination fixtures (page/offset/cursor), +`_mock_graphql_response()` helper, +`build_graphql_nested_fields_query()`, `build_graphql_cursor_query()` |
| `autonomous_crawler/tools/strategy_evidence.py` | MODIFIED | +`_api_reverse_signals()`, +`_graphql_signals()`, +`_api_replay_blocker_hints()`, updated `build_strategy_evidence_report()` to wire API/GraphQL signals, updated `build_reverse_engineering_hints()` to accept `api_candidates`, updated `has_high_crypto_replay_risk()` for new signal codes |
| `autonomous_crawler/tests/test_graphql_training.py` | NEW | 42 tests: GraphQL nested/cursor/error/rate-limit, API pagination 50+, reverse evidence signals/hints, metrics integration |
| `run_api_graphql_training_2026_05_15.py` | NEW | Training runner with GraphQL/API/reverse evidence/async metrics scenarios |
| `dev_logs/development/2026-05-15_LLM-2026-002_api_graphql_reverse_evidence_trainer.md` | NEW | This dev log |
| `docs/memory/handoffs/2026-05-15_LLM-2026-002_api_graphql_reverse_evidence_trainer.md` | NEW | Handoff |

## GraphQL Mock Fixtures

| Mock URL | Description |
|----------|-------------|
| `mock://api/graphql-countries` | Simple nested fields (countries with continent) |
| `mock://api/graphql-nested` | Deep nested fields (characters with origin + episodes) |
| `mock://api/graphql-paginated` | Relay-style cursor pagination (pageInfo/edges/nodes, 4 items, 2 pages) |
| `mock://api/graphql-error` | GraphQL validation error response |
| `mock://api/graphql-rate-limited` | Rate-limited response (429, retryAfter=30) |

## API Pagination 50+ Fixtures

| Mock URL | Type | Total Items | Pages |
|----------|------|-------------|-------|
| `mock://api/paged-products-50` | page | 55 | 6 |
| `mock://api/offset-products-50` | offset | 55 | 6 |
| `mock://api/cursor-products-50` | cursor | 50 | 5 |

## Reverse Evidence Enhancements

### New Signal Codes

| Code | Source | Description |
|------|--------|-------------|
| `api_auth_token_hint` | api | API URL/headers contain signature/token parameters |
| `api_dynamic_input_hint` | api | API URL uses timestamp/nonce parameters |
| `api_encrypted_payload_hint` | api | API body contains encrypted payload keywords |
| `graphql_rate_limit` | graphql | GraphQL endpoint returned 429 |
| `graphql_signature_hint` | graphql | GraphQL endpoint requires auth/signature headers |
| `graphql_nested_complexity` | graphql | Deeply nested GraphQL query |

### New Action Hints

- `api_replay_blocker`: set when API/GraphQL contains signature/token/encrypted payload clues
- `hook_plan`: set when signature flow detected — suggests capturing request_url, headers, query_params, timestamp, nonce
- `sandbox_plan`: set when encrypted payload detected — suggests runtime encryption capture

## Test Results

```
test_graphql_training:         42 passed
test_native_async_runtime:     23 passed
test_api_intercept:            86 passed
full suite:                  1903 passed (5 skipped)
compileall:                  clean
```

## Training Runner Output

```
GraphQL scenarios:    4/4 passed
API 50+ pagination:  3/3 meet threshold
Reverse evidence:    4 with replay risk, 4 with blockers
Async metrics:       100/100 succeeded (884 URLs/s)
```
