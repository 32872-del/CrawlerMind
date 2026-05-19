"""Backpressure signal collector and throttle advisor for batch runners.

Monitors batch-level metrics (latency, failure rate, retry rate, quality loss)
and produces a throttle recommendation: proceed, slow_down, pause, or abort.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackpressureConfig:
    """Thresholds for backpressure signal evaluation."""

    latency_warn_ms: float = 5000.0
    latency_pause_ms: float = 15000.0
    failure_rate_warn: float = 0.15
    failure_rate_pause: float = 0.40
    retry_rate_warn: float = 0.25
    quality_loss_warn: float = 0.10
    consecutive_slow_threshold: int = 3

    def as_dict(self) -> dict[str, Any]:
        return {
            "latency_warn_ms": self.latency_warn_ms,
            "latency_pause_ms": self.latency_pause_ms,
            "failure_rate_warn": self.failure_rate_warn,
            "failure_rate_pause": self.failure_rate_pause,
            "retry_rate_warn": self.retry_rate_warn,
            "quality_loss_warn": self.quality_loss_warn,
            "consecutive_slow_threshold": self.consecutive_slow_threshold,
        }


@dataclass
class BackpressureSignals:
    """Snapshot of accumulated backpressure signals."""

    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    retry_rate: float = 0.0
    failure_rate: float = 0.0
    quality_loss_rate: float = 0.0
    consecutive_slow_batches: int = 0
    total_batches: int = 0
    recommendation: str = "proceed"
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "retry_rate": round(self.retry_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "quality_loss_rate": round(self.quality_loss_rate, 4),
            "consecutive_slow_batches": self.consecutive_slow_batches,
            "total_batches": self.total_batches,
            "recommendation": self.recommendation,
            "reason": self.reason,
        }


class BackpressureMonitor:
    """Collects per-batch signals and computes a throttle recommendation."""

    def __init__(self, config: BackpressureConfig | None = None) -> None:
        self.config = config or BackpressureConfig()
        self._latencies: list[float] = []
        self._total_claimed: int = 0
        self._total_succeeded: int = 0
        self._total_failed: int = 0
        self._total_retried: int = 0
        self._total_checkpoint_errors: int = 0
        self._consecutive_slow: int = 0

    def record_batch(
        self,
        batch_latency_ms: float,
        claimed: int,
        succeeded: int,
        failed: int,
        retried: int,
        checkpoint_errors: int = 0,
    ) -> None:
        """Record metrics from a single batch execution."""
        self._latencies.append(batch_latency_ms)
        self._total_claimed += claimed
        self._total_succeeded += succeeded
        self._total_failed += failed
        self._total_retried += retried
        self._total_checkpoint_errors += checkpoint_errors

        if batch_latency_ms >= self.config.latency_warn_ms:
            self._consecutive_slow += 1
        else:
            self._consecutive_slow = 0

    def current_signals(self) -> BackpressureSignals:
        """Compute current state and recommendation."""
        signals = BackpressureSignals()

        if not self._latencies:
            return signals

        signals.total_batches = len(self._latencies)
        signals.avg_latency_ms = sum(self._latencies) / len(self._latencies)

        sorted_latencies = sorted(self._latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        signals.p95_latency_ms = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]

        if self._total_claimed > 0:
            signals.retry_rate = self._total_retried / self._total_claimed
            signals.failure_rate = self._total_failed / self._total_claimed
            signals.quality_loss_rate = self._total_checkpoint_errors / self._total_claimed

        signals.consecutive_slow_batches = self._consecutive_slow

        recommendation, reason = self._evaluate(signals)
        signals.recommendation = recommendation
        signals.reason = reason
        return signals

    def should_pause(self) -> bool:
        """Check if current signals warrant a pause."""
        return self.current_signals().recommendation in ("pause", "abort")

    def should_abort(self) -> bool:
        """Check if current signals warrant an abort."""
        return self.current_signals().recommendation == "abort"

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._latencies.clear()
        self._total_claimed = 0
        self._total_succeeded = 0
        self._total_failed = 0
        self._total_retried = 0
        self._total_checkpoint_errors = 0
        self._consecutive_slow = 0

    def _evaluate(self, signals: BackpressureSignals) -> tuple[str, str]:
        """Evaluate signals against thresholds and return (recommendation, reason)."""
        cfg = self.config

        if signals.failure_rate >= cfg.failure_rate_pause:
            return "abort", f"failure_rate {signals.failure_rate:.1%} >= {cfg.failure_rate_pause:.0%}"

        if signals.avg_latency_ms >= cfg.latency_pause_ms:
            return "pause", f"avg_latency {signals.avg_latency_ms:.0f}ms >= {cfg.latency_pause_ms:.0f}ms"

        if signals.consecutive_slow_batches >= cfg.consecutive_slow_threshold:
            return "pause", f"consecutive_slow_batches {signals.consecutive_slow_batches} >= {cfg.consecutive_slow_threshold}"

        if signals.failure_rate >= cfg.failure_rate_warn:
            return "slow_down", f"failure_rate {signals.failure_rate:.1%} >= {cfg.failure_rate_warn:.0%}"

        if signals.retry_rate >= cfg.retry_rate_warn:
            return "slow_down", f"retry_rate {signals.retry_rate:.1%} >= {cfg.retry_rate_warn:.0%}"

        if signals.avg_latency_ms >= cfg.latency_warn_ms:
            return "slow_down", f"avg_latency {signals.avg_latency_ms:.0f}ms >= {cfg.latency_warn_ms:.0f}ms"

        if signals.quality_loss_rate >= cfg.quality_loss_warn:
            return "slow_down", f"quality_loss_rate {signals.quality_loss_rate:.1%} >= {cfg.quality_loss_warn:.0%}"

        return "proceed", ""

    def time_batch(self) -> "_BatchTimer":
        """Return a context manager that times a batch and records it."""
        return _BatchTimer(self)


class _BatchTimer:
    """Context manager that times a batch and records it to the monitor."""

    def __init__(self, monitor: BackpressureMonitor) -> None:
        self._monitor = monitor
        self._start: float = 0.0
        self.claimed: int = 0
        self.succeeded: int = 0
        self.failed: int = 0
        self.retried: int = 0
        self.checkpoint_errors: int = 0

    def __enter__(self) -> _BatchTimer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed_ms = (time.monotonic() - self._start) * 1000
        self._monitor.record_batch(
            batch_latency_ms=elapsed_ms,
            claimed=self.claimed,
            succeeded=self.succeeded,
            failed=self.failed,
            retried=self.retried,
            checkpoint_errors=self.checkpoint_errors,
        )


# ---------------------------------------------------------------------------
# Long-run diagnostics: classify bottlenecks and produce recommendations
# ---------------------------------------------------------------------------

BOTTLENECK_KEYS = (
    "access_blocking",
    "selector_loss",
    "pagination_gap",
    "transport_pressure",
    "retry_pressure",
    "quality_loss",
)


def classify_bottlenecks(
    signals: BackpressureSignals,
    item_errors: list[dict[str, Any]] | None = None,
    frontier_stats: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Classify likely bottlenecks from backpressure signals and error samples.

    Returns a list of bottleneck dicts, each with:
      - key: stable identifier (e.g. "access_blocking")
      - severity: "info" | "warn" | "critical"
      - summary: English one-liner
      - summary_zh: Chinese one-liner for frontend display
      - evidence: dict of supporting metrics
    """
    bottlenecks: list[dict[str, Any]] = []
    errors = item_errors or []
    frontier = frontier_stats or {}
    error_texts = [str(e.get("error", "")) for e in errors if isinstance(e, dict)]
    error_joined = " ".join(error_texts).lower()

    # 1. Access blocking
    blocking_keywords = ["403", "429", "captcha", "blocked", "forbidden", "cloudflare", "access denied"]
    blocking_hits = sum(1 for kw in blocking_keywords if kw in error_joined)
    if blocking_hits >= 2 or (signals.failure_rate >= 0.30 and blocking_hits >= 1):
        bottlenecks.append({
            "key": "access_blocking",
            "severity": "critical" if signals.failure_rate >= 0.40 else "warn",
            "summary": "Access blocking detected — many requests rejected by anti-bot or rate limiting.",
            "summary_zh": "检测到访问被封锁 — 大量请求被反爬或限流拒绝。",
            "evidence": {
                "failure_rate": round(signals.failure_rate, 4),
                "blocking_keyword_hits": blocking_hits,
                "sample_errors": error_texts[:3],
            },
        })

    # 2. Selector loss
    selector_keywords = ["selector", "no records", "empty", "not found", "none found", "parse error", "xpath"]
    selector_hits = sum(1 for kw in selector_keywords if kw in error_joined)
    if selector_hits >= 1:
        bottlenecks.append({
            "key": "selector_loss",
            "severity": "warn",
            "summary": "Possible selector loss — items could not be extracted from pages.",
            "summary_zh": "可能选择器失效 — 无法从页面中提取商品。",
            "evidence": {
                "selector_keyword_hits": selector_hits,
                "sample_errors": error_texts[:3],
            },
        })

    # 3. Pagination gap
    done = frontier.get("done", 0)
    queued = frontier.get("queued", 0)
    if done > 0 and queued == 0 and signals.total_batches > 0:
        success_rate = 1.0 - signals.failure_rate
        if success_rate < 0.5:
            bottlenecks.append({
                "key": "pagination_gap",
                "severity": "warn",
                "summary": "Pagination gap — frontier exhausted early with low success rate.",
                "summary_zh": "翻页中断 — 前端队列耗尽且成功率较低。",
                "evidence": {
                    "frontier_done": done,
                    "frontier_queued": queued,
                    "success_rate": round(success_rate, 4),
                },
            })

    # 4. Transport pressure
    if signals.avg_latency_ms >= 10000:
        bottlenecks.append({
            "key": "transport_pressure",
            "severity": "critical" if signals.avg_latency_ms >= 15000 else "warn",
            "summary": f"Transport pressure — average latency {signals.avg_latency_ms:.0f}ms indicates server overload or network issues.",
            "summary_zh": f"传输压力 — 平均延迟 {signals.avg_latency_ms:.0f}ms，服务器过载或网络异常。",
            "evidence": {
                "avg_latency_ms": round(signals.avg_latency_ms, 1),
                "p95_latency_ms": round(signals.p95_latency_ms, 1),
            },
        })

    # 5. Retry pressure
    if signals.retry_rate >= 0.20:
        bottlenecks.append({
            "key": "retry_pressure",
            "severity": "critical" if signals.retry_rate >= 0.40 else "warn",
            "summary": f"High retry rate ({signals.retry_rate:.0%}) — many items require re-fetching.",
            "summary_zh": f"重试率过高（{signals.retry_rate:.0%}）— 大量项目需要重新抓取。",
            "evidence": {
                "retry_rate": round(signals.retry_rate, 4),
            },
        })

    # 6. Quality loss
    if signals.quality_loss_rate >= 0.05:
        bottlenecks.append({
            "key": "quality_loss",
            "severity": "critical" if signals.quality_loss_rate >= 0.15 else "warn",
            "summary": f"Data quality loss ({signals.quality_loss_rate:.0%}) — checkpoint or save errors detected.",
            "summary_zh": f"数据质量下降（{signals.quality_loss_rate:.0%}）— 检查点或保存出错。",
            "evidence": {
                "quality_loss_rate": round(signals.quality_loss_rate, 4),
            },
        })

    return bottlenecks


def recommendation_text(
    signals: BackpressureSignals,
    bottlenecks: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Produce human-readable recommendation text for frontend display.

    Returns a dict with:
      - code: stable machine-readable code (same as signals.recommendation)
      - message_en: English summary
      - message_zh: Chinese summary
    """
    rec = signals.recommendation
    bns = bottlenecks or []
    critical_keys = [bn["key"] for bn in bns if bn.get("severity") == "critical"]

    if rec == "abort":
        if "access_blocking" in critical_keys:
            return {
                "code": "abort",
                "message_en": "Run aborted: access blocking detected. The site is actively rejecting requests.",
                "message_zh": "任务已中止：检测到访问被封锁，目标站点正在拒绝请求。",
            }
        if "quality_loss" in critical_keys:
            return {
                "code": "abort",
                "message_en": "Run aborted: critical data quality loss. Too many checkpoint/save errors.",
                "message_zh": "任务已中止：数据质量严重下降，检查点/保存错误过多。",
            }
        return {
            "code": "abort",
            "message_en": f"Run aborted: {signals.reason}.",
            "message_zh": f"任务已中止：{signals.reason}。",
        }

    if rec == "pause":
        if "transport_pressure" in critical_keys:
            return {
                "code": "pause",
                "message_en": "Run paused: server response is too slow. Will resume when conditions improve.",
                "message_zh": "任务已暂停：服务器响应过慢，待条件改善后恢复。",
            }
        if signals.consecutive_slow_batches >= 3:
            return {
                "code": "pause",
                "message_en": f"Run paused: {signals.consecutive_slow_batches} consecutive slow batches detected.",
                "message_zh": f"任务已暂停：连续 {signals.consecutive_slow_batches} 个批次过慢。",
            }
        return {
            "code": "pause",
            "message_en": f"Run paused: {signals.reason}.",
            "message_zh": f"任务已暂停：{signals.reason}。",
        }

    if rec == "slow_down":
        reasons = []
        reasons_zh = []
        if "retry_pressure" in critical_keys or signals.retry_rate >= 0.20:
            reasons.append(f"high retry rate ({signals.retry_rate:.0%})")
            reasons_zh.append(f"重试率过高（{signals.retry_rate:.0%}）")
        if "access_blocking" in [bn["key"] for bn in bns]:
            reasons.append("access blocking signals")
            reasons_zh.append("访问封锁信号")
        if signals.avg_latency_ms >= 5000:
            reasons.append(f"elevated latency ({signals.avg_latency_ms:.0f}ms)")
            reasons_zh.append(f"延迟升高（{signals.avg_latency_ms:.0f}ms）")
        if "quality_loss" in [bn["key"] for bn in bns]:
            reasons.append("data quality loss")
            reasons_zh.append("数据质量下降")
        reason_en = "; ".join(reasons) if reasons else signals.reason
        reason_zh = "；".join(reasons_zh) if reasons_zh else signals.reason
        return {
            "code": "slow_down",
            "message_en": f"Run slowing down: {reason_en}.",
            "message_zh": f"任务降速中：{reason_zh}。",
        }

    return {
        "code": "proceed",
        "message_en": "Run proceeding normally.",
        "message_zh": "任务正常运行中。",
    }
