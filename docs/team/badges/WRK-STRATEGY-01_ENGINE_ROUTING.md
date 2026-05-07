# Badge: WRK-STRATEGY-01

## Identity

Role: Strategy / Engine Routing Worker

Mission:

Maintain strategy selection and engine routing rules.

## Primary Ownership

```text
autonomous_crawler/agents/strategy.py
autonomous_crawler/tools/site_spec_adapter.py
autonomous_crawler/tools/fnspider_adapter.py
strategy-related tests
```

## Current Status

Accepted on 2026-05-06 for explicit fnspider routing.

## Common Tasks

- Add strategy templates.
- Improve engine selection rules.
- Add optional LLM Strategy interface.
- Keep deterministic fallback behavior.

## Avoid Unless Approved

```text
autonomous_crawler/agents/executor.py
autonomous_crawler/storage/
autonomous_crawler/api/
```
