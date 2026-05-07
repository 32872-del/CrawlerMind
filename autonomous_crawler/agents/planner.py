"""Planner Agent - parses user intent and determines crawl objective."""
from __future__ import annotations

import re
import uuid
from typing import Any, Callable

from .base import preserve_state
from ..llm.protocols import PlanningAdvisor
from ..llm.audit import build_decision_record


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


_PLANNER_ALLOWED_FIELDS = frozenset({
    "task_type", "target_fields", "max_items",
    "crawl_preferences", "constraints", "reasoning_summary",
})


def make_planner_node(
    advisor: PlanningAdvisor | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Return a planner node, optionally wrapping a planning advisor.

    When no advisor is provided, the returned node is equivalent to
    ``planner_node`` but always emits the LLM audit state fields.
    """

    def _node(state: dict[str, Any]) -> dict[str, Any]:
        result = planner_node(state)

        if advisor is None:
            result["llm_enabled"] = False
            result["llm_decisions"] = []
            result["llm_errors"] = []
            return result

        result["llm_enabled"] = True
        decisions: list[dict[str, Any]] = list(state.get("llm_decisions") or [])
        errors: list[str] = list(state.get("llm_errors") or [])

        user_goal = state.get("user_goal", "")
        target_url = state.get("target_url", "")
        fallback_used = False
        accepted: list[str] = []
        rejected: list[str] = []

        try:
            advisor_output = advisor.plan(user_goal, target_url)
            advisor_fields = {
                k: v for k, v in advisor_output.items()
                if k in _PLANNER_ALLOWED_FIELDS
            }
            rejected = [
                k for k in advisor_output if k not in _PLANNER_ALLOWED_FIELDS
            ]

            recon = result.get("recon_report", {})

            if "task_type" in advisor_fields:
                recon["task_type"] = advisor_fields["task_type"]
                accepted.append("task_type")

            if "target_fields" in advisor_fields:
                recon["target_fields"] = advisor_fields["target_fields"]
                accepted.append("target_fields")

            if "max_items" in advisor_fields:
                constraints = recon.get("constraints", {})
                existing = constraints.get("max_items")
                advisor_val = advisor_fields["max_items"]
                if existing and existing != advisor_val:
                    rejected.append("max_items (conflict)")
                else:
                    constraints["max_items"] = advisor_val
                    recon["constraints"] = constraints
                    accepted.append("max_items")

            if "constraints" in advisor_fields:
                constraints = recon.get("constraints", {})
                for k, v in advisor_fields["constraints"].items():
                    if k not in constraints:
                        constraints[k] = v
                        accepted.append(f"constraints.{k}")
                recon["constraints"] = constraints

            if "crawl_preferences" in advisor_fields:
                accepted.append("crawl_preferences")
                recon["crawl_preferences"] = advisor_fields["crawl_preferences"]

            result["recon_report"] = recon

            decisions.append(build_decision_record(
                node="planner",
                advisor=advisor,
                input_summary=f"goal={user_goal[:100]} url={target_url[:100]}",
                raw_response=advisor_output,
                parsed_decision=advisor_fields,
                accepted_fields=accepted,
                rejected_fields=rejected,
                fallback_used=False,
            ))

        except Exception as exc:
            fallback_used = True
            errors.append(f"planner advisor: {exc}")
            decisions.append(build_decision_record(
                node="planner",
                advisor=advisor,
                input_summary=f"goal={user_goal[:100]} url={target_url[:100]}",
                raw_response=str(exc),
                parsed_decision={},
                accepted_fields=[],
                rejected_fields=list(_PLANNER_ALLOWED_FIELDS),
                fallback_used=True,
            ))

        if fallback_used:
            result.setdefault("messages", [])
            result["messages"] = result.get("messages", []) + [
                "[Planner] Advisor failed, using deterministic fallback"
            ]

        result["llm_decisions"] = decisions
        result["llm_errors"] = errors
        return result

    return _node
