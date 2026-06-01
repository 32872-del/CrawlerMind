# 2026-05-20 Supervisor Memory - Backend Hard Capability

Agentmemory MCP still returned `Transport closed`, so this is the local
fallback memory for the current supervisor thread.

Current product direction:

- Keep CLM focused on crawler backend hard capability first.
- Avoid drifting into visibility-only or analysis-only work.
- Continue using the existing plan: evidence -> executable replay -> profile
  longrun -> quality/coverage diagnostics.
- User wants large concrete implementation blocks, with capability-first
  backend progress.

Recent baseline:

- POST/GraphQL API replay v1 is implemented.
- Replay diagnostics/dynamic inputs v1 is implemented.
- `api_hints.replay_diagnostics` can mark volatile timestamps/nonces,
  signature/token-like fields, and session-bound headers.
- Profile ecommerce runner already refreshes generic dynamic inputs before API
  seed and pagination requests.

Next implementation block:

- Connect `hook_sandbox_planner` and `replay_executor` to `SiteProfile.api_hints`
  so signed/token API replay moves from "diagnosed" to "executable".
- Add a data-driven bridge that builds a hook/sandbox plan from
  `api_hints.replay_diagnostics`, executes it with the existing sandbox/fixture
  executor, and applies the resulting request patch to profile API requests.
- Keep this generic; no site-specific rules in core.

Touched concepts:

- CAP-2.2 signature/token replay
- CAP-3.5 long-run profile execution
- CAP-5.1 agent strategy runtime
- API/XHR/GraphQL ecommerce replay
