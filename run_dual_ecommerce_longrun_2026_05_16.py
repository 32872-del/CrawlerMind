"""Real ecommerce long-run training for Sephora PL and uvex PL.

The script is intentionally a training artifact. It studies sitemap/category
structure, samples product URLs across multiple sitemap/category partitions,
and collects normalized product fields into JSON and Excel outputs.
"""
from __future__ import annotations

import argparse
import html
import json
import random
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from autonomous_crawler.tools.coverage_report import CoverageCounters, build_coverage_report
from autonomous_crawler.tools.product_quality import has_errors, validate_product_record
from autonomous_crawler.tools.site_hardening import (
    cache_key,
    category_levels,
    clean_product_images,
    is_bad_html,
    normalize_url as harden_url,
    read_good_page_cache,
    write_good_page_cache,
)
from autonomous_crawler.runners.multi_site_runner import MultiSiteRunner, MultiSiteRunnerConfig


DEFAULT_REPORT = Path("dev_logs/training/2026-05-16_dual_ecommerce_longrun_report.json")
DEFAULT_EXCEL = Path("dev_logs/training/2026-05-16_dual_ecommerce_longrun.xlsx")
DEFAULT_CHECKPOINT = Path("dev_logs/runtime/dual_ecommerce_longrun_2026_05_16_checkpoint.json")
DEFAULT_CATALOG_CACHE = Path("dev_logs/runtime/catalog_cache")


HEADERS = {
    "accept-language": "pl-PL,pl;q=0.9,en;q=0.8",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class SiteRunStats:
    site: str
    requested_target: int
    sitemap_url_count: int = 0
    category_count: int = 0
    attempted: int = 0
    accepted: int = 0
    failed: int = 0
    blocked: int = 0
    rejected_quality: int = 0
    rejected_invalid_page: int = 0
    catalog_exhausted: bool = False
    started_at: float = field(default_factory=time.time)
    failures: list[dict[str, Any]] = field(default_factory=list)
    category_samples: list[str] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)
    issue_counts: dict[str, int] = field(default_factory=dict)
    coverage_report: dict[str, Any] = field(default_factory=dict)
    time_budget_exhausted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "requested_target": self.requested_target,
            "sitemap_url_count": self.sitemap_url_count,
            "category_count": self.category_count,
            "attempted": self.attempted,
            "accepted": self.accepted,
            "failed": self.failed,
            "blocked": self.blocked,
            "rejected_quality": self.rejected_quality,
            "rejected_invalid_page": self.rejected_invalid_page,
            "catalog_exhausted": self.catalog_exhausted,
            "elapsed_seconds": round(time.time() - self.started_at, 2),
            "records_per_minute": round(self.accepted / max((time.time() - self.started_at) / 60, 0.001), 2),
            "acceptance_rate": round(self.accepted / max(self.attempted, 1), 4),
            "failures": self.failures[:50],
            "category_samples": self.category_samples[:30],
            "timing": {key: round(value, 3) for key, value in self.timing.items()},
            "issue_counts": dict(sorted(self.issue_counts.items())),
            "coverage_report": self.coverage_report,
            "time_budget_exhausted": self.time_budget_exhausted,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect Sephora PL and uvex PL product training data.")
    parser.add_argument("--per-site", type=int, default=2000)
    parser.add_argument("--sample-multiplier", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260516)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--time-budget-seconds", type=float, default=0.0, help="Overall wall-clock limit for this training run.")
    parser.add_argument("--site-time-budget-seconds", type=float, default=0.0, help="Per-site wall-clock limit. Useful for 10-minute two-site training.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent product detail workers per site.")
    parser.add_argument("--max-sites", type=int, default=2, help="Concurrent site jobs. Hard cap is 5.")
    parser.add_argument("--catalog-cache-dir", type=Path, default=DEFAULT_CATALOG_CACHE)
    parser.add_argument("--refresh-catalog", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.excel.parent.mkdir(parents=True, exist_ok=True)
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    args.catalog_cache_dir.mkdir(parents=True, exist_ok=True)

    existing = load_checkpoint(args.checkpoint) if args.resume else {"sephora": [], "uvex": []}
    report: dict[str, Any] = {
        "schema_version": "dual-ecommerce-longrun/v1",
        "targets": {
            "sephora": "https://www.sephora.pl/",
            "uvex": "https://uvex.com.pl/",
        },
        "field_requirements": [
            "title",
            "highest_price_regular",
            "colors",
            "subtitle",
            "product_detail",
            "image_urls",
        ],
        "runs": {},
    }

    site_summary = MultiSiteRunner(
        {
            "sephora": lambda: collect_sephora(args, existing.get("sephora") or []),
            "uvex": lambda: collect_uvex(args, existing.get("uvex") or []),
        },
        MultiSiteRunnerConfig(max_sites=min(int(args.max_sites or 2), 5)),
    ).run()
    site_results = {result.name: result for result in site_summary.results}
    if not all(result.ok for result in site_summary.results):
        raise RuntimeError(json.dumps(site_summary.to_dict(), ensure_ascii=False, default=str))
    sephora_records, sephora_stats = site_results["sephora"].result
    uvex_records, uvex_stats = site_results["uvex"].result
    all_records = {"sephora": sephora_records, "uvex": uvex_records}
    save_checkpoint(args.checkpoint, all_records)

    report["runs"]["sephora"] = sephora_stats.to_dict()
    report["runs"]["uvex"] = uvex_stats.to_dict()
    report["summary"] = {
        "sephora_records": len(sephora_records),
        "uvex_records": len(uvex_records),
        "total_records": len(sephora_records) + len(uvex_records),
        "accepted": bool(sephora_stats.coverage_report.get("accepted")) and bool(uvex_stats.coverage_report.get("accepted")),
        "known_limitations": [
            "Sephora direct product pages trigger Akamai challenge; Product-Detail endpoint is used for field extraction.",
            "uvex sitemap includes stale 404 product URLs and media URLs; collector filters catalog-product-view pages.",
        ],
        "multi_site_runner": multi_site_report(site_summary),
    }
    write_outputs(args.report, args.excel, report, all_records)
    print(json.dumps({
        "accepted": report["summary"]["accepted"],
        "sephora_records": len(sephora_records),
        "uvex_records": len(uvex_records),
        "total_records": report["summary"]["total_records"],
        "report": str(args.report),
        "excel": str(args.excel),
        "checkpoint": str(args.checkpoint),
    }, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["accepted"] else 1


def collect_sephora(args: argparse.Namespace, existing: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], SiteRunStats]:
    stats = SiteRunStats(site="sephora.pl", requested_target=args.per_site)
    records = dedupe_records([r for r in existing if is_valid_training_record(r, site="sephora")])
    seen = {r.get("source_url") for r in records}
    deadline = site_deadline(args)
    session = requests.Session(impersonate="safari17_0")
    categories, product_urls = timed(stats, "catalog_seconds", lambda: cached_catalog(args, "sephora", lambda: sephora_catalog(session)))
    stats.category_count = len(categories)
    stats.category_samples = categories[:30]
    stats.sitemap_url_count = len(product_urls)
    candidates = bounded_candidates(prioritized_sephora_urls(product_urls), args.per_site, args.sample_multiplier)
    collect_products_concurrently(
        stats,
        records,
        seen,
        candidates,
        args=args,
        deadline=deadline,
        site="sephora",
        parser=parse_sephora_product,
    )
    stats.catalog_exhausted = len(records) < args.per_site and stats.attempted >= len(candidates)
    attach_coverage(stats, records, product_urls, args.per_site)
    return records[: args.per_site], stats


def collect_uvex(args: argparse.Namespace, existing: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], SiteRunStats]:
    stats = SiteRunStats(site="uvex.com.pl", requested_target=args.per_site)
    records = dedupe_records([r for r in existing if is_valid_training_record(r, site="uvex")])
    seen = {r.get("source_url") for r in records}
    deadline = site_deadline(args)
    session = requests.Session(impersonate="safari17_0")
    categories, product_urls = timed(stats, "catalog_seconds", lambda: cached_catalog(args, "uvex", lambda: uvex_catalog(session)))
    stats.category_count = len(categories)
    stats.category_samples = categories[:30]
    stats.sitemap_url_count = len(product_urls)
    shuffled = random_sample(product_urls, args.per_site * args.sample_multiplier)
    collect_products_concurrently(
        stats,
        records,
        seen,
        shuffled,
        args=args,
        deadline=deadline,
        site="uvex",
        parser=parse_uvex_product,
    )
    stats.catalog_exhausted = len(records) < args.per_site and stats.attempted >= len(shuffled)
    attach_coverage(stats, records, product_urls, args.per_site)
    return records[: args.per_site], stats


def sephora_catalog(session: Any) -> tuple[list[str], list[str]]:
    index = fetch_text(session, "https://www.sephora.pl/sitemap_index.xml")
    sitemap_urls = xml_locs(index)
    category_urls: list[str] = []
    product_urls: list[str] = []
    for sitemap in sitemap_urls:
        if "category" in sitemap:
            category_urls.extend(xml_locs(fetch_text(session, sitemap)))
        if "product" in sitemap:
            product_urls.extend([u for u in xml_locs(fetch_text(session, sitemap)) if "/p/" in u and u.endswith(".html")])
    return sorted(set(category_urls)), sorted(set(product_urls))


def uvex_catalog(session: Any) -> tuple[list[str], list[str]]:
    category_urls = uvex_category_urls_from_home(session)
    product_urls: set[str] = set()
    for category_url in category_urls:
        product_urls.update(uvex_product_urls_from_category(session, category_url, max_pages=20))
        polite_sleep(0.03)
    return sorted(category_urls), sorted(product_urls)


def uvex_category_urls_from_home(session: Any) -> list[str]:
    text = fetch_text(session, "https://uvex.com.pl/")
    soup = BeautifulSoup(text, "html.parser")
    urls: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = harden_url(str(anchor.get("href") or ""), "https://uvex.com.pl/")
        if not href.startswith("https://uvex.com.pl/produkty/"):
            continue
        if href.rstrip("/") == "https://uvex.com.pl/produkty":
            continue
        urls.add(href.split("#", 1)[0])
    return sorted(urls)


def uvex_product_urls_from_category(session: Any, category_url: str, *, max_pages: int = 10) -> list[str]:
    discovered: set[str] = set()
    queued = [category_url]
    seen_pages: set[str] = set()
    while queued and len(seen_pages) < max_pages:
        url = queued.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        try:
            text = fetch_text(session, url)
        except Exception:
            continue
        soup = BeautifulSoup(text, "html.parser")
        for item in soup.select(".product-item a[href], .product-item-info a[href]"):
            href = str(item.get("href") or "")
            href = harden_url(href, "https://uvex.com.pl/")
            if not href.startswith("https://uvex.com.pl/"):
                continue
            if "/produkty/" in href or "/customer/" in href or "/media/" in href:
                continue
            discovered.add(href.split("#", 1)[0])
        for page in soup.select(".pages a[href]"):
            href = str(page.get("href") or "")
            href = harden_url(href, "https://uvex.com.pl/", keep_query=True)
            if href.startswith("https://uvex.com.pl/") and href not in seen_pages and href not in queued:
                queued.append(href)
    return sorted(discovered)


def collect_products_concurrently(
    stats: SiteRunStats,
    records: list[dict[str, Any]],
    seen: set[str],
    candidates: list[str],
    *,
    args: argparse.Namespace,
    deadline: float | None,
    site: str,
    parser: Any,
) -> None:
    pending = [url for url in candidates if url not in seen]
    workers = max(1, int(args.workers or 1))
    cursor = 0
    while cursor < len(pending) and len(records) < args.per_site:
        if time_exceeded(deadline):
            stats.time_budget_exhausted = True
            break
        batch_size = max(workers * 4, workers)
        batch = pending[cursor: cursor + batch_size]
        cursor += len(batch)
        if not batch:
            break
        batch_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(parse_with_new_session, parser, url, site): url
                for url in batch
                if url not in seen
            }
            for future in as_completed(futures):
                url = futures[future]
                if len(records) >= args.per_site:
                    break
                stats.attempted += 1
                try:
                    record = future.result()
                    accept_or_raise(record, stats, site=site)
                    records.append(record)
                    seen.add(url)
                    stats.accepted += 1
                except Exception as exc:
                    text = str(exc)
                    if "challenge" in text.lower() or "access denied" in text.lower() or "403" in text:
                        stats.blocked += 1
                    stats.failed += 1
                    stats.failures.append({"url": url, "error": text[:300]})
        stats.timing["fetch_parse_seconds"] = stats.timing.get("fetch_parse_seconds", 0.0) + (time.perf_counter() - batch_start)
        polite_sleep(args.sleep)


def parse_with_new_session(parser: Any, url: str, site: str) -> dict[str, Any]:
    session = requests.Session(impersonate="safari17_0")
    return parser(session, url)


def cached_catalog(args: argparse.Namespace, site: str, builder: Any) -> tuple[list[str], list[str]]:
    cache_path = Path(args.catalog_cache_dir) / f"{site}_catalog.json"
    if cache_path.exists() and not args.refresh_catalog:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return list(payload.get("categories") or []), list(payload.get("product_urls") or [])
        except json.JSONDecodeError:
            pass
    categories, product_urls = builder()
    cache_path.write_text(
        json.dumps(
            {
                "site": site,
                "created_at": time.time(),
                "categories": categories,
                "product_urls": product_urls,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return categories, product_urls


def prioritized_sephora_urls(product_urls: list[str]) -> list[str]:
    p_prefixed: list[str] = []
    numeric: list[str] = []
    for url in sorted(set(product_urls)):
        pid = sephora_pid_from_url(url)
        if pid.startswith("P"):
            p_prefixed.append(url)
        else:
            numeric.append(url)
    random.shuffle(p_prefixed)
    random.shuffle(numeric)
    return p_prefixed + numeric


def sephora_pid_from_url(url: str) -> str:
    match = re.search(r"-((?:P)?\d+)\.html", url)
    return match.group(1) if match else ""


def bounded_candidates(product_urls: list[str], target: int, sample_multiplier: int) -> list[str]:
    limit = max(target * max(sample_multiplier, 1), target)
    return list(product_urls)[: min(len(product_urls), limit)]


def parse_sephora_product(session: Any, product_url: str) -> dict[str, Any]:
    pid = sephora_pid_from_url(product_url)
    if not pid:
        raise ValueError("missing Sephora pid in URL")
    detail_url = f"https://www.sephora.pl/on/demandware.store/Sites-Sephora_PL-Site/pl_PL/Product-Detail?pid={pid}"
    text = fetch_text(
        session,
        detail_url,
        headers={
            "x-requested-with": "XMLHttpRequest",
            "referer": product_url,
            "accept": "text/html,application/xhtml+xml,*/*",
        },
    )
    if is_akamai_challenge(text):
        raise RuntimeError("Akamai challenge shell")
    soup = BeautifulSoup(text, "html.parser")
    title = first_text(soup, ["h1", ".product-name"])
    brand = first_text(soup, [".brand-name", "[itemprop='brand']", ".product-brand"])
    subtitle = brand
    variant_texts = [clean_text(x.get_text(" ", strip=True)) for x in soup.select(".variation-selected, .product-variations strong")]
    colors = unique([v for v in variant_texts if v])
    price_values = [float(v) for v in re.findall(r'itemprop="price"\s+content="([0-9.]+)"', text)]
    if not price_values:
        price_values = parse_price_texts([x.get_text(" ", strip=True) for x in soup.select(".product-price")])
    highest_price = max(price_values) if price_values else None
    description = first_text(soup, [
        ".product-description",
        ".product-detail-description",
        ".short-description",
        ".long-description",
        "[itemprop='description']",
        ".product-info-description",
    ])
    if not description:
        description = clean_text(" ".join([x.get_text(" ", strip=True) for x in soup.select(".product-info, .product-content")[:2]]))
    images = unique([
        normalize_img(x.get("data-zoom-image") or x.get("data-src") or x.get("src") or "")
        for x in soup.select("img, a[data-zoom-image]")
        if x.get("data-zoom-image") or x.get("data-src") or x.get("src")
    ])
    category = category_from_url(product_url)
    return {
        "site": "sephora.pl",
        "source_url": product_url,
        "detail_endpoint": detail_url,
        "category": category,
        "title": title,
        "subtitle": subtitle,
        "brand": brand,
        "highest_price_regular": highest_price,
        "currency": "PLN",
        "colors": colors,
        "sizes": [],
        "product_detail": description,
        "image_urls": product_images(images, site="sephora")[:20],
        "status": "ok",
        "access_path": "sfcc_product_detail_endpoint",
    }


def parse_uvex_product(session: Any, product_url: str) -> dict[str, Any]:
    text = fetch_text(session, product_url)
    soup = BeautifulSoup(text, "html.parser")
    body_class = " ".join(soup.body.get("class") if soup.body else [])
    if "catalog-product-view" not in body_class and not soup.select(".product-info-main"):
        raise RuntimeError("not catalog-product-view")
    title = first_text(soup, ["h1", ".page-title", ".base"])
    subtitle = first_text(soup, [".product.attribute.overview", ".value[itemprop='description']"])
    description = first_text(soup, [".product.attribute.description", "#description", ".product-info-main"])
    price_old = attr_float(soup, '[data-price-type="oldPrice"]', "data-price-amount")
    price_final = attr_float(soup, '[data-price-type="finalPrice"]', "data-price-amount")
    cfg = extract_magento_json_config(text)
    sizes: list[str] = []
    colors: list[str] = []
    images: list[str] = []
    if cfg:
        for attr in (cfg.get("attributes") or {}).values():
            label = str(attr.get("label") or attr.get("code") or "").lower()
            opts = [str(opt.get("label") or "") for opt in attr.get("options") or [] if opt.get("label")]
            if "rozmiar" in label or "size" in label:
                sizes.extend(opts)
            elif "kolor" in label or "color" in label:
                colors.extend(opts)
        option_prices = cfg.get("optionPrices") or {}
        old_prices = [safe_float((value.get("oldPrice") or {}).get("amount")) for value in option_prices.values() if isinstance(value, dict)]
        final_prices = [safe_float((value.get("finalPrice") or {}).get("amount")) for value in option_prices.values() if isinstance(value, dict)]
        old_prices = [v for v in old_prices if v is not None]
        final_prices = [v for v in final_prices if v is not None]
        if old_prices:
            price_old = max(old_prices)
        if final_prices and price_final is None:
            price_final = max(final_prices)
        for img_list in (cfg.get("images") or {}).values():
            if isinstance(img_list, list):
                for img in img_list:
                    if isinstance(img, dict):
                        images.extend([img.get("full") or "", img.get("img") or ""])
    images.extend([
        x.get("src") or ""
        for x in soup.select(".product.media img, .gallery-placeholder img, img")
        if x.get("src") and "/media/catalog/product/" in x.get("src")
    ])
    if not colors:
        colors = infer_colors_from_text(title + " " + subtitle)
    return {
        "site": "uvex.com.pl",
        "source_url": product_url,
        "category": category_from_url(product_url),
        "title": title,
        "subtitle": subtitle,
        "brand": urlparse(product_url).path.strip("/").split("/")[0],
        "highest_price_regular": price_old if price_old is not None else price_final,
        "current_price": price_final,
        "currency": "PLN",
        "colors": unique(colors),
        "sizes": unique(sizes),
        "product_detail": description,
        "image_urls": product_images(unique([normalize_img(img) for img in images if img]), site="uvex")[:30],
        "status": "ok",
        "access_path": "magento_product_html",
    }


def accept_or_raise(record: dict[str, Any], stats: SiteRunStats, *, site: str) -> None:
    issues = training_quality_issues(record, site=site)
    if not has_errors(issues):
        return
    stats.rejected_quality += 1
    for issue in issues:
        stats.issue_counts[issue.code] = stats.issue_counts.get(issue.code, 0) + 1
    issue_codes = [issue.code for issue in issues]
    if "invalid_title" in issue_codes:
        stats.rejected_invalid_page += 1
    raise ValueError("quality rejected: " + ", ".join(issue_codes))


def is_valid_training_record(record: dict[str, Any], *, site: str) -> bool:
    return not has_errors(training_quality_issues(record, site=site))


def training_quality_issues(record: dict[str, Any], *, site: str) -> list[Any]:
    normalized = {
        "url": record.get("canonical_url") or record.get("source_url"),
        "title": record.get("title"),
        "highest_price": record.get("highest_price_regular") if record.get("highest_price_regular") is not None else record.get("highest_price"),
        "description": record.get("product_detail") or record.get("description"),
        "image_urls": product_images(list(record.get("image_urls") or []), site=site),
        "category": record.get("category"),
        "dedupe_key": record.get("source_url"),
    }
    return validate_product_record(
        normalized,
        profile={
            "required_fields": ("url", "title", "highest_price", "description", "image_urls", "category"),
            "invalid_title_patterns": (
                r"strona\s+nieodnaleziona",
                r"page\s+not\s+found",
                r"not\s+found",
                r"404",
            ),
            "min_description_length": 8,
        },
    )


def product_images(images: list[str], *, site: str) -> list[str]:
    if site == "sephora":
        return clean_product_images(
            images,
            required_contains=("media.sephora",),
        )
    if site == "uvex":
        return clean_product_images(
            images,
            required_contains=("/media/catalog/product/",),
        )
    return clean_product_images(images)


def attach_coverage(stats: SiteRunStats, records: list[dict[str, Any]], product_urls: list[str], target: int) -> None:
    counters = CoverageCounters(
        estimated_inventory=len(set(product_urls)),
        discovered_urls=len(set(product_urls)),
        attempted_fetches=stats.attempted,
        time_budget_exhausted=stats.time_budget_exhausted,
        fetched_success=stats.accepted + stats.rejected_quality,
        blocked_or_challenged=stats.blocked,
        fetch_failed=max(stats.failed - stats.rejected_quality, 0),
        parsed_records=stats.accepted + stats.rejected_quality,
        quality_passed=len(records),
        quality_failed=stats.rejected_quality,
        exported_unique=len(dedupe_records(records)),
        stale_or_invalid_pages=stats.rejected_invalid_page,
        missing_required_fields=sum(
            count for code, count in stats.issue_counts.items()
            if code in {"missing_title", "unparsable_price", "missing_body", "empty_images", "noise_only_images", "missing_category"}
        ),
        catalog_exhausted=stats.catalog_exhausted,
    )
    stats.coverage_report = build_coverage_report(counters, target_records=target).to_dict()


def timed(stats: SiteRunStats, key: str, fn: Any) -> Any:
    start = time.perf_counter()
    try:
        return fn()
    finally:
        stats.timing[key] = stats.timing.get(key, 0.0) + (time.perf_counter() - start)


def site_deadline(args: argparse.Namespace) -> float | None:
    seconds = float(args.site_time_budget_seconds or 0.0)
    if seconds <= 0:
        seconds = float(args.time_budget_seconds or 0.0) / 2 if float(args.time_budget_seconds or 0.0) > 0 else 0.0
    return time.monotonic() + seconds if seconds > 0 else None


def time_exceeded(deadline: float | None) -> bool:
    return bool(deadline and time.monotonic() >= deadline)


def multi_site_report(summary: Any) -> dict[str, Any]:
    return {
        "total_sites": summary.total_sites,
        "ok_sites": summary.ok_sites,
        "failed_sites": summary.failed_sites,
        "elapsed_seconds": round(summary.elapsed_seconds, 3),
        "results": [
            {
                "name": result.name,
                "ok": result.ok,
                "error": result.error,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
            }
            for result in summary.results
        ],
    }


def fetch_text(session: Any, url: str, headers: dict[str, str] | None = None) -> str:
    merged = dict(HEADERS)
    if headers:
        merged.update(headers)
    cache_dir = DEFAULT_CATALOG_CACHE / "page_cache"
    key = cache_key(url + json.dumps(merged, sort_keys=True))
    cached = read_good_page_cache(cache_dir, key)
    if cached:
        return str(cached.get("text") or "")
    response = session.get(url, headers=merged, timeout=35)
    if response.status_code >= 500:
        raise RuntimeError(f"HTTP {response.status_code}")
    text = response.text
    write_good_page_cache(cache_dir, key, url=url, text=text, status=response.status_code)
    return text


def xml_locs(text: str) -> list[str]:
    try:
        root = ET.fromstring(text.encode("utf-8"))
        return [str(el.text or "").strip() for el in root.iter() if el.tag.endswith("loc") and str(el.text or "").strip()]
    except Exception:
        return [html.unescape(x.strip()) for x in re.findall(r"<loc>(.*?)</loc>", text, flags=re.S)]


def is_akamai_challenge(text: str) -> bool:
    lowered = text.lower()
    return "sec-if-cpt-container" in lowered or "akamai" in lowered or "access denied" in lowered


def first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        found = soup.select_one(selector)
        if found:
            text = clean_text(found.get_text(" ", strip=True))
            if text:
                return text
    return ""


def clean_text(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_price_texts(values: list[str]) -> list[float]:
    prices: list[float] = []
    for value in values:
        for match in re.findall(r"(\d+(?:[\s\xa0]\d{3})*(?:[,.]\d{2})?)\s*z", value, flags=re.I):
            parsed = safe_float(match.replace("\xa0", "").replace(" ", "").replace(",", "."))
            if parsed is not None:
                prices.append(parsed)
    return prices


def attr_float(soup: BeautifulSoup, selector: str, attr: str) -> float | None:
    values = []
    for node in soup.select(selector):
        parsed = safe_float(node.get(attr))
        if parsed is not None:
            values.append(parsed)
    return max(values) if values else None


def safe_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def extract_magento_json_config(text: str) -> dict[str, Any]:
    match = re.search(r'"jsonConfig"\s*:\s*(\{.*?\})\s*,\s*"jsonSwatchConfig"', text, flags=re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def infer_colors_from_text(text: str) -> list[str]:
    colors_pl = [
        "czarn", "bial", "biały", "czerw", "niebies", "zielon", "żółt", "zolty",
        "fiolet", "róż", "roz", "szar", "granat", "khaki", "brąz", "braz",
        "pomarań", "pomaran", "beż", "bez",
    ]
    lowered = text.lower()
    return [token for token in colors_pl if token in lowered]


def normalize_img(url: str) -> str:
    return html.unescape(str(url or "")).replace("\\/", "/").strip()


def category_from_url(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if not parts:
        return ""
    if parts[0] == "p" and len(parts) > 1:
        return "product"
    return " > ".join([part for part in category_levels(parts) if part])


def unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = clean_text(str(value or ""))
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def random_sample(values: list[str], limit: int) -> list[str]:
    unique_values = sorted(set(values))
    random.shuffle(unique_values)
    return unique_values[: min(len(unique_values), max(limit, 0))]


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get("source_url") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(record)
    return output


def polite_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def load_checkpoint(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {"sephora": [], "uvex": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"sephora": [], "uvex": []}
    return {
        "sephora": list(payload.get("sephora") or []),
        "uvex": list(payload.get("uvex") or []),
    }


def save_checkpoint(path: Path, records: dict[str, list[dict[str, Any]]]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def write_outputs(report_path: Path, excel_path: Path, report: dict[str, Any], records: dict[str, list[dict[str, Any]]]) -> None:
    report_payload = dict(report)
    report_payload["samples"] = {
        "sephora": records["sephora"][:10],
        "uvex": records["uvex"][:10],
    }
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    import pandas as pd

    with pd.ExcelWriter(excel_path) as writer:
        for name, rows in records.items():
            normalized = []
            for row in rows:
                item = dict(row)
                item["colors"] = "; ".join(item.get("colors") or [])
                item["sizes"] = "; ".join(item.get("sizes") or [])
                item["image_urls"] = "; ".join(item.get("image_urls") or [])
                normalized.append(item)
            pd.DataFrame(normalized).to_excel(writer, index=False, sheet_name=name[:31])
        summary_rows = []
        for site, stats in report["runs"].items():
            row = dict(stats)
            row.pop("failures", None)
            row.pop("category_samples", None)
            summary_rows.append(row)
        pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="summary")


if __name__ == "__main__":
    raise SystemExit(main())
