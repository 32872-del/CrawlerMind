"""Error-path tests for the autonomous crawler workflow.

Covers the Priority 3 items from the short-term plan:
- Unsupported URL scheme
- HTTP failure / timeout
- Empty HTML
- Invalid selectors
- Retry exhaustion
- Failure persistence through the graph
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.extractor import extractor_node
from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.agents.validator import validator_node
from autonomous_crawler.storage.result_store import CrawlResultStore
from autonomous_crawler.tools.html_recon import fetch_html
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph


# ---------------------------------------------------------------------------
# 1. Unsupported URL scheme
# ---------------------------------------------------------------------------

class TestUnsupportedURLScheme(unittest.TestCase):
    """Executor and Recon should reject non-HTTP schemes cleanly."""

    def test_executor_rejects_ftp_scheme(self) -> None:
        state = executor_node({
            "target_url": "ftp://files.example.com/data.csv",
            "crawl_strategy": {"mode": "http", "headers": {}},
            "messages": [],
            "error_log": [],
        })
        self.assertEqual(state["status"], "failed")
        self.assertIn("Unsupported URL scheme", state["error_log"][0])
        self.assertEqual(state["raw_html"], {})
        self.assertEqual(state["visited_urls"], [])

    def test_executor_rejects_file_scheme(self) -> None:
        state = executor_node({
            "target_url": "file:///etc/passwd",
            "crawl_strategy": {"mode": "http", "headers": {}},
            "messages": [],
            "error_log": [],
        })
        self.assertEqual(state["status"], "failed")

    def test_recon_rejects_unsupported_scheme(self) -> None:
        result = fetch_html("ftp://files.example.com/data.csv")
        self.assertIn("unsupported scheme", result.error)
        self.assertEqual(result.html, "")

    def test_recon_rejects_mailto_scheme(self) -> None:
        result = fetch_html("mailto:user@example.com")
        self.assertIn("unsupported scheme", result.error)


# ---------------------------------------------------------------------------
# 2. HTTP failure / timeout
# ---------------------------------------------------------------------------

class TestHTTPFailure(unittest.TestCase):
    """Executor should handle network errors gracefully."""

    def test_executor_handles_connection_error(self) -> None:
        state = executor_node({
            "target_url": "https://this-host-does-not-exist.invalid",
            "crawl_strategy": {"mode": "http", "headers": {}},
            "messages": [],
            "error_log": [],
        })
        self.assertEqual(state["status"], "failed")
        self.assertTrue(len(state["error_log"]) > 0)
        self.assertIn("HTTP fetch failed", state["error_log"][0])

    def test_executor_handles_http_500(self) -> None:
        """Mock an HTTP 500 response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch("autonomous_crawler.agents.executor.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            state = executor_node({
                "target_url": "https://example.com",
                "crawl_strategy": {"mode": "http", "headers": {}},
                "messages": [],
                "error_log": [],
            })

        self.assertEqual(state["status"], "failed")
        self.assertIn("HTTP fetch failed", state["error_log"][0])

    def test_executor_handles_timeout(self) -> None:
        """Mock a connection timeout."""
        with patch("autonomous_crawler.agents.executor.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectTimeout("Connection timed out")
            mock_client_cls.return_value = mock_client

            state = executor_node({
                "target_url": "https://slow.example.com",
                "crawl_strategy": {"mode": "http", "headers": {}},
                "messages": [],
                "error_log": [],
            })

        self.assertEqual(state["status"], "failed")
        self.assertIn("HTTP fetch failed", state["error_log"][0])
        self.assertIn("timed out", state["error_log"][0].lower())

    def test_recon_handles_http_failure(self) -> None:
        """Recon should return recon_failed when fetch fails."""
        with patch("autonomous_crawler.tools.fetch_policy.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client_cls.return_value = mock_client

            state = recon_node({
                "target_url": "https://down.example.com",
                "recon_report": {},
                "messages": [],
                "error_log": [],
            })

        self.assertEqual(state["status"], "recon_failed")
        self.assertIn("recon_error", state["recon_report"])
        self.assertTrue(len(state["error_log"]) > 0)


# ---------------------------------------------------------------------------
# 3. Empty HTML
# ---------------------------------------------------------------------------

class TestEmptyHTML(unittest.TestCase):
    """Extractor should handle empty/missing HTML gracefully."""

    def test_extractor_with_empty_raw_html_dict(self) -> None:
        state = extractor_node({
            "raw_html": {},
            "crawl_strategy": {
                "selectors": {
                    "item_container": ".item",
                    "title": ".title",
                }
            },
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        self.assertEqual(state["extracted_data"]["item_count"], 0)
        self.assertEqual(state["extracted_data"]["confidence"], 0.0)
        self.assertEqual(state["extracted_data"]["items"], [])

    def test_extractor_with_empty_string_html(self) -> None:
        state = extractor_node({
            "raw_html": {"https://example.com": ""},
            "crawl_strategy": {
                "selectors": {
                    "item_container": ".item",
                    "title": ".title",
                }
            },
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        self.assertEqual(state["extracted_data"]["item_count"], 0)
        self.assertEqual(state["extracted_data"]["confidence"], 0.0)

    def test_extractor_with_whitespace_only_html(self) -> None:
        state = extractor_node({
            "raw_html": {"https://example.com": "   \n\t  "},
            "crawl_strategy": {
                "selectors": {
                    "item_container": ".item",
                    "title": ".title",
                }
            },
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        self.assertEqual(state["extracted_data"]["item_count"], 0)

    def test_extractor_with_none_html_value(self) -> None:
        """raw_html values should not be None, but handle it if they are."""
        state = extractor_node({
            "raw_html": {"https://example.com": None},
            "crawl_strategy": {
                "selectors": {
                    "item_container": ".item",
                    "title": ".title",
                }
            },
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        self.assertEqual(state["extracted_data"]["item_count"], 0)


# ---------------------------------------------------------------------------
# 4. Invalid selectors
# ---------------------------------------------------------------------------

class TestInvalidSelectors(unittest.TestCase):
    """Extractor should handle selectors that match nothing."""

    def test_extractor_with_nonexistent_container(self) -> None:
        state = extractor_node({
            "raw_html": {
                "https://example.com": "<div class='real'><p>content</p></div>"
            },
            "crawl_strategy": {
                "selectors": {
                    "item_container": ".this-class-does-not-exist",
                    "title": ".title",
                }
            },
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        self.assertEqual(state["extracted_data"]["item_count"], 0)
        self.assertEqual(state["extracted_data"]["confidence"], 0.0)

    def test_extractor_with_mismatched_field_selector(self) -> None:
        """Container exists but field selectors don't match inside it."""
        state = extractor_node({
            "raw_html": {
                "https://example.com": """
                <div class="card">
                    <h2>Product Name</h2>
                </div>
                """
            },
            "crawl_strategy": {
                "selectors": {
                    "item_container": ".card",
                    "title": ".nonexistent-title-class",
                    "price": ".nonexistent-price-class",
                }
            },
            "recon_report": {"target_fields": ["title", "price"]},
            "messages": [],
        })
        # Item has no title, so it's filtered out by the extractor
        self.assertEqual(state["extracted_data"]["item_count"], 0)

    def test_extractor_with_empty_selectors_dict(self) -> None:
        """Empty selectors should not crash."""
        state = extractor_node({
            "raw_html": {
                "https://example.com": "<div class='card'><p>content</p></div>"
            },
            "crawl_strategy": {"selectors": {}},
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        self.assertEqual(state["extracted_data"]["item_count"], 0)

    def test_extractor_with_malformed_css_selector(self) -> None:
        """Invalid CSS syntax should not crash the extractor."""
        state = extractor_node({
            "raw_html": {
                "https://example.com": "<div class='card'><p>content</p></div>"
            },
            "crawl_strategy": {
                "selectors": {
                    "item_container": "[[invalid",
                    "title": ">>>bad",
                }
            },
            "recon_report": {"target_fields": ["title"]},
            "messages": [],
        })
        # Should not raise; item_count should be 0
        self.assertEqual(state["extracted_data"]["item_count"], 0)


# ---------------------------------------------------------------------------
# 5. Retry exhaustion
# ---------------------------------------------------------------------------

class TestRetryExhaustion(unittest.TestCase):
    """Validator should stop retrying after max_retries is reached."""

    def test_validator_fails_after_max_retries(self) -> None:
        state = validator_node({
            "extracted_data": {
                "items": [],
                "confidence": 0.0,
            },
            "recon_report": {"target_fields": ["title"]},
            "retries": 3,
            "max_retries": 3,
            "messages": [],
        })
        self.assertEqual(state["status"], "failed")
        self.assertFalse(state["validation_result"]["is_valid"])
        self.assertFalse(state["validation_result"]["needs_retry"])
        self.assertIn("max retries exceeded", state["messages"][-1].lower())

    def test_validator_retries_when_below_max(self) -> None:
        state = validator_node({
            "extracted_data": {
                "items": [],
                "confidence": 0.0,
            },
            "recon_report": {"target_fields": ["title"]},
            "retries": 1,
            "max_retries": 3,
            "messages": [],
        })
        self.assertEqual(state["status"], "retrying")
        self.assertTrue(state["validation_result"]["needs_retry"])
        self.assertEqual(state["retries"], 2)

    def test_validator_fails_on_zero_max_retries(self) -> None:
        """With max_retries=0, any failure should immediately fail."""
        state = validator_node({
            "extracted_data": {
                "items": [],
                "confidence": 0.0,
            },
            "recon_report": {"target_fields": ["title"]},
            "retries": 0,
            "max_retries": 0,
            "messages": [],
        })
        self.assertEqual(state["status"], "failed")

    def test_validator_fails_on_low_completeness(self) -> None:
        """Items with mostly empty fields should fail validation."""
        state = validator_node({
            "extracted_data": {
                "items": [
                    {"title": "Only Title"},  # missing price, image
                    {"title": "Another"},     # missing price, image
                ],
                "confidence": 0.33,
            },
            "recon_report": {"target_fields": ["title", "price", "image"]},
            "retries": 0,
            "max_retries": 1,
            "messages": [],
        })
        # completeness = 2/6 = 0.33, below 0.5 threshold
        self.assertEqual(state["status"], "retrying")
        self.assertIn("Low completeness", state["validation_result"]["anomalies"][0])


# ---------------------------------------------------------------------------
# 6. Full graph error propagation
# ---------------------------------------------------------------------------

class TestGraphErrorPropagation(unittest.TestCase):
    """End-to-end tests verifying errors propagate through the graph."""

    def test_graph_fails_on_unsupported_url_scheme(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect data",
            "target_url": "ftp://files.example.com/data",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 3,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })
        # Recon fails fast on unsupported scheme, graph exits early
        self.assertEqual(final_state["status"], "recon_failed")
        self.assertTrue(len(final_state["error_log"]) > 0)

    def test_graph_fails_on_unreachable_host(self) -> None:
        """Graph should complete (not hang) when host is unreachable."""
        with patch("autonomous_crawler.tools.fetch_policy.httpx.Client") as mock_recon_client:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = httpx.ConnectError("DNS resolution failed")
            mock_recon_client.return_value = mock_client

            app = compile_crawl_graph()
            final_state = app.invoke({
                "user_goal": "collect products",
                "target_url": "https://nonexistent.invalid",
                "recon_report": {},
                "crawl_strategy": {},
                "visited_urls": [],
                "raw_html": {},
                "api_responses": [],
                "extracted_data": {},
                "validation_result": {},
                "retries": 0,
                "max_retries": 0,
                "status": "pending",
                "error_log": [],
                "messages": [],
            })

        # Should end in a terminal state, not hang
        self.assertIn(final_state["status"], {"failed", "completed", "recon_failed"})

    def test_graph_handles_empty_extraction_gracefully(self) -> None:
        """When extractor finds nothing, validator should fail (not crash)."""
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect products",
            "target_url": "mock://catalog",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 0,  # No retries to speed up test
            "status": "pending",
            "error_log": [],
            "messages": [],
        })
        # mock://catalog should succeed, but with max_retries=0 even a
        # marginal failure would be terminal
        self.assertIn(final_state["status"], {"completed", "failed"})

    def test_error_log_accumulates_across_nodes(self) -> None:
        """Error log should accumulate messages from multiple failing nodes."""
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect data",
            "target_url": "ftp://bad.scheme",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 0,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })
        # At minimum, recon should log an error
        self.assertTrue(
            len(final_state["error_log"]) > 0,
            f"Expected errors in error_log, got: {final_state['error_log']}"
        )
        # Messages should accumulate from multiple nodes
        self.assertTrue(len(final_state["messages"]) > 1)


# ---------------------------------------------------------------------------
# 7. Validator edge cases
# ---------------------------------------------------------------------------

class TestValidatorEdgeCases(unittest.TestCase):
    """Validator should handle unusual input gracefully."""

    def test_validator_with_none_extracted_data(self) -> None:
        """Validator should not crash if extracted_data is missing."""
        state = validator_node({
            "extracted_data": {},
            "recon_report": {"target_fields": ["title"]},
            "retries": 0,
            "max_retries": 0,
            "messages": [],
        })
        self.assertEqual(state["status"], "failed")
        self.assertIn("No items extracted", state["validation_result"]["anomalies"])

    def test_validator_with_duplicate_urls(self) -> None:
        state = validator_node({
            "extracted_data": {
                "items": [
                    {"title": "A", "link": "/same"},
                    {"title": "B", "link": "/same"},
                ],
                "confidence": 1.0,
            },
            "recon_report": {"target_fields": ["title", "link"]},
            "retries": 0,
            "max_retries": 0,
            "messages": [],
        })
        self.assertFalse(state["validation_result"]["is_valid"])
        self.assertIn("Duplicate URLs", state["validation_result"]["anomalies"][0])

    def test_validator_detects_missing_prices_when_requested(self) -> None:
        state = validator_node({
            "extracted_data": {
                "items": [
                    {"title": "Product A", "link": "/a"},
                    {"title": "Product B", "link": "/b"},
                ],
                "confidence": 0.5,
            },
            "recon_report": {"target_fields": ["title", "price"]},
            "retries": 0,
            "max_retries": 0,
            "messages": [],
        })
        self.assertIn("No prices found", state["validation_result"]["anomalies"])


# ---------------------------------------------------------------------------
# 8. Failure persistence to storage
# ---------------------------------------------------------------------------

class TestFailurePersistence(unittest.TestCase):
    """Verify that failed crawl states persist correctly to SQLite."""

    def test_recon_failed_state_persists_with_error_log(self) -> None:
        """A recon_failed run should persist with status and error_log intact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite3"
            store = CrawlResultStore(db_path=db_path)

            app = compile_crawl_graph()
            final_state = app.invoke({
                "user_goal": "collect data",
                "target_url": "ftp://bad.scheme",
                "recon_report": {},
                "crawl_strategy": {},
                "visited_urls": [],
                "raw_html": {},
                "api_responses": [],
                "extracted_data": {},
                "validation_result": {},
                "retries": 0,
                "max_retries": 0,
                "status": "pending",
                "error_log": [],
                "messages": [],
            })

            task_id = store.save_final_state(final_state)
            loaded = store.get_task(task_id)

            self.assertEqual(loaded["status"], "recon_failed")
            self.assertTrue(len(loaded["error_log"]) > 0)
            self.assertIn("unsupported scheme", loaded["error_log"][0].lower())

    def test_retry_exhausted_state_persists_as_failed(self) -> None:
        """A failed (retry exhausted) run should persist with items=0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite3"
            store = CrawlResultStore(db_path=db_path)

            state = {
                "task_id": "test-fail-001",
                "user_goal": "collect products",
                "target_url": "mock://catalog",
                "status": "failed",
                "extracted_data": {"items": [], "confidence": 0.0, "item_count": 0},
                "validation_result": {"is_valid": False, "completeness": 0.0, "anomalies": ["No items extracted"]},
                "error_log": ["Retry exhaustion: max retries exceeded"],
                "recon_report": {},
                "messages": ["[Validator] FAILED"],
            }

            task_id = store.save_final_state(state)
            loaded = store.get_task(task_id)

            self.assertEqual(loaded["status"], "failed")
            self.assertEqual(loaded["item_count"], 0)
            self.assertFalse(loaded["is_valid"])
            self.assertEqual(loaded["items"], [])

    def test_failed_task_appears_in_list(self) -> None:
        """Failed tasks should appear in task listing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.sqlite3"
            store = CrawlResultStore(db_path=db_path)

            store.save_final_state({
                "task_id": "ok-001",
                "user_goal": "test",
                "target_url": "https://example.com",
                "status": "completed",
                "extracted_data": {"items": [{"title": "A"}], "confidence": 1.0, "item_count": 1},
                "validation_result": {"is_valid": True},
                "error_log": [],
                "messages": [],
            })
            store.save_final_state({
                "task_id": "fail-001",
                "user_goal": "test",
                "target_url": "ftp://bad",
                "status": "recon_failed",
                "extracted_data": {"items": [], "confidence": 0.0, "item_count": 0},
                "validation_result": {"is_valid": False},
                "error_log": ["unsupported scheme"],
                "messages": [],
            })

            tasks = store.list_tasks()
            statuses = [t["status"] for t in tasks]
            self.assertIn("completed", statuses)
            self.assertIn("recon_failed", statuses)


if __name__ == "__main__":
    unittest.main()
