# 2026-05-05 14:20 - Automatic Ranking Workflow

## Goal

Turn the Baidu hot-search smoke test from a manually configured selector test
into a full Agent graph workflow:

```text
Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
```

Target command:

```text
python run_skeleton.py "采集百度热搜榜前30条" https://top.baidu.com/board?tab=realtime
```

## Changes

- Planner now recognizes ranking-list goals and extracts `max_items` from goals
  such as `采集百度热搜榜前30条`.
- Recon now includes a deterministic `mock://ranking` fixture and can infer
  Baidu-style ranking selectors:
  - `item_container`
  - `rank`
  - `title`
  - `link`
  - `hot_score`
  - `summary`
  - `image`
- Executor now supports `mock://ranking` for graph-level fixture tests.
- Strategy now keeps ranking-list pages on DOM parsing when reliable DOM
  selectors were inferred.
- API endpoint discovery now ignores non-path resource hints such as
  `dns-prefetch`.
- `run_skeleton.py` now prints ranking-list summaries using rank, title,
  hot score, and link instead of product price formatting.
- `run_baidu_hot_test.py` is now a self-contained Agent smoke test that writes
  `dev_logs/smoke/baidu_hot_smoke_result.json`.
- `PROJECT_STATUS.md` was updated to reflect the current completed workflow.

## Verification

Unit tests:

```text
python -m unittest discover autonomous_crawler\tests
Ran 14 tests
OK
```

Mock graph workflow:

```text
python run_skeleton.py "采集百度热搜榜前30条" mock://ranking
Final Status: completed
Extracted Data: 2 items
Validation: passed
```

Real Baidu workflow:

```text
python run_skeleton.py "采集百度热搜榜前30条" https://top.baidu.com/board?tab=realtime
Final Status: completed
Extracted Data: 30 items
Validation: passed
```

Self-contained Baidu smoke test:

```text
python run_baidu_hot_test.py
Status: completed
Items: 30
Valid: True
Output: dev_logs/smoke/baidu_hot_smoke_result.json
```

The latest full real-run state is saved at:

```text
dev_logs/runtime/skeleton_run_result.json
```

## Result

The project now has a first working automatic ranking-list path against a real
website. It still uses deterministic heuristics, but the full Agent loop is no
longer just a skeleton for this case.

## Recommended Next Step

Build persistence and a small service boundary next:

1. Save completed workflow outputs into a project-local results store.
2. Add a FastAPI job API for submitting crawl goals and reading results.
3. Keep Baidu hot-search as the first repeatable smoke test for that API.
