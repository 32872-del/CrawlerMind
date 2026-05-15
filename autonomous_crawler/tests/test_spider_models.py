from __future__ import annotations

import unittest

from autonomous_crawler.runners import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
    canonicalize_request_url,
    make_spider_event,
)
from autonomous_crawler.runtime import RuntimeArtifact, RuntimeEvent


class CrawlRequestEnvelopeTests(unittest.TestCase):
    def test_canonical_url_sorts_query_and_merges_params(self) -> None:
        url = canonicalize_request_url(
            "HTTPS://Example.COM/products?b=2&a=1#frag",
            params={"c": "3", "a": "0"},
        )

        self.assertEqual(url, "https://example.com/products?a=0&a=1&b=2&c=3")

    def test_fingerprint_is_stable_for_json_key_order(self) -> None:
        first = CrawlRequestEnvelope(
            run_id="run",
            url="https://example.com/api",
            method="POST",
            json={"b": 2, "a": 1},
        )
        second = CrawlRequestEnvelope(
            run_id="run",
            url="https://example.com/api",
            method="POST",
            json={"a": 1, "b": 2},
        )

        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.request_id, first.fingerprint[:16])

    def test_fingerprint_can_include_headers_and_fragments(self) -> None:
        request = CrawlRequestEnvelope(
            run_id="run",
            url="https://example.com/page#one",
            headers={"X-Mode": "a"},
        )

        no_header = request.compute_fingerprint(include_headers=False)
        with_header = request.compute_fingerprint(include_headers=True)
        with_fragment = request.compute_fingerprint(keep_fragments=True)

        self.assertNotEqual(no_header, with_header)
        self.assertNotEqual(no_header, with_fragment)

    def test_from_frontier_item_and_runtime_request_conversion(self) -> None:
        envelope = CrawlRequestEnvelope.from_frontier_item(
            {
                "url": "https://shop.example/list",
                "priority": 5,
                "kind": "list",
                "depth": 2,
                "parent_url": "https://shop.example/",
                "attempts": 1,
                "payload": {
                    "method": "POST",
                    "json": {"page": 1},
                    "meta": {
                        "proxy_url": "http://user:pass@proxy.example:8080",
                        "storage_state_path": "profiles/shop/state.json",
                    },
                },
            },
            run_id="run-shop",
            headers={"Authorization": "Bearer secret"},
            cookies={"sid": "abc"},
            session_profile_id="profile-shop",
        )

        runtime_request = envelope.to_runtime_request(mode="dynamic", timeout_ms=45000)

        self.assertEqual(envelope.kind, "list")
        self.assertEqual(envelope.retry_count, 1)
        self.assertEqual(runtime_request.mode, "dynamic")
        self.assertEqual(runtime_request.timeout_ms, 45000)
        self.assertEqual(runtime_request.json, {"page": 1})
        self.assertEqual(runtime_request.proxy_config["proxy"], "http://user:pass@proxy.example:8080")
        self.assertEqual(runtime_request.meta["request_fingerprint"], envelope.fingerprint)

    def test_safe_dict_redacts_headers_cookies_proxy_and_storage_state(self) -> None:
        envelope = CrawlRequestEnvelope(
            run_id="run",
            url="https://example.com",
            headers={"Authorization": "Bearer secret", "Accept": "text/html"},
            cookies={"sid": "abc"},
            meta={
                "proxy_url": "http://user:pass@proxy.example:8080",
                "storage_state_path": "profiles/site/state.json",
                "token": "secret",
            },
        )

        safe = envelope.to_safe_dict()

        self.assertEqual(safe["headers"]["Authorization"], "[redacted]")
        self.assertEqual(safe["cookies"], {"sid": "[redacted]"})
        self.assertNotIn("pass", safe["meta"]["proxy_url"])
        self.assertIn("[redacted-path]", safe["meta"]["storage_state_path"])
        self.assertEqual(safe["meta"]["token"], "[redacted]")


class CrawlItemResultTests(unittest.TestCase):
    def test_success_converts_to_batch_runner_result(self) -> None:
        request = CrawlRequestEnvelope(run_id="run", url="https://example.com/list")
        detail = CrawlRequestEnvelope(
            run_id="run",
            url="https://example.com/detail/1",
            kind="detail",
            priority=10,
        )
        result = CrawlItemResult.success(
            request,
            status_code=200,
            records=[{"title": "Alpha"}],
            discovered_requests=[detail],
            runtime_events=[RuntimeEvent(type="spider.request_succeeded", message="ok")],
            artifacts=[RuntimeArtifact(kind="html", path="out/page.html")],
            elapsed_ms=12,
        )

        batch_result = result.to_item_process_result()

        self.assertTrue(batch_result.ok)
        self.assertEqual(batch_result.records, [{"title": "Alpha"}])
        self.assertEqual(batch_result.discovered_urls, ["https://example.com/detail/1"])
        self.assertEqual(batch_result.discovered_kind, "detail")
        self.assertEqual(batch_result.discovered_priority, 10)
        self.assertEqual(batch_result.metrics["status_code"], 200)
        self.assertEqual(batch_result.metrics["elapsed_ms"], 12)

    def test_failure_converts_to_retryable_batch_runner_result(self) -> None:
        request = CrawlRequestEnvelope(run_id="run", url="https://example.com/blocked")
        result = CrawlItemResult.failure(
            request,
            error="blocked by status 429",
            status_code=429,
            retry=True,
            failure_bucket="rate_limited",
        )

        batch_result = result.to_item_process_result()

        self.assertFalse(batch_result.ok)
        self.assertTrue(batch_result.retry)
        self.assertEqual(batch_result.metrics["failure_bucket"], "rate_limited")
        self.assertEqual(batch_result.metrics["status_code"], 429)


class SpiderRunSummaryTests(unittest.TestCase):
    def test_summary_records_item_metrics_and_events(self) -> None:
        request = CrawlRequestEnvelope(run_id="run", url="https://example.com")
        ok = CrawlItemResult.success(
            request,
            status_code=200,
            records=[{"title": "A"}, {"title": "B"}],
            discovered_requests=[
                CrawlRequestEnvelope(run_id="run", url="https://example.com/detail", kind="detail")
            ],
            runtime_events=[make_spider_event("request_succeeded", "ok")],
        )
        retry = CrawlItemResult.failure(
            request,
            error="timeout",
            status_code=0,
            retry=True,
            failure_bucket="timeout",
        )
        failed = CrawlItemResult.failure(
            request,
            error="forbidden",
            status_code=403,
            retry=False,
            failure_bucket="http_blocked",
        )

        summary = SpiderRunSummary(run_id="run", status="running")
        summary.record_item(ok)
        summary.record_item(retry)
        summary.record_item(failed)
        payload = summary.as_dict()

        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["retried"], 1)
        self.assertEqual(payload["failed"], 1)
        self.assertEqual(payload["records_saved"], 2)
        self.assertEqual(payload["discovered_urls"], 1)
        self.assertEqual(payload["response_status_count"], {"200": 1, "403": 1})
        self.assertEqual(payload["failure_buckets"], {"timeout": 1, "http_blocked": 1})
        self.assertEqual(payload["events"][0]["type"], "spider.request_succeeded")

    def test_invalid_status_falls_back_to_completed(self) -> None:
        summary = SpiderRunSummary(run_id="run", status="weird")

        self.assertEqual(summary.status, "completed")


if __name__ == "__main__":
    unittest.main()
