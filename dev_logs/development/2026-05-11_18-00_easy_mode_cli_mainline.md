# Easy Mode CLI Mainline

## Goal

Add a single beginner-friendly command surface for CLM so users do not need to
know the individual development scripts before running a basic crawl.

## Changes

- Added `clm.py` with subcommands:
  - `init` creates local config.
  - `check` verifies Python/package/config readiness.
  - `crawl` runs the existing LangGraph workflow with optional LLM config.
  - `smoke` runs or plans bounded smoke checks.
  - `train` lists developer training commands.
- Reused existing `run_simple.py` LLM config helpers and `run_skeleton.py`
  workflow runner.
- Added JSON/XLSX output support for `clm.py crawl --output`.
- Added focused CLI tests in `autonomous_crawler/tests/test_clm_cli.py`.

## Verification

```text
python clm.py init --config dev_logs/runtime/clm_test_config.json --force
OK

python clm.py check --config dev_logs/runtime/clm_test_config.json
OK

python clm.py smoke --kind runner
accepted: true

python clm.py crawl "collect product titles" mock://catalog --config dev_logs/runtime/clm_test_config.json --no-llm --output dev_logs/runtime/clm_mock_output.json
Final Status: completed

python -m compileall clm.py run_simple.py run_skeleton.py run_batch_runner_smoke.py run_baidu_hot_test.py
OK
```

## Notes

This is an entry-point wrapper. It does not change crawler strategy logic,
extractor behavior, or LLM advisor merge rules.
