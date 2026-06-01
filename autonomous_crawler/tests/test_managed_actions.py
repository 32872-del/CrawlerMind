from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.runners.managed_actions import (
    ManagedActionPlan,
    build_deterministic_action_plan,
    execute_managed_action_plan,
)
from autonomous_crawler.runners.profile_longrun import initial_requests_from_profile, next_api_requests
from autonomous_crawler.runners.site_profile import SiteProfile
from autonomous_crawler.runtime import RuntimeResponse


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "dev_logs"
    / "training"
    / "xiaomi_recon_2026_05_28"
    / "fixtures"
)


def _read_fixture_text(*parts: str) -> str:
    return FIXTURE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def _read_fixture_json(*parts: str):
    return json.loads(_read_fixture_text(*parts))


class ManagedActionPlanTests(unittest.TestCase):
    def test_llm_protocol_accepts_canonical_aliases_and_records_validation(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "schema_version": "managed-action-plan/v2",
            "reasoning_summary": "repair runtime and export results",
            "actions": [
                {"action": "analyze_site", "priority": "high", "params": {"target_url": "https://shop.test"}},
                {"action": "switch_runtime", "priority": "high", "params": {"mode": "protected", "wait_until": "networkidle"}},
                {"action": "export_results", "priority": "low", "params": {"format": "csv", "output_path": "out.csv"}},
            ],
        })

        self.assertEqual(plan.to_dict()["protocol_validation"]["schema_version"], "managed-action-plan/v2")
        self.assertEqual([item.action for item in plan.actions], ["reanalyze_site", "adjust_runtime", "prepare_export"])
        self.assertEqual(plan.actions[1].params["mode"], "protected")
        self.assertEqual(plan.actions[2].params["format"], "csv")
        self.assertEqual(plan.actions[0].reason, "")

    def test_llm_protocol_rejects_unsafe_action_and_bounded_profile_patch(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {"action": "run_shell", "priority": "high", "params": {"cmd": "rm -rf /"}},
                {
                    "action": "patch_profile",
                    "params": {
                        "profile_patch": {
                            "selectors": {
                                "detail": {
                                    "title": {"selector_type": "xpath", "selector": "string(//h1)"},
                                    "script": "<script>alert(1)</script>",
                                }
                            },
                            "access_config": {"mode": "protected", "browser_config": {"capture_api": True}},
                            "unexpected": {"value": "ignored"},
                        }
                    },
                },
            ],
        })

        validation = plan.to_dict()["protocol_validation"]
        self.assertEqual(validation["accepted_count"], 1)
        self.assertEqual(validation["rejected_count"], 1)
        self.assertEqual(plan.actions[0].action, "patch_profile")
        self.assertIn("selectors", plan.actions[0].params["profile_patch"])
        self.assertNotIn("unexpected", plan.actions[0].params["profile_patch"])
        self.assertNotIn("script", plan.actions[0].params["profile_patch"]["selectors"]["detail"])

    def test_protocol_validation_keeps_multi_action_plan_trace(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "reasoning_summary": "three-step repair loop",
            "actions": [
                {"action": "select_catalog", "priority": "high", "params": {"target_url": "https://shop.test/cat"}},
                {"action": "resolve_fields", "priority": "high", "params": {"fields": ["title", "highest_price"]}},
                {"action": "rerun_failed", "priority": "medium", "params": {"run_kind": "test"}},
            ],
        })

        validation = plan.to_dict()["protocol_validation"]
        self.assertEqual(validation["accepted_count"], 3)
        self.assertFalse(validation["fallback_used"])
        self.assertEqual([item["action"] for item in validation["accepted"]], ["discover_catalog", "probe_fields", "prepare_rerun"])
        self.assertEqual(validation["accepted"][1]["param_keys"], ["fields"])

    def test_deterministic_plan_adds_repair_actions_for_zero_records(self) -> None:
        plan = build_deterministic_action_plan(
            target_url="https://shop.test",
            profile={"name": "shop", "target_fields": ["title"]},
            run_spec={"selected_fields": ["title"]},
            progress={"records_saved": 0, "quality_indicator": "fail"},
            supervision={"last_event": {"action": "pause", "reason": "no records"}},
        )

        actions = [item.action for item in plan.actions]
        self.assertIn("reanalyze_site", actions)
        self.assertIn("discover_catalog", actions)
        self.assertIn("inspect_access", actions)
        self.assertIn("repair_selectors", actions)
        self.assertIn("adjust_runtime", actions)
        self.assertIn("evaluate_quality", actions)
        self.assertEqual(actions[-1], "prepare_rerun")

    def test_challenge_failures_upgrade_to_protected_runtime(self) -> None:
        plan = build_deterministic_action_plan(
            target_url="https://shop.test",
            profile={"name": "shop", "target_fields": ["title"], "crawl_preferences": {"seed_urls": ["https://shop.test/c"]}},
            run_spec={"selected_fields": ["title"]},
            progress={
                "records_saved": 0,
                "quality_indicator": "fail",
                "failed": 10,
                "failure_buckets": {"challenge_like": 10},
            },
            supervision={"last_event": {"action": "pause", "reason": "captcha challenge detected"}},
        )

        runtime_actions = [item for item in plan.actions if item.action == "adjust_runtime"]
        self.assertTrue(runtime_actions)
        self.assertEqual(runtime_actions[0].params["mode"], "protected")
        self.assertTrue(runtime_actions[0].params["persistent_context"])
        self.assertEqual(runtime_actions[0].params["item_workers"], 1)

    def test_deterministic_plan_uses_available_extraction_contract(self) -> None:
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")
        plan = build_deterministic_action_plan(
            target_url="https://www.superdry.com/womens/tops",
            profile={
                "name": "superdry",
                "target_fields": ["title"],
                "crawl_preferences": {"seed_urls": ["https://www.superdry.com/womens/tops"]},
            },
            run_spec={"selected_fields": ["title"]},
            progress={"records_saved": 0, "quality_indicator": "fail"},
            extra_context={
                "extraction_contract": contract,
                "extraction_evidence": html,
                "source_url": "https://www.superdry.com/womens/tops",
                "max_items": 3,
            },
        )

        self.assertEqual(plan.actions[0].action, "extract_from_contract")
        self.assertEqual(plan.actions[0].params["contract"]["site"], "superdry.com")
        self.assertEqual(plan.actions[0].params["source_url"], "https://www.superdry.com/womens/tops")

    def test_deterministic_plan_auto_discovers_contract_from_evidence(self) -> None:
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")
        plan = build_deterministic_action_plan(
            target_url="https://www.superdry.com/womens/tops",
            profile={
                "name": "superdry",
                "target_fields": ["title"],
                "crawl_preferences": {"seed_urls": ["https://www.superdry.com/womens/tops"]},
            },
            run_spec={"selected_fields": ["title"]},
            progress={"records_saved": 0, "quality_indicator": "fail"},
            extra_context={
                "extraction_evidence": html,
                "source_url": "https://www.superdry.com/womens/tops",
                "max_items": 3,
            },
        )

        self.assertEqual(plan.actions[0].action, "extract_from_contract")
        self.assertEqual(plan.actions[0].params["contract"]["parser_strategy"]["name"], "gtm_data_attribute_extractor")

    def test_execute_plan_produces_profile_patch_and_overrides(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {"action": "probe_fields", "params": {"fields": ["title", "colors", "sizes"]}},
                {"action": "inspect_access", "priority": "high"},
                {"action": "repair_selectors", "params": {"fields": ["title", "highest_price"]}},
                {"action": "adjust_runtime", "params": {"mode": "dynamic", "capture_api": True}},
                {"action": "evaluate_quality", "params": {"required_fields": ["title", "colors"], "min_records": 25}},
                {"action": "prepare_export", "params": {"format": "csv", "output_path": "out.xlsx"}},
            ]
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile={"name": "shop", "selectors": {}, "target_fields": ["title"]},
            run_spec={"selected_fields": ["title"]},
        )

        self.assertTrue(result["rerun_ready"])
        self.assertEqual(result["profile_patch"]["access_config"]["mode"], "dynamic")
        self.assertTrue(result["profile_patch"]["access_config"]["browser_config"]["capture_api"])
        self.assertIn("title", result["profile_patch"]["selectors"]["detail"])
        self.assertIn("highest_price", result["profile_patch"]["selectors"]["detail"])
        self.assertIn("colors", result["profile_patch"]["selectors"]["detail"])
        self.assertEqual(result["profile_patch"]["quality_expectations"]["min_records"], 25)
        self.assertEqual(result["run_overrides"]["export"]["format"], "csv")
        self.assertEqual(result["run_overrides"]["export"]["output_path"], "out.xlsx")
        self.assertEqual(result["evidence"]["schema_version"], "managed-action-evidence/v1")
        self.assertEqual(result["evidence"]["access"]["target_url"], "https://shop.test")
        self.assertEqual(result["evidence"]["access"]["request"]["target_url"], "https://shop.test")

    def test_inspect_access_carries_runtime_snapshot_from_job(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [{"action": "inspect_access", "priority": "high"}],
        })
        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile={
                "name": "shop",
                "access_config": {"mode": "static"},
                "crawl_preferences": {"seed_urls": ["https://shop.test/list"]},
            },
            run_spec={"selected_fields": ["title"]},
            job={
                "status": "completed",
                "target_url": "https://shop.test",
                "product_run_spec": {"target_url": "https://shop.test", "selected_fields": ["title"]},
                "profile_run": {
                    "runner_summary": {
                        "claimed": 1,
                        "failed": 1,
                        "records_saved": 0,
                        "failure_buckets": {"challenge_like": 1},
                        "runtime_events": [
                            {"type": "browser_failure", "url": "https://shop.test/p", "classification": "challenge_like"}
                        ],
                    },
                    "failures": [
                        {"url": "https://shop.test/p", "bucket": "challenge_like", "error": "recaptcha challenge"}
                    ],
                },
            },
        )

        snapshot = result["evidence"]["access_snapshot"]
        self.assertTrue(snapshot["summary"]["challenge_like"])
        self.assertEqual(snapshot["summary"]["recommended_runtime"], "protected_browser")
        self.assertEqual(snapshot["runtime_events"][0]["bucket"], "challenge_like")
        self.assertEqual(snapshot["recent_failures"][0]["bucket"], "challenge_like")

    @patch("autonomous_crawler.runners.managed_actions.build_recon_report")
    @patch("autonomous_crawler.runners.managed_actions.NativeBrowserRuntime")
    def test_inspect_access_live_probe_collects_access_snapshot(
        self,
        mock_runtime_cls: MagicMock,
        mock_recon_report: MagicMock,
    ) -> None:
        mock_runtime = MagicMock()
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.final_url = "https://shop.test/list"
        mock_response.status_code = 200
        mock_response.error = ""
        mock_response.html = "<html><body><div class='product-card'>Alpha</div></body></html>"
        mock_response.to_dict.return_value = {
            "runtime_events": [
                {"type": "browser_render_complete", "message": "native browser render completed"},
            ],
            "captured_xhr": [
                {
                    "url": "https://shop.test/api/products",
                    "method": "GET",
                    "status_code": 200,
                    "content_type": "application/json",
                    "body_preview": "{\"items\":[{\"title\":\"Alpha\"}]}",
                },
            ],
            "artifacts": [
                {"kind": "screenshot", "path": "shot.png", "url": "https://shop.test/list"},
            ],
            "engine_result": {
                "failure_classification": {"category": "none"},
            },
        }
        mock_runtime.render.return_value = mock_response
        mock_runtime_cls.return_value = mock_runtime
        mock_recon_report.return_value = {
            "frontend_framework": "react",
            "rendering": "spa",
            "anti_bot": {"detected": False},
            "dom_structure": {"item_count": 3, "field_selectors": {}, "product_selector": ".product-card"},
        }

        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "inspect_access",
                    "priority": "high",
                    "params": {"live_probe": True, "sample_limit": 2},
                }
            ],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test/list",
            profile={
                "name": "shop",
                "access_config": {"mode": "dynamic"},
                "crawl_preferences": {"seed_urls": ["https://shop.test/list"]},
            },
            run_spec={"selected_fields": ["title"]},
            extra_context={"live_probe": True},
        )

        snapshot = result["evidence"]["access_snapshot"]
        self.assertEqual(snapshot["schema_version"], "access-probe/v1")
        self.assertEqual(snapshot["summary"]["captured_xhr"], 1)
        self.assertEqual(snapshot["summary"]["framework"], "react")
        self.assertEqual(snapshot["xhr_samples"][0]["url"], "https://shop.test/api/products")
        promotion = result["profile_patch"]["api_hints"]
        self.assertEqual(promotion["endpoint"], "https://shop.test/api/products")
        self.assertEqual(promotion["items_path"], "items")
        self.assertEqual(promotion["field_mapping"]["title"], "title")
        self.assertEqual(result["profile_patch"]["crawl_preferences"]["seed_kind"], "api")
        self.assertEqual(result["api_replay_promotion"]["promoted"], True)
        self.assertEqual(snapshot["artifact_samples"][0]["kind"], "screenshot")
        mock_runtime.render.assert_called_once()
        mock_recon_report.assert_called_once()

    def test_inspect_access_promotes_job_xhr_snapshot_to_api_replay_patch(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [{"action": "inspect_access", "priority": "high"}],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test/list",
            profile={
                "name": "shop",
                "target_fields": ["title", "highest_price"],
                "access_config": {"mode": "dynamic"},
                "crawl_preferences": {"seed_urls": ["https://shop.test/list"], "seed_kind": "list"},
            },
            run_spec={"selected_fields": ["title", "highest_price"]},
            job={
                "status": "completed",
                "target_url": "https://shop.test/list",
                "latest_access_probe": {
                    "snapshot": {
                        "schema_version": "access-probe/v1",
                        "xhr_samples": [
                            {
                                "url": "https://shop.test/api/catalog?page=1&limit=20",
                                "method": "GET",
                                "status": 200,
                                "content_type": "application/json",
                                "preview": "{\"data\":{\"items\":[{\"name\":\"Alpha\",\"price\":10.5,\"image\":\"/a.jpg\"}]}}",
                            }
                        ],
                    }
                },
            },
        )

        self.assertTrue(result["api_replay_promotion"]["promoted"])
        self.assertEqual(result["profile_patch"]["api_hints"]["endpoint"], "https://shop.test/api/catalog")
        self.assertEqual(result["profile_patch"]["api_hints"]["items_path"], "data.items")
        self.assertEqual(result["profile_patch"]["api_hints"]["field_mapping"]["title"], "name")
        self.assertEqual(result["profile_patch"]["pagination_hints"]["type"], "page")
        self.assertEqual(result["profile_patch"]["pagination_hints"]["page_param"], "page")
        self.assertEqual(result["profile_patch"]["pagination_hints"]["page_size"], 20)
        profile = SiteProfile.from_dict({
            "name": "shop",
            **result["profile_patch"],
        })
        requests = initial_requests_from_profile(profile, run_id="api-rerun")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].kind, "api")
        self.assertEqual(requests[0].url, "https://shop.test/api/catalog?page=1&limit=20")

    def test_inspect_access_promotes_post_graphql_xhr_to_replayable_profile(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [{"action": "inspect_access", "priority": "high"}],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test/category",
            profile={
                "name": "shop",
                "target_fields": ["title", "highest_price"],
                "access_config": {"mode": "dynamic"},
                "crawl_preferences": {"seed_urls": ["https://shop.test/category"], "seed_kind": "list"},
            },
            run_spec={"selected_fields": ["title", "highest_price"]},
            job={
                "status": "completed",
                "target_url": "https://shop.test/category",
                "latest_access_probe": {
                    "snapshot": {
                        "schema_version": "access-probe/v1",
                        "xhr_samples": [
                            {
                                "url": "https://shop.test/graphql",
                                "method": "POST",
                                "status": 200,
                                "content_type": "application/json",
                                "request_headers": {
                                    "content-type": "application/json",
                                    "x-store": "nl",
                                    "authorization": "Bearer secret",
                                },
                                "post_data_preview": (
                                    '{"operationName":"CategoryProducts","query":"query CategoryProducts { products { items { name price image } total_count page_info { current_page page_size } } }",'
                                    '"variables":{"currentPage":1,"pageSize":24,"categoryId":"42"}}'
                                ),
                                "preview": (
                                    '{"data":{"products":{"total_count":96,"items":[{"name":"Alpha","price":10.5,"image":"/a.jpg"}]}}}'
                                ),
                            }
                        ],
                    }
                },
            },
        )

        self.assertTrue(result["api_replay_promotion"]["promoted"])
        api_hints = result["profile_patch"]["api_hints"]
        pagination = result["profile_patch"]["pagination_hints"]
        self.assertEqual(api_hints["endpoint"], "https://shop.test/graphql")
        self.assertEqual(api_hints["method"], "POST")
        self.assertEqual(api_hints["format"], "graphql")
        self.assertEqual(api_hints["kind"], "graphql")
        self.assertEqual(api_hints["items_path"], "data.products.items")
        self.assertEqual(api_hints["field_mapping"]["title"], "name")
        self.assertEqual(api_hints["headers"]["content-type"], "application/json")
        self.assertEqual(api_hints["headers"]["x-store"], "nl")
        self.assertNotIn("authorization", api_hints["headers"])
        self.assertEqual(api_hints["post_json"]["variables"]["currentPage"], 1)
        self.assertTrue(api_hints["replay_diagnostics"]["replay_required"])
        self.assertEqual(api_hints["replay_diagnostics"]["risk_level"], "medium")
        session_names = {item["name"] for item in api_hints["replay_diagnostics"]["session_requirements"]}
        self.assertIn("x-store", session_names)
        self.assertEqual(pagination["type"], "page")
        self.assertEqual(pagination["json_page_path"], "variables.currentPage")
        self.assertEqual(pagination["json_page_size_path"], "variables.pageSize")
        self.assertEqual(pagination["page_size"], 24)

        profile = SiteProfile.from_dict({
            "name": "shop",
            **result["profile_patch"],
        })
        requests = initial_requests_from_profile(profile, run_id="graphql-rerun")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url, "https://shop.test/graphql")
        self.assertEqual(requests[0].method, "POST")
        self.assertEqual(requests[0].headers["content-type"], "application/json")
        self.assertEqual(requests[0].headers["x-store"], "nl")
        self.assertEqual(requests[0].json["variables"]["currentPage"], 1)

        response = RuntimeResponse(
            ok=True,
            final_url=requests[0].url,
            status_code=200,
            text='{"data":{"products":{"total_count":96,"items":[{"name":"Alpha","price":10.5}]}}}',
        )
        next_requests = next_api_requests(profile, requests[0], response)
        self.assertEqual(len(next_requests), 1)
        self.assertEqual(next_requests[0].url, "https://shop.test/graphql")
        self.assertEqual(next_requests[0].json["variables"]["currentPage"], 2)
        self.assertEqual(next_requests[0].json["variables"]["pageSize"], 24)

    def test_profile_api_requests_refresh_replay_dynamic_inputs(self) -> None:
        profile = SiteProfile.from_dict({
            "name": "shop",
            "api_hints": {
                "endpoint": "https://shop.test/api/products?timestamp=1",
                "method": "POST",
                "format": "json",
                "kind": "api",
                "items_path": "items",
                "post_json": {
                    "page": 1,
                    "nonce": "old",
                },
                "replay_diagnostics": {
                    "schema_version": "replay-diagnostics/v1",
                    "replay_required": True,
                    "dynamic_inputs": [
                        {
                            "name": "timestamp",
                            "location": "query",
                            "path": "timestamp",
                            "generation_method": "unix_ms",
                            "refresh_each_request": True,
                            "required": True,
                        },
                        {
                            "name": "nonce",
                            "location": "json",
                            "path": "nonce",
                            "generation_method": "random_hex_16",
                            "refresh_each_request": True,
                            "required": True,
                        },
                    ],
                },
            },
            "pagination_hints": {"type": "page", "json_page_path": "page", "start_page": 1},
            "crawl_preferences": {"seed_kind": "api", "include_seed_urls_with_api": False},
        })

        requests = initial_requests_from_profile(profile, run_id="refresh-rerun")

        self.assertEqual(len(requests), 1)
        self.assertRegex(requests[0].url, r"timestamp=\d{13}")
        self.assertEqual(requests[0].json["page"], 1)
        self.assertNotEqual(requests[0].json["nonce"], "old")

    def test_protected_runtime_patch_preserves_persistent_context_knobs(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "adjust_runtime",
                    "params": {
                        "mode": "protected",
                        "capture_api": True,
                        "persistent_context": True,
                        "rotate_proxy": True,
                        "item_workers": 1,
                    },
                },
            ]
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile={"name": "shop"},
            run_spec={"selected_fields": ["title"]},
        )

        browser = result["profile_patch"]["access_config"]["browser_config"]
        self.assertEqual(result["profile_patch"]["access_config"]["mode"], "protected")
        self.assertTrue(browser["persistent_context"])
        self.assertFalse(browser["close_persistent_context"])
        self.assertTrue(browser["pool_enabled"])
        self.assertEqual(result["run_overrides"]["item_workers"], 1)
        self.assertEqual(result["run_overrides"]["proxy_policy"]["strategy"], "rotate_on_challenge")

    def test_unknown_action_is_bounded_to_prepare_rerun(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [{"action": "run_arbitrary_python", "priority": "critical"}],
        })

        self.assertEqual(plan.actions[0].action, "prepare_rerun")
        self.assertTrue(plan.to_dict()["protocol_validation"]["fallback_used"])

    def test_protocol_accepts_extract_from_contract_action(self) -> None:
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "priority": "high",
                    "params": {
                        "contract": contract,
                        "evidence": html,
                        "source_url": "https://www.superdry.com/womens/tops",
                        "max_items": 3,
                    },
                }
            ],
        })

        validation = plan.to_dict()["protocol_validation"]
        self.assertEqual(validation["accepted_count"], 1)
        self.assertEqual(plan.actions[0].action, "extract_from_contract")
        self.assertEqual(plan.actions[0].params["source_url"], "https://www.superdry.com/womens/tops")
        self.assertEqual(plan.actions[0].params["max_items"], 3)
        self.assertEqual(plan.actions[0].params["contract"]["site"], "superdry.com")

    def test_execute_extract_from_contract_uses_real_superdry_fixture(self) -> None:
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {
                        "contract": contract,
                        "evidence": html,
                        "source_url": "https://www.superdry.com/womens/tops",
                    },
                }
            ],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://www.superdry.com/womens/tops",
            profile={"name": "superdry"},
            run_spec={"selected_fields": ["title", "highest_price", "color"]},
        )

        action_result = result["results"][0]
        extraction = result["run_overrides"]["extraction_result"]
        self.assertTrue(action_result["ok"])
        self.assertTrue(result["rerun_ready"])
        self.assertEqual(extraction["schema_version"], "contract-extraction-result/v1")
        self.assertEqual(extraction["site"], "superdry.com")
        self.assertEqual(extraction["parser_strategy"], "gtm_data_attribute_extractor")
        self.assertEqual(extraction["item_count"], 3)
        self.assertEqual(extraction["items"][0]["title"], "Athletic Essentials Stripe Jersey Polo Shirt")
        self.assertEqual(extraction["items"][0]["highest_price"], 29.99)
        self.assertIn("color", extraction["fields_found"])
        self.assertEqual(result["evidence"]["schema_version"], "managed-action-evidence/v1")
        self.assertEqual(result["evidence"]["access"]["contract_site"], "superdry.com")
        self.assertEqual(result["evidence"]["access"]["item_count"], 3)
        self.assertEqual(result["evidence"]["items"][-1]["contract_site"], "superdry.com")

    def test_extract_from_contract_reports_unknown_strategy(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {
                        "contract": {"site": "example.com", "parser_strategy": {"name": "unknown_strategy"}},
                        "evidence": {"items": []},
                    },
                }
            ],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://example.com",
            profile={"name": "example"},
            run_spec={},
        )

        self.assertFalse(result["results"][0]["ok"])
        self.assertIn("unsupported parser_strategy.name", result["results"][0]["error"])
        self.assertFalse(result["rerun_ready"])

    def test_extract_from_contract_requires_evidence(self) -> None:
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {"contract": contract},
                }
            ],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://www.superdry.com/womens/tops",
            profile={"name": "superdry"},
            run_spec={},
        )

        self.assertFalse(result["results"][0]["ok"])
        self.assertEqual(result["results"][0]["error"], "missing extraction evidence")
        self.assertFalse(result["rerun_ready"])

    def test_execute_extract_from_contract_auto_discovers_contract_from_extra_context(self) -> None:
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {"max_items": 3},
                }
            ],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://www.superdry.com/womens/tops",
            profile={"name": "superdry"},
            run_spec={"selected_fields": ["title", "highest_price"]},
            extra_context={
                "extraction_evidence": html,
                "source_url": "https://www.superdry.com/womens/tops",
            },
        )

        extraction = result["run_overrides"]["extraction_result"]
        action_evidence = result["results"][0]["evidence"]
        self.assertTrue(result["results"][0]["ok"])
        self.assertEqual(extraction["item_count"], 3)
        self.assertEqual(extraction["parser_strategy"], "gtm_data_attribute_extractor")
        self.assertEqual(action_evidence["contract_discovery"]["best_sample_count"], 3)

    # ------------------------------------------------------------------
    # End-to-end: AI managed loop integration for extract_from_contract
    # ------------------------------------------------------------------

    def test_fake_advisor_extract_from_contract_accepted_and_executed(self) -> None:
        """Simulate LLM outputting extract_from_contract via action plan.

        A fake advisor returns an action plan containing extract_from_contract
        with the Superdry fixture contract + evidence. The plan must be
        accepted, executed, and produce 3 extracted items.
        """
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")

        fake_plan_payload = {
            "schema_version": "managed-action-plan/v2",
            "reasoning_summary": "Site uses GTM data-gtm attributes; extract products from listing page evidence.",
            "actions": [
                {
                    "action": "extract_from_contract",
                    "priority": "high",
                    "reason": "GTM data-gtm contract available with matching HTML evidence.",
                    "params": {
                        "contract": contract,
                        "evidence": html,
                        "source_url": "https://www.superdry.com/womens/tops",
                        "max_items": 5,
                    },
                },
            ],
        }

        # Parse through ManagedActionPlan.from_dict (same path as LLM output)
        plan = ManagedActionPlan.from_dict(fake_plan_payload, source="llm")
        validation = plan.to_dict()["protocol_validation"]

        self.assertEqual(validation["accepted_count"], 1)
        self.assertEqual(validation["rejected_count"], 0)
        self.assertEqual(plan.actions[0].action, "extract_from_contract")
        self.assertEqual(plan.source, "llm")

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://www.superdry.com/womens/tops",
            profile={"name": "superdry", "target_fields": ["title", "highest_price"]},
            run_spec={"selected_fields": ["title", "highest_price"]},
        )

        action_result = result["results"][0]
        extraction = result["run_overrides"]["extraction_result"]
        self.assertTrue(action_result["ok"])
        self.assertEqual(extraction["item_count"], 3)
        self.assertEqual(extraction["items"][0]["title"], "Athletic Essentials Stripe Jersey Polo Shirt")
        self.assertEqual(extraction["items"][0]["highest_price"], 29.99)
        self.assertIn("title", extraction["fields_found"])
        self.assertIn("highest_price", extraction["fields_found"])
        self.assertTrue(result["rerun_ready"])

    def test_extraction_result_flows_into_managed_state(self) -> None:
        """Extraction result must be visible in the managed action record.

        Simulates the path through _execute_managed_actions_for_job where the
        result is appended to job["managed_actions"]. Verifies the extraction
        result is accessible and carries the expected schema + items.
        """
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        html = _read_fixture_text("superdry_com", "raw_evidence_list_page.html")

        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {
                        "contract": contract,
                        "evidence": html,
                        "source_url": "https://www.superdry.com/womens/tops",
                    },
                },
            ],
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://www.superdry.com/womens/tops",
            profile={"name": "superdry"},
            run_spec={"selected_fields": ["title", "highest_price", "color"]},
        )

        # Simulate what _execute_managed_actions_for_job does: wrap in a record
        from datetime import datetime, timezone
        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "executed": True,
            "result": result,
        }
        managed_actions = [record]

        # Verify extraction result is accessible from the managed action record
        latest = managed_actions[-1]
        self.assertTrue(latest["executed"])
        extraction = latest["result"]["run_overrides"]["extraction_result"]
        self.assertEqual(extraction["schema_version"], "contract-extraction-result/v1")
        self.assertEqual(extraction["site"], "superdry.com")
        self.assertEqual(extraction["parser_strategy"], "gtm_data_attribute_extractor")
        self.assertEqual(extraction["item_count"], 3)

        # Verify evidence is also in the record
        evidence = latest["result"]["evidence"]
        self.assertEqual(evidence["schema_version"], "managed-action-evidence/v1")
        self.assertEqual(evidence["access"]["contract_site"], "superdry.com")
        self.assertEqual(evidence["access"]["item_count"], 3)

    def test_extract_from_contract_rejects_non_dict_contract(self) -> None:
        """Contract must be a dict; non-dict values produce validation error."""
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {
                        "contract": "not a dict",
                        "evidence": "<html></html>",
                    },
                }
            ],
        })

        # contract="not a dict" should cause a validation error → action rejected
        validation = plan.to_dict()["protocol_validation"]
        self.assertEqual(validation["accepted_count"], 0)
        self.assertEqual(validation["rejected_count"], 1)
        self.assertIn("contract must be an object", validation["rejected"][0]["errors"])

    def test_extract_from_contract_rejects_invalid_evidence_type(self) -> None:
        """Evidence must be string, dict, or list; int is rejected."""
        contract = _read_fixture_json("superdry_com", "extraction_contract.json")
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {
                        "contract": contract,
                        "evidence": 12345,
                    },
                }
            ],
        })

        validation = plan.to_dict()["protocol_validation"]
        self.assertEqual(validation["accepted_count"], 0)
        self.assertEqual(validation["rejected_count"], 1)
        self.assertIn("evidence must be string, object, or array", validation["rejected"][0]["errors"])

    def test_extract_from_contract_empty_contract_rejected_at_execution(self) -> None:
        """Empty contract dict passes validation but fails at execution time."""
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {
                    "action": "extract_from_contract",
                    "params": {
                        "contract": {},
                        "evidence": "<html></html>",
                    },
                }
            ],
        })

        # Empty contract passes param validation (dict check) but fails at execution
        validation = plan.to_dict()["protocol_validation"]
        self.assertEqual(validation["accepted_count"], 1)

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://example.com",
            profile={"name": "test"},
            run_spec={},
        )

        self.assertFalse(result["results"][0]["ok"])
        self.assertEqual(result["results"][0]["error"], "missing extraction contract")
        self.assertFalse(result["rerun_ready"])


if __name__ == "__main__":
    unittest.main()
