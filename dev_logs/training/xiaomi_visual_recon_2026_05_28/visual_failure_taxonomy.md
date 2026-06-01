# Visual Failure Taxonomy Report

**Generated**: 2026-05-28
**Total Pages Analyzed**: 100
**Schema Version**: clm-visual-recon-v1

---

## 1. Failure Category Overview

| Category | Count | Percentage | Severity |
|----------|-------|------------|----------|
| **Blocked Access** | 8 | 8% | High |
| **Empty/Error Pages** | 2 | 2% | Medium |
| **Category Mismatch** | 2 | 2% | Low |
| **Successful Pages** | 88 | 88% | - |

---

## 2. Blocked Access Patterns

### 2.1 Cloudflare/Captcha Blocks (5 instances)
- **Etsy**: Consistent bot detection across all attempts
  - Visual indicator: Full-page captcha challenge
  - IP identified: 80.93.218.39
  - Recommendation: Stealth browser + proxy rotation required
  
- **Home Depot**: Akamai WAF block
  - Visual indicator: "Access Denied" page
  - Recommendation: Different User-Agent + rate limiting

- **Dell**: WAF block
  - Visual indicator: "Access Denied" page
  - Recommendation: Different User-Agent + rate limiting

### 2.2 Geo-Redirects (1 instance)
- **Best Buy**: Geographic restriction
  - Visual indicator: Redirect to region-specific page
  - Recommendation: Use local proxy or VPN

### 2.3 Login Walls (1 instance)
- **AliExpress**: Authentication required
  - Visual indicator: Full login page overlay
  - Recommendation: Account-based scraping or public API

### 2.4 Robots.txt Blocks (1 instance)
- **Walmart**: Blocked by robots.txt
  - Visual indicator: Screenshot tool returns "robots.txt 禁止抓取"
  - Recommendation: Respect robots.txt, use alternative sources

---

## 3. Empty/Error Page Patterns

### 3.1 Product Not Found (1 instance)
- **Newegg**: Invalid product URL
  - URL: https://www.newegg.com/p/N82E16824015501
  - Visual indicator: "Item not found" page
  - Recommendation: Validate product URLs before crawling

### 3.2 Category Mismatch (2 instances)
- **Newegg**: Search term vs. category mismatch
  - "keyboard" routed to Desktop CPU Processor category
  - "camera" routed to Switches category
  - Visual indicator: Wrong product category displayed
  - Recommendation: Fix category mapping for search terms

---

## 4. Field Region Patterns

### 4.1 Consistent Selector Hints (Amazon)
- Title: `.a-size-base-plus` (confidence: 0.6)
- Price: `.a-price .a-offscreen` (confidence: 0.65)
- Image: `.s-image` (confidence: 0.7)
- Colors: `.swatchElement` (confidence: 0.5)
- Product URL: `.a-link-normal` (confidence: 0.6)

### 4.2 Field Detection Confidence
- **High confidence (0.7)**: Image URLs - consistently visible
- **Medium confidence (0.6-0.65)**: Title, Price, Product URL
- **Low confidence (0.5)**: Color variants - often incomplete

---

## 5. Layout Patterns

### 5.1 Search Results Layouts
- **Grid layout**: 5-column grid (most common)
- **Vertical list**: Single-column list (less common)

### 5.2 Pagination Signals
- Next button: Present in 88% of successful pages
- Page numbers: Sometimes visible
- Product count text: Occasionally present

---

## 6. Confidence Distribution

| Confidence Range | Pages | Percentage |
|-----------------|-------|------------|
| 0.0-0.2 (Almost no evidence) | 0 | 0% |
| 0.3-0.4 (Weak visual clues) | 0 | 0% |
| 0.5-0.6 (Clear regions, no HTML support) | 100 | 100% |
| 0.7-0.8 (Screenshot + HTML mutual support) | 0 | 0% |
| 0.9-1.0 (Screenshot + HTML/API/running results) | 0 | 0% |

**Note**: All pages limited to 0.65 maximum overall confidence per guide rules (screenshot-only evidence).

---

## 7. Recommendations

### 7.1 For Blocked Sites
1. Implement stealth browser with fingerprint rotation
2. Use residential proxy pools
3. Add random delays between requests
4. Rotate User-Agent strings

### 7.2 For Field Extraction
1. Prioritize image URLs (highest confidence)
2. Validate title selectors across different product categories
3. Handle price variants (sale vs. regular)
4. Improve color variant detection

### 7.3 For Pagination
1. Detect and handle "next" button reliably
2. Support infinite scroll patterns
3. Handle page number navigation

---

## 8. Success Metrics

- **Total pages analyzed**: 100
- **Successful pages**: 88 (88%)
- **Failed pages**: 12 (12%)
- **Average confidence**: 0.58
- **Sites covered**: 7 (Amazon, Newegg, eBay, Etsy, Best Buy, Home Depot, AliExpress)
- **Page types covered**: 11 (home, search_results, product_listing, product_detail, blocked, error, empty, login, captcha, geo_redirect, unknown)

---

**Report compiled by**: Multimodal Visual Evidence Annotator
**Schema**: clm-visual-recon-v1
**Output directory**: F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28\
