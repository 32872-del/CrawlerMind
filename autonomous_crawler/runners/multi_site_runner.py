"""Run multiple site crawl jobs concurrently with a hard site limit."""
from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable


SiteJob = Callable[[], Any]


@dataclass(frozen=True)
class MultiSiteRunnerConfig:
    max_sites: int = 5

    def __post_init__(self) -> None:
        if self.max_sites < 1:
            raise ValueError("max_sites must be >= 1")
        if self.max_sites > 5:
            raise ValueError("max_sites cannot exceed 5")


@dataclass
class SiteJobResult:
    name: str
    ok: bool
    result: Any = None
    error: str = ""
    traceback: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


@dataclass
class MultiSiteRunSummary:
    total_sites: int
    ok_sites: int
    failed_sites: int
    elapsed_seconds: float
    results: list[SiteJobResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sites": self.total_sites,
            "ok_sites": self.ok_sites,
            "failed_sites": self.failed_sites,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "results": [result.to_dict() for result in self.results],
        }


class MultiSiteRunner:
    """Execute up to five site jobs concurrently."""

    def __init__(self, jobs: dict[str, SiteJob], config: MultiSiteRunnerConfig | None = None) -> None:
        self.jobs = dict(jobs)
        self.config = config or MultiSiteRunnerConfig()
        if len(self.jobs) > self.config.max_sites:
            raise ValueError(f"Too many site jobs: {len(self.jobs)} > {self.config.max_sites}")

    def run(self) -> MultiSiteRunSummary:
        started = time.perf_counter()
        results: list[SiteJobResult] = []
        with ThreadPoolExecutor(max_workers=min(self.config.max_sites, max(len(self.jobs), 1))) as executor:
            futures = {executor.submit(self._run_one, name, job): name for name, job in self.jobs.items()}
            for future in as_completed(futures):
                results.append(future.result())
        elapsed = time.perf_counter() - started
        ok = sum(1 for result in results if result.ok)
        return MultiSiteRunSummary(
            total_sites=len(results),
            ok_sites=ok,
            failed_sites=len(results) - ok,
            elapsed_seconds=elapsed,
            results=sorted(results, key=lambda item: item.name),
        )

    @staticmethod
    def _run_one(name: str, job: SiteJob) -> SiteJobResult:
        started = time.perf_counter()
        try:
            return SiteJobResult(name=name, ok=True, result=job(), elapsed_seconds=time.perf_counter() - started)
        except Exception as exc:
            return SiteJobResult(
                name=name,
                ok=False,
                error=str(exc)[:1000],
                traceback=traceback.format_exc(limit=10),
                elapsed_seconds=time.perf_counter() - started,
            )
