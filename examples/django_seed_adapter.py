"""Example project adapter for deterministic Django VRT seeding.

Copy this into your Django project and replace placeholder logic with model-specific code.
"""

from __future__ import annotations

from typing import Any

from djvrt.django_seed import BaseDjangoVRTSeeder, SeedBuildResult, SeedOptions


class ExampleSeeder(BaseDjangoVRTSeeder):
    @property
    def all_experiment_types(self) -> list[str]:
        return ['acr_audio', 'pairwise_image']

    @property
    def config_schema(self) -> dict[str, Any]:
        # Return the global experiment config schema used by your project.
        raise NotImplementedError

    def get_default_config(self) -> dict[str, Any]:
        # Return the default experiment config payload used by your project.
        raise NotImplementedError

    def build_seed(
        self,
        *,
        options: SeedOptions,
        experiment_types: list[str],
        default_config: dict[str, Any],
        variants_by_type: dict[str, list[Any]],
    ) -> SeedBuildResult:
        del options
        del experiment_types
        del default_config
        del variants_by_type
        # Upsert deterministic model data and return scenarios + manifest.
        raise NotImplementedError
