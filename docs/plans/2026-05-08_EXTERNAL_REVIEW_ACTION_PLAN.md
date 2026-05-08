# 2026-05-08 External Review Action Plan

## Summary

Two external reports agreed with the supervisor assessment:

- CLM is now a real MVP, not just a demo.
- Architecture is strong.
- Product and operations maturity are still early.
- The next cycle should reduce operational friction and prove broader crawl
  coverage before adding a large frontend surface.

## Product Direction Decision

Do not start the full frontend app yet.

Reason:

- A frontend would improve usability, but it would mostly wrap current backend
  complexity.
- The backend still needs clearer diagnostics, stronger error structures, and
  more real-site coverage.
- A lightweight frontend becomes much easier after API/config/error contracts
  stabilize.

Frontend remains planned for the next product layer:

- configure LLM/API keys
- describe crawl needs
- upload examples
- inspect results and errors
- run provider diagnostics

## P0 Adjustments

### 1. Provider diagnostics

Status: complete.

Implemented:

```text
python run_simple.py --check-llm
```

It validates config, resolves endpoint, hides API key, and sends a minimal JSON
request through the same OpenAI-compatible adapter path used by Planner and
Strategy.

### 2. Structured errors

Status: next P0 item.

Target:

- Define stable error codes for crawler and LLM failures.
- Preserve human-readable messages, but add machine-actionable codes.

Initial code candidates:

```text
LLM_CONFIG_INVALID
LLM_PROVIDER_UNREACHABLE
LLM_RESPONSE_INVALID
FETCH_UNSUPPORTED_SCHEME
FETCH_HTTP_ERROR
BROWSER_RENDER_FAILED
EXTRACTION_EMPTY
SELECTOR_INVALID
VALIDATION_FAILED
ANTI_BOT_BLOCKED
```

### 3. Documentation and release clarity

Status: partially complete.

Needed:

- README polish.
- API usage examples.
- Release note for the current MVP milestone.
- Clear "known limitations" section for dynamic pages, API interception,
  Cloudflare, and persistent jobs.

## P1 Direction

### 1. Dynamic-page capability iteration

User concern is valid: current real-site proof is mostly static HTML. Browser
fallback exists, but real dynamic-site coverage is not broad enough.

Need a small capability matrix:

```text
static HTML list page
local SPA fixture
public JS-rendered page
infinite scroll page
API-backed page
Cloudflare/challenge page
```

For Cloudflare, the policy should be diagnostic and respectful:

- detect challenge/block
- report structured error
- suggest browser/manual/authenticated/API route when appropriate
- do not implement bypass or circumvention logic

### 2. Use local MCP crawler as comparison/borrowed capability

The local MCP crawler can help with:

- access strategy probing
- browser network observation
- pagination inference
- selector/site-spec sampling
- structured crawl diagnostics

Plan:

- use MCP crawler during supervisor research and P1 evaluation
- identify which capabilities should be wrapped or ported into CLM
- avoid hard dependency until portability story is clear

### 3. Site Zoo

Create a small committed registry of target categories and expected outcomes,
without committing sensitive or large runtime artifacts.

Suggested first set:

- `mock://catalog`
- `mock://ranking`
- Baidu realtime hot search
- local SPA fixture
- one simple JS-rendered public page
- one API-backed public page
- one known challenge/protected page for detection-only tests

## Staffing Recommendation

Do not recruit a frontend worker yet unless the goal is a mockup only.

Better staffing now:

- Worker Alpha: structured errors or FastAPI diagnostics.
- Worker Delta: docs/release note/API examples.
- Supervisor: dynamic-page capability plan and MCP crawler comparison.

Frontend worker becomes useful after:

- provider diagnostics endpoint exists
- structured errors exist
- API request/response shape stabilizes
- at least 3-5 site sample categories are tested

## Next Supervisor Task

Complete P0 structured errors, then move into P1 dynamic-page/site-zoo work.
