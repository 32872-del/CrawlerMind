# Round 2 Assignment: Profile-Driven Ecommerce Runner

Date: 2026-05-14

Employee: `LLM-2026-004`

Priority: P0

Track: `SCRAPLING-ABSORB-3H / CAP-3.1 / CAP-3.6 / CAP-5.3`

## Mission

After finishing the LangGraph BatchRunner processor and site profile schema,
turn the schema into a usable profile-driven ecommerce run path.

## Requirements

1. Add a deterministic ecommerce profile fixture that includes:
   - list selectors
   - detail selectors
   - pagination or link discovery hints
   - access config
   - quality expectations
2. Add a runner smoke that uses the profile to collect structured product-like
   records through the long-running runner path.
3. Prove pause/resume still works with profile-driven execution.
4. Save output evidence under `dev_logs/training/` or `dev_logs/smoke/`.

## Acceptance

Report:

- profile schema example
- collected record count
- pause/resume evidence
- remaining gap between fixture profile and real ecommerce sites
