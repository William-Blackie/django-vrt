# CI Integration

## CI goals

- Fail fast on visual regressions.
- Keep runtime deterministic across branches and environments.
- Preserve artifacts for review.

## Minimal pipeline

```bash
uv sync --frozen --extra dev
uv run playwright install chromium
uv run djvrt discover --settings your_project.settings
uv run djvrt lock
uv run djvrt check
```

Reference workflow: `examples/github-actions.yml`.

## Required pinning

- Python version
- `uv.lock`
- `playwright` version (through dependency lock)
- CI image and fonts

## Artifacts to upload

- `.djvrt/runs/**/summary.json`
- `.djvrt/runs/**/report.html`
- `.djvrt/runs/**/junit.xml`
- `.djvrt/runs/**/actual/*.png`
- `.djvrt/runs/**/diff/*.png`

## Baseline strategy

Two common models:

- `main` owns baseline. PRs run `check` against committed lock + baseline artifacts.
- approved PR or release runs `approve` in a controlled job and updates baseline storage.

## Exit semantics

`djvrt check` exits non-zero for:

- regressions
- capture errors
- missing baseline images
- dimension mismatches

This makes it safe as a required status check.

## Operational tips

- Run data hooks in CI exactly as local (`[data]` phases).
- Keep browser launch args stable.
- Avoid parallel jobs mutating the same baseline target.
