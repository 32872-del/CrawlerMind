# Batch Summary: Pages 1-20

**Generated:** 2026-05-28
**Schema:** clm-visual-recon-v1
**Output Directory:** xiaomi_visual_recon_2026_05_28/

---

## 1. Page Count
- **Total pages analyzed:** 20
- **Unique domains:** 7 (amazon.com, ebay.com, etsy.com, walmart.com, bestbuy.com, newegg.com, aliexpress.com, homedepot.com)

## 2. Page Type Distribution

| Page Type | Count | Percentage |
|-----------|-------|------------|
| home | 3 | 15% |
| product_listing | 3 | 15% |
| search_results | 2 | 10% |
| product_detail | 2 | 10% |
| blocked | 8 | 40% |
| error | 2 | 10% |

## 3. Product Listing Pages
- **Count:** 3
- **Domains:** amazon.com (2), newegg.com (1)
- **Notes:** Amazon bestsellers and search results, Newegg laptop search

## 4. Product Detail Pages
- **Count:** 2
- **Domains:** amazon.com (1), newegg.com (1)
- **Notes:** Amazon iPad Air (out of stock), Newegg MSI laptop (out of stock)

## 5. Blocked/Challenge Pages
- **Count:** 8 (40%)
- **Breakdown:**
  - Etsy captcha/bot detection: 5 pages (consistent IP block)
  - Best Buy geo-redirect: 2 pages
  - Home Depot WAF block: 1 page
  - AliExpress login wall: 1 page (counted separately)
- **Note:** High blocking rate indicates need for stealth browser and proxy rotation

## 6. Cookie Banner Pages
- **Count:** 1
- **Domain:** ebay.com (on 404 page)

## 7. Pages with Visible Product Cards
- **Count:** 5
- **Domains:** amazon.com (4), newegg.com (1)
- **Layout types:** horizontal_carousel, vertical_list, grid

## 8. Pages with Pagination Signals
- **Count:** 4
- **Types:** page_numbers (3), filter_sort_panel (1)

## 9. Most Common Visual Failure Reasons
1. **Bot detection/CAPTCHA** (Etsy) - 5 occurrences, same IP consistently blocked
2. **Geo-redirect** (Best Buy) - 2 occurrences, non-US IP detected
3. **WAF/CDN block** (Home Depot) - 1 occurrence, Akamai block
4. **Login wall** (AliExpress) - 1 occurrence, requires authentication
5. **404/Not Found** (Amazon, eBay) - 2 occurrences, invalid URLs

## 10. Most Recommended CLM Backend Capability Enhancement
1. **Stealth browser runtime** - Essential for Etsy, Home Depot
2. **Proxy rotation** - Needed for IP-blocked sites
3. **Cookie/session management** - For eBay, AliExpress
4. **Geo-bypass headers** - For Best Buy

## 11. Pages Requiring Human Review
- `visual_003_etsy_home_blocked.json` - First Etsy block encounter
- `visual_008_etsy_search_blocked.json` - Etsy search blocked
- `visual_013_etsy_listing_blocked.json` - Etsy listing blocked
- `visual_015_aliexpress_login_wall.json` - Login wall
- `visual_016_homedepot_access_denied.json` - WAF block
- `visual_017_etsy_jewelry_blocked.json` - Fourth Etsy block

## 12. Confidence Distribution

| Confidence Range | Count |
|-----------------|-------|
| 0.60 - 0.65 | 15 |
| 0.65 - 0.70 | 5 |

**Note:** All pages limited to 0.65 max overall confidence because only screenshots were used (no HTML/network summary).

## 13. Key Observations

### Site Accessibility Ranking (easiest to hardest)
1. **Amazon** - Most accessible, clear product cards, minimal blocking
2. **Newegg** - Good accessibility, clear product structure
3. **eBay** - Homepage accessible, but 404 on category pages, cookie consent needed
4. **Walmart** - Homepage accessible but search blocked by robots.txt
5. **Best Buy** - Geo-redirect blocks all content
6. **AliExpress** - Login wall blocks all content
7. **Home Depot** - WAF blocks all access
8. **Etsy** - Consistently blocked by bot detection

### Action Priority for Next Batch
1. Focus on Amazon and Newegg for successful extractions
2. Try eBay with cookie acceptance
3. Skip Etsy (needs stealth browser + proxy)
4. Skip Best Buy (needs US proxy)
5. Skip Home Depot (needs stealth + proxy)
