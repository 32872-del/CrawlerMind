# Round 2 Assignment: Long-Run Async Stress And Proxy Metrics

Date: 2026-05-14

Employee: `LLM-2026-002`

Priority: P0

Track: `SCRAPLING-ABSORB-1G / CAP-1.3 / CAP-3.3 / CAP-3.5`

## Mission

After finishing the async fetch pool task, prove it can support long-running
crawls. The goal is not theoretical async support; the goal is measurable
throughput, retry, backpressure, and proxy-health evidence.

## Requirements

1. Add deterministic stress coverage for:
   - 1,000 URL fetch simulation
   - per-domain concurrency limits
   - retry/backoff event counts
   - proxy failures and recovery
2. Feed aggregate async/proxy metrics into a runner summary or an inspectable
   report object.
3. Keep public-network dependencies out of unit tests.
4. Save a dev log and handoff.

## Acceptance

Report:

- throughput metric from deterministic test/smoke
- max concurrency observed per domain
- retry/backoff/proxy success/failure counts
- remaining bottlenecks before 10,000+ real URL runs
