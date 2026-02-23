from __future__ import annotations

import json
import shutil
import webbrowser
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import typer
from rich.console import Console

from djvrt.auth_state import create_form_auth_state
from djvrt.capture import capture_scenarios
from djvrt.config import (
    DEFAULT_CONFIG_FILENAME,
    default_scenarios,
    load_config,
    write_default_config,
)
from djvrt.data import DataContext, DataPhase, DataPreparationError, prepare_data
from djvrt.diffing import compare_against_baseline
from djvrt.discovery import DiscoveryError, discover_scenarios, read_scenarios, write_scenarios
from djvrt.lockfile import build_lockfile, read_lockfile, write_lockfile
from djvrt.models import CaptureOutcome, DJVRTConfig, Lockfile, ScenarioResult
from djvrt.paths import (
    artifact_root,
    baseline_dir,
    lock_file_path,
    project_root_from_config,
    run_dir,
    scenario_file_path,
)
from djvrt.reporting import (
    build_summary,
    read_summary,
    write_html_report,
    write_junit,
    write_summary,
)

app = typer.Typer(help="Deterministic visual regression testing for Django", no_args_is_help=True)
console = Console()


def _now_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _format_duration(seconds: float) -> str:
    return f"{seconds:.2f}s"


def _capture_progress_logger(*, label: str) -> Callable[[int, int], None]:
    started = perf_counter()
    last_reported = 0

    def _log(completed: int, total: int) -> None:
        nonlocal last_reported
        if total <= 0:
            return

        step = max(1, total // 8)
        if completed != total and (completed - last_reported) < step:
            return

        last_reported = completed
        percent = int((completed / total) * 100)
        console.print(
            f"[cyan]{label}[/cyan] "
            f"completed={completed}/{total} ({percent}%) "
            f"elapsed={_format_duration(perf_counter() - started)}"
        )

    return _log


def _load_config(config_path: Path) -> tuple[Path, DJVRTConfig]:
    resolved = config_path.resolve()
    if not resolved.exists():
        console.print(f"[red]Config not found:[/red] {resolved}")
        raise typer.Exit(code=2)
    return resolved, load_config(resolved)


def _load_lock(config: DJVRTConfig, config_path: Path, lock_path: Path | None) -> tuple[Path, Lockfile]:
    resolved_lock_path = lock_path.resolve() if lock_path else lock_file_path(config, config_path)
    if not resolved_lock_path.exists():
        console.print(f"[red]Lockfile not found:[/red] {resolved_lock_path}")
        raise typer.Exit(code=2)
    return resolved_lock_path, read_lockfile(resolved_lock_path)


def _open_report(path: Path) -> None:
    report_path = path.resolve()
    try:
        opened = webbrowser.open(report_path.as_uri())
    except Exception as exc:  # pragma: no cover - environment/browser dependent
        console.print(f"[yellow]Could not open report:[/yellow] {exc}")
        return

    if opened:
        console.print(f"[green]Opened report:[/green] {report_path}")
    else:
        console.print(f"[yellow]Could not open report automatically:[/yellow] {report_path}")


def _prepare_data_or_exit(
    *,
    config: DJVRTConfig,
    config_path: Path,
    phase: DataPhase,
    skip_data_prepare: bool,
    run_id: str | None = None,
    lock_hash: str | None = None,
) -> None:
    if skip_data_prepare:
        console.print("[yellow]Skipping data preparation (--skip-data-prepare)[/yellow]")
        return

    context = DataContext(
        project_root=project_root_from_config(config_path),
        config_path=config_path,
        phase=phase,
        run_id=run_id,
        lock_hash=lock_hash,
    )
    try:
        result = prepare_data(config, context=context)
    except DataPreparationError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if result.executed_commands or result.loader_called:
        console.print(
            "[green]Prepared data[/green] "
            f"(commands={len(result.executed_commands)}, loader_called={result.loader_called})"
        )


@app.command()
def init(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config and scenario skeleton"),
) -> None:
    """Create djvrt.toml and initial scenario file."""
    config_path = config_path.resolve()
    try:
        write_default_config(config_path, force=force)
    except FileExistsError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    config = load_config(config_path)
    root_artifacts = artifact_root(config, config_path)
    root_artifacts.mkdir(parents=True, exist_ok=True)
    (root_artifacts / "runs").mkdir(parents=True, exist_ok=True)
    (root_artifacts / "baselines").mkdir(parents=True, exist_ok=True)

    scenarios_path = scenario_file_path(config, config_path)
    if force or not scenarios_path.exists():
        scenarios_path.parent.mkdir(parents=True, exist_ok=True)
        scenarios_path.write_text(
            json.dumps(default_scenarios(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    console.print(f"[green]Created config:[/green] {config_path}")
    console.print(f"[green]Created scenarios:[/green] {scenarios_path}")
    console.print("Next steps:")
    console.print("  1) uv sync --extra dev")
    console.print("  2) uv run playwright install chromium")
    console.print("  3) uv run djvrt discover --config djvrt.toml")
    console.print("  4) uv run djvrt lock --config djvrt.toml")
    console.print("  5) uv run djvrt baseline --config djvrt.toml")


@app.command()
def discover(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    settings: str | None = typer.Option(None, "--settings", help="DJANGO_SETTINGS_MODULE for URL discovery"),
    output: Path | None = typer.Option(None, "--output", help="Write discovered scenarios to this file"),
    skip_data_prepare: bool = typer.Option(
        False,
        "--skip-data-prepare",
        help="Skip configured data preparation hooks",
    ),
) -> None:
    """Discover URL scenarios from sitemap and Django URLConf."""
    config_path, config = _load_config(config_path)
    _prepare_data_or_exit(
        config=config,
        config_path=config_path,
        phase="discover",
        skip_data_prepare=skip_data_prepare,
    )

    try:
        scenarios = discover_scenarios(config, settings_module=settings)
    except DiscoveryError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    if not scenarios:
        console.print("[yellow]No scenarios discovered.[/yellow]")
        raise typer.Exit(code=1)

    output_path = output.resolve() if output else scenario_file_path(config, config_path)
    write_scenarios(output_path, scenarios)

    console.print(f"[green]Discovered {len(scenarios)} scenarios[/green]")
    console.print(f"Saved: {output_path}")


@app.command(name="lock")
def lock_cmd(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    scenarios: Path | None = typer.Option(None, "--scenarios", help="Path to scenario JSON"),
    output: Path | None = typer.Option(None, "--output", help="Path for lockfile JSON"),
) -> None:
    """Build deterministic scenario matrix lockfile."""
    started = perf_counter()
    config_path, config = _load_config(config_path)

    scenario_path = scenarios.resolve() if scenarios else scenario_file_path(config, config_path)
    if not scenario_path.exists():
        console.print(f"[red]Scenario file not found:[/red] {scenario_path}")
        raise typer.Exit(code=2)

    scenario_models = read_scenarios(scenario_path)
    console.print(
        "[cyan]Building lockfile[/cyan] "
        f"(source={scenario_path}, scenarios={len(scenario_models)})"
    )

    build_started = perf_counter()
    lockfile = build_lockfile(config, scenario_models)
    build_elapsed = perf_counter() - build_started

    output_path = output.resolve() if output else lock_file_path(config, config_path)
    write_lockfile(output_path, lockfile)

    console.print(f"[green]Lockfile generated:[/green] {output_path}")
    console.print(f"hash={lockfile.hash} scenarios={len(lockfile.scenarios)}")
    console.print(
        " ".join(
            [
                f"build_duration={_format_duration(build_elapsed)}",
                f"duration={_format_duration(perf_counter() - started)}",
            ]
        )
    )


def _baseline_results(lockfile: Lockfile, captures: dict[str, CaptureOutcome]) -> list[ScenarioResult]:
    results: list[ScenarioResult] = []
    for scenario in lockfile.scenarios:
        capture = captures.get(scenario.key)
        if capture is None or capture.status != "ok" or capture.image_path is None:
            results.append(
                ScenarioResult(
                    key=scenario.key,
                    id=scenario.id,
                    url=scenario.url,
                    viewport_name=scenario.viewport_name,
                    auth_profile=scenario.auth_profile,
                    experiment_name=scenario.experiment_name,
                    status="capture_error",
                    passed=False,
                    threshold=scenario.threshold,
                    error=capture.error if capture else "No capture output",
                )
            )
            continue

        results.append(
            ScenarioResult(
                key=scenario.key,
                id=scenario.id,
                url=scenario.url,
                viewport_name=scenario.viewport_name,
                auth_profile=scenario.auth_profile,
                experiment_name=scenario.experiment_name,
                status="passed",
                passed=True,
                threshold=scenario.threshold,
                baseline_path=capture.image_path,
                actual_path=capture.image_path,
            )
        )

    return results


@app.command()
def baseline(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    lock_path: Path | None = typer.Option(None, "--lock", help="Path to lockfile"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing baseline for this lock hash"),
    open_report: bool = typer.Option(
        False,
        "--open",
        help="Open generated HTML report in default browser",
    ),
    skip_data_prepare: bool = typer.Option(
        False,
        "--skip-data-prepare",
        help="Skip configured data preparation hooks",
    ),
) -> None:
    """Capture baseline images for the current lockfile."""
    started = perf_counter()
    config_path, config = _load_config(config_path)
    resolved_lock_path, lockfile = _load_lock(config, config_path, lock_path)

    baseline_path = baseline_dir(config, config_path, lockfile.hash)
    if baseline_path.exists():
        if not force:
            console.print(f"[red]Baseline already exists:[/red] {baseline_path} (pass --force to replace)")
            raise typer.Exit(code=2)
        shutil.rmtree(baseline_path)

    baseline_path.mkdir(parents=True, exist_ok=True)
    run_id = f"baseline-{_now_run_id()}"
    console.print(
        "[cyan]Capturing baseline[/cyan] "
        f"(run_id={run_id}, lock={lockfile.hash}, scenarios={len(lockfile.scenarios)})"
    )

    _prepare_data_or_exit(
        config=config,
        config_path=config_path,
        phase="baseline",
        skip_data_prepare=skip_data_prepare,
        run_id=run_id,
        lock_hash=lockfile.hash,
    )

    project_root = project_root_from_config(config_path)
    capture_started = perf_counter()
    captures = capture_scenarios(
        lockfile,
        config=config,
        project_root=project_root,
        output_dir=baseline_path,
        progress_callback=_capture_progress_logger(label="Baseline capture progress"),
    )
    capture_elapsed = perf_counter() - capture_started

    current_run_dir = run_dir(config, config_path, run_id)
    current_run_dir.mkdir(parents=True, exist_ok=True)

    results = _baseline_results(lockfile, captures)
    summary = build_summary(
        run_id=run_id,
        lockfile_path=resolved_lock_path,
        lockfile=lockfile,
        mode="baseline",
        results=results,
    )

    summary_path = current_run_dir / "summary.json"
    junit_path = current_run_dir / "junit.xml"
    html_path = current_run_dir / "report.html"

    write_summary(summary_path, summary)
    write_junit(junit_path, summary)
    write_html_report(html_path, summary)

    console.print(f"[green]Baseline captured:[/green] {baseline_path}")
    console.print(f"summary={summary_path}")
    console.print(
        " ".join(
            [
                f"capture_duration={_format_duration(capture_elapsed)}",
                f"duration={_format_duration(perf_counter() - started)}",
                f"capture_errors={summary.totals.capture_errors}",
            ]
        )
    )

    if open_report:
        _open_report(html_path)

    if summary.totals.capture_errors > 0:
        console.print(f"[red]Capture errors:[/red] {summary.totals.capture_errors}")
        raise typer.Exit(code=1)


@app.command()
def check(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    lock_path: Path | None = typer.Option(None, "--lock", help="Path to lockfile"),
    run_id: str | None = typer.Option(None, "--run-id", help="Run identifier for artifact folder"),
    open_report: bool = typer.Option(
        False,
        "--open",
        help="Open generated HTML report in default browser",
    ),
    retry_regressions: int = typer.Option(
        1,
        "--retry-regressions",
        min=0,
        max=5,
        help="Recapture and re-compare failed regressions this many times",
    ),
    skip_data_prepare: bool = typer.Option(
        False,
        "--skip-data-prepare",
        help="Skip configured data preparation hooks",
    ),
) -> None:
    """Capture current screenshots and compare to baseline."""
    started = perf_counter()
    config_path, config = _load_config(config_path)
    resolved_lock_path, lockfile = _load_lock(config, config_path, lock_path)

    baseline_path = baseline_dir(config, config_path, lockfile.hash)
    if not baseline_path.exists():
        console.print(f"[red]Baseline not found:[/red] {baseline_path}")
        console.print("Create it first with: djvrt baseline")
        raise typer.Exit(code=2)

    final_run_id = run_id or _now_run_id()
    current_run_dir = run_dir(config, config_path, final_run_id)
    actual_dir = current_run_dir / "actual"
    diff_dir = current_run_dir / "diff"
    console.print(
        "[cyan]Running check[/cyan] "
        f"(run_id={final_run_id}, lock={lockfile.hash}, scenarios={len(lockfile.scenarios)})"
    )

    if current_run_dir.exists():
        shutil.rmtree(current_run_dir)
    actual_dir.mkdir(parents=True, exist_ok=True)
    diff_dir.mkdir(parents=True, exist_ok=True)
    _prepare_data_or_exit(
        config=config,
        config_path=config_path,
        phase="check",
        skip_data_prepare=skip_data_prepare,
        run_id=final_run_id,
        lock_hash=lockfile.hash,
    )

    project_root = project_root_from_config(config_path)
    capture_started = perf_counter()
    captures = capture_scenarios(
        lockfile,
        config=config,
        project_root=project_root,
        output_dir=actual_dir,
        progress_callback=_capture_progress_logger(label="Check capture progress"),
    )
    capture_elapsed = perf_counter() - capture_started

    compare_started = perf_counter()
    results = compare_against_baseline(
        lockfile,
        captures=captures,
        baseline_dir=baseline_path,
        diff_dir=diff_dir,
        pixel_tolerance=config.runtime.pixel_tolerance,
        workers=config.runtime.workers,
        always_write_diff_images=config.runtime.always_write_diff_images,
    )
    compare_elapsed = perf_counter() - compare_started

    retries_used = 0
    result_by_key = {result.key: result for result in results}

    for attempt in range(retry_regressions):
        failing_keys = {key for key, result in result_by_key.items() if result.status == "regression"}
        if not failing_keys:
            break

        retries_used = attempt + 1
        console.print(
            "[yellow]Retrying regressions[/yellow] "
            f"(attempt={retries_used}/{retry_regressions}, scenarios={len(failing_keys)})"
        )
        retry_capture_started = perf_counter()
        retry_captures = capture_scenarios(
            lockfile,
            config=config,
            project_root=project_root,
            output_dir=actual_dir,
            scenario_keys=failing_keys,
            progress_callback=_capture_progress_logger(
                label=f"Retry capture progress ({retries_used}/{retry_regressions})"
            ),
        )
        capture_elapsed += perf_counter() - retry_capture_started
        captures.update(retry_captures)

        retry_compare_started = perf_counter()
        retried_results = compare_against_baseline(
            lockfile,
            captures=captures,
            baseline_dir=baseline_path,
            diff_dir=diff_dir,
            pixel_tolerance=config.runtime.pixel_tolerance,
            scenario_keys=failing_keys,
            workers=config.runtime.workers,
            always_write_diff_images=config.runtime.always_write_diff_images,
        )
        for retried in retried_results:
            result_by_key[retried.key] = retried
        compare_elapsed += perf_counter() - retry_compare_started

    results = [result_by_key[scenario.key] for scenario in lockfile.scenarios]

    summary = build_summary(
        run_id=final_run_id,
        lockfile_path=resolved_lock_path,
        lockfile=lockfile,
        mode="check",
        results=results,
    )

    summary_path = current_run_dir / "summary.json"
    junit_path = current_run_dir / "junit.xml"
    html_path = current_run_dir / "report.html"

    write_summary(summary_path, summary)
    write_junit(junit_path, summary)
    write_html_report(html_path, summary)

    console.print(f"run_id={final_run_id}")
    console.print(f"report={html_path}")
    console.print(
        " ".join(
            [
                f"passed={summary.totals.passed}/{summary.totals.total}",
                f"regressions={summary.totals.regressions}",
                f"capture_errors={summary.totals.capture_errors}",
                f"baseline_missing={summary.totals.baseline_missing}",
                f"dimension_mismatches={summary.totals.dimension_mismatches}",
            ]
        )
    )
    console.print(
        " ".join(
            [
                f"capture_duration={_format_duration(capture_elapsed)}",
                f"compare_duration={_format_duration(compare_elapsed)}",
                f"retries_used={retries_used}",
                f"duration={_format_duration(perf_counter() - started)}",
            ]
        )
    )

    if open_report:
        _open_report(html_path)

    failures = (
        summary.totals.regressions
        + summary.totals.capture_errors
        + summary.totals.baseline_missing
        + summary.totals.dimension_mismatches
    )
    if failures > 0:
        raise typer.Exit(code=1)


@app.command()
def report(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    run_id: str | None = typer.Option(None, "--run-id", help="Run id under .djvrt/runs"),
    summary_file: Path | None = typer.Option(None, "--summary", help="Path to summary.json"),
    html_file: Path | None = typer.Option(None, "--html", help="Path for HTML report output"),
    junit_file: Path | None = typer.Option(None, "--junit", help="Path for JUnit XML output"),
    open_report: bool = typer.Option(
        False,
        "--open",
        help="Open generated HTML report in default browser",
    ),
) -> None:
    """Regenerate reports from an existing summary.json."""
    config_path, config = _load_config(config_path)

    if summary_file is None and run_id is None:
        console.print("[red]Provide --run-id or --summary[/red]")
        raise typer.Exit(code=2)

    if summary_file is None:
        summary_file = run_dir(config, config_path, run_id or "") / "summary.json"

    summary_path = summary_file.resolve()
    if not summary_path.exists():
        console.print(f"[red]Summary not found:[/red] {summary_path}")
        raise typer.Exit(code=2)

    summary = read_summary(summary_path)

    html_path = html_file.resolve() if html_file else summary_path.parent / "report.html"
    junit_path = junit_file.resolve() if junit_file else summary_path.parent / "junit.xml"

    write_html_report(html_path, summary)
    write_junit(junit_path, summary)

    console.print(f"[green]HTML:[/green] {html_path}")
    console.print(f"[green]JUnit:[/green] {junit_path}")
    if open_report:
        _open_report(html_path)


@app.command()
def approve(
    config_path: Path = typer.Option(Path(DEFAULT_CONFIG_FILENAME), "--config", help="Path to djvrt.toml"),
    run_id: str = typer.Option(..., "--run-id", help="Run id to promote from .djvrt/runs/<run_id>/actual"),
    lock_path: Path | None = typer.Option(None, "--lock", help="Path to lockfile (defaults to summary lock path)"),
    allow_capture_errors: bool = typer.Option(
        False,
        "--allow-capture-errors",
        help="Allow baseline promotion when some scenarios had capture errors",
    ),
) -> None:
    """Promote a run's actual screenshots to baseline images."""
    config_path, config = _load_config(config_path)

    current_run_dir = run_dir(config, config_path, run_id)
    summary_path = current_run_dir / "summary.json"
    if not summary_path.exists():
        console.print(f"[red]Run summary not found:[/red] {summary_path}")
        raise typer.Exit(code=2)

    summary = read_summary(summary_path)

    if summary.totals.capture_errors > 0 and not allow_capture_errors:
        console.print(
            f"[red]Run has capture errors ({summary.totals.capture_errors}).[/red] "
            "Rerun check or pass --allow-capture-errors."
        )
        raise typer.Exit(code=2)

    resolved_lock_path: Path
    lockfile: object
    if lock_path:
        resolved_lock_path = lock_path.resolve()
        lockfile = read_lockfile(resolved_lock_path)
    else:
        resolved_lock_path = Path(summary.lock_file).resolve()
        if not resolved_lock_path.exists():
            console.print(f"[red]Lockfile from summary does not exist:[/red] {resolved_lock_path}")
            raise typer.Exit(code=2)
        lockfile = read_lockfile(resolved_lock_path)

    destination = baseline_dir(config, config_path, lockfile.hash)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    copied = 0
    for result in summary.results:
        if not result.actual_path:
            continue
        source = Path(result.actual_path)
        if not source.exists():
            if allow_capture_errors:
                continue
            console.print(f"[red]Missing actual image:[/red] {source}")
            raise typer.Exit(code=2)
        shutil.copy2(source, destination / source.name)
        copied += 1

    (destination / "APPROVED_FROM_RUN.txt").write_text(
        f"run_id={run_id}\nlock_file={resolved_lock_path}\napproved_at={datetime.now(UTC).isoformat()}\n",
        encoding="utf-8",
    )

    console.print(f"[green]Promoted baseline:[/green] {destination}")
    console.print(f"copied_images={copied}")


@app.command(name="auth-state")
def auth_state_cmd(
    base_url: str = typer.Option("http://localhost:8000", "--base-url", help="Application base URL"),
    login_path: str = typer.Option("/accounts/login/", "--login-path", help="Login page path"),
    email: str = typer.Option(..., "--email", help="Login email"),
    password: str = typer.Option(..., "--password", help="Login password"),
    output: Path = typer.Option(
        Path(".djvrt/auth/user.json"),
        "--output",
        help="Output path for Playwright storage_state JSON",
    ),
    next_path: str = typer.Option("/", "--next-path", help="Path to open after successful login"),
    timeout_ms: int = typer.Option(45_000, "--timeout-ms", min=1, help="Navigation timeout in ms"),
    email_selector: str = typer.Option(
        "input[type='email']",
        "--email-selector",
        help="CSS selector for email input",
    ),
    password_selector: str = typer.Option(
        "input[type='password']",
        "--password-selector",
        help="CSS selector for password input",
    ),
    submit_selector: str = typer.Option(
        "button[type='submit']",
        "--submit-selector",
        help="CSS selector for submit button",
    ),
    wait_until: str = typer.Option(
        "domcontentloaded",
        "--wait-until",
        help="Playwright wait_until strategy for login navigation",
    ),
) -> None:
    """Create a deterministic Playwright auth storage state file."""
    try:
        output_path = create_form_auth_state(
            base_url=base_url,
            login_path=login_path,
            email=email,
            password=password,
            output=output.resolve(),
            next_path=next_path,
            timeout_ms=timeout_ms,
            email_selector=email_selector,
            password_selector=password_selector,
            submit_selector=submit_selector,
            wait_until=wait_until,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    console.print(f"[green]Wrote auth storage_state:[/green] {output_path}")


if __name__ == "__main__":
    app()
