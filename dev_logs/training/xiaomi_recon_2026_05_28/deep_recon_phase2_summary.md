# Deep Recon Phase 2 Summary — 10 Target Sites

**Generated**: 2026-05-29
**Phase**: Deep Recon Phase 2 (from Round 1 侦察地图)
**Target**: Upgrade Round 1 intelligence into CLM-executable or semi-executable training assets

## Aggregate Stats

| Metric | Value |
|--------|-------|
| Total Sites | 10 |
| Suitable for CLM | 3 (Superdry, Nike, M&S) |
| Partially Suitable | 2 (Otto, Coolblue) |
| Not Suitable | 5 (Aboutyou, Reiss, Next, Guess, Mango) |
| Avg Confidence | 0.42 |

## Site-by-Site Results

| # | Site | Platform | Verdict | Confidence | Key Data Source | Products Found | Blocking Issue |
|---|------|----------|---------|------------|-----------------|----------------|----------------|
| 1 | superdry.com | Demandware | **Suitable** | 0.85 | GTM data-gtm attrs | 48 | None |
| 2 | nike.com | Next.js + Nike API | **Suitable** | 0.80 | __NEXT_DATA__ Wall | 78 (947 total) | SPA requires browser |
| 3 | marksandspencer.com | Next.js + GraphQL | **Suitable** | 0.85 | __NEXT_DATA__ GQL | 48 | GraphQL auth needed |
| 4 | otto.de | Proprietary Svelte | Partial | 0.65 | reptile-tile HTML | 120 | API returns 401 |
| 5 | coolblue.nl | Next.js SPA | Partial | 0.50 | JSON-LD on PDP | 0 (listing) | SPA - no listing data |
| 6 | mango.com | Proprietary | Not Suitable | 0.15 | None | 0 | Geo-redirect, data not in HTML |
| 7 | guess.com | Demandware + Algolia | Not Suitable | 0.10 | None | 0 | Geo-redirect to Spain |
| 8 | aboutyou.de | Proprietary SPA | Not Suitable | 0.10 | None | 0 | Pure SPA, API 404 |
| 9 | reiss.com | Next Group CMS | Not Suitable | 0.05 | None | 0 | 403 on all /shop/* |
| 10 | next.co.uk | Next Group CMS | Not Suitable | 0.05 | None | 0 | 403 on all /shop/* |

## Tier 1: Fully Suitable Sites (3)

### 1. superdry.com — Demandware GTM Gold Mine
- **Data Source**: `data-gtm` attributes on product tiles contain complete JSON
- **Fields Available**: title, price, color, brand, category, season, SKU, original price
- **Sample**: 48 products with full GTM data
- **URL Pattern**: `/{category}/{slug}-{product_id}.html`
- **Image CDN**: `images.laguna-live.sd.co.uk`
- **Approach**: `requests` mode + regex extraction of `data-gtm` JSON

### 2. nike.com — __NEXT_DATA__ with API Pagination
- **Data Source**: `__NEXT_DATA__` → `props.pageProps.initialState.Wall.productGroupings`
- **Fields Available**: title, subtitle, price, currency, color description, product code, product type, image URL, detail URL
- **Sample**: 78 products per page, 947 total across 40 pages
- **URL Pattern**: `/gb/t/{slug}/{styleColor}`
- **API**: `/discover/product_wall/v1/marketplace/GB/...?anchor=N&count=24`
- **Approach**: `browser` mode + __NEXT_DATA__ JSON extraction

### 3. marksandspencer.com — GraphQL in __NEXT_DATA__
- **Data Source**: `__NEXT_DATA__` → `serverSideGqlResponseFed.productPageData.search.results`
- **Fields Available**: title, brand, price, currency, SEO path, variant size, variant SKU, image asset ID
- **Sample**: 48 products with full variant data
- **URL Pattern**: `/{seo-slug}/p/clp{product_id}?color={color}`
- **Approach**: `browser` mode + __NEXT_DATA__ JSON extraction

## Tier 2: Partially Suitable Sites (2)

### 4. otto.de — HTML Tile Parsing
- **Data Source**: `reptile-tile-item` HTML elements with data attributes
- **Fields Available**: product_id, variation_id, name (alt text), price, image
- **Sample**: 120 product tiles
- **Limitation**: API returns 401, product names only in alt text
- **URL Pattern**: `/p/{slug}-{product_id}/`
- **Approach**: `browser` mode + HTML parsing of reptile-tile structure

### 5. coolblue.nl — JSON-LD on Detail Pages Only
- **Data Source**: JSON-LD Product schema on product detail pages
- **Fields Available**: title, brand, price, currency, SKU, image, description
- **Limitation**: Listing pages are SPAs with no product data; need to discover product URLs first
- **URL Pattern**: `/product/{product_id}/{slug}.html`
- **Approach**: Sitemap/API for URL discovery + detail page JSON-LD extraction

## Tier 3: Not Suitable Sites (5)

### 6. mango.com
- **Issue**: Product data not in initial HTML, geo-redirect to Spanish
- **API Found**: `api.shop.mango.com` (not tested)
- **Fix**: Test API endpoints with locale cookies

### 7. guess.com
- **Issue**: Geo-redirected to Spanish locale, empty product grid
- **Platform**: Demandware + Algolia search
- **Fix**: Use US proxy or locale override cookies

### 8. aboutyou.de
- **Issue**: Pure SPA, no product data in HTML, API returns 404
- **Fix**: Need API authentication or advanced browser automation

### 9. reiss.com
- **Issue**: 403 on all /shop/* URLs
- **Platform**: Next Group CMS (shared with next.co.uk)
- **Fix**: Proxy rotation or cookie-based access

### 10. next.co.uk
- **Issue**: 403 on all /shop/* URLs
- **Platform**: Next Group CMS (shared with reiss.com)
- **Fix**: Same as reiss.com

## Key Technical Findings

### Data Extraction Patterns Discovered

| Pattern | Sites | Fields | Reliability |
|---------|-------|--------|-------------|
| GTM data-gtm JSON | Superdry | title, price, color, brand, category | High |
| __NEXT_DATA__ productGroupings | Nike | title, price, color, image, URL | High |
| __NEXT_DATA__ GraphQL results | M&S | title, price, size, image, variant | High |
| reptile-tile HTML | Otto | product_id, name, price, image | Medium |
| JSON-LD Product | Coolblue | title, price, image, description | High (PDP only) |

### Platform Patterns

| Platform | Sites | Blocking | Data Quality |
|----------|-------|----------|-------------|
| Demandware (SFCC) | Superdry, Guess | Mixed | High (GTM) |
| Next.js SSR | Nike, M&S | None | High (__NEXT_DATA__) |
| Next Group CMS | Reiss, Next | 403 | N/A |
| Proprietary SPA | Aboutyou, Coolblue | SPA | Medium (PDP only) |

### Anti-Scraping Signals

| Signal | Sites | Impact |
|--------|-------|--------|
| 403 on category pages | Reiss, Next | Complete block |
| Geo-redirect | Guess, Mango | Locale mismatch |
| SPA (no server data) | Aboutyou, Coolblue | Listing pages empty |
| API authentication | Otto, Aboutyou | API access blocked |

## Recommendations for CLM Training

### Priority 1: Superdry (Easiest)
- Use `requests` mode
- Extract GTM JSON from `data-gtm` attributes
- 48 products per page with all fields

### Priority 2: M&S (Best Data Quality)
- Use `browser` mode for __NEXT_DATA__
- GraphQL response has richest field data
- 48 products with variants, sizes, images

### Priority 3: Nike (Most Products)
- Use `browser` mode for __NEXT_DATA__
- 947 total products with API pagination
- Need to handle consumerChannelId for API access

### Priority 4: Otto (Volume)
- Use `browser` mode for reptile-tile HTML
- 120 products per page
- Need HTML parsing for product names

### Priority 5: Coolblue (Detail Pages Only)
- Use sitemap for product URL discovery
- JSON-LD on detail pages for field extraction
- Two-step process: URL discovery → detail scraping

## Files Created

| File | Site | Description |
|------|------|-------------|
| `deep_recon_superdry_com.json` | superdry.com | GTM data extraction guide |
| `deep_recon_nike_com.json` | nike.com | __NEXT_DATA__ + API pagination |
| `deep_recon_marksandspencer_com.json` | marksandspencer.com | GraphQL product data |
| `deep_recon_otto_de.json` | otto.de | reptile-tile HTML parsing |
| `deep_recon_coolblue_nl.json` | coolblue.nl | JSON-LD detail page approach |
| `deep_recon_mango_com.json` | mango.com | Partial - API not tested |
| `deep_recon_guess_com.json` | guess.com | Failed - geo-redirect |
| `deep_recon_aboutyou_de.json` | aboutyou.de | Failed - SPA |
| `deep_recon_reiss_com.json` | reiss.com | Failed - 403 |
| `deep_recon_next_co_uk.json` | next.co.uk | Failed - 403 |
