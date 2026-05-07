"""Planner Agent - parses user intent and determines crawl objective."""
from __future__ import annotations

import re
import uuid
from typing import Any

from .base import preserve_state


FIELD_KEYWORDS = {
    "rank": ["rank", "ranking", "排名", "排行", "榜单", "榜"],
    "title": ["title", "name", "标题", "名称", "商品名", "产品名", "词条", "热搜"],
    "price": ["price", "价格", "售价", "价钱", "金额"],
    "image": ["image", "img", "photo", "picture", "图片", "主图", "照片"],
    "description": ["description", "desc", "描述", "详情", "介绍", "摘要", "简介"],
    "summary": ["summary", "摘要", "简介", "描述"],
    "hot_score": ["hot", "score", "指数", "热度", "热搜指数"],
    "size": ["size", "尺寸", "尺码", "规格"],
    "color": ["color", "colour", "颜色", "色号"],
    "stock": ["stock", "inventory", "库存", "现货"],
    "url": ["url", "link", "链接", "地址"],
}

RANKING_KEYWORDS = ["热搜", "榜", "排行", "排名", "top", "前"]
PRODUCT_KEYWORDS = ["商品", "产品", "价格", "库存", "尺码", "颜色"]


@preserve_state
def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    """Parse user goal and produce a structured crawl objective.

    This MVP planner uses deterministic keyword rules. Later versions can swap
    this for an LLM-backed structured parser while preserving the same state
    contract.
    """
    user_goal = state.get("user_goal", "")
    goal_lower = user_goal.lower()

    fields = _extract_fields(goal_lower)
    task_type = _detect_task_type(goal_lower)
    max_items = _extract_max_items(user_goal)

    if not fields:
        fields = ["rank", "title", "hot_score"] if task_type == "ranking_list" else ["title", "price"]

    task_id = state.get("task_id") or str(uuid.uuid4())[:8]

    return {
        "task_id": task_id,
        "status": "planned",
        "messages": state.get("messages", []) + [f"[Planner] Goal: {user_goal}"],
        "recon_report": {
            "target_fields": fields,
            "task_type": task_type,
            "constraints": {"max_items": max_items} if max_items else {},
        },
        "error_log": [],
    }


def _extract_fields(goal_lower: str) -> list[str]:
    fields = []
    for field_name, keywords in FIELD_KEYWORDS.items():
        if any(keyword in goal_lower for keyword in keywords):
            fields.append(field_name)
    if "rank" in fields and "title" not in fields:
        fields.append("title")
    return fields


def _detect_task_type(goal_lower: str) -> str:
    if any(keyword in goal_lower for keyword in RANKING_KEYWORDS):
        return "ranking_list"
    if any(keyword in goal_lower for keyword in PRODUCT_KEYWORDS):
        return "product_list"
    return "product_list"


def _extract_max_items(user_goal: str) -> int | None:
    patterns = [
        r"前\s*(\d+)\s*条",
        r"top\s*(\d+)",
        r"(\d+)\s*条",
    ]
    goal_lower = user_goal.lower()
    for pattern in patterns:
        match = re.search(pattern, goal_lower, re.I)
        if match:
            return int(match.group(1))
    return None
