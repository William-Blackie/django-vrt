# Django Seeding

Visual regression testing is most effective when the UI state is stable and deterministic. If your pages depend on specific database state (e.g., user-generated content, specific feature flags), you need a way to seed this data before running `djvrt`.

`djvrt` offers two primary methods for data seeding, catering to different levels of complexity.

## Choosing a Seeding Method

-   **Method 1: `[data]` section in `djvrt.toml`**:
    -   **Best for**: Simple seeding needs.
    -   **Use when**: You can set up your test state with a few shell commands (like `manage.py loaddata`) or a straightforward Python script.
    -   **How it works**: Runs commands or a Python function at specified phases (`discover`, `baseline`, `check`).

-   **Method 2: `BaseDjangoVRTSeeder` framework**:
    -   **Best for**: Complex, dynamic scenarios.
    -   **Use when**: You need to programmatically generate a large number of scenarios based on combinations of data, such as for testing a design system with many component variations.
    -   **How it works**: You implement a `BaseDjangoVRTSeeder` subclass that has full control over creating database objects and generating the final scenario list.

---

## Method 1: Simple Seeding with `[data]`

For many projects, seeding can be accomplished by running a few `manage.py` commands. The `[data]` section in `djvrt.toml` is designed for this.

### Example

```toml
[data]
# Must be true to run any data hooks
enabled = true

# A list of shell commands to run in order
commands = [
  "python manage.py migrate --noinput",
  "python manage.py loaddata fixtures/vrt/base.json"
]

# (Optional) A Python function to call for more complex logic
# The function receives a `DataContext` object.
loader = "myproject.vrt_seed:load"

# Environment variables to set for the commands
env = { DJANGO_SETTINGS_MODULE = "myproject.settings" }

# Phases to run the seeding in. Default is ["baseline", "check"]
phases = ["discover", "baseline", "check"]

# If true, the run will stop if a seeding command fails
fail_on_error = true
```

---

## Method 2: Advanced Seeding with `BaseDjangoVRTSeeder`

For complex systems, especially those with many experimental variations, you may need to generate scenarios programmatically. The `BaseDjangoVRTSeeder` framework provides the structure for this.

You create a seeder class in your project that `djvrt` can call via the `python -m djvrt.django_seed_cli` command.

### Example Seeder Implementation

Here is an example of a seeder that creates a matrix of tests for different experiment types.

```python
# In your_project/vrt_seeder.py

from typing import Any
from djvrt.django_seed import BaseDjangoVRTSeeder, SeedBuildResult, SeedOptions, Variant

class ProjectSeeder(BaseDjangoVRTSeeder):
    """
    A project-specific seeder that defines how to create VRT scenarios.
    """
    @property
    def all_experiment_types(self) -> list[str]:
        """Define all the high-level experiment categories to test."""
        return ["feature_a", "feature_b"]

    @property
    def config_schema(self) -> dict[str, Any]:
        """(Optional) Define a schema for experiment configuration."""
        # return EXPERIMENT_CONFIG_SCHEMA
        return {}

    def get_default_config(self) -> dict[str, Any]:
        """(Optional) Provide default configuration for experiments."""
        # return get_default_config()
        return {}

    def build_seed(
        self,
        *,
        options: SeedOptions,
        experiment_types: list[str],
        default_config: dict[str, Any],
        variants_by_type: dict[str, list[Variant]],
    ) -> SeedBuildResult:
        """
        The core method where seeding logic and scenario generation happens.
        """
        # 1. CREATE YOUR DETERMINISTIC DATA
        # Use Django's ORM to create or update the database records needed
        # for your tests. Always use stable, predictable IDs and data.
        # Example:
        # user, _ = User.objects.get_or_create(email="vrt@example.com")
        # project, _ = Project.objects.update_or_create(id=99, defaults={"name": "VRT Project"})

        # 2. GENERATE SCENARIOS
        # Based on the data you just created, build a list of VRT scenarios.
        scenarios = [
            self.build_scenario_entry(
                scenario_id="example-feature-a",
                url="/features/feature-a/",
                tags=["vrt", "feature-a"],
                wait_for_selector="body",
            )
            # ... add more scenarios for different variants
        ]

        # 3. (Optional) CREATE A MANIFEST
        # The manifest is a record of what was generated, useful for debugging.
        manifest = {
            "seed": {
                "tree_shake": options.tree_shake,
                "max_variants_per_type": options.max_variants_per_type,
            },
            "types": [
                {
                    "experiment_type": "feature_a",
                    "variant_count": len(variants_by_type.get("feature_a", [])),
                }
            ],
        }

        # 4. RETURN THE RESULT
        return SeedBuildResult(
            project_id=1,
            project_sid="example_project",
            experiment_count=1, # Total number of experiments created
            scenarios=scenarios,
            manifest=manifest,
        )
```

### Running the Seeder

You run this seeder using a dedicated CLI command:

```bash
python -m djvrt.django_seed_cli \
  --seeder myproject.vrt_seed:ProjectSeeder \
  --setup myproject.vrt_seed:setup_django \
  --options-builder myproject.vrt_seed:build_seed_options \
  --scenario-file .djvrt/scenarios.json \
  --manifest-file .djvrt/tree_shake_manifest.json \
  --max-variants-per-type 24
```
This command tells `djvrt` to:
1. Run your `setup_django` function.
2. Call your `ProjectSeeder` to perform the seeding.
3. Write the generated scenarios to `.djvrt/scenarios.json`.

See the [CLI Reference](cli-reference.md) for more on the available options.

## Deterministic Seeding Rules

Regardless of the method you choose, follow these rules to ensure your tests are stable:

-   Use `get_or_create` or idempotent `update_or_create` calls to avoid duplicate data.
-   Always use stable, predictable IDs and slugs for seeded database rows.
-   Avoid randomness (`random.randint`) and clock-dependent values (`datetime.now()`).
-   Isolate your VRT tests to a single, dedicated user or project context if possible.
-   Ensure your seeding logic is run in every relevant phase (`discover`, `baseline`, `check`) to guarantee a clean state.
