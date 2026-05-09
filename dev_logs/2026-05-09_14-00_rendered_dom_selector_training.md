# 2026-05-09 14:00 - Rendered DOM Selector Training

## Goal

Improve Crawler-Mind's DOM selector inference for modern SPA/SSR list pages,
specifically HN Algolia-style `article/list/card` structures where items render
but cannot be extracted.

Employee: LLM-2026-001 / Worker Alpha
Assignment: Rendered DOM Selector Training

## Changes

### Modified files

- `autonomous_crawler/tools/html_recon.py`:
  - Added `MOCK_HN_ALGOLIA_HTML` fixture: 3 story items with CSS module class
    names (`Story_storyContainer`, `Story_titleLink`, `Story_meta`), nested
    link/title structures, `data-testid` attributes, and bare-text score/metadata
    nodes.
  - Added `MOCK_HN_ALGOLIA_VARIANT_HTML` fixture: 3 story items with explicit
    `<span class="Story_score">` elements and `<time datetime="...">` elements.
  - Registered `mock://hn-algolia` and `mock://hn-algolia-variant` in both
    `fetch_html()` and `_mock_best_fetch()`.
  - Added `POINTS_RE` pattern for matching "123 points", "45 votes", etc.
  - Improved `_infer_field_selectors`:
    - Title: added `[data-testid*=title]` fallback.
    - Date: added `<time[datetime]>` detection (returns `selector@datetime`).
    - Date: added `[class*=time], [class*=date]` fallback.
    - Summary: added `[data-testid*=summary], [data-testid*=desc]` fallback.
  - Improved `_find_primary_link`: added `a[data-testid*=link][href]` and
    `a[data-testid*=title][href]` selectors.
  - Improved `_find_score_element`: added `data-testid` check for score/points,
    `[class*=score/points]` class check, and `POINTS_RE` text matching.
  - Updated `_score_container`: added `+1` for `date` field.

### New files

- `autonomous_crawler/tests/test_hn_algolia_dom.py`:
  - 15 tests across 5 test classes covering HN Algolia fixtures, field selectors,
    existing fixture regression, and POINTS_RE pattern.

### Not modified

- No changes to agents/, api/, storage/, llm/, workflows/.
- No changes to `browser_network_observer.py` (per assignment constraint).
- No changes to FastAPI/LLM/storage.

## Tests

```text
python -m unittest autonomous_crawler.tests.test_hn_algolia_dom -v
Ran 15 tests in 0.062s OK

python -m unittest discover -s autonomous_crawler/tests
Ran 336 tests (skipped=4)
OK
```

Compile check: OK.

## What Was Learned

1. Modern SPA frameworks use CSS module class names like `Story_storyContainer`
   which the existing `_stable_selector` already handles correctly (underscores
   and mixed case pass `_is_safe_css_class`).

2. The real gap was in field inference: bare-text nodes like "123 points by user1"
   don't match dedicated `<span>` elements, so `_find_score_element` missed them.
   The `POINTS_RE` pattern now catches these.

3. `data-testid` attributes are a reliable signal for modern SPAs. Adding
   `[data-testid*=title]` and `a[data-testid*=link]` as fallback selectors
   improves coverage without overfitting.

4. `<time datetime="...">` elements are a semantic HTML5 signal for dates that
   the previous code didn't detect at all.

## Known Limitations

- Bare-text score detection returns the parent meta div rather than a
  purpose-built element, which may include extra text. Acceptable for scoring
  purposes.
- No pagination detection improvements in this round.
- The fixture is simplified; real HN Algolia pages have more complex nested
  structures and dynamic class names.
