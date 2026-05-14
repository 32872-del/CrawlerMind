# CAP-3.3 Proxy Trace Reporting Integration

**Date**: 2026-05-13
**Worker**: LLM-2026-002
**Capability**: CAP-3.3 Proxy pool, CAP-3.5 Long-running crawl stability, CAP-6.2 Evidence/audit

## Summary

Connected proxy trace evidence to the executor reporting path. Every executor return dict now includes a `proxy_trace` field — a credential-safe snapshot of the proxy selection decision and health state. Also wired the proxy into the HTTP client for the default fetch mode.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/agents/executor.py` | **MODIFIED** | Added proxy_trace to all 12 return paths; wired proxy into httpx client |
| `autonomous_crawler/tests/test_proxy_trace.py` | **MODIFIED** | Added 10 executor integration tests |

## Changes in executor.py

### 1. Proxy trace in all return paths

Added at the top of `executor_node` (before branching):
```python
recon_report = state.get("recon_report", {})
_access_config = resolve_access_config(state, recon_report ...)
_proxy_trace = ProxyTrace.from_manager(ProxyManager(_access_config.proxy), target_url)
_trace_dict = _proxy_trace.to_dict()
```

Every return dict now includes `"proxy_trace": _trace_dict`. This covers:
- mock://products, mock://ranking, mock://json-direct
- fnspider (success + failure)
- browser mode (success + failure)
- api_intercept (success + failure)
- HTTP mode (success + failure + unsupported scheme)

### 2. Proxy wired into HTTP client

In the default HTTP fetch path, the proxy URL is now applied:
```python
proxy_url = _access_config.proxy_for(target_url)
if proxy_url:
    client_kwargs["proxy"] = proxy_url
```

Previously HTTP mode ignored proxy configuration entirely. Now it respects `access_config.proxy` when configured.

### 3. Removed duplicate access_config resolution

Browser mode previously called `resolve_access_config()` separately. Now uses the `_access_config` resolved at the top.

## Trace Output Shape

```json
{
  "selected": true,
  "proxy": "http://***:***@proxy:8080",
  "source": "pool_round_robin",
  "provider": "static",
  "strategy": "round_robin",
  "health": {
    "success_count": 5,
    "failure_count": 0,
    "in_cooldown": false
  }
}
```

When proxy is disabled (default):
```json
{
  "selected": false,
  "proxy": "",
  "source": "disabled"
}
```

## Credential Safety

- All proxy URLs go through `redact_proxy_url()` → `***:***@host`
- Health errors go through `redact_error_message()` → URLs and key=value secrets stripped
- Test `test_proxy_trace_no_credentials_leaked` verifies executor output
- Proxy is opt-in: `access_config.proxy.enabled` defaults to `False`

## Test Results

```
Targeted (3 modules): 99/99 OK
Full suite: 1111/1111 OK (4 skipped)
```

## New Tests (10)

- `test_mock_products_has_proxy_trace` — mock path includes trace
- `test_mock_ranking_has_proxy_trace` — mock path includes trace
- `test_mock_json_direct_has_proxy_trace` — mock path includes trace
- `test_default_proxy_disabled` — no access_config → disabled
- `test_proxy_trace_with_pool_config` — pool config → pool source
- `test_proxy_trace_with_per_domain` — per_domain → enabled
- `test_proxy_trace_no_credentials_leaked` — no plaintext in trace
- `test_proxy_trace_in_failed_fnspider` — failure path includes trace
- `test_proxy_trace_default_http_mode` — scheme error includes trace
- `test_proxy_trace_shape_consistent` — core fields always present
