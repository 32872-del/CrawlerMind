# Dev Log - 2026-05-04 16:30 - LangGraph Skeleton Setup

## What was done

### 1. Cleaned up old code
- Removed previous `agent/` directory (threading-based engine, CSS parsers, infra layer)
- Removed `config.yaml`, `requirements.txt`, `run.py`, `cache/`, `goods/`, `logs/`, `specs/`
- Preserved `.claude/` and `README.md`

### 2. Installed dependencies
```
pip install -U langgraph langchain-openai pydantic fastapi uvicorn
```
Installed versions:
- langgraph: 1.1.10
- langchain-openai: 1.2.1
- langchain-core: 1.3.2
- pydantic: 2.13.3
- fastapi: 0.136.1

### 3. Created blueprint directory structure
```
autonomous_crawler/
├── agents/          # 6 Agent node functions
├── tools/           # Typed tools (recon_tools.py stubs)
├── workflows/       # LangGraph state machine
├── models/          # CrawlTaskState Pydantic model
├── storage/         # (empty, future)
├── api/             # (empty, future)
├── prompts/         # (empty, future)
└── tests/           # (empty, future)
dev_logs/            # Development logs with timestamps
```

### 4. Implemented core files

| File | Status | Description |
|------|--------|-------------|
| `models/state.py` | Done | CrawlTaskState Pydantic BaseModel (README Section 6) |
| `agents/base.py` | Done | `@preserve_state` decorator - critical for state persistence |
| `agents/planner.py` | Stub | Parses user intent, extracts target fields |
| `agents/recon.py` | Stub | Website structure analysis |
| `agents/strategy.py` | Stub | Crawl strategy generation (API > Hydration > DOM > Browser) |
| `agents/executor.py` | Stub | Strategy execution (HTTP/Browser/API modes) |
| `agents/extractor.py` | Working | BeautifulSoup-based extraction with CSS selectors |
| `agents/validator.py` | Working | Data validation + retry/replan logic |
| `tools/recon_tools.py` | Stub | 4 @tool functions: detect_framework, discover_api_endpoints, detect_anti_bot, analyze_dom_structure |
| `workflows/crawl_graph.py` | Done | LangGraph StateGraph with conditional retry edge |
| `run_skeleton.py` | Done | End-to-end test script |

### 5. Key problem solved: State persistence across nodes

**Problem:** `StateGraph(dict)` uses last-write-wins for each key. When a node returns a partial dict (only its modified fields), fields from previous nodes are lost.

**Solution:** Created `@preserve_state` decorator in `agents/base.py` that merges node output ON TOP of existing state:
```python
def preserve_state(fn):
    def wrapper(state):
        node_output = fn(state)
        return {**state, **node_output}  # Merge
    return wrapper
```

Every agent node uses this decorator to ensure all state fields are preserved through the workflow.

## Test results

```
python run_skeleton.py "采集 tatuum.com 所有商品的标题和价格" "https://www.tatuum.com"
```

Output:
- Final Status: completed
- Elapsed: 0.01s
- Retries: 0
- 6 nodes executed in order: Planner → Recon → Strategy → Executor → Extractor → Validator
- Extracted 2 mock items (Classic Blazer: 299.0, Slim Fit Trousers: 189.0)
- Validation: PASSED, completeness=100%
- All state fields preserved (recon_report, crawl_strategy, extracted_data, validation_result)

## What needs testing/modification

1. **Retry loop**: Need to test the validator → strategy retry path. Current mock always passes. Need a test case where extraction fails to trigger retry.
2. **Extractor**: Currently uses hardcoded BeautifulSoup selectors from strategy. Needs to handle missing selectors gracefully.
3. **Error handling**: No try/catch in nodes. If a node throws, the graph crashes. Need error boundaries.
4. **LLM integration**: All nodes are stubs. Need to integrate `langchain-openai` ChatOpenAI for planner/recon/strategy nodes.
5. **State schema**: Currently using raw `dict`. Should migrate to TypedDict with Annotated reducers for type safety.

## Next steps

1. **Milestone 1: Recon MVP** - Implement the 4 recon tools for real:
   - `detect_framework()`: Parse HTML for React/Vue/Angular markers
   - `discover_api_endpoints()`: Browser network interception
   - `detect_anti_bot()`: Check for Cloudflare/CAPTCHA/rate-limiting
   - `analyze_dom_structure()`: Identify repeating patterns, pagination, data elements
2. **Add LLM to Planner**: Use ChatOpenAI to parse natural language goals
3. **Test retry path**: Create a failing extraction scenario and verify retry → strategy loop works
4. **Add error handling**: Wrap node execution in try/catch, log errors to state.error_log

## Files modified (complete list)

- `autonomous_crawler/__init__.py` (new)
- `autonomous_crawler/agents/__init__.py` (new)
- `autonomous_crawler/agents/base.py` (new)
- `autonomous_crawler/agents/planner.py` (new)
- `autonomous_crawler/agents/recon.py` (new)
- `autonomous_crawler/agents/strategy.py` (new)
- `autonomous_crawler/agents/executor.py` (new)
- `autonomous_crawler/agents/extractor.py` (new)
- `autonomous_crawler/agents/validator.py` (new)
- `autonomous_crawler/tools/__init__.py` (new)
- `autonomous_crawler/tools/recon_tools.py` (new)
- `autonomous_crawler/workflows/__init__.py` (new)
- `autonomous_crawler/workflows/crawl_graph.py` (new)
- `autonomous_crawler/models/__init__.py` (new)
- `autonomous_crawler/models/state.py` (new)
- `autonomous_crawler/storage/__init__.py` (new)
- `autonomous_crawler/api/__init__.py` (new)
- `autonomous_crawler/prompts/__init__.py` (new)
- `autonomous_crawler/tests/__init__.py` (new)
- `run_skeleton.py` (new)
- `dev_logs/skeleton_run_result.json` (generated)
