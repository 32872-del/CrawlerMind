# 2026-05-11 Easy Mode Docs And Command Consistency Audit

## Assignee

Employee ID: `LLM-2026-004`

Project Role: `ROLE-DOCS-AUDIT`

## Scope

Audit Easy Mode implementation and documentation from a new outside user's
perspective.

Reviewed:

```text
README.md
PROJECT_STATUS.md
dev_logs/README.md
docs/process/COLLABORATION_GUIDE.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
docs/team/TEAM_BOARD.md
clm.py
run_simple.py
run_skeleton.py
run_baidu_hot_test.py
run_batch_runner_smoke.py
autonomous_crawler/tests/test_clm_cli.py
```

No code files or product docs were edited.

## Summary

Easy Mode implementation exists: `clm.py` provides `init`, `check`, `crawl`,
`smoke`, and `train` commands, with focused CLI tests. However, the user-facing
README and quick-start runbooks still present `run_simple.py` as the main
beginner entry point. This makes Easy Mode discoverability inconsistent with
the project board, which says Easy Mode CLI/docs work is active.

The main action should be documentation alignment, not pausing implementation.

## Number Of Findings

7

## Highest Severity

medium

## Findings

### Finding 1

Severity: medium

Files:

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
clm.py
```

Issue:

`clm.py` exists and exposes an Easy Mode command set:

```text
init, check, crawl, smoke, train
```

But README and all quick-start docs still recommend `run_simple.py` for the
first environment check, first crawl, LLM check, and normal crawl path.

Impact:

A new user cannot easily find the one recommended Easy Mode entry point. The
project now has two visible beginner paths, and the older path still dominates.

Recommended action:

Update README and platform quick starts so `python clm.py ...` is the primary
new-user path. Keep `run_simple.py` as an advanced/legacy compatibility command
only if still needed.

### Finding 2

Severity: medium

Files:

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
clm.py
```

Issue:

The documented LLM config check is:

```text
python run_simple.py --check-llm
```

Easy Mode's equivalent is:

```text
python clm.py check --llm
```

README and quick starts do not explain the difference between `clm.py check`
(local setup check) and `clm.py check --llm` (real provider request).

Impact:

Users may keep using the old diagnostic command and miss the new Easy Mode
setup check. They may also accidentally make a provider request when they only
wanted a local dependency/config check, or the reverse.

Recommended action:

Document both Easy Mode checks:

```text
python clm.py check
python clm.py check --llm
```

Then demote `python run_simple.py --check-llm` to legacy/developer reference.

### Finding 3

Severity: medium

Files:

```text
README.md
PROJECT_STATUS.md
docs/team/TEAM_BOARD.md
```

Issue:

TEAM_BOARD lists Easy Mode CLI tests, quick-start docs, and docs audit as active
assignments. `PROJECT_STATUS.md` has detailed completed work through runner and
real-site training, but does not yet list Easy Mode CLI as completed or current
stage. README also does not mention `clm.py`.

Impact:

Project state and board are not fully aligned yet. A new worker reading status
first may not know Easy Mode exists or is being introduced.

Recommended action:

After Easy Mode work is accepted, update `PROJECT_STATUS.md` and README in the
same supervisor pass.

### Finding 4

Severity: medium

Files:

```text
docs/runbooks/QUICK_START_CN.md
README.md
PROJECT_STATUS.md
```

Issue:

`QUICK_START_CN.md` still contains mojibake throughout, and README has mojibake
in the Chinese quick-start link label:

```text
Quick start (涓枃)
```

`PROJECT_STATUS.md` also still contains mojibake in the Baidu goal example.

Impact:

Chinese-language onboarding is not reliable for new users. This is especially
visible now that Easy Mode is meant to make first use simpler.

Recommended action:

Treat Chinese quick-start encoding cleanup as a blocking docs polish item before
public release, though not necessarily before internal Easy Mode testing.

### Finding 5

Severity: low

Files:

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
```

Issue:

User and developer workflows are partially separated, but the beginner docs
still include a large "Developer Training Scripts" section with many
scenario-specific commands. This can distract from Easy Mode.

Impact:

Low to medium for outside users. Advanced commands are labeled as internal, but
they still sit in the main README.

Recommended action:

Keep README short: `clm.py init/check/crawl/smoke` for users, and link
developer training scripts to a separate runbook.

### Finding 6

Severity: low

Files:

```text
README.md
PROJECT_STATUS.md
docs/reports/
docs/memory/handoffs/
```

Issue:

The new `dev_logs/` partition is documented in `dev_logs/README.md` and current
README uses `dev_logs/training/`, `dev_logs/smoke/`, and `dev_logs/stress/`.
However, broad repository scan still finds many historical flat
`dev_logs/<file>` references in old reports, handoffs, acceptance records, and
older dev logs.

Impact:

Low. Most are historical evidence references, not current commands. But new
workers may copy stale flat paths from older handoffs.

Recommended action:

Do not rewrite all history. Add a short note in current onboarding/runbook docs:
old flat `dev_logs/<file>` references are historical and may now live under
`development/`, `audits/`, `training/`, `smoke/`, or `stress/`.

### Finding 7

Severity: low

Files:

```text
clm.py
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
```

Issue:

`clm.py crawl --output` supports `.json` and `.xlsx`, but README/quick starts
do not mention the Easy Mode output flag. They still direct result inspection
through SQLite and `run_results.py`.

Impact:

Low. Existing result inspection remains valid, but Easy Mode can provide a
simpler output story if documented.

Recommended action:

When Easy Mode docs are updated, include one beginner-friendly example:

```text
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

## Audit Question Answers

- Can a new user find the one recommended entry point?
  Not yet. `clm.py` exists, but user docs still recommend `run_simple.py`.

- Do documented commands exist and run in principle?
  Yes for the documented `run_simple.py`, `run_results.py`, smoke, and test
  commands. `clm.py --help` and `clm.py smoke --kind runner --plan` also run.

- Is it clear which commands are for users and which are for developers?
  Partially. Training scripts are labeled internal, but the main beginner path
  is still crowded.

- Is LLM optional and clearly configured?
  Yes in current docs, but Easy Mode should document `clm.py check` versus
  `clm.py check --llm`.

- Are output paths consistent with the new `dev_logs/` partition?
  Current README is mostly consistent. Historical references remain.

- Are there stale flat `dev_logs/<file>` references?
  Yes, mostly in historical docs and handoffs. Treat as historical unless they
  appear in current quick-start paths.

- Are safety boundaries clear?
  Yes. README and contributing-style docs state no login/CAPTCHA/Cloudflare
  bypass without authorization.

- Are Windows, Linux, and macOS instructions consistent?
  Mostly yes, but all still use `run_simple.py` rather than Easy Mode.

## Recommended Supervisor Action

Implementation should proceed, but docs should be revised before public-facing
Easy Mode acceptance.

Recommended next action:

1. Make `clm.py` the primary README and Quick Start path.
2. Document:
   - `python clm.py init`
   - `python clm.py check`
   - `python clm.py check --llm`
   - `python clm.py crawl ...`
   - `python clm.py smoke --kind runner`
3. Move `run_simple.py` and training scripts into "developer/legacy commands".
4. Fix Chinese quick-start mojibake.
5. Add a migration note for historical flat `dev_logs/<file>` references.

## No-Conflict Confirmation

- No code files were edited.
- No README, PROJECT_STATUS, quick-start runbook, or TEAM_BOARD file was edited.
- Created only assignment-allowed audit, dev log, and handoff files.
- Existing Easy Mode implementation/doc files from other workers were left
  untouched.

## Verification

Commands/read checks performed:

```text
git pull origin main
git status --short
Get-Content README.md
Get-Content PROJECT_STATUS.md
Get-Content dev_logs/README.md
Get-Content docs/process/COLLABORATION_GUIDE.md
Get-Content docs/runbooks/QUICK_START_WINDOWS.md
Get-Content docs/runbooks/QUICK_START_LINUX_MAC.md
Get-Content docs/runbooks/QUICK_START_CN.md
Get-Content docs/team/TEAM_BOARD.md
Get-Content clm.py
Get-Content run_simple.py
Get-Content run_skeleton.py
Get-Content run_baidu_hot_test.py
Get-Content run_batch_runner_smoke.py
Get-Content autonomous_crawler/tests/test_clm_cli.py
python clm.py --help
python clm.py smoke --kind runner --plan
```

No test suite was run because this is a documentation/command audit.
