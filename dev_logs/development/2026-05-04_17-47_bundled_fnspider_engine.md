# Dev Log - 2026-05-04 17:47 - Bundled fnspider Engine

## Goal

Make the mature spider_Uvex collection framework available as a built-in Agent
collection tool, without requiring the external spider_Uvex workspace
folder.

## What changed

### 1. Bundled fnspider into the Agent project

- Copied `spider_Uvex/fnspider` into:
  `autonomous_crawler/engines/fnspider`.
- Added `autonomous_crawler/engines/__init__.py`.
- Removed copied `__pycache__` folders.

### 2. Made runtime paths project-local

- Replaced bundled `fnspider/settings.py`.
- Runtime data now lives inside the Agent project:
  - cache: `autonomous_crawler/engines/runtime/fnspider_cache`
  - goods DBs: `autonomous_crawler/engines/runtime/fnspider_goods`
- This avoids depending on the shell working directory or the old external
  spider_Uvex folder.

### 3. Added fnspider adapter

- Added `autonomous_crawler/tools/fnspider_adapter.py`.
- Provides a thin boundary:
  - `validate_fnspider_site_spec`
  - `save_fnspider_site_spec`
  - `run_fnspider_site_spec`
  - `count_goods_rows`
  - `load_goods_rows`
  - `fnspider_runtime_paths`

### 4. Updated dependencies

- Updated `requirements.txt` with bundled engine dependencies:
  - `botasaurus`
  - `curl_cffi`
  - `fake_useragent`
  - `loguru`
  - `playwright`
  - `redis`

### 5. Added project ignore rules

- Added `.gitignore`.
- Runtime cache/db output is ignored.
- Generated skeleton result JSON is ignored.

### 6. Tests expanded

- `test_bundled_fnspider_adapter_validates_and_saves_spec`
- `test_bundled_fnspider_runtime_paths_are_project_local`

## Verification

```text
python -m unittest discover autonomous_crawler\tests
Ran 9 tests
OK

python -m compileall autonomous_crawler run_skeleton.py
OK

python -c "from autonomous_crawler.tools.fnspider_adapter import fnspider_runtime_paths; print(fnspider_runtime_paths())"
site_specs/cache/goods all point inside the Agent project
```

## Current status

fnspider is now an embedded engine. The Agent can validate and save
spider_Uvex-compatible site specs from inside the current project.

The real `run_fnspider_site_spec` path is implemented but not exercised in unit
tests because it may launch browser/network crawls. It should be covered by an
integration test with a local fixture HTTP server.

## Next recommended step

Add an executor mode:

```json
{
  "engine": "fnspider",
  "site_spec_draft": { ... }
}
```

Then `executor_node` can call `run_fnspider_site_spec`, read rows from the
generated SQLite database, and feed them into `extracted_data`.
