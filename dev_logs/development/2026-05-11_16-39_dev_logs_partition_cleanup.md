# Dev Logs Partition Cleanup

## Goal

Reduce documentation/log clutter by splitting the flat `dev_logs/` directory
into purpose-based sections that are easier for supervisors, workers, and future
contributors to navigate.

## Changes

- Added `dev_logs/README.md` as the local evidence map.
- Moved historical developer notes into `dev_logs/development/`.
- Moved local audit and QA notes into `dev_logs/audits/`.
- Moved real-site training exports and summaries into `dev_logs/training/`.
- Moved smoke outputs into `dev_logs/smoke/`.
- Moved stress-test evidence into `dev_logs/stress/`.
- Reserved `dev_logs/runtime/` for untracked scratch command output.
- Updated training, smoke, stress, and skeleton scripts to write into the new
  subdirectories.
- Updated entry documents and historical references so old flat paths point to
  the new locations.

## Verification

```text
python -m compileall run_skeleton.py run_baidu_hot_test.py run_batch_runner_smoke.py run_ecommerce_training_2026_05_09.py run_real_training_2026_05_11.py run_stress_test_2026_05_09.py run_training_round1.py run_training_round2.py run_training_round3.py run_training_round4.py
OK

python -m unittest autonomous_crawler.tests.test_batch_runner autonomous_crawler.tests.test_run_simple -v
Ran 19 tests
OK

checked for stale flat `dev_logs/<file>` references
No stale-path matches outside this log
```

## Notes

This is a documentation and artifact-layout cleanup. Core crawler behavior is
unchanged.
