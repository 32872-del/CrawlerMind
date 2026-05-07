# ADR-004: Fnspider Routing Is Explicit Until More Site Samples Exist

## Status

Accepted

## Date

2026-05-07

## Decision Owner

`LLM-2026-000`

## Context

The project bundles a mature `fnspider` engine, but the current lightweight DOM
path is already reliable for Baidu-style ranking lists.

Automatic engine selection without site samples may route tasks incorrectly.

## Options

| Option | Pros | Cons |
|---|---|---|
| Always prefer fnspider | Uses mature engine | Can overfit product-list assumptions and break ranking-list tasks |
| Automatic selection now | More autonomous | Insufficient evidence and test coverage |
| Explicit routing only | Predictable and testable | Less autonomous until sampling improves |

## Decision

Fnspider routing remains explicit.

Supported explicit inputs:

```text
preferred_engine="fnspider"
crawl_preferences={"engine": "fnspider"}
```

Ranking-list tasks stay on the lightweight DOM path.

## Consequences

- Product-list tasks can opt into fnspider.
- Ranking-list tasks avoid unnecessary engine complexity.
- Automatic selection is deferred.

## Follow-Up

Collect real site samples before designing automatic engine selection.
