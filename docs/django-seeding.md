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

For complex experiment systems, build a small adapter module in the consumer project.

```python
from typing import Any
from djvrt.django_seed import BaseDjangoVRTSeeder, SeedBuildResult, SeedOptions


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
        variants_by_type: dict[str, list[Any]],
    ) -> SeedBuildResult:
        from django.db import transaction
        from django.urls import reverse
        from myproject.models import Experiment, Project

        with transaction.atomic():
            # Use helpers to reduce boilerplate
            user = self.ensure_user(
                email=options.get_extra("seed_email", "vrt@local"),
                password=options.get_extra("seed_password", "secret"),
            )
            self.ensure_waffle_flag("can_run_vrt")
            
            project, _ = Project.objects.get_or_create(id=99, defaults={"name": "VRT"})
            
            # ... seeding logic using get_stable_id and variant_manifest_entry
            # ... return SeedBuildResult
            ...
```

## CLI hooks

When running via `django_seed_cli.py`, you can provide setup and options-builder hooks:

```python
# myproject/vrt_seed.py
from pathlib import Path
from djvrt.utils import ensure_django_ready
from djvrt.django_seed import SeedOptions

def setup_django(settings: str | None) -> None:
    # Convenient helper for setting up Django app/DB context
    ensure_django_ready(settings)

def build_seed_options(**kwargs) -> SeedOptions:
    # Custom options with extra_context loaded from env or defaults
    import os
    return SeedOptions(
        **kwargs,
        extra_context={
            "seed_email": os.environ.get("VRT_EMAIL", "vrt@local"),
            "assets_root": Path(__file__).parent / "static",
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

`--option key=value` flags are automatically passed into `SeedOptions.extra_context` if no options-builder is provided, or into the `options_builder` kwargs.

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
