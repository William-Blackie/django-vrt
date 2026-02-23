# Welcome to django-vrt

`django-vrt` (`djvrt`) is a Python-first visual regression testing package for Django platforms. It's designed for large, fast-moving UI systems where you need deterministic screenshots, repeatable CI, and safe baseline promotion.

Visual regression testing automatically detects unwanted visual changes in your Django application by comparing screenshots over time. It's the perfect way to ensure UI consistency and prevent accidental regressions in:

-   Large, complex component libraries
-   Design system updates
-   Cross-browser testing initiatives

## The `djvrt` Workflow

`django-vrt` uses a simple, powerful workflow based on a few key commands:

1.  **`discover`**: Finds all the URLs in your Django project that you want to test.
2.  **`lock`**: Creates a deterministic `djvrt.lock.json` file, which is a "plan" for all the screenshots to be taken. This ensures that the same set of tests run everywhere.
3.  **`baseline`**: Takes the initial "golden" set of screenshots. This is your source of truth.
4.  **`check`**: Takes a new set of screenshots and compares them against your baseline, highlighting any differences.

This workflow ensures that your tests are reproducible and that you have a clear process for managing visual changes.

## Key Features

-   **Deterministic Lockfile**: The `djvrt.lock.json` file ensures a reproducible test matrix.
-   **Reproducible Workflows**: Separate `baseline` and `check` commands provide a clear and safe process for managing screenshots.
-   **Screenshot Diffing**: `djvrt` has built-in visual diffing and generates a rich HTML report for reviewing changes.
-   **Interactive Review UI**: The generated report includes an interactive UI with filtering and multiple image comparison modes (side-by-side, slider, and diff overlay).
-   **Django Integration**: Automatically discovers routes directly from your project's `sitemap.xml` and URLConf.
-   **Data Seeding**: For pages that require specific data, `djvrt` provides data and model seeding hooks to ensure a stable UI state during tests.
-   **CI-Ready**: Designed for speed and reliability in continuous integration environments.

## Where to Next?

-   **[Quickstart](quickstart.md)**: Jump right in and run your first visual regression test.
-   **[Overview](overview.md)**: Understand the core concepts and workflow of `django-vrt`.
-   **[Configuration](configuration.md)**: Learn about all the available settings in `djvrt.toml`.
