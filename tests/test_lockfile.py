from __future__ import annotations

from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

import djvrt.lockfile as lockfile_module
from djvrt.lockfile import (
    _merge_query_params,
    _playwright_version,
    _unique,
    build_lockfile,
    read_lockfile,
    write_lockfile,
)
from djvrt.models import (
    AuthProfile,
    DiscoveredScenario,
    DJVRTConfig,
    ExperimentVariant,
    LockEnvironment,
    Lockfile,
    Viewport,
)


def test_lockfile_matrix_is_deterministic() -> None:
    config = DJVRTConfig(
        base_url="http://example.test",
        viewports=[
            Viewport(name="desktop", width=1200, height=800),
            Viewport(name="mobile", width=390, height=844),
        ],
        auth_profiles=[
            AuthProfile(name="anonymous"),
            AuthProfile(name="staff", storage_state=".auth/staff.json"),
        ],
    )

    scenarios = [
        DiscoveredScenario(id="home", url="/", viewports=["desktop"], auth_profiles=["anonymous"]),
        DiscoveredScenario(id="about", url="/about/"),
    ]

    first = build_lockfile(config, scenarios)
    second = build_lockfile(config, scenarios)

    assert first.hash == second.hash
    assert len(first.scenarios) == 5
    assert all(scenario.url.startswith("http://example.test") for scenario in first.scenarios)
    assert {scenario.experiment_name for scenario in first.scenarios} == {"control"}


def test_lockfile_expands_experiment_variants() -> None:
    config = DJVRTConfig(
        base_url="http://example.test",
        viewports=[Viewport(name="desktop", width=1200, height=800)],
        auth_profiles=[AuthProfile(name="anonymous", headers={"X-Auth": "anon"})],
        experiments=[
            ExperimentVariant(name="control"),
            ExperimentVariant(
                name="variant-a",
                query_params={"exp_banner": "variant-a"},
                headers={"X-Experiment": "variant-a"},
            ),
        ],
    )

    scenarios = [DiscoveredScenario(id="home", url="/", experiments=["control", "variant-a"])]
    lockfile = build_lockfile(config, scenarios)

    assert len(lockfile.scenarios) == 2
    experiment_names = {scenario.experiment_name for scenario in lockfile.scenarios}
    assert experiment_names == {"control", "variant-a"}

    variant = next(scenario for scenario in lockfile.scenarios if scenario.experiment_name == "variant-a")
    assert "exp_banner=variant-a" in variant.url
    assert variant.headers["X-Auth"] == "anon"
    assert variant.headers["X-Experiment"] == "variant-a"


def test_playwright_version_returns_none_when_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_not_found(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(lockfile_module, "version", _raise_not_found)
    assert _playwright_version() is None


def test_merge_query_params_merges_and_overrides() -> None:
    merged = _merge_query_params("https://example.test/path?a=1&b=2", {"b": "3", "c": "4"})
    assert "a=1" in merged
    assert "b=3" in merged
    assert "c=4" in merged


def test_unique_preserves_order_and_deduplicates() -> None:
    assert _unique(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_build_lockfile_errors_on_unknown_matrix_entries() -> None:
    config = DJVRTConfig(
        base_url="https://example.test",
        viewports=[Viewport(name="desktop", width=1280, height=720)],
        auth_profiles=[AuthProfile(name="anonymous")],
        experiments=[ExperimentVariant(name="control")],
    )

    with pytest.raises(ValueError, match="Unknown viewport"):
        build_lockfile(config, [DiscoveredScenario(id="x", url="/", viewports=["mobile"])])

    with pytest.raises(ValueError, match="Unknown auth profile"):
        build_lockfile(config, [DiscoveredScenario(id="x", url="/", auth_profiles=["staff"])])

    with pytest.raises(ValueError, match="Unknown experiment"):
        build_lockfile(config, [DiscoveredScenario(id="x", url="/", experiments=["variant"])])


def test_write_and_read_lockfile_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "a" / "lock.json"
    lockfile = Lockfile(
        lock_version=1,
        generated_at=datetime.now(UTC),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.13",
            platform="test",
            playwright_version="1.0",
        ),
        scenarios=[],
        hash="lockhash",
    )
    write_lockfile(path, lockfile)
    loaded = read_lockfile(path)
    assert loaded.hash == lockfile.hash
    assert loaded.environment.platform == "test"
