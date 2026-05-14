# 2026-05-14 - Scrapling Absorption Direction Correction

Owner: LLM-2026-000

## Context

The project owner clarified that the goal is not to wrap or vendor Scrapling as
an external package inside CLM. The goal is to absorb Scrapling 0.4.8's crawler
capabilities into CLM as a strong native backend.

## Correction

Previous wording such as "Scrapling-first runtime" could be misread as:

```text
CLM -> call scrapling package
```

The corrected architecture goal is:

```text
CLM Agent -> CLM Runtime Protocol -> CLM Native Backend
```

Scrapling is now documented as:

- capability source
- engineering reference
- temporary adapter benchmark

The current adapters are useful transition bridges, not the final backend.

## Documents Updated

- `docs/plans/2026-05-14_SCRAPLING_FIRST_RUNTIME_PLAN.md`
- `docs/runbooks/SCRAPLING_FIRST_RUNTIME.md`
- `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md`
- `docs/plans/2026-05-14_SCRAPLING_SOURCE_TRACKING_PLAN.md`
- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/TEAM_BOARD.md`
- `PROJECT_STATUS.md`
- `README.md`
- `requirements.txt`

## Current Truth

CLM has transition adapters for Scrapling static/parser/browser/session/proxy
behavior, and executor routing can enter `engine="scrapling"`. Full absorption
is not complete.

The next engineering task is `SCRAPLING-ABSORB-1`: convert static fetch and
parser behavior into CLM-native backend modules, using current adapters as
oracles and benchmarks.

