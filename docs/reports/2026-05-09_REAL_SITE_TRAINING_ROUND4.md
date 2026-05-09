# 2026-05-09 Real-Site Training Round 4

## Summary

Round 4 focused on public JSON APIs and one browser-network observation probe.
The training started with 2/5 scenarios passing. Two general defects were found
and fixed during the session:

- JSON payloads containing words like `captcha` could be misclassified as
  anti-bot pages.
- Common API response shapes such as `hits` and `quotes` were not extracted.

After fixes, 4/5 scenarios passed. The remaining failure is a real dynamic-page
browser/network-observation gap, not a direct JSON API gap.

## Scenarios

| Scenario | Target | Result | Items | Notes |
|---|---|---:|---:|---|
| DummyJSON products public API | `https://dummyjson.com/products?limit=10` | completed | 10 | Product API with price, rating, image, summary normalization |
| Hacker News Algolia front page API | `https://hn.algolia.com/api/v1/search_by_date?tags=front_page` | completed | 10 | Fixed JSON anti-bot false positive and `hits` extraction |
| GitHub CPython issues API | `https://api.github.com/repos/python/cpython/issues?per_page=10` | completed | 10 | GitHub `html_url` and `comments` normalization |
| Quotes to Scrape API | `https://quotes.toscrape.com/api/quotes?page=1` | completed | 10 | Fixed `quotes` extraction and quote text normalization |
| HN Algolia browser-network observation | `https://hn.algolia.com/?dateRange=all&page=0&prefix=false&query=&sort=byPopularity&type=story` | failed | 0 | Browser rendered page observed only document response; no API candidate surfaced |

Raw training output:

```text
dev_logs/2026-05-09_real_site_training_round4.json
```

## Code Improvements From Training

- `extract_records_from_json()` now handles `hits` and `quotes` list keys.
- `normalize_api_records()` now maps:
  - `points`, `num_comments`, `comments`, and `rating` to `hot_score`
  - `description`, `text`, `body`, and `story_text` to `summary`
  - `html_url` to `link`
  - plain `text` to `title` when no title/name exists
- `detect_challenge()` and `detect_anti_bot()` no longer treat JSON payload
  body text as HTML challenge evidence.

## Remaining Failure Analysis

The HN Algolia browser-network observation scenario failed because the current
observer captured only the document response and produced zero API candidates.
The page rendered some DOM, but current DOM selector inference did not produce
extractable story items.

Likely next work:

1. Add a real browser-network smoke fixture with controlled XHR so the
   observer proves full end-to-end candidate discovery outside mocks.
   Completed later on 2026-05-09 in
   `autonomous_crawler/tests/test_real_browser_smoke.py`.
2. Enhance browser observation timing to wait for network idle and/or capture
   request URLs triggered after hydration.
3. Add rendered DOM selector training for modern SPA list layouts.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_api_intercept -v
Ran 28 tests
OK

python run_training_round4.py
4 completed, 1 failed
```
