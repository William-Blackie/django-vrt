from __future__ import annotations

from pathlib import Path

from djvrt.models import DJVRTConfig
from djvrt.paths import (
    artifact_root,
    baseline_dir,
    lock_file_path,
    project_root_from_config,
    run_dir,
    runs_dir,
    scenario_file_path,
)


def test_paths_helpers_resolve_relative_project_paths(tmp_path: Path) -> None:
    config = DJVRTConfig()
    config_path = tmp_path / "nested" / "djvrt.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("version = 1\nbase_url = 'http://example.test'\n", encoding="utf-8")

    root = project_root_from_config(config_path)
    assert root == config_path.parent.resolve()
    assert artifact_root(config, config_path) == root / ".djvrt"
    assert scenario_file_path(config, config_path) == root / ".djvrt/scenarios.json"
    assert lock_file_path(config, config_path) == root / "djvrt.lock.json"
    assert baseline_dir(config, config_path, "abc123") == root / ".djvrt" / "baselines" / "abc123"
    assert runs_dir(config, config_path) == root / ".djvrt" / "runs"
    assert run_dir(config, config_path, "run-1") == root / ".djvrt" / "runs" / "run-1"
