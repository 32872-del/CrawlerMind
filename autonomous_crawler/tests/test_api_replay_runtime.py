from __future__ import annotations

import json
import unittest

from autonomous_crawler.runners import SiteProfile
from autonomous_crawler.runners.profile_longrun import initial_requests_from_profile, next_api_requests
from autonomous_crawler.runtime import RuntimeResponse
from autonomous_crawler.tools.api_replay_runtime import (
    apply_api_replay_runtime,
    replay_plan_from_api_hints,
)


class ApiReplayRuntimeTests(unittest.TestCase):
    def test_signed_component_generates_executable_plan(self) -> None:
        plan = replay_plan_from_api_hints({
            "replay_diagnostics": {
                "signed_components": [
                    {"location": "header", "name": "x-signature", "kind": "signature_or_token"},
                ],
            },
        })

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.hook_targets[0].name, "api_request_signature")
        self.assertEqual(plan.hook_targets[0].kind, "signature")
        self.assertTrue(any(step.action == "call_hook" for step in plan.replay_steps))

    def test_replay_runtime_applies_signature_header_binding(self) -> None:
        result = apply_api_replay_runtime(
            api_hints={
                "replay_diagnostics": {
                    "risk_level": "medium",
                    "signed_components": [
                        {"location": "header", "name": "x-signature", "kind": "signature_or_token"},
                    ],
                },
                "replay_runtime": {"secret_key": "fixture-secret"},
            },
            url="https://shop.test/api/products?page=1",
            headers={"accept": "application/json"},
        )

        self.assertTrue(result.applied)
        self.assertIn("x-signature", result.headers)
        self.assertEqual(len(result.headers["x-signature"]), 64)
        self.assertEqual(result.bindings_applied[0]["location"], "header")

    def test_replay_runtime_applies_query_and_json_bindings(self) -> None:
        result = apply_api_replay_runtime(
            api_hints={
                "replay_diagnostics": {
                    "risk_level": "medium",
                    "signed_components": [
                        {"location": "query", "name": "sign", "kind": "signature_or_token"},
                        {"location": "json", "path": "variables.signature", "name": "signature", "kind": "signature_or_token"},
                    ],
                },
                "replay_runtime": {"secret_key": "fixture-secret"},
            },
            url="https://shop.test/graphql",
            headers={"content-type": "application/json"},
            json_body={"variables": {"page": 1}},
            method="POST",
        )

        self.assertTrue(result.applied)
        self.assertIn("sign=", result.url)
        self.assertEqual(len(result.json_body["variables"]["signature"]), 64)

    def test_explicit_hook_source_can_sign_profile_request(self) -> None:
        source = """
        function signShop(inputs) {
          var crypto = require('crypto');
          return crypto.createHash('sha256')
            .update(inputs.request_url + JSON.stringify(inputs.query_params))
            .digest('hex');
        }
        """
        result = apply_api_replay_runtime(
            api_hints={
                "replay_diagnostics": {
                    "signed_components": [
                        {"location": "header", "name": "x-signature", "kind": "signature_or_token"},
                    ],
                },
                "replay_runtime": {
                    "hook_name": "signShop",
                    "hook_sources": {"signShop": source},
                    "secret_key": "unused",
                },
            },
            url="https://shop.test/api/products?page=1",
            headers={},
        )

        self.assertTrue(result.applied)
        self.assertIn("x-signature", result.headers)
        self.assertEqual(len(result.headers["x-signature"]), 64)


class ProfileEcommerceReplayRuntimeTests(unittest.TestCase):
    def test_initial_profile_request_applies_replay_signature(self) -> None:
        profile = SiteProfile.from_dict({
            "name": "signed-shop",
            "api_hints": {
                "endpoint": "https://shop.test/api/products?ts=1&sign=old",
                "method": "GET",
                "kind": "api",
                "items_path": "items",
                "replay_diagnostics": {
                    "dynamic_inputs": [
                        {
                            "name": "ts",
                            "location": "query",
                            "path": "ts",
                            "generation_method": "unix_ms",
                            "refresh_each_request": True,
                        }
                    ],
                    "signed_components": [
                        {"location": "query", "name": "sign", "kind": "signature_or_token"},
                    ],
                },
                "replay_runtime": {"secret_key": "fixture-secret"},
            },
            "pagination_hints": {"type": "page", "page_param": "page", "start_page": 1},
            "crawl_preferences": {"include_seed_urls_with_api": False},
        })

        requests = initial_requests_from_profile(profile, run_id="signed-seed")

        self.assertEqual(len(requests), 1)
        self.assertIn("ts=", requests[0].url)
        self.assertIn("sign=", requests[0].url)
        self.assertNotIn("sign=old", requests[0].url)

    def test_next_profile_request_replays_signature_for_next_page(self) -> None:
        profile = SiteProfile.from_dict({
            "name": "signed-shop",
            "api_hints": {
                "endpoint": "https://shop.test/api/products?sign=old",
                "method": "GET",
                "kind": "api",
                "items_path": "items",
                "total_path": "total",
                "field_mapping": {"title": "name", "highest_price": "price"},
                "replay_diagnostics": {
                    "signed_components": [
                        {"location": "header", "name": "x-signature", "kind": "signature_or_token"},
                    ],
                },
                "replay_runtime": {"secret_key": "fixture-secret"},
            },
            "pagination_hints": {
                "type": "page",
                "page_param": "page",
                "start_page": 1,
                "page_size": 2,
            },
            "crawl_preferences": {"include_seed_urls_with_api": False},
        })
        seed = initial_requests_from_profile(profile, run_id="signed-next")[0]
        response = RuntimeResponse(
            ok=True,
            final_url=seed.url,
            status_code=200,
            text=json.dumps({
                "total": 4,
                "items": [
                    {"name": "Alpha", "price": 10},
                    {"name": "Beta", "price": 11},
                ],
            }),
        )

        next_requests = next_api_requests(profile, seed, response)

        self.assertEqual(len(next_requests), 1)
        self.assertIn("page=2", next_requests[0].url)
        self.assertIn("x-signature", next_requests[0].headers)
        self.assertEqual(len(next_requests[0].headers["x-signature"]), 64)


if __name__ == "__main__":
    unittest.main()
