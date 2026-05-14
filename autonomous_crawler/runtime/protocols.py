"""Runtime backend protocols.

Concrete crawler engines implement these protocols.  The workflow layer should
depend on these interfaces rather than concrete libraries such as Scrapling,
Playwright, httpx, or fnspider.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import RuntimeRequest, RuntimeResponse, RuntimeSelectorRequest, RuntimeSelectorResult


@runtime_checkable
class FetchRuntime(Protocol):
    """Static HTTP/API runtime contract."""

    name: str

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        """Fetch a static HTTP/API resource and return a normalized response."""
        ...


@runtime_checkable
class BrowserRuntime(Protocol):
    """Browser rendering runtime contract."""

    name: str

    def render(self, request: RuntimeRequest) -> RuntimeResponse:
        """Render a page in a browser-capable runtime and return normalized output."""
        ...


@runtime_checkable
class ParserRuntime(Protocol):
    """HTML parser runtime contract."""

    name: str

    def parse(
        self,
        html: str,
        selectors: list[RuntimeSelectorRequest],
        *,
        url: str = "",
    ) -> list[RuntimeSelectorResult]:
        """Extract selector results from HTML."""
        ...


@runtime_checkable
class SpiderRuntime(Protocol):
    """Long-running crawler runtime contract."""

    name: str

    def crawl(self, request: RuntimeRequest) -> RuntimeResponse:
        """Run a checkpointable crawl and return normalized summary/results."""
        ...


@runtime_checkable
class ProxyRuntime(Protocol):
    """Proxy mapping/rotation runtime contract."""

    name: str

    def select_proxy(self, request: RuntimeRequest) -> dict:
        """Return a credential-safe proxy selection payload."""
        ...


@runtime_checkable
class SessionRuntime(Protocol):
    """Session continuity runtime contract."""

    name: str

    def prepare_session(self, request: RuntimeRequest) -> RuntimeRequest:
        """Return a request enriched with runtime session continuity settings."""
        ...
