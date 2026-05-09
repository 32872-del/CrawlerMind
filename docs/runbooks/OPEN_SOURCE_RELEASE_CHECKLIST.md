# Open Source Release Checklist

Use this before tagging a public release.

## Required

- [ ] Choose and add a `LICENSE` file.
- [ ] Confirm `clm_config.json` is not tracked.
- [ ] Confirm runtime databases and caches are not tracked.
- [ ] Run the standard test suite.
- [ ] Verify README quick start on a clean environment.
- [ ] Confirm no real API keys, proxy credentials, cookies, or session tokens
      are committed.

## Recommended

- [ ] Add GitHub issue templates.
- [ ] Add a contribution guide.
- [ ] Add a release tag.
- [ ] Add CI for unit tests.
- [ ] Add a small screenshot or demo GIF after the frontend exists.

## Current Notes

- License is still pending project-owner choice.
- `clm_config.json` is ignored by Git.
- Runtime folders are ignored by Git.
- The repository is suitable for source synchronization, but not yet a polished
  public release package.
