---
worker: LLM-2026-002
date: 2026-05-15
task: REVERSE-HARDEN-2 + SCALE-HARDEN-2 (3 rounds)
status: COMPLETE
---

# Handoff: Replay Executor + Training + Resumable 30k

## What was delivered

### Round 1 — REVERSE-HARDEN-2: Executable Replay Fixture MVP

New module `autonomous_crawler/tools/replay_executor.py` that takes a `HookSandboxPlan` + `FixtureContext` and executes deterministic replay steps:

- **Dynamic input generation**: `Date.now()` → int ms timestamp, `Math.random()` → hex nonce
- **Built-in signature hooks**: hmacSHA256, hmac, sha256, md5, sign, signRequest, api_request_signature
- **Built-in token/encoding hooks**: generateToken (btoa), base64, btoa
- **Sandbox stubs**: aes (deterministic hash-based), cryptojs, api_payload_encryption
- **Credential redaction**: automatic removal of secret_key, api_key, token, etc. from output
- **Custom hooks**: `FixtureContext.hook_implementations` allows override per function name
- **Request preview**: built from generated inputs + hook outputs + sandbox outputs

Tests: 31 passed across 11 test classes (success, missing function, dynamic inputs, encryption stub, credential redaction, request preview, custom context, integration, serialization, deterministic).

### Round 2 — GraphQL/API Replay Training

Training runner `run_replay_executor_training_2026_05_15.py` with 9 deterministic scenarios:

| Scenario | Risk | Steps | Hooks |
|----------|------|-------|-------|
| signed_url_mock | medium | 5/5 | api_request_signature |
| signed_header_mock | medium | 3/3 | api_request_signature |
| timestamp_nonce_query | low | 4/4 | — |
| graphql_auth_evidence | medium | 3/3 | api_request_signature |
| graphql_rate_limit | none | 2/2 | — |
| js_sign_hmac_flow | medium | 6/6 | hmacSHA256, signRequest |
| js_encrypt_aes_flow | medium | 4/4 | — |
| combined_sign_encrypt_dynamic | high | 8/8 | hmacSHA256, api_request_signature |
| clean_no_crypto | none | 2/2 | — |

All 9/9 passed. Output: `dev_logs/training/replay_executor_training_*.json`.

### Round 3 — SCALE-HARDEN-2: Resumable 30k Checkpoint Restart

Script `run_scale_resume_2026_05_15.py` proves CLM can pause mid-run, persist checkpoint, and resume:

- 30k URLs, 20 domains, 4 per-domain / 32 global concurrency
- Phase 1: 18000 URLs → checkpoint → pause
- Phase 2: load checkpoint → resume remaining 12000 → complete
- 0 duplicates, 0 failed, 2127 URLs/s throughput, 14.1s total

Tests: 7 passed (basic resume, boundary, no remaining, roundtrip, failures, status, frontier persistence).

## Key files

| File | Action |
|------|--------|
| `autonomous_crawler/tools/replay_executor.py` | NEW |
| `autonomous_crawler/tests/test_replay_executor.py` | NEW |
| `run_replay_executor_training_2026_05_15.py` | NEW |
| `run_scale_resume_2026_05_15.py` | NEW |
| `autonomous_crawler/tests/test_scale_resume.py` | NEW |
| `dev_logs/development/2026-05-15_LLM-2026-002_replay_executor_training_scale_resume.md` | NEW |
| `dev_logs/smoke/scale_resume_30000_*.json` | NEW |
| `dev_logs/training/replay_executor_training_*.json` | NEW |

## Test results

```
test_replay_executor:          31 passed
test_scale_resume:              7 passed
test_hook_sandbox_planner:     36 passed (REVERSE-HARDEN-1)
test_graphql_training:         42 passed
full suite:                  2009 passed (5 skipped)
compileall:                  clean
```

## Known risks

1. **Replay executor uses stubs** — AES stub is a hash, not real crypto. Real sites need WebCrypto runtime.
2. **Hook matching is prefix-based** — heavily obfuscated names may not match built-in fixtures.
3. **30k resume uses mock** — real network adds latency, retries, partial failures.
4. **Credential redaction is pattern-based** — unknown credential patterns may leak.
5. **Checkpoint summary is per-batch** — final checkpoint only has phase2 summary, not combined.

## Next steps

1. **Real JS bundle replay** — test against minified/obfuscated JS from real sites
2. **WebCrypto sandbox** — implement browser-based crypto.subtle execution
3. **Checkpoint merging** — combine phase1 + phase2 summaries in final checkpoint
4. **Streaming checkpoint** — checkpoint during execution, not just at batch boundaries
5. **Frontier integration** — connect URLFrontier with checkpoint for true resumable crawling
