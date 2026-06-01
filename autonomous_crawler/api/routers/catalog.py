"""Catalog import endpoint."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...runners.product_workflow import import_catalog_tree
from ..deps import load_json_file
from ..schemas import CatalogImportRequest, SiteAnalyzeRequest

router = APIRouter()


def _catalog_payload_from_request(request: CatalogImportRequest | SiteAnalyzeRequest) -> Any:
    payload = getattr(request, "catalog", None)
    if payload is not None:
        return payload
    imported = getattr(request, "imported_catalog", None)
    if imported is not None:
        return imported
    path = str(getattr(request, "catalog_path", "") or getattr(request, "imported_catalog_path", "") or "").strip()
    if path:
        return load_json_file(path)
    return None


def _count_catalog_nodes(nodes: list[dict[str, Any]]) -> int:
    return sum(1 + _count_catalog_nodes(list(node.get("children") or [])) for node in nodes if isinstance(node, dict))


def _count_catalog_leaves(nodes: list[dict[str, Any]]) -> int:
    total = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        children = list(node.get("children") or [])
        if node.get("url"):
            total += 1
        total += _count_catalog_leaves(children)
    return total


@router.post("/catalog/import")
def catalog_import(request: CatalogImportRequest) -> dict[str, Any]:
    try:
        payload = _catalog_payload_from_request(request)
        if payload is None:
            raise ValueError("catalog or catalog_path is required")
        nodes = import_catalog_tree(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "schema_version": "catalog-tree/v1",
        "catalog_tree": nodes,
        "node_count": _count_catalog_nodes(nodes),
        "leaf_count": _count_catalog_leaves(nodes),
    }
