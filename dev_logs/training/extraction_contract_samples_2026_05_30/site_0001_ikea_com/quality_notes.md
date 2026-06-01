# IKEA.com Extraction Quality Notes

## Site Overview
- **Domain**: ikea.com
- **Platform**: IKEA Proprietary (sik.search.blue.cdtapps.com API)
- **Access Mode**: requests (API call, no browser rendering needed)
- **Locale**: gb/en (UK English)
- **Currency**: GBP

## Field Coverage

| CLM Field | Status | Source | Notes |
|---|---|---|---|
| title | observed | `product.name` | Short product names (e.g. "GLOSTAD"), not descriptive titles |
| highest_price | observed | `product.salesPrice.numeral` | Float value (e.g. 150.0). Currency in separate field. |
| currency | observed | `product.salesPrice.currencyCode` | ISO 4217 code determined by locale |
| color | observed | `product.colors[0].name` | First color from colors array. Multiple colors available. |
| size | missing | N/A | Not available in listing API. Detail page only. |
| description | inferred | `product.typeName` | Product type (e.g. "3-seat sofa"). Full descriptions on detail pages. |
| image_url | observed | `product.mainImageUrl` | Direct URL to main product image |
| product_url | observed | `product.pipUrl` | Full URL to product detail page |
| category_level_1 | inferred | `product.typeName` or category ID | Can be derived from typeName or search query category |
| category_level_2 | missing | N/A | Not available in listing API response |

## Evidence Source
- **Type**: JSON API response
- **Endpoint**: `https://sik.search.blue.cdtapps.com/gb/en/search?c=listaf&v=20250507`
- **Method**: POST with JSON body
- **Response Structure**: `results[0].items[].product`
- **Discovery Method**: `observe_browser_network` on category page revealed XHR/fetch calls to this endpoint

## Parser Strategy
- **Strategy**: `api_response_extractor`
- **Rationale**: IKEA's search API returns structured JSON with complete product data. No HTML parsing needed. The API is publicly accessible without authentication.
- **Advantages**: Fast, reliable, no anti-bot issues, structured data
- **Disadvantages**: API endpoint may change, requires category ID knowledge

## Confidence Assessment
- **Overall Confidence**: 0.85
- **Title**: High confidence - always present, consistent format
- **Price**: High confidence - structured numeric value with currency code
- **Image**: High confidence - direct URL, always present
- **Color**: Medium confidence - may not always be present, depends on product
- **Description**: Medium confidence - typeName is available but not full description

## Known Limitations
1. **Short product names**: IKEA uses short names (e.g. "GLOSTAD") rather than descriptive titles. The full product name requires combining name + typeName.
2. **No size data**: Size/dimensions are not available in the listing API response. Requires detail page scraping.
3. **No sub-categories**: Category_level_2 is not available in the listing response.
4. **API versioning**: The API URL includes a version parameter (v=20250507) that may change over time.
5. **Locale-dependent**: The API URL includes locale path (e.g. "gb/en") which determines currency and language.
