# 2026-05-08 10:45 Real LLM Smoke And Supervisor Closeout

## Summary

Completed the first real LLM-assisted smoke validation for Crawler-Mind after
hardening the OpenAI-compatible adapter and mock-fixture routing.

## What Happened

User first ran:

```text
python run_simple.py "collect product titles and prices" mock://catalog
```

The LLM advisor connected successfully, but suggested `fnspider` for a
`mock://` URL. That exposed a real guardrail issue: mock fixtures are local test
protocols and must never be sent to real network engines.

Supervisor fixed:

- OpenAI-compatible endpoint normalization and diagnostics.
- `response_format` compatibility fallback.
- non-HTTP URL rejection for `fnspider` strategy suggestions.
- executor priority so mock fixtures load before engine routing.

## Verification

Focused and full verification passed:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 175 tests
OK (skipped=3)

python run_simple.py "collect product titles and prices" mock://catalog
Final Status: completed
Extracted Data: 2 items
```

User then ran the real LLM-assisted Baidu hot-search smoke. Latest persisted
artifact:

```text
dev_logs/skeleton_run_result.json
```

Observed:

```text
Goal: collect top 30 hot searches
URL: https://top.baidu.com/board?tab=realtime
Final status: completed
Items: 30
Confidence: 1.0
Validation: passed
LLM decisions: 2
LLM errors: 0
```

## Supervisor Assessment

This marks Phase 3 as usable for CLI-level LLM-assisted Planner/Strategy runs.
It is not yet a full autonomous agent, but it is no longer a deterministic-only
pipeline.

Next highest-leverage work:

1. Add FastAPI opt-in LLM support.
2. Add provider diagnostics / config check command.
3. Begin a small real-site sample suite for strategy and selector reliability.
