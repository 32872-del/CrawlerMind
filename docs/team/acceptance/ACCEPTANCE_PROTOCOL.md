# Acceptance Protocol

## Purpose

Worker completion is not enough. Project progress is recognized only after
supervisor acceptance.

## Inputs For Acceptance

The supervisor reviews:

1. Assignment document.
2. Changed files.
3. Worker developer log.
4. Test output.
5. Documentation updates.
6. Integration risk.

## Acceptance Criteria

Work can be accepted when:

- Scope matches assignment.
- Implementation is minimal and maintainable.
- Required tests pass.
- Full test suite passes unless explicitly waived.
- Compile check passes.
- Docs/status are updated.
- No unrelated files were changed.
- Any shared-file edits are justified.

## Acceptance Record Format

```text
# YYYY-MM-DD Topic - ACCEPTED

## Assignment
## Assignee
## Scope Reviewed
## Verification
## Accepted Changes
## Risks / Follow-Up
## Supervisor Decision
```

## Rework Record

If not accepted, create:

```text
docs/team/acceptance/YYYY-MM-DD_topic_REWORK.md
```

Include:

- blocker
- required fixes
- verification needed
- whether worker should continue or task should be reassigned

## Project Truth

Developer logs are evidence.

Acceptance records are project truth.
