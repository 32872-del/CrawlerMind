"""Product-facing workflow helpers for the CLM frontend/API layer.

This module is intentionally product-level glue. It turns crawler primitives
such as HTML recon, SiteProfile, and ProductStore into stable objects that a
frontend can render: catalog trees, field candidates, run specs, progress
events, and export artifacts.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.storage.product_store import ProductStore
from autonomous_crawler.tools.html_recon import build_recon_report, fetch_best_html

from .site_profile import SiteProfile


DEFAULT_PRODUCT_FIELDS = [
    "title",
    "highest_price",
    "colors",
    "sizes",
    "description",
    "image_urls",
    "canonical_url",
    "category_level_1",
    "category_level_2",
    "category_level_3",
]

FIELD_ALIASES = {
    "title": {"title", "name", "product_name", "商品标题", "标题", "名称"},
    "highest_price": {"highest_price", "price", "original_price", "最高价格", "原价", "价格", "吊牌价"},
    "colors": {"colors", "color", "colour", "颜色", "色号"},
    "sizes": {"sizes", "size", "尺码", "规格"},
    "description": {"description", "desc", "body", "详情", "描述", "商品描述"},
    "image_urls": {"image_urls", "images", "image", "main_image", "图片", "主图", "商品图"},
    "canonical_url": {"canonical_url", "url", "link", "商品链接", "详情页"},
    "category_level_1": {"category_level_1", "一级目录", "一级分类"},
    "category_level_2": {"category_level_2", "二级目录", "二级分类"},
    "category_level_3": {"category_level_3", "三级目录", "三级分类"},
}


@dataclass(frozen=True)
class CatalogNode:
    id: str
    label: str
    url: str = ""
    path: list[str] = field(default_factory=list)
    level1: str = ""
    level2: str = ""
    level3: str = ""
    children: list["CatalogNode"] = field(default_factory=list)
    source: str = "agent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "url": self.url,
            "path": list(self.path),
            "level1": self.level1,
            "level2": self.level2,
            "level3": self.level3,
            "source": self.source,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(frozen=True)
class FieldCandidate:
    name: str
    label: str
    selected: bool = True
    source: str = "agent"
    selector: str = ""
    api_path: str = ""
    confidence: float = 0.5
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "selected": self.selected,
            "source": self.source,
            "selector": self.selector,
            "api_path": self.api_path,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExportSpec:
    format: str = "xlsx"
    output_path: str = ""
    template_path: str = ""
    field_mapping: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CrawlRunSpec:
    target_url: str
    profile: dict[str, Any]
    catalog_nodes: list[dict[str, Any]] = field(default_factory=list)
    selected_fields: list[str] = field(default_factory=list)
    export: ExportSpec = field(default_factory=ExportSpec)
    run_mode: str = "direct"
    item_workers: int = 4
    max_sites: int = 1
    test_limit: int = 100
    runtime_dir: str = ""


def import_catalog_tree(payload: Any, *, source: str = "import") -> list[dict[str, Any]]:
    """Normalize nested menu JSON into frontend-friendly catalog nodes."""
    nodes = _catalog_nodes_from_any(payload, path=[], source=source)
    return [node.to_dict() for node in nodes]


def analyze_site_for_product_workflow(
    url: str,
    *,
    imported_catalog: Any = None,
    field_goal: str = "",
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Analyze a site entry URL and return catalog/field/profile draft data."""
    fetch = fetch_best_html(url, headers=headers)
    html = fetch.html or ""
    final_url = fetch.url or url
    recon = build_recon_report(final_url, html) if html else _empty_recon(final_url)
    discovered_catalog = discover_catalog_tree(html, base_url=final_url)
    imported_nodes = import_catalog_tree(imported_catalog, source="import") if imported_catalog else []
    field_candidates = discover_field_candidates(recon, field_goal=field_goal)
    profile = site_profile_from_analysis(
        url=final_url,
        recon=recon,
        catalog_nodes=imported_nodes or discovered_catalog,
        field_candidates=field_candidates,
    )
    return {
        "schema_version": "site-analysis/v1",
        "target_url": url,
        "final_url": final_url,
        "status_code": fetch.status_code,
        "fetch_error": fetch.error,
        "catalog_tree": imported_nodes or discovered_catalog,
        "discovered_catalog_tree": discovered_catalog,
        "imported_catalog_tree": imported_nodes,
        "field_candidates": [field.to_dict() for field in field_candidates],
        "profile": profile.to_dict(),
        "recon_summary": {
            "framework": recon.get("frontend_framework"),
            "rendering": recon.get("rendering"),
            "anti_bot": recon.get("anti_bot"),
            "item_count": recon.get("dom_structure", {}).get("item_count", 0),
            "field_selectors": recon.get("dom_structure", {}).get("field_selectors", {}),
            "product_selector": recon.get("dom_structure", {}).get("product_selector", ""),
        },
    }


def discover_catalog_tree(html: str, *, base_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html or "", "lxml")
    candidates: list[tuple[str, str]] = []
    scopes = soup.select("nav a[href], header a[href], [role=navigation] a[href], .menu a[href], .nav a[href]")
    if not scopes:
        scopes = soup.select("a[href]")
    for anchor in scopes:
        label = _clean_text(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href") or "").strip()
        if not label or not href:
            continue
        url = urljoin(base_url, href)
        if not _looks_like_catalog_url(url, label):
            continue
        candidates.append((label, url))

    deduped: dict[str, tuple[str, str]] = {}
    for label, url in candidates:
        deduped.setdefault(_url_without_fragment(url), (label, _url_without_fragment(url)))
    nodes = [
        CatalogNode(
            id=_stable_id([label], url),
            label=label,
            url=url,
            path=[label],
            level1=label,
            source="agent",
        ).to_dict()
        for label, url in list(deduped.values())[:200]
    ]
    return nodes


def discover_field_candidates(recon: dict[str, Any], *, field_goal: str = "") -> list[FieldCandidate]:
    dom = recon.get("dom_structure") if isinstance(recon.get("dom_structure"), dict) else {}
    selectors = dom.get("field_selectors") if isinstance(dom.get("field_selectors"), dict) else {}
    target_fields = set(_fields_from_text(field_goal))
    fields: list[FieldCandidate] = []
    for name in DEFAULT_PRODUCT_FIELDS:
        selector = _selector_for_field(name, selectors)
        fields.append(
            FieldCandidate(
                name=name,
                label=_field_label(name),
                selected=not target_fields or name in target_fields,
                source="dom" if selector else "default",
                selector=selector,
                confidence=0.85 if selector else 0.45,
                reason="detected from page structure" if selector else "standard ecommerce field",
            )
        )
    for name in sorted(target_fields - {field.name for field in fields}):
        fields.append(
            FieldCandidate(
                name=name,
                label=_field_label(name),
                selected=True,
                source="user_goal",
                confidence=0.4,
                reason="requested by natural language goal",
            )
        )
    return fields


def resolve_fields(
    available_fields: list[dict[str, Any]],
    *,
    natural_language: str = "",
    requested_fields: list[str] | None = None,
) -> dict[str, Any]:
    selected = set(_fields_from_text(natural_language))
    for item in requested_fields or []:
        selected.add(_normalize_field_name(str(item)))
    if not selected:
        selected = {
            str(item.get("name"))
            for item in available_fields
            if isinstance(item, dict) and item.get("selected", True)
        }
    resolved = []
    missing = []
    known = {str(item.get("name")): item for item in available_fields if isinstance(item, dict)}
    for name in sorted(item for item in selected if item):
        if name in known:
            resolved.append({**known[name], "selected": True})
        else:
            missing.append(name)
            resolved.append(FieldCandidate(
                name=name,
                label=_field_label(name),
                selected=True,
                source="user_goal",
                confidence=0.25,
                reason="not detected yet; requires advisor/browser/API refinement",
            ).to_dict())
    return {
        "schema_version": "field-resolution/v1",
        "selected_fields": [item["name"] for item in resolved],
        "resolved_fields": resolved,
        "missing_fields": missing,
        "needs_refinement": bool(missing),
    }


def build_run_spec(payload: dict[str, Any]) -> CrawlRunSpec:
    export_payload = payload.get("export") if isinstance(payload.get("export"), dict) else {}
    return CrawlRunSpec(
        target_url=str(payload.get("target_url") or ""),
        profile=dict(payload.get("profile") or {}),
        catalog_nodes=list(payload.get("catalog_nodes") or []),
        selected_fields=[str(item) for item in payload.get("selected_fields") or [] if str(item).strip()],
        export=ExportSpec(
            format=str(export_payload.get("format") or "xlsx"),
            output_path=str(export_payload.get("output_path") or ""),
            template_path=str(export_payload.get("template_path") or ""),
            field_mapping={str(k): str(v) for k, v in dict(export_payload.get("field_mapping") or {}).items()},
        ),
        run_mode=str(payload.get("run_mode") or "direct"),
        item_workers=max(1, int(payload.get("item_workers") or 4)),
        max_sites=max(1, min(int(payload.get("max_sites") or 1), 5)),
        test_limit=max(1, int(payload.get("test_limit") or 100)),
        runtime_dir=str(payload.get("runtime_dir") or ""),
    )


def profile_from_run_spec(spec: CrawlRunSpec, *, limit: int | None = None) -> SiteProfile:
    profile_data = dict(spec.profile or {})
    selected_nodes = _flatten_catalog_nodes(spec.catalog_nodes)
    seed_urls = [node["url"] for node in selected_nodes if node.get("url")]
    crawl_preferences = dict(profile_data.get("crawl_preferences") or {})
    if seed_urls:
        crawl_preferences["seed_urls"] = seed_urls
        crawl_preferences.setdefault("seed_kind", "list")
    if limit is not None:
        crawl_preferences["max_items"] = int(limit)
    profile_data["crawl_preferences"] = crawl_preferences
    if spec.selected_fields:
        profile_data["target_fields"] = list(spec.selected_fields)
    quality = dict(profile_data.get("quality_expectations") or {})
    if spec.selected_fields:
        quality["required_fields"] = list(spec.selected_fields)
    profile_data["quality_expectations"] = quality
    if not profile_data.get("name"):
        profile_data["name"] = urlparse(spec.target_url).netloc or "frontend-run"
    return SiteProfile.from_dict(profile_data)


def build_test_run_payload(spec: CrawlRunSpec) -> dict[str, Any]:
    return {
        "profile": profile_from_run_spec(spec, limit=spec.test_limit).to_dict(),
        "run_id": f"test-{uuid.uuid4().hex[:8]}",
        "batch_size": min(max(spec.item_workers * 2, 10), 100),
        "max_batches": max(1, (spec.test_limit // max(spec.item_workers * 2, 10)) + 1),
        "item_workers": spec.item_workers,
        "runtime_dir": spec.runtime_dir,
    }


def build_full_run_payload(spec: CrawlRunSpec) -> dict[str, Any]:
    return {
        "profile": profile_from_run_spec(spec, limit=None).to_dict(),
        "run_id": f"full-{uuid.uuid4().hex[:8]}",
        "batch_size": min(max(spec.item_workers * 4, 20), 200),
        "max_batches": 0,
        "item_workers": spec.item_workers,
        "runtime_dir": spec.runtime_dir,
    }


def summarize_run_progress(job: dict[str, Any]) -> dict[str, Any]:
    profile_run = job.get("profile_run") if isinstance(job.get("profile_run"), dict) else {}
    summary = profile_run.get("runner_summary") if isinstance(profile_run.get("runner_summary"), dict) else {}
    frontier = profile_run.get("frontier_stats") if isinstance(profile_run.get("frontier_stats"), dict) else {}
    product_stats = profile_run.get("product_stats") if isinstance(profile_run.get("product_stats"), dict) else {}
    claimed = int(summary.get("claimed") or 0)
    saved = int(summary.get("records_saved") or product_stats.get("total") or job.get("item_count") or 0)
    failed = int(summary.get("failed") or frontier.get("failed") or 0)
    queued = int(frontier.get("queued") or 0)
    done = int(frontier.get("done") or summary.get("succeeded") or 0)
    total_known = max(done + queued + failed, claimed, saved)
    completion = round(done / total_known, 4) if total_known else 0.0
    return {
        "status": job.get("status", "unknown"),
        "records_saved": saved,
        "claimed": claimed,
        "failed": failed,
        "queued": queued,
        "done": done,
        "completion": completion,
        "estimated_remaining_seconds": None,
        "quality": profile_run.get("quality_summary", {}),
    }


def events_for_job(job: dict[str, Any]) -> list[dict[str, Any]]:
    events = [
        {
            "time": job.get("created_at", ""),
            "type": "job_created",
            "message": f"{job.get('user_goal', 'job')} created",
            "data": {"target": job.get("target_url", "")},
        },
        {
            "time": job.get("updated_at", ""),
            "type": f"job_{job.get('status', 'unknown')}",
            "message": f"job status: {job.get('status', 'unknown')}",
            "data": summarize_run_progress(job),
        },
    ]
    result = job.get("profile_run") or job.get("multi_profile_run")
    if isinstance(result, dict) and result.get("failures"):
        for failure in list(result.get("failures") or [])[:50]:
            events.append({
                "time": job.get("updated_at", ""),
                "type": "failure",
                "message": str(failure.get("error") or "crawl item failed"),
                "data": failure,
            })
    return events


def export_product_records(
    *,
    run_id: str,
    runtime_dir: str,
    export_spec: ExportSpec,
) -> dict[str, Any]:
    product_db = Path(runtime_dir) / "products.sqlite3" if runtime_dir else None
    store = ProductStore(product_db)
    records = store.list_records(run_id, limit=1_000_000)
    rows = [_record_to_export_row(record, export_spec.field_mapping) for record in records]
    output = Path(export_spec.output_path or f"dev_logs/exports/{run_id}.{_export_suffix(export_spec.format)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    fmt = export_spec.format.lower()
    if fmt == "json":
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    elif fmt == "csv":
        _write_csv(output, rows)
    elif fmt in {"xlsx", "xls"}:
        _write_xlsx(output, rows, template_path=export_spec.template_path)
    elif fmt in {"sqlite", "db"}:
        if product_db is None or not product_db.exists():
            raise ValueError("runtime_dir with products.sqlite3 is required for sqlite export")
        shutil.copyfile(product_db, output)
    else:
        raise ValueError("format must be json, csv, xlsx, sqlite, or db")
    return {
        "schema_version": "export-result/v1",
        "run_id": run_id,
        "format": fmt,
        "output_path": str(output),
        "record_count": len(rows),
    }


def site_profile_from_analysis(
    *,
    url: str,
    recon: dict[str, Any],
    catalog_nodes: list[dict[str, Any]],
    field_candidates: list[FieldCandidate],
) -> SiteProfile:
    dom = recon.get("dom_structure") if isinstance(recon.get("dom_structure"), dict) else {}
    selectors: dict[str, Any] = {}
    if dom.get("product_selector"):
        selectors["item_container"] = dom.get("product_selector")
    for field in field_candidates:
        if field.selector:
            selectors[field.name] = field.selector
    seed_urls = [node["url"] for node in _flatten_catalog_nodes(catalog_nodes) if node.get("url")]
    if not seed_urls and url:
        seed_urls = [url]
    return SiteProfile.from_dict({
        "name": urlparse(url).netloc or "analyzed-site",
        "selectors": selectors,
        "target_fields": [field.name for field in field_candidates if field.selected],
        "pagination_hints": {"type": "dom_links"},
        "crawl_preferences": {
            "seed_urls": seed_urls[:500],
            "seed_kind": "list",
            "catalog_tree": catalog_nodes,
        },
        "quality_expectations": {
            "required_fields": ["title"],
            "field_thresholds": {"title": 0.8},
        },
    })


def _catalog_nodes_from_any(value: Any, *, path: list[str], source: str) -> list[CatalogNode]:
    nodes: list[CatalogNode] = []
    if isinstance(value, dict):
        for label, child in value.items():
            text = _clean_text(str(label))
            child_path = [*path, text] if text else list(path)
            if isinstance(child, str):
                nodes.append(_leaf_node(text, child, child_path, source))
            elif isinstance(child, (dict, list)):
                children = _catalog_nodes_from_any(child, path=child_path, source=source)
                nodes.append(CatalogNode(
                    id=_stable_id(child_path, ""),
                    label=text,
                    path=child_path,
                    level1=_level(child_path, 0),
                    level2=_level(child_path, 1),
                    level3=_level(child_path, 2),
                    children=children,
                    source=source,
                ))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and ("url" in item or "label" in item):
                label = _clean_text(str(item.get("label") or item.get("name") or item.get("title") or item.get("url") or ""))
                item_path = [str(part) for part in (item.get("path") or [*path, label]) if str(part).strip()]
                children = _catalog_nodes_from_any(item.get("children"), path=item_path, source=source) if item.get("children") else []
                nodes.append(CatalogNode(
                    id=str(item.get("id") or _stable_id(item_path, str(item.get("url") or ""))),
                    label=label,
                    url=str(item.get("url") or ""),
                    path=item_path,
                    level1=str(item.get("level1") or _level(item_path, 0)),
                    level2=str(item.get("level2") or _level(item_path, 1)),
                    level3=str(item.get("level3") or _level(item_path, 2)),
                    children=children,
                    source=str(item.get("source") or source),
                ))
            elif isinstance(item, (dict, list)):
                nodes.extend(_catalog_nodes_from_any(item, path=path, source=source))
    return nodes


def _leaf_node(label: str, url: str, path: list[str], source: str) -> CatalogNode:
    return CatalogNode(
        id=_stable_id(path, url),
        label=label,
        url=url,
        path=path,
        level1=_level(path, 0),
        level2=_level(path, 1),
        level3=_level(path, 2),
        source=source,
    )


def _flatten_catalog_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        if node.get("url"):
            flat.append(node)
        flat.extend(_flatten_catalog_nodes(list(node.get("children") or [])))
    return flat


def _record_to_export_row(record: ProductRecord, mapping: dict[str, str]) -> dict[str, Any]:
    path = [part for part in str(record.category or "").split(">") if part.strip()]
    raw = {
        "title": record.title,
        "highest_price": record.highest_price,
        "currency": record.currency,
        "colors": "; ".join(record.colors),
        "sizes": "; ".join(record.sizes),
        "description": record.description,
        "image_urls": "; ".join(record.image_urls),
        "canonical_url": record.canonical_url,
        "source_url": record.source_url,
        "category": record.category,
        "category_level_1": _level(path, 0),
        "category_level_2": _level(path, 1),
        "category_level_3": _level(path, 2),
    }
    if not mapping:
        return raw
    return {target: raw.get(source, "") for source, target in mapping.items()}


def _write_csv(output: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_xlsx(output: Path, rows: list[dict[str, Any]], *, template_path: str = "") -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required for xlsx export") from exc
    if template_path and Path(template_path).exists():
        # MVP behavior: keep template support explicit but data-first. A later
        # slice can write into exact cell coordinates once TemplateSpec is added.
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as _tmp:
            pass
    pd.DataFrame(rows).to_excel(output, index=False)


def _fields_from_text(text: str) -> list[str]:
    lowered = str(text or "").lower()
    found: list[str] = []
    for canonical, aliases in FIELD_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            found.append(canonical)
    return found


def _normalize_field_name(name: str) -> str:
    text = name.strip().lower()
    for canonical, aliases in FIELD_ALIASES.items():
        if text == canonical or text in {alias.lower() for alias in aliases}:
            return canonical
    return re.sub(r"[^a-z0-9_]+", "_", text).strip("_")


def _selector_for_field(name: str, selectors: dict[str, Any]) -> str:
    if name in selectors:
        return str(selectors[name])
    aliases = FIELD_ALIASES.get(name, set())
    for key, value in selectors.items():
        if key in aliases or str(key).lower() in {alias.lower() for alias in aliases}:
            return str(value)
    if name == "highest_price" and selectors.get("price"):
        return str(selectors["price"])
    if name == "image_urls" and selectors.get("image"):
        return str(selectors["image"])
    return ""


def _field_label(name: str) -> str:
    labels = {
        "title": "商品标题",
        "highest_price": "最高价格",
        "colors": "颜色",
        "sizes": "尺码",
        "description": "商品描述",
        "image_urls": "商品图URL",
        "canonical_url": "商品详情URL",
        "category_level_1": "一级目录",
        "category_level_2": "二级目录",
        "category_level_3": "三级目录",
    }
    return labels.get(name, name)


def _looks_like_catalog_url(url: str, label: str) -> bool:
    lower = f"{url} {label}".lower()
    positive = (
        "category", "collection", "collections", "catalog", "shop", "product-category",
        "women", "men", "kids", "sale", "outlet", "new", "nowosci", "kobieta",
        "mezczyzna", "produkty", "akcesoria",
    )
    negative = ("login", "account", "cart", "checkout", "privacy", "terms", "contact", "blog")
    return any(token in lower for token in positive) and not any(token in lower for token in negative)


def _url_without_fragment(url: str) -> str:
    return str(url).split("#", 1)[0]


def _stable_id(path: list[str], url: str) -> str:
    import hashlib

    raw = " > ".join(path) + "|" + str(url)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _level(path: list[str], index: int) -> str:
    return str(path[index]) if len(path) > index else ""


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _empty_recon(url: str) -> dict[str, Any]:
    return {
        "url": url,
        "framework": "unknown",
        "rendering": "unknown",
        "anti_bot": False,
        "dom_structure": {"item_count": 0, "field_selectors": {}, "product_selector": ""},
    }


def _export_suffix(fmt: str) -> str:
    value = str(fmt or "xlsx").lower()
    return "sqlite3" if value in {"sqlite", "db"} else value
