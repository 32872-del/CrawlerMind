# Project Roles

## Principle

Project roles are temporary assignments.

Employees are permanent identities.

One employee may hold different project roles over time.

## Current Roles

| Role ID | Role Name | Typical Ownership |
|---|---|---|
| ROLE-SUPERVISOR | Project Supervisor | project direction, assignments, acceptance |
| ROLE-BROWSER | Browser Executor Worker | browser fetch, executor browser branch, browser tests |
| ROLE-QA | Error Path QA Worker | failure tests, retry tests, defensive behavior |
| ROLE-STORAGE | Storage / CLI Worker | SQLite result store, result CLI, exports |
| ROLE-STRATEGY | Strategy / Engine Routing Worker | strategy rules, engine selection, site specs |
| ROLE-API | API Job Worker | FastAPI service boundary, background jobs, API tests |
| ROLE-DOCS | Documentation Worker | docs, reports, plans, onboarding |

## Assignment Mapping

Assignments should declare:

```text
Employee ID:
Project Role:
Assignment:
Owned Files:
Avoid Files:
Acceptance Target:
```

## Role Change Rule

When an employee changes role:

1. Update `docs/team/employees/EMPLOYEE_REGISTRY.md`.
2. Update the employee badge file.
3. Update `docs/team/TEAM_BOARD.md`.
4. Create or update assignment document.
