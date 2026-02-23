# Django Seeding

Use seeding when route discovery alone is not enough and UI depends on deterministic model state.

## Option 1: `data.commands` and `data.loader`

Use built-in data hooks in `djvrt.toml`:

```toml
[data]
enabled = true
commands = [
  "python manage.py migrate --noinput",
  "python manage.py loaddata fixtures/vrt/base.json"
]
loader = "myproject.vrt_seed:load"
env = { DJANGO_SETTINGS_MODULE = "myproject.settings" }
phases = ["discover", "baseline", "check"]
fail_on_error = true
```

`loader` receives `DataContext` and can upsert model data safely.

## Option 2: package seeder framework (`BaseDjangoVRTSeeder`)

For complex experiment systems, create a small adapter module in the consumer project.

```python
from typing import Any
from djvrt.django_seed import BaseDjangoVRTSeeder, SeedBuildResult, SeedOptions, Variant


class ProjectSeeder(BaseDjangoVRTSeeder):
    @property
    def all_experiment_types(self) -> list[str]:
        return ["acr_audio", "pairwise_image"]

    @property
    def config_schema(self) -> dict[str, Any]:
        return EXPERIMENT_CONFIG_SCHEMA

    def get_default_config(self) -> dict[str, Any]:
        return get_default_config()

    def build_seed(
        self,
        *,
        options: SeedOptions,
        experiment_types: list[str],
        default_config: dict[str, Any],
        variants_by_type: dict[str, list[Variant]],
    ) -> SeedBuildResult:
        # 1. Upsert deterministic DB rows (project, datasets, experiments, sessions)
        # 2. Build deterministic scenario entries with stable IDs
        scenarios = [
            self.build_scenario_entry(
                scenario_id="xp-acr-audio-control",
                url="/xp/latest/acr_audio/123/456/",
                tags=["vrt", "xp", "acr_audio", "control"],
                wait_for_selector="body",
            )
        ]

        manifest = {
            "seed": {
                "tree_shake": options.tree_shake,
                "max_variants_per_type": options.max_variants_per_type,
            },
            "types": [
                {
                    "experiment_type": "acr_audio",
                    "variant_count": len(variants_by_type["acr_audio"]),
                }
            ],
        }

        return SeedBuildResult(
            project_id=99,
            project_sid="proj_demo",
            experiment_count=1,
            scenarios=scenarios,
            manifest=manifest,
        )
```

## CLI hooks

When running via `django_seed_cli.py`, you can provide setup and options-builder hooks.

```python
# myproject/vrt_seed.py
from djvrt.django_seed import SeedOptions

def setup_django(settings: str | None) -> None:
    import os
    import django

    if settings:
        os.environ["DJANGO_SETTINGS_MODULE"] = settings
    django.setup()

def build_seed_options(**kwargs) -> SeedOptions:
    import os
    return SeedOptions(
        **kwargs,
        extra_context={
            "seed_email": os.environ.get("VRT_EMAIL", "vrt@local"),
            "seed_password": os.environ.get("VRT_PASSWORD", "secret"),
        }
    )
```

Run it:

```bash
python -m djvrt.django_seed_cli \
  --seeder myproject.vrt_seed:ProjectSeeder \
  --setup myproject.vrt_seed:setup_django \
  --options-builder myproject.vrt_seed:build_seed_options \
  --option my_flag=true \
  --scenario-file .djvrt/scenarios.json \
  --manifest-file .djvrt/tree_shake_manifest.json \
  --max-variants-per-type 24
```

If you pass `--option key=value`, you must also pass `--options-builder`.
The options builder receives those values and can map them into `SeedOptions.extra_context` (or a custom `SeedOptions` subclass).

## Tree-shaking behavior

- Default mode: `tree_shake = true`.
- Generates `control` plus targeted schema mutations per experiment type.
- Output is deterministic and bounded by `max_variants_per_type`.
- This avoids an unbounded Cartesian explosion while still providing broad coverage.

To disable tree-shaking:

```bash
python -m djvrt.django_seed_cli ... --no-tree-shake
```

## Deterministic seeding rules

- Use `get_or_create` or idempotent upserts.
- Use stable IDs/slugs for seeded rows.
- Avoid randomness and clock-dependent defaults.
- Keep one dedicated VRT project/user context.
- Re-run seeding in every test phase (`discover`, `baseline`, `check`).
