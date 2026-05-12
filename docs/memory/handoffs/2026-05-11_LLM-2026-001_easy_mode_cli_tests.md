# Handoff: Easy Mode CLI Tests

Employee: LLM-2026-001
Date: 2026-05-11
Assignment: `2026-05-11_LLM-2026-001_EASY_MODE_CLI_TESTS`

## What Was Done

Created CLI test harness for `clm.py` unified entry point. Found and fixed
2 bugs in `clm.py`. 59 test methods covering all subcommands.

## Files Changed

- `autonomous_crawler/tests/test_clm_cli.py` — **new** (59 tests in 8 classes)
- `clm.py` — 3 bug fixes (smoke sys.argv isolation, check JSON error handling)
- `dev_logs/development/2026-05-11_14-30_easy_mode_cli_tests.md` — new dev log
- `docs/memory/handoffs/2026-05-11_LLM-2026-001_easy_mode_cli_tests.md` — this handoff

## Bug Fixes in clm.py

1. `cmd_smoke` — `runner_smoke_main()` called with wrong args; also didn't
   isolate `sys.argv`. Fixed with save/restore pattern.
2. `cmd_check` — corrupt config JSON leaked a traceback. Fixed with try/except.

## Test Status

```text
python -m unittest autonomous_crawler.tests.test_clm_cli -v
Ran 59 tests OK

python -m unittest discover -s autonomous_crawler/tests
Ran 506 tests OK (skipped=4)
```

No regressions.

## Test Coverage (59 cases)

| Category | Cases | What's Verified |
| --- | --- | --- |
| Argument parsing | 17 | All flags for init/check/crawl/smoke/train |
| init command | 8 | Create, overwrite, LLM defaults, no secrets |
| check command | 6 | No config, disabled LLM, packages, --llm flag |
| crawl command | 8 | Goal+URL, --limit, --output, missing args, conflicting flags |
| smoke command | 5 | Runner executes, --plan, no public sites |
| Error handling | 8 | Unknown cmd, corrupt config, no args, --help, invalid --kind |
| Deterministic default | 2 | Full cycle no-API-key, no env vars |
| Module import | 5 | Importable, has build_parser/main/cmd_* functions |

## Known Risks

1. Baidu smoke not tested (hits public site). Only `--plan` variant tested.
2. Crawl tests invoke real LangGraph workflow via `mock://catalog`. May be slow.
3. `sys.argv` manipulation in `cmd_smoke` is not thread-safe.
4. `.xlsx` output path not tested (requires pandas).
