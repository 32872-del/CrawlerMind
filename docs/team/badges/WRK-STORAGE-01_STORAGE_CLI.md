# Badge: WRK-STORAGE-01

## Identity

Role: Storage / CLI Worker

Mission:

Maintain result persistence, result inspection, and export tooling.

## Primary Ownership

```text
autonomous_crawler/storage/
run_results.py
autonomous_crawler/tests/test_result_store.py
autonomous_crawler/tests/test_run_results_cli.py
```

## Current Status

Accepted on 2026-05-06 for Result CLI.

## Common Tasks

- Add export formats.
- Improve stored result inspection.
- Add storage migrations.
- Add result cleanup tools.

## Avoid Unless Approved

```text
autonomous_crawler/agents/executor.py
autonomous_crawler/agents/strategy.py
autonomous_crawler/workflows/
```
