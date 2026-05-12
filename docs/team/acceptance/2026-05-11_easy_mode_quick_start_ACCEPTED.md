# Acceptance: Easy Mode Quick Start Docs

Employee: `LLM-2026-002`

Status: accepted

Date: 2026-05-11

## Accepted Work

- Reframed the first-use documentation around a shorter install -> check ->
  crawl -> optional LLM path.
- Identified that `run_simple.py` was still the documented main path while
  Easy Mode was being introduced.
- The supervisor applied the final alignment pass so README and platform quick
  starts now use `clm.py` as the primary user entrypoint.

## Files Reviewed

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
dev_logs/development/2026-05-11_17-46_easy_mode_quick_start.md
docs/memory/handoffs/2026-05-11_LLM-2026-002_easy_mode_quick_start.md
```

## Verification

The final docs now document:

```text
python clm.py init
python clm.py check
python clm.py check --llm
python clm.py crawl ...
python clm.py smoke --kind runner
```
