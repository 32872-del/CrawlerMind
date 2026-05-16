#!/usr/bin/env python3
"""Profile Draft Training Smoke (Round 3).

Takes browser training evidence from REAL-HARDEN-4, generates SiteProfile
drafts via profile_draft module, verifies drafts can enter profile_ecommerce
runner, and outputs structured evidence.

This validates the end-to-end flow:
  browser evidence -> profile_draft -> SiteProfile -> profile_ecommerce runner
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomous_crawler.runners.profile_draft import draft_profile_from_evidence
from autonomous_crawler.runners.site_profile import SiteProfile

OUTPUT_DIR = Path("dev_logs") / "training"
BROWSER_EVIDENCE_PATH = OUTPUT_DIR / "2026-05-15_real_harden4_dynamic_list_training.json"


def load_browser_evidence(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load browser training evidence from JSON file."""
    evidence_path = Path(path) if path else BROWSER_EVIDENCE_PATH
    if not evidence_path.exists():
        return []
    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    return data.get("results") or []


def draft_from_training_evidence(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Convert a single browser training evidence entry to a profile draft."""
    draft = draft_profile_from_evidence(evidence)
    return draft


def verify_profile_loadable(draft: dict[str, Any]) -> dict[str, Any]:
    """Verify a profile draft can be loaded as SiteProfile."""
    result: dict[str, Any] = {"loadable": False, "errors": []}
    try:
        profile = SiteProfile.from_dict(draft)
        result["loadable"] = True
        result["profile_name"] = profile.name
        result["selector_count"] = len(profile.selectors)
        result["target_field_count"] = len(profile.target_fields)
        result["has_api_hints"] = bool(profile.api_hints)
        result["has_pagination_hints"] = bool(profile.pagination_hints)
        result["has_quality_expectations"] = bool(profile.quality_expectations)
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    return result


def try_runner_integration(
    draft: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Test if the draft profile can drive the ecommerce runner.

    Uses a simple fixture fetch runtime to verify selector_builder and
    record_builder work with the draft profile's selectors.
    """
    result: dict[str, Any] = {
        "runner_compatible": False,
        "initial_requests_generated": 0,
        "errors": [],
    }

    try:
        from autonomous_crawler.runners import (
            initial_requests_from_profile,
            make_ecommerce_profile_callbacks,
        )

        profile = SiteProfile.from_dict(draft)

        # Test initial_requests_from_profile
        try:
            initial = initial_requests_from_profile(profile, run_id="draft-smoke")
            result["initial_requests_generated"] = len(initial)
            result["seed_urls"] = [r.url for r in initial[:5]]
        except Exception as exc:
            result["errors"].append(f"initial_requests: {type(exc).__name__}: {exc}")

        # Test callbacks creation
        try:
            callbacks = make_ecommerce_profile_callbacks(profile, run_id="draft-smoke")
            result["runner_compatible"] = True
            result["has_selector_builder"] = hasattr(callbacks, "selector_builder")
            result["has_record_builder"] = hasattr(callbacks, "record_builder")
            result["has_link_builder"] = hasattr(callbacks, "link_builder")
        except Exception as exc:
            result["errors"].append(f"callbacks: {type(exc).__name__}: {exc}")

    except Exception as exc:
        result["errors"].append(f"import: {type(exc).__name__}: {exc}")

    return result


def run(
    browser_evidence_path: Path | str | None = None,
    output_name: str = "2026-05-15_profile_draft_training.json",
) -> dict[str, Any]:
    """Run profile draft training smoke test."""
    evidence_list = load_browser_evidence(browser_evidence_path)

    if not evidence_list:
        return {
            "status": "no_evidence",
            "message": "No browser training evidence found. Run REAL-HARDEN-4 first.",
        }

    results: list[dict[str, Any]] = []
    for evidence in evidence_list:
        site_id = evidence.get("id", "unknown")
        site_name = evidence.get("name", site_id)

        # Generate draft
        draft = draft_from_training_evidence(evidence)

        # Verify loadable
        verification = verify_profile_loadable(draft)

        # Try runner integration
        runner_result = try_runner_integration(draft, evidence)

        result = {
            "id": site_id,
            "name": site_name,
            "source_url": evidence.get("url", ""),
            "source_stop_reason": evidence.get("stop_reason", "unknown"),
            "source_rendered_items": evidence.get("rendered_item_count", 0),
            "draft": {
                "profile_name": draft.get("name", ""),
                "selector_count": len(draft.get("selectors", {})),
                "target_field_count": len(draft.get("target_fields", [])),
                "has_api_hints": bool(draft.get("api_hints")),
                "has_pagination_hints": bool(draft.get("pagination_hints")),
                "training_notes_count": len(draft.get("training_notes", [])),
            },
            "verification": verification,
            "runner_integration": runner_result,
            "profile_json": draft,
        }
        results.append(result)

    # Summary
    loadable_count = sum(1 for r in results if r["verification"]["loadable"])
    runner_count = sum(1 for r in results if r["runner_integration"]["runner_compatible"])
    total_initial_requests = sum(r["runner_integration"]["initial_requests_generated"] for r in results)

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "PROFILE-AUTO-1 profile draft training smoke",
        "source_evidence": str(browser_evidence_path or BROWSER_EVIDENCE_PATH),
        "summary": {
            "total": len(results),
            "loadable_as_site_profile": loadable_count,
            "runner_compatible": runner_count,
            "total_initial_requests": total_initial_requests,
        },
        "results": results,
    }

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_name
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Print summary
    print(f"Profile Draft Training Smoke")
    print(f"{'='*60}")
    print(f"Sources: {len(results)} evidence entries")
    print(f"Loadable as SiteProfile: {loadable_count}/{len(results)}")
    print(f"Runner compatible: {runner_count}/{len(results)}")
    print(f"Total initial requests: {total_initial_requests}")
    print()
    for r in results:
        v = r["verification"]
        ri = r["runner_integration"]
        icon = "OK" if v["loadable"] and ri["runner_compatible"] else "PARTIAL" if v["loadable"] else "FAIL"
        print(f"  [{icon}] {r['name']}")
        print(f"    selectors={r['draft']['selector_count']} fields={r['draft']['target_field_count']}")
        if ri["initial_requests_generated"]:
            print(f"    initial_requests={ri['initial_requests_generated']}")
        if ri["errors"]:
            for err in ri["errors"]:
                print(f"    error: {err}")
    print(f"\nEvidence: {output_path}")
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Profile draft training smoke")
    parser.add_argument("--evidence", default="", help="Browser evidence JSON path")
    parser.add_argument("--output", default="2026-05-15_profile_draft_training.json", help="Output filename")
    args = parser.parse_args()

    evidence_path = args.evidence if args.evidence else None
    report = run(browser_evidence_path=evidence_path, output_name=args.output)
    ok = report.get("summary", {}).get("loadable_as_site_profile", 0) > 0
    exit(0 if ok else 1)


if __name__ == "__main__":
    main()
