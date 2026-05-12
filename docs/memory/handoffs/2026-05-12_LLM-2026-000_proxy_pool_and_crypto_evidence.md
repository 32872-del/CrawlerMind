# Handoff: Proxy Pool and Crypto Evidence

Date: 2026-05-12

Employee: `LLM-2026-000`

## Current State

CLM now has two new capability foundations.

### CAP-3.3 Pluggable Proxy Pool

File:

```text
autonomous_crawler/tools/proxy_pool.py
```

Use through `ProxyConfig.pool`:

```python
{
    "enabled": True,
    "pool": {
        "enabled": True,
        "strategy": "round_robin",
        "endpoints": ["http://proxy1:8080", "http://proxy2:8080"]
    }
}
```

Selection order:

1. `per_domain`
2. `pool`
3. `default_proxy`

### CAP-2.x Crypto Evidence

File:

```text
autonomous_crawler/tools/js_crypto_analysis.py
```

It is integrated into:

```text
autonomous_crawler/tools/js_evidence.py
```

New JS evidence fields:

```text
items[].crypto_analysis
top_crypto_signals
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_proxy_pool autonomous_crawler.tests.test_access_layer -v
Ran 83 tests
OK

python -m unittest autonomous_crawler.tests.test_js_crypto_analysis autonomous_crawler.tests.test_js_evidence autonomous_crawler.tests.test_js_static_analysis -v
Ran 66 tests
OK
```

## Next Best Move

1. Connect crypto evidence to Strategy as explicit reverse-engineering action
   hints (`hook_plan`, `sandbox_plan`, `api_replay_blocker`).
2. Add an adapter template for paid proxy providers while keeping core provider
   protocol stable.
