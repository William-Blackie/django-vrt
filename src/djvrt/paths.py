from __future__ import annotations

from pathlib import Path

from djvrt.models import DJVRTConfig
from djvrt.utils import resolve_path


def project_root_from_config(config_path: Path) -> Path:
    return config_path.parent.resolve()


def artifact_root(config: DJVRTConfig, config_path: Path) -> Path:
    root = project_root_from_config(config_path)
    return resolve_path(root, config.paths.artifact_dir)


def scenario_file_path(config: DJVRTConfig, config_path: Path) -> Path:
    root = project_root_from_config(config_path)
    return resolve_path(root, config.paths.scenario_file)


def lock_file_path(config: DJVRTConfig, config_path: Path) -> Path:
    root = project_root_from_config(config_path)
    return resolve_path(root, config.paths.lock_file)


def baseline_dir(config: DJVRTConfig, config_path: Path, lock_hash: str) -> Path:
    return artifact_root(config, config_path) / "baselines" / lock_hash


def runs_dir(config: DJVRTConfig, config_path: Path) -> Path:
    return artifact_root(config, config_path) / "runs"


def run_dir(config: DJVRTConfig, config_path: Path, run_id: str) -> Path:
    return runs_dir(config, config_path) / run_id
