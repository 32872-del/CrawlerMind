# Git Workflow Runbook

## Purpose

Git is the project history and rollback mechanism.

Use it to preserve code, docs, memory, assignments, and acceptance records.

## Current Repository

Local repository:

```text
F:\datawork\agent
```

Initialized:

```text
2026-05-07
```

## Before Work

Run:

```text
git status
```

Check:

- no unexpected modified files in your assigned scope
- no unrelated files staged
- runtime/cache files are ignored

## During Work

Stay inside assignment scope.

If you need to edit a file outside scope, record it in your developer log and
ask supervisor when risk is high.

## After Work

Run relevant tests from the assignment.

Default broad verification:

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

Review changed files:

```text
git status --short
git diff --stat
```

## Commit Message Format

Use:

```text
<employee-id>: <short task summary>
```

Examples:

```text
LLM-2026-001: add real browser SPA smoke
LLM-2026-004: audit project state docs
LLM-2026-000: initialize repository and memory model
```

## What To Commit

Commit:

- source code
- tests
- docs
- dev logs
- assignment documents
- acceptance records
- memory/handoff docs

Do not commit:

- runtime SQLite databases
- screenshots
- caches
- `__pycache__`
- local platform metadata
- secrets, cookies, tokens, proxy credentials

## Recovery

Use:

```text
git log --oneline
git show <commit>
```

Avoid destructive reset commands unless the supervisor explicitly approves.
