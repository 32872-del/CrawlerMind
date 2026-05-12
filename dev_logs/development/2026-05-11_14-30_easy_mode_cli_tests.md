# Dev Log: Easy Mode CLI Tests

Employee: LLM-2026-001
Date: 2026-05-11 14:30

## Task

Write CLI tests for the `clm.py` unified entry point. Validate init/check/crawl/smoke
parameter parsing, deterministic defaults (no LLM/API key), and clear error exits.

## What Was Done

Created `autonomous_crawler/tests/test_clm_cli.py` with 8 test classes and
59 individual test methods. Found and fixed 2 bugs in `clm.py`.

### Test Classes

| Class | Tests | Focus |
|---|---|---|
| ArgParsingTests | 17 | All subcommand flags: goal, URL, --limit, --output, --force, --enable-llm, --llm, --no-llm, --kind, --plan, --round |
| InitCommandTests | 8 | Config creation, LLM disabled by default, no secrets, overwrite protection, --force, --enable-llm, placeholder key |
| CheckCommandTests | 6 | No config, disabled LLM, Python version, packages, --llm flag, deterministic no-network |
| CrawlCommandTests | 8 | Goal+URL, default no-LLM, --limit, --output, missing URL, no args, conflicting --llm/--no-llm |
| SmokeCommandTests | 5 | Runner completes, exits cleanly, --plan doesn't execute, --plan baidu, no public site access |
| ErrorHandlingTests | 8 | Unknown command, no args, --help, corrupt config, missing llm section, invalid --kind |
| DeterministicDefaultTests | 2 | Full init→check→crawl cycle no-API-key, no env vars required |
| ModuleImportTests | 5 | Importable, build_parser, main, main returns int, cmd_* functions |

### Bugs Found and Fixed in clm.py

1. **`cmd_smoke` passed `[]` to `runner_smoke_main()`** — `main()` takes 0 positional
   arguments. Fixed by calling `runner_smoke_main()` without args.

2. **`cmd_smoke` didn't isolate `sys.argv`** — `runner_smoke_main()` calls
   `argparse.parse_args()` on `sys.argv[1:]`, which still contained `["smoke", "--kind", "runner"]`.
   Fixed by saving/restoring `sys.argv` around the call.

3. **`cmd_check` leaked JSONDecodeError traceback** — corrupt config file caused
   `json.load()` to raise, and the traceback leaked to stderr. Fixed by wrapping
   `load_simple_config()` in try/except for `json.JSONDecodeError` and `OSError`.

## Tests Run

```text
python -m unittest autonomous_crawler.tests.test_clm_cli -v
Ran 59 tests in 59.230s OK

python -m unittest autonomous_crawler.tests.test_run_simple -v
Ran 9 tests in 0.006s OK

python -m unittest discover -s autonomous_crawler/tests
Ran 506 tests in 90.115s OK (skipped=4)
```

No regressions. 4 skipped = browser availability only.

## Key Design Decisions

1. **Subprocess-based tests**: Tests use `subprocess.run` to invoke `clm.py`
   as `python clm.py <subcommand>`. This tests the real CLI surface including
   argument parsing, environment isolation, and exit codes.

2. **Temp directory isolation**: Each test uses `tempfile.TemporaryDirectory`
   for config files. No writes to project root.

3. **No network, no API key**: All tests use `mock://catalog` or no URL.
   Deterministic mode is the default.

4. **Error quality checks**: Tests verify that error output contains useful
   keywords AND that no Python traceback leaks to stdout/stderr.

## Command Naming

Actual interface matches the expected interface exactly:

```text
python clm.py init [--force] [--enable-llm] [--base-url] [--model] [--api-key]
python clm.py check [--config] [--llm]
python clm.py crawl "goal" URL [--limit N] [--output FILE] [--llm] [--no-llm]
python clm.py smoke [--kind runner|baidu] [--plan]
python clm.py train [--round N]
```

No command naming mismatches. The `train` subcommand was not in the original
assignment scope but is tested for parse recognition.

## Known Risks

1. **`cmd_baidu_smoke` not tested** — the baidu smoke path calls
   `run_baidu_hot_test.main()` which hits the public Baidu site. Tests only
   cover `--plan` for baidu (prints command without executing).

2. **`cmd_crawl` actually runs `run_crawl()`** — crawl tests use `mock://catalog`
   which may trigger the full LangGraph workflow. If the workflow is slow or
   has side effects, tests could flake. Current timeout is 15s.

3. **`_write_crawl_output` for .xlsx** — requires pandas. Tests use .json
   output to avoid pandas dependency in test environment.

4. **sys.argv manipulation in cmd_smoke** — the save/restore pattern is not
   thread-safe. If clm.py is ever called from a multi-threaded context, this
   could break. Acceptable for CLI usage.
