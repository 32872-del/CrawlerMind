"""Tests for replay_executor (REVERSE-HARDEN-2).

Covers success paths, missing functions, missing keys, dynamic inputs,
encryption stubs, and credential redaction.
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


if __name__ == "__main__":
    unittest.main()
