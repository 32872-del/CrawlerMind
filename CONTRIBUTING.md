# Contributing to Crawler-Mind

Thanks for your interest in contributing.

## Setup

1. Fork and clone the repository.

2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Linux / macOS
   # .\.venv\Scripts\Activate.ps1   # Windows PowerShell

   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. (Optional) Install Playwright browsers for browser-mode tests:

   ```bash
   playwright install
   ```

4. Copy the example config if you want to test LLM features:

   ```bash
   cp clm_config.example.json clm_config.json
   # Edit clm_config.json with your provider settings
   ```

## Running Tests

Standard suite (no browser binaries or API keys required):

```bash
python -m unittest discover -s autonomous_crawler/tests
```

Browser smoke (requires Playwright browsers):

```bash
AUTONOMOUS_CRAWLER_RUN_BROWSER_SMOKE=1 python -m unittest autonomous_crawler.tests.test_real_browser_smoke -v
```

## No Secrets Rule

- Never commit `clm_config.json`, `.env`, or any file containing API keys.
- `clm_config.json` is already in `.gitignore`.
- CI never requires real API keys. Tests use deterministic fixtures and mocks.

## Branch and PR Guidance

1. Create a feature branch from `main`.
2. Keep PRs focused: one logical change per PR.
3. Run the test suite before opening a PR.
4. Describe what changed and why in the PR body.
5. Link related issues if applicable.

## Crawling Safety

- Only crawl targets you are authorized to access.
- Do not bypass login, CAPTCHA, or access controls without explicit permission.
- Respect `robots.txt` when the crawler checks it.
- Do not submit PRs that add scraping of private or paywalled content without
  a clear authorization story.

## Project Structure

See the repository map in `README.md` for an overview of the codebase layout.
