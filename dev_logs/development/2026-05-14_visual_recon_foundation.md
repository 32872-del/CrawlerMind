# 2026-05-14 VisualRecon Foundation

Supervisor: `LLM-2026-000`

Track: `CAP-5.2`

## Summary

Added the first CLM-native visual recon foundation without blocking the current
Scrapling absorption workers.

This is intentionally a small backend capability, not a full OCR product yet:
browser screenshots can now produce normalized visual evidence, and optional
OCR providers can plug in through a simple protocol.

## Files Changed

- `autonomous_crawler/tools/visual_recon.py`
- `autonomous_crawler/runtime/native_browser.py`
- `autonomous_crawler/tests/test_visual_recon.py`
- `autonomous_crawler/tests/test_native_browser_runtime.py`

## Behavior

- `analyze_screenshot()` inspects a screenshot artifact.
- It reports:
  - image type
  - file size
  - PNG/GIF/JPEG dimensions when available
  - orientation
  - viewport class
  - bytes-per-pixel
  - optional OCR provider status/text preview/confidence
  - findings such as missing file, empty file, tiny screenshot, unknown format,
    and OCR provider failure
- `analyze_runtime_artifacts()` filters runtime artifacts and analyzes only
  screenshot artifacts.
- `NativeBrowserRuntime` now supports opt-in
  `browser_config.visual_recon=true`. When enabled with screenshot capture, it
  stores visual evidence under `engine_result.visual_recon`.

## Design Notes

- No heavyweight OCR dependency is required.
- The OCR path is provider-based and optional.
- Existing browser behavior remains unchanged unless `visual_recon=true`.
- Python 3.13 compatibility: avoided deprecated/removed `imghdr`.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_visual_recon autonomous_crawler.tests.test_native_browser_runtime -v
Ran 17 tests
OK

python -m compileall autonomous_crawler\tools\visual_recon.py autonomous_crawler\runtime\native_browser.py autonomous_crawler\tests\test_visual_recon.py autonomous_crawler\tests\test_native_browser_runtime.py
OK
```

## Next

- Add a real OCR provider adapter once dependencies are selected.
- Add screenshot-to-DOM alignment using browser element bounding boxes.
- Use visual recon evidence in AntiBotReport and StrategyEvidenceReport.
