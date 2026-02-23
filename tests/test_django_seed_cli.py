from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from djvrt.django_seed_cli import main


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


def test_django_seed_cli_runs_with_hook_builder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
