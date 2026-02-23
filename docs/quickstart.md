# Quickstart

## Goal

Run deterministic visual checks in a Django project with minimal setup.

## Prerequisites

- Python 3.11+
- A running Django app
- Chromium installed for Playwright

## Install

```bash
uv add django-vrt
uv run playwright install chromium
```

## Initialize config

```bash
uv run djvrt init
```

This creates:

- `djvrt.toml`
- `.djvrt/scenarios.json`

Recommended runtime hardening in `djvrt.toml`:

- `timezone = "UTC"`
- `locale = "en-US"`
- `js_random_seed = 2026` (if frontend code uses `Math.random()`)

## Build first baseline

```bash
uv run djvrt discover --settings your_project.settings
uv run djvrt lock
uv run djvrt baseline
```

## Run a check

```bash
uv run djvrt check
```

If regressions are found, `djvrt` exits non-zero and writes artifacts under `.djvrt/runs/<run_id>/`.
`report.html` includes a built-in triage UI with filters plus side-by-side, slider, and diff comparison modes.
Use `uv run djvrt check --open` to open the report automatically after the run.

## Add authenticated coverage (optional)

Create storage state:

```bash
uv run djvrt auth-state \
  --base-url http://localhost:8000 \
  --login-path /accounts/login/ \
  --email vrt@example.com \
  --password "$VRT_PASSWORD" \
  --output .djvrt/auth/user.json
```

Then reference it in `djvrt.toml`:

```toml
[[auth_profiles]]
name = "signed_in"
storage_state = ".djvrt/auth/user.json"
```

## Baseline lifecycle

- `baseline`: capture canonical images for the current lock hash.
- `check`: compare current images with baseline.
- `approve --run-id <id>`: promote a run to the new baseline.

## Outputs

- `.djvrt/runs/<run_id>/summary.json`
- `.djvrt/runs/<run_id>/report.html`
- `.djvrt/runs/<run_id>/junit.xml`
- `.djvrt/runs/<run_id>/actual/*.png`
- `.djvrt/runs/<run_id>/diff/*.png`
