# django-vrt

`django-vrt` (`djvrt`) is a Python-first visual regression testing package for Django platforms.

It is built for large, fast-moving UI systems where you need deterministic screenshots, repeatable CI, and safe baseline promotion.

## Core value

- Deterministic lockfile matrix (`djvrt.lock.json`)
- Reproducible baseline and check workflows
- Built-in screenshot diffing and CI reports
- Interactive HTML review UI with filter/sort and image comparison modes
- Django route discovery from sitemap and URLConf
- Data and model seeding hooks for stable UI state
- Package-first extension model for complex projects

## Install

Consumer project:

```bash
uv add django-vrt
uv run playwright install chromium
```

Package development:

```bash
uv sync --extra dev
uv run playwright install chromium
```

## Quickstart

```bash
uv run djvrt init
uv run djvrt discover --settings your_project.settings
uv run djvrt lock
uv run djvrt baseline
uv run djvrt check
```

Artifacts are stored in `.djvrt/` by default.

## Getting Started Checklist

1. Install package + Chromium.
2. Generate config/scenarios with `djvrt init`.
3. Discover routes (or provide deterministic seeded scenarios).
4. Build `djvrt.lock.json` with `djvrt lock`.
5. Capture baseline once with `djvrt baseline`.
6. Gate PRs using `djvrt check`.

## CLI commands

- `djvrt init`: create `djvrt.toml` and starter scenarios
- `djvrt discover`: discover URL scenarios
- `djvrt lock`: compile deterministic matrix lockfile
- `djvrt baseline`: capture baseline images
- `djvrt check`: compare current screenshots against baseline
- `djvrt report`: regenerate HTML and JUnit reports from `summary.json`
- `djvrt approve`: promote run `actual/` images to baseline
- `djvrt auth-state`: capture Playwright `storage_state` JSON
- `python -m djvrt.django_seed_cli`: run hook-driven project seeding

## Package-first integration model

Use `django-vrt` as the shared engine. Keep consumer-repo code limited to small extension modules:

- seeder class (`module:Class`) implementing `BaseDjangoVRTSeeder`
- optional setup hook (`module:function`) to call `django.setup()`
- optional options builder (`module:function`) for project-specific seed options

This keeps custom logic minimal and avoids per-project forks of VRT infrastructure.

## Determinism checklist

- Commit `uv.lock`
- Commit `djvrt.lock.json` for the baseline contract
- Pin Python version and Playwright version
- Install Chromium in CI (`playwright install chromium`)
- Run on a stable OS image with controlled fonts
- Prefer deterministic data hooks (`get_or_create`, fixed identifiers)
- Set `runtime.js_random_seed` in `djvrt.toml` when frontend code uses `Math.random()`

## Documentation map

- `/docs/quickstart.md`
- `/docs/configuration.md`
- `/docs/django-seeding.md`
- `/docs/ci.md`
- `/docs/local-playbook.md`

## Examples

- CI workflow: `examples/github-actions.yml`
- Seeder adapter template: `examples/django_seed_adapter.py`
