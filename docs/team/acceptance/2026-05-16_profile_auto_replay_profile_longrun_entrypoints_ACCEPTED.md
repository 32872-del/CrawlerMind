# Acceptance: Profile Automation, Replay Runtime, And Profile Long-Run Entrypoints

Date: 2026-05-16

Employee: `LLM-2026-000`

Assignments:

- `LLM-2026-001`: Profile draft refinement, runnable diagnostics, selector repair hints, and API pagination inference
- `LLM-2026-002`: JS sandbox execution path behind replay executor, request patch output, and profile API hint artifact
- `LLM-2026-000`: Profile long-run facade plus CLI/API entrypoints

Status: accepted

## Verdict

Accepted. This round strengthens the bridge between evidence, generated site
profiles, replay/signature assistance, and long-running profile execution.
The work keeps site-specific behavior in profiles, fixtures, and training
assets while moving reusable backend capability into CLM-owned modules.

## Accepted Scope

- `profile_draft.py` now merges evidence sources, reads recon evidence, infers
  API items paths and field mappings, detects pagination, and reports draft
  runnability, weak selectors, missing fields, and repair candidates.
- `js_sandbox.py` adds a Node.js-backed JavaScript execution runtime with
  bounded output, timeout handling, runtime events, and redaction.
- `replay_executor.py` now tries real JS sandbox execution before falling back
  to deterministic fixtures, and emits `request_patch` plus
  `profile_api_hints` for later profile integration.
- `ProfileLongRunExecutor` wires `SiteProfile -> URLFrontier -> BatchRunner ->
  SpiderRuntimeProcessor -> ProductStore -> CheckpointStore ->
  profile-run-report/v1`.
- `clm.py profile-run` exposes the profile long-run facade from Easy Mode.
- FastAPI now exposes `POST /profile-runs` and `GET /profile-runs/{task_id}`.

## Evidence

- Profile long-run smoke:
  `dev_logs/smoke/2026-05-16_profile_longrun_smoke.json`
- Replay runtime development note:
  `dev_logs/development/2026-05-15_LLM-2026-002_replay_runtime_1_js_sandbox.md`
- Replay runtime handoff:
  `docs/memory/handoffs/2026-05-15_LLM-2026-002_replay_runtime_1_js_sandbox.md`

## Supervisor Verification

```text
python -m unittest autonomous_crawler.tests.test_profile_draft autonomous_crawler.tests.test_replay_executor autonomous_crawler.tests.test_profile_longrun autonomous_crawler.tests.test_clm_cli autonomous_crawler.tests.test_api_mvp -v
Ran 271 tests in 10.979s
OK

python -m compileall autonomous_crawler clm.py run_profile_longrun_smoke_2026_05_16.py -q
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 2213 tests in 89.313s
OK (skipped=5)
```

## Notes

- Full-suite verification produced non-failing `ResourceWarning` messages from
  browser/socket cleanup paths. They should be tracked as polish work, not as a
  blocker for this acceptance.
- The new profile long-run API currently uses the native static fetch runtime
  by default. Browser-mode profile long-runs and richer GraphQL POST profile
  support are still follow-up backend tasks.

## Next Actions

1. Run a real high-difficulty GraphQL long task with at least 1000 records.
2. Convert the resulting gaps into backend work for profile-run GraphQL POST
   support, progress reporting, and frontend-ready job/result APIs.
3. Continue hardening browser/profile/proxy long-running execution on real
   dynamic ecommerce targets.
