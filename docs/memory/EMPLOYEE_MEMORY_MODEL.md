# Employee Memory Model

## Purpose

Employee memory is persistent project state.

It is not role-play.

When a new AI session takes over an employee ID, it should inherit the
employee's externalized work state: history, strengths, risks, current
assignment, accepted work, known context, and handoff notes.

The model instance may change. The employee state remains.

## Core Principle

```text
AI session != employee
Employee = persistent project identity + memory files + accepted work history
```

An AI session temporarily operates an employee identity.

The project files are the source of truth.

## Memory Layers

### 1. Identity Memory

Location:

```text
docs/team/employees/
```

Contains:

- permanent employee ID
- display name
- stable strengths
- accepted work
- current assignment
- known risks
- quality notes

This answers:

```text
Who is this employee in the project?
```

### 2. Task Memory

Location:

```text
docs/team/assignments/
docs/team/acceptance/
dev_logs/
```

Contains:

- assigned scope
- owned files
- avoid files
- implementation evidence
- supervisor acceptance decisions

This answers:

```text
What did this employee do, and what is accepted as true?
```

### 3. Project Memory

Location:

```text
PROJECT_STATUS.md
docs/reports/
docs/plans/
docs/blueprints/
docs/reviews/
```

Contains:

- current stage
- current limitations
- daily progress
- roadmap
- engineering reviews

This answers:

```text
Where is the project now?
```

### 4. Decision Memory

Planned location:

```text
docs/decisions/
```

Contains architecture decisions that should survive context loss.

This answers:

```text
Why did we choose this direction?
```

### 5. Handoff Memory

Planned location:

```text
docs/memory/handoffs/
```

Contains compact continuation notes for the next session operating an employee
ID.

This answers:

```text
What does the next AI need to know to continue safely?
```

## Session Takeover Protocol

When an AI takes over an existing employee ID, it must read:

```text
PROJECT_STATUS.md
docs/team/TEAM_BOARD.md
docs/team/employees/<employee>.md
current assignment, if any
latest docs/reports/*_DAILY_REPORT.md
relevant acceptance records
relevant dev logs
relevant ADRs, when present
latest handoff note, when present
```

Then it must reply with:

```text
Employee ID:
Operating session:
Current assignment:
Accepted work I inherit:
Known risks I inherit:
Files I may edit:
Files I must avoid:
Open questions:
I understand I am taking over persisted state, not role-playing: yes/no
```

## Memory Update Protocol

At the end of a task, the worker should update or produce:

```text
dev_logs/YYYY-MM-DD_HH-MM_topic.md
docs/team/acceptance/YYYY-MM-DD_topic_ACCEPTED.md  # supervisor only
docs/team/employees/<employee>.md                  # supervisor or approved worker
docs/memory/handoffs/YYYY-MM-DD_<employee>_<topic>.md
```

The handoff note should be short.

Required sections:

```text
# Handoff: <employee> - <topic>

## Current State
## Completed Work
## Verification
## Known Risks
## Next Recommended Action
## Files To Read First
```

## What This Prevents

- losing progress when a conversation ends
- relying on human memory to reconstruct context
- asking a new AI to impersonate an old one
- stale project status after parallel work
- untraceable task ownership

## What This Does Not Solve Yet

- automatic cross-platform synchronization
- Git conflict prevention
- durable runtime job queues
- automatic memory summarization
- semantic retrieval over large project history

Those should be added after the Git and ADR foundation is stable.
