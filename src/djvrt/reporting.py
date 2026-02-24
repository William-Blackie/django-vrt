from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Literal

from djvrt.models import Lockfile, RunSummary, RunTotals, ScenarioResult
from djvrt.report_templates import get_report_html
from djvrt.utils import utcnow


def _build_totals(results: list[ScenarioResult]) -> RunTotals:
    return RunTotals(
        total=len(results),
        passed=sum(1 for result in results if result.status == "passed"),
        regressions=sum(1 for result in results if result.status == "regression"),
        capture_errors=sum(1 for result in results if result.status == "capture_error"),
        baseline_missing=sum(1 for result in results if result.status == "baseline_missing"),
        dimension_mismatches=sum(1 for result in results if result.status == "dimension_mismatch"),
    )


def build_summary(
    *,
    run_id: str,
    lockfile_path: Path,
    lockfile: Lockfile,
    mode: Literal["check", "baseline"],
    results: list[ScenarioResult],
    report_title: str | None = None,
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        report_title=report_title,
        lock_hash=lockfile.hash,
        lock_file=str(lockfile_path),
        mode=mode,
        created_at=utcnow(),
        totals=_build_totals(results),
        results=results,
    )


def write_summary(path: Path, summary: RunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = summary.model_dump(mode="json")
    # indent was misplaced in write_text, should be in json.dumps
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_summary(path: Path) -> RunSummary:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RunSummary.model_validate(payload)


def write_junit(path: Path, summary: RunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    failures = (
        summary.totals.regressions
        + summary.totals.capture_errors
        + summary.totals.baseline_missing
        + summary.totals.dimension_mismatches
    )

    testsuite = ET.Element(
        "testsuite",
        attrib={
            "name": "djvrt",
            "tests": str(summary.totals.total),
            "failures": str(failures),
            "errors": "0",
            "skipped": "0",
        },
    )

    for result in summary.results:
        testcase = ET.SubElement(
            testsuite,
            "testcase",
            attrib={
                "classname": "djvrt.visual",
                "name": (f"{result.id}[{result.viewport_name}|{result.auth_profile}|{result.experiment_name}]"),
            },
        )

        if not result.passed:
            message = result.error or f"status={result.status}, mismatch={result.mismatch_ratio}"
            failure = ET.SubElement(testcase, "failure", attrib={"message": result.status})
            failure.text = message

    tree = ET.ElementTree(testsuite)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _relative(path: str | None, report_dir: Path) -> str:
    if not path:
        return ""
    try:
        return os.path.relpath(path, start=report_dir)
    except ValueError:
        # relpath can fail on different drives.
        return path


def write_html_report(path: Path, summary: RunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[str] = []
    row_data: list[dict[str, Any]] = []
    report_dir = path.parent

    for index, result in enumerate(summary.results):
        baseline_link = _relative(result.baseline_path, report_dir)
        actual_link = _relative(result.actual_path, report_dir)
        diff_link = _relative(result.diff_path, report_dir)

        mismatch_pct = f"{result.mismatch_ratio * 100:.2f}%" if result.mismatch_ratio is not None else "0.00%"

        status_class = "badge-passed" if result.passed else "badge-failed"
        if result.status in ("baseline_missing", "dimension_mismatch"):
            status_class = "badge-warn"

        row_data.append(
            {
                "index": index,
                "id": result.id,
                "url": result.url,
                "viewport": result.viewport_name,
                "auth": result.auth_profile,
                "experiment": result.experiment_name,
                "status": result.status,
                "passed": result.passed,
                "mismatch": mismatch_pct,
                "error": result.error or "",
                "baseline": baseline_link,
                "actual": actual_link,
                "diff": diff_link,
            }
        )

        rows.append(
            f"""
            <tr class="result-row" data-index="{index}" data-passed="{"true" if result.passed else "false"}">
              <td>
                <div class="scenario-cell">
                  <span class="scenario-id">{html.escape(result.id)}</span>
                  <span class="scenario-url">{html.escape(result.url)}</span>
                </div>
              </td>
              <td>
                <div style="font-size: 12px; color: var(--text-muted);">
                   <strong>{html.escape(result.viewport_name)}</strong><br/>
                   {html.escape(result.auth_profile)} • {html.escape(result.experiment_name)}
                </div>
              </td>
              <td>
                <span class="badge {status_class}">{html.escape(result.status)}</span>
              </td>
              <td style="text-align: right;" class="mono">
                {mismatch_pct}
              </td>
              <td>
                <div style="display: flex; gap: 4px;">
                   <button class="btn" style="padding: 4px 8px; font-size: 11px;"
                           onclick="event.stopPropagation(); window.open('{actual_link}', '_blank')">View</button>
                </div>
              </td>
            </tr>
            """
        )

    total_failures = (
        summary.totals.regressions
        + summary.totals.capture_errors
        + summary.totals.baseline_missing
        + summary.totals.dimension_mismatches
    )

    summary_data = {
        "run_id": summary.run_id,
        "title": summary.report_title,
        "lock_hash": summary.lock_hash,
        "mode": summary.mode,
        "totals": summary.totals.model_dump(),
        "total_failures": total_failures,
    }

    html_doc = get_report_html(summary_data, row_data, "".join(rows))
    path.write_text(html_doc, encoding="utf-8")
