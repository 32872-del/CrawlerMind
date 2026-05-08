"""Validator Agent - Validates extracted data and triggers retry/replan.

Responsibilities (README Section 7):
- Check completeness
- Detect anomalies
- Trigger retry / replan

Retry Logic (README Section 11):
    if validation_failed:
        if retries < max_retries:
            retries += 1
            goto("strategy_agent")
        else:
            fail_task()
"""
from __future__ import annotations

from typing import Any

from .base import preserve_state
from ..errors import ANTI_BOT_BLOCKED, EXTRACTION_EMPTY, VALIDATION_FAILED


@preserve_state
def validator_node(state: dict[str, Any]) -> dict[str, Any]:
    """Validate extracted data quality.

    This is a STUB implementation. In production, this node will:
    1. Check completeness (are all required fields present?)
    2. Detect anomalies (empty prices, duplicate URLs, suspicious patterns)
    3. Compute validation score
    4. Set needs_retry if quality is below threshold
    """
    extracted_data = state.get("extracted_data", {})
    recon_report = state.get("recon_report", {})
    target_fields = recon_report.get("target_fields", ["title", "price"])
    items = extracted_data.get("items", [])
    confidence = extracted_data.get("confidence", 0)

    anomalies = []
    completeness = 0.0

    if not items:
        anomalies.append("No items extracted")
    else:
        # Check field completeness
        total_fields = 0
        filled_fields = 0
        for item in items:
            for field in target_fields:
                total_fields += 1
                if item.get(field):
                    filled_fields += 1
        completeness = filled_fields / max(total_fields, 1)

        # Detect anomalies
        if completeness < 0.5:
            anomalies.append(f"Low completeness: {completeness:.0%}")
        if confidence < 0.3:
            anomalies.append(f"Low confidence: {confidence:.2f}")

        # Price is only mandatory when the task requested price.
        if "price" in target_fields:
            prices = [item.get("price") for item in items if item.get("price")]
            if not prices:
                anomalies.append("No prices found")

        # Check for duplicate URLs
        urls = [item.get("link") for item in items if item.get("link")]
        if len(urls) != len(set(urls)):
            anomalies.append("Duplicate URLs detected")

    is_valid = len(anomalies) == 0 and completeness >= 0.5
    retries = state.get("retries", 0)
    max_retries = state.get("max_retries", 3)
    needs_retry = not is_valid and retries < max_retries

    if is_valid:
        status = "completed"
        msg = f"[Validator] PASSED - {len(items)} items, completeness={completeness:.0%}"
    elif needs_retry:
        status = "retrying"
        msg = f"[Validator] RETRY - anomalies={anomalies}, attempt {retries + 1}/{max_retries}"
    else:
        status = "failed"
        msg = f"[Validator] FAILED - anomalies={anomalies}, max retries exceeded"

    error_code = None
    if status == "failed":
        challenge = (
            recon_report.get("access_diagnostics", {})
            .get("signals", {})
            .get("challenge", "")
        )
        if challenge and not items:
            error_code = ANTI_BOT_BLOCKED
        else:
            error_code = EXTRACTION_EMPTY if not items else VALIDATION_FAILED

    result: dict[str, Any] = {
        "status": status,
        "validation_result": {
            "is_valid": is_valid,
            "completeness": completeness,
            "anomalies": anomalies,
            "needs_retry": needs_retry,
        },
        "retries": retries + (1 if needs_retry else 0),
        "messages": state.get("messages", []) + [msg],
    }
    if error_code:
        result["error_code"] = error_code
    return result
