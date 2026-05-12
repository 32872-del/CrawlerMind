# CAP-3.3 Proxy Health Trace Integration

**Date**: 2026-05-12
**Worker**: LLM-2026-002
**Capability**: CAP-3.3 Proxy pool, CAP-3.5 Long-running crawl stability, CAP-6.2 Evidence/audit

## Summary

Added a lightweight, redacted proxy trace mechanism that bridges proxy selection, health state, and evidence chains. Proxy traces can now be embedded in fetch results, runner summaries, or audit logs without leaking credentials.

## Design Decisions

1. **Standalone module** — `proxy_trace.py` does not modify `ProxyManager`, `fetch_policy.py`, or `batch_runner.py` interfaces. It composes on top of existing `describe_selection()` and `ProxyHealthStore`.

2. **Health-aware selection** — `ProxyTrace.from_manager()` temporarily wires the health store into the pool provider via `set_health_store()`, so cooldown-aware `_available_endpoints()` is used during selection. Previous health store is restored after the call.

3. **Error redaction** — `redact_error_message()` strips proxy URLs and `key=value` secrets from error strings before they enter the trace.

4. **Aggregate summary** — `health_store_summary()` produces a proxy-identity-free aggregate for runner summaries (tracked_proxies, healthy, in_cooldown, total_failures).

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/tools/proxy_trace.py` | **NEW** | ProxyTrace dataclass, redact_error_message, health_store_summary |
| `autonomous_crawler/tools/proxy_pool.py` | **MODIFIED** | Added `set_health_store()` to StaticProxyPoolProvider |
| `autonomous_crawler/tests/test_proxy_trace.py` | **NEW** | 39 tests covering all trace scenarios + credential safety |

## API Surface

### `ProxyTrace` (frozen dataclass)

```python
@dataclass(frozen=True)
class ProxyTrace:
    selected: bool = False
    proxy: str = ""          # redacted URL
    source: str = "none"     # per_domain | pool_round_robin | disabled | …
    provider: str = ""       # static | brightdata | …
    strategy: str = ""       # round_robin | domain_sticky | first_healthy
    health: dict = {}        # success_count, failure_count, in_cooldown, …
    errors: tuple = ()

    def to_dict(self) -> dict: ...
    
    @classmethod
    def disabled(cls) -> ProxyTrace: ...
    
    @classmethod
    def from_selection(cls, selection, *, health_store=None, now=0.0) -> ProxyTrace: ...
    
    @classmethod
    def from_manager(cls, manager, target_url, *, health_store=None, now=0.0) -> ProxyTrace: ...
```

### `health_store_summary(health_store, *, now=0.0) -> dict`

Returns aggregate stats without exposing individual proxy identity:
```python
{"tracked_proxies": 3, "healthy": 2, "in_cooldown": 1, "total_failures": 5}
```

### `redact_error_message(message: str) -> str`

Strips proxy URLs and `password=...`, `token=...`, `api_key=...` patterns from error strings.

## Trace Scenarios Covered

| Scenario | `selected` | `source` | `health` |
|----------|-----------|----------|----------|
| Proxy disabled | `False` | `"disabled"` | `{}` |
| No proxy configured | `False` | `"none"` | `{}` |
| Pool round-robin | `True` | `"pool_round_robin"` | `{success, failure, cooldown}` |
| Per-domain override | `True` | `"per_domain"` | `{…}` |
| Cooldown active | `True` | varies | `{in_cooldown: True, cooldown_until: …}` |
| Pool empty | `False` | `"pool_empty"` | `{}` |

## Credential Safety

- All proxy URLs in trace output go through `redact_proxy_url()` → `***:***@host`
- Error messages go through `redact_error_message()` → URLs and key=value secrets stripped
- `health_store_summary()` exposes zero individual proxy identity
- `ProxyTrace` is frozen (immutable) — no post-creation mutation
- Test `CredentialSafetyTests` (6 tests) verifies no plaintext in any trace output

## Test Results

```
Targeted (3 modules): 89/89 OK
Full suite: 1020/1020 OK (4 skipped)
```

## Integration Points (future)

1. **fetch_policy.py**: Add `proxy_trace: ProxyTrace` to `FetchAttempt.access_context`
2. **batch_runner.py**: Carry `ProxyTrace.to_dict()` in `ItemProcessResult.metrics["proxy_trace"]`
3. **access_policy.py**: Accept `ProxyTrace` instead of bare `proxy_enabled` boolean
4. **CLI**: `clm proxy trace --url <url>` to inspect trace for a target URL
