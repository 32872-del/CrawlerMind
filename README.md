# Autonomous Crawl Agent

An early MVP for an autonomous crawling agent.

Current capabilities:

- LangGraph workflow:
  `Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator`
- Static HTML recon and selector inference.
- HTTP execution.
- Playwright browser fallback for rendered SPA/anti-bot pages.
- Structured extraction and validation.
- SQLite result persistence.
- FastAPI background-job service MVP with in-memory job registry.
- Bundled `fnspider` engine for project-local portability.
- Verified Baidu realtime hot-search smoke test.
- Opt-in real browser SPA smoke test using a local JS fixture.
- Result inspection/export CLI.
- Git-backed team workflow with employee memory, ADRs, runbooks, and supervisor
  acceptance records.
- Optional OpenAI-compatible LLM advisor adapter for Planner/Strategy.

## Quick Start

Run tests:

```text
python -m unittest discover autonomous_crawler\tests
```

Run opt-in real browser SPA smoke test:

```text
$env:AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE='1'
python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

Run Baidu smoke test:

```text
python run_baidu_hot_test.py
```

Run a workflow directly:

```text
python run_skeleton.py "采集百度热搜榜前30条" https://top.baidu.com/board?tab=realtime
```

Inspect persisted results:

```text
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

Run with an OpenAI-compatible LLM advisor:

```text
$env:CLM_LLM_BASE_URL='https://api.openai.com/v1'
$env:CLM_LLM_MODEL='gpt-4o-mini'
$env:CLM_LLM_API_KEY='...'
python run_skeleton.py --llm "collect product titles and prices" https://example.com
```

Compatible providers usually only require changing `CLM_LLM_BASE_URL`,
`CLM_LLM_MODEL`, and `CLM_LLM_API_KEY`. Local OpenAI-compatible servers can omit
`CLM_LLM_API_KEY`.

Start API service:

```text
uvicorn autonomous_crawler.api.app:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Current API

```text
GET  /health
POST /crawl
GET  /crawl/{task_id}
GET  /history
```

`POST /crawl` returns a task ID immediately with `running` status. The workflow
runs in a background thread and can be queried through `GET /crawl/{task_id}`.
The current job registry is in-memory, so in-flight jobs do not survive process
restart.

Example request:

```json
{
  "user_goal": "采集百度热搜榜前30条",
  "target_url": "https://top.baidu.com/board?tab=realtime"
}
```

## Project Map

```text
autonomous_crawler/
  agents/       Workflow nodes
  api/          FastAPI service
  engines/      Bundled crawler engines
  models/       State schemas
  storage/      SQLite result store
  tests/        Unit and integration tests
  tools/        Recon and adapter tools
  workflows/    LangGraph graph
  llm/          Optional provider-neutral LLM advisors

docs/
  blueprints/   Long-term architecture and capability blueprints
  plans/        Short-term implementation plans
  process/      Development and collaboration rules
  reports/      Daily reports
  reviews/      Engineering reviews
  team/         Supervisor/worker LLM workspace

dev_logs/       Developer logs only
```

## Important Docs

- Current status: [PROJECT_STATUS.md](PROJECT_STATUS.md)
- Main blueprint: [docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md](docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md)
- MCP blueprint: [docs/blueprints/MCP_BLUEPRINT.md](docs/blueprints/MCP_BLUEPRINT.md)
- Collaboration rules: [docs/process/COLLABORATION_GUIDE.md](docs/process/COLLABORATION_GUIDE.md)
- Decisions: [docs/decisions/](docs/decisions/)
- Runbooks: [docs/runbooks/](docs/runbooks/)
- Quick start guide: [docs/runbooks/QUICK_START_CN.md](docs/runbooks/QUICK_START_CN.md)
- Employee memory model: [docs/memory/EMPLOYEE_MEMORY_MODEL.md](docs/memory/EMPLOYEE_MEMORY_MODEL.md)
- LLM team workspace: [docs/team/TEAM_WORKSPACE.md](docs/team/TEAM_WORKSPACE.md)
- New LLM onboarding: [docs/team/training/NEW_LLM_ONBOARDING.md](docs/team/training/NEW_LLM_ONBOARDING.md)
- Short-term plan: [docs/plans/2026-05-05_SHORT_TERM_PLAN.md](docs/plans/2026-05-05_SHORT_TERM_PLAN.md)

## Runtime Data

Runtime files are intentionally not packaged:

```text
autonomous_crawler/storage/runtime/
autonomous_crawler/engines/runtime/
```

The project should remain portable without external folders.
