# Quickstart

This guide will walk you through setting up `django-vrt` and running your first visual regression test.

## Prerequisites

-   Python 3.11+
-   A running Django application
-   `uv` (or `pip`) for package installation

## 1. Install

First, install `django-vrt` and the Playwright browser dependencies.

```bash
uv add django-vrt
uv run playwright install chromium
```

## 2. Initialize

Generate the configuration file (`djvrt.toml`) and a starting scenario file.

```bash
uv run djvrt init
```
This creates:
-   `djvrt.toml`: The main configuration file.
-   `.djvrt/scenarios.json`: A file where you can define test scenarios.

For best results, it's recommended to set a few runtime options in `djvrt.toml` to ensure deterministic screenshots:
```toml
[runtime]
timezone = "UTC"
locale = "en-US"
# Use a seed if your frontend code uses Math.random()
# js_random_seed = 2026
```

## 3. Discover, Lock, and Baseline

This three-step process creates your initial set of "golden" screenshots.

```bash
# Step 1: Find all testable URLs in your project
uv run djvrt discover --settings your_project.settings

# Step 2: Create a deterministic plan of all test variations
uv run djvrt lock

# Step 3: Take the initial screenshots
uv run djvrt baseline
```

After this, you will have a `.djvrt/baselines/` directory containing the canonical screenshots for your project. You should commit the `djvrt.lock.json` file and the contents of the `.djvrt/baselines/` directory to your repository.

## 4. Run a Check

Now you can run a check to look for visual changes.

```bash
uv run djvrt check
```

This command will:
1.  Take a new set of screenshots.
2.  Compare them against your baseline images.
3.  Generate a report in `.djvrt/runs/<run_id>/report.html`.

If any regressions are found, the command will exit with a non-zero status code, making it ideal for use in CI pipelines.

To automatically open the report after a run, add the `--open` flag:
```bash
uv run djvrt check --open
```

## 5. Approve Changes (Optional)

If a `check` run fails because of an *intentional* UI change, you can "approve" the new screenshots to make them the new baseline.

```bash
# Replace <run_id> with the ID from your check run
uv run djvrt approve --run-id <run_id>
```
This is faster than re-running `baseline` and is the standard way to update your golden files.

## Adding Authenticated Pages

To test pages that require a user to be logged in, you first need to generate an authentication state file.

```bash
uv run djvrt auth-state \
  --base-url http://localhost:8000 \
  --login-path /accounts/login/ \
  --email vrt@example.com \
  --password "$VRT_PASSWORD" \
  --output .djvrt/auth/user.json
```

Then, reference this file in `djvrt.toml` under a named profile:
```toml
[[auth_profiles]]
name = "signed_in"
storage_state = ".djvrt/auth/user.json"
```

You can now apply this profile to scenarios in `.djvrt/scenarios.json`.
