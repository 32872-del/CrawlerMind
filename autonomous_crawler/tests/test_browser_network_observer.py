from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.tools.browser_network_observer import (
    NetworkEntry,
    NetworkObservationResult,
    build_api_candidates_from_entries,
    observe_browser_network,
    sanitize_headers,
    score_network_entry,
)
from autonomous_crawler.agents.recon import _merge_api_candidates, _should_observe_network, recon_node


class BrowserNetworkObserverUnitTests(unittest.TestCase):
    def test_sanitize_headers_redacts_sensitive_values(self) -> None:
        headers = sanitize_headers({
            "Authorization": "Bearer secret",
            "Cookie": "sid=secret",
            "Accept": "application/json",
        })

        self.assertEqual(headers["Authorization"], "[redacted]")
        self.assertEqual(headers["Cookie"], "[redacted]")
        self.assertEqual(headers["Accept"], "application/json")

    def test_score_json_xhr_api_candidate(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/api/products?page=1",
            method="GET",
            resource_type="xhr",
            status_code=200,
            response_headers={"content-type": "application/json"},
            json_preview={"items": [{"title": "Alpha"}]},
        )

        score, reasons, kind = score_network_entry(entry)

        self.assertGreaterEqual(score, 50)
        self.assertEqual(kind, "json")
        self.assertIn("xhr_fetch", reasons)
        self.assertIn("json", reasons)
        self.assertIn("api_url_keywords", reasons)

    def test_score_graphql_post_candidate(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/graphql",
            method="POST",
            resource_type="fetch",
            status_code=200,
            response_headers={"content-type": "application/json"},
            post_data_preview='{"query":"query Products { products { title } }"}',
            json_preview={"data": {"products": []}},
        )

        score, reasons, kind = score_network_entry(entry)

        self.assertGreaterEqual(score, 70)
        self.assertEqual(kind, "graphql")
        self.assertIn("graphql_signal", reasons)

    def test_static_assets_score_low(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/app.js",
            method="GET",
            resource_type="script",
            status_code=200,
            response_headers={"content-type": "application/javascript"},
        )

        score, reasons, kind = score_network_entry(entry)

        self.assertLess(score, 20)
        self.assertEqual(kind, "other")
        self.assertIn("static_asset", reasons)

    def test_build_api_candidates_dedupes_and_sorts(self) -> None:
        weak = NetworkEntry(url="https://example.com/app.js", method="GET", score=5)
        strong = NetworkEntry(
            url="https://example.com/api/list",
            method="GET",
            resource_type="xhr",
            status_code=200,
            kind="json",
            score=55,
        )
        duplicate = NetworkEntry(
            url="https://example.com/api/list",
            method="GET",
            resource_type="xhr",
            status_code=200,
            kind="json",
            score=50,
        )

        candidates = build_api_candidates_from_entries([weak, duplicate, strong])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["url"], "https://example.com/api/list")
        self.assertEqual(candidates[0]["reason"], "browser_network_observation")


class BrowserNetworkObserverPlaywrightTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_observe_browser_network_captures_json_response(self, mock_pw_cls: MagicMock) -> None:
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.resource_type = "xhr"
        mock_request.headers = {"Authorization": "Bearer secret", "Accept": "application/json"}
        mock_request.post_data = ""

        mock_response = MagicMock()
        mock_response.url = "https://example.com/api/products"
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.request = mock_request
        mock_response.json.return_value = {"items": [{"title": "Alpha"}]}

        mock_page = MagicMock()
        mock_page.url = "https://example.com/catalog"
        callbacks = {}

        def on_event(event: str, callback):
            callbacks[event] = callback

        def goto(*args, **kwargs):
            callbacks["response"](mock_response)

        mock_page.on.side_effect = on_event
        mock_page.goto.side_effect = goto

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network("https://example.com/catalog")

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.final_url, "https://example.com/catalog")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].request_headers["Authorization"], "[redacted]")
        self.assertEqual(result.api_candidates[0]["url"], "https://example.com/api/products")

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright", None)
    def test_observe_browser_network_handles_missing_playwright(self) -> None:
        result = observe_browser_network("https://example.com")

        self.assertEqual(result.status, "failed")
        self.assertIn("playwright is not installed", result.error)

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_observe_browser_network_handles_navigation_failure(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.goto.side_effect = RuntimeError("Navigation failed")

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network("https://example.com")

        self.assertEqual(result.status, "failed")
        self.assertIn("Navigation failed", result.error)

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_observe_browser_network_respects_entry_limit(self, mock_pw_cls: MagicMock) -> None:
        responses = []
        for index in range(3):
            req = MagicMock()
            req.method = "GET"
            req.resource_type = "xhr"
            req.headers = {}
            req.post_data = ""
            resp = MagicMock()
            resp.url = f"https://example.com/api/{index}"
            resp.status = 200
            resp.headers = {"content-type": "application/json"}
            resp.request = req
            resp.json.return_value = {"index": index}
            responses.append(resp)

        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        callbacks = {}
        mock_page.on.side_effect = lambda event, callback: callbacks.setdefault(event, callback)
        mock_page.goto.side_effect = lambda *args, **kwargs: [
            callbacks["response"](response) for response in responses
        ]

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network("https://example.com", max_entries=2)

        self.assertEqual(len(result.entries), 2)


class NetworkEntryToDictTests(unittest.TestCase):
    def test_to_dict_returns_all_expected_keys(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/api",
            method="POST",
            resource_type="fetch",
            status_code=200,
            request_headers={"Accept": "application/json"},
            response_headers={"content-type": "application/json"},
            post_data_preview='{"q":"test"}',
            json_preview={"data": []},
            kind="graphql",
            score=70,
            reasons=["graphql_signal"],
        )
        result = entry.to_dict()

        expected_keys = {
            "url", "method", "resource_type", "status_code",
            "request_headers", "response_headers",
            "post_data_preview", "json_preview", "kind", "score", "reasons",
        }
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result["url"], "https://example.com/api")
        self.assertEqual(result["method"], "POST")
        self.assertEqual(result["kind"], "graphql")
        self.assertEqual(result["score"], 70)

    def test_to_dict_returns_copies_not_references(self) -> None:
        entry = NetworkEntry(
            url="https://example.com",
            request_headers={"X-Test": "value"},
            response_headers={"content-type": "text/html"},
            reasons=["status_ok"],
        )
        result = entry.to_dict()

        result["request_headers"]["X-Test"] = "mutated"
        result["reasons"].append("extra")
        self.assertEqual(entry.request_headers["X-Test"], "value")
        self.assertNotIn("extra", entry.reasons)

    def test_to_dict_default_empty_entry(self) -> None:
        entry = NetworkEntry(url="https://example.com")
        result = entry.to_dict()

        self.assertEqual(result["method"], "GET")
        self.assertEqual(result["resource_type"], "")
        self.assertIsNone(result["status_code"])
        self.assertEqual(result["post_data_preview"], "")
        self.assertIsNone(result["json_preview"])
        self.assertEqual(result["kind"], "other")
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["reasons"], [])


class NetworkObservationResultToDictTests(unittest.TestCase):
    def test_to_dict_returns_all_expected_keys(self) -> None:
        result = NetworkObservationResult(
            url="https://example.com",
            final_url="https://example.com/page",
            status="ok",
            error="",
            entries=[NetworkEntry(url="https://example.com/api", score=50)],
            api_candidates=[{"url": "https://example.com/api", "score": 50}],
        )
        d = result.to_dict()

        expected_keys = {"url", "final_url", "status", "error", "entries", "api_candidates"}
        self.assertEqual(set(d.keys()), expected_keys)
        self.assertEqual(d["url"], "https://example.com")
        self.assertEqual(d["final_url"], "https://example.com/page")
        self.assertEqual(d["status"], "ok")
        self.assertEqual(len(d["entries"]), 1)
        self.assertEqual(len(d["api_candidates"]), 1)

    def test_to_dict_failed_result(self) -> None:
        result = NetworkObservationResult(
            url="https://example.com",
            status="failed",
            error="timeout",
        )
        d = result.to_dict()

        self.assertEqual(d["status"], "failed")
        self.assertEqual(d["error"], "timeout")
        self.assertEqual(d["entries"], [])
        self.assertEqual(d["api_candidates"], [])


class ScoreEdgeCaseTests(unittest.TestCase):
    def test_score_blocked_status_codes(self) -> None:
        for code in (401, 403, 429, 503):
            entry = NetworkEntry(
                url="https://example.com/api",
                status_code=code,
                resource_type="xhr",
                response_headers={"content-type": "application/json"},
            )
            score, reasons, _ = score_network_entry(entry)
            self.assertIn(f"blocked_or_limited:{code}", reasons)

    def test_score_no_status_code(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/api",
            resource_type="xhr",
            response_headers={"content-type": "application/json"},
        )
        score, reasons, _ = score_network_entry(entry)
        self.assertNotIn("status_ok", reasons)
        self.assertNotIn("blocked_or_limited", ",".join(reasons))

    def test_score_post_method_bonus(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/api",
            method="POST",
            resource_type="xhr",
            response_headers={"content-type": "application/json"},
            status_code=200,
        )
        score, reasons, _ = score_network_entry(entry)
        self.assertIn("post", reasons)

    def test_score_graphql_in_url(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/v1/graphql",
            method="GET",
            status_code=200,
            response_headers={"content-type": "application/json"},
        )
        score, reasons, kind = score_network_entry(entry)
        self.assertIn("graphql_signal", reasons)
        self.assertEqual(kind, "graphql")

    def test_score_query_in_post_data(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/gateway",
            method="POST",
            status_code=200,
            response_headers={"content-type": "application/json"},
            post_data_preview='{"query":"{ users { name } }"}',
        )
        score, reasons, kind = score_network_entry(entry)
        self.assertIn("graphql_signal", reasons)
        self.assertEqual(kind, "graphql")

    def test_score_algolia_query_json_is_not_graphql(self) -> None:
        entry = NetworkEntry(
            url="https://example.algolia.net/1/indexes/Item_dev/query",
            method="POST",
            resource_type="xhr",
            status_code=200,
            response_headers={"content-type": "application/json"},
            post_data_preview='{"query":"","hitsPerPage":30,"tagFilters":[["story"],[]]}',
            json_preview={"hits": [{"title": "Story"}]},
        )

        score, reasons, kind = score_network_entry(entry)
        self.assertGreaterEqual(score, 50)
        self.assertNotIn("graphql_signal", reasons)
        self.assertEqual(kind, "json")


class ShouldKeepEntryTests(unittest.TestCase):
    def test_keep_high_score_entry(self) -> None:
        entry = NetworkEntry(url="https://example.com/api", score=20)
        from autonomous_crawler.tools.browser_network_observer import _should_keep_entry
        self.assertTrue(_should_keep_entry(entry))

    def test_keep_xhr_fetch_low_score(self) -> None:
        entry = NetworkEntry(url="https://example.com/api", score=5, resource_type="xhr")
        from autonomous_crawler.tools.browser_network_observer import _should_keep_entry
        self.assertTrue(_should_keep_entry(entry))

    def test_keep_fetch_low_score(self) -> None:
        entry = NetworkEntry(url="https://example.com/api", score=5, resource_type="fetch")
        from autonomous_crawler.tools.browser_network_observer import _should_keep_entry
        self.assertTrue(_should_keep_entry(entry))

    def test_discard_low_score_non_xhr(self) -> None:
        entry = NetworkEntry(url="https://example.com/img.png", score=5, resource_type="image")
        from autonomous_crawler.tools.browser_network_observer import _should_keep_entry
        self.assertFalse(_should_keep_entry(entry))


class HeaderAndTruncationTests(unittest.TestCase):
    def test_header_value_case_insensitive(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _header_value
        headers = {"Content-Type": "application/json"}
        self.assertEqual(_header_value(headers, "content-type"), "application/json")
        self.assertEqual(_header_value(headers, "CONTENT-TYPE"), "application/json")

    def test_header_value_missing_returns_empty(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _header_value
        self.assertEqual(_header_value({}, "content-type"), "")
        self.assertEqual(_header_value({"accept": "text/html"}, "content-type"), "")

    def test_truncate_short_text_unchanged(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _truncate
        self.assertEqual(_truncate("hello", 100), "hello")

    def test_truncate_long_text(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _truncate
        result = _truncate("a" * 500, 300)
        self.assertEqual(len(result), 300 + len("...[truncated]"))
        self.assertTrue(result.endswith("...[truncated]"))

    def test_sanitize_headers_truncates_long_values(self) -> None:
        long_value = "x" * 500
        result = sanitize_headers({"X-Custom": long_value})
        self.assertTrue(result["X-Custom"].endswith("...[truncated]"))
        self.assertLess(len(result["X-Custom"]), 500)

    def test_sanitize_headers_none_input(self) -> None:
        self.assertEqual(sanitize_headers(None), {})

    def test_sanitize_headers_all_sensitive_headers_redacted(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import SENSITIVE_HEADER_NAMES
        headers = {name: "secret" for name in SENSITIVE_HEADER_NAMES}
        result = sanitize_headers(headers)
        for name in SENSITIVE_HEADER_NAMES:
            self.assertEqual(result[name], "[redacted]")


class JsonCaptureTests(unittest.TestCase):
    def test_json_preview_not_captured_for_non_json(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/page",
            response_headers={"content-type": "text/html"},
        )
        from autonomous_crawler.tools.browser_network_observer import _response_looks_json
        self.assertFalse(_response_looks_json(entry.response_headers, entry.url))

    def test_json_preview_captured_for_json_url(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _response_looks_json
        headers = {"content-type": "text/html"}
        self.assertTrue(_response_looks_json(headers, "https://example.com/data.json"))

    def test_json_preview_captured_for_json_content_type(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _response_looks_json
        headers = {"content-type": "application/json; charset=utf-8"}
        self.assertTrue(_response_looks_json(headers, "https://example.com/api"))

    def test_truncate_json_short_unchanged(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _truncate_json
        data = {"key": "value"}
        self.assertEqual(_truncate_json(data), data)

    def test_truncate_json_long_wraps_in_preview(self) -> None:
        from autonomous_crawler.tools.browser_network_observer import _truncate_json
        data = {"items": [{"id": i, "name": f"item_{i}"} for i in range(200)]}
        result = _truncate_json(data, limit=500)
        self.assertIn("preview", result)
        self.assertTrue(result["preview"].endswith("...[truncated]"))


class BuildCandidatesEdgeCaseTests(unittest.TestCase):
    def test_empty_entries_returns_empty(self) -> None:
        self.assertEqual(build_api_candidates_from_entries([]), [])

    def test_all_low_score_entries_returns_empty(self) -> None:
        entries = [NetworkEntry(url="https://example.com", score=5)]
        self.assertEqual(build_api_candidates_from_entries(entries), [])

    def test_graphql_candidate_includes_post_data(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/graphql",
            method="POST",
            resource_type="fetch",
            status_code=200,
            kind="graphql",
            score=80,
            post_data_preview='{"query":"{ products { title } }"}',
        )
        candidates = build_api_candidates_from_entries([entry])
        self.assertEqual(len(candidates), 1)
        self.assertIn("post_data_preview", candidates[0])
        self.assertEqual(candidates[0]["post_data_preview"], '{"query":"{ products { title } }"}')

    def test_non_post_json_candidate_no_post_data(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/api/list",
            method="GET",
            resource_type="xhr",
            status_code=200,
            kind="json",
            score=55,
        )
        candidates = build_api_candidates_from_entries([entry])
        self.assertEqual(len(candidates), 1)
        self.assertNotIn("post_data_preview", candidates[0])

    def test_post_json_candidate_includes_post_data(self) -> None:
        entry = NetworkEntry(
            url="https://example.com/api/search",
            method="POST",
            resource_type="xhr",
            status_code=200,
            kind="json",
            score=60,
            post_data_preview='{"query":"","page":0}',
        )
        candidates = build_api_candidates_from_entries([entry])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["kind"], "json")
        self.assertEqual(candidates[0]["post_data_preview"], '{"query":"","page":0}')


class ObserveNetworkEdgeCaseTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_invalid_wait_until_falls_back(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"

        captured_kwargs = {}
        def goto_capture(*args, **kwargs):
            captured_kwargs.update(kwargs)

        mock_page.goto.side_effect = goto_capture
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com", wait_until="invalid_value")

        self.assertEqual(captured_kwargs.get("wait_until"), "networkidle")

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_default_wait_until_is_networkidle(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        captured_kwargs = {}
        mock_page.goto.side_effect = lambda *args, **kwargs: captured_kwargs.update(kwargs)
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com")

        self.assertEqual(captured_kwargs.get("wait_until"), "networkidle")

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_render_time_ms_waits_after_selector(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network(
            "https://example.com",
            wait_selector="#ready",
            render_time_ms=750,
        )

        mock_page.wait_for_selector.assert_called_once_with("#ready", timeout=30000)
        mock_page.wait_for_timeout.assert_called_once_with(750)

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_render_time_ms_zero_does_not_wait(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com", render_time_ms=0)

        mock_page.wait_for_timeout.assert_not_called()

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_browser_closed_on_success(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com")

        mock_browser.close.assert_called_once()

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_browser_closed_on_navigation_error(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("timeout")
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com")

        mock_browser.close.assert_called_once()

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_response_json_failure_returns_none_preview(self, mock_pw_cls: MagicMock) -> None:
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.resource_type = "xhr"
        mock_request.headers = {}
        mock_request.post_data = ""

        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.request = mock_request
        mock_response.json.side_effect = ValueError("not json")

        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        callbacks = {}
        mock_page.on.side_effect = lambda event, callback: callbacks.setdefault(event, callback)
        mock_page.goto.side_effect = lambda *a, **kw: callbacks["response"](mock_response)
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network("https://example.com")

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.entries), 1)
        self.assertIsNone(result.entries[0].json_preview)

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_wait_selector_called(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com", wait_selector="#content", timeout_ms=5000)

        mock_page.wait_for_selector.assert_called_once_with("#content", timeout=5000)

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_no_wait_selector_when_empty(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        observe_browser_network("https://example.com", wait_selector="")

        mock_page.wait_for_selector.assert_not_called()

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_capture_json_preview_disabled(self, mock_pw_cls: MagicMock) -> None:
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.resource_type = "xhr"
        mock_request.headers = {}
        mock_request.post_data = ""

        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.request = mock_request
        mock_response.json.return_value = {"items": []}

        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        callbacks = {}
        mock_page.on.side_effect = lambda event, callback: callbacks.setdefault(event, callback)
        mock_page.goto.side_effect = lambda *a, **kw: callbacks["response"](mock_response)
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network("https://example.com", capture_json_preview=False)

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.entries), 1)
        self.assertIsNone(result.entries[0].json_preview)
        mock_response.json.assert_not_called()

    @patch("autonomous_crawler.tools.browser_network_observer.sync_playwright")
    def test_entries_collected_before_goto_and_during(self, mock_pw_cls: MagicMock) -> None:
        pre_goto_response = MagicMock()
        pre_goto_response.url = "https://example.com/pre"
        pre_goto_response.status = 200
        pre_goto_response.headers = {"content-type": "application/json"}
        pre_goto_request = MagicMock()
        pre_goto_request.method = "GET"
        pre_goto_request.resource_type = "fetch"
        pre_goto_request.headers = {}
        pre_goto_request.post_data = ""
        pre_goto_response.request = pre_goto_request
        pre_goto_response.json.return_value = {"pre": True}

        during_goto_response = MagicMock()
        during_goto_response.url = "https://example.com/during"
        during_goto_response.status = 200
        during_goto_response.headers = {"content-type": "application/json"}
        during_goto_request = MagicMock()
        during_goto_request.method = "GET"
        during_goto_request.resource_type = "xhr"
        during_goto_request.headers = {}
        during_goto_request.post_data = ""
        during_goto_response.request = during_goto_request
        during_goto_response.json.return_value = {"during": True}

        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        callback_holder = {}
        mock_page.on.side_effect = lambda event, callback: callback_holder.setdefault(event, callback)

        def goto_side_effect(*args, **kwargs):
            callback_holder["response"](pre_goto_response)
            callback_holder["response"](during_goto_response)

        mock_page.goto.side_effect = goto_side_effect
        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = observe_browser_network("https://example.com")

        self.assertEqual(len(result.entries), 2)
        urls = {e.url for e in result.entries}
        self.assertIn("https://example.com/pre", urls)
        self.assertIn("https://example.com/during", urls)


class ReconHelperTests(unittest.TestCase):
    def test_merge_api_candidates_dedupes(self) -> None:
        existing = [{"url": "https://example.com/a", "method": "GET", "score": 30}]
        observed = [
            {"url": "https://example.com/a", "method": "GET", "score": 50},
            {"url": "https://example.com/b", "method": "POST", "score": 60},
        ]
        merged = _merge_api_candidates(existing, observed)
        self.assertEqual(len(merged), 2)
        urls = {c["url"] for c in merged}
        self.assertIn("https://example.com/a", urls)
        self.assertIn("https://example.com/b", urls)
        kept_duplicate = next(c for c in merged if c["url"] == "https://example.com/a")
        self.assertEqual(kept_duplicate["score"], 50)

    def test_merge_api_candidates_sorted_by_score(self) -> None:
        existing = [{"url": "https://example.com/a", "method": "GET", "score": 10}]
        observed = [{"url": "https://example.com/b", "method": "GET", "score": 90}]
        merged = _merge_api_candidates(existing, observed)
        self.assertEqual(merged[0]["url"], "https://example.com/b")
        self.assertEqual(merged[1]["url"], "https://example.com/a")

    def test_merge_api_candidates_empty_inputs(self) -> None:
        self.assertEqual(_merge_api_candidates([], []), [])
        self.assertEqual(_merge_api_candidates(None, None), [])

    def test_should_observe_network_requires_http(self) -> None:
        self.assertFalse(_should_observe_network({}, "mock://catalog"))
        self.assertFalse(_should_observe_network({}, "file:///tmp/test.html"))

    def test_should_observe_network_requires_constraint(self) -> None:
        self.assertFalse(_should_observe_network({}, "https://example.com"))
        self.assertFalse(_should_observe_network({"constraints": {}}, "https://example.com"))
        self.assertFalse(
            _should_observe_network(
                {"constraints": {"observe_network": False}},
                "https://example.com",
            )
        )

    def test_should_observe_network_enabled_for_http(self) -> None:
        self.assertTrue(
            _should_observe_network(
                {"constraints": {"observe_network": True}},
                "https://example.com",
            )
        )
        self.assertTrue(
            _should_observe_network(
                {"constraints": {"observe_network": True}},
                "http://example.com",
            )
        )


class BrowserNetworkObserverReconIntegrationTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.recon.observe_browser_network")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_recon_opt_in_records_network_observation(
        self,
        mock_fetch_best,
        mock_observe,
    ) -> None:
        from autonomous_crawler.tools.fetch_policy import BestFetchResult, FetchAttempt
        from autonomous_crawler.tools.html_recon import MOCK_PRODUCT_HTML

        attempt = FetchAttempt(
            mode="requests",
            url="https://example.com/catalog",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
            score=70,
            reasons=["status_ok", "dom_candidates"],
        )
        mock_fetch_best.return_value = BestFetchResult(
            url="https://example.com/catalog",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
            mode="requests",
            score=70,
            attempts=[attempt],
        )

        entry = NetworkEntry(
            url="https://example.com/api/products",
            method="GET",
            resource_type="xhr",
            status_code=200,
            kind="json",
            score=64,
        )
        mock_observe.return_value = type(
            "Observation",
            (),
            {
                "status": "ok",
                "entries": [entry],
                "api_candidates": [
                    {
                        "url": "https://example.com/api/products",
                        "method": "GET",
                        "kind": "json",
                        "score": 64,
                        "reason": "browser_network_observation",
                    }
                ],
                "to_dict": lambda self: {
                    "status": "ok",
                    "entries": [entry.to_dict()],
                    "api_candidates": self.api_candidates,
                },
            },
        )()

        state = recon_node({
            "target_url": "https://example.com/catalog",
            "recon_report": {"constraints": {"observe_network": True}},
            "messages": [],
            "error_log": [],
        })

        recon = state["recon_report"]
        self.assertIn("network_observation", recon)
        self.assertEqual(recon["api_candidates"][0]["url"], "https://example.com/api/products")
        self.assertTrue(any("Network observation" in message for message in state["messages"]))

    @patch("autonomous_crawler.agents.recon.observe_browser_network")
    def test_recon_does_not_observe_network_by_default(self, mock_observe) -> None:
        state = recon_node({
            "target_url": "mock://catalog",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        mock_observe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
