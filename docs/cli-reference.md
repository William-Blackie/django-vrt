# CLI Reference

This page provides a complete reference for all `djvrt` command-line interface (CLI) commands.

All commands can be run with `uv run djvrt <command>`.

## `init`

Creates a `djvrt.toml` configuration file and an initial `.djvrt/scenarios.json` file. This is the best way to get started with a new project.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. Defaults to `djvrt.toml` in the current directory. |
| `--force` | Overwrite existing config and scenario files if they exist. |

## `discover`

Discovers URL scenarios from your Django project's sitemap and URLConf.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. |
| `--settings <module>` | The `DJANGO_SETTINGS_MODULE` to use for URL discovery. |
| `--output <path>` | The file to write the discovered scenarios to. Defaults to the `scenario_file` path in `djvrt.toml`. |
| `--skip-data-prepare` | Skip the data preparation hooks defined in your configuration. |

## `lock`

Builds the deterministic `djvrt.lock.json` file from your scenarios. This file is the execution plan for your test run.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. |
| `--scenarios <path>` | Path to the scenario JSON file. Defaults to the `scenario_file` path in `djvrt.toml`. |
| `--output <path>` | The path to write the lockfile to. Defaults to the `lock_file` path in `djvrt.toml`. |

## `baseline`

Captures the initial "golden" baseline images for the current lockfile.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. |
| `--lock <path>` | Path to the lockfile. Defaults to the `lock_file` path in `djvrt.toml`. |
| `--force` | Overwrite an existing baseline for the current lock hash. |
| `--open` | Open the generated HTML report in your browser after the run. |
| `--skip-data-prepare` | Skip the data preparation hooks. |

## `check`

Captures a new set of screenshots and compares them against the baseline, reporting any regressions.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. |
| `--lock <path>` | Path to the lockfile. |
| `--run-id <id>` | A unique identifier for this run. Defaults to a timestamp. |
| `--open` | Open the generated HTML report in your browser after the run. |
| `--retry-regressions <n>` | The number of times to retry capturing and comparing a scenario that fails with a regression. Defaults to `1`. |
| `--skip-data-prepare` | Skip the data preparation hooks. |
| `--title <text>` | A custom title to display in the HTML report. |

## `report`

Regenerates HTML and JUnit reports from an existing `summary.json` file.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. |
| `--run-id <id>` | The ID of the run to generate a report for. |
| `--summary <path>` | The direct path to a `summary.json` file. Use this if you don't use `--run-id`. |
| `--html <path>` | The output path for the HTML report. |
| `--junit <path>` | The output path for the JUnit XML file. |
| `--open` | Open the generated HTML report in your browser. |
| `--title <text>` | A custom title for the HTML report. |

## `approve`

Promotes the "actual" images from a `check` run to become the new baseline.

| Option | Description |
| --- | --- |
| `--config <path>` | Path to `djvrt.toml`. |
| `--run-id <id>` | **(Required)** The ID of the run to approve images from. |
| `--lock <path>` | Path to the lockfile. If not provided, it's inferred from the run's summary. |
| `--allow-capture-errors` | Allow baseline promotion even if the run had some scenarios that failed to capture. |

## `auth-state`

A helper command to create a Playwright `storage_state` JSON file for authenticated sessions.

| Option | Description |
| --- | --- |
| `--base-url <url>` | The base URL of the application. |
| `--login-path <path>` | The path to the login page. |
| `--email <email>` | The email to use for login. |
| `--password <password>` | The password to use for login. |
| `--output <path>` | The output path for the `storage_state` JSON file. |
| `--next-path <path>` | The path to navigate to after a successful login to verify the session. |
| `--timeout-ms <ms>` | The navigation timeout in milliseconds. |
| `--email-selector <css>` | The CSS selector for the email input field. |
| `--password-selector <css>` | The CSS selector for the password input field. |
| `--submit-selector <css>` | The CSS selector for the form submission button. |
| `--wait-until <state>` | The Playwright `wait_until` strategy for navigation. |

---

*There is also a `python -m djvrt.django_seed_cli` command for advanced data seeding. See the [Django Seeding](django-seeding.md) page for details.*
