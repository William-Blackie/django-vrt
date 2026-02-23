# django-vrt

[![CI](https://github.com/William-Blackie/django-vrt/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/William-Blackie/django-vrt/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/django-vrt.svg)](https://pypi.org/project/django-vrt/)
[![License](https://img.shields.io/github/license/William-Blackie/django-vrt.svg)](LICENSE)

`django-vrt` (`djvrt`) is a Python-first visual regression testing package for Django platforms, built for large, fast-moving UI systems where you need deterministic screenshots, repeatable CI, and safe baseline promotion.

**[➡️ View the full documentation](https://william-blackie.github.io/django-vrt/)**

## Core Features

- **Deterministic Lockfile**: `djvrt.lock.json` ensures a reproducible test matrix.
- **Reproducible Workflows**: Separate `baseline` and `check` commands for clear intent.
- **Screenshot Diffing**: Built-in visual diffing with a rich HTML report for reviewing changes.
- **Django Integration**: Discover routes directly from your project's sitemap and URLConf.
- **Data Seeding**: Use data and model seeding hooks for a stable UI state during tests.

## Quick Install

```bash
uv add django-vrt
uv run playwright install chromium
```

## Quickest Start

```bash
# 1. Create config file
uv run djvrt init

# 2. Discover URLs and create a lockfile
uv run djvrt discover --settings your_project.settings
uv run djvrt lock

# 3. Capture your initial baseline screenshots
uv run djvrt baseline

# 4. Run a check for visual changes
uv run djvrt check
```

For detailed guides, configuration, and CI setup, please see the **[full documentation](https://william-blackie.github.io/django-vrt/)**.

## Contributing

Contributions are welcome! Please see the [Contributing Guide](CONTRIBUTING.md) for details on setting up your development environment, running tests, and the release process.

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
