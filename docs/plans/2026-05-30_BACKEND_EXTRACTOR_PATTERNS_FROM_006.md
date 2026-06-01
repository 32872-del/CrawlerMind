# Backend Extractor Patterns from LLM-2026-006 Deep Recon

**Date**: 2026-05-30
**Author**: LLM-2026-006
**Source**: Deep Recon Phase 2 fixtures from `dev_logs/training/xiaomi_recon_2026_05_28/fixtures/`

## 1. Why These Three Patterns

These patterns cover the three most common product data embedding strategies found across 110+ e-commerce sites:

| Pattern | Sites Using It | Coverage |
|---------|---------------|----------|
| GTM data-gtm attribute | Superdry, AllSaints, Ted Baker, and any site using Google Tag Manager | ~20% of sites |
| __NEXT_DATA__ product wall | Nike, M&S, and any Next.js SSR e-commerce site | ~15% of sites |
| GraphQL SSR cache in __NEXT_DATA__ | M&S, and sites using Apollo/urql SSR | ~10% of sites |

Combined, these three patterns cover ~45% of the sites in our recon index. They are the highest-confidence, lowest-friction extraction paths found.

## 2. Pattern 1: GTM Data Attribute Extractor

### When to Use
- Site uses Google Tag Manager
- Product tiles have `data-gtm` attributes containing JSON
- Works with `requests` mode (no browser needed)

### Input
```python
# Raw HTML string from requests/curl_cffi fetch
html: str  # Listing page HTML
```

### Parse Steps
```python
import re, json, html as html_lib

def extract_gtm_products(html_str: str) -> list[dict]:
    # 1. Find all product tiles with data-gtm
    pattern = r'class="product-tile"[^>]*data-gtm="([^"]*)"'
    matches = re.findall(pattern, html_str)
    
    products = []
    for raw_gtm in matches:
        # 2. HTML entity decode
        decoded = html_lib.unescape(raw_gtm)
        
        # 3. JSON parse
        try:
            gtm = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        
        # 4. Extract ecommerce.items[0]
        items = gtm.get('ecommerce', {}).get('items', [])
        if not items:
            continue
        
        item = items[0]
        products.append({
            'title': item.get('item_name'),
            'highest_price': item.get('price'),
            'currency': 'GBP',  # Site-specific
            'color': item.get('item_colour'),
            'sku': item.get('item_sku'),
            'brand': item.get('item_brand'),
            'category_level_1': item.get('item_category'),
            'category_level_2': item.get('item_category2'),
        })
    
    return products
```

### Failure Points
1. **GTM structure varies**: Some sites use `ecommerce.items[]`, others use `items[]` directly, or `products[]`
2. **HTML entity encoding**: Must unescape `&quot;`, `&amp;`, etc. before JSON parse
3. **Multiple GTM events**: Some tiles have multiple `data-gtm` events; filter by `event == 'view_item_list'`
4. **Missing fields**: `image_url` and `product_url` are NOT in GTM — must extract from sibling HTML elements

### Test Strategy
```python
def test_gtm_extractor():
    # Load fixture
    with open('fixtures/superdry_com/raw_evidence_list_page.html') as f:
        html = f.read()
    with open('fixtures/superdry_com/expected_items_sample.json') as f:
        expected = json.load(f)
    
    products = extract_gtm_products(html)
    
    assert len(products) == expected['item_count']
    for actual, exp in zip(products, expected['items']):
        assert actual['title'] == exp['title']
        assert actual['highest_price'] == exp['highest_price']
        assert actual['color'] == exp['color']
```

### Supplementary Extraction (image + URL)
```python
def extract_supplementary_fields(html_str: str, product_id: str) -> dict:
    # Image: from img.tile-image[srcset]
    srcset_pattern = r'<img class="tile-image"[^>]*srcset="([^"]*)"'
    srcsets = re.findall(srcset_pattern, html_str)
    
    # URL: from .tile-image-wrapper-link[href]
    url_pattern = r'<a class="tile-image-wrapper-link"[^>]*href="([^"]*)"'
    urls = re.findall(url_pattern, html_str)
    
    # Parse srcset for largest URL
    def parse_srcset(srcset: str) -> str:
        parts = [s.strip().split() for s in srcset.split(',')]
        best_url, best_w = '', 0
        for part in parts:
            if len(part) >= 2:
                try:
                    w = int(part[1].replace('w', ''))
                    if w > best_w:
                        best_w = w
                        best_url = part[0]
                except ValueError:
                    pass
        return best_url or (parts[0][0] if parts else '')
    
    return {
        'image_url': parse_srcset(srcsets[0]) if srcsets else None,
        'product_url': f'https://www.superdry.com{urls[0]}' if urls else None,
    }
```

## 3. Pattern 2: __NEXT_DATA__ Product Wall Extractor

### When to Use
- Site uses Next.js with server-side rendering
- Product data is embedded in `<script id="__NEXT_DATA__">` tag
- Works with `browser` mode (needs JS execution for full page)

### Input
```python
# Rendered HTML string from browser
html: str  # Full page HTML after JS execution
```

### Parse Steps
```python
import re, json

def extract_next_data_products(html_str: str, path: str) -> list[dict]:
    # 1. Find __NEXT_DATA__ script tag
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html_str,
        re.DOTALL
    )
    if not match:
        raise ValueError("No __NEXT_DATA__ found")
    
    # 2. JSON parse
    data = json.loads(match.group(1))
    
    # 3. Navigate to product data (site-specific path)
    obj = data
    for key in path.split('.'):
        if obj is None:
            break
        obj = obj.get(key) if isinstance(obj, dict) else None
    
    return obj or []
```

### Nike-Specific Path
```python
# Path: props.pageProps.initialState.Wall.productGroupings
def extract_nike_products(html_str: str) -> list[dict]:
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_str, re.DOTALL)
    data = json.loads(match.group(1))
    wall = data['props']['pageProps']['initialState']['Wall']
    
    products = []
    for grouping in wall.get('productGroupings', []):
        for p in (grouping.get('products') or []):
            products.append({
                'title': f"{p['copy']['title']} - {p['copy']['subTitle']}",
                'highest_price': p['prices']['currentPrice'],
                'currency': p['prices']['currency'],
                'color': p['displayColors']['colorDescription'],
                'image_url': p['colorwayImages']['portraitURL'],
                'product_url': p['pdpUrl']['url'],
                'sku': p['productCode'],
                'category_level_1': p['productType'],
            })
    
    return products
```

### Failure Points
1. **__NEXT_DATA__ not present**: Some Next.js apps don't expose it (use `isFallback` check)
2. **Path varies by site**: `props.pageProps.initialState.Wall` is Nike-specific; M&S uses `serverSideGqlResponseFed.productPageData.search.results`
3. **Large payloads**: __NEXT_DATA__ can be 1MB+; use streaming JSON parser for production
4. **Null products**: Some `productGroupings[].products` can be null; must handle with `or []`
5. **Pagination**: First page only; need to discover pagination API for full catalog

### Test Strategy
```python
def test_next_data_extractor():
    with open('fixtures/nike_com/raw_evidence_next_data_sample.json') as f:
        raw = json.load(f)
    with open('fixtures/nike_com/expected_items_sample.json') as f:
        expected = json.load(f)
    
    # Simulate __NEXT_DATA__ structure
    mock_next_data = {
        'props': {
            'pageProps': {
                'initialState': {
                    'Wall': {
                        'productGroupings': [{'products': raw}]
                    }
                }
            }
        }
    }
    html = f'<script id="__NEXT_DATA__">{json.dumps(mock_next_data)}</script>'
    
    products = extract_nike_products(html)
    assert len(products) == len(raw)
    assert products[0]['title'] == expected['items'][0]['title']
```

## 4. Pattern 3: GraphQL SSR Cache Extractor

### When to Use
- Site uses Next.js with GraphQL (Apollo/urql) SSR
- Product data is in `__NEXT_DATA__` under a GraphQL cache key
- Typically richer data than plain __NEXT_DATA__ (includes variants, sizes, SKUs)

### Input
```python
# Rendered HTML string from browser
html: str  # Full page HTML after JS execution
```

### Parse Steps
```python
import re, json

def extract_graphql_ssr_products(html_str: str) -> list[dict]:
    # 1. Find __NEXT_DATA__
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_str, re.DOTALL)
    data = json.loads(match.group(1))
    
    # 2. Navigate to GraphQL response (M&S-specific path)
    gql = data['props']['pageProps']['serverSideGqlResponseFed']
    results = gql['productPageData']['search']['results']
    
    products = []
    for p in results.get('products', []):
        # 3. Extract first variant
        variants = p.get('variants', [])
        v0 = variants[0] if variants else {}
        media = v0.get('mediaAssets', [])
        asset_id = media[0].get('assetId') if media else None
        
        # 4. Parse color from seoPath
        seo_path = p.get('seoPath', '')
        color = None
        if 'color=' in seo_path:
            color_match = re.search(r'color=([^&]+)', seo_path)
            if color_match:
                color = color_match.group(1)
        
        # 5. Construct image URL
        image_url = None
        if asset_id:
            image_url = f'https://assets.digitalcontent.marksandspencer.app/image/upload/q_auto,f_auto/{asset_id}'
        
        products.append({
            'title': p.get('title'),
            'highest_price': p.get('price', {}).get('listPrice', {}).get('amount'),
            'currency': p.get('price', {}).get('currency'),
            'color': color,
            'size': v0.get('size'),
            'description': p.get('description'),
            'image_url': image_url,
            'product_url': f'https://www.marksandspencer.com{seo_path}' if seo_path else None,
            'sku': v0.get('skuId'),
            'category_level_1': p.get('productDefinition'),
            'brand': p.get('brand'),
        })
    
    return products
```

### Failure Points
1. **GraphQL path varies**: `serverSideGqlResponseFed` is M&S-specific; other sites use different cache keys
2. **urqlState is opaque**: The `urqlState` dict contains keyed cache entries; finding the right one requires iterating
3. **Image URL construction**: Asset IDs need site-specific CDN template
4. **Color parsing**: Only available as query param in `seoPath`, not as a direct field
5. **Description often null**: GraphQL responses may omit description
6. **Variant handling**: Only first variant extracted; full size list requires iterating all variants

### Test Strategy
```python
def test_graphql_ssr_extractor():
    with open('fixtures/marksandspencer_com/raw_evidence_graphql_sample.json') as f:
        raw = json.load(f)
    with open('fixtures/marksandspencer_com/expected_items_sample.json') as f:
        expected = json.load(f)
    
    # Simulate __NEXT_DATA__ structure
    mock_next_data = {
        'props': {
            'pageProps': {
                'serverSideGqlResponseFed': {
                    'productPageData': {
                        'search': {
                            'results': raw
                        }
                    }
                }
            }
        }
    }
    html = f'<script id="__NEXT_DATA__">{json.dumps(mock_next_data)}</script>'
    
    products = extract_graphql_ssr_products(html)
    assert len(products) == raw['totalItems'] or len(products) == len(raw['products'])
    assert products[0]['title'] == expected['items'][0]['title']
```

## 5. CLM Backend Integration Recommendations

### New Extractor Classes to Add

```python
# In clm/extractors/

class GTMExtractor(BaseExtractor):
    """Extracts product data from GTM data-gtm attributes."""
    PATTERN = 'gtm_data_attribute'
    
    def can_handle(self, html: str) -> bool:
        return 'data-gtm' in html and 'product-tile' in html
    
    def extract(self, html: str) -> list[dict]:
        return extract_gtm_products(html)

class NextDataExtractor(BaseExtractor):
    """Extracts product data from __NEXT_DATA__ script tag."""
    PATTERN = 'next_data_product_wall'
    
    def can_handle(self, html: str) -> bool:
        return '__NEXT_DATA__' in html
    
    def extract(self, html: str, path: str) -> list[dict]:
        return extract_next_data_products(html, path)

class GraphQLSSRExtractor(BaseExtractor):
    """Extracts product data from GraphQL SSR cache in __NEXT_DATA__."""
    PATTERN = 'graphql_ssr_cache'
    
    def can_handle(self, html: str) -> bool:
        return '__NEXT_DATA__' in html and 'serverSideGqlResponseFed' in html
    
    def extract(self, html: str) -> list[dict]:
        return extract_graphql_ssr_products(html)
```

### Site Profile Registration

```python
# In clm/profiles/

SITE_PROFILES = {
    'superdry.com': {
        'extractor': 'GTMExtractor',
        'runtime': 'requests',
        'pagination': 'demandware_query_params',
        'base_url': 'https://www.superdry.com',
    },
    'nike.com': {
        'extractor': 'NextDataExtractor',
        'runtime': 'browser',
        'pagination': 'api_cursor',
        'path': 'props.pageProps.initialState.Wall.productGroupings',
        'consumer_channel_id': 'd9a5bc42-4b9c-4976-858a-f159cf99c647',
    },
    'marksandspencer.com': {
        'extractor': 'GraphQLSSRExtractor',
        'runtime': 'browser',
        'pagination': 'graphql_offset',
        'image_template': 'https://assets.digitalcontent.marksandspencer.app/image/upload/q_auto,f_auto/{assetId}',
    },
}
```

### Recommended New Unit Tests

| Test | File | What It Verifies |
|------|------|-----------------|
| `test_gtm_extractor_basic` | `test_gtm_extractor.py` | GTM JSON parse, field mapping |
| `test_gtm_html_entity_decode` | `test_gtm_extractor.py` | `&quot;`, `&amp;` handling |
| `test_gtm_missing_items` | `test_gtm_extractor.py` | Graceful handling when `ecommerce.items` is empty |
| `test_next_data_extractor_basic` | `test_next_data_extractor.py` | __NEXT_DATA__ parse, path navigation |
| `test_next_data_null_products` | `test_next_data_extractor.py` | Null products in productGroupings |
| `test_next_data_missing_tag` | `test_next_data_extractor.py` | No __NEXT_DATA__ in HTML |
| `test_graphql_ssr_extractor_basic` | `test_graphql_ssr_extractor.py` | GraphQL cache parse, variant extraction |
| `test_graphql_ssr_image_construction` | `test_graphql_ssr_extractor.py` | Asset ID → URL template expansion |
| `test_graphql_ssr_color_parsing` | `test_graphql_ssr_extractor.py` | seoPath query param extraction |
| `test_srcset_parser` | `test_image_utils.py` | srcset attribute parsing for largest URL |
| `test_pagination_demandware` | `test_pagination.py` | `?start=N&sz=M` URL generation |
| `test_pagination_api_cursor` | `test_pagination.py` | Nike API cursor pagination |

### Fixture-Based Integration Tests

```python
# Each test loads raw evidence from fixtures and validates against expected_items_sample.json

@pytest.mark.parametrize('site_dir', [
    'fixtures/superdry_com',
    'fixtures/nike_com',
    'fixtures/marksandspencer_com',
])
def test_extractor_from_fixture(site_dir):
    # Load contract
    with open(f'{site_dir}/extraction_contract.json') as f:
        contract = json.load(f)
    
    # Load raw evidence
    evidence_file = contract['evidence_files'][0]
    with open(f'{site_dir}/{evidence_file}') as f:
        raw = json.load(f) if evidence_file.endswith('.json') else f.read()
    
    # Load expected
    with open(f'{site_dir}/expected_items_sample.json') as f:
        expected = json.load(f)
    
    # Run extractor
    extractor = get_extractor(contract['parser_strategy']['name'])
    items = extractor.extract(raw)
    
    # Validate
    assert len(items) >= expected['item_count']
    for item in expected['items']:
        # At minimum, title and price must match
        matching = [i for i in items if i.get('title') == item['title']]
        assert matching, f"Missing product: {item['title']}"
        assert matching[0]['highest_price'] == item['highest_price']
```

## 6. Uncertainties and Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| GTM data-gtm structure varies by site | Medium | Test with multiple sites; make `ecommerce.items[0]` path configurable |
| __NEXT_DATA__ path varies per site | High | Build a path discovery heuristic; store paths in site profiles |
| GraphQL SSR cache key varies | High | M&S uses `serverSideGqlResponseFed`; other sites may use different keys |
| Image CDN templates change | Low | Store templates in site profiles, not hardcoded |
| Pagination APIs change | Medium | Re-validate pagination URLs periodically |
| Anti-scraping escalation | High | Superdry works with requests today; may need browser tomorrow |
| __NEXT_DATA__ removed in future Next.js versions | Medium | Fallback to HTML DOM parsing (product card selectors) |
| Rate limiting on pagination | Medium | Implement backoff; respect robots.txt |

## 7. Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P0 | Implement `GTMExtractor` with fixture tests | 2h | Covers ~20% of sites |
| P0 | Implement `NextDataExtractor` with fixture tests | 2h | Covers ~15% of sites |
| P1 | Implement `GraphQLSSRExtractor` with fixture tests | 3h | Covers ~10% of sites |
| P1 | Add srcset parser utility | 1h | Needed for GTM extractor image field |
| P1 | Add site profile registry | 2h | Maps domains to extractors |
| P2 | Implement pagination for each strategy | 4h | Full catalog coverage |
| P2 | Add fixture-based integration test harness | 2h | Regression protection |
| P3 | Add path auto-discovery for __NEXT_DATA__ | 4h | Reduces manual site profiling |
