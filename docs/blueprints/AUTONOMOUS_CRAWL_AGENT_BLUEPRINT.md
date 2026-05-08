# Autonomous Crawl Agent Blueprint

## 1. North Star

Build an autonomous crawling agent that can understand natural-language crawl
requests, explore websites, choose the best collection strategy, execute safely,
validate results, and improve from prior runs.

The long-term target is not just a configurable scraper. The target is a crawler
Agent with:

- HTML and browser execution capability.
- Visual page understanding.
- Site mental models.
- Exploration before large-scale exploitation.
- Failure diagnosis and self-healing.
- Persistent memory of sites, strategies, and historical failures.

## 2. Current MVP Scope

In scope now:

- Single target URL workflow.
- Natural-language task input through deterministic Planner rules, plus
  optional CLI/config LLM advisors.
- Static HTML recon and selector inference.
- HTTP execution.
- Playwright browser rendering fallback.
- Structured extraction by CSS selectors.
- Validation and retry loop.
- SQLite persistence.
- FastAPI background-job service boundary with in-memory job registry.

Out of scope for current MVP:

- Distributed workers.
- Multi-tenant deployment.
- Full anti-bot bypass.
- Browser visual self-healing.
- Long-term cross-site learning.

## 3. Workflow

```text
User Request
  -> Planner
  -> Recon
  -> Strategy
  -> Executor
  -> Extractor
  -> Validator
  -> Storage/API
```

Current nodes:

- `Planner`: parse fields, task type, and constraints.
- `Recon`: fetch/analyze HTML, detect framework/rendering/anti-bot/API hints,
  infer repeated containers and field selectors.
- `Strategy`: choose execution and extraction strategy from recon output.
- `Executor`: execute HTTP, browser, mock, or bundled engine strategy.
- `Extractor`: normalize structured items from raw HTML/API/engine results.
- `Validator`: score completeness, detect anomalies, decide retry/final status.

## 4. Service Surface

Current FastAPI MVP:

```text
GET  /health
POST /crawl
GET  /crawl/{task_id}
GET  /history
```

Current CLI/smoke entrypoints:

```text
python run_skeleton.py "采集百度热搜榜前30条" https://top.baidu.com/board?tab=realtime
python run_baidu_hot_test.py
```

## 5. Storage

Current local SQLite storage:

```text
autonomous_crawler/storage/runtime/crawl_results.sqlite3
```

Tables:

- `crawl_tasks`: task metadata, final state JSON, validation status, timestamps.
- `crawl_items`: extracted item JSON plus title/link/rank helper columns.

Runtime storage is not packaged or committed.

## 6. Capability Levels

### Level 1: HTML Pipeline

Status: current.

The system can fetch static HTML, infer selectors, extract records, validate,
persist, and expose results through a local API.

### Level 2: Browser Rendering

Status: current MVP.

- Playwright execution mode.
- Rendered DOM capture.
- Screenshot capture.
- SPA fallback when HTTP HTML is incomplete.
- Local deterministic SPA smoke validation.

### Level 3: Visual Page Understanding

Target:

- Use screenshots as a first-class recon artifact.
- Detect page type, main content area, repeated cards, fields, and pagination
  visually.
- Map visual regions back to DOM elements and selectors.

### Level 4: Site Mental Model

Target:

- Build navigation graph for a site.
- Understand list/detail/category relationships.
- Identify pagination/data distribution.
- Plan crawl routes before bulk execution.

### Level 5: Autonomous Agent

Target:

- LLM-assisted Planner/Strategy/Validator.
- Exploration-then-exploitation crawl plans.
- Failure diagnosis and self-healing.
- Site memory and strategy reuse.

## 7. Engineering Principles

1. Keep every major capability behind a typed, testable interface.
2. Prefer deterministic heuristics as fallback even after LLM integration.
3. Persist final states, key artifacts, and decisions for replay/debugging.
4. Do not hide side effects inside prompts.
5. Add tests before broadening a capability's blast radius.
6. Keep packaging portable: no dependency on external development folders.

## 8. Revised Roadmap

### Phase 1: Project Hygiene and Service MVP

Status: complete for local MVP.

- Clean dead recon tool stubs.
- Add SQLite result store.
- Add FastAPI background-job endpoints.
- Standardize docs/logs/reports.
- Add error-path tests.

### Phase 2: Browser Fallback

Status: complete for MVP.

- Implement Playwright browser executor mode.
- Capture rendered DOM and screenshot artifacts.
- Use browser fallback for SPA or empty HTTP DOM.
- Add smoke tests for a browser-rendered fixture/page.

### Phase 3: LLM-Assisted Planning

Status: current CLI MVP.

- Add optional LLM Planner with deterministic fallback.
- Add optional LLM Strategy that reasons over recon output.
- Store LLM decisions and prompts for audit.

Current evidence:

- Provider-neutral advisor interfaces and audit records are implemented.
- OpenAI-compatible adapter is available through `run_simple.py` and
  `run_skeleton.py --llm`.
- 2026-05-08 real-site smoke completed Baidu realtime hot-search extraction
  with LLM enabled: 30 items, validation passed, 0 LLM errors.

### Phase 4: Visual Recon Prototype

- Screenshot module.
- Visual page type detection.
- Main content/card/field bounding box detection.
- Visual-to-DOM selector mapping prototype.

### Phase 5: Site Mental Model and Multi-Page Crawling

- Explore sample pages.
- Detect pagination and detail-page links.
- Build crawl frontier and merge cross-page results.
- Save site profiles.

### Phase 6: Self-Healing and Memory

- Diagnose temporary vs structural failures.
- Re-run recon when selector extraction fails.
- Save successful strategies and failed attempts by domain.
- Reuse site profiles on future runs.
