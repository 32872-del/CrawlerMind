# CAP-3.3 Proxy Health Store + Provider Adapter Template

**Date**: 2026-05-12
**Worker**: LLM-2026-002
**Capability**: CAP-3.3 Pluggable proxy pool, CAP-3.5 Long-running crawl stability, CAP-6.2 Access evidence/audit

## Summary

Added persistent proxy health tracking (SQLite), health store injection into StaticProxyPoolProvider, and a ProviderAdapter template for paid proxy provider integration.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/storage/proxy_health.py` | **NEW** | SQLite-backed ProxyHealthStore with credential-safe storage |
| `autonomous_crawler/tools/proxy_pool.py` | **MODIFIED** | Health store injection into StaticProxyPoolProvider + ProviderAdapter template |
| `autonomous_crawler/tests/test_proxy_health.py` | **NEW** | 32 tests for health store, provider adapter, and integration |

## SQLite Schema

```sql
CREATE TABLE proxy_health (
    proxy_id       TEXT PRIMARY KEY,  -- SHA256 of scheme://host:port/path (16 hex chars)
    proxy_label    TEXT NOT NULL DEFAULT '',  -- redacted URL for display
    domain         TEXT NOT NULL DEFAULT '',
    success_count  INTEGER NOT NULL DEFAULT 0,
    failure_count  INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT NOT NULL DEFAULT '',
    last_used_at   REAL NOT NULL DEFAULT 0,
    cooldown_until REAL NOT NULL DEFAULT 0,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE INDEX idx_proxy_health_domain ON proxy_health(domain);
CREATE INDEX idx_proxy_health_cooldown ON proxy_health(cooldown_until);
```

## Credential Safety

- `proxy_id()`: SHA256 of `scheme://host:port/path` — credentials stripped before hashing
- `redact_proxy_url()`: Replaces `user:pass@` with `***:***@` for display
- `proxy_label` in DB: Always stored redacted
- Test `test_no_plaintext_credentials_stored`: Verifies no plaintext password in any DB row
- **No plaintext proxy passwords are ever persisted**

## Cooldown Logic

- Exponential backoff starting at 30s, doubling per failure after `max_failures`, capped at 600s
- `record_success()` resets failure count and clears cooldown
- `is_available()` checks cooldown_until <= now

## Health Store Injection

- `StaticProxyPoolProvider.__init__` accepts optional `health_store` kwarg
- `report_result()` writes through to health store when present
- `_available_endpoints()` checks health store cooldown
- Fully backward-compatible: works without health store (same as before)

## ProviderAdapter Template

- Base class for paid/API-backed proxy providers
- Subclass `_fetch_endpoints()` for vendor-specific API calls
- Built-in health store integration via `report_result()`
- Not wired into main crawl flow yet — exists for future integration

## Test Results

```
Targeted: 50 tests OK
Full suite: 968 tests OK (4 skipped)
```

## Next Steps

1. Wire ProviderAdapter into ProxyManager for runtime provider switching
2. Add `clm proxy health` CLI command for inspection
3. Integrate with rate limiter for domain-aware cooldown
4. Add concrete provider adapter (e.g., BrightData) when vendor SDK available
