"""Threaded staged crawl runner inspired by mature ecommerce spider flows.

The runner models the common production crawler pattern:

category/list stage -> product/detail stage -> variant/more stage -> sink.

It is intentionally generic.  Site logic is supplied as callbacks, while the
runner owns concurrency, bounded queues, de-duplication, progress counters, and
failure capture.  This gives CLM a reusable backend path for high-throughput
site profiles instead of leaving those behaviors inside one-off training
scripts.
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from queue import Queue
from threading import Lock, Thread
from typing import Any, Callable


StageCallback = Callable[[dict[str, Any]], list[dict[str, Any]]]
SinkCallback = Callable[[dict[str, Any]], None]
KeyCallback = Callable[[dict[str, Any]], str]


@dataclass(frozen=True)
class ThreadedStageRunnerConfig:
    list_workers: int = 1
    detail_workers: int = 8
    variant_workers: int = 8
    max_records: int = 0
    stop_when_inputs_empty: bool = True
    queue_timeout_seconds: float = 0.5

    def __post_init__(self) -> None:
        if self.list_workers < 1:
            raise ValueError("list_workers must be >= 1")
        if self.detail_workers < 1:
            raise ValueError("detail_workers must be >= 1")
        if self.variant_workers < 1:
            raise ValueError("variant_workers must be >= 1")
        if self.max_records < 0:
            raise ValueError("max_records must be >= 0")


@dataclass
class ThreadedStageRunnerSummary:
    list_seen: int = 0
    list_done: int = 0
    detail_seen: int = 0
    detail_done: int = 0
    variant_seen: int = 0
    variant_done: int = 0
    records_saved: int = 0
    duplicates_skipped: int = 0
    failures: list[dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "list_seen": self.list_seen,
            "list_done": self.list_done,
            "detail_seen": self.detail_seen,
            "detail_done": self.detail_done,
            "variant_seen": self.variant_seen,
            "variant_done": self.variant_done,
            "records_saved": self.records_saved,
            "duplicates_skipped": self.duplicates_skipped,
            "failure_count": len(self.failures),
            "failures": list(self.failures[:100]),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "records_per_minute": round(self.records_saved / max(self.elapsed_seconds / 60, 0.001), 2),
        }


class ThreadedStageRunner:
    """Run a three-stage crawl pipeline with generic callbacks."""

    def __init__(
        self,
        *,
        seeds: list[dict[str, Any]],
        list_callback: StageCallback,
        detail_callback: StageCallback,
        variant_callback: StageCallback,
        sink: SinkCallback,
        key_func: KeyCallback,
        config: ThreadedStageRunnerConfig | None = None,
    ) -> None:
        self.seeds = list(seeds)
        self.list_callback = list_callback
        self.detail_callback = detail_callback
        self.variant_callback = variant_callback
        self.sink = sink
        self.key_func = key_func
        self.config = config or ThreadedStageRunnerConfig()
        self.summary = ThreadedStageRunnerSummary()
        self._list_queue: Queue[dict[str, Any] | None] = Queue()
        self._detail_queue: Queue[dict[str, Any] | None] = Queue()
        self._variant_queue: Queue[dict[str, Any] | None] = Queue()
        self._seen_by_stage: dict[str, set[str]] = {"list": set(), "detail": set(), "variant": set()}
        self._saved_keys: set[str] = set()
        self._lock = Lock()
        self._stop = False

    def run(self) -> ThreadedStageRunnerSummary:
        started = time.perf_counter()
        for seed in self.seeds:
            if self._mark_seen(seed, "list"):
                self._list_queue.put(seed)
                self.summary.list_seen += 1
        self._send_stop(self._list_queue, self.config.list_workers)

        list_threads = [Thread(target=self._list_worker, daemon=True) for _ in range(self.config.list_workers)]
        detail_threads = [Thread(target=self._detail_worker, daemon=True) for _ in range(self.config.detail_workers)]
        variant_threads = [Thread(target=self._variant_worker, daemon=True) for _ in range(self.config.variant_workers)]
        for thread in list_threads + detail_threads + variant_threads:
            thread.start()

        self._list_queue.join()
        self._send_stop(self._detail_queue, len(detail_threads))
        self._detail_queue.join()
        self._send_stop(self._variant_queue, len(variant_threads))
        self._variant_queue.join()
        self._send_stop(self._list_queue, len(list_threads))
        for thread in list_threads + detail_threads + variant_threads:
            thread.join(timeout=2)
        self.summary.elapsed_seconds = time.perf_counter() - started
        return self.summary

    def _list_worker(self) -> None:
        self._stage_worker(
            input_queue=self._list_queue,
            output_queue=self._detail_queue,
            callback=self.list_callback,
            done_attr="list_done",
            seen_attr="detail_seen",
            stage="list",
        )

    def _detail_worker(self) -> None:
        self._stage_worker(
            input_queue=self._detail_queue,
            output_queue=self._variant_queue,
            callback=self.detail_callback,
            done_attr="detail_done",
            seen_attr="variant_seen",
            stage="detail",
        )

    def _variant_worker(self) -> None:
        while True:
            item = self._variant_queue.get()
            if item is None:
                self._variant_queue.task_done()
                return
            try:
                for record in self.variant_callback(item):
                    self._save_record(record)
                with self._lock:
                    self.summary.variant_done += 1
            except Exception as exc:
                self._record_failure("variant", item, exc)
            finally:
                self._variant_queue.task_done()

    def _stage_worker(
        self,
        *,
        input_queue: Queue[dict[str, Any] | None],
        output_queue: Queue[dict[str, Any] | None],
        callback: StageCallback,
        done_attr: str,
        seen_attr: str,
        stage: str,
    ) -> None:
        while True:
            item = input_queue.get()
            if item is None:
                input_queue.task_done()
                return
            try:
                for child in callback(item):
                    if self._mark_seen(child, "detail" if stage == "list" else "variant"):
                        output_queue.put(child)
                        with self._lock:
                            setattr(self.summary, seen_attr, getattr(self.summary, seen_attr) + 1)
                with self._lock:
                    setattr(self.summary, done_attr, getattr(self.summary, done_attr) + 1)
            except Exception as exc:
                self._record_failure(stage, item, exc)
            finally:
                input_queue.task_done()

    def _save_record(self, record: dict[str, Any]) -> None:
        key = self.key_func(record)
        with self._lock:
            if self.config.max_records and self.summary.records_saved >= self.config.max_records:
                self._stop = True
                return
            if key and key in self._saved_keys:
                self.summary.duplicates_skipped += 1
                return
            if key:
                self._saved_keys.add(key)
            self.summary.records_saved += 1
        self.sink(record)

    def _mark_seen(self, item: dict[str, Any], stage: str) -> bool:
        key = self.key_func(item)
        with self._lock:
            if self._stop:
                return False
            seen = self._seen_by_stage.setdefault(stage, set())
            if key and key in seen:
                self.summary.duplicates_skipped += 1
                return False
            if key:
                seen.add(key)
            return True

    def _record_failure(self, stage: str, item: dict[str, Any], exc: BaseException) -> None:
        with self._lock:
            self.summary.failures.append(
                {
                    "stage": stage,
                    "url": str(item.get("url") or item.get("source_url") or "")[:500],
                    "error": str(exc)[:500],
                    "traceback": traceback.format_exc(limit=5),
                }
            )

    @staticmethod
    def _send_stop(queue: Queue[dict[str, Any] | None], count: int) -> None:
        for _ in range(count):
            queue.put(None)
