from __future__ import annotations

from pathlib import Path

import pytest

import djvrt.config as config_module
from djvrt.config import default_scenarios, load_config, write_default_config


def test_load_config_normalizes_optional_blank_values(tmp_path: Path) -> None:
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text(
        """
version = 1
base_url = "http://example.test"

[runtime]
browser_channel = ""

[data]
enabled = true
loader = ""
cwd = ""

[[auth_profiles]]
name = "anon"
storage_state = ""
""".strip(),
        encoding="utf-8",
    )

    loaded = load_config(config_path)
    assert loaded.runtime.browser_channel is None
    assert loaded.data.loader is None
    assert loaded.data.cwd is None
    assert loaded.auth_profiles[0].storage_state is None


def test_load_config_raises_for_invalid_content(tmp_path: Path) -> None:
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text('base_url = "example.test"', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid config"):
        load_config(config_path)


def test_write_default_config_respects_force_flag(tmp_path: Path) -> None:
    config_path = tmp_path / "djvrt.toml"
    write_default_config(config_path)
    assert config_path.exists()

    with pytest.raises(FileExistsError, match="already exists"):
        write_default_config(config_path)

    write_default_config(config_path, force=True)
    assert config_path.read_text(encoding="utf-8").startswith("version = 1")


def test_default_scenarios_shape() -> None:
    scenarios = default_scenarios()
    assert scenarios[0]["id"] == "home"
    assert scenarios[0]["url"] == "/"


def test_default_config_filename_constant_is_exposed() -> None:
    assert config_module.DEFAULT_CONFIG_FILENAME == "djvrt.toml"
