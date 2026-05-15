from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.runtime import RuntimeArtifact
from autonomous_crawler.tools.visual_recon import analyze_runtime_artifacts, analyze_screenshot


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeOcrProvider:
    name = "fake"

    def extract_text(self, image_path: str) -> dict:
        return {"text": "Product title\n$19.99", "confidence": 0.91}


class FailingOcrProvider:
    name = "failing"

    def extract_text(self, image_path: str) -> str:
        raise RuntimeError("ocr boom")


class VisualReconTests(unittest.TestCase):
    def test_missing_screenshot_returns_failure(self) -> None:
        report = analyze_screenshot("missing-file.png")

        self.assertEqual(report.status, "failed")
        self.assertEqual(report.findings[0].code, "screenshot_missing")

    def test_png_dimensions_and_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shot.png"
            path.write_bytes(PNG_1X1)

            report = analyze_screenshot(path)

        data = report.to_dict()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["image_kind"], "png")
        self.assertEqual(data["width"], 1)
        self.assertEqual(data["height"], 1)
        self.assertEqual(data["layout"]["viewport_class"], "mobile")
        self.assertEqual(data["ocr"]["status"], "unavailable")

    def test_ocr_provider_output_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shot.png"
            path.write_bytes(PNG_1X1)

            report = analyze_screenshot(path, ocr_provider=FakeOcrProvider())

        data = report.to_dict()
        self.assertEqual(data["ocr"]["status"], "ok")
        self.assertEqual(data["ocr"]["provider"], "fake")
        self.assertIn("Product title", data["ocr"]["text_preview"])
        self.assertTrue(data["layout"]["has_visible_text_evidence"])

    def test_ocr_provider_failure_is_evidence_not_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shot.png"
            path.write_bytes(PNG_1X1)

            report = analyze_screenshot(path, ocr_provider=FailingOcrProvider())

        data = report.to_dict()
        self.assertEqual(data["ocr"]["status"], "failed")
        self.assertIn("ocr_provider_failed", {item["code"] for item in data["findings"]})

    def test_analyze_runtime_artifacts_filters_screenshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shot.png"
            path.write_bytes(PNG_1X1)
            artifacts = [
                RuntimeArtifact(kind="storage_state", path=str(Path(tmp) / "state.json")),
                RuntimeArtifact(kind="screenshot", path=str(path), url="https://example.com"),
            ]

            reports = analyze_runtime_artifacts(artifacts)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["image_kind"], "png")


if __name__ == "__main__":
    unittest.main()
