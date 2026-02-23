from __future__ import annotations

import importlib
import runpy
import sys
from pathlib import Path

import pytest

from djvrt.django_seed_cli import (
    _build_seed_options,
    _call_setup,
    _load_object,
    _parse_extra_options,
    main,
    parse_args,
)


def _write_demo_module(tmp_path: Path) -> str:
    module_name = "djvrt_seed_demo_module"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(
        "from djvrt.django_seed import BaseDjangoVRTSeeder, SeedBuildResult, SeedOptions\n"
        "setup_calls = []\n"
        "def setup(settings_module=None):\n"
        "    setup_calls.append(settings_module)\n"
        "def options_builder(*, scenario_file, manifest_file, include_types, "
        "max_variants_per_type, tree_shake, extra_options=None):\n"
        "    return SeedOptions(\n"
        "        scenario_file=scenario_file,\n"
        "        manifest_file=manifest_file,\n"
        "        include_types=include_types,\n"
        "        max_variants_per_type=max_variants_per_type,\n"
        "        tree_shake=tree_shake,\n"
        "    )\n"
        "class DemoSeeder(BaseDjangoVRTSeeder):\n"
        "    @property\n"
        "    def all_experiment_types(self):\n"
        "        return ['acr_audio']\n"
        "    @property\n"
        "    def config_schema(self):\n"
        "        return {'type': 'object', 'properties': {'acrAudio': {'type': 'object'}}}\n"
        "    def get_default_config(self):\n"
        "        return {'acrAudio': {}}\n"
        "    def build_seed(self, **kwargs):\n"
        "        return SeedBuildResult(\n"
        "            project_id=1,\n"
        "            project_sid='p1',\n"
        "            experiment_count=1,\n"
        "            scenarios=[{'id': 'home', 'url': '/'}],\n"
        "            manifest={'ok': True},\n"
        "        )\n",
        encoding="utf-8",
    )
    return module_name


def test_django_seed_cli_runs_with_hook_builder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module_name = _write_demo_module(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    scenario_file = tmp_path / "scenarios.json"
    manifest_file = tmp_path / "manifest.json"

    rc = main(
        [
            "--seeder",
            f"{module_name}:DemoSeeder",
            "--setup",
            f"{module_name}:setup",
            "--options-builder",
            f"{module_name}:options_builder",
            "--settings",
            "project.settings",
            "--scenario-file",
            str(scenario_file),
            "--manifest-file",
            str(manifest_file),
            "--include-type",
            "acr_audio",
            "--max-variants-per-type",
            "2",
            "--option",
            "seed_email=x@example.com",
        ]
    )

    demo_module = importlib.import_module(module_name)

    assert rc == 0
    assert demo_module.setup_calls == ["project.settings"]
    assert scenario_file.exists()
    assert manifest_file.exists()


def test_django_seed_cli_rejects_extra_options_without_builder(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Extra --option values require --options-builder"):
        main(
            [
                "--seeder",
                "djvrt.django_seed:BaseDjangoVRTSeeder",
                "--scenario-file",
                str(tmp_path / "scenarios.json"),
                "--manifest-file",
                str(tmp_path / "manifest.json"),
                "--option",
                "a=b",
            ]
        )


def test_load_object_validation_and_lookup_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "djvrt_seed_lookup_module"
    (tmp_path / f"{module_name}.py").write_text("value = 123\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ValueError, match="Expected 'module:object'"):
        _load_object("invalid")
    with pytest.raises(ValueError, match="Expected 'module:object'"):
        _load_object(f"{module_name}:")
    with pytest.raises(ValueError, match="not found in module"):
        _load_object(f"{module_name}:missing")


def test_parse_extra_options_validation() -> None:
    assert _parse_extra_options(["a=1", "b=2"]) == {"a": "1", "b": "2"}
    with pytest.raises(ValueError, match="Expected key=value"):
        _parse_extra_options(["bad"])
    with pytest.raises(ValueError, match="Key cannot be empty"):
        _parse_extra_options([" =x"])


def test_call_setup_supports_zero_and_one_parameter_callables() -> None:
    calls: list[str | None] = []

    def setup_no_args() -> None:
        calls.append("no-args")

    def setup_with_settings(settings_module: str | None) -> None:
        calls.append(settings_module)

    _call_setup(setup_no_args, "ignored")
    _call_setup(setup_with_settings, "proj.settings")
    assert calls == ["no-args", "proj.settings"]


def test_build_seed_options_with_builder_variants(tmp_path: Path) -> None:
    scenario_file = tmp_path / "scenarios.json"
    manifest_file = tmp_path / "manifest.json"

    default_options = _build_seed_options(
        options_builder=None,
        scenario_file=scenario_file,
        manifest_file=manifest_file,
        include_types=("acr_audio",),
        max_variants_per_type=2,
        tree_shake=True,
        extra_options={"seed_email": "x@example.com"},
    )
    assert default_options.extra["seed_email"] == "x@example.com"

    captured: dict[str, object] = {}

    def builder_with_extra(*, extra_options: dict[str, str] | None = None, **kwargs: object) -> object:
        if extra_options is not None:
            captured["extra_options"] = extra_options
        captured.update(kwargs)
        return {"ok": True}

    built = _build_seed_options(
        options_builder=builder_with_extra,
        scenario_file=scenario_file,
        manifest_file=manifest_file,
        include_types=None,
        max_variants_per_type=3,
        tree_shake=False,
        extra_options={"seed_email": "x@example.com"},
    )
    assert built == {"ok": True}
    assert "extra_options" in captured

    captured.clear()

    def builder_without_extra(*, scenario_file: Path, manifest_file: Path, **kwargs: object) -> object:
        captured["scenario_file"] = scenario_file
        captured["manifest_file"] = manifest_file
        captured.update(kwargs)
        return {"ok": True}

    built_without_extra = _build_seed_options(
        options_builder=builder_without_extra,
        scenario_file=scenario_file,
        manifest_file=manifest_file,
        include_types=None,
        max_variants_per_type=3,
        tree_shake=False,
        extra_options={"seed_email": "x@example.com"},
    )
    assert built_without_extra == {"ok": True}
    assert captured["seed_email"] == "x@example.com"


def test_parse_args_defaults() -> None:
    args = parse_args(["--seeder", "djvrt.django_seed:BaseDjangoVRTSeeder"])
    assert args.max_variants_per_type == 24
    assert args.no_tree_shake is False


def test_django_seed_cli_rejects_invalid_max_variants() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        main(
            [
                "--seeder",
                "djvrt.django_seed:BaseDjangoVRTSeeder",
                "--max-variants-per-type",
                "0",
            ]
        )


def test_django_seed_cli_rejects_non_seeder_class(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "djvrt_seed_bad_class"
    (tmp_path / f"{module_name}.py").write_text("class NotSeeder:\n    pass\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ValueError, match="BaseDjangoVRTSeeder subclass"):
        main(["--seeder", f"{module_name}:NotSeeder"])


def test_django_seed_cli_rejects_non_callable_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = _write_demo_module(tmp_path)
    (tmp_path / f"{module_name}_noncallable_setup.py").write_text(
        "setup = 42\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ValueError, match="--setup must point to a callable"):
        main(
            [
                "--seeder",
                f"{module_name}:DemoSeeder",
                "--setup",
                f"{module_name}_noncallable_setup:setup",
            ]
        )


def test_django_seed_cli_rejects_non_callable_options_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = _write_demo_module(tmp_path)
    bad_module = "djvrt_seed_bad_builder"
    (tmp_path / f"{bad_module}.py").write_text("builder = 42\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ValueError, match="--options-builder must point to a callable"):
        main(
            [
                "--seeder",
                f"{module_name}:DemoSeeder",
                "--options-builder",
                f"{bad_module}:builder",
            ]
        )


def test_django_seed_cli_module_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = _write_demo_module(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    scenario_file = tmp_path / "module_scenarios.json"
    manifest_file = tmp_path / "module_manifest.json"
    sys.modules.pop("djvrt.django_seed_cli", None)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "djvrt.django_seed_cli",
            "--seeder",
            f"{module_name}:DemoSeeder",
            "--scenario-file",
            str(scenario_file),
            "--manifest-file",
            str(manifest_file),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("djvrt.django_seed_cli", run_name="__main__")
    assert exc.value.code == 0
    assert scenario_file.exists()
    assert manifest_file.exists()
