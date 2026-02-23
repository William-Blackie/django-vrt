from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal

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
    mode: Literal["check", "baseline"],
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


def _json_script_payload(data: object) -> str:
    # Prevent accidental </script> termination in embedded JSON.
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")


def write_html_report(path: Path, summary: RunSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[str] = []
    row_data: list[dict[str, object]] = []
    report_dir = path.parent

    for index, result in enumerate(summary.results):
        css_class = "pass" if result.passed else "fail"
        mismatch = f"{result.mismatch_ratio * 100:.3f}%" if result.mismatch_ratio is not None else "-"
        mismatch_sort = result.mismatch_ratio if result.mismatch_ratio is not None else -1.0
        baseline_link = _relative(result.baseline_path, report_dir)
        actual_link = _relative(result.actual_path, report_dir)
        diff_link = _relative(result.diff_path, report_dir)
        search_text = " ".join(
            [
                result.id,
                result.url,
                result.viewport_name,
                result.auth_profile,
                result.experiment_name,
                result.status,
            ]
        ).lower()

        def maybe_link(link: str, label: str) -> str:
            if not link:
                return "-"
            escaped_link = html.escape(link)
            escaped_label = html.escape(label)
            return f'<a href="{escaped_link}" target="_blank" rel="noreferrer">{escaped_label}</a>'

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
                "mismatch": mismatch,
                "threshold": result.threshold,
                "error": result.error or "",
                "baseline": baseline_link,
                "actual": actual_link,
                "diff": diff_link,
            }
        )

        rows.append(
            "".join(
                [
                    (
                        f'<tr class="result-row {css_class}" '
                        f'data-index="{index}" '
                        f'data-status="{html.escape(result.status, quote=True)}" '
                        f'data-mismatch="{mismatch_sort:.8f}" '
                        f'data-search="{html.escape(search_text, quote=True)}">'
                    ),
                    (
                        "<td>"
                        f'<div class="scenario-id">{html.escape(result.id)}</div>'
                        f'<div class="scenario-url">{html.escape(result.url)}</div>'
                        "</td>"
                    ),
                    (
                        "<td>"
                        f"<div>{html.escape(result.viewport_name)}</div>"
                        f'<div class="meta-muted">{html.escape(result.auth_profile)}</div>'
                        "</td>"
                    ),
                    f"<td>{html.escape(result.experiment_name)}</td>",
                    (
                        "<td>"
                        f'<span class="status-pill status-{html.escape(result.status)}">'
                        f"{html.escape(result.status)}"
                        "</span>"
                        "</td>"
                    ),
                    f'<td class="mono">{html.escape(mismatch)}</td>',
                    f'<td class="mono">{result.threshold:.4f}</td>',
                    (
                        "<td>"
                        f'{maybe_link(baseline_link, "baseline")} '
                        f'{maybe_link(actual_link, "actual")} '
                        f'{maybe_link(diff_link, "diff")}'
                        "</td>"
                    ),
                    f'<td class="error-cell">{html.escape(result.error or "")}</td>',
                    (f'<td><button class="inspect-btn" data-index="{index}" type="button">' "Inspect" "</button></td>"),
                    "</tr>",
                ]
            )
        )

    data_payload = _json_script_payload(row_data)
    html_doc = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>djvrt report {html.escape(summary.run_id)}</title>
    <style>
      :root {{
        --bg: #f6f8fb;
        --panel: #ffffff;
        --border: #d7dde6;
        --text: #131a23;
        --muted: #5b677a;
        --pass: #0b7f42;
        --fail: #b42318;
        --accent: #1b61d1;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: var(--text);
        background: var(--bg);
      }}
      .page {{
        max-width: 1600px;
        margin: 20px auto;
        padding: 0 18px 28px;
      }}
      h1 {{ margin: 0 0 12px; font-size: 28px; }}
      .summary {{
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 12px;
      }}
      .card {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 10px 12px;
      }}
      .card .label {{
        display: block;
        font-size: 12px;
        color: var(--muted);
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .card .value {{ font-size: 20px; font-weight: 700; }}
      .toolbar {{
        display: grid;
        grid-template-columns: 1.2fr 0.8fr 0.8fr auto auto auto;
        gap: 8px;
        align-items: center;
        margin-bottom: 12px;
      }}
      .toolbar > * {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 8px 10px;
        font-size: 13px;
      }}
      .toolbar input[type="text"],
      .toolbar select {{ width: 100%; }}
      .toolbar .checkbox {{
        display: flex;
        align-items: center;
        gap: 8px;
      }}
      .toolbar button {{
        cursor: pointer;
        color: var(--text);
      }}
      .toolbar button:hover {{
        border-color: #b9c5d8;
      }}
      .run-meta {{
        margin-bottom: 10px;
        color: var(--muted);
        font-size: 12px;
      }}
      .layout {{
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 12px;
        align-items: start;
      }}
      .table-wrap {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 10px;
        overflow: auto;
        max-height: calc(100vh - 180px);
      }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{
        border-bottom: 1px solid var(--border);
        padding: 8px 10px;
        font-size: 13px;
        text-align: left;
        vertical-align: top;
      }}
      th {{
        background: #f1f4f9;
        position: sticky;
        top: 0;
        z-index: 2;
      }}
      tr.result-row {{ cursor: pointer; }}
      tr.result-row.pass {{ background: #f3fcf7; }}
      tr.result-row.fail {{ background: #fff4f4; }}
      tr.result-row.selected {{
        outline: 2px solid var(--accent);
        outline-offset: -2px;
      }}
      .scenario-id {{
        font-weight: 600;
        margin-bottom: 4px;
      }}
      .scenario-url {{
        color: var(--muted);
        max-width: 360px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .meta-muted {{ color: var(--muted); }}
      .status-pill {{
        display: inline-block;
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 12px;
        font-weight: 600;
        background: #eef2f8;
      }}
      .status-passed {{ color: var(--pass); }}
      .status-regression,
      .status-capture_error,
      .status-baseline_missing,
      .status-dimension_mismatch {{
        color: var(--fail);
      }}
      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .error-cell {{
        max-width: 320px;
        color: #7b3340;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .inspect-btn {{
        cursor: pointer;
        border: 1px solid #b9c5d8;
        background: #fff;
        border-radius: 6px;
        padding: 4px 8px;
      }}
      .compare {{
        position: sticky;
        top: 10px;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 12px;
        min-height: 520px;
      }}
      .compare h2 {{
        margin: 0 0 8px;
        font-size: 17px;
      }}
      .compare-meta {{
        margin: 0 0 10px;
        font-size: 12px;
        color: var(--muted);
      }}
      .compare-controls {{
        display: flex;
        gap: 6px;
        margin-bottom: 10px;
        flex-wrap: wrap;
      }}
      .mode-btn {{
        border: 1px solid #b9c5d8;
        background: #fff;
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 12px;
        cursor: pointer;
      }}
      .mode-btn.active {{
        background: #e8f0ff;
        border-color: #9eb6e6;
      }}
      .mode-btn:disabled {{
        cursor: not-allowed;
        opacity: 0.5;
      }}
      .slider-control {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: var(--muted);
        margin-bottom: 10px;
      }}
      .compare-note {{
        margin: 0 0 10px;
        font-size: 12px;
        color: var(--muted);
      }}
      .slider-control input {{ width: 180px; }}
      .pane {{ display: none; }}
      .pane.active {{ display: block; }}
      .compare-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }}
      .image-box {{
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        background: #fafbfd;
      }}
      .image-box .label {{
        display: block;
        font-size: 12px;
        color: var(--muted);
        padding: 6px 8px;
        border-bottom: 1px solid var(--border);
      }}
      .image-box img {{
        display: block;
        width: 100%;
        max-height: 460px;
        object-fit: contain;
        background: #fff;
      }}
      .slider-stage {{
        position: relative;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
      }}
      .slider-stage img {{
        display: block;
        width: 100%;
        max-height: 500px;
        object-fit: contain;
      }}
      .slider-actual-wrap {{
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        overflow: hidden;
        border-right: 2px solid rgba(27, 97, 209, 0.8);
      }}
      .compare-links {{
        margin-top: 10px;
        display: flex;
        gap: 10px;
        font-size: 12px;
      }}
      .empty {{
        color: var(--muted);
        font-size: 13px;
        border: 1px dashed var(--border);
        border-radius: 8px;
        padding: 18px;
        background: #fafbfd;
      }}
      @media (max-width: 1200px) {{
        .layout {{
          grid-template-columns: 1fr;
        }}
        .table-wrap {{ max-height: none; }}
        .compare {{ position: static; min-height: 300px; }}
        .summary {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        .toolbar {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <div class="page">
      <h1>djvrt report</h1>
      <div class="run-meta">
        run_id=<span class="mono">{html.escape(summary.run_id)}</span> |
        lock=<span class="mono">{html.escape(summary.lock_hash)}</span> |
        mode=<span class="mono">{html.escape(summary.mode)}</span>
      </div>

        <div class="summary">
        <div class="card">
          <span class="label">Total</span><span class="value">{summary.totals.total}</span>
        </div>
        <div class="card">
          <span class="label">Passed</span><span class="value">{summary.totals.passed}</span>
        </div>
        <div class="card">
          <span class="label">Regressions</span><span class="value">{summary.totals.regressions}</span>
        </div>
        <div class="card">
          <span class="label">Capture Errors</span><span class="value">{summary.totals.capture_errors}</span>
        </div>
        <div class="card">
          <span class="label">Baseline Missing</span><span class="value">{summary.totals.baseline_missing}</span>
        </div>
        <div class="card">
          <span class="label">Dimension Mismatch</span><span class="value">{summary.totals.dimension_mismatches}</span>
        </div>
        <div class="card">
          <span class="label">Visible Rows</span><span id="visible-count" class="value">{summary.totals.total}</span>
        </div>
      </div>

      <div class="toolbar">
        <input id="filter-search" type="text" placeholder="Search scenario, URL, experiment, auth..." />
        <select id="filter-status">
          <option value="">All statuses</option>
          <option value="regression">regression</option>
          <option value="capture_error">capture_error</option>
          <option value="baseline_missing">baseline_missing</option>
          <option value="dimension_mismatch">dimension_mismatch</option>
          <option value="passed">passed</option>
        </select>
        <select id="sort-by">
          <option value="mismatch_desc">Sort: mismatch (high to low)</option>
          <option value="status_then_id">Sort: status, then scenario</option>
          <option value="scenario_asc">Sort: scenario (A-Z)</option>
        </select>
        <label class="checkbox"><input id="fail-only" type="checkbox" /> Failures only</label>
        <button id="prev-fail" type="button">Prev failure</button>
        <button id="next-fail" type="button">Next failure</button>
      </div>

      <div class="layout">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>scenario</th>
                <th>viewport/auth</th>
                <th>experiment</th>
                <th>status</th>
                <th>mismatch</th>
                <th>threshold</th>
                <th>assets</th>
                <th>error</th>
                <th>inspect</th>
              </tr>
            </thead>
            <tbody id="results-body">
              {"".join(rows)}
            </tbody>
          </table>
        </div>

        <aside class="compare" id="compare-panel">
          <h2>Comparison</h2>
          <p class="compare-meta" id="compare-meta">Select a scenario to inspect.</p>
          <div id="compare-empty" class="empty">
            Select a row or click <strong>Inspect</strong> to compare baseline vs actual quickly.
          </div>
          <div id="compare-content" style="display:none;">
            <div class="compare-controls">
              <button class="mode-btn active" data-compare-mode="side" type="button">Side by side</button>
              <button class="mode-btn" data-compare-mode="slider" type="button">Slider</button>
              <button class="mode-btn" data-compare-mode="diff" type="button">Diff</button>
            </div>
            <p id="compare-note" class="compare-note"></p>
            <div class="slider-control" id="slider-control" style="display:none;">
              <span>Baseline / Actual split</span>
              <input id="compare-slider" type="range" min="1" max="99" value="50" />
              <span id="compare-slider-value">50%</span>
            </div>

            <div class="pane active" id="pane-side">
              <div class="compare-grid">
                <div class="image-box">
                  <span class="label">Baseline</span>
                  <img id="img-side-baseline" alt="Baseline screenshot" />
                </div>
                <div class="image-box">
                  <span class="label">Actual</span>
                  <img id="img-side-actual" alt="Actual screenshot" />
                </div>
              </div>
            </div>

            <div class="pane" id="pane-slider">
              <div class="slider-stage">
                <img id="img-slider-baseline" alt="Baseline screenshot" />
                <div id="slider-actual-wrap" class="slider-actual-wrap" style="width:50%;">
                  <img id="img-slider-actual" alt="Actual screenshot" />
                </div>
              </div>
            </div>

            <div class="pane" id="pane-diff">
              <div class="image-box">
                <span class="label">Diff</span>
                <img id="img-diff" alt="Diff screenshot" />
              </div>
            </div>

            <div class="compare-links">
              <a id="link-baseline" target="_blank" rel="noreferrer">Open baseline</a>
              <a id="link-actual" target="_blank" rel="noreferrer">Open actual</a>
              <a id="link-diff" target="_blank" rel="noreferrer">Open diff</a>
            </div>
          </div>
        </aside>
      </div>
    </div>

    <script id="djvrt-report-data" type="application/json">{data_payload}</script>
    <script>
      const rows = Array.from(document.querySelectorAll("tr.result-row"));
      const tbody = document.getElementById("results-body");
      const visibleCount = document.getElementById("visible-count");
      const filterSearch = document.getElementById("filter-search");
      const filterStatus = document.getElementById("filter-status");
      const failOnly = document.getElementById("fail-only");
      const sortBy = document.getElementById("sort-by");
      const prevFail = document.getElementById("prev-fail");
      const nextFail = document.getElementById("next-fail");

      const compareEmpty = document.getElementById("compare-empty");
      const compareContent = document.getElementById("compare-content");
      const compareMeta = document.getElementById("compare-meta");
      const compareNote = document.getElementById("compare-note");
      const sliderControl = document.getElementById("slider-control");
      const compareSlider = document.getElementById("compare-slider");
      const compareSliderValue = document.getElementById("compare-slider-value");
      const sliderActualWrap = document.getElementById("slider-actual-wrap");

      const imgSideBaseline = document.getElementById("img-side-baseline");
      const imgSideActual = document.getElementById("img-side-actual");
      const imgSliderBaseline = document.getElementById("img-slider-baseline");
      const imgSliderActual = document.getElementById("img-slider-actual");
      const imgDiff = document.getElementById("img-diff");
      const linkBaseline = document.getElementById("link-baseline");
      const linkActual = document.getElementById("link-actual");
      const linkDiff = document.getElementById("link-diff");

      const modeButtons = Array.from(document.querySelectorAll("[data-compare-mode]"));
      const modeButtonsByName = Object.fromEntries(
        modeButtons.map((button) => [button.dataset.compareMode, button])
      );
      const panes = {{
        side: document.getElementById("pane-side"),
        slider: document.getElementById("pane-slider"),
        diff: document.getElementById("pane-diff"),
      }};

      const dataScript = document.getElementById("djvrt-report-data");
      const entries = JSON.parse(dataScript.textContent || "[]");
      const entryByIndex = new Map(entries.map((item) => [String(item.index), item]));
      let selectedIndex = null;

      const statusRank = {{
        regression: 0,
        capture_error: 1,
        baseline_missing: 2,
        dimension_mismatch: 3,
        passed: 4,
      }};

      function isFailure(status) {{
        return status !== "passed";
      }}

      function activeMode() {{
        const active = modeButtons.find((button) => button.classList.contains("active"));
        return active ? active.dataset.compareMode : "side";
      }}

      function firstEnabledMode() {{
        const ordered = ["side", "slider", "diff"];
        for (const mode of ordered) {{
          const button = modeButtonsByName[mode];
          if (button && !button.disabled) {{
            return mode;
          }}
        }}
        return "side";
      }}

      function updateModeAvailability(entry) {{
        const hasBaseline = Boolean(entry.baseline);
        const hasActual = Boolean(entry.actual);
        const hasDiff = Boolean(entry.diff);

        modeButtonsByName.side.disabled = !(hasBaseline && hasActual);
        modeButtonsByName.slider.disabled = !(hasBaseline && hasActual);
        modeButtonsByName.diff.disabled = !hasDiff;

        if (!hasDiff) {{
          if (entry.passed) {{
            compareNote.textContent =
              "No diff image generated for this passed scenario. Baseline and actual images are available.";
          }} else {{
            compareNote.textContent = "No diff image available for this scenario.";
          }}
        }} else {{
          compareNote.textContent = "";
        }}

        const mode = activeMode();
        if (modeButtonsByName[mode] && modeButtonsByName[mode].disabled) {{
          setMode(firstEnabledMode());
        }}
      }}

      function setMode(mode) {{
        const targetButton = modeButtonsByName[mode];
        if (!targetButton || targetButton.disabled) {{
          return;
        }}

        modeButtons.forEach((button) => {{
          button.classList.toggle("active", button.dataset.compareMode === mode);
        }});

        Object.entries(panes).forEach(([name, pane]) => {{
          pane.classList.toggle("active", name === mode);
        }});

        sliderControl.style.display = mode === "slider" ? "flex" : "none";
      }}

      function setImage(img, src, fallbackAlt) {{
        if (src) {{
          img.src = src;
          img.alt = fallbackAlt;
          img.style.display = "block";
        }} else {{
          img.removeAttribute("src");
          img.alt = `Missing: ${{fallbackAlt}}`;
          img.style.display = "none";
        }}
      }}

      function setLink(link, href, label) {{
        if (href) {{
          link.href = href;
          link.style.pointerEvents = "auto";
          link.style.opacity = "1";
          link.textContent = label;
        }} else {{
          link.removeAttribute("href");
          link.style.pointerEvents = "none";
          link.style.opacity = "0.45";
          link.textContent = `${{label}} (missing)`;
        }}
      }}

      function updateSlider() {{
        const value = Number(compareSlider.value);
        sliderActualWrap.style.width = `${{value}}%`;
        compareSliderValue.textContent = `${{value}}%`;
      }}

      function selectRow(row, scrollIntoView = false) {{
        rows.forEach((candidate) => candidate.classList.remove("selected"));
        row.classList.add("selected");
        selectedIndex = row.dataset.index;

        const entry = entryByIndex.get(selectedIndex);
        if (!entry) {{
          return;
        }}

        compareEmpty.style.display = "none";
        compareContent.style.display = "block";
        compareMeta.textContent = [
          entry.id,
          `status=${{entry.status}}`,
          `mismatch=${{entry.mismatch}}`,
          `viewport=${{entry.viewport}}`,
          `auth=${{entry.auth}}`,
          `experiment=${{entry.experiment}}`,
        ].join(" | ");

        setImage(imgSideBaseline, entry.baseline, "Baseline screenshot");
        setImage(imgSideActual, entry.actual, "Actual screenshot");
        setImage(imgSliderBaseline, entry.baseline, "Baseline screenshot");
        setImage(imgSliderActual, entry.actual, "Actual screenshot");
        setImage(imgDiff, entry.diff, "Diff screenshot");

        setLink(linkBaseline, entry.baseline, "Open baseline");
        setLink(linkActual, entry.actual, "Open actual");
        setLink(linkDiff, entry.diff, "Open diff");
        updateModeAvailability(entry);

        if (scrollIntoView) {{
          row.scrollIntoView({{ block: "center", behavior: "smooth" }});
        }}
      }}

      function sortRows() {{
        const key = sortBy.value;
        const sorted = rows.slice().sort((left, right) => {{
          if (key === "scenario_asc") {{
            return left.dataset.search.localeCompare(right.dataset.search);
          }}
          if (key === "status_then_id") {{
            const leftStatus = left.dataset.status || "";
            const rightStatus = right.dataset.status || "";
            const statusCmp = (statusRank[leftStatus] ?? 99) - (statusRank[rightStatus] ?? 99);
            if (statusCmp !== 0) {{
              return statusCmp;
            }}
            return left.dataset.search.localeCompare(right.dataset.search);
          }}
          const leftMismatch = Number(left.dataset.mismatch);
          const rightMismatch = Number(right.dataset.mismatch);
          if (rightMismatch !== leftMismatch) {{
            return rightMismatch - leftMismatch;
          }}
          return left.dataset.search.localeCompare(right.dataset.search);
        }});

        sorted.forEach((row) => tbody.appendChild(row));
      }}

      function applyFilters() {{
        const term = (filterSearch.value || "").trim().toLowerCase();
        const statusFilter = filterStatus.value;
        const onlyFailures = failOnly.checked;

        let visible = 0;
        rows.forEach((row) => {{
          const status = row.dataset.status || "";
          const searchable = row.dataset.search || "";
          const matchesTerm = !term || searchable.includes(term);
          const matchesStatus = !statusFilter || status === statusFilter;
          const matchesFailure = !onlyFailures || isFailure(status);
          const show = matchesTerm && matchesStatus && matchesFailure;
          row.hidden = !show;
          if (show) {{
            visible += 1;
          }}
        }});

        visibleCount.textContent = `${{visible}}`;

        if (selectedIndex) {{
          const selectedRow = rows.find((row) => row.dataset.index === selectedIndex);
          if (selectedRow && selectedRow.hidden) {{
            selectedRow.classList.remove("selected");
          }}
        }}
      }}

      function visibleFailureRows() {{
        return rows.filter((row) => !row.hidden && isFailure(row.dataset.status || ""));
      }}

      function jumpFailure(direction) {{
        const failures = visibleFailureRows();
        if (failures.length === 0) {{
          return;
        }}

        let current = failures.findIndex((row) => row.dataset.index === selectedIndex);
        if (current < 0) {{
          current = direction > 0 ? -1 : 0;
        }}

        const next = (current + direction + failures.length) % failures.length;
        selectRow(failures[next], true);
      }}

      rows.forEach((row) => {{
        row.addEventListener("click", (event) => {{
          if (event.target instanceof HTMLElement && event.target.tagName.toLowerCase() === "a") {{
            return;
          }}
          selectRow(row);
        }});
      }});

      document.querySelectorAll(".inspect-btn").forEach((button) => {{
        button.addEventListener("click", (event) => {{
          event.stopPropagation();
          const index = button.dataset.index;
          const row = rows.find((candidate) => candidate.dataset.index === index);
          if (row) {{
            selectRow(row, true);
          }}
        }});
      }});

      modeButtons.forEach((button) => {{
        button.addEventListener("click", () => setMode(button.dataset.compareMode));
      }});

      compareSlider.addEventListener("input", updateSlider);
      filterSearch.addEventListener("input", applyFilters);
      filterStatus.addEventListener("change", applyFilters);
      failOnly.addEventListener("change", applyFilters);
      sortBy.addEventListener("change", () => {{
        sortRows();
        applyFilters();
      }});
      prevFail.addEventListener("click", () => jumpFailure(-1));
      nextFail.addEventListener("click", () => jumpFailure(1));

      setMode("side");
      updateSlider();
      sortRows();
      applyFilters();
      const firstFail = rows.find((row) => !row.hidden && isFailure(row.dataset.status || ""));
      const firstVisible = rows.find((row) => !row.hidden);
      if (firstFail) {{
        selectRow(firstFail);
      }} else if (firstVisible) {{
        selectRow(firstVisible);
      }}
    </script>
  </body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")
