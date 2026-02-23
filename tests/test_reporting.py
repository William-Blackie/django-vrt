from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from djvrt.models import RunSummary, RunTotals, ScenarioResult
from djvrt.reporting import write_html_report


def _summary(tmp_path: Path) -> RunSummary:
    baseline = tmp_path / "baseline.png"
    actual = tmp_path / "actual.png"
    diff = tmp_path / "diff.png"
    baseline.write_bytes(b"baseline")
    actual.write_bytes(b"actual")
    diff.write_bytes(b"diff")

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
    assert 'id="sort-by"' in html
    assert 'id="compare-slider"' in html
    assert 'id="djvrt-report-data"' in html
    assert "Inspect" in html
    assert "Side by side" in html
    assert "Open baseline" in html
    assert 'href="baseline.png"' in html


def test_write_html_report_escapes_embedded_json_script_content(tmp_path: Path) -> None:
    report_path = tmp_path / "report.html"
    write_html_report(report_path, _summary(tmp_path))
    html = report_path.read_text(encoding="utf-8")

    assert "bad &lt;/script&gt; scenario" in html
    assert "<\\/script>" in html
