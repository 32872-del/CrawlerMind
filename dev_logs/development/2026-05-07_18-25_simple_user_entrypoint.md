# 2026-05-07 18:25 - Simple User Entrypoint

## Goal

Reduce first-use complexity so a new user can install dependencies, fill one
API config file, and run one script.

## Changes

- Added `clm_config.example.json`.
- Added `run_simple.py`.
- Added `autonomous_crawler/tests/test_run_simple.py`.
- Updated `.gitignore` to ignore real `clm_config.json`.
- Updated `README.md` to put the simple path first.
- Rewrote `docs/runbooks/QUICK_START_CN.md` into a shorter user-facing guide.
- Updated project status and daily report.

## Verification

```text
python run_simple.py "collect product titles and prices" mock://catalog
Final Status: completed

python -m unittest autonomous_crawler.tests.test_run_simple -v
Ran 5 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 164 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_simple.py run_baidu_hot_test.py run_results.py
OK
```

## Result

Current simple path:

```text
python -m pip install -r requirements.txt
Copy-Item clm_config.example.json clm_config.json
notepad clm_config.json
python run_simple.py "<goal>" "<url>"
```
