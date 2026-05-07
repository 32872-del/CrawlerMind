# 2026-05-05 17:35 - Recon Tools Cleanup and FastAPI MVP

## Goal

Respond to the code review feedback without destabilizing the MVP:

1. Remove misleading dead recon tool stubs.
2. Expose the persisted workflow through a small FastAPI service.

## Changes

- Replaced `autonomous_crawler/tools/recon_tools.py` placeholder outputs with
  LangChain-compatible wrappers around `html_recon.py`.
- The recon tools now fetch real HTML or deterministic mock fixtures and return
  JSON for:
  - framework detection
  - API endpoint discovery
  - anti-bot marker detection
  - DOM structure inference
- Added FastAPI app in `autonomous_crawler/api/app.py`.
- Implemented endpoints:
  - `GET /health`
  - `POST /crawl`
  - `GET /crawl/{task_id}`
  - `GET /history`
- `POST /crawl` currently runs the workflow synchronously and persists the final
  state to SQLite.
- Renamed `READNE_mcp.md` to `README_mcp.md`.
- Updated `README.md` and `PROJECT_STATUS.md`.

## Verification

Unit tests:

```text
python -m unittest discover autonomous_crawler\tests
Ran 24 tests
OK
```

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py
OK
```

FastAPI TestClient smoke:

```text
POST /crawl mock://ranking -> 200 completed, 2 items
GET /crawl/{task_id} -> 200, 2 persisted items
GET /history -> 200
```

## Result

The project now has a clean first service boundary. It is still synchronous and
deterministic, but the storage/API foundation is ready for background jobs,
browser fallback, and eventually LLM-assisted Planner/Strategy nodes.

## Recommended Next Step

Add a small CLI for stored results, then implement browser-mode fallback for SPA
or incomplete HTTP HTML.
