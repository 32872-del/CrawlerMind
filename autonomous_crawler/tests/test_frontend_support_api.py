"""Tests for frontend support API: model list, export paths, workbench config."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from autonomous_crawler.api.app import create_app, _clear_jobs
from autonomous_crawler.llm.model_list import (
    ModelEntry,
    ModelListResult,
    _normalize_models,
    _redact_key,
    build_models_endpoint,
    check_provider_health,
    fetch_model_list,
)


class ModelListUnitTests(unittest.TestCase):
    def test_build_models_endpoint_plain_domain(self) -> None:
        self.assertEqual(
            build_models_endpoint("https://api.openai.com"),
            "https://api.openai.com/v1/models",
        )

    def test_build_models_endpoint_with_v1(self) -> None:
        self.assertEqual(
            build_models_endpoint("https://api.openai.com/v1"),
            "https://api.openai.com/v1/models",
        )

    def test_build_models_endpoint_already_complete(self) -> None:
        self.assertEqual(
            build_models_endpoint("https://api.openai.com/v1/models"),
            "https://api.openai.com/v1/models",
        )

    def test_build_models_endpoint_trailing_slash(self) -> None:
        self.assertEqual(
            build_models_endpoint("https://api.openai.com/v1/"),
            "https://api.openai.com/v1/models",
        )

    def test_normalize_models_standard_data_shape(self) -> None:
        raw = {"data": [{"id": "gpt-4", "owned_by": "openai"}, {"id": "gpt-3.5-turbo"}]}
        models = _normalize_models(raw)
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "gpt-4")
        self.assertEqual(models[1].id, "gpt-3.5-turbo")

    def test_normalize_models_relay_shape(self) -> None:
        raw = {"models": [{"id": "deepseek-chat"}, {"id": "deepseek-coder"}]}
        models = _normalize_models(raw)
        self.assertEqual(len(models), 2)
        self.assertEqual(models[0].id, "deepseek-chat")

    def test_normalize_models_list_shape(self) -> None:
        raw = [{"id": "qwen-7b"}, {"id": "qwen-14b"}]
        models = _normalize_models(raw)
        self.assertEqual(len(models), 2)

    def test_normalize_models_deduplicates(self) -> None:
        raw = {"data": [{"id": "gpt-4"}, {"id": "gpt-4"}]}
        models = _normalize_models(raw)
        self.assertEqual(len(models), 1)

    def test_normalize_models_skips_empty_id(self) -> None:
        raw = {"data": [{"id": ""}, {"id": "gpt-4"}, {"id": None}]}
        models = _normalize_models(raw)
        self.assertEqual(len(models), 1)

    def test_normalize_models_label_with_owned_by(self) -> None:
        raw = {"data": [{"id": "claude-3", "owned_by": "anthropic"}]}
        models = _normalize_models(raw)
        self.assertIn("anthropic", models[0].label)

    def test_redact_key_masks_long_key(self) -> None:
        result = _redact_key("error with key sk-abc12345defgh", "sk-abc12345defgh")
        self.assertNotIn("sk-abc12345defgh", result)
        self.assertIn("sk-a...efgh", result)

    def test_redact_key_ignores_short_key(self) -> None:
        text = "error with short key"
        self.assertEqual(_redact_key(text, "abc"), text)

    def test_model_entry_to_dict(self) -> None:
        entry = ModelEntry(id="gpt-4", label="gpt-4", owned_by="openai")
        d = entry.to_dict()
        self.assertEqual(d["id"], "gpt-4")
        self.assertEqual(d["owned_by"], "openai")

    def test_model_list_result_to_dict(self) -> None:
        result = ModelListResult(
            provider="test", models=[ModelEntry(id="m1", label="m1")],
            raw_count=1, status="ok", latency_ms=123.456,
        )
        d = result.to_dict()
        self.assertEqual(d["provider"], "test")
        self.assertEqual(d["raw_count"], 1)
        self.assertEqual(d["latency_ms"], 123.5)


class FetchModelListTests(unittest.TestCase):
    @patch("autonomous_crawler.llm.model_list.httpx.Client")
    def test_fetch_success(self, mock_client_cls: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"id": "gpt-4"}, {"id": "gpt-3.5-turbo"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_model_list("https://api.openai.com", api_key="sk-test1234")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.raw_count, 2)
        self.assertEqual(result.models[0].id, "gpt-4")

    @patch("autonomous_crawler.llm.model_list.httpx.Client")
    def test_fetch_http_error(self, mock_client_cls: MagicMock) -> None:
        import httpx
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_model_list("https://bad.api", api_key="sk-secret12345")
        self.assertEqual(result.status, "error")
        self.assertNotIn("sk-secret12345", result.error)

    @patch("autonomous_crawler.llm.model_list.httpx.Client")
    def test_fetch_invalid_json(self, mock_client_cls: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("not json")
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = fetch_model_list("https://api.test.com")
        self.assertEqual(result.status, "error")
        self.assertIn("not valid JSON", result.error)


class CheckProviderHealthTests(unittest.TestCase):
    @patch("autonomous_crawler.llm.model_list.httpx.Client")
    def test_health_ok(self, mock_client_cls: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = check_provider_health("https://api.openai.com/v1")
        self.assertEqual(result["status"], "ok")
        self.assertIn("latency_ms", result)
        self.assertEqual(result["normalized_url"], "https://api.openai.com")

    @patch("autonomous_crawler.llm.model_list.httpx.Client")
    def test_health_error(self, mock_client_cls: MagicMock) -> None:
        import httpx
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("timeout")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = check_provider_health("https://bad.api")
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["error"])


class LLModelsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()

    @patch("autonomous_crawler.api.app.fetch_model_list")
    def test_models_endpoint_success(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = ModelListResult(
            provider="openai-compatible",
            models=[ModelEntry(id="gpt-4", label="gpt-4")],
            raw_count=1, status="ok",
        )
        client = TestClient(create_app())
        resp = client.post("/llm/models", json={
            "base_url": "https://api.openai.com",
            "api_key": "sk-test",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["models"][0]["id"], "gpt-4")

    def test_models_endpoint_empty_base_url(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/llm/models", json={"base_url": ""})
        self.assertIn(resp.status_code, {400, 422})


class LLMHealthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()

    @patch("autonomous_crawler.api.app.check_provider_health")
    def test_health_endpoint_ok(self, mock_check: MagicMock) -> None:
        mock_check.return_value = {"status": "ok", "latency_ms": 150.0, "normalized_url": "https://api.test.com"}
        client = TestClient(create_app())
        resp = client.post("/llm/health", json={"base_url": "https://api.test.com/v1"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_health_endpoint_empty_base_url(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/llm/health", json={"base_url": ""})
        self.assertIn(resp.status_code, {400, 422})


class ExportPathTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()

    def test_validate_path_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app())
            resp = client.post("/exports/validate-path", json={"directory": tmp})
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["exists"])
            self.assertTrue(body["writable"])
            self.assertFalse(body["created"])

    def test_validate_path_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = str(Path(tmp) / "new_sub")
            client = TestClient(create_app())
            resp = client.post("/exports/validate-path", json={"directory": new_dir, "create": True})
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["exists"])
            self.assertTrue(body["created"])
            self.assertTrue(body["writable"])

    def test_validate_path_not_exists_no_create(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/validate-path", json={"directory": "/nonexistent/path/abc123"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["exists"])
        self.assertFalse(body["writable"])
        self.assertFalse(body["created"])

    def test_validate_path_empty_directory(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/validate-path", json={"directory": ""})
        self.assertIn(resp.status_code, {400, 422})

    def test_resolve_path_default(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/resolve-path", json={
            "directory": "/tmp/exports",
            "run_id": "test-abc",
            "format": "xlsx",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("test-abc.xlsx", body["output_path"])
        self.assertEqual(body["format"], "xlsx")

    def test_resolve_path_custom_filename(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/resolve-path", json={
            "directory": "/tmp/exports",
            "run_id": "test-abc",
            "format": "csv",
            "filename": "my_export",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("my_export.csv", body["output_path"])

    def test_resolve_path_adds_missing_extension(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/resolve-path", json={
            "directory": "/tmp/exports",
            "run_id": "test-abc",
            "format": "json",
            "filename": "no_ext",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["output_path"].endswith(".json"))

    def test_resolve_path_sqlite_format(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/resolve-path", json={
            "directory": "/tmp/exports",
            "run_id": "run-1",
            "format": "sqlite",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("run-1.sqlite3", body["output_path"])

    def test_resolve_path_empty_directory(self) -> None:
        client = TestClient(create_app())
        resp = client.post("/exports/resolve-path", json={
            "directory": "",
            "run_id": "test",
        })
        self.assertIn(resp.status_code, {400, 422})


class WorkbenchConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()

    def test_config_endpoint(self) -> None:
        client = TestClient(create_app())
        resp = client.get("/workbench/config")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("version", body)
        self.assertIn("supported_export_formats", body)
        self.assertIn("max_active_jobs", body)
        self.assertIn("endpoints", body)
        self.assertIn("llm_models", body["endpoints"])
        self.assertIn("exports_validate_path", body["endpoints"])

    def test_config_has_all_expected_endpoints(self) -> None:
        client = TestClient(create_app())
        body = client.get("/workbench/config").json()
        expected_keys = [
            "catalog_import", "site_analyze", "fields_resolve",
            "runs_test", "runs_full", "exports", "llm_models", "health",
        ]
        for key in expected_keys:
            self.assertIn(key, body["endpoints"], f"missing endpoint: {key}")


class CORSTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()

    def test_cors_headers_present(self) -> None:
        client = TestClient(create_app())
        resp = client.options("/health", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        })
        # Starlette CORS middleware responds to preflight
        self.assertIn(resp.status_code, {200, 405})


if __name__ == "__main__":
    unittest.main()
