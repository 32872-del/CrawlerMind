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
from .adaptive_parser import AdaptiveMatch, ElementSignature, build_element_signature, find_similar, relocate, similarity_score
from .browser_pool import BrowserContextLease, BrowserPoolConfig, BrowserPoolManager, BrowserProfile, BrowserProfileHealth, BrowserProfileHealthStore, BrowserProfileRotator
from .native_async import AsyncFetchMetrics, DomainConcurrencyPool, NativeAsyncFetchRuntime
from .native_browser import NativeBrowserRuntime
from .native_static import NativeFetchRuntime
from .protocols import BrowserRuntime, FetchRuntime, ParserRuntime, ProxyRuntime, SessionRuntime, SpiderRuntime
from .native_parser import NativeParserRuntime
from .scrapling_browser import ScraplingBrowserRuntime
from .scrapling_parser import ScraplingParserRuntime
from .scrapling_static import ScraplingStaticRuntime

__all__ = [
    "AsyncFetchMetrics",
    "BrowserContextLease",
    "BrowserPoolConfig",
    "BrowserPoolManager",
    "BrowserProfile",
    "BrowserProfileHealth",
    "BrowserProfileHealthStore",
    "BrowserProfileRotator",
    "BrowserRuntime",
    "AdaptiveMatch",
    "DomainConcurrencyPool",
    "ElementSignature",
    "FetchRuntime",
    "NativeAsyncFetchRuntime",
    "NativeBrowserRuntime",
    "NativeFetchRuntime",
    "NativeParserRuntime",
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
    "build_element_signature",
    "find_similar",
    "relocate",
    "similarity_score",
]
