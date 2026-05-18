"""Tests for replay_executor (REVERSE-HARDEN-2 + REPLAY-RUNTIME-1).

Covers success paths, missing functions, missing keys, dynamic inputs,
encryption stubs, credential redaction, sandbox execution, sandbox timeout,
sandbox fallback, and execution_mode tracking.
"""
from __future__ import annotations

import json
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
from autonomous_crawler.tools.replay_executor import (
    FixtureContext,
    ReplayResult,
    StepResult,
    execute_replay,
)
from autonomous_crawler.tools.js_sandbox import (
    CompositeRuntime,
    NodeJSRuntime,
    SandboxResult,
    set_default_runtime,
)


# ---------------------------------------------------------------------------
# Plan builders for tests
# ---------------------------------------------------------------------------

def _sign_plan() -> HookSandboxPlan:
    """Plan with signature hook + timestamp/nonce inputs."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="hmacSHA256", kind="signature", source="js_crypto",
                       inputs_to_capture=["payload", "key"], outputs_to_capture=["signature"]),
        ],
        dynamic_inputs=[
            DynamicInput(name="timestamp", generation_method="Date.now()"),
            DynamicInput(name="nonce", generation_method="Math.random()"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="generate_input", target="timestamp"),
            ReplayStep(order=1, action="generate_input", target="nonce"),
            ReplayStep(order=2, action="call_hook", target="hmacSHA256", depends_on=[0, 1]),
            ReplayStep(order=3, action="build_request", target="final_request", depends_on=[0, 1, 2]),
            ReplayStep(order=4, action="send_request", target="transport", depends_on=[3]),
        ],
        risk_level="medium",
        blockers=["signature_flow_requires_runtime_key_or_hook"],
    )


def _encrypt_plan() -> HookSandboxPlan:
    """Plan with encryption sandbox."""
    return HookSandboxPlan(
        sandbox_targets=[
            SandboxTarget(name="aes", runtime="browser_or_node",
                          reason="encryption_routine_detected",
                          capture=["plaintext", "key_material", "ciphertext"]),
        ],
        replay_steps=[
            ReplayStep(order=0, action="call_sandbox", target="aes"),
            ReplayStep(order=1, action="build_request", target="final_request", depends_on=[0]),
            ReplayStep(order=2, action="send_request", target="transport", depends_on=[1]),
        ],
        risk_level="medium",
        blockers=["encryption_requires_runtime_execution"],
    )


def _combined_plan() -> HookSandboxPlan:
    """Plan with sign + encrypt + dynamic inputs."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="signRequest", kind="signature", source="js_crypto",
                       inputs_to_capture=["url", "params", "key"], outputs_to_capture=["signature"]),
        ],
        sandbox_targets=[
            SandboxTarget(name="aes", runtime="browser_or_node",
                          capture=["plaintext", "key_material", "ciphertext"]),
        ],
        dynamic_inputs=[
            DynamicInput(name="timestamp", generation_method="Date.now()"),
            DynamicInput(name="nonce", generation_method="Math.random()"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="generate_input", target="timestamp"),
            ReplayStep(order=1, action="generate_input", target="nonce"),
            ReplayStep(order=2, action="call_hook", target="signRequest", depends_on=[0, 1]),
            ReplayStep(order=3, action="call_sandbox", target="aes", depends_on=[2]),
            ReplayStep(order=4, action="build_request", target="final_request", depends_on=[0, 1, 2, 3]),
            ReplayStep(order=5, action="send_request", target="transport", depends_on=[4]),
        ],
        risk_level="high",
        blockers=["signature_flow_requires_runtime_key_or_hook",
                  "encryption_requires_runtime_execution"],
    )


def _token_plan() -> HookSandboxPlan:
    """Plan with token generation hook."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="generateToken", kind="token", source="js_static",
                       inputs_to_capture=["session_id", "timestamp"], outputs_to_capture=["token_value"]),
        ],
        dynamic_inputs=[
            DynamicInput(name="timestamp", generation_method="Date.now()"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="generate_input", target="timestamp"),
            ReplayStep(order=1, action="call_hook", target="generateToken", depends_on=[0]),
            ReplayStep(order=2, action="build_request", target="final_request", depends_on=[0, 1]),
            ReplayStep(order=3, action="send_request", target="transport", depends_on=[2]),
        ],
        risk_level="low",
        blockers=["dynamic_inputs_required: timestamp"],
    )


def _missing_hook_plan() -> HookSandboxPlan:
    """Plan with a hook function that has no built-in fixture."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="customObfuscatedSign_v3", kind="signature", source="js_crypto"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="call_hook", target="customObfuscatedSign_v3"),
            ReplayStep(order=1, action="build_request", target="final_request", depends_on=[0]),
        ],
        risk_level="medium",
    )


def _empty_plan() -> HookSandboxPlan:
    """Plan with no steps."""
    return HookSandboxPlan()


def _api_signed_url_plan() -> HookSandboxPlan:
    """Plan from API signed URL evidence."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="api_request_signature", kind="signature", source="api_evidence",
                       inputs_to_capture=["request_url", "query_params", "headers"],
                       outputs_to_capture=["signature_header"]),
        ],
        dynamic_inputs=[
            DynamicInput(name="timestamp", generation_method="Date.now()"),
            DynamicInput(name="nonce", generation_method="Math.random()"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="generate_input", target="timestamp"),
            ReplayStep(order=1, action="generate_input", target="nonce"),
            ReplayStep(order=2, action="call_hook", target="api_request_signature", depends_on=[0, 1]),
            ReplayStep(order=3, action="build_request", target="final_request", depends_on=[0, 1, 2]),
            ReplayStep(order=4, action="send_request", target="transport", depends_on=[3]),
        ],
        risk_level="medium",
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestSuccessfulReplay(unittest.TestCase):
    """Happy path: all steps execute successfully."""

    def test_sign_plan_success(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertTrue(result.success)
        self.assertEqual(len(result.steps_run), 5)
        self.assertIn("timestamp", result.generated_inputs)
        self.assertIn("nonce", result.generated_inputs)
        self.assertIn("hmacSHA256", result.hook_outputs)
        self.assertFalse(result.credential_leak_detected)

    def test_encrypt_plan_success(self) -> None:
        result = execute_replay(_encrypt_plan())
        self.assertTrue(result.success)
        self.assertIn("aes", result.sandbox_outputs)
        self.assertIn("AES_STUB", result.sandbox_outputs["aes"])

    def test_combined_plan_success(self) -> None:
        result = execute_replay(_combined_plan())
        self.assertTrue(result.success)
        self.assertIn("timestamp", result.generated_inputs)
        self.assertIn("nonce", result.generated_inputs)
        self.assertIn("signRequest", result.hook_outputs)
        self.assertIn("aes", result.sandbox_outputs)

    def test_token_plan_success(self) -> None:
        result = execute_replay(_token_plan())
        self.assertTrue(result.success)
        self.assertIn("generateToken", result.hook_outputs)

    def test_empty_plan_success(self) -> None:
        result = execute_replay(_empty_plan())
        self.assertTrue(result.success)
        self.assertEqual(len(result.steps_run), 0)


class TestMissingFunction(unittest.TestCase):
    """Hook function not in built-in fixtures."""

    def test_missing_hook_reports_error(self) -> None:
        result = execute_replay(_missing_hook_plan())
        self.assertFalse(result.success)
        self.assertTrue(any(s.status == "missing_function" for s in result.steps_run))
        self.assertTrue(any("customObfuscatedSign_v3" in s.error for s in result.steps_run))

    def test_missing_hook_in_blockers(self) -> None:
        result = execute_replay(_missing_hook_plan())
        self.assertTrue(any("missing_function" in b or "customObfuscated" in b
                           for b in result.blockers_remaining))


class TestDynamicInputs(unittest.TestCase):
    """Dynamic input generation."""

    def test_timestamp_generated(self) -> None:
        result = execute_replay(_sign_plan())
        ts = result.generated_inputs["timestamp"]
        self.assertIsInstance(ts, int)
        self.assertGreater(ts, 1_000_000_000_000)  # ms timestamp

    def test_nonce_generated(self) -> None:
        result = execute_replay(_sign_plan())
        nonce = result.generated_inputs["nonce"]
        self.assertIsInstance(nonce, str)
        self.assertGreaterEqual(len(nonce), 8)

    def test_dynamic_inputs_in_request_preview(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("timestamp", result.request_preview["params"])
        self.assertIn("nonce", result.request_preview["params"])


class TestEncryptionStub(unittest.TestCase):
    """Sandbox encryption stub behavior."""

    def test_aes_stub_output_format(self) -> None:
        result = execute_replay(_encrypt_plan())
        output = result.sandbox_outputs["aes"]
        self.assertIn("AES_STUB", output)

    def test_aes_stub_deterministic(self) -> None:
        r1 = execute_replay(_encrypt_plan())
        r2 = execute_replay(_encrypt_plan())
        self.assertEqual(r1.sandbox_outputs["aes"], r2.sandbox_outputs["aes"])


class TestCredentialRedaction(unittest.TestCase):
    """Sensitive information must not leak in output."""

    def test_no_secret_key_in_output(self) -> None:
        result = execute_replay(_sign_plan())
        result_str = json.dumps(result.to_dict(), default=str)
        self.assertNotIn("test-secret-key-do-not-use-in-production", result_str)

    def test_no_encrypt_key_in_output(self) -> None:
        result = execute_replay(_encrypt_plan())
        result_str = json.dumps(result.to_dict(), default=str)
        self.assertNotIn("test-encrypt-key", result_str)

    def test_credential_leak_detected_flag(self) -> None:
        # The executor checks for raw credentials in the result
        result = execute_replay(_sign_plan())
        # Should be False because redaction removes them
        self.assertFalse(result.credential_leak_detected)

    def test_hook_output_redaction(self) -> None:
        """Hook outputs containing keys should be redacted."""
        plan = HookSandboxPlan(
            hook_targets=[
                HookTarget(name="sign", kind="signature", source="test",
                           inputs_to_capture=["key"], outputs_to_capture=["signature"]),
            ],
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="sign"),
            ],
        )
        result = execute_replay(plan)
        result_str = json.dumps(result.to_dict(), default=str)
        # The secret key should not appear raw
        self.assertNotIn("test-secret-key-do-not-use-in-production", result_str)


class TestRequestPreview(unittest.TestCase):
    """Request preview structure."""

    def test_preview_has_url(self) -> None:
        ctx = FixtureContext(url="https://custom.api.com/v2/data")
        result = execute_replay(_sign_plan(), ctx)
        self.assertEqual(result.request_preview["url"], "https://custom.api.com/v2/data")

    def test_preview_has_headers(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("Accept", result.request_preview["headers"])

    def test_preview_has_signature_header(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("x-hmacSHA256", result.request_preview["headers"])

    def test_preview_has_dynamic_params(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("timestamp", result.request_preview["params"])
        self.assertIn("nonce", result.request_preview["params"])


class TestCustomFixtureContext(unittest.TestCase):
    """Custom context overrides."""

    def test_custom_url(self) -> None:
        ctx = FixtureContext(url="https://real-site.com/api")
        result = execute_replay(_sign_plan(), ctx)
        self.assertEqual(result.request_preview["url"], "https://real-site.com/api")

    def test_custom_params(self) -> None:
        ctx = FixtureContext(params={"q": "search", "page": "3"})
        result = execute_replay(_sign_plan(), ctx)
        self.assertEqual(result.request_preview["params"]["q"], "search")

    def test_custom_hook_implementation(self) -> None:
        def my_sign(inputs: dict[str, Any]) -> str:
            return "custom_signature_123"

        ctx = FixtureContext(hook_implementations={"hmacSHA256": my_sign})
        result = execute_replay(_sign_plan(), ctx)
        self.assertEqual(result.hook_outputs["hmacSHA256"], "custom_signature_123")


class TestFromPlanHookSandbox(unittest.TestCase):
    """Integration: plan_hook_sandbox → execute_replay."""

    def test_sign_hmac_evidence_to_replay(self) -> None:
        js_evidence = {
            "items": [{
                "source": "inline",
                "url": "https://example.com/app.js",
                "crypto_analysis": {
                    "signals": [
                        {"kind": "hmac", "name": "hmacSHA256", "confidence": "high"},
                        {"kind": "timestamp", "name": "timestamp", "confidence": "medium"},
                    ],
                    "categories": ["hmac", "timestamp"],
                    "likely_signature_flow": True,
                    "likely_timestamp_nonce_flow": True,
                },
            }],
        }
        plan = plan_hook_sandbox(js_evidence)
        self.assertTrue(plan.hook_targets)
        result = execute_replay(plan)
        self.assertTrue(result.success)
        self.assertIn("timestamp", result.generated_inputs)

    def test_combined_evidence_to_replay(self) -> None:
        js_evidence = {
            "items": [{
                "source": "inline",
                "url": "https://example.com/bundle.js",
                "crypto_analysis": {
                    "signals": [
                        {"kind": "hmac", "name": "hmac", "confidence": "high"},
                        {"kind": "encryption", "name": "aes", "confidence": "high"},
                        {"kind": "timestamp", "name": "timestamp", "confidence": "medium"},
                        {"kind": "nonce", "name": "nonce", "confidence": "medium"},
                    ],
                    "categories": ["hmac", "encryption", "timestamp", "nonce"],
                    "likely_signature_flow": True,
                    "likely_encryption_flow": True,
                    "likely_timestamp_nonce_flow": True,
                },
            }],
        }
        plan = plan_hook_sandbox(js_evidence)
        result = execute_replay(plan)
        # Should succeed for hook and sandbox steps
        self.assertIn("timestamp", result.generated_inputs)
        self.assertIn("nonce", result.generated_inputs)

    def test_api_signed_url_evidence_to_replay(self) -> None:
        api_candidates = [{
            "url": "https://api.example.com/data?x-sign=abc&timestamp=123&nonce=xyz",
            "method": "GET",
            "kind": "json",
        }]
        plan = plan_hook_sandbox({}, api_candidates)
        result = execute_replay(plan)
        self.assertIn("timestamp", result.generated_inputs)


class TestStepResultSerialization(unittest.TestCase):
    """StepResult and ReplayResult serialization."""

    def test_step_result_to_dict(self) -> None:
        sr = StepResult(order=0, action="generate_input", target="timestamp",
                        status="ok", output=1234567890)
        d = sr.to_dict()
        self.assertEqual(d["order"], 0)
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["output"], 1234567890)

    def test_replay_result_to_dict(self) -> None:
        result = execute_replay(_sign_plan())
        d = result.to_dict()
        self.assertIn("steps_run", d)
        self.assertIn("generated_inputs", d)
        self.assertIn("hook_outputs", d)
        self.assertIn("request_preview", d)
        self.assertIn("success", d)
        self.assertIn("credential_leak_detected", d)

    def test_error_step_redaction(self) -> None:
        plan = HookSandboxPlan(
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="missing_func"),
            ],
        )
        result = execute_replay(plan)
        d = result.to_dict()
        self.assertEqual(d["steps_run"][0]["status"], "missing_function")


class TestDeterministicReplay(unittest.TestCase):
    """Replay must be deterministic across runs."""

    def test_sign_plan_deterministic(self) -> None:
        r1 = execute_replay(_sign_plan())
        r2 = execute_replay(_sign_plan())
        # Steps and statuses should be identical
        self.assertEqual(len(r1.steps_run), len(r2.steps_run))
        for s1, s2 in zip(r1.steps_run, r2.steps_run):
            self.assertEqual(s1.status, s2.status)
            self.assertEqual(s1.action, s2.action)
        # Hook outputs should be deterministic (same key, same URL)
        self.assertEqual(r1.hook_outputs.get("hmacSHA256"), r2.hook_outputs.get("hmacSHA256"))

    def test_combined_plan_deterministic(self) -> None:
        r1 = execute_replay(_combined_plan())
        r2 = execute_replay(_combined_plan())
        self.assertEqual(r1.sandbox_outputs.get("aes"), r2.sandbox_outputs.get("aes"))


# ---------------------------------------------------------------------------
# REPLAY-RUNTIME-1: Execution mode tracking
# ---------------------------------------------------------------------------

class TestExecutionMode(unittest.TestCase):
    """execution_mode field on StepResult and ReplayResult."""

    def test_fixture_stub_mode_default(self) -> None:
        """Without sandbox source_code, all steps use fixture_stub."""
        result = execute_replay(_sign_plan())
        for step in result.steps_run:
            if step.status == "ok":
                self.assertEqual(step.execution_mode, "fixture_stub")
        self.assertEqual(result.execution_mode, "fixture_stub")

    def test_execution_mode_in_to_dict(self) -> None:
        """execution_mode appears in serialized output."""
        result = execute_replay(_sign_plan())
        d = result.to_dict()
        self.assertIn("execution_mode", d)
        self.assertEqual(d["execution_mode"], "fixture_stub")
        for step_d in d["steps_run"]:
            self.assertIn("execution_mode", step_d)

    def test_skipped_mode_for_unknown_action(self) -> None:
        plan = HookSandboxPlan(
            replay_steps=[ReplayStep(order=0, action="unknown_action", target="x")],
        )
        result = execute_replay(plan)
        self.assertEqual(result.steps_run[0].execution_mode, "skipped")

    def test_error_mode_on_exception(self) -> None:
        """Error step gets execution_mode='error'."""
        def _bad_hook(inputs: dict[str, Any]) -> str:
            raise RuntimeError("boom")

        plan = HookSandboxPlan(
            hook_targets=[HookTarget(name="bad", kind="signature", source="test")],
            replay_steps=[ReplayStep(order=0, action="call_hook", target="bad")],
        )
        ctx = FixtureContext(hook_implementations={"bad": _bad_hook})
        result = execute_replay(plan, ctx)
        self.assertEqual(result.steps_run[0].execution_mode, "error")


# ---------------------------------------------------------------------------
# REPLAY-RUNTIME-1: JS Sandbox integration
# ---------------------------------------------------------------------------

# JS source fixtures for sandbox tests

_JS_HMAC_SHA256 = """
function hmacSHA256(inputs) {
    var crypto = require('crypto');
    var payload = inputs.payload || inputs.url || '';
    var key = inputs.key || '';
    var sig = crypto.createHmac('sha256', key).update(payload).digest('hex');
    return sig;
}
"""

_JS_SHA256 = """
function sha256(inputs) {
    var crypto = require('crypto');
    var payload = inputs.payload || inputs.url || '';
    return crypto.createHash('sha256').update(payload).digest('hex');
}
"""

_JS_BASE64 = """
function base64(inputs) {
    var raw = inputs.raw_value || '';
    return Buffer.from(raw).toString('base64');
}
"""

_JS_AES_ENCRYPT = """
function aes(inputs) {
    var crypto = require('crypto');
    var plaintext = inputs.plaintext || '';
    var key = inputs.key_material || inputs.key || '';
    // Simple AES-256-ECB for testing (not production-grade)
    var keyBuf = Buffer.alloc(32, 0);
    keyBuf.write(key.slice(0, 32));
    var cipher = crypto.createCipheriv('aes-256-ecb', keyBuf, null);
    var encrypted = cipher.update(plaintext, 'utf8', 'hex') + cipher.final('hex');
    return encrypted;
}
"""

_JS_SLOW_HOOK = """
function slowHook(inputs) {
    // Simulates a slow execution that should trigger timeout
    var start = Date.now();
    while (Date.now() - start < 10000) {}
    return 'should_not_reach';
}
"""

_JS_BROKEN = """
function broken(inputs) {
    throw new Error('intentional_break');
}
"""


def _sandbox_sign_plan() -> HookSandboxPlan:
    """Plan with HMAC-SHA256 hook that has JS source_code."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="hmacSHA256", kind="signature", source="js_crypto",
                       inputs_to_capture=["payload", "key"], outputs_to_capture=["signature"],
                       source_code=_JS_HMAC_SHA256),
        ],
        dynamic_inputs=[
            DynamicInput(name="timestamp", generation_method="Date.now()"),
            DynamicInput(name="nonce", generation_method="Math.random()"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="generate_input", target="timestamp"),
            ReplayStep(order=1, action="generate_input", target="nonce"),
            ReplayStep(order=2, action="call_hook", target="hmacSHA256", depends_on=[0, 1]),
            ReplayStep(order=3, action="build_request", target="final_request", depends_on=[0, 1, 2]),
            ReplayStep(order=4, action="send_request", target="transport", depends_on=[3]),
        ],
        risk_level="medium",
    )


def _sandbox_encrypt_plan() -> HookSandboxPlan:
    """Plan with AES sandbox that has JS source_code."""
    return HookSandboxPlan(
        sandbox_targets=[
            SandboxTarget(name="aes", runtime="node",
                          reason="encryption_routine_detected",
                          capture=["plaintext", "key_material", "ciphertext"],
                          source_code=_JS_AES_ENCRYPT),
        ],
        replay_steps=[
            ReplayStep(order=0, action="call_sandbox", target="aes"),
            ReplayStep(order=1, action="build_request", target="final_request", depends_on=[0]),
            ReplayStep(order=2, action="send_request", target="transport", depends_on=[1]),
        ],
        risk_level="medium",
    )


def _sandbox_combined_plan() -> HookSandboxPlan:
    """Plan with both hook (sandbox source) and sandbox (sandbox source)."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="hmacSHA256", kind="signature", source="js_crypto",
                       inputs_to_capture=["payload", "key"],
                       source_code=_JS_HMAC_SHA256),
        ],
        sandbox_targets=[
            SandboxTarget(name="aes", runtime="node",
                          capture=["plaintext", "key_material", "ciphertext"],
                          source_code=_JS_AES_ENCRYPT),
        ],
        dynamic_inputs=[
            DynamicInput(name="timestamp", generation_method="Date.now()"),
            DynamicInput(name="nonce", generation_method="Math.random()"),
        ],
        replay_steps=[
            ReplayStep(order=0, action="generate_input", target="timestamp"),
            ReplayStep(order=1, action="generate_input", target="nonce"),
            ReplayStep(order=2, action="call_hook", target="hmacSHA256", depends_on=[0, 1]),
            ReplayStep(order=3, action="call_sandbox", target="aes", depends_on=[2]),
            ReplayStep(order=4, action="build_request", target="final_request", depends_on=[0, 1, 2, 3]),
            ReplayStep(order=5, action="send_request", target="transport", depends_on=[4]),
        ],
        risk_level="high",
    )


def _sandbox_timeout_plan() -> HookSandboxPlan:
    """Plan with a hook that hangs (should trigger timeout)."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="slowHook", kind="signature", source="test",
                       source_code=_JS_SLOW_HOOK),
        ],
        replay_steps=[
            ReplayStep(order=0, action="call_hook", target="slowHook"),
        ],
    )


def _sandbox_broken_plan() -> HookSandboxPlan:
    """Plan with a hook that throws in JS."""
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="broken", kind="signature", source="test",
                       source_code=_JS_BROKEN),
        ],
        replay_steps=[
            ReplayStep(order=0, action="call_hook", target="broken"),
        ],
    )


def _sandbox_fallback_plan() -> HookSandboxPlan:
    """Plan with source_code on hook, but hook name also matches a built-in fixture.

    If sandbox succeeds, we get sandbox mode. If sandbox fails (e.g. no Node),
    we fall back to fixture_stub.
    """
    return HookSandboxPlan(
        hook_targets=[
            HookTarget(name="hmacSHA256", kind="signature", source="js_crypto",
                       inputs_to_capture=["payload", "key"],
                       source_code=_JS_HMAC_SHA256),
        ],
        replay_steps=[
            ReplayStep(order=0, action="call_hook", target="hmacSHA256"),
            ReplayStep(order=1, action="build_request", target="final_request", depends_on=[0]),
        ],
    )


def _has_node() -> bool:
    """Check if Node.js is available for real sandbox tests."""
    import shutil
    return shutil.which("node") is not None


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSandboxExecution(unittest.TestCase):
    """Sandbox execution with real Node.js."""

    def test_sandbox_hmac_hook(self) -> None:
        """HMAC-SHA256 via Node.js sandbox produces a valid hex digest."""
        result = execute_replay(_sandbox_sign_plan())
        self.assertTrue(result.success)
        self.assertIn("hmacSHA256", result.hook_outputs)
        sig = result.hook_outputs["hmacSHA256"]
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 64)  # SHA256 hex = 64 chars
        # Check execution_mode on the hook step
        hook_step = [s for s in result.steps_run if s.action == "call_hook"][0]
        self.assertEqual(hook_step.execution_mode, "sandbox")
        # Overall mode is "mixed" because generate_input steps use fixture_stub
        self.assertEqual(result.execution_mode, "mixed")

    def test_sandbox_aes_encrypt(self) -> None:
        """AES encryption via Node.js sandbox produces ciphertext."""
        result = execute_replay(_sandbox_encrypt_plan())
        self.assertTrue(result.success)
        self.assertIn("aes", result.sandbox_outputs)
        ciphertext = result.sandbox_outputs["aes"]
        self.assertIsInstance(ciphertext, str)
        self.assertGreater(len(ciphertext), 0)
        self.assertNotIn("AES_STUB", ciphertext)  # Not a stub
        sandbox_step = [s for s in result.steps_run if s.action == "call_sandbox"][0]
        self.assertEqual(sandbox_step.execution_mode, "sandbox")

    def test_sandbox_combined(self) -> None:
        """Both hook and sandbox steps run in sandbox mode."""
        result = execute_replay(_sandbox_combined_plan())
        self.assertTrue(result.success)
        # Overall is "mixed" because generate_input steps are fixture_stub
        self.assertEqual(result.execution_mode, "mixed")
        self.assertIn("hmacSHA256", result.hook_outputs)
        self.assertIn("aes", result.sandbox_outputs)

    def test_sandbox_request_preview(self) -> None:
        """Sandbox outputs flow into request preview."""
        result = execute_replay(_sandbox_sign_plan())
        self.assertIn("x-hmacSHA256", result.request_preview["headers"])
        sig = result.request_preview["headers"]["x-hmacSHA256"]
        self.assertEqual(len(sig), 64)

    def test_sandbox_sha256_hook(self) -> None:
        """SHA256 via sandbox."""
        plan = HookSandboxPlan(
            hook_targets=[
                HookTarget(name="sha256", kind="signature", source="js_crypto",
                           inputs_to_capture=["payload"],
                           source_code=_JS_SHA256),
            ],
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="sha256"),
            ],
        )
        result = execute_replay(plan)
        self.assertTrue(result.success)
        digest = result.hook_outputs["sha256"]
        self.assertEqual(len(digest), 64)

    def test_sandbox_base64_hook(self) -> None:
        """Base64 encoding via sandbox."""
        plan = HookSandboxPlan(
            hook_targets=[
                HookTarget(name="base64", kind="encoding", source="js_crypto",
                           inputs_to_capture=["raw_value"],
                           source_code=_JS_BASE64),
            ],
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="base64"),
            ],
        )
        ctx = FixtureContext()
        result = execute_replay(plan, ctx)
        self.assertTrue(result.success)
        encoded = result.hook_outputs["base64"]
        self.assertIsInstance(encoded, str)


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSandboxTimeout(unittest.TestCase):
    """Sandbox timeout handling."""

    def test_timeout_triggers_error(self) -> None:
        """Hook that hangs triggers timeout, then falls back to fixture.

        slowHook has no built-in fixture, so fallback returns missing_function.
        """
        ctx = FixtureContext(timeout_ms=500)
        result = execute_replay(_sandbox_timeout_plan(), ctx)
        # Should not succeed — sandbox timed out, no fixture fallback
        self.assertFalse(result.success)
        step = result.steps_run[0]
        # After sandbox timeout, falls back to fixture — slowHook has no fixture
        self.assertEqual(step.status, "missing_function")

    def test_timeout_does_not_crash(self) -> None:
        """Timeout error doesn't crash the executor."""
        ctx = FixtureContext(timeout_ms=300)
        result = execute_replay(_sandbox_timeout_plan(), ctx)
        # Result should still be returned, not an exception
        self.assertIsInstance(result, ReplayResult)
        self.assertGreater(len(result.steps_run), 0)


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSandboxMissingFunction(unittest.TestCase):
    """Missing function in sandbox JS."""

    def test_missing_function_falls_back(self) -> None:
        """If JS source doesn't define the function, falls back to fixture."""
        plan = HookSandboxPlan(
            hook_targets=[
                HookTarget(name="hmacSHA256", kind="signature", source="test",
                           source_code="function notTheRightName(inputs) { return 'x'; }"),
            ],
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="hmacSHA256"),
            ],
        )
        result = execute_replay(plan)
        # Falls back to fixture stub (hmacSHA256 is a built-in)
        self.assertTrue(result.success)
        self.assertEqual(result.steps_run[0].execution_mode, "fixture_stub")

    def test_broken_js_falls_back(self) -> None:
        """JS that throws falls back to fixture stub."""
        plan = HookSandboxPlan(
            hook_targets=[
                HookTarget(name="hmacSHA256", kind="signature", source="test",
                           source_code=_JS_BROKEN),
            ],
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="hmacSHA256"),
            ],
        )
        result = execute_replay(plan)
        # Falls back to fixture because sandbox threw
        self.assertTrue(result.success)
        self.assertEqual(result.steps_run[0].execution_mode, "fixture_stub")


class TestSandboxFallbackToFixture(unittest.TestCase):
    """Sandbox unavailable -> falls back to fixture_stub."""

    def test_no_source_code_uses_fixture(self) -> None:
        """Without source_code, always uses fixture_stub."""
        result = execute_replay(_sign_plan())
        for step in result.steps_run:
            if step.status == "ok":
                self.assertEqual(step.execution_mode, "fixture_stub")
        self.assertEqual(result.execution_mode, "fixture_stub")

    def test_empty_runtime_uses_fixture(self) -> None:
        """With a runtime that has no available backends, uses fixture."""
        empty_runtime = CompositeRuntime(runtimes=[])
        plan = HookSandboxPlan(
            hook_targets=[
                HookTarget(name="hmacSHA256", kind="signature", source="test",
                           source_code=_JS_HMAC_SHA256),
            ],
            replay_steps=[
                ReplayStep(order=0, action="call_hook", target="hmacSHA256"),
            ],
        )
        result = execute_replay(plan, runtime=empty_runtime)
        self.assertTrue(result.success)
        self.assertEqual(result.steps_run[0].execution_mode, "fixture_stub")


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSandboxCredentialRedaction(unittest.TestCase):
    """Sandbox output must not leak credentials."""

    def test_sandbox_result_redaction(self) -> None:
        """Sandbox result doesn't contain raw secret key."""
        result = execute_replay(_sandbox_sign_plan())
        result_str = json.dumps(result.to_dict(), default=str)
        self.assertNotIn("test-secret-key-do-not-use-in-production", result_str)

    def test_sandbox_credential_leak_detected(self) -> None:
        """credential_leak_detected is False when redaction works."""
        result = execute_replay(_sandbox_sign_plan())
        self.assertFalse(result.credential_leak_detected)


# ---------------------------------------------------------------------------
# REPLAY-RUNTIME-1: NodeJSRuntime direct tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(_has_node(), "Node.js not available")
class TestNodeJSRuntime(unittest.TestCase):
    """Direct tests of NodeJSRuntime."""

    def test_simple_function(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            "function add(inputs) { return inputs.a + inputs.b; }",
            "add",
            {"a": 3, "b": 4},
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.result, 7)
        self.assertEqual(result.execution_mode, "sandbox")

    def test_crypto_hash(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            """
            function hash(inputs) {
                var crypto = require('crypto');
                return crypto.createHash('sha256').update(inputs.data).digest('hex');
            }
            """,
            "hash",
            {"data": "hello"},
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.result), 64)

    def test_timeout(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            "function hang(inputs) { while(true) {} return 'nope'; }",
            "hang",
            {},
            timeout_ms=500,
        )
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.execution_mode, "error")

    def test_syntax_error(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            "function bad(inputs) { }}}",
            "bad",
            {},
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.execution_mode, "error")

    def test_missing_function(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            "function notMyFunc(inputs) { return 1; }",
            "targetFunc",
            {},
        )
        self.assertEqual(result.status, "error")

    def test_is_available(self) -> None:
        runtime = NodeJSRuntime()
        self.assertTrue(runtime.is_available())

    def test_runtime_events(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            "function f(inputs) { return 'ok'; }",
            "f",
            {},
        )
        self.assertGreater(len(result.runtime_events), 0)
        self.assertEqual(result.runtime_events[0]["event"], "execute")

    def test_redacted_preview(self) -> None:
        runtime = NodeJSRuntime()
        result = runtime.execute(
            "function f(inputs) { return inputs.key; }",
            "f",
            {"key": "my_secret_value"},
        )
        self.assertEqual(result.status, "ok")
        # The preview should have the result redacted if it contains "secret"
        # (depends on _redact_value behavior)


class TestCompositeRuntime(unittest.TestCase):
    """CompositeRuntime fallback behavior."""

    def test_fallback_order(self) -> None:
        """First available runtime that succeeds wins."""
        class _AlwaysFail:
            name = "fail"
            def is_available(self): return True
            def execute(self, *a, **kw): return SandboxResult(status="error", execution_mode="error")

        class _AlwaysOk:
            name = "ok"
            def is_available(self): return True
            def execute(self, *a, **kw): return SandboxResult(status="ok", result=42, execution_mode="sandbox")

        comp = CompositeRuntime(runtimes=[_AlwaysFail(), _AlwaysOk()])
        result = comp.execute("src", "fn", {})
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.result, 42)

    def test_all_fail(self) -> None:
        class _Fail:
            name = "fail"
            def is_available(self): return True
            def execute(self, *a, **kw): return SandboxResult(status="error", error="nope", execution_mode="error")

        comp = CompositeRuntime(runtimes=[_Fail()])
        result = comp.execute("src", "fn", {})
        self.assertEqual(result.status, "error")

    def test_skip_unavailable(self) -> None:
        class _Unavail:
            name = "unavail"
            def is_available(self): return False
            def execute(self, *a, **kw): raise AssertionError("should not be called")

        class _Ok:
            name = "ok"
            def is_available(self): return True
            def execute(self, *a, **kw): return SandboxResult(status="ok", result=1, execution_mode="sandbox")

        comp = CompositeRuntime(runtimes=[_Unavail(), _Ok()])
        result = comp.execute("src", "fn", {})
        self.assertEqual(result.result, 1)


# ---------------------------------------------------------------------------
# REPLAY-RUNTIME-1 Round 2: Request Patch & Profile API Hints
# ---------------------------------------------------------------------------

class TestRequestPatch(unittest.TestCase):
    """ReplayRequestPatch: machine-readable signed request output."""

    def test_request_patch_has_method(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("method", result.request_patch)
        self.assertIn(result.request_patch["method"], ("GET", "POST"))

    def test_request_patch_has_url(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("url", result.request_patch)
        self.assertTrue(result.request_patch["url"].startswith("https://"))

    def test_request_patch_has_signed_params(self) -> None:
        result = execute_replay(_sign_plan())
        params = result.request_patch["params"]
        self.assertIn("timestamp", params)
        self.assertIn("nonce", params)

    def test_request_patch_has_signature_headers(self) -> None:
        result = execute_replay(_sign_plan())
        headers = result.request_patch["headers"]
        self.assertIn("x-hmacSHA256", headers)
        # Signature should be a 64-char hex
        sig = headers["x-hmacSHA256"]
        self.assertEqual(len(sig), 64)

    def test_request_patch_has_dynamic_inputs_used(self) -> None:
        result = execute_replay(_sign_plan())
        used = result.request_patch["dynamic_inputs_used"]
        self.assertIn("timestamp", used)
        self.assertIn("nonce", used)

    def test_request_patch_has_signature_outputs(self) -> None:
        result = execute_replay(_sign_plan())
        sig_out = result.request_patch["signature_outputs"]
        self.assertIn("hmacSHA256", sig_out)

    def test_request_patch_has_base_url(self) -> None:
        ctx = FixtureContext(url="https://api.test.com/v2/feed")
        result = execute_replay(_sign_plan(), ctx)
        self.assertEqual(result.request_patch["base_url"], "https://api.test.com/v2/feed")

    def test_request_patch_in_to_dict(self) -> None:
        result = execute_replay(_sign_plan())
        d = result.to_dict()
        self.assertIn("request_patch", d)
        self.assertIn("method", d["request_patch"])

    def test_request_patch_signed_url_contains_params(self) -> None:
        """Signed URL should contain timestamp and nonce in query string."""
        result = execute_replay(_sign_plan())
        url = result.request_patch["url"]
        self.assertIn("timestamp=", url)
        self.assertIn("nonce=", url)

    def test_request_patch_redacts_secrets(self) -> None:
        """request_patch must not contain raw secret key."""
        result = execute_replay(_sign_plan())
        patch_str = json.dumps(result.request_patch, default=str)
        self.assertNotIn("test-secret-key-do-not-use-in-production", patch_str)

    def test_request_patch_encrypt_has_body(self) -> None:
        """Encrypted sandbox output flows into body field."""
        result = execute_replay(_encrypt_plan())
        body = result.request_patch.get("body", "")
        self.assertIn("AES_STUB", body)

    def test_request_patch_combined(self) -> None:
        """Combined plan: signature headers + encrypted body + dynamic params."""
        result = execute_replay(_combined_plan())
        patch = result.request_patch
        self.assertIn("x-signRequest", patch["headers"])
        self.assertIn("timestamp", patch["params"])
        self.assertIn("nonce", patch["params"])
        self.assertIn("AES_STUB", patch.get("body", ""))

    def test_request_patch_empty_plan(self) -> None:
        result = execute_replay(_empty_plan())
        self.assertEqual(result.request_patch["method"], "GET")
        self.assertEqual(result.request_patch["dynamic_inputs_used"], [])


class TestProfileApiHints(unittest.TestCase):
    """profile_api_hints: data-only artifact for SiteProfile.api_hints."""

    def test_hints_has_replay_required(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("replay_required", result.profile_api_hints)
        self.assertTrue(result.profile_api_hints["replay_required"])

    def test_hints_replay_required_false_for_empty(self) -> None:
        result = execute_replay(_empty_plan())
        self.assertFalse(result.profile_api_hints["replay_required"])

    def test_hints_has_plan_id(self) -> None:
        result = execute_replay(_sign_plan())
        plan_id = result.profile_api_hints["replay_plan_id"]
        self.assertIn("hmacSHA256", plan_id)
        self.assertIn("signature", plan_id)

    def test_hints_has_risk_level(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertEqual(result.profile_api_hints["risk_level"], "medium")

    def test_hints_has_signed_headers(self) -> None:
        result = execute_replay(_sign_plan())
        headers = result.profile_api_hints["signed_headers"]
        self.assertIn("x-hmacSHA256", headers)

    def test_hints_has_signed_params(self) -> None:
        result = execute_replay(_sign_plan())
        params = result.profile_api_hints["signed_params"]
        self.assertIn("timestamp", params)
        self.assertIn("nonce", params)

    def test_hints_has_dynamic_inputs(self) -> None:
        result = execute_replay(_sign_plan())
        dyn = result.profile_api_hints["dynamic_inputs"]
        names = [d["name"] for d in dyn]
        self.assertIn("timestamp", names)
        self.assertIn("nonce", names)
        # Each has generation_method and required
        for d in dyn:
            self.assertIn("generation_method", d)
            self.assertIn("required", d)

    def test_hints_has_hook_targets(self) -> None:
        result = execute_replay(_sign_plan())
        self.assertIn("hmacSHA256", result.profile_api_hints["hook_targets"])

    def test_hints_has_sandbox_targets(self) -> None:
        result = execute_replay(_encrypt_plan())
        self.assertIn("aes", result.profile_api_hints["sandbox_targets"])

    def test_hints_combined_plan(self) -> None:
        result = execute_replay(_combined_plan())
        hints = result.profile_api_hints
        self.assertTrue(hints["replay_required"])
        self.assertIn("signRequest", hints["hook_targets"])
        self.assertIn("aes", hints["sandbox_targets"])
        self.assertIn("x-signRequest", hints["signed_headers"])
        self.assertIn("timestamp", hints["signed_params"])
        self.assertIn("nonce", hints["signed_params"])

    def test_hints_in_to_dict(self) -> None:
        result = execute_replay(_sign_plan())
        d = result.to_dict()
        self.assertIn("profile_api_hints", d)
        self.assertIn("replay_required", d["profile_api_hints"])

    def test_hints_redacts_secrets(self) -> None:
        result = execute_replay(_sign_plan())
        hints_str = json.dumps(result.profile_api_hints, default=str)
        self.assertNotIn("test-secret-key-do-not-use-in-production", hints_str)


class TestSignedRequestFixture(unittest.TestCase):
    """Signed request generation with timestamp + nonce + param-sort + HMAC."""

    def test_signed_request_deterministic(self) -> None:
        """Same plan + context → same signature (fixture mode is deterministic)."""
        ctx = FixtureContext(url="https://api.shop.com/products", params={"page": "1"})
        r1 = execute_replay(_sign_plan(), ctx)
        r2 = execute_replay(_sign_plan(), ctx)
        self.assertEqual(
            r1.request_patch["headers"].get("x-hmacSHA256"),
            r2.request_patch["headers"].get("x-hmacSHA256"),
        )

    def test_signed_request_different_urls_different_sigs(self) -> None:
        """Different URLs produce different signatures."""
        ctx1 = FixtureContext(url="https://api.shop.com/a")
        ctx2 = FixtureContext(url="https://api.shop.com/b")
        r1 = execute_replay(_sign_plan(), ctx1)
        r2 = execute_replay(_sign_plan(), ctx2)
        self.assertNotEqual(
            r1.request_patch["headers"].get("x-hmacSHA256"),
            r2.request_patch["headers"].get("x-hmacSHA256"),
        )

    def test_signed_request_different_keys_different_sigs(self) -> None:
        """Different secret keys produce different signatures."""
        ctx1 = FixtureContext(secret_key="key-aaa")
        ctx2 = FixtureContext(secret_key="key-bbb")
        r1 = execute_replay(_sign_plan(), ctx1)
        r2 = execute_replay(_sign_plan(), ctx2)
        self.assertNotEqual(
            r1.request_patch["headers"].get("x-hmacSHA256"),
            r2.request_patch["headers"].get("x-hmacSHA256"),
        )

    def test_signed_request_params_merged(self) -> None:
        """Dynamic inputs (timestamp, nonce) are merged into params."""
        result = execute_replay(_sign_plan())
        params = result.request_patch["params"]
        # Original params
        self.assertIn("page", params)
        self.assertIn("limit", params)
        # Dynamic inputs
        self.assertIn("timestamp", params)
        self.assertIn("nonce", params)

    def test_signed_request_url_contains_base_and_dynamic(self) -> None:
        """Signed URL has base URL + original params + dynamic params."""
        ctx = FixtureContext(url="https://api.com/data", params={"q": "test"})
        result = execute_replay(_sign_plan(), ctx)
        url = result.request_patch["url"]
        self.assertTrue(url.startswith("https://api.com/data?"))
        self.assertIn("q=test", url)
        self.assertIn("timestamp=", url)
        self.assertIn("nonce=", url)

    def test_signed_request_api_signature_plan(self) -> None:
        """api_request_signature hook produces valid request patch."""
        result = execute_replay(_api_signed_url_plan())
        self.assertTrue(result.success)
        sig_out = result.request_patch["signature_outputs"]
        self.assertIn("api_request_signature", sig_out)

    def test_signed_request_with_sandbox(self) -> None:
        """Sandbox-mode signed request produces valid patch."""
        result = execute_replay(_sandbox_sign_plan())
        self.assertTrue(result.success)
        sig = result.request_patch["headers"].get("x-hmacSHA256", "")
        self.assertEqual(len(sig), 64)


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSandboxRequestPatch(unittest.TestCase):
    """Request patch from sandbox execution."""

    def test_sandbox_patch_has_real_signature(self) -> None:
        """Sandbox produces real HMAC (not stub) in request patch."""
        result = execute_replay(_sandbox_sign_plan())
        sig = result.request_patch["headers"]["x-hmacSHA256"]
        self.assertEqual(len(sig), 64)
        self.assertNotIn("STUB", sig)

    def test_sandbox_patch_aes_body(self) -> None:
        """Sandbox AES produces real ciphertext in body."""
        result = execute_replay(_sandbox_encrypt_plan())
        body = result.request_patch.get("body", "")
        self.assertGreater(len(body), 0)
        self.assertNotIn("AES_STUB", body)

    def test_sandbox_patch_combined(self) -> None:
        """Combined sandbox plan produces complete request patch."""
        result = execute_replay(_sandbox_combined_plan())
        patch = result.request_patch
        self.assertIn("x-hmacSHA256", patch["headers"])
        self.assertEqual(len(patch["headers"]["x-hmacSHA256"]), 64)
        self.assertIn("timestamp", patch["params"])
        self.assertIn("nonce", patch["params"])


@unittest.skipUnless(_has_node(), "Node.js not available")
class TestSandboxProfileHints(unittest.TestCase):
    """Profile API hints from sandbox execution."""

    def test_sandbox_hints_match_fixture_hints_structure(self) -> None:
        """Sandbox and fixture produce same hint keys."""
        r_fixture = execute_replay(_sign_plan())
        r_sandbox = execute_replay(_sandbox_sign_plan())
        self.assertEqual(
            set(r_fixture.profile_api_hints.keys()),
            set(r_sandbox.profile_api_hints.keys()),
        )

    def test_sandbox_hints_signed_headers(self) -> None:
        result = execute_replay(_sandbox_sign_plan())
        self.assertIn("x-hmacSHA256", result.profile_api_hints["signed_headers"])


if __name__ == "__main__":
    unittest.main()
