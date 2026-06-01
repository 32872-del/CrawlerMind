# Failure Taxonomy — 100 Sites (Update 002)

**Generated**: 2026-05-28
**Total Sites**: 100

## Failure Categories

### 1. WAF / 403 Forbidden (22 sites)
Sites returning HTTP 403 from all or most access modes.

| Site | Notes |
|------|-------|
| nordstrom.com | 160 bytes, text/plain, most aggressive WAF |
| very.co.uk | 4306 bytes error page, Shop Direct |
| asos.com | 403 all modes |
| hm.com | 403 all modes |
| forever21.com | 403 all modes |
| primark.com | 403 all modes |
| topshop.com | 403 all modes |
| riverisland.com | 403 all modes |
| newlook.com | 403 all modes |
| jacamo.com | 403 all modes |
| simplybe.com | 403 all modes |
| jdwilliams.co.uk | 403 all modes |
| monsoon.co.uk | 403 all modes |
| oasis-fashion.com | TLS error (new: SSL_UNEXPECTED_EOF) |
| gap.com | Gap Inc. WAF |
| bananarepublic.com | Gap Inc. WAF |
| oldnavy.com | Gap Inc. WAF |
| massimodutti.com | Inditex SPA ~2100 byte shell |
| stradivarius.com | Inditex SPA ~2100 byte shell |
| oysho.com | Inditex SPA ~2100 byte shell |
| urbanoutfitters.com | URBN captcha |
| freepeople.com | URBN captcha |
| anthropologie.com | URBN captcha |
| allsaints.com | Demandware captcha+rate_limited |

### 2. Cloudflare / Captcha Challenge (14 sites)
Sites behind Cloudflare or other captcha systems.

| Site | Challenge Type |
|------|---------------|
| zara.com | Inditex SPA shell |
| bershka.com | Inditex SPA shell |
| pullandbear.com | Inditex SPA shell |
| cosstores.com | H&M Group challenge |
| weekday.com | H&M Group challenge |
| monki.com | H&M Group challenge |
| arket.com | H&M Group challenge |
| shein.com | geetest captcha |
| lkbennett.com | browser captcha |
| tedbaker.com | browser captcha |
| boden.co.uk | browser captcha |
| scotchandsoda.com | browser captcha |
| wrangler.com | challenge detected |
| superdry.com | Demandware (accessible via requests) |

### 3. DNS / Domain Failure (3 sites)
Domains that don't resolve or redirect to error pages.

| Site | Error |
|------|-------|
| jack-wills.com | DNS resolution failure - brand defunct |
| sandro-paris.com | 502 Bad Gateway (redirects to .cn) |
| jack-wills.com | hostname cannot be resolved |

### 4. JS Shell / SPA (8 sites)
Minimal HTML shell requiring JS execution for content.

| Site | Shell Size | Framework |
|------|-----------|-----------|
| zara.com | ~2112 bytes | Inditex SPA |
| bershka.com | ~2120 bytes | Inditex SPA |
| pullandbear.com | ~2128 bytes | Inditex SPA |
| massimodutti.com | ~2100 bytes | Inditex SPA |
| stradivarius.com | ~2100 bytes | Inditex SPA |
| oysho.com | ~2100 bytes | Inditex SPA |
| next.co.uk | JS shell | Next Group |
| johnlewis.com | JS shell | Monetate |

### 5. Geo-Blocked / Region Restricted (12 sites)
Sites requiring specific geographic access.

| Site | Signal |
|------|--------|
| marksandspencer.com | region_block |
| zalando.co.uk | region_block |
| g-star.com | region_block |
| levi.com | region_block |
| mango.com | region_block |
| aboutyou.de | region_block |
| karenmillen.com | region_block |
| coastfashion.com | region_block |
| debenhams.com | region_block |
| uniqlo.com | (Fast Retailing, no explicit block) |
| asda.com | login_required + region_block |
| tkmaxx.com | inconsistent access |

### 6. Rate Limited (3 sites)
Sites with aggressive rate limiting.

| Site | Signal |
|------|--------|
| allsaints.com | rate_limited + captcha |
| farfetch.com | rate_limited |
| net-a-porter.com | rate_limited |

### 7. Login Required (8 sites)
Sites requiring authentication for full access.

| Site | Notes |
|------|-------|
| johnlewis.com | login_required |
| whistles.com | login_required |
| hobbs.co.uk | login_required |
| reiss.com | login_required |
| next.co.uk | login_required |
| tkmaxx.com | login_required |
| tkmaxx.com | inconsistent access |
| asda.com | login_required |

## Access Mode Effectiveness

| Mode | Success Rate | Best For |
|------|-------------|----------|
| requests | ~60% | Static sites, Demandware, some SPA shells |
| curl_cffi | ~45% | TLS fingerprint bypass, some WAF bypass |
| browser | ~30% | JS-heavy sites, but triggers captcha on many |

## Key API Domains Discovered

| Domain | Sites | Confidence |
|--------|-------|------------|
| api.burberry.com | burberry.com | 0.7 |
| api.selfridges.com | selfridges.com | 0.7 |
| api.farfetch.net | farfetch.com | 0.7 |
| api.nike.com | nike.com | 0.7 |
| api.e.next.co.uk | next.co.uk | 0.7 |
| api.e.reiss.com | reiss.com | 0.7 |
| api.aboutyou.com | aboutyou.de | 0.8 |
| api.shop.mango.com | mango.com | 0.7 |
| api-cloud.aboutyou.de | aboutyou.de | 0.7 |
| api.randemretail.online | tkmaxx.com | 0.6 |
| cms.platform.next | reiss.com | 0.6 |
| cquotient.com | whistles, phase-eight, hobbs | 0.5 |

## Platform Groupings

### Inditex Group (6 sites)
zara.com, bershka.com, pullandbear.com, massimodutti.com, stradivarius.com, oysho.com
- ~2100 byte SPA shell
- All blocked by JS rendering requirement
- Same architecture across all brands

### H&M Group (4 sites)
arket.com, cosstores.com, weekday.com, monki.com
- weekday-frontend-prd.prd.mcs.hmgroup.tech
- All behind challenge/WAF

### URBN Group (3 sites)
urbanoutfitters.com, freepeople.com, anthropologie.com
- Shared captcha system
- All blocked

### Gap Inc. (3 sites)
gap.com, bananarepublic.com, oldnavy.com
- Shared WAF 403
- All blocked

### Boohoo Group (5 sites)
debenhams.com, karenmillen.com, coastfashion.com, warehousefashion.com, prettylittlething.com
- 80 category URL hints each
- Accessible via requests/browser
- Shared platform

### PVH Corp (2 sites)
tommy.com, calvinklein.com
- Similar 5KB JS shell
- Limited access

### Demandware/Salesforce Commerce Cloud (4 sites)
guess.com, allsaints.com, superdry.com, scotchandsoda.com
- Product-ShowQuickView, Search-ShowAjax endpoints
- Mixed accessibility

### Next Group (2 sites)
next.co.uk, reiss.com
- api.e.next.co.uk, api.e.reiss.com
- CMS platform (cms.platform.next)

## Confidence Distribution

| Range | Count | % |
|-------|-------|---|
| 0.0-0.1 | 28 | 28% |
| 0.11-0.2 | 22 | 22% |
| 0.21-0.3 | 25 | 25% |
| 0.31-0.4 | 20 | 20% |
| 0.41-0.5 | 5 | 5% |
| 0.5+ | 0 | 0% |

**Average confidence**: 0.22

## Recommendations for Next Phase

1. **Deep explore high-confidence API sites**: aboutyou.de (0.8), reiss.com (0.7), next.co.uk (0.7), mango.com (0.7)
2. **Test Demandware endpoints**: Search-ShowAjax on superdry.com, guess.com
3. **Explore Boohoo Group catalog pages**: 80 category URLs available on 5 sites
4. **Test cquotient.com recommendation API**: whistles.com, phase-eight.com, hobbs.co.uk
5. **Skip fully blocked sites**: Focus resources on accessible sites with API hints
