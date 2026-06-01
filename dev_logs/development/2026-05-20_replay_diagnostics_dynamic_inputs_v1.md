# 2026-05-20 Replay Diagnostics + Dynamic Inputs v1

## Summary

This block starts the next backend hard-capability layer after POST/GraphQL
replay. CLM can now inspect an API request and describe whether replay is stable,
requires dynamic input refresh, depends on session headers, or likely needs a
signature/token hook.

## Changes

- Added `autonomous_crawler/tools/replay_diagnostics.py`
  - Detects timestamp-like query/header/body fields.
  - Detects nonce/request-id/random-like fields.
  - Detects signature/token-like query/header/body fields.
  - Detects session headers such as store, CSRF/XSRF, cookie, and authorization.
  - Produces `replay-diagnostics/v1`.
  - Provides `apply_replay_dynamic_inputs()` to refresh generic dynamic values.

- Updated `autonomous_crawler/runners/api_replay_promotion.py`
  - Promoted API profiles now include `api_hints.replay_diagnostics` when the
    captured request contains replay-fragile parts.

- Updated `autonomous_crawler/runners/profile_ecommerce.py`
  - API seed requests and API pagination requests apply replay diagnostics before
    dispatch.
  - Generic query/header/JSON dynamic inputs can be refreshed per request.

- Updated `autonomous_crawler/tools/browser_network_observer.py`
  - API candidates now include `replay_diagnostics` when a captured candidate
    shows dynamic, signed, or session-bound fields.

- Updated `autonomous_crawler/api/app.py`
  - Managed profile patch allowlist accepts bounded
    `api_hints.replay_diagnostics`.

## Verification

Passed targeted checks:

```text
python -m unittest autonomous_crawler.tests.test_replay_diagnostics -v
python -m unittest autonomous_crawler.tests.test_managed_actions.ManagedActionPlanTests.test_inspect_access_promotes_post_graphql_xhr_to_replayable_profile autonomous_crawler.tests.test_managed_actions.ManagedActionPlanTests.test_profile_api_requests_refresh_replay_dynamic_inputs -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_ai_can_apply_post_graphql_replay_profile_patch -v
```

## Capability Impact

CLM now has an explicit explanation layer for common API replay failures:

- "This API likely needs refreshed timestamp/nonce."
- "This API has a signature/token component."
- "This API appears tied to browser/session headers."

The backend can already refresh generic timestamp/nonce/request-id fields. Custom
signature generation remains the next hard-capability block and should connect
existing `hook_sandbox_planner` / `replay_executor` outputs into
`SiteProfile.api_hints`.
