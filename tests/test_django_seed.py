from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from djvrt.django_seed import (
    BaseDjangoVRTSeeder,
    SeedBuildResult,
    SeedOptions,
    build_tree_shaken_variants,
    generate_variants_for_schema,
)


def test_generate_variants_for_schema_is_deterministic() -> None:
    schema = {
        "type": "object",
        "properties": {
            "feature": {"type": "boolean"},
            "mode": {"type": "string", "enum": ["a", "b", "c"]},
            "nested": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                },
            },
        },
    }
    default_section = {
        "feature": True,
        "mode": "a",
        "nested": {"enabled": False},
    }

    variants = generate_variants_for_schema(
        section_schema=schema,
        default_section=default_section,
        max_variants=8,
    )

    assert [variant.slug for variant in variants] == [
        "control",
        "feature-false",
        "mode-b",
        "mode-c",
        "nested-enabled-true",
    ]


def test_build_tree_shaken_variants_uses_default_snake_to_camel_mapping() -> None:
    config_schema = {
        "type": "object",
        "properties": {
            "acrAudio": {
                "type": "object",
                "properties": {
                    "hiddenReference": {"type": "boolean"},
                },
            }
        },
    }
    default_config = {
        "acrAudio": {"hiddenReference": True},
    }

    variants_by_type = build_tree_shaken_variants(
        experiment_types=["acr_audio"],
        config_schema=config_schema,
        default_config=default_config,
        max_variants_per_type=4,
        tree_shake=True,
    )

    assert "acr_audio" in variants_by_type
    assert [variant.slug for variant in variants_by_type["acr_audio"]] == [
        "control",
        "hiddenreference-false",
    ]


class _MinimalSeeder(BaseDjangoVRTSeeder):
    @property
    def all_experiment_types(self) -> list[str]:
        return ["acr_audio"]

    @property
    def config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "acrAudio": {
                    "type": "object",
                    "properties": {
                        "hiddenReference": {"type": "boolean"},
                    },
                }
            },
        }

    def get_default_config(self) -> dict[str, Any]:
        return {"acrAudio": {"hiddenReference": True}}

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

        return SeedBuildResult(
            project_id=1,
            project_sid="p-1",
            experiment_count=len(variants_by_type["acr_audio"]),
            scenarios=[
                {"id": "b", "url": "/b"},
                {"id": "a", "url": "/a"},
            ],
            manifest={"variant_count": len(variants_by_type["acr_audio"])},
        )


def test_base_seeder_writes_stable_sorted_scenarios(tmp_path: Path) -> None:
    scenario_file = tmp_path / "scenarios.json"
    manifest_file = tmp_path / "manifest.json"

    result = _MinimalSeeder().run(
        SeedOptions(
            scenario_file=scenario_file,
            manifest_file=manifest_file,
            include_types=("acr_audio",),
            max_variants_per_type=2,
            tree_shake=True,
        )
    )

    scenarios = json.loads(scenario_file.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert result.scenario_count == 2
    assert result.experiment_count == 2
    assert [scenario["id"] for scenario in scenarios] == ["a", "b"]
    assert manifest == {"variant_count": 2}


def test_base_seeder_rejects_duplicate_scenario_ids(tmp_path: Path) -> None:
    class _DuplicateSeeder(_MinimalSeeder):
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

            return SeedBuildResult(
                project_id=1,
                project_sid="p-1",
                experiment_count=1,
                scenarios=[
                    {"id": "dup", "url": "/a"},
                    {"id": "dup", "url": "/b"},
                ],
                manifest={},
            )

    with pytest.raises(ValueError, match="Duplicate scenario ids"):
        _DuplicateSeeder().run(
            SeedOptions(
                scenario_file=tmp_path / "scenarios.json",
                manifest_file=tmp_path / "manifest.json",
                max_variants_per_type=1,
            )
        )
