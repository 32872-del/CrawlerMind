# 2026-05-09 Real-Site Training Round 4

## Summary

Round 4 focused on public JSON APIs and one browser-network observation probe.
The training started with 2/5 scenarios passing. Two general defects were found
and fixed during the session:

- JSON payloads containing words like `captcha` could be misclassified as
  anti-bot pages.
- Common API response shapes such as `hits` and `quotes` were not extracted.

After the first fixes, 4/5 scenarios passed. A follow-up timing and API replay
fix closed the remaining dynamic-page gap: the HN Algolia SPA now completes by
observing its public Algolia XHR and replaying the JSON POST request.

## Scenarios

| Scenario | Target | Result | Items | Notes |
|---|---|---:|---:|---|
| DummyJSON products public API | `https://dummyjson.com/products?limit=10` | completed | 10 | Product API with price, rating, image, summary normalization |
| Hacker News Algolia front page API | `https://hn.algolia.com/api/v1/search_by_date?tags=front_page` | completed | 10 | Fixed JSON anti-bot false positive and `hits` extraction |
| GitHub CPython issues API | `https://api.github.com/repos/python/cpython/issues?per_page=10` | completed | 10 | GitHub `html_url` and `comments` normalization |
| Quotes to Scrape API | `https://quotes.toscrape.com/api/quotes?page=1` | completed | 10 | Fixed `quotes` extraction and quote text normalization |
| HN Algolia browser-network observation | `https://hn.algolia.com/?dateRange=all&page=0&prefix=false&query=&sort=byPopularity&type=story` | completed | 10 | Observed Algolia XHR, selected `api_intercept`, replayed JSON POST body |

Raw training output:

```text
dev_logs/training/2026-05-09_real_site_training_round4.json
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

The HN Algolia browser-network observation scenario initially failed because
the observer returned too early and because Algolia's JSON POST body contains a
plain `query` field that was incorrectly treated as GraphQL. Both issues were
fixed later on 2026-05-09.

Resolved follow-up:

1. Added a real browser-network smoke fixture with controlled XHR so the
   observer proves full end-to-end candidate discovery outside mocks.
   Completed later on 2026-05-09 in
   `autonomous_crawler/tests/test_real_browser_smoke.py`.
2. Changed network observation timing to default to `networkidle` and added
   optional `render_time_ms`.
3. Tightened GraphQL detection so Algolia-style JSON POST search requests stay
   classified as `json`.
4. Preserved JSON POST bodies on API candidates and replayed them in Executor.
5. Retried the public HN Algolia scenario successfully:

```text
status=completed
mode=api_intercept
method=api_json
items=10
confidence=1.0
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_access_diagnostics autonomous_crawler.tests.test_api_intercept -v
Ran 28 tests
OK

python run_training_round4.py
5 completed, 0 failed
```
