# Assignment: Easy Mode CLI Tests

## Assignee

Employee ID: `LLM-2026-001`

Project role: `ROLE-CLI-QA`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-11

## Goal

Add focused tests for the new CLM Easy Mode command-line entry point.

The supervisor will implement the main CLI surface. Your job is to make sure
the entry point stays stable, deterministic by default, and usable without a
real API key during tests.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
PROJECT_STATUS.md
README.md
docs/runbooks/EMPLOYEE_TAKEOVER.md
docs/process/COLLABORATION_GUIDE.md
docs/decisions/ADR-002-deterministic-fallback-required.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
dev_logs/README.md
```

Code to inspect:

```text
run_simple.py
run_skeleton.py
run_baidu_hot_test.py
run_batch_runner_smoke.py
autonomous_crawler/llm/openai_compatible.py
autonomous_crawler/tests/test_run_simple.py
```

## Expected Supervisor Mainline

The supervisor is expected to add or update a unified entry point similar to:

```text
clm.py
python clm.py init
python clm.py check
python clm.py crawl "goal" https://example.com --limit 50 --output result.xlsx
python clm.py smoke
```

If the exact command names differ, test the implemented behavior and report the
difference clearly.

## Allowed Write Scope

You may create or edit:

```text
autonomous_crawler/tests/test_clm_cli.py
dev_logs/development/2026-05-11_HH-MM_easy_mode_cli_tests.md
docs/memory/handoffs/2026-05-11_LLM-2026-001_easy_mode_cli_tests.md
```

Only edit `clm.py` or CLI implementation files if a small testability hook is
needed. Do not change crawler behavior, LLM merge behavior, or training scripts.

## Requirements

Test at least:

1. `init` can create a config file from supplied non-interactive arguments or a
   test helper without writing secrets into tracked files.
2. `check` can run without a real API key and reports deterministic local
   checks.
3. `crawl` argument parsing preserves goal and URL correctly.
4. LLM remains opt-in; default crawl path must not require API credentials.
5. `smoke` routes to a bounded smoke command or prints the expected command
   plan without hitting public sites in tests.
6. Invalid command/config cases return clear non-zero exits.

## Minimum Commands

Run:

```text
python -m unittest autonomous_crawler.tests.test_clm_cli -v
python -m unittest autonomous_crawler.tests.test_run_simple -v
python -m unittest discover -s autonomous_crawler/tests
```

## Deliverables

Create:

```text
autonomous_crawler/tests/test_clm_cli.py
dev_logs/development/2026-05-11_HH-MM_easy_mode_cli_tests.md
docs/memory/handoffs/2026-05-11_LLM-2026-001_easy_mode_cli_tests.md
```

Completion note should include:

- files changed
- tests run
- number of CLI cases covered
- any command naming mismatch
- known risks
