# django-vrt

[![CI](https://github.com/William-Blackie/django-vrt/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/William-Blackie/django-vrt/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-vrt.svg)](https://pypi.org/project/django-vrt/)
[![License](https://img.shields.io/github/license/William-Blackie/django-vrt.svg)](LICENSE)

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

Tip: add `--open` to `djvrt baseline`, `djvrt check`, or `djvrt report` to auto-open the generated HTML report.

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
- Set `runtime.always_write_diff_images = true` if you need diff overlays for passed scenarios

## Deployment to PyPI

`django-vrt` is automatically published to PyPI via GitHub Actions. There are three ways to trigger a release:

### 1. **GitHub Release (Recommended)**
Create a new release through the GitHub UI:
1. Go to Releases → "Create a new release"
2. Set tag (e.g., `v0.2.0`) and title
3. Click "Publish release"
4. The workflow automatically builds and publishes to PyPI

### 2. **Version Tag Push**
Push a version tag directly:
```bash
git tag v0.2.0
git push origin v0.2.0
```
This triggers the build and publish automatically.

### 3. **Manual Workflow Trigger**
Run the publish workflow manually from GitHub:
1. Go to Actions → "publish" workflow
2. Click "Run workflow" → "Run workflow"
3. The current `main` branch code is built and published

### Pre-release checklist
Before releasing:
- Create or verify the release tag (`vX.Y.Z`) for `hatch-vcs` versioning
- Update `CHANGELOG.md` or release notes (if applicable)
- Ensure all tests pass: `uv sync --extra dev && uv run pytest`
- Verify linting: `uv run ruff check .`
- Verify coverage gate: `make coverage` (fails below configured threshold)
- Commit and push changes to `main`

### How it works
The publish workflow (`.github/workflows/publish.yml`) does the following:
1. **Build stage**: Installs dependencies, builds wheel and source distributions, validates metadata
2. **Publish stage**: Downloads artifacts and publishes to PyPI using OIDC authentication (no API key needed)

The workflow uses GitHub's trusted publisher model for PyPI authentication. No secrets need to be configured—PyPI automatically trusts builds from this repository.

## Documentation map

- `/docs/quickstart.md`
- `/docs/configuration.md`
- `/docs/django-seeding.md`
- `/docs/ci.md`
- `/docs/local-playbook.md`

## Examples

- CI workflow: `examples/github-actions.yml`
- Seeder adapter template: `examples/django_seed_adapter.py`

## Attribution

If you use this project in a product or service, please include the following
notice in your documentation or credits: "django-vrt by William Blackie".
See [NOTICE](NOTICE) for details.

## Sponsors

This project is developed with support from **[Mabyduck](https://www.mabyduck.com/)** — Evaluating AI-generated audio, images, and videos with human feedback.

<table>
  <tr>
    <td bgcolor="white" align="center">
      <a href="https://www.mabyduck.com/">
        <img src="docs/assets/mabyduck_logo.png" alt="Mabyduck Logo" width="350">
      </a>
    </td>
  </tr>
</table>

Special thanks to [Lucas Theis](https://github.com/lucastheis) ([LinkedIn](https://www.linkedin.com/in/lucas-theis-5408109a/)) for enabling this work during business hours. Project maintained by [William Blackie](https://github.com/William-Blackie) ([LinkedIn](https://www.linkedin.com/in/william-blackie/)).

Learn more: [Mabyduck on GitHub](https://github.com/mabyduck) | [Mabyduck on LinkedIn](https://www.linkedin.com/company/mabyduck/)
