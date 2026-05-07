# 2026-05-05 Short-Term Plan

## Context

The project has moved from a script-only MVP to a local background-job service
MVP:

- LangGraph crawl workflow runs end to end.
- Baidu realtime hot-search real smoke test succeeds.
- Results persist to SQLite.
- FastAPI exposes crawl/history endpoints and runs crawl requests in a
  background thread.
- Recon tool stubs have been replaced by real wrappers.

The next goal is to make the service more usable and resilient before adding
large LLM/vision capabilities.

## Short-Term Goal

Stabilize the MVP as a maintainable local Agent service.

## Priority 1: Project Governance

Status: in progress.

Tasks:

- Separate blueprints, reviews, plans, reports, and developer logs.
- Keep `dev_logs/` developer-only.
- Add daily report workflow.
- Add multi-Codex collaboration guide.
- Keep root directory small and navigable.

## Priority 2: Result Access CLI

Status: completed on 2026-05-06.

Tasks:

- Add a small CLI for stored results:
  - list recent tasks
  - show task summary
  - export task items as JSON/CSV
- Reuse `autonomous_crawler.storage`.
- Add tests for CLI output where practical.

Suggested file:

```text
run_results.py
```

Implemented commands:

```text
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## Priority 3: Error-Path Hardening

Status: completed on 2026-05-06.

Tasks:

- Test unsupported URL scheme. Done.
- Test HTTP failure/timeout path. Done.
- Test empty HTML. Done.
- Test invalid selectors. Done.
- Test retry exhaustion. Done.
- Ensure failures are persisted. Done.

Implemented in `autonomous_crawler/tests/test_error_paths.py` (30 tests).
Code fixes in `extractor.py` (None HTML, malformed selectors) and
`crawl_graph.py` (recon failure early exit).

## Priority 3.5: Explicit Fnspider Engine Routing

Status: completed on 2026-05-06.

Tasks:

- Allow product-list tasks to request the bundled fnspider engine explicitly.
- Support `preferred_engine="fnspider"`.
- Support `crawl_preferences={"engine": "fnspider"}`.
- Keep ranking-list tasks on the lightweight DOM path.

Automatic engine selection is intentionally deferred until more real site
samples are available.

## Priority 4: Browser Fallback Prototype

Status: completed on 2026-05-06.

Tasks:

- Add browser executor mode using Playwright. Done.
- Capture rendered HTML. Done.
- Save optional screenshot artifact path. Done.
- Use browser mode when recon detects SPA or empty static DOM. Done.
- Keep HTTP mode as default. Done.

Implemented in `autonomous_crawler/tools/browser_fetch.py` (fetch_rendered_html)
and wired into `autonomous_crawler/agents/executor.py` (mode=="browser" branch).
Tests in `autonomous_crawler/tests/test_browser_fallback.py` (16 tests).

## Priority 5: LLM Integration Design

Tasks:

- Design optional LLM Planner/Strategy interfaces.
- Keep deterministic fallback.
- Store model decisions/prompts in final state for audit.
- Do not block normal tests on external API keys.

## Non-Goals For Immediate Next Cycle

- Full visual page understanding.
- Site mental model.
- Distributed queue.
- Proxy pool.
- Anti-bot bypass.

These are important, but they should build on the stable service and browser
foundation.

## Recommended Next Task

Design optional LLM Planner/Strategy interfaces (Priority 5), add job registry
persistence/rate limiting, or collect site samples for future automatic engine
selection.
