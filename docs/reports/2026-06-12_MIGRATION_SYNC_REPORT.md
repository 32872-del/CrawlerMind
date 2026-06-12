# 2026-06-12 CLM Migration Sync Report

## Summary

This report records the repository state before moving CLM to a new development
environment.

CLM is no longer only a LangGraph crawler MVP. The current project is an early
AI-managed crawler platform with:

- Easy Mode CLI
- FastAPI product workflow APIs
- Chinese React workbench
- CLM-native crawler/runtime backend
- profile longrun and checkpoint foundation
- managed actions
- quality gate and diagnosis/repair loop
- extraction contract discovery
- real-site training evidence

## Current Progress

Estimated maturity:

```text
Overall: 68% - 75%
Level 1 skeleton: complete
Level 2 usable MVP: complete
Level 3 advanced crawler backend: 75% - 82%
Level 4 visible AI decision loop: 58% - 68%
Level 5 product workbench / long-run operations: 45% - 55%
```

Current mainline:

```text
AI managed workflow -> evidence/recon -> profile/runtime patch -> long-run execution -> quality/export
```

## Recent Important Capabilities

- `execute_and_run()` connects managed actions to profile longrun execution.
- `diagnose_and_repair()` implements the first closed-loop repair function.
- `QualityGate` evaluates record count, required fields, field coverage, and
  critical failures.
- Managed API endpoints now include:
  - `/runs/{task_id}/managed-control-loop`
  - `/runs/managed/execute-and-run`
  - `/runs/managed/diagnose-and-repair`
- `/site/analyze` can return extraction contract discovery and profile-carried
  extraction evidence.
- The frontend workbench can use model config, task details, AI managed panels,
  export path tools, and one-click workflow wiring.

## Synced Local Evidence

The 2026-06-02 E2E managed-loop training batch is being preserved in Git:

```text
dev_logs/training/e2e_site_list_20260602/
```

This includes:

- `training_report.md`
- `analysis.md`
- `full_results.json`
- per-site result JSON files

The training result showed useful progress but also an important regression
signal: managed loop execution can still underperform direct crawl on some sites
such as JSON APIs, pagination pages, and Superdry-style ecommerce pages.

## Current Gaps

- Managed loop hardening: preserve successful direct crawl paths and avoid
  weaker reanalysis overriding known-good extraction.
- API detection: improve pure JSON array APIs, Firebase-like APIs, and
  GraphQL endpoint handling.
- Pagination: ensure detected pagination is actually executed in profile runs.
- Browser/SPAs: Playwright must be installed on the new environment for dynamic
  training and browser fallback.
- Frontend: one-click workflow exists but still needs polish around live AI
  process visibility and smoother task handoff.
- Persistence: job registry/runtime state remains local and should be made more
  durable for production-style workbench usage.

## Migration Runbook

Use:

```text
docs/runbooks/ENVIRONMENT_MIGRATION_2026_06_12.md
```

The repo intentionally does not sync:

```text
.venv/
frontend/node_modules/
frontend/dist/
clm_config.json
runtime databases
browser artifacts
exports
```

These are regenerated or manually copied only if historical runtime state is
needed.

## Next Development Priority

After the environment move, continue with:

```text
Managed-loop real-site hardening
```

Priority order:

1. Make managed loop preserve direct crawl/API success paths.
2. Fix JSON array and Firebase-style API extraction inside managed workflow.
3. Wire extraction contract discovery into browser/XHR and API replay evidence.
4. Improve pagination execution and coverage reporting.
5. Run a fresh E2E managed-loop batch with Playwright installed.
