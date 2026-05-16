# Acceptance: Scrapling Harden Round 1 And 2

Date: 2026-05-15

Employee: `LLM-2026-000`

Assignments:

- combined supervisor acceptance for `LLM-2026-001`, `LLM-2026-002`, and
  `LLM-2026-004`

Status: accepted

## Verdict

Accepted. The first hardening block after Scrapling absorption is complete:
browser scenarios, profile health, API/GraphQL evidence, native long-run
metrics, and profile ecommerce training now have deterministic tests and
training artifacts.

## Combined Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1903 tests in 82.387s
OK (skipped=5)

python -m compileall autonomous_crawler clm.py run_browser_profile_health_smoke_2026_05_15.py run_browser_scenario_training_2026_05_15.py run_api_graphql_training_2026_05_15.py run_native_longrun_stress_2026_05_15.py run_profile_training_2026_05_15.py
OK
```

## Accepted Scope

- Browser profile health scoring and scenario training.
- Native async/API/GraphQL training and reverse replay-risk evidence.
- Native long-run summary metrics and checkpoint roundtrip validation.
- Profile ecommerce library and deterministic training artifacts.
- Real-site scenario matrix preserved under `docs/team/training/`.

## Remaining Product Work

- Real public dynamic and ecommerce profile training. Superseded on
  2026-05-15 by
  `docs/team/acceptance/2026-05-15_real_scale_reverse_profile_hardening_ACCEPTED.md`.
- 10k/30k native spider stress using the new summary and profile paths.
  Superseded on 2026-05-15 by the real/scale/reverse/profile hardening
  acceptance record.
- Persistent health decay/persistence. Accepted for browser profile health on
  2026-05-15; adaptive async concurrency remains future work.
- JS hook/sandbox MVP for signature-function localization. Initial planning MVP
  accepted on 2026-05-15; executable replay remains future work.
- Product-facing CLI/API/UI simplification.
