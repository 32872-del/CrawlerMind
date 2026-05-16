"""Tests for hook_sandbox_planner (REVERSE-HARDEN-1).

Deterministic JS fixtures with known crypto patterns, verifying that
plan_hook_sandbox produces stable, correct hook/sandbox plans.
"""
from __future__ import annotations

import unittest
from typing import Any

from autonomous_crawler.tools.hook_sandbox_planner import (
    DynamicInput,
    HookSandboxPlan,
    HookTarget,
    ReplayStep,
    SandboxTarget,
    plan_hook_sandbox,
)


# ---------------------------------------------------------------------------
# Deterministic JS fixtures (inline strings with known crypto patterns)
# ---------------------------------------------------------------------------

_JS_SIGN_HMAC = """
function signRequest(url, params) {
    var sorted = Object.keys(params).sort().map(function(k) {
        return k + '=' + params[k];
    }).join('&');
    var ts = Date.now();
    var nonce = Math.random().toString(36).substring(2);
    var payload = url + '?' + sorted + '&ts=' + ts + '&nonce=' + nonce;
    var sig = hmacSHA256(payload, SECRET_KEY);
    return { signature: sig, timestamp: ts, nonce: nonce };
}
"""

_JS_ENCRYPT_AES = """
function encryptPayload(data) {
    var key = document.getElementById('cipher-key').value;
    var encrypted = CryptoJS.AES.encrypt(JSON.stringify(data), key).toString();
    return { payload: encrypted };
}
"""

_JS_WEBHOOK_TOKEN = """
function generateToken(sessionId) {
    var ts = Date.now();
    var rand = Math.random().toString(36).substring(2);
    var raw = sessionId + ':' + ts + ':' + rand;
    var token = btoa(raw);
    return { token: token, timestamp: ts };
}
"""

_JS_WEBHOOK_ALL = """
function buildSecureRequest(url, data) {
    var ts = Date.now();
    var nonce = Math.random().toString(36).substring(2);
    var sorted = Object.keys(data).sort().join('&');
    var sig = hmacSHA256(url + sorted + ts + nonce, API_SECRET);
    var key = document.getElementById('ek').value;
    var encrypted = CryptoJS.AES.encrypt(JSON.stringify(data), key).toString();
    var token = btoa(ts + ':' + nonce);
    return { signature: sig, encrypted: encrypted, token: token, ts: ts, nonce: nonce };
}
"""

_JS_CLEAN = """
function renderList(items) {
    var html = '';
    for (var i = 0; i < items.length; i++) {
        html += '<div>' + items[i].name + '</div>';
    }
    document.getElementById('container').innerHTML = html;
}
"""


# ---------------------------------------------------------------------------
# Helpers to build mock JS evidence items
# ---------------------------------------------------------------------------

def _make_crypto_signal(kind: str, name: str, confidence: str = "high", context: str = "") -> dict[str, str]:
    return {"kind": kind, "name": name, "confidence": confidence, "context": context}


def _make_js_item(
    crypto_signals: list[dict[str, Any]] | None = None,
    categories: list[str] | None = None,
    suspicious_functions: list[dict[str, Any]] | None = None,
    suspicious_calls: list[dict[str, Any]] | None = None,
    url: str = "https://example.com/app.js",
    *,
    likely_signature: bool = False,
    likely_encryption: bool = False,
    likely_timestamp_nonce: bool = False,
) -> dict[str, Any]:
    crypto_analysis: dict[str, Any] = {}
    if crypto_signals is not None:
        crypto_analysis["signals"] = crypto_signals
    if categories is not None:
        crypto_analysis["categories"] = categories
    crypto_analysis["likely_signature_flow"] = likely_signature
    crypto_analysis["likely_encryption_flow"] = likely_encryption
    crypto_analysis["likely_timestamp_nonce_flow"] = likely_timestamp_nonce
    crypto_analysis["score"] = 80 if (likely_signature or likely_encryption) else 30

    item: dict[str, Any] = {
        "source": "inline",
        "url": url,
        "inline_id": "test-inline-1",
        "crypto_analysis": crypto_analysis,
    }
    if suspicious_functions is not None:
        item["suspicious_functions"] = suspicious_functions
    if suspicious_calls is not None:
        item["suspicious_calls"] = suspicious_calls
    return item


def _make_js_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": items}


def _make_api_candidate(
    url: str = "https://api.example.com/data",
    method: str = "GET",
    kind: str = "json",
    headers: dict[str, str] | None = None,
    body: str = "",
    status_code: int = 200,
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "url": url,
        "method": method,
        "kind": kind,
        "status_code": status_code,
    }
    if headers is not None:
        candidate["headers"] = headers
    if body:
        candidate["body"] = body
    return candidate


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestHookTargetExtraction(unittest.TestCase):
    """Hook targets from crypto signals and suspicious functions."""

    def test_sign_hmac_hook(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("hmac", "hmacSHA256"),
                _make_crypto_signal("signature", "sign"),
            ],
            categories=["hmac", "signature"],
            likely_signature=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.hook_targets)
        kinds = {h.kind for h in plan.hook_targets}
        self.assertIn("signature", kinds)
        names = {h.name for h in plan.hook_targets}
        self.assertIn("hmacSHA256", names)

    def test_encrypt_aes_hook_to_sandbox(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("encryption", "aes")],
            categories=["encryption"],
            likely_encryption=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        # AES goes to sandbox, not hook
        sandbox_names = {s.name for s in plan.sandbox_targets}
        self.assertIn("aes", sandbox_names)
        self.assertFalse(any(h.kind == "encryption" for h in plan.hook_targets))

    def test_token_hook(self) -> None:
        item = _make_js_item(
            suspicious_functions=[
                {"name": "generateToken", "kind": "arrow", "suspicious": True, "reason": "token"},
            ],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.hook_targets)
        token_hooks = [h for h in plan.hook_targets if h.kind == "token"]
        self.assertEqual(len(token_hooks), 1)
        self.assertEqual(token_hooks[0].name, "generateToken")

    def test_combined_sign_encrypt_token(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("hmac", "hmacSHA256"),
                _make_crypto_signal("encryption", "aes"),
                _make_crypto_signal("timestamp", "timestamp"),
                _make_crypto_signal("nonce", "nonce"),
            ],
            categories=["hmac", "encryption", "timestamp", "nonce"],
            likely_signature=True,
            likely_encryption=True,
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.hook_targets)
        self.assertTrue(plan.sandbox_targets)
        self.assertTrue(plan.dynamic_inputs)
        self.assertGreaterEqual(len(plan.replay_steps), 5)

    def test_clean_js_no_hooks(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("encoding", "base64", confidence="low")],
            categories=["encoding"],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        # base64 is an encoding hook, not signature/encryption
        self.assertEqual(plan.risk_level, "none")


class TestDynamicInputExtraction(unittest.TestCase):
    """Dynamic inputs from timestamp/nonce categories."""

    def test_timestamp_input(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("timestamp", "timestamp")],
            categories=["timestamp"],
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        names = {i.name for i in plan.dynamic_inputs}
        self.assertIn("timestamp", names)

    def test_nonce_input(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("nonce", "nonce")],
            categories=["nonce"],
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        names = {i.name for i in plan.dynamic_inputs}
        self.assertIn("nonce", names)

    def test_timestamp_and_nonce_combined(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("timestamp", "timestamp"),
                _make_crypto_signal("nonce", "nonce"),
            ],
            categories=["timestamp", "nonce"],
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        names = {i.name for i in plan.dynamic_inputs}
        self.assertIn("timestamp", names)
        self.assertIn("nonce", names)
        self.assertEqual(len(plan.dynamic_inputs), 2)

    def test_no_dynamic_inputs(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("hash", "sha256")],
            categories=["hash"],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertEqual(len(plan.dynamic_inputs), 0)


class TestSandboxTargetExtraction(unittest.TestCase):
    """Sandbox targets from encryption/webcrypto signals."""

    def test_webcrypto_sandbox(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("webcrypto", "subtle.sign")],
            categories=["webcrypto"],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.sandbox_targets)
        self.assertEqual(plan.sandbox_targets[0].runtime, "browser")
        self.assertEqual(plan.sandbox_targets[0].name, "subtle.sign")

    def test_aes_cryptojs_sandbox(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("encryption", "cryptojs")],
            categories=["encryption"],
            likely_encryption=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.sandbox_targets)
        self.assertIn(plan.sandbox_targets[0].runtime, ("browser", "browser_or_node"))

    def test_no_sandbox(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("hash", "sha256")],
            categories=["hash"],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertEqual(len(plan.sandbox_targets), 0)


class TestReplayStepGeneration(unittest.TestCase):
    """Replay steps ordering and dependencies."""

    def test_sign_flow_steps(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("hmac", "hmacSHA256"),
                _make_crypto_signal("timestamp", "timestamp"),
            ],
            categories=["hmac", "timestamp"],
            likely_signature=True,
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        actions = [s.action for s in plan.replay_steps]
        # Should have: generate_input, call_hook, build_request, send_request
        self.assertIn("generate_input", actions)
        self.assertIn("call_hook", actions)
        self.assertIn("build_request", actions)
        self.assertIn("send_request", actions)

    def test_encrypt_flow_steps(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("encryption", "aes")],
            categories=["encryption"],
            likely_encryption=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        actions = [s.action for s in plan.replay_steps]
        self.assertIn("call_sandbox", actions)

    def test_combined_ordering(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("timestamp", "timestamp"),
                _make_crypto_signal("nonce", "nonce"),
                _make_crypto_signal("hmac", "hmacSHA256"),
                _make_crypto_signal("encryption", "aes"),
            ],
            categories=["timestamp", "nonce", "hmac", "encryption"],
            likely_signature=True,
            likely_encryption=True,
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        # Steps should be ordered
        for i, step in enumerate(plan.replay_steps):
            self.assertEqual(step.order, i)
        # build_request should depend on all prior
        build_step = [s for s in plan.replay_steps if s.action == "build_request"]
        self.assertEqual(len(build_step), 1)
        self.assertTrue(build_step[0].depends_on)

    def test_step_ordering_monotonic(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("hmac", "hmac"),
                _make_crypto_signal("timestamp", "timestamp"),
                _make_crypto_signal("encryption", "aes"),
            ],
            categories=["hmac", "timestamp", "encryption"],
            likely_signature=True,
            likely_encryption=True,
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        orders = [s.order for s in plan.replay_steps]
        self.assertEqual(orders, sorted(orders))


class TestRiskLevelAndBlockers(unittest.TestCase):
    """Risk level and blocker computation."""

    def test_risk_none(self) -> None:
        plan = plan_hook_sandbox(_make_js_evidence([]))
        self.assertEqual(plan.risk_level, "none")
        self.assertEqual(len(plan.blockers), 0)

    def test_risk_low_dynamic_only(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("timestamp", "timestamp")],
            categories=["timestamp"],
            likely_timestamp_nonce=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertEqual(plan.risk_level, "low")
        self.assertTrue(any("dynamic_inputs" in b for b in plan.blockers))

    def test_risk_medium_signature(self) -> None:
        item = _make_js_item(
            crypto_signals=[_make_crypto_signal("hmac", "hmacSHA256")],
            categories=["hmac"],
            likely_signature=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertEqual(plan.risk_level, "medium")
        self.assertTrue(any("signature" in b for b in plan.blockers))

    def test_risk_high_signature_and_encryption(self) -> None:
        item = _make_js_item(
            crypto_signals=[
                _make_crypto_signal("hmac", "hmacSHA256"),
                _make_crypto_signal("encryption", "aes"),
            ],
            categories=["hmac", "encryption"],
            likely_signature=True,
            likely_encryption=True,
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertEqual(plan.risk_level, "high")


class TestPlanFromAPICandidates(unittest.TestCase):
    """Plans driven by API candidate evidence."""

    def test_signature_in_url(self) -> None:
        candidate = _make_api_candidate(
            url="https://api.example.com/data?x-sign=abc&timestamp=123",
        )
        plan = plan_hook_sandbox({}, [candidate])
        self.assertTrue(plan.hook_targets)
        self.assertTrue(plan.dynamic_inputs)

    def test_encrypted_body(self) -> None:
        candidate = _make_api_candidate(
            url="https://api.example.com/data",
            method="POST",
            body='{"encrypted": "AES_CIPHERTEXT"}',
        )
        plan = plan_hook_sandbox({}, [candidate])
        self.assertTrue(plan.sandbox_targets)

    def test_clean_api_candidate(self) -> None:
        candidate = _make_api_candidate(
            url="https://api.example.com/products?page=1",
        )
        plan = plan_hook_sandbox({}, [candidate])
        self.assertEqual(plan.risk_level, "none")


class TestStrategyEvidenceIntegration(unittest.TestCase):
    """Integration with strategy_evidence.build_reverse_engineering_hints."""

    def test_hook_sandbox_plan_in_hints(self) -> None:
        from autonomous_crawler.tools.strategy_evidence import build_strategy_evidence_report

        report = build_strategy_evidence_report({
            "js_evidence": _make_js_evidence([
                _make_js_item(
                    crypto_signals=[
                        _make_crypto_signal("hmac", "hmacSHA256"),
                        _make_crypto_signal("timestamp", "timestamp"),
                    ],
                    categories=["hmac", "timestamp"],
                    likely_signature=True,
                    likely_timestamp_nonce=True,
                ),
            ]),
        })
        hints = report.action_hints
        # Should have hook_sandbox_plan in addition to existing hook_plan
        self.assertIn("hook_sandbox_plan", hints)
        plan_dict = hints["hook_sandbox_plan"]
        self.assertIn("hook_targets", plan_dict)
        self.assertIn("replay_steps", plan_dict)
        self.assertIn("risk_level", plan_dict)

    def test_backward_compat_existing_hints(self) -> None:
        from autonomous_crawler.tools.strategy_evidence import build_strategy_evidence_report

        report = build_strategy_evidence_report({
            "js_evidence": _make_js_evidence([
                _make_js_item(
                    crypto_signals=[
                        _make_crypto_signal("hmac", "hmacSHA256"),
                    ],
                    categories=["hmac"],
                    likely_signature=True,
                ),
            ]),
        })
        hints = report.action_hints
        # Existing hook_plan should still be present
        self.assertIn("hook_plan", hints)
        # hook_sandbox_plan is additive
        self.assertIn("hook_sandbox_plan", hints)

    def test_no_plan_for_clean_evidence(self) -> None:
        from autonomous_crawler.tools.strategy_evidence import build_strategy_evidence_report

        report = build_strategy_evidence_report({
            "js_evidence": _make_js_evidence([
                _make_js_item(
                    crypto_signals=[],
                    categories=[],
                ),
            ]),
        })
        # No crypto → no hook_sandbox_plan
        self.assertNotIn("hook_sandbox_plan", report.action_hints)


class TestDeterministicFixtures(unittest.TestCase):
    """Each fixture produces a stable, reproducible plan."""

    def _plan_from_js_text(self, js_text: str) -> HookSandboxPlan:
        """Build plan from JS text using real crypto analysis."""
        from autonomous_crawler.tools.js_crypto_analysis import analyze_js_crypto
        from autonomous_crawler.tools.js_static_analysis import (
            extract_suspicious_calls,
            extract_functions,
        )

        crypto = analyze_js_crypto(js_text)
        functions = extract_functions(js_text)
        calls = extract_suspicious_calls(js_text)

        item: dict[str, Any] = {
            "source": "inline",
            "url": "https://test.example.com/bundle.js",
            "inline_id": "fixture-test",
            "crypto_analysis": crypto.to_dict(),
            "suspicious_functions": [
                {"name": f.name, "kind": f.kind, "suspicious": f.suspicious, "reason": f.suspicion_reason}
                for f in functions if f.suspicious
            ],
            "suspicious_calls": [
                {"call": c.call_expression, "keyword": c.matched_keyword, "category": c.category, "context": c.context}
                for c in calls
            ],
        }
        return plan_hook_sandbox(_make_js_evidence([item]))

    def test_sign_hmac_fixture_stable(self) -> None:
        plan = self._plan_from_js_text(_JS_SIGN_HMAC)
        self.assertIn(plan.risk_level, ("medium", "high"))
        self.assertTrue(plan.hook_targets or plan.dynamic_inputs)
        # Deterministic: run twice, same result
        plan2 = self._plan_from_js_text(_JS_SIGN_HMAC)
        self.assertEqual(plan.to_dict(), plan2.to_dict())

    def test_encrypt_aes_fixture_stable(self) -> None:
        plan = self._plan_from_js_text(_JS_ENCRYPT_AES)
        self.assertTrue(plan.sandbox_targets)
        plan2 = self._plan_from_js_text(_JS_ENCRYPT_AES)
        self.assertEqual(plan.to_dict(), plan2.to_dict())

    def test_webhook_token_fixture_stable(self) -> None:
        plan = self._plan_from_js_text(_JS_WEBHOOK_TOKEN)
        self.assertTrue(plan.hook_targets or plan.dynamic_inputs)
        plan2 = self._plan_from_js_text(_JS_WEBHOOK_TOKEN)
        self.assertEqual(plan.to_dict(), plan2.to_dict())

    def test_webhook_all_fixture_stable(self) -> None:
        plan = self._plan_from_js_text(_JS_WEBHOOK_ALL)
        self.assertEqual(plan.risk_level, "high")
        self.assertTrue(plan.hook_targets)
        self.assertTrue(plan.sandbox_targets)
        self.assertTrue(plan.dynamic_inputs)
        self.assertTrue(plan.blockers)
        plan2 = self._plan_from_js_text(_JS_WEBHOOK_ALL)
        self.assertEqual(plan.to_dict(), plan2.to_dict())

    def test_clean_fixture_no_risk(self) -> None:
        plan = self._plan_from_js_text(_JS_CLEAN)
        self.assertEqual(plan.risk_level, "none")
        self.assertEqual(len(plan.hook_targets), 0)
        self.assertEqual(len(plan.sandbox_targets), 0)
        plan2 = self._plan_from_js_text(_JS_CLEAN)
        self.assertEqual(plan.to_dict(), plan2.to_dict())


class TestPlanToDict(unittest.TestCase):
    """to_dict() serialization."""

    def test_empty_plan_to_dict(self) -> None:
        plan = HookSandboxPlan()
        d = plan.to_dict()
        self.assertEqual(d["risk_level"], "none")
        self.assertEqual(d["hook_targets"], [])
        self.assertEqual(d["sandbox_targets"], [])
        self.assertEqual(d["dynamic_inputs"], [])
        self.assertEqual(d["replay_steps"], [])
        self.assertEqual(d["blockers"], [])

    def test_full_plan_to_dict(self) -> None:
        plan = HookSandboxPlan(
            hook_targets=[HookTarget(name="sign", kind="signature", source="js_crypto")],
            sandbox_targets=[SandboxTarget(name="aes", runtime="browser")],
            dynamic_inputs=[DynamicInput(name="timestamp", generation_method="Date.now()")],
            replay_steps=[ReplayStep(order=0, action="generate_input", target="timestamp")],
            risk_level="high",
            blockers=["signature_flow", "encryption"],
        )
        d = plan.to_dict()
        self.assertEqual(len(d["hook_targets"]), 1)
        self.assertEqual(d["hook_targets"][0]["name"], "sign")
        self.assertEqual(len(d["sandbox_targets"]), 1)
        self.assertEqual(d["risk_level"], "high")
        self.assertEqual(len(d["blockers"]), 2)


class TestSuspiciousCallHooks(unittest.TestCase):
    """Hook targets from suspicious_calls in JS evidence."""

    def test_signature_call_hook(self) -> None:
        item = _make_js_item(
            suspicious_calls=[
                {"call": "signRequest", "keyword": "sign", "category": "signature", "context": "signRequest(url, params)"},
            ],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.hook_targets)
        self.assertEqual(plan.hook_targets[0].kind, "signature")
        self.assertEqual(plan.hook_targets[0].confidence, "high")

    def test_encryption_call_sandbox(self) -> None:
        item = _make_js_item(
            suspicious_calls=[
                {"call": "CryptoJS.AES.encrypt", "keyword": "CryptoJS", "category": "encryption", "context": "CryptoJS.AES.encrypt(data, key)"},
            ],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        self.assertTrue(plan.sandbox_targets)
        self.assertIn("browser", plan.sandbox_targets[0].runtime)

    def test_token_call_hook(self) -> None:
        item = _make_js_item(
            suspicious_calls=[
                {"call": "generateXBogus", "keyword": "xbogus", "category": "token", "context": "xbogus(params)"},
            ],
        )
        plan = plan_hook_sandbox(_make_js_evidence([item]))
        token_hooks = [h for h in plan.hook_targets if h.kind == "token"]
        self.assertEqual(len(token_hooks), 1)


if __name__ == "__main__":
    unittest.main()
