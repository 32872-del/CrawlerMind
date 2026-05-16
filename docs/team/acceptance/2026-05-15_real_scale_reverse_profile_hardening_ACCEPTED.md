# Acceptance: Real Scale Reverse Profile Hardening

Date: 2026-05-15

Employee: `LLM-2026-000`

Assignments:

- `LLM-2026-001`: REAL-HARDEN-1 browser real dynamic training and BROWSER-HARDEN-2 profile health persistence/decay
- `LLM-2026-002`: SCALE-HARDEN-1 native 10k/30k long-run stress and REVERSE-HARDEN-1 JS hook/sandbox planning MVP
- `LLM-2026-004`: REAL-HARDEN-3 real ecommerce profile training and PROFILE-HARDEN-2 profile quality gates/report

Status: accepted

## Verdict

Accepted. This closes the second hardening batch after Scrapling capability
absorption. The work stays on target: Scrapling-inspired capabilities are being
absorbed into CLM-native backend modules, while site-specific behavior remains
in profiles, fixtures, or training artifacts instead of runtime code.

## Accepted Scope

- Browser scenario training now includes real public dynamic/doc-site targets
  and deterministic local fixtures for infinite scroll, virtualized lists, and
  mobile viewport behavior.
- `BrowserProfileHealth` now supports windowed decay scoring, recovery,
  summaries, and JSON persistence through `BrowserProfileHealthStore`.
- Native async scale validation now covers 10,000 URL stress with proxy retry,
  checkpoint roundtrip, backpressure/concurrency metrics, and credential
  redaction checks.
- API/GraphQL training now covers nested fields, cursor pagination, error and
  rate-limit responses, 50+ item page/offset/cursor pagination, and reverse
  replay-risk evidence.
- `hook_sandbox_planner.py` adds a deterministic advisory plan for signatures,
  encrypted payloads, runtime hooks, sandbox execution, dynamic inputs, replay
  steps, risk level, and blockers.
- Profile-driven ecommerce training now covers DOM, API pagination, mixed
  SSR/hydration profiles, and one real public product-like API run.
- `profile_quality_summary()` now emits `quality_gate` reports with `min_items`,
  required-field completeness, duplicate-rate, and failed-URL checks. Default
  mode is report-only; callers can opt in to fail mode.

## Evidence

- Real dynamic browser evidence:
  `dev_logs/training/2026-05-15_real_site_training.json`
- Browser scenario evidence:
  `dev_logs/training/2026-05-15_browser_scenario_training.json`
- Real ecommerce profile evidence:
  `dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json`
- Profile ecommerce fixture evidence:
  `dev_logs/training/2026-05-15_profile_ecommerce_training.json`
- API/GraphQL evidence:
  `dev_logs/training/real_api_training_20260515_103958.json`
- Scale stress evidence:
  `dev_logs/smoke/scale_stress_10000_20260515_103947.json`
  and `dev_logs/smoke/scale_stress_30000_20260515_104053.json`

## Supervisor Verification

```text
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_browser_scenario_training -v
Ran 192 tests in 0.163s
OK

python -m unittest autonomous_crawler.tests.test_native_async_runtime autonomous_crawler.tests.test_native_longrun_stress autonomous_crawler.tests.test_graphql_training autonomous_crawler.tests.test_hook_sandbox_planner -v
Ran 109 tests in 2.576s
OK

python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v
Ran 8 tests in 3.931s
OK

python run_real_ecommerce_profile_training_2026_05_15.py
accepted=true, record_count=75, quality_gate.passed=true

python run_profile_training_2026_05_15.py
accepted=true, total_records=135

python run_api_graphql_training_2026_05_15.py
GraphQL scenarios 4/4 passed, API 50+ pagination 3/3 met threshold

python run_browser_profile_health_smoke_2026_05_15.py
Smoke results: 6 passed, 0 failed out of 6

python run_native_longrun_stress_2026_05_15.py --count 10000
Succeeded: 10000, Failed: 0, Throughput: 2211.2 URLs/s

python -m unittest discover -s autonomous_crawler/tests
Ran 1968 tests in 83.336s
OK (skipped=5)

python -m compileall autonomous_crawler clm.py run_simple.py run_browser_scenario_training_2026_05_15.py run_native_longrun_stress_2026_05_15.py run_profile_training_2026_05_15.py run_real_ecommerce_profile_training_2026_05_15.py run_api_graphql_training_2026_05_15.py run_browser_profile_health_smoke_2026_05_15.py
OK
```

## Supervisor Patch

During acceptance, the supervisor made one small compatibility fix:

- `BrowserProfileHealth.to_dict()` now persists `total_elapsed_seconds`, so
  restored health records preserve average elapsed time correctly.

Focused regression after the patch:

```text
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_profile_ecommerce_runner autonomous_crawler.tests.test_hook_sandbox_planner -v
Ran 161 tests in 5.630s
OK
```

## Remaining Product Work

- Convert hook/sandbox plans into an actual replay execution path for selected
  deterministic fixtures.
- Add real-site profile generation assistance so users do not hand-author
  profiles for every ecommerce site.
- Add adaptive concurrency and persistent async client pooling on top of the
  accepted scale metrics.
- Expand real dynamic training to harder virtualized and protected-profile
  targets.
- Keep simplifying `clm.py` and API/UI entry points so the stronger backend
  becomes easy for operators to use.
