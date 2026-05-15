# Handoff: VisualRecon Foundation

Date: 2026-05-14

Employee: `LLM-2026-000`

## What Changed

Added `autonomous_crawler/tools/visual_recon.py` and wired it into
`NativeBrowserRuntime` behind `browser_config.visual_recon=true`.

The current implementation is a foundation:

- screenshot existence/file health
- image type and dimensions for common formats
- layout summary
- optional OCR provider protocol
- normalized visual recon report

## How To Use

Set browser config:

```python
{
    "screenshot": True,
    "visual_recon": True,
}
```

When a screenshot artifact is produced, `response.engine_result["visual_recon"]`
contains visual evidence.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_visual_recon autonomous_crawler.tests.test_native_browser_runtime -v
```

## Known Gaps

- No bundled OCR engine yet.
- No DOM bounding-box alignment yet.
- Visual recon is not yet consumed by Strategy or AntiBotReport.
