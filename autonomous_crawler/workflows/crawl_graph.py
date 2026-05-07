"""LangGraph workflow definition for the autonomous crawler.

Workflow (README Section 8):
START -> Planner -> Recon -> Generate Strategy -> Execute Crawl ->
Extract Data -> Validate -> Retry/Replan -> END

Retry Logic (README Section 11):
    if validation_failed:
        if retries < max_retries:
            retries += 1
            goto("strategy_agent")
        else:
            fail_task()
"""
from __future__ import annotations

from typing import Annotated, Any
from operator import add

from langgraph.graph import StateGraph, START, END

from ..agents.planner import planner_node
from ..agents.recon import recon_node
from ..agents.strategy import strategy_node
from ..agents.executor import executor_node
from ..agents.extractor import extractor_node
from ..agents.validator import validator_node


# --- State Schema with Reducers ---
# Using Annotated with add so messages accumulate across nodes.
# All other fields use last-write-wins (no Annotated needed).

def _merge_messages(existing: list, new: list) -> list:
    return existing + new


def _sum_ints(existing: int, new: int) -> int:
    return existing + new


# We define the schema as a dict but configure reducers via add_reducer.
# LangGraph supports this pattern with StateGraph(dict) + custom reducers.

def _route_after_validation(state: dict[str, Any]) -> str:
    """Conditional edge router after validation."""
    status = state.get("status", "")
    if status == "completed":
        return "end"
    elif status == "retrying":
        return "retry"
    return "end"


def _route_after_recon(state: dict[str, Any]) -> str:
    """Skip strategy/execution if recon failed."""
    if state.get("status") == "recon_failed":
        return "fail_fast"
    return "continue"


def build_crawl_graph() -> StateGraph:
    """Build and return the crawl workflow graph (not compiled)."""
    graph = StateGraph(dict)

    # Register nodes
    graph.add_node("planner", planner_node)
    graph.add_node("recon", recon_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("executor", executor_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("validator", validator_node)

    # Linear flow
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "recon")
    graph.add_conditional_edges(
        "recon",
        _route_after_recon,
        {
            "continue": "strategy",
            "fail_fast": END,
        },
    )
    graph.add_edge("strategy", "executor")
    graph.add_edge("executor", "extractor")
    graph.add_edge("extractor", "validator")

    # Conditional edge: validator -> retry or END
    graph.add_conditional_edges(
        "validator",
        _route_after_validation,
        {
            "retry": "strategy",
            "end": END,
        },
    )

    return graph


def compile_crawl_graph():
    """Compile and return the runnable crawl graph."""
    graph = build_crawl_graph()
    return graph.compile()
