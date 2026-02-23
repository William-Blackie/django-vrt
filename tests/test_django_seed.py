from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any, cast

import pytest

import djvrt.django_seed as django_seed
from djvrt.django_seed import (
    BaseDjangoVRTSeeder,
    Mutation,
    SeedBuildResult,
    SeedOptions,
    Variant,
    _candidate_values,
    _collect_mutations,
    _default_for_schema,
    _has_type,
    _set_nested_value,
    _slugify,
    build_tree_shaken_variants,
    generate_variants_for_schema,
    snake_to_lower_camel,
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


def test_seed_option_and_variant_helpers(tmp_path: Path) -> None:
    options = SeedOptions(
        scenario_file=tmp_path / "scenarios.json",
        manifest_file=tmp_path / "manifest.json",
        extra_context={"seed_email": "seed@example.test"},
    )
    assert options.get_extra("seed_email") == "seed@example.test"
    assert options.get_extra("missing", "fallback") == "fallback"

    variant = Variant(
        name="control",
        slug="control",
        config={},
        mutation=Mutation(path=("section", 0), value=True),
    )
    assert variant.mutation_path == "section.0"
    assert Variant(name="plain", slug="plain", config={}).mutation_path is None
    assert snake_to_lower_camel("acr_audio") == "acrAudio"
    assert _slugify("!!!") == "variant"


def test_schema_defaults_and_candidate_value_selection() -> None:
    assert _has_type({"type": "string"}, "string") is True
    assert _has_type({"type": ["string", "null"]}, "null") is True
    assert _has_type({"type": 1}, "string") is False

    assert _default_for_schema({"default": {"x": 1}}) == {"x": 1}
    assert _default_for_schema({"type": "boolean"}) is False
    assert _default_for_schema({"enum": ["a", "b"]}) == "a"
    assert _default_for_schema({"type": "integer", "minimum": 3}) == 3
    assert _default_for_schema({"type": "number"}) == 0
    assert _default_for_schema({"type": "array"}) == []
    assert _default_for_schema({"properties": {"x": {"type": "boolean"}}}) == {}
    assert _default_for_schema({"type": "string"}) is None

    assert _candidate_values({"type": "boolean"}, "bad") == [True]
    assert _candidate_values({"enum": ["a", "b"]}, "missing") == ["b"]
    assert _candidate_values({"type": "integer", "minimum": 1, "maximum": 3}, 2) == [1, 3]
    assert _candidate_values({"type": "integer"}, 5) == [6]
    assert _candidate_values({"type": "number", "maximum": 1.6}, 1.5) == [1.6]


def test_collect_mutations_and_nested_assignment_edge_cases() -> None:
    array_mutations = _collect_mutations(
        {"type": "array", "items": {"enum": ["a", "b"]}},
        ["a"],
        path=("items",),
    )
    assert array_mutations == [Mutation(path=("items", 0), value="b")]

    object_mutations = _collect_mutations(
        {
            "type": "object",
            "properties": {
                "ignored": "not-a-schema",
                "enabled": {"type": "boolean"},
            },
        },
        {"enabled": False},
    )
    assert object_mutations == [Mutation(path=("enabled",), value=True)]

    payload: dict[str, Any] = {}
    _set_nested_value(payload, ("a", "b"), 1)
    assert payload == {"a": {"b": 1}}

    list_payload: dict[str, Any] = {"items": []}
    _set_nested_value(list_payload, ("items", 1, "name"), "x")
    assert list_payload == {"items": [{}, {"name": "x"}]}

    list_assignment_payload: dict[str, Any] = {"items": []}
    _set_nested_value(list_assignment_payload, ("items", 2), 9)
    assert list_assignment_payload == {"items": [None, None, 9]}

    with pytest.raises(ValueError, match="Cannot mutate root payload"):
        _set_nested_value(payload, (), 2)

    with pytest.raises(ValueError, match="Expected object at path segment 'a'"):
        _set_nested_value(cast(dict[str, Any], []), ("a", "b"), 1)

    with pytest.raises(ValueError, match="Expected list at path segment 0"):
        _set_nested_value({"a": {}}, ("a", 0), 1)

    with pytest.raises(ValueError, match="Expected list at path segment 0"):
        _set_nested_value({}, (0, "value"), 1)

    with pytest.raises(ValueError, match="Expected object at path segment 'b'"):
        _set_nested_value({"a": []}, ("a", "b"), 1)


def test_generate_variants_handles_dedup_errors_slug_collisions_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mutations = [
        Mutation(path=("alpha",), value=True),
        Mutation(path=("alpha",), value=True),
        Mutation(path=("alpha",), value=False),
        Mutation(path=("name",), value="A"),
        Mutation(path=("name",), value="a"),
        Mutation(path=("other",), value=1),
        Mutation(path=("zeta",), value=1),
        Mutation(path=(), value="invalid"),
    ]

    monkeypatch.setattr(django_seed, "_collect_mutations", lambda *_args, **_kwargs: raw_mutations)

    variants = generate_variants_for_schema(
        section_schema={"type": "object"},
        default_section={"alpha": False, "name": "base", "other": 0, "zeta": 0},
        max_variants=5,
    )

    slugs = [variant.slug for variant in variants]
    assert slugs == ["control", "alpha-true", "name-a", "name-a-2", "other-1"]


def test_build_tree_shaken_variants_with_tree_shake_disabled() -> None:
    variants = build_tree_shaken_variants(
        experiment_types=["acr_audio"],
        config_schema={"type": "object", "properties": {"acrAudio": {"type": "object"}}},
        default_config={"acrAudio": {"enabled": True}},
        max_variants_per_type=8,
        tree_shake=False,
    )
    assert [item.slug for item in variants["acr_audio"]] == ["control"]


def test_base_seeder_helper_methods_and_validation(tmp_path: Path) -> None:
    seeder = _MinimalSeeder()

    with pytest.raises(ValueError, match="Unknown experiment types: missing"):
        seeder.resolve_experiment_types(("missing",))

    scenario_entry = seeder.build_scenario_entry(
        scenario_id="scenario-1",
        url="/seeded/",
        tags=["seeded"],
    )
    assert scenario_entry["auth_profiles"] == ["seeded_user"]
    assert scenario_entry["viewports"] == ["desktop", "mobile"]
    assert scenario_entry["wait_for_selector"] == "form"

    manifest_entry = seeder.variant_manifest_entry(
        Variant(
            name="flag_enabled",
            slug="flag-enabled",
            config={},
            mutation=Mutation(path=("flags", "enabled"), value=True),
        )
    )
    assert manifest_entry["mutation_path"] == "flags.enabled"
    assert manifest_entry["mutation_value"] is True
    assert seeder.get_stable_id(base=1_000, block_size=10, slot=2, index=3) == 1_024

    with pytest.raises(ValueError, match="at least 1"):
        seeder.run(
            SeedOptions(
                scenario_file=tmp_path / "scenarios.json",
                manifest_file=tmp_path / "manifest.json",
                max_variants_per_type=0,
            )
        )


def test_base_seeder_ensure_user_updates_password_and_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    class _User:
        def __init__(self) -> None:
            self.is_staff = False
            self.is_superuser = False
            self.is_verified = False
            self.saved_fields: list[list[str]] = []
            self.password_value = ""

        def check_password(self, _: str) -> bool:
            return False

        def set_password(self, password: str) -> None:
            self.password_value = password

        def save(self, *, update_fields: list[str]) -> None:
            self.saved_fields.append(update_fields)

    class _Manager:
        def __init__(self, user: _User) -> None:
            self.user = user
            self.kwargs: dict[str, Any] | None = None

        def get_or_create(self, **kwargs: Any) -> tuple[_User, bool]:
            self.kwargs = kwargs
            return self.user, True

    user = _User()
    manager = _Manager(user)
    User = type("User", (), {"USERNAME_FIELD": "email", "name": "", "objects": manager})

    monkeypatch.setattr("django.contrib.auth.get_user_model", lambda: User)

    ensured_user = BaseDjangoVRTSeeder.ensure_user(
        "seed@example.test",
        "secret",
        is_staff=True,
        is_superuser=True,
    )

    assert ensured_user is user
    assert manager.kwargs is not None
    assert manager.kwargs["email"] == "seed@example.test"
    assert manager.kwargs["defaults"]["name"] == "VRT Seed User"
    assert user.password_value == "secret"
    assert user.saved_fields and set(user.saved_fields[0]) == {"password", "is_staff", "is_superuser", "is_verified"}


def test_base_seeder_ensure_user_supports_first_name_models(monkeypatch: pytest.MonkeyPatch) -> None:
    class _User:
        def __init__(self) -> None:
            self.is_staff = False
            self.is_superuser = False
            self.is_verified = True
            self.saved = False

        def check_password(self, _: str) -> bool:
            return True

        def set_password(self, _: str) -> None:
            self.saved = True

        def save(self, *, update_fields: list[str]) -> None:
            del update_fields
            self.saved = True

    class _Manager:
        def __init__(self, user: _User) -> None:
            self.user = user
            self.kwargs: dict[str, Any] | None = None

        def get_or_create(self, **kwargs: Any) -> tuple[_User, bool]:
            self.kwargs = kwargs
            return self.user, False

    user = _User()
    manager = _Manager(user)
    User = type("User", (), {"USERNAME_FIELD": "email", "first_name": "", "objects": manager})

    monkeypatch.setattr("django.contrib.auth.get_user_model", lambda: User)

    BaseDjangoVRTSeeder.ensure_user("seed@example.test", "secret")

    assert manager.kwargs is not None
    assert manager.kwargs["defaults"]["first_name"] == "VRT Seed User"
    assert user.saved is False


def test_base_seeder_ensure_waffle_flag_handles_module_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_import_error(_: str) -> types.ModuleType:
        raise ImportError

    monkeypatch.setattr("djvrt.django_seed.importlib.import_module", _raise_import_error)
    assert BaseDjangoVRTSeeder.ensure_waffle_flag("flag") is None

    monkeypatch.setattr("djvrt.django_seed.importlib.import_module", lambda _: types.SimpleNamespace())
    assert BaseDjangoVRTSeeder.ensure_waffle_flag("flag") is None

    class _Flag:
        def __init__(self) -> None:
            self.everyone = False
            self.saved = False

        def save(self, *, update_fields: list[str]) -> None:
            assert update_fields == ["everyone"]
            self.saved = True

    class _FlagManager:
        def __init__(self, flag: _Flag) -> None:
            self.flag = flag

        def get_or_create(self, *, name: str) -> tuple[_Flag, bool]:
            assert name == "flag"
            return self.flag, False

    flag = _Flag()
    Flag = type("Flag", (), {"objects": _FlagManager(flag)})
    monkeypatch.setattr("djvrt.django_seed.importlib.import_module", lambda _: types.SimpleNamespace(Flag=Flag))

    result = BaseDjangoVRTSeeder.ensure_waffle_flag("flag", everyone=True)
    assert result is flag
    assert flag.everyone is True
    assert flag.saved is True


def test_base_seeder_read_asset_bytes_validates_paths(tmp_path: Path) -> None:
    assets_root = tmp_path / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    file_path = assets_root / "seed.bin"
    file_path.write_bytes(b"seed")

    assert BaseDjangoVRTSeeder.read_asset_bytes(assets_root, "seed.bin") == b"seed"

    with pytest.raises(FileNotFoundError, match="Seed asset not found"):
        BaseDjangoVRTSeeder.read_asset_bytes(assets_root, "missing.bin")
