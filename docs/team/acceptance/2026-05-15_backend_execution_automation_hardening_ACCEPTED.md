# Acceptance: Backend Execution Automation Hardening

Date: 2026-05-15

Employee: `LLM-2026-000`

Assignments:

- `LLM-2026-001`: Browser dynamic training, profile draft generation, and profile draft smoke
- `LLM-2026-002`: Replay executor, API/GraphQL replay training, and resumable 30k checkpoint restart
- `LLM-2026-004`: Profile quality policy, profile run report export, and real profile batch training

Status: accepted

## Verdict

Accepted. This batch moves CLM from evidence collection and planning toward
operator-facing execution automation. The new work keeps the product direction
aligned with the Scrapling absorption goal: CLM owns the backend abstractions,
while site-specific behavior remains in profiles, fixtures, and training
artifacts.

## Accepted Scope

- `profile_draft.py` can convert browser/API/recon evidence into reusable
  `SiteProfile` draft dictionaries.
- Profile drafts now preserve observed seed URLs under
  `crawl_preferences.seed_urls`, so generated profiles can produce executable
  initial requests instead of only loadable metadata.
- `replay_executor.py` provides a deterministic fixture replay layer for
  `HookSandboxPlan` outputs: dynamic inputs, hook outputs, sandbox stubs,
  request previews, step results, and credential redaction.
- `profile_report.py` emits stable `profile-run-report/v1` payloads with run
  metrics, quality gate state, samples, failures, and next-action hints.
- The scale resume script now combines phase-1 and phase-2 summaries into the
  final checkpoint, so restarted long-run evidence reflects the whole run
  instead of only the second phase.
- Real profile batch training produced a reportable multi-profile result across
  public product-like API sources.

## Evidence

- Profile draft training:
  `dev_logs/training/2026-05-15_profile_draft_training.json`
- Replay executor training:
  `dev_logs/training/replay_executor_training_20260515_162605.json`
- 30k resumable scale evidence:
  `dev_logs/smoke/scale_resume_30000_20260515_163640.json`
- Real profile batch report:
  `dev_logs/training/2026-05-15_profile_real_batch_report.json`
- Worker handoffs:
  `docs/memory/handoffs/2026-05-15_LLM-2026-001_real_harden4_profile_auto1_profile_draft_smoke.md`,
  `docs/memory/handoffs/2026-05-15_LLM-2026-002_replay_executor_training_scale_resume.md`,
  `docs/memory/handoffs/2026-05-15_LLM-2026-004_profile_harden3_quality_reports_real_batch.md`

## Supervisor Fixes

- Added profile draft crawl preference preservation, so generated profiles
  retain seed URLs and `initial_requests_from_profile()` can create runnable
  requests.
- Added regression tests that prove profile draft round-trips produce seed
  requests.
- Added scale summary merging so pause/resume checkpoint evidence reports the
  complete run total.
- Added regression coverage for the combined resume summary behavior.

## Supervisor Verification

```text
python -m unittest autonomous_crawler.tests.test_profile_draft autonomous_crawler.tests.test_replay_executor autonomous_crawler.tests.test_scale_resume -v
Ran 77 tests
OK

python -m unittest autonomous_crawler.tests.test_browser_scenario_training autonomous_crawler.tests.test_profile_ecommerce_runner autonomous_crawler.tests.test_hook_sandbox_planner autonomous_crawler.tests.test_graphql_training autonomous_crawler.tests.test_native_longrun_stress -v
Ran 169 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 2062 tests in 84.067s
OK (skipped=5)

python -m compileall autonomous_crawler clm.py run_simple.py run_browser_scenario_training_2026_05_15.py run_native_longrun_stress_2026_05_15.py run_profile_training_2026_05_15.py run_real_ecommerce_profile_training_2026_05_15.py run_api_graphql_training_2026_05_15.py run_browser_profile_health_smoke_2026_05_15.py run_profile_draft_training_2026_05_15.py run_replay_executor_training_2026_05_15.py run_scale_resume_2026_05_15.py run_profile_real_batch_2026_05_15.py -q
OK
```

Additional smoke results:

```text
python run_profile_draft_training_2026_05_15.py
Loadable: 10/10
Runner compatible: 10/10
total_initial_requests: 10

python run_replay_executor_training_2026_05_15.py
9 scenarios, 9 passed, credential leak none

python run_scale_resume_2026_05_15.py --count 30000
Total processed: 30000
Unique URLs: 30000
Duplicates: 0
Failed: 0
final_ckpt_succeeded: 30000

python run_profile_real_batch_2026_05_15.py
accepted=true, total_real_records=168
DummyJSON=75 pass, Platzi Fake Store API=73 pass, FakeStoreAPI=20 warn accepted
```

## Documented Limitations

- Replay execution is deterministic fixture/stub execution. It is not yet a
  real JS/WebCrypto execution runtime.
- Profile draft generation creates loadable and runnable profile drafts, but
  selector/API inference still needs refinement on harder real ecommerce sites.
- The 30k resume proof uses deterministic simulated fetch behavior. The next
  milestone should connect the same restart pattern to real
  `URLFrontier` plus `SpiderRuntimeProcessor` long-running crawls.
- Real public dynamic browser training preserved useful partial/failure cases;
  these are training assets, not production guarantees.

## Next Actions

1. Build `REPLAY-RUNTIME-1`: real JS/WebCrypto sandbox execution behind the
   same replay result contract.
2. Build `PROFILE-AUTO-2`: LLM/advisor assisted profile draft refinement and
   missing-field explanation.
3. Build `SCALE-RUNTIME-1`: connect resumable checkpoints to real
   `URLFrontier`, `SpiderRuntimeProcessor`, and `ProductStore` jobs.
4. Run `REAL-ECOM-2`: 600+ records through profile runner on two or three
   public ecommerce/API targets, with generated profile reports.
