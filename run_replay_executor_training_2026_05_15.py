"""REVERSE-HARDEN-2: Replay Executor Training Runner.

Trains the replay executor against deterministic API/GraphQL fixtures:
- Signed URL mock (x-sign + timestamp + nonce query params)
- Signed header mock (authorization + x-signature headers)
- Timestamp/nonce query (dynamic inputs without signature)
- GraphQL auth evidence (auth headers + nested complexity)
- GraphQL rate-limit evidence (429 + retry-after)
- Combined sign + encrypt + dynamic inputs

All fixtures are deterministic — no real API keys required.

Usage:
    python run_replay_executor_training_2026_05_15.py
    python run_replay_executor_training_2026_05_15.py --output dev_logs/training/

Results saved to dev_logs/training/.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from autonomous_crawler.tools.hook_sandbox_planner import (
    DynamicInput,
    HookSandboxPlan,
    HookTarget,
    ReplayStep,
    SandboxTarget,
    plan_hook_sandbox,
)
from autonomous_crawler.tools.replay_executor import (
    FixtureContext,
    execute_replay,
)


# ---------------------------------------------------------------------------
# Training scenarios
# ---------------------------------------------------------------------------

_SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "signed_url_mock",
        "description": "API with x-sign + timestamp + nonce query params",
        "api_candidates": [{
            "url": "https://api.shop.com/products?x-sign=abc123&timestamp=1234567890&nonce=xyz&page=1",
            "method": "GET",
            "kind": "json",
            "status_code": 200,
        }],
        "js_evidence": {},
    },
    {
        "name": "signed_header_mock",
        "description": "API with authorization + x-signature headers",
        "api_candidates": [{
            "url": "https://api.secure.com/data",
            "method": "POST",
            "kind": "json",
            "headers": {"Authorization": "Bearer tok123", "X-Signature": "sig456"},
            "status_code": 200,
        }],
        "js_evidence": {},
    },
    {
        "name": "timestamp_nonce_query",
        "description": "API with timestamp/nonce query params (no signature)",
        "api_candidates": [{
            "url": "https://api.dynamic.com/feed?ts=1715750000&nonce=abc123def",
            "method": "GET",
            "kind": "json",
            "status_code": 200,
        }],
        "js_evidence": {},
    },
    {
        "name": "graphql_auth_evidence",
        "description": "GraphQL with auth headers and nested complexity",
        "api_candidates": [{
            "url": "https://graphql.example.com/",
            "method": "POST",
            "kind": "graphql",
            "headers": {"Authorization": "Bearer gq1_token"},
            "status_code": 200,
            "query": "{ Page(page: 1) { media { id title { romaji } characters { nodes { name } } } } }",
        }],
        "js_evidence": {},
    },
    {
        "name": "graphql_rate_limit",
        "description": "GraphQL rate-limited (429) with retry-after",
        "api_candidates": [{
            "url": "https://graphql.rate-limited.com/",
            "method": "POST",
            "kind": "graphql",
            "headers": {"Retry-After": "30"},
            "status_code": 429,
        }],
        "js_evidence": {},
    },
    {
        "name": "js_sign_hmac_flow",
        "description": "JS HMAC-SHA256 signature flow with timestamp + nonce",
        "api_candidates": [],
        "js_evidence": {
            "items": [{
                "source": "inline",
                "url": "https://shop.com/bundle.js",
                "inline_id": "sign-hmac",
                "crypto_analysis": {
                    "signals": [
                        {"kind": "hmac", "name": "hmacSHA256", "confidence": "high", "context": "hmacSHA256(payload, key)"},
                        {"kind": "timestamp", "name": "timestamp", "confidence": "medium", "context": "Date.now()"},
                        {"kind": "nonce", "name": "nonce", "confidence": "medium", "context": "Math.random()"},
                    ],
                    "categories": ["hmac", "timestamp", "nonce"],
                    "likely_signature_flow": True,
                    "likely_timestamp_nonce_flow": True,
                    "score": 85,
                },
                "suspicious_functions": [
                    {"name": "signRequest", "kind": "declaration", "suspicious": True, "reason": "signature"},
                ],
            }],
        },
    },
    {
        "name": "js_encrypt_aes_flow",
        "description": "JS AES encryption with CryptoJS",
        "api_candidates": [],
        "js_evidence": {
            "items": [{
                "source": "inline",
                "url": "https://secure.app/main.js",
                "inline_id": "encrypt-aes",
                "crypto_analysis": {
                    "signals": [
                        {"kind": "encryption", "name": "cryptojs", "confidence": "high", "context": "CryptoJS.AES.encrypt(data, key)"},
                    ],
                    "categories": ["encryption"],
                    "likely_encryption_flow": True,
                    "score": 70,
                },
                "suspicious_calls": [
                    {"call": "CryptoJS.AES.encrypt", "keyword": "CryptoJS", "category": "encryption", "context": "CryptoJS.AES.encrypt(JSON.stringify(data), key)"},
                ],
            }],
        },
    },
    {
        "name": "combined_sign_encrypt_dynamic",
        "description": "Combined: JS sign + encrypt + timestamp + nonce + API signed URL",
        "api_candidates": [{
            "url": "https://api.complex.com/data?x-sign=abc&timestamp=999&nonce=qwerty",
            "method": "POST",
            "kind": "json",
            "body": '{"encrypted": "AES_CIPHER"}',
            "status_code": 200,
        }],
        "js_evidence": {
            "items": [{
                "source": "inline",
                "url": "https://complex.com/app.js",
                "inline_id": "combined",
                "crypto_analysis": {
                    "signals": [
                        {"kind": "hmac", "name": "hmacSHA256", "confidence": "high"},
                        {"kind": "encryption", "name": "aes", "confidence": "high"},
                        {"kind": "timestamp", "name": "timestamp", "confidence": "medium"},
                        {"kind": "nonce", "name": "nonce", "confidence": "medium"},
                    ],
                    "categories": ["hmac", "encryption", "timestamp", "nonce"],
                    "likely_signature_flow": True,
                    "likely_encryption_flow": True,
                    "likely_timestamp_nonce_flow": True,
                    "score": 95,
                },
            }],
        },
    },
    {
        "name": "clean_no_crypto",
        "description": "Clean API with no crypto/signature/timestamp evidence",
        "api_candidates": [{
            "url": "https://api.public.com/products?page=1&limit=20",
            "method": "GET",
            "kind": "json",
            "status_code": 200,
        }],
        "js_evidence": {
            "items": [{
                "source": "inline",
                "url": "https://public.com/app.js",
                "inline_id": "clean",
                "crypto_analysis": {
                    "signals": [],
                    "categories": [],
                    "score": 0,
                },
            }],
        },
    },
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="REVERSE-HARDEN-2: Replay Executor Training")
    parser.add_argument("--output", type=str, default="dev_logs/training/", help="Output directory")
    args = parser.parse_args()

    print("=" * 70)
    print("REVERSE-HARDEN-2: Replay Executor Training")
    print("=" * 70)
    print()

    results: list[dict[str, Any]] = []
    t0 = time.monotonic()

    for scenario in _SCENARIOS:
        name = scenario["name"]
        desc = scenario["description"]
        print(f"  [{name}] {desc}")

        # Build plan from evidence
        plan = plan_hook_sandbox(
            scenario.get("js_evidence") or {},
            scenario.get("api_candidates") or [],
        )

        # Execute replay
        context = FixtureContext(
            url=(scenario.get("api_candidates") or [{}])[0].get("url", "https://api.example.com/data"),
        )
        replay = execute_replay(plan, context)

        # Build result
        result = {
            "scenario": name,
            "description": desc,
            "plan": {
                "risk_level": plan.risk_level,
                "hook_targets": len(plan.hook_targets),
                "sandbox_targets": len(plan.sandbox_targets),
                "dynamic_inputs": len(plan.dynamic_inputs),
                "replay_steps": len(plan.replay_steps),
                "blockers": plan.blockers,
            },
            "replay": {
                "success": replay.success,
                "steps_run": len(replay.steps_run),
                "steps_ok": sum(1 for s in replay.steps_run if s.status == "ok"),
                "steps_error": sum(1 for s in replay.steps_run if s.status in ("error", "missing_function")),
                "generated_inputs": list(replay.generated_inputs.keys()),
                "hook_outputs": list(replay.hook_outputs.keys()),
                "sandbox_outputs": list(replay.sandbox_outputs.keys()),
                "blockers_remaining": replay.blockers_remaining,
                "credential_leak_detected": replay.credential_leak_detected,
            },
        }
        results.append(result)

        # Print summary
        risk = plan.risk_level
        ok = replay.success
        steps_ok = result["replay"]["steps_ok"]
        steps_err = result["replay"]["steps_error"]
        inputs = result["replay"]["generated_inputs"]
        hooks = result["replay"]["hook_outputs"]

        status = "OK" if ok else ("PARTIAL" if steps_ok > 0 else "FAIL")
        if risk == "none" and ok:
            status = "CLEAN"
        print(f"    Status:   {status}")
        print(f"    Risk:     {risk}")
        print(f"    Steps:    {steps_ok} ok, {steps_err} error")
        if inputs:
            print(f"    Inputs:   {inputs}")
        if hooks:
            print(f"    Hooks:    {hooks}")
        if replay.blockers_remaining:
            print(f"    Blockers: {replay.blockers_remaining[:3]}")
        print()

    elapsed = time.monotonic() - t0

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["replay"]["success"])
    partial = sum(1 for r in results if r["replay"]["steps_ok"] > 0 and not r["replay"]["success"])
    failed = sum(1 for r in results if r["replay"]["steps_ok"] == 0)
    print(f"  Scenarios: {len(results)} total, {passed} passed, {partial} partial, {failed} failed")
    print(f"  Elapsed:   {round(elapsed, 2)}s")
    print()

    for r in results:
        status = "PASS" if r["replay"]["success"] else ("PARTIAL" if r["replay"]["steps_ok"] > 0 else "FAIL")
        risk = r["plan"]["risk_level"]
        print(f"  [{status}] {r['scenario']}: risk={risk}, steps={r['replay']['steps_ok']}/{r['replay']['steps_run']}")
    print("=" * 70)

    # Credential leak check
    leak = any(r["replay"]["credential_leak_detected"] for r in results)
    print(f"\n  Credential leak: {'DETECTED!' if leak else 'none'}")

    # Save report
    report = {
        "task": "REVERSE-HARDEN-2",
        "worker": "LLM-2026-002",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed, 2),
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "partial": partial,
            "failed": failed,
        },
    }
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"replay_executor_training_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
