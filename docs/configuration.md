# Configuration

`djvrt` is configured through a single file in the root of your project: `djvrt.toml`.

You can generate a default version of this file by running `djvrt init`. This page documents all the available configuration options.

## Top-Level Settings

These settings are at the root of your `djvrt.toml` file.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `version` | Integer | `1` | The version of the configuration schema. Currently, only `1` is supported. |
| `base_url` | String | `"http://localhost:8000"` | The base URL for all captured pages. It must start with `http://` or `https://`. |

## `[paths]`

This section defines where `djvrt` should read from and write to.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `artifact_dir` | String | `".djvrt"` | The directory where all run artifacts (screenshots, reports, etc.) are stored. |
| `scenario_file` | String | `".djvrt/scenarios.json"` | The path to the JSON file containing scenario definitions. |
| `lock_file` | String | `"djvrt.lock.json"` | The path to the lockfile that ensures deterministic test runs. |

## `[discovery]`

This section controls how `djvrt` finds URLs to test in your Django project.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `use_sitemap` | Boolean | `true` | Whether to discover URLs from your project's `/sitemap.xml`. |
| `sitemap_url` | String | `"/sitemap.xml"` | The path to the sitemap file. |
| `use_django_urlconf` | Boolean | `true` | Whether to discover URLs by inspecting your Django URL configuration. |
| `include` | List of Strings | `[]` | A list of regex patterns. Only URLs matching these patterns will be included. |
| `exclude` | List of Strings | `["^/admin", "^/__debug__"]` | A list of regex patterns. URLs matching these patterns will be excluded. |
| `max_urls`| Integer | `400` | The maximum number of URLs to discover. |

## `[runtime]`

This section configures the browser environment and screenshotting behavior.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `workers` | Integer | `4` | The number of parallel workers to use for capturing screenshots. |
| `headless` | Boolean | `true` | Whether to run the browser in headless mode. |
| `browser_channel` | String | `""` | The Playwright browser channel to use (e.g., `"chrome"`, `"msedge"`). Defaults to the `chromium` package default. |
| `launch_args` | List of Strings | `["--no-sandbox"]` | A list of command-line arguments to pass to the browser on launch. |
| `locale` | String | `"en-US"` | The locale to set in the browser context. |
| `timezone` | String | `"UTC"` | The timezone to set in the browser context. |
| `wait_until` | String | `"networkidle"` | The browser state to wait for before taking a screenshot. Can be `load`, `domcontentloaded`, `networkidle`, or `commit`. |
| `navigation_timeout_ms` | Integer | `45000` | The maximum time in milliseconds to wait for a page to navigate. |
| `settle_time_ms` | Integer | `500` | An additional delay in milliseconds to wait after `wait_until` is met, allowing for animations or late-loading content to finish. |
| `default_mismatch_threshold` | Float | `0.001` | The default tolerance for visual differences, from `0.0` (exact match) to `1.0` (all different). Can be overridden per scenario. |
| `pixel_tolerance` | Integer | `8` | A value from 0 to 255 that represents the color difference tolerance for a single pixel. A higher value makes the comparison less sensitive to minor color changes. |
| `default_full_page` | Boolean | `true` | Whether to capture the entire scrollable page by default. Can be overridden per scenario. |
| `default_mask_selectors` | List of Strings | `[]` | A list of CSS selectors to mask (cover with a pink box) by default. Useful for dynamic content like timestamps or ads. |
| `default_hide_selectors` | List of Strings | `[]` | A list of CSS selectors to hide (`display: none`) by default. |
| `js_random_seed` | Integer | `null` | If set, this will seed `Math.random()` in the browser to make JavaScript-driven randomness deterministic. |
| `always_write_diff_images` | Boolean | `false` | If `true`, diff images will be generated even for tests that pass. By default, they are only created for regressions to save time. |

## `[data]`

This section configures commands and hooks for seeding data to ensure a stable UI state.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | Boolean | `false` | If `true`, data seeding commands will be run. |
| `loader` | String | `null` | A Python import path to a data loading function (e.g., `"my_project.seeding:load"`). |
| `commands` | List of Strings | `[]` | A list of shell commands to run for seeding (e.g., `"python manage.py loaddata ..."`). |
| `env` | Dictionary | `{}` | A dictionary of environment variables to set for the command execution. |
| `cwd` | String | `null` | The working directory to run the commands in. Defaults to the project root. |
| `phases` | List of Strings | `["baseline", "check"]` | The `djvrt` phases during which to run the seeding process. Can be `discover`, `baseline`, or `check`. |
| `fail_on_error` | Boolean | `true` | If `true`, the `djvrt` run will fail if any seeding command returns a non-zero exit code. |

## `[[experiments]]`

This is a list of tables defining named experiment variants, which can be applied to scenarios.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | String | (required) | The unique name for this experiment (e.g., `"control"`, `"new-feature-a"`). |
| `query_params` | Dictionary | `{}` | A dictionary of query parameters to add to the URL. |
| `headers` | Dictionary | `{}` | A dictionary of HTTP headers to send with the request. |

*Default: A single "control" experiment with no params or headers.*

## `[[viewports]]`

A list of tables defining named viewport sizes for screenshots.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | String | (required) | The unique name for this viewport (e.g., `"desktop"`, `"mobile"`). |
| `width` | Integer | (required) | The viewport width in pixels. |
| `height`| Integer | (required) | The viewport height in pixels. |

*Default: "desktop" (1440x900) and "mobile" (390x844).*

## `[[auth_profiles]]`

A list of tables defining named authentication profiles.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | String | (required) | The unique name for this profile (e.g., `"anonymous"`, `"signed_in_user"`). |
| `storage_state` | String | `null` | Path to a Playwright `storage_state` JSON file to load for this profile. |
| `headers` | Dictionary | `{}` | A dictionary of HTTP headers to use, which can supplement or override `storage_state` headers. |

*Default: A single "anonymous" profile.*
