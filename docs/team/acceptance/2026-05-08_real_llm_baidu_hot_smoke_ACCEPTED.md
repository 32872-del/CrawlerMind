# 2026-05-08 Real LLM Baidu Hot Smoke - ACCEPTED

## Scope Reviewed

Supervisor reviewed the latest persisted run artifact:

```text
dev_logs/runtime/skeleton_run_result.json
```

The run used:

```text
Goal: collect top 30 hot searches
URL:  https://top.baidu.com/board?tab=realtime
LLM:  enabled
```

## Result

Accepted.

The workflow completed end to end:

```text
Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
```

Observed result:

```text
Final status: completed
Items extracted: 30
Confidence: 1.0
Validation: passed
Completeness: 100%
Retries: 0
LLM decisions: 2
LLM errors: 0
```

## Evidence

Workflow log excerpt:

```text
[Planner] Goal: collect top 30 hot searches
[Recon] Analyzed https://top.baidu.com/board?tab=realtime - framework=unknown, items=51, anti_bot=False
[Strategy] Mode=http, Method=dom_parse, Rationale=Ranking list with inferred DOM selectors
[Executor] Mode=http, fetched https://top.baidu.com/board?tab=realtime (200, 196850 chars)
[Extractor] Extracted 30 items, confidence=1.00
[Validator] PASSED - 30 items, completeness=100%
```

LLM advisor behavior:

- Planner accepted task type, target fields, max items, crawl preferences, and reasoning summary.
- Strategy accepted mode, engine, wait selector, wait until, max items, and reasoning summary.
- Strategy preserved deterministic selectors for the Baidu ranking page instead of replacing strong recon selectors.

## Related Fixes

Two supervisor fixes were completed before this acceptance:

- `6a9541b LLM-2026-000: harden OpenAI-compatible adapter`
- `3e700d4 LLM-2026-000: keep mock fixtures off fnspider`

The second fix was validated with:

```text
python run_simple.py "collect product titles and prices" mock://catalog
Final Status: completed
Extracted Data: 2 items
```

## Capability Impact

This is the first accepted real LLM-assisted smoke run against a public page.

Crawler-Mind is now beyond a deterministic-only pipeline for CLI usage:

- Level 1 HTML Pipeline: MVP complete.
- Level 2 Browser Rendering: MVP complete.
- Level 5 Autonomous Agent: early LLM-assisted Planner/Strategy slice is working in CLI.

Level 5 is not complete yet because Validator, self-healing, site memory, and exploration planning are still incomplete.

## Remaining Risks

- FastAPI does not yet expose opt-in LLM advisor configuration.
- API interception remains incomplete.
- Site mental model and visual recon are still blueprint-level.
- LLM provider behavior needs more samples across OpenAI-compatible gateways.

## Supervisor Decision

Accepted as the 2026-05-08 LLM-assisted real-site smoke milestone.
