from __future__ import annotations

import time
import unittest

from autonomous_crawler.capabilities.license import (
    CapabilityGate,
    create_license_token,
    verify_license_token,
)


class CapabilityLicenseTests(unittest.TestCase):
    def test_community_capability_is_available_without_token(self) -> None:
        gate = CapabilityGate()

        status = gate.check("community.demo")

        self.assertTrue(status.available)
        self.assertEqual(status.edition, "community")

    def test_private_capability_degrades_without_token(self) -> None:
        gate = CapabilityGate()

        status = gate.check("private.advanced_api_replay")

        self.assertFalse(status.available)
        self.assertEqual(status.edition, "private")
        self.assertIn("no license token", status.reason)

    def test_signed_token_enables_matching_private_capability(self) -> None:
        secret = "owner-secret"
        token = create_license_token(
            {
                "subject": "owner",
                "capabilities": ["private.advanced_api_replay"],
                "expires_at": int(time.time()) + 3600,
            },
            secret,
        )
        gate = CapabilityGate(token=token, secret=secret)

        enabled = gate.check("private.advanced_api_replay")
        disabled = gate.check("private.site_profiles")

        self.assertTrue(enabled.available)
        self.assertFalse(disabled.available)
        self.assertEqual(disabled.reason, "not included in license")

    def test_wildcard_token_enables_all_private_capabilities(self) -> None:
        secret = "owner-secret"
        token = create_license_token({"subject": "owner", "capabilities": ["*"]}, secret)
        gate = CapabilityGate(token=token, secret=secret)

        self.assertTrue(gate.check("private.site_profiles").available)
        self.assertTrue(gate.check("enterprise.longrun_ops").available)

    def test_invalid_signature_is_rejected(self) -> None:
        token = create_license_token({"subject": "owner", "capabilities": ["*"]}, "right-secret")

        result = verify_license_token(token, "wrong-secret")

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "invalid token signature")

    def test_expired_token_is_rejected(self) -> None:
        token = create_license_token(
            {"subject": "owner", "capabilities": ["*"], "expires_at": 10},
            "owner-secret",
        )

        result = verify_license_token(token, "owner-secret", now=20)

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "license token expired")


if __name__ == "__main__":
    unittest.main()
