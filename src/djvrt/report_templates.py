from __future__ import annotations

import html
import json
from typing import Any


def _json_script_payload(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("</", r"<\/")


def get_report_html(summary_data: dict[str, Any], row_data: list[dict[str, Any]], rows_html: str) -> str:
    data_payload = _json_script_payload(row_data)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(summary_data["title"] or "djvrt report")} | djvrt</title>
    <style>
      :root {{
        /* Refined Palette */
        --bg: #f8fafc;
        --panel: #ffffff;
        --border: #e2e8f0;
        --border-hover: #cbd5e1;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --text-inv: #ffffff;

        /* Semantic Colors */
        --pass-bg: #f0fdf4;
        --pass-text: #166534;
        --pass-border: #bbf7d0;

        --fail-bg: #fef2f2;
        --fail-text: #991b1b;
        --fail-border: #fecaca;

        --warn-bg: #fffbeb;
        --warn-text: #92400e;
        --warn-border: #fef3c7;

        --accent: #2563eb;
        --accent-hover: #1d4ed8;
        --accent-soft: #eff6ff;

        /* Layout */
        --radius-sm: 6px;
        --radius-md: 8px;
        --radius-lg: 12px;
        --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
      }}

      * {{ box-sizing: border-box; }}

      body {{
        margin: 0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: var(--text-main);
        background: var(--bg);
        line-height: 1.5;
        -webkit-font-smoothing: antialiased;
      }}

      /* Accessibility: Skip Link */
      .skip-link {{
        position: absolute;
        top: -40px;
        left: 0;
        background: var(--accent);
        color: white;
        padding: 8px;
        z-index: 100;
        transition: top 0.2s;
      }}
      .skip-link:focus {{ top: 0; }}

      .container {{
        max-width: 1600px;
        margin: 0 auto;
        padding: 24px;
      }}

      header {{
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--border);
      }}

      h1 {{
        margin: 0;
        font-size: 24px;
        font-weight: 700;
        letter-spacing: -0.025em;
        line-height: 1.2;
      }}

      .report-subtitle {{
        font-size: 15px;
        color: var(--text-muted);
        font-weight: 500;
        margin-top: 4px;
      }}

      .run-meta {{
        font-size: 12px;
        color: var(--text-muted);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        margin-top: 8px;
      }}

      .header-links a {{
        color: var(--text-muted);
        font-size: 12px;
        text-decoration: none;
        margin-left: 12px;
        transition: color 0.2s;
      }}

      .header-links a:hover {{ color: var(--accent); }}

      /* Summary Cards */
      .summary-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
      }}

      .card {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        padding: 16px;
        box-shadow: var(--shadow);
        transition: transform 0.1s ease;
      }}

      .card:hover {{ transform: translateY(-1px); }}

      .card .label {{
        display: block;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
      }}

      .card .value {{
        font-size: 24px;
        font-weight: 800;
        color: var(--text-main);
      }}

      /* Toolbar / Filters */
      .toolbar {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 20px;
        align-items: center;
        background: var(--panel);
        padding: 16px;
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow);
      }}

      .toolbar-group {{
        display: flex;
        align-items: center;
        gap: 8px;
      }}

      .toolbar input[type="text"],
      .toolbar select {{
        padding: 8px 12px;
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        font-size: 14px;
        color: var(--text-main);
        background-color: var(--bg);
      }}

      .toolbar input[type="text"] {{ min-width: 300px; }}

      .toolbar input:focus,
      .toolbar select {{
        outline: 2px solid var(--accent);
        outline-offset: -1px;
        border-color: transparent;
      }}

      .btn {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 8px 16px;
        border-radius: var(--radius-sm);
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        border: 1px solid var(--border);
        background: var(--panel);
        color: var(--text-main);
      }}

      .btn:hover {{ border-color: var(--border-hover); background: var(--accent-soft); }}
      .btn:active {{ transform: scale(0.98); }}

      .btn-primary {{
        background: var(--accent);
        color: var(--text-inv);
        border-color: var(--accent);
      }}
      .btn-primary:hover {{ background: var(--accent-hover); border-color: var(--accent-hover); }}

      /* Main Layout */
      .main-layout {{
        display: grid;
        grid-template-columns: 1fr 500px;
        gap: 24px;
        align-items: start;
      }}

      @media (max-width: 1400px) {{
        .main-layout {{ grid-template-columns: 1fr 400px; }}
      }}

      @media (max-width: 1100px) {{
        .main-layout {{ grid-template-columns: 1fr; }}
        .compare-sidebar {{ position: static !important; max-height: none !important; }}
      }}

      /* Table Styles */
      .table-container {{
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow);
        overflow: hidden;
      }}

      .table-scroll {{
        max-height: calc(100vh - 350px);
        overflow-y: auto;
      }}

      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
      }}

      th {{
        background: #f8fafc;
        padding: 12px 16px;
        text-align: left;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 0.05em;
        position: sticky;
        top: 0;
        z-index: 10;
        border-bottom: 1px solid var(--border);
      }}

      tr.result-row {{
        border-bottom: 1px solid var(--border);
        cursor: pointer;
        transition: background-color 0.1s;
      }}

      tr.result-row:hover {{ background-color: var(--accent-soft) !important; }}
      tr.result-row.selected {{
        background-color: var(--accent-soft) !important;
        box-shadow: inset 4px 0 0 var(--accent);
      }}

      td {{ padding: 12px 16px; vertical-align: middle; }}

      .scenario-cell {{ display: flex; flex-direction: column; gap: 2px; }}
      .scenario-id {{ font-weight: 600; color: var(--text-main); }}
      .scenario-url {{ font-size: 12px; color: var(--text-muted); font-family: ui-monospace, monospace; }}

      /* Status Badges */
      .badge {{
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.2;
        border: 1px solid transparent;
      }}

      .badge-passed {{ background: var(--pass-bg); color: var(--pass-text); border-color: var(--pass-border); }}
      .badge-failed {{ background: var(--fail-bg); color: var(--fail-text); border-color: var(--fail-border); }}
      .badge-warn {{ background: var(--warn-bg); color: var(--warn-text); border-color: var(--warn-border); }}

      .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 13px; }}

      /* Sidebar Comparison */
      .compare-sidebar {{
        position: sticky;
        top: 24px;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 20px;
        box-shadow: var(--shadow-md);
        max-height: calc(100vh - 48px);
        overflow-y: auto;
      }}

      .compare-header {{ margin-bottom: 16px; }}
      .compare-title {{ margin: 0 0 4px; font-size: 18px; font-weight: 700; }}
      .compare-subtitle {{ font-size: 13px; color: var(--text-muted); margin: 0; }}

      .compare-empty {{
        text-align: center;
        padding: 48px 24px;
        color: var(--text-muted);
        border: 2px dashed var(--border);
        border-radius: var(--radius-md);
        background: var(--bg);
      }}

      .compare-modes {{
        display: flex;
        gap: 4px;
        background: var(--bg);
        padding: 4px;
        border-radius: var(--radius-md);
        margin-bottom: 20px;
      }}

      .mode-tab {{
        flex: 1;
        padding: 6px 12px;
        border: none;
        background: transparent;
        font-size: 13px;
        font-weight: 600;
        color: var(--text-muted);
        cursor: pointer;
        border-radius: var(--radius-sm);
        transition: all 0.2s;
      }}

      .mode-tab.active {{
        background: var(--panel);
        color: var(--accent);
        box-shadow: var(--shadow);
      }}

      .mode-tab:disabled {{ opacity: 0.4; cursor: not-allowed; }}

      /* Visualization */
      .view-pane {{ display: none; }}
      .view-pane.active {{ display: block; }}

      .img-container {{
        position: relative;
        background: #f1f5f9;
        border-radius: var(--radius-md);
        border: 1px solid var(--border);
        overflow: hidden;
        margin-bottom: 12px;
      }}

      .img-label {{
        position: absolute;
        top: 8px;
        left: 8px;
        background: rgba(15, 23, 42, 0.8);
        color: white;
        font-size: 10px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 4px;
        z-index: 5;
        text-transform: uppercase;
      }}

      .view-pane img {{
        display: block;
        width: 100%;
        height: auto;
        max-height: 500px;
        object-fit: contain;
      }}

      /* Slider Specific */
      .slider-box {{ position: relative; cursor: ew-resize; }}
      .slider-actual {{
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        overflow: hidden;
        border-right: 2px solid var(--accent);
      }}
      .slider-actual img {{ width: auto; max-width: none; height: 100%; object-fit: cover; }}

      .range-input {{
        width: 100%;
        margin: 12px 0;
        accent-color: var(--accent);
      }}

      .asset-links {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-top: 16px;
      }}

      .asset-link {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 8px;
        background: var(--bg);
        border-radius: var(--radius-sm);
        text-decoration: none;
        color: var(--text-main);
        font-size: 11px;
        font-weight: 600;
        border: 1px solid var(--border);
        transition: background 0.2s;
      }}

      .asset-link:hover {{ background: var(--accent-soft); border-color: var(--accent); }}

      /* Muted State */
      .muted {{ opacity: 0.5; pointer-events: none; }}

      [hidden] {{ display: none !important; }}
    </style>
  </head>
  <body>
    <a href="#main-content" class="skip-link">Skip to content</a>

    <div class="container">
      <header>
        <div>
          {'<div class="report-subtitle">DJVRT</div>' if summary_data.get("title") else ""}
          <h1>{html.escape(summary_data["title"] or "djvrt report")}</h1>
          <div class="run-meta">
            run: <span>{html.escape(summary_data["run_id"])}</span> |
            lock: <span>{html.escape(summary_data["lock_hash"])}</span>
          </div>
        </div>
        <div style="text-align: right;">
          <div class="card" style="padding: 8px 16px; border-radius: 999px; display: inline-block;">
            <span class="label" style="margin:0; display:inline; margin-right: 8px;">Mode</span>
            <span class="value" style="font-size: 14px; text-transform: uppercase;">
              {html.escape(summary_data["mode"])}
            </span>
          </div>
          <div style="margin-top: 8px;">
            <div class="header-links">
              <a href="https://github.com/William-Blackie/django-vrt/"
                 target="_blank" rel="noopener" style="margin-left: 0;">GitHub</a>
              <a href="https://william-blackie.github.io/django-vrt/"
                 target="_blank" rel="noopener">Docs</a>
            </div>
          </div>
        </div>
      </header>

      <main id="main-content">
        <section class="summary-grid" aria-label="Run Summary">
          <div class="card">
            <span class="label">Total Scenarios</span>
            <span class="value">{summary_data["totals"]["total"]}</span>
          </div>
          <div class="card">
            <span class="label">Passed</span>
            <span class="value" style="color: var(--pass-text)">{summary_data["totals"]["passed"]}</span>
          </div>
          <div class="card">
            <span class="label">Failures</span>
            <span class="value" style="color: var(--fail-text)">{summary_data["total_failures"]}</span>
          </div>
          <div class="card">
            <span class="label">Filtered Results</span>
            <span id="visible-count" class="value">{summary_data["totals"]["total"]}</span>
          </div>
        </section>

        <section class="toolbar" aria-label="Filters and Tools">
          <div class="toolbar-group">
            <label for="filter-search" class="visually-hidden">Search</label>
            <input id="filter-search" type="text"
                   placeholder="Search by ID, URL, experiment..."
                   aria-label="Search scenarios" />
          </div>

          <div class="toolbar-group">
            <select id="filter-status" aria-label="Filter by status">
              <option value="">All Statuses</option>
              <option value="passed">Passed</option>
              <option value="regression">Regression</option>
              <option value="capture_error">Capture Error</option>
              <option value="baseline_missing">Baseline Missing</option>
              <option value="dimension_mismatch">Dimension Mismatch</option>
            </select>
          </div>

          <div class="toolbar-group">
            <label style="font-size: 13px; font-weight: 500; display: flex;
                          align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" id="fail-only" style="width: 16px; height: 16px;" />
              Show failures only
            </label>
          </div>

          <div style="flex-grow: 1;"></div>

          <div class="toolbar-group">
            <button id="prev-fail" class="btn" title="Previous failure" aria-label="Previous failure">← Prev</button>
            <button id="next-fail" class="btn" title="Next failure" aria-label="Next failure">Next →</button>
          </div>
        </section>

        <div class="main-layout">
          <div class="table-container">
            <div class="table-scroll">
              <table id="results-table">
                <thead>
                  <tr>
                    <th scope="col">Scenario</th>
                    <th scope="col">Config</th>
                    <th scope="col">Status</th>
                    <th scope="col" style="text-align: right;">Mismatch</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody id="results-body">
                  {rows_html}
                </tbody>
              </table>
            </div>
          </div>

          <aside class="compare-sidebar" aria-labelledby="compare-title">
            <div id="compare-empty" class="compare-empty">
              <p>Select a scenario from the list to view details and compare images.</p>
            </div>

            <div id="compare-content" hidden>
              <header class="compare-header">
                <h2 id="compare-title" class="compare-title">Comparison</h2>
                <p id="compare-subtitle" class="compare-subtitle"></p>
              </header>

              <div class="compare-modes" role="tablist">
                <button class="mode-tab active" data-mode="side" role="tab" aria-selected="true">Side by Side</button>
                <button class="mode-tab" data-mode="slider" role="tab" aria-selected="false">Slider</button>
                <button class="mode-tab" data-mode="overlay" role="tab" aria-selected="false">Overlay</button>
                <button class="mode-tab" data-mode="diff" role="tab" aria-selected="false">Diff</button>
              </div>

              <div id="view-side" class="view-pane active">
                <div class="img-container">
                  <span class="img-label">Baseline</span>
                  <img id="img-side-baseline" alt="Baseline" />
                </div>
                <div class="img-container">
                  <span class="img-label">Actual</span>
                  <img id="img-side-actual" alt="Actual" />
                </div>
              </div>

              <div id="view-slider" class="view-pane">
                <div class="img-container slider-box" id="slider-box">
                   <img id="img-slider-baseline" alt="Baseline" style="width: 100%; display: block;" />
                   <div class="slider-actual" id="slider-actual" style="width: 50%;">
                      <img id="img-slider-actual" alt="Actual" style="display: block;" />
                   </div>
                </div>
                <input type="range" min="0" max="100" value="50" class="range-input"
                       id="slider-input" aria-label="Comparison slider" />
              </div>

              <div id="view-overlay" class="view-pane">
                <div class="img-container" style="position: relative;">
                  <img id="img-overlay-baseline" alt="Baseline"
                       style="display: block; width: 100%;" />
                  <img id="img-overlay-actual" alt="Actual"
                       style="position: absolute; top: 0; left: 0; width: 100%;
                              height: 100%; mix-blend-mode: difference;" />
                  <div style="position: absolute; bottom: 10px; left: 10px; background: rgba(0,0,0,0.7);
                              color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 11px;">
                    Difference Overlay (Black = Match)
                  </div>
                </div>
              </div>

              <div id="view-diff" class="view-pane">
                <div class="img-container">
                  <span class="img-label">Difference</span>
                  <img id="img-diff" alt="Visual difference" />
                </div>
              </div>

              <div id="error-box" class="card"
                   style="margin-top: 16px; border-color: var(--fail-border);
                          background: var(--fail-bg); color: var(--fail-text);
                          font-size: 13px; display: none;">
                <strong>Error:</strong> <span id="error-message"></span>
              </div>

              <div class="asset-links">
                <a id="link-baseline" href="#" class="asset-link" target="_blank">
                  <span>Baseline</span>
                </a>
                <a id="link-actual" href="#" class="asset-link" target="_blank">
                  <span>Actual</span>
                </a>
                <a id="link-diff" href="#" class="asset-link" target="_blank">
                  <span>Diff</span>
                </a>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>

    <style>
      .visually-hidden {{
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        border: 0;
      }}
    </style>

    <script id="djvrt-data" type="application/json">{data_payload}</script>

    <script>
      (function() {{
        const data = JSON.parse(document.getElementById('djvrt-data').textContent);
        const resultsBody = document.getElementById('results-body');
        const rows = Array.from(resultsBody.querySelectorAll('.result-row'));
        const searchInput = document.getElementById('filter-search');
        const statusSelect = document.getElementById('filter-status');
        const failOnlyCheckbox = document.getElementById('fail-only');
        const visibleCount = document.getElementById('visible-count');

        const compareEmpty = document.getElementById('compare-empty');
        const compareContent = document.getElementById('compare-content');
        const compareTitle = document.getElementById('compare-title');
        const compareSubtitle = document.getElementById('compare-subtitle');
        const errorBox = document.getElementById('error-box');
        const errorMessage = document.getElementById('error-message');

        const modeTabs = document.querySelectorAll('.mode-tab');
        const viewPanes = document.querySelectorAll('.view-pane');

        const imgSideBaseline = document.getElementById('img-side-baseline');
        const imgSideActual = document.getElementById('img-side-actual');
        const imgSliderBaseline = document.getElementById('img-slider-baseline');
        const imgSliderActual = document.getElementById('img-slider-actual');
        const imgOverlayBaseline = document.getElementById('img-overlay-baseline');
        const imgOverlayActual = document.getElementById('img-overlay-actual');
        const imgDiff = document.getElementById('img-diff');

        const sliderActual = document.getElementById('slider-actual');
        const sliderInput = document.getElementById('slider-input');

        const linkBaseline = document.getElementById('link-baseline');
        const linkActual = document.getElementById('link-actual');
        const linkDiff = document.getElementById('link-diff');

        const prevFailBtn = document.getElementById('prev-fail');
        const nextFailBtn = document.getElementById('next-fail');

        let selectedIndex = -1;

        function updateFilter() {{
          const term = searchInput.value.toLowerCase();
          const status = statusSelect.value;
          const failOnly = failOnlyCheckbox.checked;

          let count = 0;
          rows.forEach(row => {{
            const rowData = data[row.dataset.index];
            const matchesTerm = rowData.id.toLowerCase().includes(term) ||
                              rowData.url.toLowerCase().includes(term) ||
                              rowData.experiment.toLowerCase().includes(term);
            const matchesStatus = !status || rowData.status === status;
            const matchesFail = !failOnly || !rowData.passed;

            const isVisible = matchesTerm && matchesStatus && matchesFail;
            row.hidden = !isVisible;
            if (isVisible) count++;
          }});

          visibleCount.textContent = count;
        }}

        function selectRow(index) {{
          selectedIndex = index;
          const item = data[index];

          rows.forEach(r => r.classList.toggle('selected', parseInt(r.dataset.index) === index));

          compareEmpty.hidden = true;
          compareContent.hidden = false;

          compareTitle.textContent = item.id;
          compareSubtitle.textContent = `${{item.viewport}} • ${{item.auth}} • ${{item.experiment}}`;

          if (item.error) {{
            errorBox.style.display = 'block';
            errorMessage.textContent = item.error;
          }} else {{
            errorBox.style.display = 'none';
          }}

          // Update images
          imgSideBaseline.src = item.baseline || '';
          imgSideActual.src = item.actual || '';
          imgSliderBaseline.src = item.baseline || '';
          imgSliderActual.src = item.actual || '';
          imgOverlayBaseline.src = item.baseline || '';
          imgOverlayActual.src = item.actual || '';
          imgDiff.src = item.diff || '';

          // Update links
          linkBaseline.href = item.baseline || '#';
          linkBaseline.classList.toggle('muted', !item.baseline);
          linkActual.href = item.actual || '#';
          linkActual.classList.toggle('muted', !item.actual);
          linkDiff.href = item.diff || '#';
          linkDiff.classList.toggle('muted', !item.diff);

          // Update tab availability
          document.querySelector('[data-mode="diff"]').disabled = !item.diff;
          if (!item.diff && document.querySelector('.mode-tab.active').dataset.mode === 'diff') {{
            switchTab('side');
          }}
        }}

        function switchTab(mode) {{
          modeTabs.forEach(tab => {{
            const isActive = tab.dataset.mode === mode;
            tab.classList.toggle('active', isActive);
            tab.ariaSelected = isActive;
          }});

          viewPanes.forEach(pane => {{
            pane.classList.toggle('active', pane.id === `view-${{mode}}`);
          }});
        }}

        function navigateFailure(direction) {{
          const visibleFailures = rows.filter(r => !r.hidden && !data[r.dataset.index].passed);
          if (visibleFailures.length === 0) return;

          let currentIdx = visibleFailures.findIndex(r => parseInt(r.dataset.index) === selectedIndex);
          let nextIdx;

          if (currentIdx === -1) {{
             nextIdx = direction > 0 ? 0 : visibleFailures.length - 1;
          }} else {{
             nextIdx = (currentIdx + direction + visibleFailures.length) % visibleFailures.length;
          }}

          const targetRow = visibleFailures[nextIdx];
          selectRow(parseInt(targetRow.dataset.index));
          targetRow.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
        }}

        // Events
        resultsBody.addEventListener('click', e => {{
          const row = e.target.closest('.result-row');
          if (row) selectRow(parseInt(row.dataset.index));
        }});

        searchInput.addEventListener('input', updateFilter);
        statusSelect.addEventListener('change', updateFilter);
        failOnlyCheckbox.addEventListener('change', updateFilter);

        modeTabs.forEach(tab => {{
          tab.addEventListener('click', () => switchTab(tab.dataset.mode));
        }});

        sliderInput.addEventListener('input', e => {{
          sliderActual.style.width = `${{e.target.value}}%`;
        }});

        prevFailBtn.addEventListener('click', () => navigateFailure(-1));
        nextFailBtn.addEventListener('click', () => navigateFailure(1));

        // Keyboard navigation
        document.addEventListener('keydown', e => {{
          if (e.target.tagName === 'INPUT') return;

          if (e.key === 'j') navigateFailure(1);
          if (e.key === 'k') navigateFailure(-1);
        }});

        // Initialize
        updateFilter();
        const firstFail = rows.find(r => !data[r.dataset.index].passed);
        if (firstFail) selectRow(parseInt(firstFail.dataset.index));
        else if (rows.length > 0) selectRow(0);

      }})();
    </script>
  </body>
</html>
"""
