# Scrapling Source Tracking Plan

Date: 2026-05-14

Purpose: establish a lightweight record for using Scrapling as a capability
source while CLM absorbs the useful behavior into its own crawler backend.

This plan does not define success as "install and call the `scrapling` package".
It defines success as "understand the useful Scrapling capabilities, compare
them with CLM's current behavior, then implement or reorganize equivalent
capabilities as CLM-native runtime modules".

## Source Snapshot

Current local source inspected:

```text
F:\datawork\Scrapling-0.4.8
```

Source metadata from `pyproject.toml`:

```text
name: scrapling
version: 0.4.8
license: LICENSE file
requires-python: >=3.10
repository: https://github.com/D4Vinci/Scrapling
documentation: https://scrapling.readthedocs.io/en/latest/
author: Karim Shoair
maintainer: Karim Shoair
```

License metadata from `LICENSE`:

```text
license: BSD 3-Clause
copyright: Copyright (c) 2024, Karim shoair
```

## Tracking Requirement

Before CLM vendors, copies, adapts, or relies on Scrapling-specific behavior,
record the following:

| Field | Required | Notes |
|---|---|---|
| upstream package | yes | `scrapling` |
| upstream version | yes | e.g. `0.4.8` |
| acquisition date | yes | date source was downloaded or dependency pinned |
| upstream repository | yes | include URL |
| upstream docs | recommended | include URL |
| license | yes | BSD 3-Clause |
| copied source files | yes if copied | exact paths |
| adapted source files | yes if adapted | exact paths and local owner |
| imported API surface | yes during transition | Fetcher, Selector, DynamicFetcher, etc. when used as temporary adapter baseline |
| absorbed capability | yes | e.g. static fetch, parser, browser, proxy rotation, scheduler |
| local adapter files | yes | CLM files that wrap or depend on Scrapling |
| native CLM target files | yes | local files where behavior is reimplemented or reorganized |
| redistribution notice location | yes if source is copied | where license/notice is preserved |
| update policy | yes | who reviews new upstream versions |

## Recommended Repository Locations

Allowed immediately by this assignment:

```text
docs/plans/2026-05-14_SCRAPLING_SOURCE_TRACKING_PLAN.md
```

Recommended future locations if supervisor opens write scope:

```text
docs/vendor/scrapling/SOURCE_RECORD.md
docs/vendor/scrapling/NOTICE.md
docs/vendor/scrapling/UPSTREAM_DIFFS.md
```

Do not put downloaded external source trees, proxy binaries, browser binaries,
or generated runtime caches into the CLM repository unless a future vendor
decision explicitly requires it. The preferred route is native absorption:
study behavior, write CLM-owned modules, keep provenance records, and test
against transition adapters or fixtures.

## License Notice Guidance

Scrapling's BSD 3-Clause license permits source and binary redistribution with
conditions. CLM maintainers should preserve:

- the copyright notice
- the list of license conditions
- the warranty disclaimer
- the non-endorsement condition for the copyright holder and contributors

When packaging CLM with copied Scrapling code or binary artifacts, include the
license notice in distributed documentation or materials.

## Adapter Documentation Checklist

Every Scrapling absorption PR should include:

- runtime capability being mapped: static, parser, browser, protected, proxy,
  session, or spider
- CLM runtime protocol interface used
- whether Scrapling is used as a transition dependency, copied source, or
  pure behavior reference
- source tracking update
- redaction check and governance-doc update when needed
- fallback behavior when Scrapling is missing or fails
- tests proving `mock://` and non-Scrapling paths still behave deterministically
- native CLM module or target module that will own the behavior long term

## Stale Documentation Risks To Track

- `README.md` should describe Scrapling work as capability absorption, not as
  a finished external-package wrapper.
- `PROJECT_STATUS.md` should distinguish transition adapters from CLM-native
  backend absorption.
- `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md` should keep
  `SCRAPLING-ABSORB-*` rows current as native modules land.
- `docs/team/TEAM_BOARD.md` already lists Scrapling assignments. This audit did
  not modify the board because the assignment prohibited it.
- Historical dev logs and audits may mention `httpx`, browser tools, fnspider,
  or access diagnostics as independent paths. Those are historical records and
  should not be rewritten; future summaries should explain how they become
  fallback or specialized tools behind the CLM runtime protocol.

## Next Steps

1. Maintain an absorption record that maps Scrapling source concepts to CLM
   target modules.
2. Runtime workers record exact Scrapling APIs they use during the transition
   period.
3. Replace adapter-backed behavior with CLM-native implementations in small,
   testable slices.
4. Use transition adapters as benchmarks while native modules mature.
5. After browser/session/proxy absorption, update Access Layer and Advanced
   Diagnostics docs to describe how native runtime events map into evidence.
