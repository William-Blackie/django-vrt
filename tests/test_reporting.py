from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from djvrt.models import LockEnvironment, Lockfile, RunSummary, RunTotals, ScenarioResult
from djvrt.reporting import _relative, build_summary, read_summary, write_html_report, write_junit, write_summary


def _summary(tmp_path: Path) -> RunSummary:
    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    
    # Create real images
    Image.new("RGB", (1, 1), color="white").save(baseline)
    Image.new("RGB", (1, 1), color="white").save(actual)
    Image.new("RGB", (1, 1), color="red").save(diff)

    results = [
        ScenarioResult(
            key="scenario-pass",
            id="home",
            url="http://example.test/",
            viewport_name="desktop",
            auth_profile="anonymous",
            experiment_name="control",
            status="passed",
            passed=True,
            threshold=0.001,
            mismatch_ratio=0.0,
            baseline_path=str(baseline),
            actual_path=str(actual),
            diff_path=str(diff),
        ),
        ScenarioResult(
            key="scenario-fail",
            id="bad </script> scenario",
            url="http://example.test/bad",
            viewport_name="mobile",
            auth_profile="signed_in",
            experiment_name="variant-a",
            status="regression",
            passed=False,
            threshold=0.001,
            mismatch_ratio=0.2,
            baseline_path=str(baseline),
            actual_path=str(actual),
            diff_path=str(diff),
            error="pixel mismatch",
        ),
    ]

    return RunSummary(
        run_id="run-1",
        lock_hash="abc123",
        lock_file="djvrt.lock.json",
        mode="check",
        created_at=datetime.now(UTC),
        totals=RunTotals(
            total=2,
            passed=1,
            regressions=1,
            capture_errors=0,
            baseline_missing=0,
            dimension_mismatches=0,
        ),
        results=results,
    )


def test_write_html_report_renders_interactive_review_ui(tmp_path: Path) -> None:
    report_path = tmp_path / "report.html"
    write_html_report(report_path, _summary(tmp_path))
    html = report_path.read_text(encoding="utf-8")

    assert 'id="filter-search"' in html
    assert 'id="filter-status"' in html
    assert 'id="djvrt-data"' in html
    assert "djvrt report" in html
    assert "Side by Side" in html
    assert '"baseline":"baseline.png"' in html


def test_write_html_report_escapes_embedded_json_script_content(tmp_path: Path) -> None:
    report_path = tmp_path / "report.html"
    write_html_report(report_path, _summary(tmp_path))
    html = report_path.read_text(encoding="utf-8")

    assert "bad &lt;/script&gt; scenario" in html


def test_write_self_contained_html_report(tmp_path: Path) -> None:
    # Create a dummy image
    img_path = tmp_path / "baseline.png"
    Image.new("RGB", (10, 10), color="red").save(img_path)

    summary = _summary(tmp_path)
    # Ensure the path is absolute for embedding logic
    img_abs_path = img_path.resolve()
    summary.results[0].baseline_path = str(img_abs_path)

    report_path = tmp_path / "report-bundled.html"
    write_html_report(report_path, summary, self_contained=True)
    html_content = report_path.read_text(encoding="utf-8")

    # Verify data URL is present in the JSON payload
    assert "data:image/webp;base64," in html_content
    # Relative path should NOT be present in this mode for the baseline link
    assert '"baseline":"baseline.png"' not in html_content


def test_summary_roundtrip_and_junit_output(tmp_path: Path) -> None:
    summary = _summary(tmp_path)
    summary_file = tmp_path / "summary.json"
    junit_file = tmp_path / "junit.xml"

    write_summary(summary_file, summary)
    loaded = read_summary(summary_file)
    assert loaded.totals.total == 2
    assert loaded.totals.regressions == 1

    write_junit(junit_file, loaded)
    xml = junit_file.read_text(encoding="utf-8")
    assert 'tests="2"' in xml
    assert 'failures="1"' in xml
    assert "pixel mismatch" in xml


def test_build_summary_counts_baseline_missing_and_capture_errors(tmp_path: Path) -> None:
    lockfile_path = tmp_path / "lock.json"
    summary = build_summary(
        run_id="run-1",
        lockfile_path=lockfile_path,
        lockfile=Lockfile(
            lock_version=1,
            generated_at=datetime.now(UTC),
            config_digest="digest",
            environment=LockEnvironment(
                python_version="3.13",
                platform="test",
                playwright_version="1.0",
            ),
            scenarios=[],
            hash="h1",
        ),
        mode="check",
        results=[
            ScenarioResult(
                key="1",
                id="a",
                url="https://example.test/a",
                viewport_name="desktop",
                auth_profile="anon",
                experiment_name="control",
                status="baseline_missing",
                passed=False,
                threshold=0.001,
            ),
            ScenarioResult(
                key="2",
                id="b",
                url="https://example.test/b",
                viewport_name="desktop",
                auth_profile="anon",
                experiment_name="control",
                status="capture_error",
                passed=False,
                threshold=0.001,
                error="boom",
            ),
        ],
    )
    assert summary.totals.baseline_missing == 1
    assert summary.totals.capture_errors == 1


def test_relative_returns_original_path_when_relpath_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.path.relpath", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError))
    original = "/different/drive/report.png"
    assert _relative(original, Path("/tmp")) == original


def test_relative_returns_empty_string_for_none_path() -> None:
    assert _relative(None, Path(".")) == ""


def test_write_html_report_uses_dash_for_missing_artifact_links(tmp_path: Path) -> None:
    summary = RunSummary(
        run_id="run-missing-links",
        lock_hash="abc",
        lock_file="lock.json",
        mode="check",
        created_at=datetime.now(UTC),
        totals=RunTotals(
            total=1,
            passed=0,
            regressions=1,
            capture_errors=0,
            baseline_missing=0,
            dimension_mismatches=0,
        ),
        results=[
            ScenarioResult(
                key="k1",
                id="home",
                url="http://example.test/",
                viewport_name="desktop",
                auth_profile="anonymous",
                experiment_name="control",
                status="regression",
                passed=False,
                threshold=0.001,
                error="no links",
            )
        ],
    )
    report_path = tmp_path / "report-missing-links.html"
    write_html_report(report_path, summary)
    html = report_path.read_text(encoding="utf-8")
    # In new JSON structure, missing links are empty strings
    assert '"baseline":""' in html
    assert '"actual":""' in html
    assert '"diff":""' in html
