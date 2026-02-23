from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from djvrt.models import Lockfile, RunSummary, RunTotals, ScenarioResult
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
    mode: str,
    results: list[ScenarioResult],
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
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
    report_dir = path.parent

    for result in summary.results:
        css_class = "pass" if result.passed else "fail"
        mismatch = f"{result.mismatch_ratio * 100:.3f}%" if result.mismatch_ratio is not None else "-"
        baseline_link = _relative(result.baseline_path, report_dir)
        actual_link = _relative(result.actual_path, report_dir)
        diff_link = _relative(result.diff_path, report_dir)

        def maybe_link(link: str, label: str) -> str:
            if not link:
                return "-"
            escaped_link = html.escape(link)
            escaped_label = html.escape(label)
            return f'<a href="{escaped_link}">{escaped_label}</a>'

        rows.append(
            "".join(
                [
                    f'<tr class="{css_class}">',
                    f"<td>{html.escape(result.id)}</td>",
                    f"<td>{html.escape(result.viewport_name)}</td>",
                    f"<td>{html.escape(result.auth_profile)}</td>",
                    f"<td>{html.escape(result.experiment_name)}</td>",
                    f"<td>{html.escape(result.status)}</td>",
                    f"<td>{html.escape(mismatch)}</td>",
                    f"<td>{maybe_link(baseline_link, 'baseline')}</td>",
                    f"<td>{maybe_link(actual_link, 'actual')}</td>",
                    f"<td>{maybe_link(diff_link, 'diff')}</td>",
                    f"<td>{html.escape(result.error or '')}</td>",
                    "</tr>",
                ]
            )
        )

    html_doc = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>djvrt report {html.escape(summary.run_id)}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #d5d5d5; padding: 6px 8px; font-size: 13px; text-align: left; }}
      th {{ background: #f5f5f5; }}
      tr.pass {{ background: #f2fff6; }}
      tr.fail {{ background: #fff3f3; }}
      .stats {{ margin-bottom: 16px; }}
      .stats code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
    </style>
  </head>
  <body>
    <h1>djvrt report</h1>
    <p class="stats">
      run_id=<code>{html.escape(summary.run_id)}</code>
      lock=<code>{html.escape(summary.lock_hash)}</code>
      passed=<code>{summary.totals.passed}/{summary.totals.total}</code>
      regressions=<code>{summary.totals.regressions}</code>
      capture_errors=<code>{summary.totals.capture_errors}</code>
      baseline_missing=<code>{summary.totals.baseline_missing}</code>
      dimension_mismatches=<code>{summary.totals.dimension_mismatches}</code>
    </p>
    <table>
      <thead>
        <tr>
          <th>scenario</th>
          <th>viewport</th>
          <th>auth</th>
          <th>experiment</th>
          <th>status</th>
          <th>mismatch</th>
          <th>baseline</th>
          <th>actual</th>
          <th>diff</th>
          <th>error</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows)}
      </tbody>
    </table>
  </body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")
