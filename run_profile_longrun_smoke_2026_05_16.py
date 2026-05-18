#!/usr/bin/env python3
"""SCALE-RUNTIME-1 profile long-run smoke.

This offline smoke proves the product-facing profile long-run executor can
pause, resume, persist products, write checkpoints, and emit a profile run
report without site-specific runtime code.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from autonomous_crawler.runners import ProfileLongRunConfig, SiteProfile, run_profile_longrun
from autonomous_crawler.runtime import RuntimeRequest, RuntimeResponse
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


PROFILE_PATH = Path("autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json")
OUTPUT_PATH = Path("dev_logs/smoke/2026-05-16_profile_longrun_smoke.json")


class ApiFixtureFetchRuntime:
    name = "profile_longrun_api_fixture"

    def __init__(self, *, total: int = 55, page_size: int = 20) -> None:
        self.total = total
        self.page_size = page_size
        self.requests: list[str] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request.url)
        query = parse_qs(urlparse(request.url).query)
        page = int(query.get("page", ["1"])[0])
        limit = int(query.get("limit", [str(self.page_size)])[0])
        start = (page - 1) * limit
        end = min(start + limit, self.total)
        products = [
            {
                "name": f"LongRun Product {idx:02d}",
                "price": {"amount": 20 + idx / 10, "currency": "USD"},
                "url": f"https://api-profile-shop.local/products/{idx:02d}",
                "variants": {
                    "colors": ["Black", "Blue"] if idx % 2 == 0 else ["White"],
                    "sizes": ["40", "41", "42"],
                },
                "description": f"Long-run API product {idx}",
                "media": {"images": [f"/images/longrun-product-{idx:02d}.jpg"]},
            }
            for idx in range(start, end)
        ]
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            text=json.dumps({"data": {"products": products}}, ensure_ascii=False),
            engine_result={"engine": self.name},
        )


def run(
    *,
    output_path: str | Path = OUTPUT_PATH,
    keep_db: bool = False,
) -> dict[str, object]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="clm_profile_longrun_smoke_"))
    try:
        run_id = "profile-longrun-smoke-2026-05-16"
        profile = SiteProfile.load(PROFILE_PATH)
        frontier = URLFrontier(temp_dir / "frontier.sqlite3")
        product_store = ProductStore(temp_dir / "products.sqlite3")
        checkpoint_store = CheckpointStore(temp_dir / "checkpoints.sqlite3")
        fetch = ApiFixtureFetchRuntime(total=55, page_size=20)

        first = run_profile_longrun(
            profile=profile,
            config=ProfileLongRunConfig(
                run_id=run_id,
                worker_id="profile-longrun-pass-1",
                batch_size=1,
                max_batches=1,
                sample_limit=5,
            ),
            fetch_runtime=fetch,
            frontier=frontier,
            product_store=product_store,
            checkpoint_store=checkpoint_store,
        )
        resumed = run_profile_longrun(
            profile=profile,
            config=ProfileLongRunConfig(
                run_id=run_id,
                worker_id="profile-longrun-resume",
                batch_size=10,
                sample_limit=10,
                output_report_path=temp_dir / "profile_run_report.json",
            ),
            fetch_runtime=fetch,
            frontier=frontier,
            product_store=product_store,
            checkpoint_store=checkpoint_store,
        )
        summary: dict[str, object] = {
            "accepted": (
                first.status == "paused"
                and resumed.status == "completed"
                and resumed.product_stats.get("total") == 55
                and resumed.quality_summary.get("quality_gate", {}).get("passed") is True
                and resumed.checkpoint_latest.get("run", {}).get("status") == "completed"
            ),
            "run_id": run_id,
            "profile": profile.name,
            "first_pass": first.to_dict(),
            "resume_pass": resumed.to_dict(),
            "request_urls": list(fetch.requests),
            "report_path": str(temp_dir / "profile_run_report.json"),
            "runtime_dir": str(temp_dir) if keep_db else "",
        }
        if keep_db:
            kept_dir = output.parent / "2026-05-16_profile_longrun_runtime"
            if kept_dir.exists():
                shutil.rmtree(kept_dir)
            shutil.copytree(temp_dir, kept_dir)
            summary["runtime_dir"] = str(kept_dir)
            summary["report_path"] = str(kept_dir / "profile_run_report.json")
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return summary
    finally:
        if not keep_db:
            shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run profile long-run smoke.")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()
    summary = run(output_path=args.output, keep_db=args.keep_db)
    print(json.dumps({
        "accepted": summary["accepted"],
        "run_id": summary["run_id"],
        "profile": summary["profile"],
        "record_count": summary["resume_pass"]["product_stats"]["total"],  # type: ignore[index]
        "first_status": summary["first_pass"]["status"],  # type: ignore[index]
        "resume_status": summary["resume_pass"]["status"],  # type: ignore[index]
        "output": str(args.output),
    }, ensure_ascii=True, indent=2))
    return 0 if summary.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
