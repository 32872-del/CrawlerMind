# SCRAPLING-ABSORB-2E-A: Real Dynamic Training Targets

Date: 2026-05-14
Worker: LLM-2026-001
Status: COMPLETE

## Deliverables

- `autonomous_crawler/tests/dynamic_training_targets.py` — 8 scenario type fixtures
- `autonomous_crawler/tests/test_dynamic_training_targets.py` — 48 focused tests (all pass)

## Scenario Coverage

| Category | Scenario ID | Mode | Key Browser Evidence |
|---|---|---|---|
| JS rendered list | js_rendered_product_list | browser | wait_selector, wait_until |
| XHR/API data | xhr_api_product_data | browser | capture_xhr regex |
| Lazy load scroll | lazy_load_infinite_scroll | browser | scroll_count, scroll_delay |
| Cookie/session | cookie_session_changes | browser | user_data_dir, storage_state |
| Challenge/block | challenge_block_evidence | browser | expected_evidence.failure_classification |
| Static fallback | static_fallback_page | http | empty browser fields |
| Pagination | multi_page_pagination | browser | max_items, next_page selector |
| Protected init | protected_dynamic_init_script | browser | init_script, fingerprint_report |

## Key Design Decisions

1. `build_state()` is standalone — no executor import, no shared boundary change
2. Scenarios are data structures — no public network required for validation
3. Challenge scenario carries `expected_evidence` dict with `failure_classification`
   and `blocked_status_codes` for future automated QA
4. All browser scenarios have non-empty `wait_selector` and `wait_until`
5. XHR scenarios must be browser-mode with valid regex pattern

## Usage

```python
from autonomous_crawler.tests.dynamic_training_targets import (
    SCENARIO_TYPES, build_state, get_scenario, get_scenarios_by_category
)

# Get all scenarios
for s in SCENARIO_TYPES:
    state = build_state(s, "native")

# Get by category
scroll_scenarios = get_scenarios_by_category("lazy_load_scroll")

# Get by ID
scenario = get_scenario("xhr_api_product_data")
state = build_state(scenario, "scrapling")
```

## Next Steps

- Replace placeholder URLs with real training targets
- Run comparison harness against real targets
- Calibrate expected_evidence for challenge scenarios
