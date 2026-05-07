"""Base utilities for agent nodes."""
from __future__ import annotations

import functools
from typing import Any, Callable


def preserve_state(fn: Callable) -> Callable:
    """Decorator that merges node output with existing state.

    Problem: LangGraph's dict merge overwrites the entire value for each key.
    If a node returns only partial state, fields from previous nodes are lost.

    Solution: This decorator ensures the node's return is merged ON TOP of
    the existing state, so all fields from previous nodes are preserved.
    """
    @functools.wraps(fn)
    def wrapper(state: dict[str, Any]) -> dict[str, Any]:
        node_output = fn(state)
        # Merge: start with existing state, overlay node output
        merged = {**state, **node_output}
        return merged
    return wrapper
