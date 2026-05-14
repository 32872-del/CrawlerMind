"""CLM crawler runtime protocol layer.

Runtime modules expose crawler backend capabilities through CLM-owned models
and protocols. Concrete engines such as httpx, fnspider, Playwright, or
Scrapling adapters should plug in here instead of leaking engine-specific
classes into workflow/business layers.
"""
from .models import (
    RuntimeArtifact,
    RuntimeEvent,
    RuntimeProxyTrace,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
    RuntimeSelectorResult,
)
from .protocols import BrowserRuntime, FetchRuntime, ParserRuntime, ProxyRuntime, SessionRuntime, SpiderRuntime
from .scrapling_browser import ScraplingBrowserRuntime
from .scrapling_parser import ScraplingParserRuntime
from .scrapling_static import ScraplingStaticRuntime

__all__ = [
    "BrowserRuntime",
    "FetchRuntime",
    "ParserRuntime",
    "ProxyRuntime",
    "RuntimeArtifact",
    "RuntimeEvent",
    "RuntimeProxyTrace",
    "RuntimeRequest",
    "RuntimeResponse",
    "RuntimeSelectorRequest",
    "RuntimeSelectorResult",
    "ScraplingBrowserRuntime",
    "ScraplingParserRuntime",
    "ScraplingStaticRuntime",
    "SessionRuntime",
    "SpiderRuntime",
]
