# Development Log: Proxy Pool and Crypto Evidence

Date: 2026-05-12 17:20

Owner: `LLM-2026-000`

## Goal

Advance capability-first crawler development in two places:

- `CAP-3.3`: make IP/proxy pool support pluggable and opt-in.
- `CAP-2.1/CAP-2.2`: make signature/encryption evidence a built-in CLM
  reverse-engineering signal, not ad-hoc per-site scripting.

## Work Completed

### Pluggable Proxy Pool

- Added `tools/proxy_pool.py`.
- Added provider protocol:

```text
ProxyPoolProvider.select()
ProxyPoolProvider.report_result()
ProxyPoolProvider.to_safe_dict()
```

- Added static provider with:
  - `round_robin`;
  - `domain_sticky`;
  - `first_healthy`;
  - failure-count exclusion;
  - cooldown checks;
  - credential redaction.
- Updated `ProxyManager` priority:
  1. explicit per-domain proxy;
  2. proxy pool;
  3. default proxy.

### Crypto / Signature Evidence

- Added `tools/js_crypto_analysis.py`.
- Detects:
  - MD5/SHA/HMAC;
  - sign/signature;
  - WebCrypto digest/sign/getRandomValues;
  - AES/RSA/CryptoJS;
  - base64/URL encoding;
  - timestamp/nonce;
  - parameter sorting/query joining;
  - custom token families such as x-bogus/wbi.
- Integrated into `tools/js_evidence.py`:
  - per-item `crypto_analysis`;
  - report-level `top_crypto_signals`;
  - recommendations for signature/encryption flows.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_proxy_pool autonomous_crawler.tests.test_access_layer -v
Ran 83 tests
OK

python -m unittest autonomous_crawler.tests.test_js_crypto_analysis autonomous_crawler.tests.test_js_evidence autonomous_crawler.tests.test_js_static_analysis -v
Ran 66 tests
OK
```

## Boundaries

- Proxy pool remains opt-in and does not imply automatic evasion.
- Crypto analysis is evidence-only: no JS execution, no key recovery, no
  challenge solving.

## Next Step

- Add paid-provider adapter examples for proxy pools.
- Add JS sandbox/hook planning so Strategy can convert crypto evidence into a
  controlled reverse-engineering task plan.
