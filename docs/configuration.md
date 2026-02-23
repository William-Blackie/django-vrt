# Configuration

`djvrt` is configured via `djvrt.toml` and `.djvrt/scenarios.json`.

## `djvrt.toml` sections

| Section | Purpose |
| --- | --- |
| `version` | Config schema version. |
| `base_url` | Base URL for captured pages. |
| `[paths]` | Artifact/scenario/lockfile locations. |
| `[discovery]` | Sitemap and URLConf discovery controls. |
| `[runtime]` | Browser, wait strategy, diff defaults. |
| `[data]` | Deterministic data/model preparation hooks. |
| `[[experiments]]` | Named experiment variants (query params + headers). |
| `[[viewports]]` | Named viewport dimensions. |
| `[[auth_profiles]]` | Named auth contexts (`storage_state`, headers). |

## Scenario contract

Each entry in `.djvrt/scenarios.json` can define:

- `id`, `url`, `tags`
- `viewports`, `auth_profiles`, `experiments`
- `threshold`
- `wait_for_selector`, `wait_for_timeout_ms`
- `mask_selectors`, `hide_selectors`
- `full_page`

If `viewports`, `auth_profiles`, or `experiments` are omitted, `djvrt` expands them from `djvrt.toml`.

## Lockfile behavior

`djvrt lock` expands scenarios into a deterministic matrix and writes `djvrt.lock.json` with:

- `config_digest`
- `environment` (`python`, `platform`, `playwright`)
- expanded `scenarios`
- stable `hash`

The hash drives baseline storage at `.djvrt/baselines/<hash>/`.

## Deterministic runtime recommendations

- Use `timezone = "UTC"` and fixed `locale`.
- Keep `wait_until` and settle times stable across CI and local runs.
- Set `js_random_seed` to force deterministic `Math.random()` in browser-side code.
- Mask or hide dynamic selectors (timestamps, ads, rotating badges).
- Set explicit scenario thresholds for noisy pages.
- Keep auth-state users deterministic and free of unstable UI settings.

Example:

```toml
[runtime]
timezone = "UTC"
locale = "en-US"
js_random_seed = 2026
```

## Example experiments

```toml
[[experiments]]
name = "control"
query_params = {}
headers = {}

[[experiments]]
name = "exp-onboarding-b"
query_params = { exp_onboarding = "b" }
headers = { X-Experiment-Onboarding = "b" }
```
