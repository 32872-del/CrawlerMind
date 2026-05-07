# ADR-003: Local Background Jobs Are In-Memory For MVP

## Status

Accepted

## Date

2026-05-07

## Decision Owner

`LLM-2026-000`

## Context

FastAPI `/crawl` now returns immediately and runs the workflow in a background
thread. The project needs a local MVP before adopting durable queues.

## Options

| Option | Pros | Cons |
|---|---|---|
| In-memory job registry | Simple, no new service dependency, good for local MVP | In-flight jobs are lost on restart, no cross-process state |
| SQLite-backed job registry | More durable, still local | More schema and lifecycle complexity |
| Redis/Celery queue | Production-oriented | Adds infrastructure too early |

## Decision

Use an in-memory job registry for the local MVP.

Persist completed workflow results to SQLite as before.

## Consequences

- Running jobs are lost if the process exits.
- Completed jobs remain available through SQLite.
- This limitation must stay documented.
- Rate limiting and max concurrency are not solved yet.

## Follow-Up

Add either SQLite-backed job state or concurrency limits before long-running
service use.
