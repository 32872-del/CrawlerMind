# 2026-05-09 Open Source Docs And Onboarding Audit

## Assignee

Employee ID: `LLM-2026-004`

Project Role: `ROLE-DOCS`

Assignment: Open Source Docs And Onboarding Audit

## Scope

Audit the repository as if arriving from GitHub as a new contributor.

Reviewed:

```text
PROJECT_STATUS.md
docs/team/TEAM_BOARD.md
docs/team/employees/LLM-2026-004_WORKER_DELTA.md
docs/team/assignments/2026-05-09_LLM-2026-004_OPEN_SOURCE_DOCS_AUDIT.md
README.md
LICENSE
docs/runbooks/
docs/team/training/
docs/reports/2026-05-08_STAGE_AND_BLUEPRINT_ANALYSIS.txt
CONTRIBUTING.md
.github/
```

No code files were edited.

## Summary

The repository is now much more approachable for new GitHub contributors than
it was earlier in the project. The root README and platform-specific quick
starts are clear about Windows, Linux, and macOS setup, and the no-API-key
mock path is visible. CONTRIBUTING.md and the GitHub templates also exist.

The main remaining problems are status drift and a few stale memory files that
could confuse someone taking over `LLM-2026-004` or reading the team board
without chat context.

## Number Of Findings

6

## Highest Severity

medium

## Findings

### Finding 1

Severity: medium

Files:

```text
docs/team/employees/LLM-2026-004_WORKER_DELTA.md
docs/team/TEAM_BOARD.md
docs/team/acceptance/
```

Issue:

Worker Delta's employee file is stale. It still says the current assignment is
`None`, but the team board shows `Open Source Docs And Onboarding Audit` as the
active assignment. The employee file also stops at the 2026-05-08 audits and
does not reflect the current open-source onboarding work.

Impact:

A new session taking over `LLM-2026-004` could incorrectly think there is no
active assignment and miss the open-source audit scope.

Recommended action:

Supervisor should refresh the employee memory after audit review so the current
assignment matches the board.

### Finding 2

Severity: medium

Files:

```text
PROJECT_STATUS.md
docs/team/TEAM_BOARD.md
docs/reports/2026-05-08_STAGE_AND_BLUEPRINT_ANALYSIS.txt
```

Issue:

`PROJECT_STATUS.md` has already moved into open-source preparation mode and
lists the new open-source preparation docs, training ladder, and contributor
support. The team board also reflects the new open-source roles.

However, the stage-and-blueprint analysis still reads like a pre-open-source
milestone note and is not clearly marked as historical. A fresh contributor may
find it before the current README and assume it is the latest project state.

Impact:

The docs are not contradictory, but the analysis file can mislead because it is
indexed alongside current status documents.

Recommended action:

Mark the analysis explicitly as historical context in its header or link it from
an archival section only.

### Finding 3

Severity: low

Files:

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
```

Issue:

The setup instructions are much better now, but they are split across multiple
entry points. A new GitHub contributor can install on Windows, Linux, and
macOS, and can run without an API key via `mock://catalog`. That said, the root
README, platform-specific quick starts, and Chinese quick start all repeat
nearly the same path with slight wording differences.

Impact:

Low. The information is present, but the duplication increases the chance of
one guide drifting out of sync.

Recommended action:

Keep the README as the canonical quick start and treat the platform-specific
runbooks as platform detail pages. Avoid introducing new setup variants without
updating all three together.

### Finding 4

Severity: low

Files:

```text
README.md
CONTRIBUTING.md
LICENSE
```

Issue:

The open-source basics are in place: license, contribution guide, issue
templates, and workflow docs. But the project still does not explicitly say in
one compact place that hostile anti-bot bypass is out of scope and diagnosis-only
for Cloudflare/CAPTCHA/login targets.

Impact:

Low for experienced readers, but a new contributor could miss the safety
boundary if they read only the front page.

Recommended action:

Keep the current safety note in README and reinforce the same boundary in
contributor-facing release notes or onboarding docs.

### Finding 5

Severity: low

Files:

```text
CONTRIBUTING.md
.github/workflows/tests.yml
```

Issue:

The contribution guide says browser smoke tests are optional and deterministic
fixtures/mocks are enough for CI. The workflow matches that by skipping browser
smoke. Good.

The only drift is that the guide refers to "current project structure" only
indirectly, so a new contributor may not realize that API key free paths are
first-class and expected in CI/local dev.

Impact:

Low. The behavior is correct, but the contributor guide could be a little more
explicit about the no-key path being the default test route.

Recommended action:

When next edited, call out `mock://catalog` and `python run_simple.py
--check-llm` as the standard newcomer sanity checks.

### Finding 6

Severity: low

Files:

```text
docs/runbooks/OPEN_SOURCE_RELEASE_CHECKLIST.md
docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md
```

Issue:

The release checklist and training ladder are useful, but they are not linked
from the root README or the onboarding flow. New contributors may not discover
them unless they already know the docs tree.

Impact:

Low to medium for discoverability.

Recommended action:

Add one short pointer from the README or quick-start docs to the release
checklist and training ladder once the docs set is stable.

## Audit Answers

- Can a new user install on Windows, Linux, and macOS? Yes, the README and
  platform-specific quick starts cover all three.
- Is it clear how to run without an API key? Yes, `mock://catalog` and the
  no-key mock path are visible.
- Is it clear how to configure an OpenAI-compatible API? Yes, in README,
  platform quick starts, and `CONTRIBUTING.md`.
- Is it clear that hostile anti-bot bypass is out of scope? Mostly yes, but it
  should be reinforced in contributor-facing docs.
- Are project status and team board consistent? Mostly yes, but the employee
  memory file is stale and the stage analysis is easy to misread as current.
- Are open-source release gaps visible? Yes, especially in the release
  checklist.
- Are there stale or misleading docs? Yes, mainly Worker Delta memory and the
  stage/blueprint analysis framing.

## Recommended Supervisor Action

Accept the audit, then refresh Worker Delta memory and mark
`docs/reports/2026-05-08_STAGE_AND_BLUEPRINT_ANALYSIS.txt` as historical or
archival context so new contributors do not confuse it with current status.

## No-Conflict Confirmation

- No code files were edited.
- No README, status, board, runbook, or training file was edited.
- Created only assignment-allowed files:
  - this audit report
  - one developer log
  - one handoff note
- Existing unrelated worktree changes were observed and left untouched.

## Verification

Commands/read checks performed:

```text
git pull origin main
git status --short
Get-Content PROJECT_STATUS.md
Get-Content docs/team/TEAM_BOARD.md
Get-Content docs/team/employees/LLM-2026-004_WORKER_DELTA.md
Get-Content docs/team/assignments/2026-05-09_LLM-2026-004_OPEN_SOURCE_DOCS_AUDIT.md
Get-Content README.md
Get-Content LICENSE
Get-Content docs/reports/2026-05-08_STAGE_AND_BLUEPRINT_ANALYSIS.txt
Get-Content CONTRIBUTING.md
Get-Content .github/workflows/tests.yml
Get-Content docs/runbooks/README.md
Get-Content docs/runbooks/OPEN_SOURCE_RELEASE_CHECKLIST.md
Get-Content docs/runbooks/QUICK_START_WINDOWS.md
Get-Content docs/runbooks/QUICK_START_LINUX_MAC.md
Get-Content docs/runbooks/QUICK_START_CN.md
Get-Content docs/team/training/NEW_LLM_ONBOARDING.md
Get-Content docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md
Get-ChildItem -Recurse -File -Filter CONTRIBUTING*
Get-ChildItem -Recurse -Directory -Filter .github
```

No tests were run because this is a documentation-only audit.
