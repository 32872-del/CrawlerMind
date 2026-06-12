# E2E Site List Training Report - 2026-06-02
Generated: 2026-06-02 11:38:06

## Overview
- Total sites: 13
- Pass (records > 0): 4
- Empty (completed, 0 records): 6
- Failed: 3
- Total records extracted: 60
- Browser fallbacks (no Playwright): 13
- API auto-detected: 1

## ECOMMERCE (6 sites, 3 passed, 58 records)

### ✅ ecommerce_dummyjson
- URL: https://dummyjson.com/products
- Scenario: json_api, Difficulty: easy
- Records: 30, Status: completed, Elapsed: 13.95s
- API: auto-detected ✅
- Browser: fallback to static (Playwright not installed)

### ⚠️ ecommerce_jsonplaceholder
- URL: https://jsonplaceholder.typicode.com/posts
- Scenario: json_api, Difficulty: easy
- Records: 0, Status: completed, Elapsed: 23.7s
- Browser: fallback to static (Playwright not installed)

### ✅ ecommerce_scrapingcourse
- URL: https://www.scrapingcourse.com/ecommerce/
- Scenario: ssr, Difficulty: medium
- Records: 16, Status: completed, Elapsed: 29.31s
- Browser: fallback to static (Playwright not installed)

### ⚠️ ecommerce_scrapingcourse_pagination
- URL: https://www.scrapingcourse.com/pagination/
- Scenario: pagination, Difficulty: medium
- Records: 0, Status: completed, Elapsed: 67.89s
- Browser: fallback to static (Playwright not installed)

### ✅ ecommerce_marksandspencer
- URL: https://www.marksandspencer.com/
- Scenario: real_ecommerce, Difficulty: hard
- Records: 12, Status: completed, Elapsed: 19.92s
- Browser: fallback to static (Playwright not installed)

### ❌ ecommerce_superdry
- URL: https://www.superdry.com/
- Scenario: real_ecommerce, Difficulty: hard
- Records: 0, Status: paused, Elapsed: 21.43s
- Browser: fallback to static (Playwright not installed)

## API (1 sites, 0 passed, 0 records)

### ⚠️ api_hackernews
- URL: https://hacker-news.firebaseio.com/v0/topstories.json
- Scenario: json_api, Difficulty: easy
- Records: 0, Status: completed, Elapsed: 23.25s
- Browser: fallback to static (Playwright not installed)

## CONTENT (2 sites, 0 passed, 0 records)

### ⚠️ content_quotes_toscrape
- URL: https://quotes.toscrape.com/
- Scenario: ssr, Difficulty: easy
- Records: 0, Status: completed, Elapsed: 26.77s
- Browser: fallback to static (Playwright not installed)

### ❌ content_douban_top250
- URL: https://movie.douban.com/top250
- Scenario: ssr_pagination, Difficulty: medium
- Records: 0, Status: paused, Elapsed: 6.36s
- Browser: fallback to static (Playwright not installed)

## SPA (1 sites, 0 passed, 0 records)

### ⚠️ spa_nike
- URL: https://www.nike.com/
- Scenario: spa_browser, Difficulty: hard
- Records: 0, Status: completed, Elapsed: 10.18s
- Browser: fallback to static (Playwright not installed)

## GRAPHQL (1 sites, 0 passed, 0 records)

### ⚠️ graphql_countries
- URL: https://countries.trevorblades.com/
- Scenario: graphql, Difficulty: medium
- Records: 0, Status: completed, Elapsed: 38.39s
- Browser: fallback to static (Playwright not installed)

## DIAGNOSIS (2 sites, 1 passed, 2 records)

### ✅ diagnosis_scrapfly_fingerprint
- URL: https://scrapfly.io/web-scraping-tools/browser-fingerprint
- Scenario: protected, Difficulty: hard
- Records: 2, Status: completed, Elapsed: 92.94s
- Browser: fallback to static (Playwright not installed)
- Mode: diagnosis only

### ❌ diagnosis_cloudflare_challenge
- URL: https://scrapingcourse.com/cloudflare-challenge
- Scenario: protected, Difficulty: hard
- Records: 0, Status: paused, Elapsed: 62.76s
- Browser: fallback to static (Playwright not installed)
- Mode: diagnosis only
- Diagnosis: critical
- Repair plan: ['inspect_access', 'probe_fields', 'evaluate_quality', 'repair_selectors', 'adjust_runtime', 'prepare_rerun']

## Summary Table

| Site | Category | Records | Quality | Elapsed |
|------|----------|---------|---------|---------|
| ecommerce_dummyjson | ecommerce | 30 | ✅ pass | 13.95s |
| ecommerce_jsonplaceholder | ecommerce | 0 | ⚠️ empty | 23.7s |
| ecommerce_scrapingcourse | ecommerce | 16 | ✅ pass | 29.31s |
| ecommerce_scrapingcourse_pagination | ecommerce | 0 | ⚠️ empty | 67.89s |
| ecommerce_marksandspencer | ecommerce | 12 | ✅ pass | 19.92s |
| ecommerce_superdry | ecommerce | 0 | ❌ fail | 21.43s |
| api_hackernews | api | 0 | ⚠️ empty | 23.25s |
| content_quotes_toscrape | content | 0 | ⚠️ empty | 26.77s |
| content_douban_top250 | content | 0 | ❌ fail | 6.36s |
| spa_nike | spa | 0 | ⚠️ empty | 10.18s |
| graphql_countries | graphql | 0 | ⚠️ empty | 38.39s |
| diagnosis_scrapfly_fingerprint | diagnosis | 2 | ✅ pass | 92.94s |
| diagnosis_cloudflare_challenge | diagnosis | 0 | ❌ fail | 62.76s |
