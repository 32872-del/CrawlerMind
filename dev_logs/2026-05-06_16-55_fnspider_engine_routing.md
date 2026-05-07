# 2026-05-06 16:55 - Fnspider Engine Routing

## Goal

Pick a low-conflict module after Error-Path Hardening and implement the next
short-term planning item: decide how the bundled `fnspider` engine is selected.

## Changes

- Added explicit fnspider routing in `strategy.py`.
- Product-list tasks can request fnspider through:
  - `preferred_engine="fnspider"`
  - `crawl_preferences={"engine": "fnspider"}`
- Ranking-list tasks stay on the lightweight DOM strategy even if fnspider is
  requested.
- Existing default behavior remains conservative: no automatic fnspider routing
  until more real site samples exist.
- Added Strategy tests for explicit fnspider routing and ranking-list bypass.
- Updated `PROJECT_STATUS.md`, short-term plan, and daily report.

## Verification

Focused tests:

```text
python -m unittest autonomous_crawler.tests.test_workflow_mvp.WorkflowMVPTests.test_strategy_uses_recon_selectors autonomous_crawler.tests.test_workflow_mvp.WorkflowMVPTests.test_strategy_uses_fnspider_when_explicitly_requested autonomous_crawler.tests.test_workflow_mvp.WorkflowMVPTests.test_strategy_does_not_route_ranking_list_to_fnspider autonomous_crawler.tests.test_workflow_mvp.WorkflowMVPTests.test_bundled_fnspider_adapter_validates_and_saves_spec
Ran 4 tests
OK
```

Full tests:

```text
python -m unittest discover autonomous_crawler\tests
Ran 60 tests
OK
```

Compile check:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Result

The project now has a clear first engine selection rule:

- lightweight DOM pipeline by default
- explicit `fnspider` for product-list tasks when requested
- ranking-list tasks remain on DOM extraction

## Next Step

Coordinate before starting Browser Fallback because it touches Executor, a shared
boundary that may be edited by another Codex.
