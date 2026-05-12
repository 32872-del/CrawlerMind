# Dev Log: Easy Mode Quick Start Docs

Date: 2026-05-11 17:46
Employee: LLM-2026-002

## What Changed

Rewrote first-use documentation to follow a clear user path:
install → environment check → first crawl → optional LLM → output.

## Files Modified

1. `README.md` — restructured: quick start at top, LLM config as optional
   section, training scripts moved to "Developer Training Scripts" section
   at bottom.
2. `docs/runbooks/QUICK_START_WINDOWS.md` — reordered: install → check →
   crawl → results → optional LLM → optional API → optional tests.
3. `docs/runbooks/QUICK_START_LINUX_MAC.md` — same restructuring.
4. `docs/runbooks/QUICK_START_CN.md` — same restructuring, Chinese.

## Key Design Decisions

- **No `clm.py init`/`clm.py check`**: These commands don't exist. The
  actual entry point is `run_simple.py`. The environment check is running
  `mock://catalog` — if it succeeds, the environment is ready.
- **LLM config is step 7, not step 4**: New users should see the tool work
  first without API keys. LLM is optional.
- **Training scripts clearly separated**: `run_training_round*.py`,
  `run_ecommerce_training_*.py`, `run_stress_test_*.py` are developer
  scripts, not user commands. Moved to dedicated section.
- **"Where Output Goes" section added**: Users need to know results go to
  `autonomous_crawler/storage/runtime/crawl_results.sqlite3` and can be
  inspected via `run_results.py`.
- **Safety note preserved**: Not for bypassing login/CAPTCHA/Cloudflare.

## Commands Documented

| Command | Purpose |
|---|---|
| `python run_simple.py "collect product titles and prices" mock://catalog` | Environment check |
| `python run_simple.py "collect top 30 hot searches" "https://top.baidu.com/..."` | Real crawl |
| `python run_simple.py --check-llm` | LLM config check |
| `python run_results.py list/show/items/export-json/export-csv` | Result inspection |
| `python -m unittest discover -s autonomous_crawler/tests` | Test suite |
| `uvicorn autonomous_crawler.api.app:app --reload` | FastAPI service |

## Remaining Confusing Areas

1. **No `clm.py` CLI**: The assignment mentions `python clm.py init` and
   `python clm.py check` but these don't exist. `run_simple.py` is the
   actual entry point. A unified `clm.py` CLI would be clearer.
2. **Output location not obvious**: `autonomous_crawler/storage/runtime/`
   is deep in the tree. A `--output` flag or symlink would help.
3. **`run_simple.py` vs `run_skeleton.py`**: Both exist. `run_simple.py`
   wraps `run_skeleton.py` with config loading. Users should only need
   `run_simple.py`.
4. **No `--check-env` command**: The "environment check" is running a mock
   crawl. A dedicated `--check-env` that verifies Python version, deps,
   and Playwright would be more explicit.
