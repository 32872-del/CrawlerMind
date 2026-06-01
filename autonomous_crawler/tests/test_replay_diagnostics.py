from __future__ import annotations

import unittest

from autonomous_crawler.tools.replay_diagnostics import (
    apply_replay_dynamic_inputs,
    build_replay_diagnostics,
)


class ReplayDiagnosticsTests(unittest.TestCase):
    def test_detects_query_timestamp_nonce_and_signature(self) -> None:
        result = build_replay_diagnostics(
            url="https://shop.test/api/products?timestamp=1710000000000&nonce=abc&sign=deadbeef",
            headers={"accept": "application/json"},
        ).to_dict()

        self.assertTrue(result["replay_required"])
        self.assertEqual(result["risk_level"], "medium")
        paths = {(item["location"], item["path"]) for item in result["dynamic_inputs"]}
        self.assertIn(("query", "timestamp"), paths)
        self.assertIn(("query", "nonce"), paths)
        self.assertEqual(result["signed_components"][0]["name"], "sign")
        self.assertIn("refresh_dynamic_inputs_before_each_api_request", result["recommendations"])

    def test_detects_session_headers_and_json_body_dynamic_inputs(self) -> None:
        result = build_replay_diagnostics(
            url="https://shop.test/graphql",
            method="POST",
            headers={
                "x-csrf-token": "csrf-value",
                "x-signature": "sig-value",
            },
            post_json={
                "variables": {
                    "currentPage": 1,
                    "timestamp": 1710000000000,
                    "requestId": "old",
                },
            },
        ).to_dict()

        self.assertTrue(result["replay_required"])
        self.assertEqual(result["risk_level"], "high")
        paths = {(item["location"], item["path"]) for item in result["dynamic_inputs"]}
        self.assertIn(("json", "variables.timestamp"), paths)
        self.assertIn(("json", "variables.requestId"), paths)
        session_names = {item["name"] for item in result["session_requirements"]}
        self.assertIn("x-csrf-token", session_names)
        signed_names = {item["name"] for item in result["signed_components"]}
        self.assertIn("x-signature", signed_names)

    def test_apply_dynamic_inputs_refreshes_url_headers_and_json(self) -> None:
        diagnostics = {
            "dynamic_inputs": [
                {"location": "query", "path": "timestamp", "generation_method": "unix_ms"},
                {"location": "header", "path": "x-request-id", "generation_method": "random_hex_16"},
                {"location": "json", "path": "variables.nonce", "generation_method": "uuid4"},
            ]
        }

        url, headers, body = apply_replay_dynamic_inputs(
            url="https://shop.test/api?timestamp=1",
            headers={"accept": "application/json"},
            json_body={"variables": {"nonce": "old"}},
            diagnostics=diagnostics,
        )

        self.assertRegex(url, r"timestamp=\d{13}")
        self.assertIn("x-request-id", headers)
        self.assertNotEqual(body["variables"]["nonce"], "old")
        self.assertRegex(body["variables"]["nonce"], r"^[0-9a-f-]{36}$")


if __name__ == "__main__":
    unittest.main()
