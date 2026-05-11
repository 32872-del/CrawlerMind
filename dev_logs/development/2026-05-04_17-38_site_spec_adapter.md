# Dev Log - 2026-05-04 17:38 - spider_Uvex Site Spec Adapter

## Goal

Create a bridge from Agent strategy output to spider_Uvex-compatible
`site_spec` drafts.

## What changed

### 1. Added site_spec adapter

- Added `autonomous_crawler/tools/site_spec_adapter.py`.
- Converts:
  - `user_goal`
  - `target_url`
  - `recon_report`
  - inferred selectors
  - strategy mode
- Into a spider_Uvex-style `site_spec` draft.

### 2. Strategy now emits `site_spec_draft`

- Updated `autonomous_crawler/agents/strategy.py`.
- Every strategy now includes:

```json
{
  "site_spec_draft": {
    "version": "1.0",
    "site": "...",
    "mode": "curl_cffi",
    "start_urls": [{"url": "..."}],
    "list": {
      "item_container": "...",
      "item_link": "..."
    },
    "detail": {
      "title": "...",
      "price": "...",
      "image_src": "..."
    }
  }
}
```

### 3. Added tests

- `test_strategy_uses_recon_selectors` now checks that `site_spec_draft` is
  produced.
- Added `test_site_spec_adapter_builds_spider_uvex_draft`.
- Full graph test checks the strategy carries a draft site spec.

## Verification

```text
python -m unittest discover autonomous_crawler\tests
Ran 7 tests
OK

python -m compileall autonomous_crawler run_skeleton.py
OK

python run_skeleton.py "<Chinese product title and price goal>" mock://catalog
Final Status: completed
Extracted 2 items
site_spec_draft generated
```

## Current limitation

This is a draft adapter. When only a list page is known, `detail` selectors are
copied from inferred card selectors. For production sites, the next refinement
should sample one or more detail pages and vote on detail-field selectors.

## Next recommended step

Add an executor path for `engine="spider_uvex"` or a separate tool wrapper that:

1. Validates `site_spec_draft`.
2. Exports it to `F:\datawork\spider_Uvex\site_specs`.
3. Runs `ConfigSpider`.
4. Reads the generated SQLite goods table back into Agent state.
