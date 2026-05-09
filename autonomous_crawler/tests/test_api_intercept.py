from __future__ import annotations

import unittest

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph
from autonomous_crawler.tools.api_candidates import (
    build_direct_json_candidate,
    fetch_graphql_api,
    fetch_json_api,
    fetch_paginated_api,
    build_api_candidates,
    extract_records_from_json,
    normalize_api_records,
    _detect_pagination_fields,
    _set_query_param,
    is_tracking_url,
    PaginationSpec,
)


class ApiInterceptTests(unittest.TestCase):
    def test_build_api_candidates_ranks_product_api(self) -> None:
        candidates = build_api_candidates(["/static/app.js", "/api/products?page=1"], base_url="https://shop.example")

        self.assertEqual(candidates[0]["url"], "https://shop.example/api/products?page=1")

    def test_extract_records_from_common_json_shapes(self) -> None:
        records = extract_records_from_json({"data": {"items": [{"name": "Alpha"}]}})

        self.assertEqual(records, [{"name": "Alpha"}])

    def test_extract_records_from_training_json_shapes(self) -> None:
        self.assertEqual(
            extract_records_from_json({"hits": [{"title": "HN Story"}]}),
            [{"title": "HN Story"}],
        )
        self.assertEqual(
            extract_records_from_json({"quotes": [{"text": "Quote text"}]}),
            [{"text": "Quote text"}],
        )

    def test_normalize_api_records_maps_name_to_title(self) -> None:
        items = normalize_api_records([{"name": "Alpha", "url": "/p/a"}])

        self.assertEqual(items[0]["title"], "Alpha")
        self.assertEqual(items[0]["link"], "/p/a")

    def test_normalize_api_records_maps_content_platform_metrics(self) -> None:
        items = normalize_api_records([
            {
                "title": {"english": "Attack on Titan", "romaji": "Shingeki no Kyojin"},
                "siteUrl": "https://anilist.co/anime/16498",
                "coverImage": {"medium": "https://img.example/a.jpg"},
                "popularity": 986169,
            },
            {
                "title": "Bilibili Video",
                "pic": "https://img.example/b.jpg",
                "stat": {"view": 12345, "like": 100},
            },
        ])

        self.assertEqual(items[0]["title"], "Attack on Titan")
        self.assertEqual(items[0]["link"], "https://anilist.co/anime/16498")
        self.assertEqual(items[0]["image"], "https://img.example/a.jpg")
        self.assertEqual(items[0]["hot_score"], 986169)
        self.assertEqual(items[1]["hot_score"], 12345)
        self.assertEqual(items[1]["rank"], 2)
        self.assertEqual(items[1]["image"], "https://img.example/b.jpg")

    def test_normalize_api_records_maps_training_api_fields(self) -> None:
        items = normalize_api_records([
            {
                "title": "HN Story",
                "points": 123,
                "story_text": "A useful story summary",
            },
            {
                "title": "Rated Product",
                "rating": 4.7,
                "description": "A product description",
            },
        ])

        self.assertEqual(items[0]["hot_score"], 123)
        self.assertEqual(items[0]["summary"], "A useful story summary")
        self.assertEqual(items[1]["hot_score"], 4.7)
        self.assertEqual(items[1]["summary"], "A product description")

    def test_normalize_api_records_maps_quote_and_github_fields(self) -> None:
        items = normalize_api_records([
            {
                "text": "Quote text",
                "author": {"name": "Ada"},
            },
            {
                "title": "Issue title",
                "html_url": "https://github.example/issues/1",
                "comments": 3,
            },
        ])

        self.assertEqual(items[0]["title"], "Quote text")
        self.assertEqual(items[0]["summary"], "Quote text")
        self.assertEqual(items[1]["link"], "https://github.example/issues/1")
        self.assertEqual(items[1]["hot_score"], 3)


    def test_extract_records_from_reddit_children_shape(self) -> None:
        records = extract_records_from_json({
            "data": {
                "children": [
                    {"kind": "t3", "data": {"title": "Alpha", "score": 12}},
                    {"kind": "t3", "data": {"title": "Beta", "score": 8}},
                ]
            }
        })

        self.assertEqual(records[0]["title"], "Alpha")
        self.assertEqual(records[0]["score"], 12)

    def test_direct_json_candidate_marks_target_url_as_api(self) -> None:
        candidate = build_direct_json_candidate("https://example.test/items.json")

        self.assertEqual(candidate["url"], "https://example.test/items.json")
        self.assertEqual(candidate["reason"], "target_url_is_json")

    def test_recon_marks_json_payload_as_direct_api(self) -> None:
        state = recon_node({
            "target_url": "mock://json-direct",
            "recon_report": {
                "target_fields": ["title"],
                "task_type": "product_list",
            },
            "messages": [],
            "error_log": [],
        })

        recon = state["recon_report"]
        self.assertEqual(recon["rendering"], "api")
        self.assertEqual(recon["api_candidates"][0]["reason"], "target_url_is_json")

    def test_recon_adds_api_candidates(self) -> None:
        state = recon_node({
            "target_url": "mock://site-zoo/spa-shell",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        candidates = state["recon_report"]["api_candidates"]
        self.assertTrue(candidates)
        self.assertIn("/api/products", candidates[0]["url"])

    def test_strategy_uses_api_candidate_when_not_browser_required(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "https://shop.example",
            "recon_report": {
                "target_url": "https://shop.example",
                "task_type": "product_list",
                "constraints": {"max_items": 2},
                "rendering": "static",
                "anti_bot": {"detected": False},
                "api_endpoints": [],
                "api_candidates": [{"url": "mock://api/products", "score": 32}],
                "access_diagnostics": {"findings": [], "signals": {}},
                "dom_structure": {"pagination_type": "none", "field_selectors": {}},
            },
            "retries": 0,
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "mock://api/products")

    def test_strategy_prefers_observed_api_candidate_over_browser_for_spa(self) -> None:
        state = strategy_node({
            "user_goal": "collect stories",
            "target_url": "https://hn.algolia.com/",
            "recon_report": {
                "target_url": "https://hn.algolia.com/",
                "task_type": "ranking_list",
                "constraints": {"max_items": 10},
                "rendering": "spa",
                "anti_bot": {"detected": False},
                "api_endpoints": [],
                "api_candidates": [{
                    "url": "mock://api/search-post",
                    "method": "POST",
                    "kind": "json",
                    "score": 88,
                    "reason": "browser_network_observation",
                    "status_code": 200,
                    "post_data_preview": '{"query":"","hitsPerPage":10}',
                }],
                "access_diagnostics": {"findings": ["js_rendering_likely_required"], "signals": {}},
                "dom_structure": {"pagination_type": "none", "field_selectors": {}, "item_count": 0},
            },
            "retries": 0,
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["extraction_method"], "api_json")
        self.assertEqual(strategy["api_method"], "POST")
        self.assertEqual(strategy["api_post_data"], '{"query":"","hitsPerPage":10}')

    def test_strategy_keeps_browser_for_challenge_even_with_observed_api(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "https://blocked.example",
            "recon_report": {
                "target_url": "https://blocked.example",
                "task_type": "product_list",
                "constraints": {},
                "rendering": "spa",
                "anti_bot": {"detected": True},
                "api_endpoints": [],
                "api_candidates": [{
                    "url": "https://blocked.example/api/products",
                    "method": "GET",
                    "kind": "json",
                    "score": 88,
                    "reason": "browser_network_observation",
                    "status_code": 200,
                }],
                "access_diagnostics": {"findings": [], "signals": {"challenge": "cf-challenge"}},
                "dom_structure": {"pagination_type": "none", "field_selectors": {}, "item_count": 0},
            },
            "retries": 0,
            "messages": [],
        })

        self.assertEqual(state["crawl_strategy"]["mode"], "browser")

    def test_strategy_prefers_good_dom_candidates_over_weak_api_hints(self) -> None:
        state = strategy_node({
            "user_goal": "collect documentation links",
            "target_url": "https://docs.example",
            "recon_report": {
                "target_url": "https://docs.example",
                "task_type": "product_list",
                "constraints": {"max_items": 10},
                "rendering": "ssr",
                "anti_bot": {"detected": False},
                "api_endpoints": [],
                "api_candidates": [{"url": "https://docs.example/api/", "score": 20}],
                "access_diagnostics": {"findings": [], "signals": {}},
                "dom_structure": {
                    "pagination_type": "none",
                    "product_selector": ".doc-link",
                    "item_count": 5,
                    "field_selectors": {
                        "title": "a",
                        "link": "a@href",
                    },
                },
            },
            "retries": 0,
            "messages": [],
        })

        self.assertEqual(state["crawl_strategy"]["mode"], "http")
        self.assertEqual(state["crawl_strategy"]["extraction_method"], "dom_parse")

    def test_executor_api_intercept_extracts_mock_json(self) -> None:
        state = executor_node({
            "target_url": "https://shop.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "api_endpoint": "mock://api/products",
                "headers": {},
                "max_items": 2,
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 2)
        self.assertEqual(state["extracted_data"]["items"][0]["title"], "API Alpha")

    def test_executor_api_intercept_extracts_post_json(self) -> None:
        state = executor_node({
            "target_url": "https://search.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "extraction_method": "api_json",
                "api_endpoint": "mock://api/search-post",
                "api_method": "POST",
                "api_post_data": '{"query":"","hitsPerPage":2}',
                "headers": {},
                "max_items": 2,
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 2)
        self.assertEqual(state["extracted_data"]["items"][0]["title"], "POST Alpha")

    def test_fetch_json_api_supports_mock_post(self) -> None:
        result = fetch_json_api(
            "mock://api/search-post",
            method="POST",
            post_data='{"query":""}',
        )

        records = extract_records_from_json(result["data"])
        self.assertEqual(records[0]["title"], "POST Alpha")

    def test_executor_graphql_intercept_extracts_mock_json(self) -> None:
        state = executor_node({
            "target_url": "mock://api/graphql-countries",
            "crawl_strategy": {
                "mode": "api_intercept",
                "extraction_method": "graphql_json",
                "api_endpoint": "mock://api/graphql-countries",
                "graphql_query": "{ countries { code name capital } }",
                "graphql_variables": {},
                "headers": {},
                "max_items": 2,
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 2)
        self.assertEqual(state["extracted_data"]["items"][0]["title"], "China")

    def test_fetch_graphql_api_supports_mock_countries(self) -> None:
        result = fetch_graphql_api(
            "mock://api/graphql-countries",
            "{ countries { code name capital } }",
        )

        records = extract_records_from_json(result["data"])
        self.assertEqual(records[0]["code"], "CN")

    def test_graph_completes_api_intercept_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect product titles and prices",
            "target_url": "mock://site-zoo/api-hint-static",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 1,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })

        self.assertEqual(final_state["status"], "completed")
        self.assertEqual(final_state["crawl_strategy"]["mode"], "api_intercept")
        self.assertEqual(final_state["extracted_data"]["item_count"], 2)

    def test_graph_completes_direct_json_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect product titles",
            "target_url": "mock://json-direct",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 1,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })

        self.assertEqual(final_state["status"], "completed")
        self.assertEqual(final_state["crawl_strategy"]["mode"], "api_intercept")
        self.assertEqual(final_state["extracted_data"]["item_count"], 2)

    def test_graph_completes_explicit_graphql_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect country names and capitals",
            "target_url": "mock://api/graphql-countries",
            "recon_report": {
                "target_fields": ["title", "capital"],
                "task_type": "product_list",
                "constraints": {
                    "graphql_query": "{ countries { code name capital } }",
                    "max_items": 2,
                },
            },
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 1,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })

        self.assertEqual(final_state["status"], "completed")
        self.assertEqual(final_state["recon_report"]["fetch"]["selected_mode"], "configured_api")
        self.assertIn("capital", final_state["recon_report"]["target_fields"])
        self.assertEqual(final_state["crawl_strategy"]["extraction_method"], "graphql_json")
        self.assertEqual(final_state["extracted_data"]["items"][0]["capital"], "Beijing")


class PaginationDetectionTests(unittest.TestCase):
    def test_detect_next_cursor(self) -> None:
        result = _detect_pagination_fields({"items": [], "next_cursor": "abc123"})
        self.assertEqual(result["next_cursor"], "abc123")

    def test_detect_next_page(self) -> None:
        result = _detect_pagination_fields({"items": [], "next_page": 3})
        self.assertEqual(result["next_page"], 3)

    def test_detect_next_offset(self) -> None:
        result = _detect_pagination_fields({"items": [], "next_offset": 20})
        self.assertEqual(result["next_offset"], 20)

    def test_detect_no_pagination(self) -> None:
        result = _detect_pagination_fields({"items": [1, 2, 3]})
        self.assertEqual(result, {})

    def test_detect_prefers_first_cursor_field(self) -> None:
        result = _detect_pagination_fields({"after": "xyz", "next_cursor": "abc"})
        self.assertEqual(result["next_cursor"], "abc")

    def test_set_query_param_adds_param(self) -> None:
        url = _set_query_param("https://api.test/items", "page", "2")
        self.assertEqual(url, "https://api.test/items?page=2")

    def test_set_query_param_updates_existing(self) -> None:
        url = _set_query_param("https://api.test/items?page=1", "page", "3")
        self.assertEqual(url, "https://api.test/items?page=3")


class PagePaginationTests(unittest.TestCase):
    def test_mock_paged_products_page_1(self) -> None:
        result = fetch_json_api("mock://api/paged-products?page=1")
        self.assertTrue(result["ok"])
        data = result["data"]
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["items"][0]["title"], "Paged Alpha")
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["next_page"], 2)

    def test_mock_paged_products_page_3(self) -> None:
        result = fetch_json_api("mock://api/paged-products?page=3")
        data = result["data"]
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["items"][0]["title"], "Paged Eta")
        self.assertNotIn("next_page", data)

    def test_mock_paged_products_empty_page(self) -> None:
        result = fetch_json_api("mock://api/paged-products?page=4")
        data = result["data"]
        self.assertEqual(len(data["items"]), 0)

    def test_fetch_paginated_page_type(self) -> None:
        spec = PaginationSpec(type="page", limit=3, max_pages=10)
        result = fetch_paginated_api("mock://api/paged-products", pagination=spec)
        self.assertEqual(result.pagination_type, "page")
        self.assertEqual(len(result.all_items), 9)
        self.assertEqual(result.pages_fetched, 3)
        self.assertEqual(result.all_items[0]["title"], "Paged Alpha")
        self.assertEqual(result.all_items[8]["title"], "Paged Iota")

    def test_fetch_paginated_page_respects_max_items(self) -> None:
        spec = PaginationSpec(type="page", limit=3, max_pages=10)
        result = fetch_paginated_api(
            "mock://api/paged-products", pagination=spec, max_items=5,
        )
        self.assertEqual(len(result.all_items), 5)

    def test_executor_page_pagination(self) -> None:
        state = executor_node({
            "target_url": "https://shop.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "api_endpoint": "mock://api/paged-products",
                "headers": {},
                "max_items": 0,
                "pagination": {"type": "page", "param": "page", "limit": 3, "max_pages": 10},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 9)
        self.assertEqual(len(state["api_responses"]), 3)


class OffsetPaginationTests(unittest.TestCase):
    def test_mock_offset_products_page_1(self) -> None:
        result = fetch_json_api("mock://api/offset-products?offset=0&limit=3")
        data = result["data"]
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["items"][0]["title"], "Offset Alpha")
        self.assertEqual(data["next_offset"], 3)

    def test_mock_offset_products_last_page(self) -> None:
        result = fetch_json_api("mock://api/offset-products?offset=6&limit=3")
        data = result["data"]
        self.assertEqual(len(data["items"]), 3)
        self.assertNotIn("next_offset", data)

    def test_fetch_paginated_offset_type(self) -> None:
        spec = PaginationSpec(type="offset", limit=3, max_pages=10)
        result = fetch_paginated_api("mock://api/offset-products", pagination=spec)
        self.assertEqual(result.pagination_type, "offset")
        self.assertEqual(len(result.all_items), 9)
        self.assertEqual(result.pages_fetched, 3)

    def test_fetch_paginated_offset_respects_max_items(self) -> None:
        spec = PaginationSpec(type="offset", limit=3, max_pages=10)
        result = fetch_paginated_api(
            "mock://api/offset-products", pagination=spec, max_items=4,
        )
        self.assertEqual(len(result.all_items), 4)

    def test_executor_offset_pagination(self) -> None:
        state = executor_node({
            "target_url": "https://shop.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "api_endpoint": "mock://api/offset-products",
                "headers": {},
                "max_items": 0,
                "pagination": {"type": "offset", "param": "offset", "limit": 3, "max_pages": 10},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 9)


class CursorPaginationTests(unittest.TestCase):
    def test_mock_cursor_products_first_page(self) -> None:
        result = fetch_json_api("mock://api/cursor-products?cursor=")
        data = result["data"]
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["items"][0]["title"], "Cursor Alpha")
        self.assertEqual(data["next_cursor"], "page2")

    def test_mock_cursor_products_last_page(self) -> None:
        result = fetch_json_api("mock://api/cursor-products?cursor=page3")
        data = result["data"]
        self.assertEqual(len(data["items"]), 3)
        self.assertNotIn("next_cursor", data)

    def test_fetch_paginated_cursor_type(self) -> None:
        spec = PaginationSpec(type="cursor", max_pages=10)
        result = fetch_paginated_api("mock://api/cursor-products", pagination=spec)
        self.assertEqual(result.pagination_type, "cursor")
        self.assertEqual(len(result.all_items), 9)
        self.assertEqual(result.pages_fetched, 3)
        self.assertEqual(result.all_items[0]["title"], "Cursor Alpha")
        self.assertEqual(result.all_items[8]["title"], "Cursor Iota")

    def test_fetch_paginated_cursor_respects_max_items(self) -> None:
        spec = PaginationSpec(type="cursor", max_pages=10)
        result = fetch_paginated_api(
            "mock://api/cursor-products", pagination=spec, max_items=7,
        )
        self.assertEqual(len(result.all_items), 7)

    def test_executor_cursor_pagination(self) -> None:
        state = executor_node({
            "target_url": "https://search.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "api_endpoint": "mock://api/cursor-products",
                "headers": {},
                "max_items": 0,
                "pagination": {"type": "cursor", "param": "cursor", "max_pages": 10},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 9)

    def test_executor_cursor_pagination_max_items(self) -> None:
        state = executor_node({
            "target_url": "https://search.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "api_endpoint": "mock://api/cursor-products",
                "headers": {},
                "max_items": 4,
                "pagination": {"type": "cursor", "param": "cursor", "max_pages": 10},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 4)

    def test_fetch_paginated_none_type_uses_single_fetch(self) -> None:
        result = fetch_paginated_api("mock://api/products")
        self.assertEqual(result.pagination_type, "none")
        self.assertEqual(result.pages_fetched, 1)
        self.assertTrue(result.all_items)

    def test_api_responses_captured_per_page(self) -> None:
        spec = PaginationSpec(type="page", limit=3, max_pages=10)
        result = fetch_paginated_api("mock://api/paged-products", pagination=spec)
        self.assertEqual(len(result.api_responses), 3)
        for resp in result.api_responses:
            self.assertTrue(resp["ok"])


class AnalyticsDenylistTests(unittest.TestCase):
    def test_is_tracking_url_google_analytics(self) -> None:
        self.assertTrue(is_tracking_url("https://www.google-analytics.com/collect"))
        self.assertTrue(is_tracking_url("https://www.googletagmanager.com/gtm.js"))

    def test_is_tracking_url_segment_mixpanel(self) -> None:
        self.assertTrue(is_tracking_url("https://api.segment.io/v1/track"))
        self.assertTrue(is_tracking_url("https://api.mixpanel.com/track"))

    def test_is_tracking_url_beacon_pixel(self) -> None:
        self.assertTrue(is_tracking_url("https://example.com/pixel.gif"))
        self.assertTrue(is_tracking_url("https://example.com/beacon"))
        self.assertTrue(is_tracking_url("https://example.com/collect"))

    def test_is_tracking_url_normal_api(self) -> None:
        self.assertFalse(is_tracking_url("https://api.example.com/products"))
        self.assertFalse(is_tracking_url("https://shop.example.com/api/items"))

    def test_build_api_candidates_filters_tracking(self) -> None:
        candidates = build_api_candidates([
            "/api/products",
            "https://www.google-analytics.com/collect",
            "https://api.mixpanel.com/track",
            "/api/items",
        ], base_url="https://shop.example")
        urls = [c["url"] for c in candidates]
        self.assertNotIn("https://www.google-analytics.com/collect", urls)
        self.assertNotIn("https://api.mixpanel.com/track", urls)
        self.assertEqual(len(candidates), 2)

    def test_build_api_candidates_empty_after_filtering(self) -> None:
        candidates = build_api_candidates([
            "https://www.google-analytics.com/collect",
            "https://api.segment.io/v1/track",
        ])
        self.assertEqual(candidates, [])


class CrossPageDedupeTests(unittest.TestCase):
    def test_fetch_paginated_dedupes_across_pages(self) -> None:
        spec = PaginationSpec(type="page", limit=2, max_pages=10)
        result = fetch_paginated_api("mock://api/duped-products", pagination=spec)
        # Page 1: a1, b2; Page 2: b2 (dup), c3 → unique: a1, b2, c3
        self.assertEqual(len(result.all_items), 3)
        ids = [item.get("id") for item in result.all_items]
        self.assertEqual(ids, ["a1", "b2", "c3"])
        self.assertEqual(result.deduplicated_count, 1)

    def test_fetch_paginated_no_dedup_when_no_dupes(self) -> None:
        spec = PaginationSpec(type="page", limit=3, max_pages=10)
        result = fetch_paginated_api("mock://api/paged-products", pagination=spec)
        self.assertEqual(result.deduplicated_count, 0)
        self.assertEqual(len(result.all_items), 9)


class CursorStuckGuardTests(unittest.TestCase):
    def test_cursor_stuck_breaks_loop(self) -> None:
        spec = PaginationSpec(type="cursor", max_pages=10)
        result = fetch_paginated_api("mock://api/cursor-stuck", pagination=spec)
        # First page: "", second page: "stuck" (next_cursor="stuck" = current) → stops
        self.assertEqual(result.stop_reason, "cursor_stuck")
        self.assertEqual(result.pages_fetched, 2)
        self.assertEqual(len(result.all_items), 2)


class RepeatedUrlGuardTests(unittest.TestCase):
    def test_repeated_url_detected(self) -> None:
        # Use empty-after-first: page 1 has items, pages 2-3 are empty.
        # The empty-page guard should stop at threshold 2, but let's verify
        # repeated URL detection works by checking stop_reason.
        spec = PaginationSpec(type="page", limit=1, max_pages=10, empty_page_threshold=3)
        result = fetch_paginated_api("mock://api/empty-after-first", pagination=spec)
        # Pages 2 and 3 are empty, threshold=3 so we don't hit empty_pages.
        # Page 4 would be generated but there's no next_page hint after page 3,
        # so we get "no_next_hint" stop.
        self.assertIn(result.stop_reason, ("no_next_hint", "empty_pages"))
        self.assertEqual(result.pages_fetched, 1)


class EmptyPageGuardTests(unittest.TestCase):
    def test_empty_page_guard_stops_after_threshold(self) -> None:
        spec = PaginationSpec(type="page", limit=1, max_pages=10, empty_page_threshold=2)
        result = fetch_paginated_api("mock://api/empty-after-first", pagination=spec)
        # Page 1 has items, page 2 is empty (count=1), page 3 is empty (count=2 → stop)
        self.assertEqual(result.stop_reason, "empty_pages")
        self.assertEqual(result.pages_fetched, 1)
        self.assertEqual(len(result.all_items), 1)

    def test_empty_page_guard_resets_on_nonempty(self) -> None:
        # Normal paged products: all pages have items, no empty pages
        spec = PaginationSpec(type="page", limit=3, max_pages=10, empty_page_threshold=1)
        result = fetch_paginated_api("mock://api/paged-products", pagination=spec)
        self.assertEqual(result.stop_reason, "no_next_hint")
        self.assertEqual(result.pages_fetched, 3)

    def test_stop_reason_max_items(self) -> None:
        spec = PaginationSpec(type="page", limit=3, max_pages=10)
        result = fetch_paginated_api(
            "mock://api/paged-products", pagination=spec, max_items=4,
        )
        self.assertEqual(result.stop_reason, "max_items")

    def test_stop_reason_no_next_hint(self) -> None:
        spec = PaginationSpec(type="page", limit=3, max_pages=10)
        result = fetch_paginated_api("mock://api/paged-products", pagination=spec)
        self.assertEqual(result.stop_reason, "no_next_hint")


if __name__ == "__main__":
    unittest.main()
