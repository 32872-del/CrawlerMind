# 2026-05-08 Daily Report

## Summary

Today Crawler-Mind crossed from optional LLM interface work into a real
LLM-assisted smoke run and a FastAPI LLM opt-in integration. The system
completed a Baidu realtime hot-search crawl with LLM Planner/Strategy enabled
and extracted 30 validated items.

Today also added a persistent real-site training ladder and completed three
training rounds that broadened API, GraphQL, SSR, and ranking-page coverage.

## Completed

### OpenAI-Compatible Adapter Hardening

- Normalized provider base URLs:
  - root URL -> `/v1/chat/completions`
  - `/v1` URL -> `/v1/chat/completions`
  - full `/chat/completions` endpoint -> unchanged
- Added safer provider diagnostics with bounded, redacted response previews.
- Added support for common alternate response shapes:
  - `choices[0].message.content`
  - content parts
  - `choices[0].text`
- Added automatic retry without `response_format` when a provider rejects that
  parameter.
- Added `use_response_format` to `clm_config.example.json` and `run_simple.py`.

### Mock Fixture / Engine Guardrail

- Fixed a real LLM side effect where the advisor could suggest `fnspider` for
  `mock://catalog`.
- Strategy now rejects `fnspider` for non-HTTP URLs.
- Executor now loads mock fixtures before engine routing.
- Added regression tests for both strategy and executor behavior.

### Real LLM Smoke

Latest persisted result:

```text
dev_logs/runtime/skeleton_run_result.json
```

Result:

```text
Goal: collect top 30 hot searches
URL: https://top.baidu.com/board?tab=realtime
Final status: completed
Items extracted: 30
Confidence: 1.0
Validation: passed
Completeness: 100%
Retries: 0
LLM decisions: 2
LLM errors: 0
```

### FastAPI Opt-In LLM Advisors (LLM-2026-001)

- Added `LLMConfig` Pydantic model to `app.py` with fields: `enabled`,
  `base_url`, `model`, `api_key`, `provider`, `timeout_seconds`, `temperature`,
  `max_tokens`, `use_response_format`.
- Added optional `llm` field to `CrawlRequest` (default `None`).
- `POST /crawl` validates LLM config eagerly: returns 400 on missing
  `base_url` or `model` when `llm.enabled=true`.
- `_build_advisor_from_config()` constructs `OpenAICompatibleAdvisor` from
  request-level config.
- `run_crawl_workflow()` passes advisor to `compile_crawl_graph()`.
- Background job stores `llm_enabled`, `llm_decisions`, `llm_errors` in
  persisted final state.
- 11 new tests added: 7 endpoint-level (`FastAPILLMOptInTests`), 4 unit-level
  (`BuildAdvisorFromConfigTests`). Total: 38 API tests, 186 suite tests.

### Real-Site Training Rounds

The external training list is now preserved as a long-term ladder under:

```text
docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md
```

Round 1:

- JSONPlaceholder posts: direct JSON target detection, 10 items
- Reddit r/python JSON: nested JSON record extraction, 10 items
- Countries GraphQL: explicit GraphQL POST execution, 10 items

Round 2:

- AniList GraphQL: nested GraphQL records, 10 items
- Bilibili public ranking API: public API normalization, 10 items

Round 3:

- Douban Top250: static ranking page, 25 items
- React docs SSR recon: framework recon plus minimal extraction, 1 item
- Vue examples recon: static/framework recon, 10 items

Training takeaway:

- public JSON and GraphQL routes are now part of the main graph
- ranking pages work on both static DOM and public API paths
- SSR/framework recon works, but some targets are navigation-heavy and return
  sparse items by nature
- the next useful rung is a controlled SPA, then a virtualized-list target

## Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 261 tests (skipped=3)
OK

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py
OK

python run_simple.py "collect product titles and prices" mock://catalog
Final Status: completed
Extracted Data: 2 items
```

## Blueprint Position

- Level 1 HTML Pipeline: MVP complete.
- Level 2 Browser Rendering: MVP complete.
- Level 3 Visual Page Understanding: not started.
- Level 4 Site Mental Model: not started.
- Level 5 Autonomous Agent: early CLI-level LLM Planner/Strategy slice is now
  working against a real public page, and FastAPI opt-in LLM support is also
  working.
- Phase 6 Self-Healing and Memory: memory docs exist for team workflow, but
  crawler runtime memory and self-healing are not implemented.

## Current Risks

- API interception remains incomplete.
- Site sample coverage is still thin.
- Provider compatibility needs more real gateway samples.
- No streaming support or persistent job registry.

## Next Recommended Tasks

1. Continue the real-site training ladder with one controlled SPA target.
2. Add one virtualized-list target for scroll strategy validation.
3. Continue docs cleanup for employee memory and handoff refreshes when new
   assignments land.
