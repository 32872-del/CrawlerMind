"""CLM-native robots policy helper.

SCRAPLING-ABSORB-3D provides a small, explicit robots layer that can run in
`respect`, `record_only`, or `disabled` mode and emit runtime events for spider
training and checkpoint evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

from autonomous_crawler.runtime import RuntimeEvent


ROBOTS_MODES = {"respect", "record_only", "disabled"}


@dataclass(frozen=True)
class RobotsDirectives:
    can_fetch: bool
    crawl_delay_seconds: float | None = None
    request_rate: tuple[int, int] | None = None
    source_url: str = ""
    error: str = ""
    mode: str = "respect"

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_fetch": self.can_fetch,
            "crawl_delay_seconds": self.crawl_delay_seconds,
            "request_rate": list(self.request_rate) if self.request_rate else None,
            "source_url": self.source_url,
            "error": self.error,
            "mode": self.mode,
        }


class RobotsPolicyHelper:
    """Fetch, cache, and evaluate robots.txt directives."""

    def __init__(
        self,
        *,
        mode: str = "respect",
        user_agent: str = "*",
        fetcher: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.mode = mode if mode in ROBOTS_MODES else "respect"
        self.user_agent = user_agent or "*"
        self.fetcher = fetcher
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._cache: dict[str, tuple[RobotFileParser | None, str]] = {}

    def can_fetch(self, url: str, *, user_agent: str = "") -> bool:
        return self.get_directives(url, user_agent=user_agent).can_fetch

    def get_directives(self, url: str, *, user_agent: str = "") -> RobotsDirectives:
        robots_url = robots_url_for(url)
        if self.mode == "disabled":
            return RobotsDirectives(can_fetch=True, source_url=robots_url, mode=self.mode)
        parser, error = self._parser_for(robots_url)
        if parser is None:
            return RobotsDirectives(
                can_fetch=True,
                source_url=robots_url,
                error=error,
                mode=self.mode,
            )
        ua = user_agent or self.user_agent
        allowed = parser.can_fetch(ua, url)
        if self.mode == "record_only":
            allowed = True
        request_rate = parser.request_rate(ua)
        return RobotsDirectives(
            can_fetch=allowed,
            crawl_delay_seconds=parser.crawl_delay(ua),
            request_rate=(request_rate.requests, request_rate.seconds) if request_rate else None,
            source_url=robots_url,
            mode=self.mode,
        )

    def prefetch(self, urls: list[str], *, user_agent: str = "") -> None:
        for url in urls:
            self.get_directives(url, user_agent=user_agent)

    def to_events(self, url: str, *, user_agent: str = "") -> list[RuntimeEvent]:
        directives = self.get_directives(url, user_agent=user_agent)
        return [
            RuntimeEvent(
                type="spider.robots_checked",
                message="robots policy checked",
                data=directives.to_dict(),
            )
        ]

    def _parser_for(self, robots_url: str) -> tuple[RobotFileParser | None, str]:
        if robots_url in self._cache:
            return self._cache[robots_url]
        try:
            text = self._fetch_robots(robots_url)
            parser = RobotFileParser(robots_url)
            parser.parse(text.splitlines())
            result = (parser, "")
        except Exception as exc:
            result = (None, f"{type(exc).__name__}: {exc}")
        self._cache[robots_url] = result
        return result

    def _fetch_robots(self, robots_url: str) -> str:
        if self.fetcher is not None:
            result = self.fetcher(robots_url)
            if hasattr(result, "text"):
                return str(result.text)
            return str(result)
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(robots_url)
            response.raise_for_status()
            return response.text


def robots_url_for(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme or "https", parsed.netloc, "/robots.txt", "", "", ""))
