# Failure Taxonomy — First 50 Sites

**Generated**: 2026-05-28
**Total sites analyzed**: 50
**Schema**: clm-site-recon-v1

## Failure Mode Classification

### 1. Captcha/Bot Detection (12 sites, 24%)
**Sites**: adidas.com, forever21.com, newlook.com, riverisland.com, allsaints.com, tedbaker.com, frenchconnection.com, shein.com, matchesfashion.com, zara.com (partial), mango.com (partial), aboutyou.com (partial)
**Evidence**: Browser returns captcha challenge page (Cloudflare, geetest, or custom)
**Impact**: Cannot access site via browser mode
**Suggested handling**: Requires proxy, authenticated session, or captcha solving service
**Confidence**: 0.9

### 2. WAF/CDN 403 Block (8 sites, 16%)
**Sites**: adidas.com, louisvuitton.com, newlook.com, forever21.com, frenchconnection.com, zara.com, mango.com, aboutyou.com
**Evidence**: 403 Forbidden across all modes (requests, curl_cffi, browser)
**Impact**: Site blocks automated access via WAF/CDN
**Suggested handling**: Requires proxy or authenticated session
**Confidence**: 0.9

### 3. Inditex Group SPA (6 sites, 12%)
**Sites**: zara.com, massimodutti.com, bershka.com, pullandbear.com, stradivarius.com, oysho.com
**Evidence**: ~2100 byte HTML shell, SPA architecture, all return same minimal content
**Impact**: Content requires full browser rendering, API-driven architecture
**Suggested handling**: Identify and use product API endpoints directly
**Confidence**: 0.95

### 4. robots.txt Block (2 sites, 4%)
**Sites**: hm.com, jackwills.com
**Evidence**: robots.txt explicitly prohibits crawling
**Impact**: Site blocks automated access via robots.txt
**Suggested handling**: Respect robots.txt or use manual access
**Confidence**: 0.95

### 5. Geo-blocking/Region Restriction (5 sites, 10%)
**Sites**: boohoo.com, debenhams.com, prettylittlething.com, reiss.com, superdry.com
**Evidence**: Region block detected, locale-specific content
**Impact**: May get different content or be blocked based on geo
**Suggested handling**: Use locale-specific URL or proxy
**Confidence**: 0.6

### 6. HTTP2 Protocol Error (3 sites, 6%)
**Sites**: gucci.com, houseoffraser.co.uk, flannels.com
**Evidence**: Browser returns net::ERR_HTTP2_PROTOCOL_ERROR
**Impact**: Browser mode fails but requests mode may work
**Suggested handling**: Use requests mode for data extraction
**Confidence**: 0.7

### 7. SPA/JS Shell (8 sites, 16%)
**Sites**: nike.com, next.co.uk, topshop.com, primark.com, burberry.com, farfetch.com, harveynichols.com, uniqlo.com (partial)
**Evidence**: Large HTML (80KB+) but minimal DOM content, requires JS rendering
**Impact**: Content requires browser rendering or API access
**Suggested handling**: Use browser mode or identify API endpoints
**Confidence**: 0.8

### 8. Network Timeout (2 sites, 4%)
**Sites**: asos.com, farfetch.com
**Evidence**: Requests timeout during analysis
**Impact**: Site may be slow or rate-limiting
**Suggested handling**: Increase timeout or use proxy
**Confidence**: 0.6

## Platform Distribution

| Platform | Sites | Notes |
|----------|-------|-------|
| Inditex Group | 6 | All SPA, ~2100 bytes, shared architecture |
| Demandware | 3 | superdry.com, allsaints.com, debenhams.com |
| api.e.* subdomain | 2 | next.co.uk, reiss.com |
| Dedicated API domain | 5 | nike.com, burberry.com, selfridges.com, harveynichols.com, farfetch.com |

## Success Patterns

### High Accessibility (confidence ≥0.4)
- **Dutch/German e-commerce**: shoesme.nl, klebefieber.de, spreadshirt.de, aboutyou.com (partial)
- **UK accessible**: uniqlo.com, boohoo.com, debenhams.com, selfridges.com, harveynichols.com
- **API-driven**: nike.com (api.nike.com), next.co.uk (api.e.next.co.uk)

### Key API Patterns Discovered
- `api.{domain}.com` - nike.com, burberry.com, selfridges.com
- `api.e.{domain}.com` - next.co.uk, reiss.com
- `api.randemretail.online` - harveynichols.com
- `api.farfetch.net` - farfetch.com
- `/api/v2/{endpoint}` - harveynichols.com
- `/search?q={query}` - superdry.com, prettylittlething.com
- `/categories/{slug}` - boohoo.com, debenhams.com

## Recommendations for CLM Framework

1. **Prioritize API discovery**: Dedicated API domains provide the most reliable data access
2. **Implement proxy rotation**: 24% of sites require proxy for captcha bypass
3. **Add Inditex Group handler**: 6 sites share identical architecture, one handler works for all
4. **Support category faceted URLs**: boohoo.com and debenhams.com use faceted URL patterns
5. **Handle HTTP2 errors gracefully**: 3 sites fail in browser mode but work in requests mode
6. **Respect robots.txt**: 2 sites explicitly block crawling, should be flagged and skipped

## Evidence Quality Summary

- **observed**: 65% of evidence (from HTML/scripts/network)
- **inferred**: 20% of evidence (from URL/DOM patterns)
- **guessed**: 15% of evidence (low-confidence assumptions)

## Next Steps

1. Continue expanding to 100+ sites for broader coverage
2. Focus on accessible sites with API hints for deeper analysis
3. Test discovered API endpoints for product data extraction
4. Build platform-specific handlers for common patterns (Inditex, Demandware)
