# 2026-05-09 09:30 Open Source Docs Sync

## Summary

Prepared the repository for GitHub synchronization and easier public onboarding.

## Changes

- Rewrote `README.md` for GitHub users.
- Added Windows quick start runbook.
- Added Linux/macOS quick start runbook.
- Repaired Chinese quick start text.
- Added open-source release checklist.
- Added Unix helper scripts for setup, LLM check, mock run, and API startup.
- Added common local environment ignores.

## Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 261 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py run_training_round1.py run_training_round2.py run_training_round3.py
OK
```

## Notes

License is still pending project-owner choice.
