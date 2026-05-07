"""FastAPI app factory for the autonomous crawler service."""
from .app import app, create_app, run_crawl_workflow

__all__ = ["app", "create_app", "run_crawl_workflow"]
