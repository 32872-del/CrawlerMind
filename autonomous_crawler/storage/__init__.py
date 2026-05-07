"""Storage helpers for autonomous crawler results."""
from .result_store import (
    CrawlResultStore,
    list_crawl_results,
    load_crawl_result,
    save_crawl_result,
)

__all__ = [
    "CrawlResultStore",
    "list_crawl_results",
    "load_crawl_result",
    "save_crawl_result",
]
