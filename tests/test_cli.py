from __future__ import annotations

import json
import re
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest
import typer

import djvrt.cli as cli
from djvrt.data import DataPreparationError, DataPreparationResult
from djvrt.discovery import DiscoveryError
from djvrt.models import (
    CaptureOutcome,
    DiscoveredScenario,
    DJVRTConfig,
    LockedScenario,
    LockEnvironment,
    Lockfile,
    RunSummary,
    RunTotals,
    ScenarioResult,
)


class _ConsoleRecorder:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, *args: object, **kwargs: object) -> None:
        del kwargs
        self.messages.append(" ".join(str(arg) for arg in args))


def _scenario(key: str = "home-key") -> LockedScenario:
    return LockedScenario(
        key=key,
        id="home",
        url="http://example.test/",
        tags=[],
        viewport_name="desktop",
        experiment_name="control",
        width=1200,
        height=800,
        auth_profile="anonymous",
        storage_state=None,
        headers={},
        threshold=0.001,
        wait_for_selector=None,
        wait_for_timeout_ms=0,
        mask_selectors=[],
        hide_selectors=[],
        full_page=True,
    )


def _lockfile(*scenarios: LockedScenario) -> Lockfile:
    return Lockfile(
        lock_version=1,
        generated_at=datetime.now(UTC),
        config_digest="digest",
        environment=LockEnvironment(
            python_version="3.13",
            platform="test",
            playwright_version="1.0",
        ),
        scenarios=list(scenarios),
        hash="lock-hash",
    )


def _summary(
    *,
    mode: Literal["check", "baseline"],
    results: list[ScenarioResult],
    capture_errors: int = 0,
    regressions: int = 0,
    baseline_missing: int = 0,
    dimension_mismatches: int = 0,
) -> RunSummary:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    return RunSummary(
        run_id="run-1",
        lock_hash="lock-hash",
        lock_file="djvrt.lock.json",
        mode=mode,
        created_at=datetime.now(UTC),
        totals=RunTotals(
            total=total,
            passed=passed,
            regressions=regressions,
            capture_errors=capture_errors,
            baseline_missing=baseline_missing,
            dimension_mismatches=dimension_mismatches,
        ),
        results=results,
    )


def _passed_result(key: str = "home-key", actual_path: str | None = "/tmp/actual.png") -> ScenarioResult:
    return ScenarioResult(
        key=key,
        id="home",
        url="http://example.test/",
        viewport_name="desktop",
        auth_profile="anonymous",
        experiment_name="control",
        status="passed",
        passed=True,
        threshold=0.001,
        baseline_path="/tmp/baseline.png",
        actual_path=actual_path,
    )


def _regression_result(key: str = "home-key") -> ScenarioResult:
    return ScenarioResult(
        key=key,
        id="home",
        url="http://example.test/",
        viewport_name="desktop",
        auth_profile="anonymous",
        experiment_name="control",
        status="regression",
        passed=False,
        threshold=0.001,
        baseline_path="/tmp/baseline.png",
        actual_path="/tmp/actual.png",
        diff_path="/tmp/diff.png",
    )


def test_now_run_id_and_format_duration_helpers() -> None:
    run_id = cli._now_run_id()
    assert re.match(r"^\d{8}-\d{6}$", run_id) is not None
    assert cli._format_duration(1.234) == "1.23s"


def test_capture_progress_logger_reports_by_step(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    times = iter([0.0, 0.5, 1.0, 1.5])
    monkeypatch.setattr(cli, "perf_counter", lambda: next(times))

    logger = cli._capture_progress_logger(label="Capture")
    logger(0, 0)
    logger(1, 8)
    logger(1, 8)
    logger(8, 8)

    assert len(recorder.messages) == 2
    assert "completed=1/8" in recorder.messages[0]
    assert "completed=8/8" in recorder.messages[1]


def test_load_config_and_load_lock_missing_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)

    with pytest.raises(typer.Exit) as missing_config:
        cli._load_config(tmp_path / "missing.toml")
    assert missing_config.value.exit_code == 2

    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text("version = 1\n", encoding="utf-8")
    with pytest.raises(typer.Exit) as missing_lock:
        cli._load_lock(config, config_path, tmp_path / "missing.lock.json")
    assert missing_lock.value.exit_code == 2


def test_load_config_and_load_lock_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = DJVRTConfig(base_url="http://example.test")
    lockfile = _lockfile(_scenario())
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text("ok", encoding="utf-8")
    lock_path = tmp_path / "djvrt.lock.json"
    lock_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(cli, "load_config", lambda _: config)
    monkeypatch.setattr(cli, "read_lockfile", lambda _: lockfile)

    resolved_config, loaded_config = cli._load_config(config_path)
    resolved_lock, loaded_lock = cli._load_lock(config, config_path, lock_path)

    assert resolved_config == config_path.resolve()
    assert loaded_config.base_url == "http://example.test"
    assert resolved_lock == lock_path.resolve()
    assert loaded_lock.hash == "lock-hash"


def test_open_report_handles_success_failure_and_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    path = tmp_path / "report.html"
    path.write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr("djvrt.cli.webbrowser.open", lambda _: True)
    cli._open_report(path)

    monkeypatch.setattr("djvrt.cli.webbrowser.open", lambda _: False)
    cli._open_report(path)

    def _raise(_: str) -> bool:
        raise RuntimeError("browser missing")

    monkeypatch.setattr("djvrt.cli.webbrowser.open", _raise)
    cli._open_report(path)

    assert any("Opened report" in message for message in recorder.messages)
    assert any("Could not open report automatically" in message for message in recorder.messages)
    assert any("Could not open report" in message for message in recorder.messages)


def test_prepare_data_or_exit_skip_error_and_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text("version = 1\n", encoding="utf-8")

    cli._prepare_data_or_exit(
        config=config,
        config_path=config_path,
        phase="discover",
        skip_data_prepare=True,
    )

    def _fail_prepare(_: DJVRTConfig, *, context: object) -> DataPreparationResult:
        del context
        raise DataPreparationError("failed")

    monkeypatch.setattr(cli, "prepare_data", _fail_prepare)
    with pytest.raises(typer.Exit) as exc:
        cli._prepare_data_or_exit(
            config=config,
            config_path=config_path,
            phase="check",
            skip_data_prepare=False,
        )
    assert exc.value.exit_code == 2

    monkeypatch.setattr(
        cli,
        "prepare_data",
        lambda *_args, **_kwargs: DataPreparationResult(executed_commands=["echo hi"], loader_called=True),
    )
    cli._prepare_data_or_exit(
        config=config,
        config_path=config_path,
        phase="baseline",
        skip_data_prepare=False,
    )
    assert any("Prepared data" in message for message in recorder.messages)


def test_init_writes_config_and_scenarios(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)

    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    scenarios_path = tmp_path / "custom" / "scenarios.json"
    artifacts_dir = tmp_path / ".djvrt"

    monkeypatch.setattr(cli, "write_default_config", lambda path, force=False: path.write_text("ok", encoding="utf-8"))
    monkeypatch.setattr(cli, "load_config", lambda _: config)
    monkeypatch.setattr(cli, "artifact_root", lambda *_args, **_kwargs: artifacts_dir)
    monkeypatch.setattr(cli, "scenario_file_path", lambda *_args, **_kwargs: scenarios_path)
    monkeypatch.setattr(cli, "default_scenarios", lambda: [{"id": "home", "url": "/"}])

    cli.init(config_path=config_path, force=False)

    assert (artifacts_dir / "runs").exists()
    assert (artifacts_dir / "baselines").exists()
    assert scenarios_path.exists()
    assert json.loads(scenarios_path.read_text(encoding="utf-8")) == [{"id": "home", "url": "/"}]


def test_init_exits_when_config_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)

    def _raise_exists(_: Path, *, force: bool = False) -> None:
        del force
        raise FileExistsError("already exists")

    monkeypatch.setattr(cli, "write_default_config", _raise_exists)
    with pytest.raises(typer.Exit) as exc:
        cli.init(config_path=tmp_path / "djvrt.toml", force=False)
    assert exc.value.exit_code == 2


def test_discover_handles_error_empty_and_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    monkeypatch.setattr(cli, "_prepare_data_or_exit", lambda **_: None)

    def _raise_discovery(_: DJVRTConfig, settings_module: str | None = None) -> list[DiscoveredScenario]:
        del settings_module
        raise DiscoveryError("boom")

    monkeypatch.setattr(cli, "discover_scenarios", _raise_discovery)
    with pytest.raises(typer.Exit) as exc_error:
        cli.discover(config_path=config_path, settings=None, output=None, skip_data_prepare=False)
    assert exc_error.value.exit_code == 2

    monkeypatch.setattr(cli, "discover_scenarios", lambda *_args, **_kwargs: [])
    with pytest.raises(typer.Exit) as exc_empty:
        cli.discover(config_path=config_path, settings=None, output=None, skip_data_prepare=False)
    assert exc_empty.value.exit_code == 1

    saved: dict[str, Any] = {}
    output_path = tmp_path / "out.json"
    monkeypatch.setattr(
        cli,
        "discover_scenarios",
        lambda *_args, **_kwargs: [DiscoveredScenario(id="home", url="http://example.test/")],
    )

    def _write_scenarios(path: Path, scenarios: list[DiscoveredScenario]) -> None:
        saved.update({"path": path, "count": len(scenarios)})

    monkeypatch.setattr(
        cli,
        "write_scenarios",
        _write_scenarios,
    )
    cli.discover(config_path=config_path, settings="project.settings", output=output_path, skip_data_prepare=True)
    assert saved["path"] == output_path.resolve()
    assert saved["count"] == 1


def test_lock_command_missing_scenario_file_and_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    config_path.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    missing_scenarios_path = tmp_path / "missing_scenarios.json"
    monkeypatch.setattr(cli, "scenario_file_path", lambda *_args, **_kwargs: missing_scenarios_path)

    with pytest.raises(typer.Exit) as exc:
        cli.lock_cmd(config_path=config_path, scenarios=None, output=None)
    assert exc.value.exit_code == 2

    scenarios_path = tmp_path / "scenarios.json"
    scenarios_path.write_text("[]", encoding="utf-8")
    lockfile = _lockfile(_scenario())
    captured: dict[str, Any] = {}
    monkeypatch.setattr(cli, "read_scenarios", lambda _: [DiscoveredScenario(id="home", url="http://example.test/")])
    monkeypatch.setattr(cli, "build_lockfile", lambda *_args, **_kwargs: lockfile)
    monkeypatch.setattr(cli, "write_lockfile", lambda path, lock: captured.update({"path": path, "hash": lock.hash}))
    cli.lock_cmd(config_path=config_path, scenarios=scenarios_path, output=tmp_path / "lock.json")
    assert captured["hash"] == "lock-hash"


def test_baseline_results_maps_capture_errors_and_success() -> None:
    lockfile = _lockfile(_scenario("ok"), _scenario("missing"))
    captures = {"ok": CaptureOutcome(key="ok", status="ok", image_path="/tmp/ok.png")}
    results = cli._baseline_results(lockfile, captures)
    assert [result.status for result in results] == ["passed", "capture_error"]


def test_baseline_command_blocks_existing_baseline_without_force(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    lockfile = _lockfile(_scenario())
    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    monkeypatch.setattr(cli, "_load_lock", lambda *_args, **_kwargs: (tmp_path / "djvrt.lock.json", lockfile))
    existing_baseline = tmp_path / "baselines" / lockfile.hash
    existing_baseline.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cli, "baseline_dir", lambda *_args, **_kwargs: existing_baseline)

    with pytest.raises(typer.Exit) as exc:
        cli.baseline(config_path=config_path, lock_path=None, force=False, open_report=False, skip_data_prepare=False)
    assert exc.value.exit_code == 2


def test_baseline_command_success_and_capture_error_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    lockfile = _lockfile(_scenario())
    run_path = tmp_path / "runs" / "baseline-fixed"
    baseline_path = tmp_path / "baselines" / lockfile.hash
    written: list[Path] = []
    open_calls: list[Path] = []

    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    monkeypatch.setattr(cli, "_load_lock", lambda *_args, **_kwargs: (tmp_path / "djvrt.lock.json", lockfile))
    monkeypatch.setattr(cli, "baseline_dir", lambda *_args, **_kwargs: baseline_path)
    monkeypatch.setattr(cli, "_now_run_id", lambda: "fixed")
    monkeypatch.setattr(cli, "_prepare_data_or_exit", lambda **_: None)
    monkeypatch.setattr(cli, "project_root_from_config", lambda _: tmp_path)
    monkeypatch.setattr(
        cli,
        "capture_scenarios",
        lambda *_args, **_kwargs: {"home-key": CaptureOutcome(key="home-key", status="ok", image_path="/tmp/home.png")},
    )
    monkeypatch.setattr(cli, "run_dir", lambda *_args, **_kwargs: run_path)
    monkeypatch.setattr(cli, "write_summary", lambda path, *_args, **_kwargs: written.append(path))
    monkeypatch.setattr(cli, "write_junit", lambda path, *_args, **_kwargs: written.append(path))
    monkeypatch.setattr(cli, "write_html_report", lambda path, *_args, **_kwargs: written.append(path))
    monkeypatch.setattr(cli, "_open_report", lambda path: open_calls.append(path))

    monkeypatch.setattr(
        cli,
        "build_summary",
        lambda **_kwargs: _summary(mode="baseline", results=[_passed_result()], capture_errors=0),
    )
    cli.baseline(config_path=config_path, lock_path=None, force=True, open_report=True, skip_data_prepare=False)
    assert open_calls and open_calls[0].name == "report.html"
    assert len(written) == 3

    monkeypatch.setattr(
        cli,
        "build_summary",
        lambda **_kwargs: _summary(mode="baseline", results=[_passed_result()], capture_errors=1),
    )
    with pytest.raises(typer.Exit) as exc:
        cli.baseline(config_path=config_path, lock_path=None, force=True, open_report=False, skip_data_prepare=False)
    assert exc.value.exit_code == 1


def test_check_command_baseline_missing_and_retry_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    lockfile = _lockfile(_scenario("home-key"))
    run_path = tmp_path / "runs" / "run-1"
    baseline_path = tmp_path / "baselines" / lockfile.hash
    scenario_key_calls: list[set[str] | None] = []

    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    monkeypatch.setattr(cli, "_load_lock", lambda *_args, **_kwargs: (tmp_path / "djvrt.lock.json", lockfile))
    monkeypatch.setattr(cli, "baseline_dir", lambda *_args, **_kwargs: baseline_path)
    monkeypatch.setattr(cli, "run_dir", lambda *_args, **_kwargs: run_path)
    monkeypatch.setattr(cli, "_prepare_data_or_exit", lambda **_: None)
    monkeypatch.setattr(cli, "project_root_from_config", lambda _: tmp_path)

    def _capture_scenarios(*_args: Any, **kwargs: Any) -> dict[str, CaptureOutcome]:
        scenario_key_calls.append(kwargs.get("scenario_keys"))
        return {"home-key": CaptureOutcome(key="home-key", status="ok", image_path="/tmp/home.png")}

    monkeypatch.setattr(cli, "capture_scenarios", _capture_scenarios)

    with pytest.raises(typer.Exit) as missing_baseline:
        cli.check(config_path=config_path, lock_path=None, run_id=None, open_report=False, retry_regressions=1)
    assert missing_baseline.value.exit_code == 2

    baseline_path.mkdir(parents=True, exist_ok=True)
    compare_calls = {"count": 0}

    def _compare(*_args: Any, **kwargs: Any) -> list[ScenarioResult]:
        compare_calls["count"] += 1
        if compare_calls["count"] == 1:
            assert kwargs.get("scenario_keys") is None
            return [_regression_result()]
        assert kwargs.get("scenario_keys") == {"home-key"}
        return [_regression_result()]

    monkeypatch.setattr(cli, "compare_against_baseline", _compare)
    monkeypatch.setattr(
        cli,
        "build_summary",
        lambda **_kwargs: _summary(mode="check", results=[_regression_result()], regressions=1),
    )
    monkeypatch.setattr(cli, "write_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "write_junit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "write_html_report", lambda *_args, **_kwargs: None)

    with pytest.raises(typer.Exit) as failed_check:
        cli.check(config_path=config_path, lock_path=None, run_id="run-1", open_report=False, retry_regressions=1)
    assert failed_check.value.exit_code == 1
    assert scenario_key_calls[0] is None
    assert scenario_key_calls[1] == {"home-key"}


def test_check_command_success_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    lockfile = _lockfile(_scenario("home-key"))
    run_path = tmp_path / "runs" / "run-ok"
    run_path.mkdir(parents=True, exist_ok=True)
    (run_path / "stale.txt").write_text("stale", encoding="utf-8")
    baseline_path = tmp_path / "baselines" / lockfile.hash
    baseline_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    monkeypatch.setattr(cli, "_load_lock", lambda *_args, **_kwargs: (tmp_path / "djvrt.lock.json", lockfile))
    monkeypatch.setattr(cli, "baseline_dir", lambda *_args, **_kwargs: baseline_path)
    monkeypatch.setattr(cli, "run_dir", lambda *_args, **_kwargs: run_path)
    monkeypatch.setattr(cli, "_prepare_data_or_exit", lambda **_: None)
    monkeypatch.setattr(cli, "project_root_from_config", lambda _: tmp_path)
    monkeypatch.setattr(
        cli,
        "capture_scenarios",
        lambda *_args, **_kwargs: {"home-key": CaptureOutcome(key="home-key", status="ok", image_path="/tmp/home.png")},
    )
    monkeypatch.setattr(cli, "compare_against_baseline", lambda *_args, **_kwargs: [_passed_result()])
    monkeypatch.setattr(cli, "build_summary", lambda **_kwargs: _summary(mode="check", results=[_passed_result()]))
    monkeypatch.setattr(cli, "write_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "write_junit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "write_html_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_open_report", lambda *_args, **_kwargs: None)

    cli.check(config_path=config_path, lock_path=None, run_id="run-ok", open_report=True, retry_regressions=1)


def test_report_command_validation_and_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))

    with pytest.raises(typer.Exit) as exc_missing_args:
        cli.report(
            config_path=config_path,
            run_id=None,
            summary_file=None,
            html_file=None,
            junit_file=None,
            open_report=False,
        )
    assert exc_missing_args.value.exit_code == 2

    with pytest.raises(typer.Exit) as exc_missing_summary:
        cli.report(
            config_path=config_path,
            run_id=None,
            summary_file=tmp_path / "missing-summary.json",
            html_file=None,
            junit_file=None,
            open_report=False,
        )
    assert exc_missing_summary.value.exit_code == 2

    summary_file = tmp_path / "summary.json"
    summary_file.write_text("{}", encoding="utf-8")
    opened: list[Path] = []
    outputs: list[Path] = []

    def _read_summary(*_args: Any, **_kwargs: Any) -> RunSummary:
        return _summary(mode="check", results=[_passed_result()])

    monkeypatch.setattr(
        cli,
        "read_summary",
        _read_summary,
    )
    monkeypatch.setattr(cli, "write_html_report", lambda path, *_args, **_kwargs: outputs.append(path))
    monkeypatch.setattr(cli, "write_junit", lambda path, *_args, **_kwargs: outputs.append(path))
    monkeypatch.setattr(cli, "_open_report", lambda path: opened.append(path))
    cli.report(
        config_path=config_path,
        run_id=None,
        summary_file=summary_file,
        html_file=tmp_path / "report.html",
        junit_file=tmp_path / "junit.xml",
        open_report=True,
    )
    assert len(outputs) == 2
    assert opened and opened[0].name == "report.html"

    run_summary_dir = tmp_path / "runs" / "run-from-id"
    run_summary_dir.mkdir(parents=True, exist_ok=True)
    run_summary_file = run_summary_dir / "summary.json"
    run_summary_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "run_dir", lambda *_args, **_kwargs: run_summary_dir)
    outputs.clear()
    cli.report(
        config_path=config_path,
        run_id="run-from-id",
        summary_file=None,
        html_file=None,
        junit_file=None,
        open_report=False,
    )
    assert any(path.name == "report.html" for path in outputs)
    assert any(path.name == "junit.xml" for path in outputs)


def test_approve_command_validation_and_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    config = DJVRTConfig(base_url="http://example.test")
    config_path = tmp_path / "djvrt.toml"
    run_dir = tmp_path / "runs" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "summary.json"

    monkeypatch.setattr(cli, "_load_config", lambda _: (config_path, config))
    monkeypatch.setattr(cli, "run_dir", lambda *_args, **_kwargs: run_dir)

    with pytest.raises(typer.Exit) as missing_summary:
        cli.approve(config_path=config_path, run_id="run-1", lock_path=None, allow_capture_errors=False)
    assert missing_summary.value.exit_code == 2

    summary_path.write_text("{}", encoding="utf-8")
    summary_with_errors = _summary(mode="check", results=[_passed_result()], capture_errors=1)
    monkeypatch.setattr(cli, "read_summary", lambda *_args, **_kwargs: summary_with_errors)
    with pytest.raises(typer.Exit) as capture_errors:
        cli.approve(config_path=config_path, run_id="run-1", lock_path=None, allow_capture_errors=False)
    assert capture_errors.value.exit_code == 2

    missing_lock_summary = _summary(mode="check", results=[_passed_result()], capture_errors=0)
    missing_lock_summary = missing_lock_summary.model_copy(update={"lock_file": str(tmp_path / "missing.lock.json")})
    monkeypatch.setattr(cli, "read_summary", lambda *_args, **_kwargs: missing_lock_summary)
    with pytest.raises(typer.Exit) as missing_lock:
        cli.approve(config_path=config_path, run_id="run-1", lock_path=None, allow_capture_errors=False)
    assert missing_lock.value.exit_code == 2

    missing_actual_summary = _summary(
        mode="check",
        results=[_passed_result(actual_path=str(tmp_path / "no-image.png"))],
        capture_errors=0,
    )
    monkeypatch.setattr(cli, "read_summary", lambda *_args, **_kwargs: missing_actual_summary)
    monkeypatch.setattr(cli, "read_lockfile", lambda *_args, **_kwargs: _lockfile(_scenario()))
    monkeypatch.setattr(cli, "baseline_dir", lambda *_args, **_kwargs: tmp_path / "baselines" / "lock-hash")
    with pytest.raises(typer.Exit) as missing_actual:
        cli.approve(
            config_path=config_path,
            run_id="run-1",
            lock_path=tmp_path / "provided.lock.json",
            allow_capture_errors=False,
        )
    assert missing_actual.value.exit_code == 2

    actual_image = tmp_path / "actual.png"
    actual_image.write_bytes(b"img")
    ok_summary = _summary(
        mode="check",
        results=[_passed_result(actual_path=str(actual_image))],
        capture_errors=0,
    )
    monkeypatch.setattr(cli, "read_summary", lambda *_args, **_kwargs: ok_summary)
    destination = tmp_path / "baselines" / "lock-hash"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "old.png").write_bytes(b"old")
    monkeypatch.setattr(cli, "baseline_dir", lambda *_args, **_kwargs: destination)
    cli.approve(
        config_path=config_path, run_id="run-1", lock_path=tmp_path / "provided.lock.json", allow_capture_errors=True
    )
    assert (destination / "actual.png").exists()
    approval = (destination / "APPROVED_FROM_RUN.txt").read_text(encoding="utf-8")
    assert "run_id=run-1" in approval

    summary_lock_file = tmp_path / "summary.lock.json"
    summary_lock_file.write_text("{}", encoding="utf-8")
    summary_with_skips = _summary(
        mode="check",
        results=[
            _passed_result(actual_path=None),
            _passed_result(actual_path=str(tmp_path / "missing-image.png")),
        ],
        capture_errors=1,
    ).model_copy(update={"lock_file": str(summary_lock_file)})
    monkeypatch.setattr(cli, "read_summary", lambda *_args, **_kwargs: summary_with_skips)
    cli.approve(config_path=config_path, run_id="run-1", lock_path=None, allow_capture_errors=True)
    assert (destination / "APPROVED_FROM_RUN.txt").exists()


def test_auth_state_command_success_and_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorder = _ConsoleRecorder()
    monkeypatch.setattr(cli, "console", recorder)
    output = tmp_path / "auth" / "user.json"

    monkeypatch.setattr(cli, "create_form_auth_state", lambda **_kwargs: output)
    cli.auth_state_cmd(email="seed@example.test", password="secret", output=output)
    assert any("Wrote auth storage_state" in message for message in recorder.messages)

    def _raise_runtime(**_kwargs: Any) -> Path:
        raise RuntimeError("invalid credentials")

    monkeypatch.setattr(cli, "create_form_auth_state", _raise_runtime)
    with pytest.raises(typer.Exit) as exc:
        cli.auth_state_cmd(email="seed@example.test", password="secret", output=output)
    assert exc.value.exit_code == 2


def test_cli_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    original_cli_module = sys.modules.get("djvrt.cli")
    sys.modules.pop("djvrt.cli", None)
    monkeypatch.setattr(sys, "argv", ["djvrt.cli", "--help"])
    try:
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("djvrt.cli", run_name="__main__")
        assert exc.value.code == 0
    finally:
        if original_cli_module is None:
            sys.modules.pop("djvrt.cli", None)
        else:
            sys.modules["djvrt.cli"] = original_cli_module


def test_example_report_command(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from djvrt.cli import app

    runner = CliRunner()

    report_path = tmp_path / "example-report.html"
    # Use --no-open to avoid opening browser in tests
    result = runner.invoke(app, ["example-report", "--output", str(report_path), "--no-open"])
    assert result.exit_code == 0
    assert report_path.exists()
    assert "Example report generated at:" in result.stdout
    assert "djvrt report" in report_path.read_text(encoding="utf-8")


def test_example_report_command_with_title(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from djvrt.cli import app

    runner = CliRunner()

    report_path = tmp_path / "example-report.html"
    result = runner.invoke(
        app, ["example-report", "--output", str(report_path), "--no-open", "--title", "Custom Raccoons"]
    )
    assert result.exit_code == 0
    assert "Custom Raccoons" in report_path.read_text(encoding="utf-8")


def test_example_report_command_self_contained(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from djvrt.cli import app

    runner = CliRunner()

    report_path = tmp_path / "example-report.html"
    result = runner.invoke(app, ["example-report", "--output", str(report_path), "--no-open", "--self-contained"])
    assert result.exit_code == 0
    assert "data:image/webp;base64," in report_path.read_text(encoding="utf-8")
