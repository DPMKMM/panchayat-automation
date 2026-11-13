"""Standalone HTML view for the MAS Consolidated Report Workspace (/reports/mas)."""

from __future__ import annotations

from core.branding import CONSOLE_NAME, GOV_SUBTITLE, PLATFORM_NAME, render_canonical_footer_html

_FOOTER_HTML = render_canonical_footer_html(
    "border-top:1px solid #e2e8f0; background:#ffffff; padding:22px 20px; color:#334155; font-size:0.86rem; margin-top:40px;"
)

MAS_PAGE_HTML = (
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Monthly Activity Statement (MAS) | """
    + CONSOLE_NAME
    + """</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f4f7f6;
      color: #0f172a;
      line-height: 1.5;
    }
    .navbar {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: #0c3829;
      color: #ffffff;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
    }
    .nav-inner {
      max-width: 1620px;
      margin: 0 auto;
      padding: 0 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 64px;
      gap: 12px;
      flex-wrap: wrap;
    }
    .nav-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: #ffffff;
    }
    .nav-brand-sup {
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #8cd6b7;
    }
    .nav-brand-main {
      font-size: 1.05rem;
      font-weight: 800;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .console-pill {
      background: rgba(251, 191, 36, 0.18);
      color: #fde68a;
      border: 1px solid rgba(251, 191, 36, 0.45);
      padding: 2px 9px;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 800;
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .nav-link {
      color: #d4e8de;
      text-decoration: none;
      padding: 8px 13px;
      font-weight: 700;
      font-size: 0.86rem;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      background: rgba(255, 255, 255, 0.08);
      transition: all 0.15s;
    }
    .nav-link:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.18);
    }
    main {
      max-width: 1620px;
      margin: 22px auto 40px;
      padding: 0 16px;
    }
    .mas-notice {
      display: none;
      margin-bottom: 16px;
      padding: 13px 16px;
      border-radius: 10px;
      font-size: 0.88rem;
      font-weight: 700;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .card {
      background: #ffffff;
      border: 1px solid #cbd5e1;
      border-radius: 14px;
      box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
      overflow: hidden;
    }
    .btn {
      padding: 8px 14px;
      border-radius: 8px;
      border: 1px solid transparent;
      font-family: inherit;
      font-size: 0.84rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      text-decoration: none;
      transition: all 0.15s;
    }
    .btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn-primary {
      background: linear-gradient(135deg, #0c3829, #15803d);
      color: #ffffff;
      box-shadow: 0 2px 6px rgba(12, 56, 41, 0.25);
    }
    .btn-outline {
      background: #eff6ff;
      color: #1d4ed8;
      border: 1.5px solid #3b82f6;
    }
    .btn-gold {
      background: #fef3c7;
      color: #92400e;
      border: 1px solid #f59e0b;
    }
    .mas-select {
      padding: 8px 12px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      font-weight: 700;
      font-size: 0.85rem;
      background: #ffffff;
      color: #0f172a;
      font-family: inherit;
    }
    @media (max-width: 720px) {
      .nav-inner { padding: 10px 14px; }
      main { padding: 0 12px; }
    }
  </style>
</head>
<body>
  <header class="navbar">
    <div class="nav-inner">
      <a class="nav-brand" id="mas-brand-home-link" href="/?site=console">
        <span style="font-size:1.6rem; line-height:1;">📊</span>
        <div>
          <div class="nav-brand-sup">""" + GOV_SUBTITLE + """</div>
          <div class="nav-brand-main">
            <span>"""
    + PLATFORM_NAME
    + """</span>
            <span id="subpage-console-pill" style="display:none;" class="console-pill">Console Workspace</span>
          </div>
        </div>
      </a>
      <div class="nav-actions">
        <span id="mas-session-pill" style="background:rgba(16,185,129,0.18); color:#a7f3d0; border:1px solid rgba(16,185,129,0.4); padding:5px 12px; border-radius:999px; font-size:0.76rem; font-weight:800;">
          ⏳ Checking Console Session...
        </span>
        <a class="nav-link" id="mas-back-console-link" href="/?site=console">← Back to Console Dashboard</a>
      </div>
    </div>
  </header>

  <main>
    <div id="portal-notice-banner" class="mas-notice">
      <span id="portal-notice-text"></span>
      <button type="button" class="btn btn-outline" style="padding:4px 10px; font-size:0.75rem;" onclick="hidePortalNotice()">Dismiss</button>
    </div>

    <div id="mas-auth-gate-banner" class="mas-notice" style="background:#fffbeb; border:1.5px solid #fcd34d; color:#92400e;">
      <span id="mas-auth-gate-text">🔐 Console authentication check in progress...</span>
      <button type="button" class="btn btn-gold" id="mas-auth-gate-btn" onclick="handleMasAuthGateAction()">
        🔐 Login Once on Console →
      </button>
    </div>

    <div id="mas-reporting-card" class="card">
      <div style="background:linear-gradient(135deg, #0c3829 0%, #165b43 100%); color:#ffffff; padding:20px 24px; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:16px;">
        <div>
          <div style="font-size:0.72rem; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; color:#a7f3d0;">
            Executive Analytics Engine &bull; Shared EPTS Session (Zero Duplicate Login)
          </div>
          <h1 style="margin:4px 0 0; font-size:1.35rem; font-weight:800; color:#ffffff;">
            📑 Consolidated MAS 18-Indicator Reporting (GM-R 5.24 + Births GM-R 5.23)
          </h1>
          <div style="font-size:0.84rem; color:#d1fae5; margin-top:4px;">
            District: <strong id="mas-header-district">Active District</strong>
            &bull; Officer: <strong id="mas-header-officer">Authenticated Session</strong>
            <span id="mas-header-scope">&bull; All Mandals &amp; Gram Panchayats</span>
          </div>
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
          <select id="mas-select-month" class="mas-select" title="Select Reporting Month" onchange="onMasSelectionChanged()">
            <option value="">-- Select Month --</option>
            <option value="January">January</option>
            <option value="February">February</option>
            <option value="March">March</option>
            <option value="April">April</option>
            <option value="May">May</option>
            <option value="June">June</option>
            <option value="July">July</option>
            <option value="August">August</option>
            <option value="September">September</option>
            <option value="October">October</option>
            <option value="November">November</option>
            <option value="December">December</option>
          </select>
          <select id="mas-select-year" class="mas-select" title="Select Reporting Year" onchange="onMasYearChanged()"></select>
          <button type="button" id="btn-fetch-mas-years" onclick="fetchMasYearsFromPortal(false)" class="btn" title="Fetch live available Years &amp; Months from e-Panchayat portal" style="background:rgba(255,255,255,0.14); color:#ffffff; border:1px solid rgba(255,255,255,0.32);">
            🔄 Fetch Years
          </button>
          <select id="mas-select-report-type" class="mas-select" title="Choose Report Scope" onchange="onMasReportTypeChanged()">
            <option value="">-- Select Report Type --</option>
            <option value="abstract_only">Mandal Abstract Only (Fast)</option>
            <option value="abstract_and_gp">Mandal Abstract &amp; GP-Wise Data</option>
          </select>
          <button type="button" id="btn-run-mas" onclick="runMasReportGeneration(false)" class="btn btn-primary" style="border:1.5px solid rgba(255,255,255,0.28);">
            🚀 Generate Report
          </button>
          <a href="#" onclick="return onDownloadMandalGpPdf(event);" id="btn-mas-dl-pdf" class="btn" style="background:rgba(255,255,255,0.14); color:#ffffff; border:1px solid rgba(255,255,255,0.3);">
            📄 Download Mandal &amp; GP Report
          </a>
          <a href="#" onclick="return handleMasDownloadClick(event, 'abstract_pdf');" id="btn-mas-dl-abstract-pdf" class="btn" style="background:rgba(16,185,129,0.28); color:#ecfdf5; border:1px solid rgba(255,255,255,0.32);">
            📑 Download Mandal Abstract
          </a>
          <a href="#" onclick="return handleMasDownloadClick(event, 'excel');" id="btn-mas-dl-excel" class="btn" style="background:#ffffff; color:#0c3829; border:1px solid #ffffff;">
            📊 Excel (5 Sheets)
          </a>
          <a href="#" onclick="return handleMasDownloadClick(event, 'pending_csv');" id="btn-mas-dl-pending-csv" class="btn" style="background:#fef3c7; color:#92400e; border:1px solid #f59e0b;">
            ⚠️ Pending GPs CSV
          </a>
        </div>
      </div>

      <!-- Dynamic Exclusion Controls Bar -->
      <div style="background:#f8fafc; padding:16px 24px; border-bottom:1px solid #e2e8f0;">
        <div style="display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px;">
          <div>
            <div style="font-weight:800; font-size:0.9rem; color:#0f172a;">
              🎛️ Percentage Calculation Filter: Exclude Modules from District Overall %
            </div>
            <div style="font-size:0.78rem; color:#475569;">
              By default, all 18 modules are included. Check any module below to exclude it from the denominator, or use Quick Excludes for CC Charges, Expenditure &amp; Cheques.
            </div>
          </div>
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <button type="button" onclick="toggleQuickExcludeModule('Payment of Electricity')" id="btn-preset-cc" class="btn btn-outline" style="font-size:0.78rem;">
              <span id="cc-btn-text">⚡ Exclude CC Charges</span>
            </button>
            <button type="button" onclick="toggleQuickExcludeModule('Expenditure')" id="btn-preset-expenditure" class="btn btn-outline" style="font-size:0.78rem;">
              <span id="expenditure-btn-text">⚡ Exclude Expenditure</span>
            </button>
            <button type="button" onclick="toggleQuickExcludeModule('Cheque Details')" id="btn-preset-cheques" class="btn btn-outline" style="font-size:0.78rem;">
              <span id="cheques-btn-text">⚡ Exclude Cheque Details</span>
            </button>
            <button type="button" onclick="presetIncludeAllModules()" class="btn" style="background:#f1f5f9; color:#334155; border:1px solid #cbd5e1; font-size:0.78rem;">
              🔄 Include All 18 Modules
            </button>
          </div>
        </div>

        <div id="mas-module-chips-grid" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:8px;">
          <div style="grid-column:1/-1; color:#64748b; font-size:0.82rem; padding:8px;">Loading 18 MAS Indicators...</div>
        </div>

        <div style="margin-top:12px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px; padding:10px 14px; font-size:0.8rem; color:#1e40af; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px;">
          <span id="mas-formula-text"><strong>Formula:</strong> Sum(Updated in Included Modules) / (18 &times; Applicable GPs) &times; 100</span>
          <span id="mas-formula-badge" style="background:#ffffff; color:#0f172a; padding:4px 10px; border-radius:6px; border:1px solid #cbd5e1;">
            Module Cell Format: Not Updated / Updated (0 / 22 = 0 Pending)
          </span>
        </div>
      </div>

      <!-- Live Robot Progress Box (MAS) -->
      <div id="mas-progress-card" class="robot-progress-card" style="display:none; background:#ffffff; border:1.5px solid #38bdf8; border-radius:12px; padding:18px; margin:16px 24px; box-shadow:0 4px 16px rgba(56,189,248,0.12);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <div class="robot-sonar-dot" style="width:12px; height:12px; border-radius:50%; background:#0284c7; box-shadow:0 0 0 3px rgba(56,189,248,0.4);"></div>
            <strong style="color:#0369a1; font-size:0.95rem;">GM-R 5.24 &amp; 5.23 MAS Robot Active</strong>
          </div>
          <span id="mas-progress-pct" class="progress-pct-badge" style="background:#e0f2fe; color:#0369a1; font-weight:800; font-size:0.85rem; padding:3px 10px; border-radius:999px;">0%</span>
        </div>
        <div class="progress-track-8px" style="background:#e2e8f0; height:8px; border-radius:999px; overflow:hidden; margin-bottom:12px;">
          <div id="mas-progress-fill" class="progress-fill-gradient" style="background:linear-gradient(90deg, #0284c7, #10b981); width:0%; height:100%; border-radius:999px; transition:width 0.3s ease;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; font-size:0.85rem; color:#334155;">
          <div><span style="font-weight:700;">Status:</span> <span id="mas-status-text">Extracting GM-R 5.24 &amp; 5.23 reports from e-Panchayat portal...</span></div>
          <div style="display:flex; gap:12px; font-weight:600;">
            <span>⏱️ Elapsed: <strong id="mas-elapsed-time" style="color:#047857;">00:00</strong></span>
            <span>⏳ Estimated: <strong id="mas-estimated-time" style="color:#0284c7;">01:30</strong></span>
          </div>
        </div>
      </div>

      <!-- KPI Summary Row -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; padding:20px 24px; background:#ffffff; border-bottom:1px solid #e2e8f0;">
        <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:10px; padding:14px 16px;">
          <div style="font-size:0.72rem; font-weight:800; color:#047857; text-transform:uppercase;">District Overall % Entered</div>
          <div id="kpi-overall-pct" style="font-size:1.7rem; font-weight:900; color:#065f46; margin-top:4px;">--%</div>
          <div id="kpi-pct-sub" style="font-size:0.76rem; color:#059669; margin-top:2px;">Calculated across included modules</div>
        </div>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px;">
          <div style="font-size:0.72rem; font-weight:800; color:#475569; text-transform:uppercase;">Fields Updated / Total</div>
          <div id="kpi-updated-fields" style="font-size:1.55rem; font-weight:900; color:#0f172a; margin-top:4px;">-- / --</div>
          <div id="kpi-fields-sub" style="font-size:0.76rem; color:#64748b; margin-top:2px;">Awaiting report generation</div>
        </div>
        <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:10px; padding:14px 16px;">
          <div style="font-size:0.72rem; font-weight:800; color:#1d4ed8; text-transform:uppercase;">District Coverage</div>
          <div id="kpi-coverage" style="font-size:1.55rem; font-weight:900; color:#1e3a8a; margin-top:4px;">-- Mandals</div>
          <div id="kpi-coverage-sub" style="font-size:0.76rem; color:#3b82f6; margin-top:2px;">-- Gram Panchayats</div>
        </div>
        <div style="background:#fef3c7; border:1px solid #fde68a; border-radius:10px; padding:14px 16px;">
          <div style="font-size:0.72rem; font-weight:800; color:#b45309; text-transform:uppercase;">Included Module Base</div>
          <div id="kpi-module-base" style="font-size:1.55rem; font-weight:900; color:#92400e; margin-top:4px;">18 / 18</div>
          <div id="kpi-module-sub" style="font-size:0.76rem; color:#b45309; margin-top:2px;">All modules active in %</div>
        </div>
        <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:10px; padding:14px 16px;">
          <div style="font-size:0.72rem; font-weight:800; color:#b91c1c; text-transform:uppercase;">Pending Action GPs</div>
          <div id="kpi-pending-gps" style="font-size:1.55rem; font-weight:900; color:#991b1b; margin-top:4px;">-- GPs</div>
          <div id="kpi-pending-gps-sub" style="font-size:0.76rem; color:#dc2626; margin-top:2px;">Requiring MPO follow-up</div>
        </div>
      </div>

      <!-- Prepared For Month Banner -->
      <div id="mas-prepared-period-bar" style="padding:10px 24px; background:#f8fafc; border-bottom:1px solid #e2e8f0; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; font-size:0.84rem; color:#475569;">
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <span style="font-size:1rem;">🗓️</span>
          <span>Report Prepared For Month:</span>
          <strong id="mas-prepared-month-value" style="padding:2px 10px; border-radius:6px; background:#e2e8f0; color:#334155; font-size:0.86rem;">--</strong>
          <span id="mas-prepared-meta" style="color:#64748b; font-size:0.8rem;">Select Month, Year &amp; Report Type and click Generate Report</span>
        </div>
        <span id="mas-prepared-timestamp" style="font-size:0.78rem; color:#64748b; font-weight:600;"></span>
      </div>

      <!-- View Tabs & Table Filter -->
      <div style="padding:14px 24px; background:#ffffff; border-bottom:1px solid #e2e8f0; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px;">
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button type="button" onclick="switchMasView('abstract')" id="tab-btn-abstract" style="padding:8px 16px; border-radius:8px; border:1px solid #0c3829; background:#0c3829; color:#ffffff; font-weight:700; cursor:pointer; font-size:0.85rem;">
            📋 Mandal Abstract (22 Cols)
          </button>
          <button type="button" onclick="switchMasView('pending')" id="tab-btn-pending" style="padding:8px 16px; border-radius:8px; border:1px solid #cbd5e1; background:#ffffff; color:#475569; font-weight:700; cursor:pointer; font-size:0.85rem;">
            🚨 Pending GPs Action List <span id="pending-badge" style="background:#dc2626; color:#ffffff; padding:1px 7px; border-radius:10px; font-size:0.72rem; margin-left:4px;">0</span>
          </button>
          <span id="mas-table-period-badge" style="display:none; padding:6px 12px; border-radius:8px; background:#ecfdf5; border:1px solid #6ee7b7; color:#065f46; font-weight:800; font-size:0.82rem;"></span>
        </div>
        <input type="text" id="mas-table-filter" oninput="filterMasTable()" placeholder="🔍 Search Mandal or GP..." style="padding:8px 14px; border:1px solid #cbd5e1; border-radius:8px; font-size:0.84rem; width:260px; font-family:inherit;">
      </div>

      <!-- TAB 1: Mandal Abstract -->
      <div id="mas-abstract-view" style="width:100%; overflow-x:auto;">
        <table id="mas-abstract-table" style="width:100%; border-collapse:collapse; font-size:0.75rem; text-align:center;">
          <thead>
            <tr id="mas-thead-row-1" style="background:#0c3829; color:#ffffff;">
              <th style="padding:7px 4px; border:1px solid #165b43; width:34px;">S<br>No</th>
              <th style="padding:7px 8px; text-align:left; border:1px solid #165b43; min-width:118px;">Mandal Name</th>
              <th style="padding:7px 4px; border:1px solid #165b43; width:38px;">GPs</th>
              <th style="padding:7px 4px; border:1px solid #165b43; background:#10b981; color:#064e3b; font-weight:900; width:58px;">Overall<br>%</th>
            </tr>
            <tr id="mas-thead-row-2" style="background:#165b43; color:#d1fae5; font-size:0.66rem;"></tr>
          </thead>
          <tbody id="mas-tbody">
            <tr><td colspan="22" style="padding:40px; color:#64748b;">Select Month, Year &amp; Report Type above and click <strong>🚀 Generate Report</strong> to extract live MAS data using your active Department session.</td></tr>
          </tbody>
          <tfoot id="mas-tfoot" style="background:#fef3c7; font-weight:900; color:#0f172a;"></tfoot>
        </table>
      </div>

      <!-- TAB 2: Pending GPs Action List -->
      <div id="mas-pending-view" style="display:none; width:100%; overflow-x:auto;">
        <table id="mas-pending-table" style="width:100%; border-collapse:collapse; font-size:0.83rem; text-align:center;">
          <thead>
            <tr style="background:#7f1d1d; color:#ffffff;">
              <th style="padding:11px 8px; border:1px solid #991b1b;">S No</th>
              <th style="padding:11px 12px; text-align:left; border:1px solid #991b1b;">Mandal Name</th>
              <th style="padding:11px 12px; text-align:left; border:1px solid #991b1b;">Gram Panchayat</th>
              <th style="padding:11px 8px; border:1px solid #991b1b;">Pending Count</th>
              <th style="padding:11px 12px; text-align:left; border:1px solid #991b1b;">Pending Module(s)</th>
              <th style="padding:11px 8px; border:1px solid #991b1b;">Completed / Included</th>
              <th style="padding:11px 8px; border:1px solid #991b1b;">Completion %</th>
            </tr>
          </thead>
          <tbody id="mas-pending-tbody">
            <tr><td colspan="7" style="padding:36px; color:#64748b;">No GP-wise pendency data loaded yet.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  """
    + _FOOTER_HTML
    + """

  <script src="/static/js/dept_session.js?v=6"></script>
  <script>
    const DEFAULT_MAS_MODULES = [
      { id: 'Nursery', label: 'Nursery', default_excluded: false, is_highlighted: false },
      { id: 'Plantation', label: 'Plantation', default_excluded: false, is_highlighted: false },
      { id: 'Vaikunta Dhamam', label: 'Vaikunta Dhamam', default_excluded: false, is_highlighted: false },
      { id: 'Dump Yard', label: 'Dump Yard', default_excluded: false, is_highlighted: false },
      { id: 'Water Supply', label: 'Water Supply', default_excluded: false, is_highlighted: false },
      { id: 'GP Meetings', label: 'GP Meetings', default_excluded: false, is_highlighted: false },
      { id: 'Gram Sabha', label: 'Gram Sabha', default_excluded: false, is_highlighted: false },
      { id: 'Record Maintenance', label: 'Record Maintenance', default_excluded: false, is_highlighted: false },
      { id: 'Approvals and Certificates', label: 'Approvals and Certificates', default_excluded: false, is_highlighted: false },
      { id: 'Deaths', label: 'Deaths', default_excluded: false, is_highlighted: false },
      { id: 'Recipts', label: 'Recipts', default_excluded: false, is_highlighted: false },
      { id: 'Expenditure', label: 'Expenditure', default_excluded: false, is_highlighted: true },
      { id: 'Cheque Details', label: 'Cheque Details', default_excluded: false, is_highlighted: true },
      { id: 'Salary Details', label: 'Salary Details', default_excluded: false, is_highlighted: false },
      { id: 'VWSC Bank Balance', label: 'VWSC Bank Balance', default_excluded: false, is_highlighted: false },
      { id: 'MGNRE Bank Balance', label: 'MGNRE Bank Balance', default_excluded: false, is_highlighted: false },
      { id: 'Payment of Electricity', label: 'Payment of Electricity', default_excluded: false, is_highlighted: true, is_cc_charges: true },
      { id: 'Birth Details', label: 'Birth Details', default_excluded: false, is_highlighted: false }
    ];

    const HIGHLIGHTED_EXCLUDE_CANDIDATES = new Set(['Payment of Electricity', 'Expenditure', 'Cheque Details']);
    const QUICK_EXCLUDE_BUTTONS = [
      { value: 'Payment of Electricity', btnId: 'btn-preset-cc', textId: 'cc-btn-text', label: 'CC Charges' },
      { value: 'Expenditure', btnId: 'btn-preset-expenditure', textId: 'expenditure-btn-text', label: 'Expenditure' },
      { value: 'Cheque Details', btnId: 'btn-preset-cheques', textId: 'cheques-btn-text', label: 'Cheque Details' }
    ];

    let allMasModules = DEFAULT_MAS_MODULES.slice();
    let masCurrentData = null;
    let isStage1Authenticated = false;
    let isDeptAuthenticated = false;
    let hasFetchedPortalYears = false;
    let isFetchingPortalYears = false;
    let isGeneratingMas = false;
    let authGateActionMode = 'dept';

    function escapeHtml(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function showPortalNotice(msg, kind) {
      const box = document.getElementById('portal-notice-banner');
      const txt = document.getElementById('portal-notice-text');
      if (!box || !txt) return;
      const styles = {
        success: { bg: '#ecfdf5', bd: '#6ee7b7', fg: '#065f46' },
        warning: { bg: '#fffbeb', bd: '#fcd34d', fg: '#92400e' },
        error: { bg: '#fef2f2', bd: '#fca5a5', fg: '#991b1b' }
      };
      const st = styles[kind] || styles.warning;
      box.style.background = st.bg;
      box.style.border = '1.5px solid ' + st.bd;
      box.style.color = st.fg;
      txt.textContent = String(msg || '');
      box.style.display = 'flex';
    }

    function hidePortalNotice() {
      const box = document.getElementById('portal-notice-banner');
      if (box) box.style.display = 'none';
    }

    function consoleApiFetch(url, options) {
      if (window.DeptSessionManager && typeof window.DeptSessionManager.consoleFetch === 'function') {
        return window.DeptSessionManager.consoleFetch(url, options);
      }
      return fetch(url, Object.assign({ credentials: 'same-origin' }, options || {}));
    }

    function redirectMasToConsoleLogin(reason, autoGen) {
      const month = (document.getElementById('mas-select-month')?.value || '').trim();
      const year = (document.getElementById('mas-select-year')?.value || '').trim();
      const reportType = (document.getElementById('mas-select-report-type')?.value || 'abstract_and_gp').trim();
      const excluded = getSelectedExcludedModules();
      if (window.DeptSessionManager && typeof window.DeptSessionManager.redirectToConsoleDeptLogin === 'function') {
        window.DeptSessionManager.redirectToConsoleDeptLogin({
          module: 'mas',
          reason: reason || 'required',
          autoGenerate: Boolean(autoGen && month),
          params: {
            month: month,
            year: year,
            report_type: reportType,
            excluded_modules: excluded.join(',')
          }
        });
      } else {
        window.location.href = '/?site=console&dept_login=1&pending_module=mas';
      }
    }

    function handleMasAuthGateAction() {
      if (!isStage1Authenticated) {
        const target = window.DeptSessionManager ? window.DeptSessionManager.getConsoleHomeUrl() : '/?site=console';
        window.location.href = target;
        return;
      }
      redirectMasToConsoleLogin(authGateActionMode === 'expired' ? 'expired' : 'required', false);
    }

    function updateSessionBannerUI(stage1, dept) {
      const pill = document.getElementById('mas-session-pill');
      const gate = document.getElementById('mas-auth-gate-banner');
      const gateTxt = document.getElementById('mas-auth-gate-text');
      const gateBtn = document.getElementById('mas-auth-gate-btn');
      const distEl = document.getElementById('mas-header-district');
      const offEl = document.getElementById('mas-header-officer');

      isStage1Authenticated = Boolean(stage1 && stage1.authenticated);
      isDeptAuthenticated = Boolean(dept && dept.authenticated);

      if (!isStage1Authenticated) {
        authGateActionMode = 'stage1';
        if (pill) {
          pill.textContent = '🔒 Google Sign-In Required';
          pill.style.background = 'rgba(239,68,68,0.22)';
          pill.style.color = '#fecaca';
        }
        if (gate && gateTxt && gateBtn) {
          gateTxt.textContent = 'Sign in with your Google Account on e-Panchayat Automation Console first to access MAS Report generation.';
          gateBtn.textContent = '🔐 Open Console Sign-In →';
          gate.style.display = 'flex';
        }
        return;
      }

      if (isDeptAuthenticated) {
        const uid = (dept.data && dept.data.user_id) || dept.user_id || 'Officer';
        const dist = (dept.data && (dept.data.district_name || dept.data.district)) || '';
        if (pill) {
          pill.textContent = '🟢 EPTS Active · ' + uid + ' (Zero Duplicate Login)';
          pill.style.background = 'rgba(16,185,129,0.25)';
          pill.style.color = '#a7f3d0';
        }
        if (distEl && dist) distEl.textContent = dist;
        if (offEl && uid) offEl.textContent = uid;
        if (gate) gate.style.display = 'none';
      } else {
        authGateActionMode = dept && dept.expired ? 'expired' : 'required';
        if (pill) {
          pill.textContent = dept && dept.expired ? '⚠️ EPTS Session Expired' : '🔐 Dept Login Required';
          pill.style.background = 'rgba(245,158,11,0.25)';
          pill.style.color = '#fde68a';
        }
        if (gate && gateTxt && gateBtn) {
          gateTxt.textContent = (dept && dept.expired)
            ? 'Your Department Login session expired. Authenticate once on Console to resume MAS extraction cleanly.'
            : 'Complete Department Login & OTP once on the Console header — MAS will automatically reuse that active session with zero duplicate login.';
          gateBtn.textContent = '🔐 Authenticate Dept Login Once →';
          gate.style.display = 'flex';
        }
      }
    }

    function initYearSelector() {
      const yearSelect = document.getElementById('mas-select-year');
      if (!yearSelect) return;
      const currentYear = new Date().getFullYear();
      let html = '';
      for (let y = currentYear - 3; y <= currentYear + 1; y++) {
        html += `<option value="${y}" ${y === currentYear ? 'selected' : ''}>${y}</option>`;
      }
      yearSelect.innerHTML = html;
    }

    function applyPortalPeriodsToSelects(data, preferredYear) {
      const yearSelect = document.getElementById('mas-select-year');
      const monthSelect = document.getElementById('mas-select-month');
      const years = Array.isArray(data && data.years) ? data.years : [];
      if (yearSelect && years.length) {
        const curVal = String(preferredYear || yearSelect.value || (data && data.selected_year) || '').trim();
        yearSelect.innerHTML = years.map(y => {
          const val = String(y.value || y.text || '').trim();
          const txt = String(y.text || y.value || '').trim();
          const sel = val === curVal ? 'selected' : '';
          return `<option value="${escapeHtml(val)}" ${sel}>${escapeHtml(txt)}</option>`;
        }).join('');
        if (!yearSelect.value && years[0]) {
          yearSelect.value = String(years[0].value || years[0].text || '').trim();
        }
      }
      const months = Array.isArray(data && data.months) ? data.months : [];
      if (monthSelect && months.length) {
        const curMonth = String(monthSelect.value || '').trim();
        let mHtml = '<option value="">-- Select Month --</option>';
        months.forEach(m => {
          const txt = String(m.text || m.value || '').trim();
          if (!txt) return;
          const canonical = txt.charAt(0).toUpperCase() + txt.slice(1);
          const sel = canonical.toLowerCase() === curMonth.toLowerCase() ? 'selected' : '';
          mHtml += `<option value="${escapeHtml(canonical)}" ${sel}>${escapeHtml(canonical)}</option>`;
        });
        monthSelect.innerHTML = mHtml;
      }
    }

    async function fetchMasYearsFromPortal(isSilent, requestedYear) {
      if (isFetchingPortalYears) return;
      if (!isStage1Authenticated) {
        if (!isSilent) handleMasAuthGateAction();
        return;
      }
      if (!isDeptAuthenticated) {
        if (!isSilent) {
          showPortalNotice('Department Login required once before fetching live Years from e-Panchayat portal.', 'warning');
          redirectMasToConsoleLogin('required', false);
        }
        return;
      }
      const btn = document.getElementById('btn-fetch-mas-years');
      const yrSel = document.getElementById('mas-select-year');
      const targetYear = requestedYear || (yrSel ? yrSel.value : '');
      isFetchingPortalYears = true;
      if (btn && !isSilent) {
        btn.disabled = true;
        btn.textContent = '⏳ Fetching Years...';
      }
      try {
        const url = targetYear
          ? `/api/reports/mas-consolidated/years?year=${encodeURIComponent(targetYear)}`
          : '/api/reports/mas-consolidated/years';
        const res = await consoleApiFetch(url);
        const data = await res.json().catch(() => ({}));
        if (res.status === 401 || res.status === 403) {
          if (!isSilent) {
            showPortalNotice(data.detail || 'Departmental session expired. Please re-authenticate once.', 'warning');
            redirectMasToConsoleLogin('expired', false);
          }
          return;
        }
        if (data && data.success && Array.isArray(data.years) && data.years.length) {
          hasFetchedPortalYears = true;
          applyPortalPeriodsToSelects(data, requestedYear || (yrSel ? yrSel.value : ''));
          if (!isSilent) {
            const yrLabels = data.years.map(y => y.text || y.value).join(', ');
            showPortalNotice(`✅ Fetched ${data.years.length} portal year(s) from GM-R 5.24: ${yrLabels}`, 'success');
          }
        } else if (!isSilent) {
          showPortalNotice((data && data.detail) || 'No years returned from portal GM-R 5.24 dropdown.', 'warning');
        }
      } catch (err) {
        if (!isSilent) {
          showPortalNotice('Unable to fetch years from EPTS portal: ' + (err && err.message ? err.message : err), 'error');
        }
      } finally {
        isFetchingPortalYears = false;
        if (btn) {
          btn.disabled = false;
          btn.textContent = '🔄 Fetch Years';
        }
      }
    }

    function onMasYearChanged() {
      onMasSelectionChanged();
      if (isStage1Authenticated && isDeptAuthenticated) {
        const y = (document.getElementById('mas-select-year')?.value || '').trim();
        if (y) fetchMasYearsFromPortal(true, y);
      }
    }

    function renderMasModuleChips(initialExcludedSet) {
      const container = document.getElementById('mas-module-chips-grid');
      if (!container) return;
      const initExcl = initialExcludedSet || new Set(allMasModules.filter(m => m.default_excluded).map(m => m.id));
      container.innerHTML = allMasModules.map((m, idx) => {
        const isExcl = initExcl.has(m.id);
        const isHighlight = Boolean(m.is_highlighted || HIGHLIGHTED_EXCLUDE_CANDIDATES.has(m.id));
        const starHtml = isHighlight ? '<span title="Highlighted optional exclusion module" style="color:#2563eb; margin-right:3px;">★</span>' : '';
        return (
          `<label id="chip-wrap-${idx}" data-highlight="${isHighlight ? '1' : '0'}" style="display:flex; align-items:center; gap:8px; padding:7px 11px; border-radius:8px; border:1px solid #cbd5e1; background:#ffffff; cursor:pointer; font-size:0.8rem; user-select:none; transition:all 0.2s;">` +
          `<input type="checkbox" id="mod-chk-${idx}" value="${escapeHtml(m.id)}" ${isExcl ? 'checked' : ''} onchange="onModuleCheckboxChanged()" style="cursor:pointer; accent-color:#b45309; width:15px; height:15px;">` +
          `<span id="chip-label-${idx}" style="font-weight:700; color:#1e293b; flex:1;">${starHtml}${escapeHtml(m.label)}${m.is_cc_charges ? ' (CC Charges)' : ''}</span>` +
          `<span id="chip-tag-${idx}" style="font-size:0.68rem; font-weight:800; padding:1px 6px; border-radius:4px; background:#e2e8f0; color:#64748b;">INCLUDED</span>` +
          `</label>`
        );
      }).join('');
      onModuleCheckboxChanged();
    }

    function getSelectedExcludedModules() {
      const checkboxes = document.querySelectorAll('#mas-module-chips-grid input[type="checkbox"]:checked');
      return Array.from(checkboxes).map(cb => cb.value);
    }

    function updateQuickExcludeButtonsUI() {
      const excludedSet = new Set(getSelectedExcludedModules());
      QUICK_EXCLUDE_BUTTONS.forEach(cfg => {
        const btn = document.getElementById(cfg.btnId);
        const text = document.getElementById(cfg.textId);
        if (!btn || !text) return;
        const isExcl = excludedSet.has(cfg.value);
        if (isExcl) {
          btn.style.background = '#fef3c7';
          btn.style.color = '#92400e';
          btn.style.borderColor = '#d97706';
          text.textContent = '✓ ' + cfg.label + ': EXCLUDED';
        } else {
          btn.style.background = '#eff6ff';
          btn.style.color = '#1d4ed8';
          btn.style.borderColor = '#3b82f6';
          text.textContent = '⚡ Exclude ' + cfg.label;
        }
      });
    }

    function onModuleCheckboxChanged() {
      const checkboxes = document.querySelectorAll('#mas-module-chips-grid input[type="checkbox"]');
      checkboxes.forEach((cb, idx) => {
        const isExcl = cb.checked;
        const wrap = document.getElementById('chip-wrap-' + idx);
        const label = document.getElementById('chip-label-' + idx);
        const tag = document.getElementById('chip-tag-' + idx);
        const isHighlight = wrap ? wrap.getAttribute('data-highlight') === '1' : HIGHLIGHTED_EXCLUDE_CANDIDATES.has(cb.value);
        if (wrap) {
          if (isExcl) {
            wrap.style.border = '1.5px solid #f59e0b';
            wrap.style.background = '#fef3c7';
          } else if (isHighlight) {
            wrap.style.border = '2px solid #3b82f6';
            wrap.style.background = '#eff6ff';
          } else {
            wrap.style.border = '1px solid #cbd5e1';
            wrap.style.background = '#ffffff';
          }
        }
        if (label) label.style.color = isExcl ? '#92400e' : (isHighlight ? '#1e40af' : '#1e293b');
        if (tag) {
          tag.style.background = isExcl ? '#b45309' : (isHighlight ? '#dbeafe' : '#e2e8f0');
          tag.style.color = isExcl ? '#ffffff' : (isHighlight ? '#1d4ed8' : '#64748b');
          tag.textContent = isExcl ? 'EXCLUDED' : 'INCLUDED';
        }
      });
      updateMasFormulaBanner();
      updateQuickExcludeButtonsUI();
    }

    function toggleQuickExcludeModule(modName) {
      document.querySelectorAll('#mas-module-chips-grid input[type="checkbox"]').forEach(cb => {
        if (cb.value === modName) cb.checked = !cb.checked;
      });
      onModuleCheckboxChanged();
    }

    function presetIncludeAllModules() {
      document.querySelectorAll('#mas-module-chips-grid input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
      });
      onModuleCheckboxChanged();
    }

    function updateMasFormulaBanner() {
      const excluded = getSelectedExcludedModules();
      const nIncluded = Math.max(1, 18 - excluded.length);
      const bannerText = document.getElementById('mas-formula-text');
      const bannerBadge = document.getElementById('mas-formula-badge');
      if (bannerText) {
        bannerText.innerHTML = `<strong>Formula:</strong> Sum(Updated in Included) / (${nIncluded} Modules &times; Total Applicable GPs) &times; 100`;
      }
      if (bannerBadge) {
        const exclHtml = excluded.length === 0
          ? '<span style="color:#059669; font-weight:700;">✅ Excluded Modules from %: None (All 18 Modules Included)</span>'
          : `<span style="color:#b45309; font-weight:700;">⚡ Excluded Modules from %: ${escapeHtml(excluded.join(', '))}</span>`;
        bannerBadge.innerHTML = `${exclHtml} &nbsp;&bull;&nbsp; <span style="color:#047857; font-weight:700;">Cell Format:</span> Not Updated / Updated`;
      }
      const kpiModuleBase = document.getElementById('kpi-module-base');
      const kpiModuleSub = document.getElementById('kpi-module-sub');
      if (kpiModuleBase) kpiModuleBase.textContent = `${nIncluded} / 18 Modules`;
      if (kpiModuleSub) kpiModuleSub.textContent = excluded.length > 0 ? `${excluded.length} Excluded from %` : 'All modules active in %';
    }

    function onMasSelectionChanged() {
      masCurrentData = null;
      applyPreparedPeriodDisplay(false, '--', 'Period changed — click Generate Report', '');
    }

    function onMasReportTypeChanged() {
      masCurrentData = null;
      const rtype = document.getElementById('mas-select-report-type')?.value || '';
      const pdfBtn = document.getElementById('btn-mas-dl-pdf');
      if (pdfBtn) pdfBtn.style.display = rtype === 'abstract_only' ? 'none' : 'inline-flex';
      applyPreparedPeriodDisplay(false, '--', 'Report type changed — click Generate Report', '');
    }

    async function _performMasDownload(fileType) {
      const url = `/api/reports/mas-consolidated/download/${encodeURIComponent(fileType)}`;
      try {
        const res = await consoleApiFetch(url, { method: 'GET' });
        if (!res.ok) {
          let errMsg = `Download unavailable (${res.status}).`;
          try {
            const payload = await res.json();
            errMsg = payload.detail || payload.message || payload.error || errMsg;
          } catch (e) {}
          showPortalNotice(errMsg, 'warning');
          if (res.status === 401) {
            redirectMasToConsoleLogin('expired', false);
          }
          return;
        }
        const blob = await res.blob();
        const cd = res.headers.get('content-disposition') || '';
        const match = cd.match(/filename="?([^";]+)"?/i);
        const fallbackNames = {
          excel: 'MAS_Consolidated_Master.xlsx',
          pdf: 'MAS_Mandal_and_GP_Report.pdf',
          abstract_pdf: 'MAS_Mandal_Abstract.pdf',
          pending_csv: 'MAS_Pending_GPs_Action_List.csv'
        };
        const filename = (match && match[1]) ? match[1].trim() : (fallbackNames[fileType] || `MAS_Report_${fileType}`);
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
      } catch (err) {
        showPortalNotice('Failed to download report: ' + (err.message || 'Network error'), 'error');
      }
    }

    function handleMasDownloadClick(event, fileType) {
      if (event) event.preventDefault();
      if (!isDeptAuthenticated) {
        showPortalNotice('Please complete Department Login once on Console, then generate your report.', 'warning');
        redirectMasToConsoleLogin('required', false);
        return false;
      }
      if (!masCurrentData || !masCurrentData.success) {
        showPortalNotice('Please click "🚀 Generate Report" first to prepare downloadable deliverables.', 'warning');
        return false;
      }
      if (fileType === 'pdf' && masCurrentData.include_gp_data === false) {
        showPortalNotice('Select "Mandal Abstract & GP-Wise Data" and regenerate for GP-wise PDF, or use Download Mandal Abstract.', 'warning');
        return false;
      }
      _performMasDownload(fileType);
      return false;
    }

    function onDownloadMandalGpPdf(event) {
      return handleMasDownloadClick(event, 'pdf');
    }

    let masProgressInterval = null;
    function startMasProgressTimer(targetSec = 45) {
      if (masProgressInterval) clearInterval(masProgressInterval);
      const card = document.getElementById('mas-progress-card');
      const elapEl = document.getElementById('mas-elapsed-time');
      const estEl = document.getElementById('mas-estimated-time');
      const pctEl = document.getElementById('mas-progress-pct');
      const fillEl = document.getElementById('mas-progress-fill');
      const statusEl = document.getElementById('mas-status-text');
      const startMs = Date.now();
      let target = Math.max(15, targetSec);

      if (card) card.style.display = 'block';
      if (elapEl) elapEl.textContent = '00:00';
      if (estEl) estEl.textContent = formatSecMin(target);
      if (pctEl) pctEl.textContent = '0%';
      if (fillEl) fillEl.style.width = '0%';
      if (statusEl) statusEl.textContent = 'Extracting GM-R 5.24 & 5.23 reports from e-Panchayat portal...';

      masProgressInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startMs) / 1000);
        if (elapEl) elapEl.textContent = formatSecMin(elapsed);
        if (elapsed >= target - 2) target = elapsed + 6;
        if (estEl) estEl.textContent = formatSecMin(Math.max(0, target - elapsed));
        const pct = Math.min(96, Math.round((elapsed / Math.max(1, target)) * 96));
        if (pctEl) pctEl.textContent = pct + '%';
        if (fillEl) fillEl.style.width = pct + '%';
      }, 250);
    }

    function formatSecMin(sec) {
      const s = Math.max(0, Math.floor(sec || 0));
      const m = Math.floor(s / 60);
      const rem = s % 60;
      return (m < 10 ? '0' + m : m) + ':' + (rem < 10 ? '0' + rem : rem);
    }

    function finishMasProgressTimer(success) {
      if (masProgressInterval) {
        clearInterval(masProgressInterval);
        masProgressInterval = null;
      }
      const estEl = document.getElementById('mas-estimated-time');
      const pctEl = document.getElementById('mas-progress-pct');
      const fillEl = document.getElementById('mas-progress-fill');
      const statusEl = document.getElementById('mas-status-text');
      const card = document.getElementById('mas-progress-card');
      if (success) {
        if (estEl) estEl.textContent = '00:00';
        if (pctEl) pctEl.textContent = '100%';
        if (fillEl) fillEl.style.width = '100%';
        if (statusEl) statusEl.textContent = 'MAS report compiled successfully!';
        setTimeout(() => {
          if (card) card.style.display = 'none';
        }, 1500);
      } else {
        if (estEl) estEl.textContent = '--:--';
        if (statusEl) statusEl.textContent = 'MAS report generation halted.';
      }
    }

    async function runMasReportGeneration(isSilent) {
      const btn = document.getElementById('btn-run-mas');
      if (btn && btn.disabled) return;
      const monthSelect = document.getElementById('mas-select-month');
      const month = (monthSelect?.value || '').trim();
      if (!month) {
        if (!isSilent) {
          showPortalNotice('Please select a Reporting Month before generating the report.', 'warning');
          monthSelect?.focus();
        }
        return;
      }
      const year = parseInt(document.getElementById('mas-select-year')?.value || new Date().getFullYear(), 10);
      const rtypeEl = document.getElementById('mas-select-report-type');
      const reportType = (rtypeEl?.value || '').trim() || 'abstract_and_gp';
      if (rtypeEl && !rtypeEl.value) rtypeEl.value = reportType;

      if (!isStage1Authenticated) {
        handleMasAuthGateAction();
        return;
      }
      if (!isDeptAuthenticated) {
        if (!isSilent) {
          showPortalNotice(`Department Login required once to extract live ${month} ${year} MAS data.`, 'warning');
          redirectMasToConsoleLogin('required', false);
        }
        return;
      }

      const excluded = getSelectedExcludedModules();
      isGeneratingMas = true;
      if (!isSilent) startMasProgressTimer(reportType === 'abstract_only' ? 30 : 75);
      if (btn && !isSilent) {
        btn.disabled = true;
        btn.textContent = reportType === 'abstract_only'
          ? '⏳ Scraping Mandal Abstract...'
          : '⏳ Scraping Abstract & GP Data...';
      }

      async function _parseJsonOrText(response) {
        const raw = await response.text().catch(() => '');
        if (!raw) return {};
        try {
          return JSON.parse(raw);
        } catch (e) {
          const cleanSnippet = raw.replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim().slice(0, 180);
          return { detail: `HTTP ${response.status}: ${cleanSnippet || response.statusText || 'Unexpected server response'}` };
        }
      }

      try {
        const payloadBody = JSON.stringify({
          month: month,
          year: year,
          excluded_modules: excluded,
          report_type: reportType
        });

        let res = await consoleApiFetch('/api/reports/mas-consolidated/start-job', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payloadBody
        });
        let data = await _parseJsonOrText(res);

        if (res.status === 404) {
          res = await consoleApiFetch('/api/reports/mas-consolidated/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payloadBody
          });
          data = await _parseJsonOrText(res);
        } else if (res.ok && data && data.job_id && data.status === 'running') {
          const jobId = data.job_id;
          while (true) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            const pollRes = await consoleApiFetch(`/api/reports/mas-consolidated/jobs/${encodeURIComponent(jobId)}`);
            const pollData = await _parseJsonOrText(pollRes);
            if (pollRes.status === 401 || pollRes.status === 403) {
              res = pollRes;
              data = pollData;
              break;
            }
            if (!pollRes.ok) {
              res = pollRes;
              data = pollData;
              break;
            }
            if (pollData && pollData.status === 'running') {
              const sec = pollData.elapsed_sec ? Math.round(pollData.elapsed_sec) + 's' : '';
              const statusEl = document.getElementById('mas-status-text');
              if (statusEl) statusEl.textContent = sec ? `Extracting GM-R 5.24 & 5.23 reports (${sec})...` : 'Extracting GM-R 5.24 & 5.23 reports...';
              if (btn && !isSilent) {
                btn.textContent = sec
                  ? `⏳ Extracting GM-R 5.24 & 5.23 (${sec})...`
                  : '⏳ Extracting GM-R 5.24 & 5.23...';
              }
              continue;
            }
            res = pollRes;
            data = pollData;
            break;
          }
        }

        if (res.status === 401 || res.status === 403) {
          finishMasProgressTimer(false);
          if (!isSilent) {
            showPortalNotice(data.detail || 'Departmental session expired. Please re-authenticate once on Console.', 'warning');
            redirectMasToConsoleLogin('expired', false);
          }
          return;
        }
        if (data && data.success) {
          finishMasProgressTimer(true);
          masCurrentData = data;
          renderMasKPIs(data);
          renderMasTable(data);
          renderMasPendingTable(data);
          if (data.include_gp_data === false) switchMasView('abstract');
          if (!isSilent) {
            showPortalNotice(
              `✅ Live MAS report ready for ${data.month} ${data.year}: ${data.total_mandals} Mandals · ${data.total_gps} GPs (${data.pending_gps_count ?? 0} Pending GPs).`,
              'success'
            );
          }
        } else if (!isSilent) {
          finishMasProgressTimer(false);
          const errDetail = data.detail || data.error || data.message || `HTTP ${res.status || 'Error'} ${res.statusText || ''}`.trim();
          showPortalNotice('Error generating MAS report: ' + errDetail, 'error');
        }
      } catch (err) {
        finishMasProgressTimer(false);
        if (!isSilent) showPortalNotice('Failed to generate MAS report: ' + ((err && err.message) || 'Network error'), 'error');
      } finally {
        isGeneratingMas = false;
        if (btn) {
          btn.disabled = false;
          btn.textContent = '🚀 Generate Report';
        }
      }
    }

    function applyPreparedPeriodDisplay(isReady, periodText, metaText, tsText) {
      const bar = document.getElementById('mas-prepared-period-bar');
      const valEl = document.getElementById('mas-prepared-month-value');
      const metaEl = document.getElementById('mas-prepared-meta');
      const tsEl = document.getElementById('mas-prepared-timestamp');
      const tabBadge = document.getElementById('mas-table-period-badge');

      if (bar) {
        bar.style.background = isReady ? '#f0fdf4' : '#f8fafc';
        bar.style.borderBottom = isReady ? '1px solid #bbf7d0' : '1px solid #e2e8f0';
      }
      if (valEl) {
        valEl.textContent = periodText;
        valEl.style.background = isReady ? '#065f46' : '#e2e8f0';
        valEl.style.color = isReady ? '#ffffff' : '#334155';
      }
      if (metaEl) metaEl.textContent = metaText;
      if (tsEl) tsEl.textContent = tsText;
      if (tabBadge) {
        tabBadge.textContent = isReady ? `🗓️ Data Month: ${periodText}` : '🗓️ --';
        tabBadge.style.display = isReady ? 'inline-flex' : 'none';
      }
    }

    function renderMasKPIs(data) {
      const kpiPct = document.getElementById('kpi-overall-pct');
      const kpiPctSub = document.getElementById('kpi-pct-sub');
      const kpiUpdated = document.getElementById('kpi-updated-fields');
      const kpiFieldsSub = document.getElementById('kpi-fields-sub');
      const kpiCoverage = document.getElementById('kpi-coverage');
      const kpiCoverageSub = document.getElementById('kpi-coverage-sub');
      const kpiModuleBase = document.getElementById('kpi-module-base');
      const kpiModuleSub = document.getElementById('kpi-module-sub');
      const kpiPendingGps = document.getElementById('kpi-pending-gps');
      const kpiPendingGpsSub = document.getElementById('kpi-pending-gps-sub');

      if (kpiPct) {
        const distPctVal = Number(data.district_overall_pct || 0);
        const distPending = distPctVal < 100 || Number(data.pending_mandals_count || 0) > 0;
        kpiPct.textContent = `${data.district_overall_pct}%`;
        kpiPct.style.color = distPending ? '#dc2626' : '#065f46';
      }
      if (kpiPctSub) kpiPctSub.textContent = `Calculated across ${data.included_modules_count} included modules`;
      if (kpiUpdated) kpiUpdated.textContent = `${Number(data.total_updated_fields).toLocaleString()} / ${Number(data.total_possible_fields).toLocaleString()}`;
      if (kpiFieldsSub) kpiFieldsSub.textContent = `${Number(data.total_possible_fields - data.total_updated_fields).toLocaleString()} fields pending`;
      if (kpiCoverage) kpiCoverage.textContent = `${data.total_mandals} Mandals`;
      if (kpiCoverageSub) kpiCoverageSub.textContent = `${Number(data.total_gps || 0).toLocaleString()} Gram Panchayats`;
      if (kpiModuleBase) kpiModuleBase.textContent = `${data.included_modules_count} / ${data.total_modules} Modules`;
      if (kpiModuleSub) kpiModuleSub.textContent = data.excluded_modules.length > 0 ? `${data.excluded_modules.length} Excluded from %` : 'All modules active in %';

      const pendingGpsCount = data.pending_gps_count ?? (data.pending_action_list ? data.pending_action_list.length : 0);
      const isAbstractOnlyWithPendency = (data.include_gp_data === false && (data.pending_mandals_count || 0) > 0);
      if (kpiPendingGps) {
        kpiPendingGps.textContent = isAbstractOnlyWithPendency
          ? `${Number(data.pending_mandals_count || 0)} Mandals`
          : `${Number(pendingGpsCount).toLocaleString()} GPs`;
        kpiPendingGps.style.color = isAbstractOnlyWithPendency ? '#b45309' : (pendingGpsCount === 0 ? '#059669' : '#991b1b');
      }
      if (kpiPendingGpsSub) {
        kpiPendingGpsSub.textContent = isAbstractOnlyWithPendency
          ? 'Select "Abstract & GP-Wise Data" for GP count'
          : (pendingGpsCount === 0 ? `All ${Number(data.total_gps || 0).toLocaleString()} GPs 100% updated` : `${data.pending_mandals_count || 0} Mandals pending`);
      }

      const distEl = document.getElementById('mas-header-district');
      const offEl = document.getElementById('mas-header-officer');
      const scopeEl = document.getElementById('mas-header-scope');
      if (distEl && data.district) distEl.textContent = data.district;
      if (offEl && data.officer) offEl.textContent = data.officer;
      if (scopeEl) scopeEl.innerHTML = `&bull; ${escapeHtml(data.month)} ${escapeHtml(data.year)} &bull; ${data.total_mandals} Mandals &bull; ${Number(data.total_gps || 0).toLocaleString()} Gram Panchayats`;

      const nowStr = new Date().toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
      applyPreparedPeriodDisplay(
        true,
        `${data.month} ${data.year}`,
        `District: ${data.district || 'Active District'} • ${data.include_gp_data === false ? 'Mandal Abstract Only' : 'Mandal Abstract & GP-Wise Data'}`,
        `Prepared: ${nowStr}`
      );
    }

    const MAS_SHORT_HEADERS = {
      'Nursery': 'Nursery',
      'Plantation': 'Plant.',
      'Vaikunta Dhamam': 'Vaikunta<br>Dhamam',
      'Dump Yard': 'Dump<br>Yard',
      'Water Supply': 'Water<br>Supply',
      'GP Meetings': 'GP<br>Meet.',
      'Gram Sabha': 'Gram<br>Sabha',
      'Record Maintenance': 'Record<br>Maint.',
      'Approvals and Certificates': 'Approv.<br>&amp; Cert.',
      'Deaths': 'Deaths',
      'Recipts': 'Receipts',
      'Expenditure': 'Expend.',
      'Cheque Details': 'Cheque<br>Details',
      'Salary Details': 'Salary<br>Details',
      'VWSC Bank Balance': 'VWSC<br>Bal.',
      'MGNRE Bank Balance': 'MGNRE<br>Bal.',
      'Payment of Electricity': 'CC<br>Charges',
      'Birth Details': 'Birth<br>Details'
    };

    function renderMasTable(data) {
      const thead1 = document.getElementById('mas-thead-row-1');
      const thead2 = document.getElementById('mas-thead-row-2');
      const tbody = document.getElementById('mas-tbody');
      const tfoot = document.getElementById('mas-tfoot');
      if (!thead1 || !tbody || !tfoot) return;

      const nMandals = (data.mandals && data.mandals.length) ? data.mandals.length : 20;
      const cellPad = nMandals > 25 ? '4px 3px' : '5px 4px';
      const mandalPad = nMandals > 25 ? '4px 6px' : '5px 8px';
      const excludedSet = new Set(data.excluded_modules || []);

      let h1 = `
        <th style="padding:6px 3px; border:1px solid #165b43; width:34px; font-size:0.72rem; line-height:1.15;">S<br>No</th>
        <th style="padding:6px 8px; text-align:left; border:1px solid #165b43; min-width:118px; font-size:0.74rem;">Mandal Name</th>
        <th style="padding:6px 3px; border:1px solid #165b43; width:38px; font-size:0.72rem;">GPs</th>
        <th style="padding:6px 4px; border:1px solid #165b43; background:#10b981; color:#064e3b; font-weight:900; width:56px; font-size:0.72rem; line-height:1.15;">Overall<br>%</th>
      `;
      let h2 = `
        <th style="padding:4px 3px; border:1px solid #165b43;"></th>
        <th style="padding:4px 8px; border:1px solid #165b43;"></th>
        <th style="padding:4px 3px; border:1px solid #165b43;"></th>
        <th style="padding:4px 3px; border:1px solid #165b43; background:#059669; color:#ffffff; font-size:0.64rem; white-space:nowrap;">(${data.included_modules_count} Mod)</th>
      `;

      allMasModules.forEach(mod => {
        const isExcl = excludedSet.has(mod.label);
        const bg = isExcl ? '#b45309' : '#0c3829';
        const hdrHtml = MAS_SHORT_HEADERS[mod.label] || escapeHtml(mod.label);
        const tag = isExcl ? '<br><span style="font-size:0.58rem; color:#fef08a; background:rgba(0,0,0,0.3); padding:0px 3px; border-radius:3px;">[Excl]</span>' : '';
        h1 += `<th title="${escapeHtml(mod.label)}" style="padding:5px 3px; border:1px solid #165b43; background:${bg}; font-size:0.7rem; line-height:1.15; min-width:48px; vertical-align:middle;">${hdrHtml}${tag}</th>`;
        h2 += `<th title="Not Updated / Updated" style="padding:3px 2px; border:1px solid #165b43; background:${isExcl ? '#92400e' : '#165b43'}; font-size:0.62rem; font-weight:700; white-space:nowrap;">Not / Upd</th>`;
      });
      thead1.innerHTML = h1;
      if (thead2) thead2.innerHTML = h2;

      let bHtml = '';
      data.mandals.forEach((m, idx) => {
        const rowBg = idx % 2 === 0 ? '#ffffff' : '#f9fafb';
        const pct = Number(m['Overall % Entered'] || 0);
        const hasPendingMod = allMasModules.some(mod => {
          if (excludedSet.has(mod.label)) return false;
          const mi = m.modules[mod.label] || {};
          return Number(mi['Not Entered'] || 0) > 0;
        });
        const hasPending = pct < 100 || hasPendingMod;
        const pctColor = hasPending ? '#dc2626' : '#059669';
        const mandalColor = hasPending ? '#dc2626' : '#0f172a';
        bHtml += `<tr style="background:${rowBg}; border-bottom:1px solid #e5e7eb;">`;
        bHtml += `<td style="padding:${cellPad}; border:1px solid #e5e7eb; color:${hasPending ? '#dc2626' : '#64748b'}; font-weight:${hasPending ? '700' : '400'}; font-size:0.74rem;">${escapeHtml(m['S No'])}</td>`;
        bHtml += `<td style="padding:${mandalPad}; text-align:left; font-weight:700; color:${mandalColor}; border:1px solid #e5e7eb; font-size:0.75rem; white-space:nowrap;">${escapeHtml(m['Mandal Name'])}</td>`;
        bHtml += `<td style="padding:${cellPad}; border:1px solid #e5e7eb; font-weight:600; font-size:0.74rem;">${escapeHtml(m['No of GPs'])}</td>`;
        bHtml += `<td style="padding:${cellPad}; border:1px solid #e5e7eb; font-weight:800; color:${pctColor}; font-size:0.75rem; white-space:nowrap;">${pct}%</td>`;
        allMasModules.forEach(mod => {
          const isExcl = excludedSet.has(mod.label);
          const modInfo = m.modules[mod.label] || { formatted_compact: '-' };
          const isModPending = !isExcl && Number(modInfo['Not Entered'] || 0) > 0;
          const cellBg = isExcl ? '#fffbeb' : (isModPending ? '#fef2f2' : 'inherit');
          const cellClr = isExcl ? '#92400e' : (isModPending ? '#dc2626' : '#334155');
          const cellWt = isModPending ? '800' : '600';
          bHtml += `<td style="padding:${cellPad}; border:1px solid #e5e7eb; background:${cellBg}; color:${cellClr}; font-weight:${cellWt}; font-size:0.73rem; white-space:nowrap;">${escapeHtml(modInfo.formatted_compact)}</td>`;
        });
        bHtml += '</tr>';
      });
      tbody.innerHTML = bHtml;

      const tot = data.total_row;
      const totPctVal = Number(tot['Overall % Entered'] || 0);
      const totHasPending = totPctVal < 100 || allMasModules.some(mod => !excludedSet.has(mod.label) && Number((tot.modules[mod.label] || {})['Not Entered'] || 0) > 0);
      let fHtml = `
        <tr style="border-top:2px solid #0f172a; border-bottom:3px double #0f172a; background:#fef3c7;">
          <td style="padding:7px 4px; border:1px solid #cbd5e1; font-weight:800; font-size:0.74rem;">Tot</td>
          <td style="padding:7px 8px; text-align:left; font-weight:900; color:#0c3829; border:1px solid #cbd5e1; font-size:0.75rem;">District Total</td>
          <td style="padding:7px 4px; border:1px solid #cbd5e1; font-weight:800; font-size:0.74rem;">${escapeHtml(tot['No of GPs'])}</td>
          <td style="padding:7px 4px; border:1px solid #cbd5e1; font-weight:900; font-size:0.75rem; color:${totHasPending ? '#dc2626' : '#065f46'}; white-space:nowrap;">${escapeHtml(tot['Overall % Entered'])}%</td>
      `;
      allMasModules.forEach(mod => {
        const isExcl = excludedSet.has(mod.label);
        const modInfo = tot.modules[mod.label] || { formatted_compact: '-' };
        const isTotModPending = !isExcl && Number(modInfo['Not Entered'] || 0) > 0;
        const totModClr = isExcl ? '#92400e' : (isTotModPending ? '#dc2626' : '#0f172a');
        fHtml += `<td style="padding:7px 3px; border:1px solid #cbd5e1; background:${isExcl ? '#fef08a' : '#fef3c7'}; color:${totModClr}; font-weight:800; font-size:0.73rem; white-space:nowrap;">${escapeHtml(modInfo.formatted_compact)}</td>`;
      });
      fHtml += '</tr>';
      tfoot.innerHTML = fHtml;
    }

    function switchMasView(viewName) {
      const abstractView = document.getElementById('mas-abstract-view');
      const pendingView = document.getElementById('mas-pending-view');
      const btnAbstract = document.getElementById('tab-btn-abstract');
      const btnPending = document.getElementById('tab-btn-pending');

      if (viewName === 'pending') {
        if (abstractView) abstractView.style.display = 'none';
        if (pendingView) pendingView.style.display = 'block';
        if (btnAbstract) { btnAbstract.style.background = '#ffffff'; btnAbstract.style.color = '#475569'; btnAbstract.style.borderColor = '#cbd5e1'; }
        if (btnPending) { btnPending.style.background = '#b45309'; btnPending.style.color = '#ffffff'; btnPending.style.borderColor = '#b45309'; }
      } else {
        if (pendingView) pendingView.style.display = 'none';
        if (abstractView) abstractView.style.display = 'block';
        if (btnPending) { btnPending.style.background = '#ffffff'; btnPending.style.color = '#475569'; btnPending.style.borderColor = '#cbd5e1'; }
        if (btnAbstract) { btnAbstract.style.background = '#0c3829'; btnAbstract.style.color = '#ffffff'; btnAbstract.style.borderColor = '#0c3829'; }
      }
    }

    function renderMasPendingTable(data) {
      const tbody = document.getElementById('mas-pending-tbody');
      const badge = document.getElementById('pending-badge');
      const isAbstractOnly = (data.include_gp_data === false);
      const pendingMandals = data.pending_mandals_count || 0;
      const pCount = data.pending_gps_count ?? (data.pending_action_list ? data.pending_action_list.length : 0);
      const nIncl = data.included_modules_count || 18;

      if (badge) {
        badge.textContent = (isAbstractOnly && pendingMandals > 0) ? 'Abstract Only' : `${pCount} Pending`;
        badge.style.background = (isAbstractOnly && pendingMandals > 0) ? '#b45309' : (pCount > 0 ? '#dc2626' : '#059669');
      }
      if (!tbody) return;

      if (isAbstractOnly && pendingMandals > 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="padding:36px; color:#92400e; background:#fffbeb;"><strong>Mandal Abstract Only Mode Selected</strong> — Select "Mandal Abstract &amp; GP-Wise Data" when GP drill-down rows are required (${pendingMandals} pending mandals).</td></tr>`;
        return;
      }

      const pList = data.pending_action_list || [];
      if (pList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="padding:36px; color:#059669; background:#f0fdf4;"><strong>🎉 100% Fully Compliant — Zero Pendency!</strong></td></tr>`;
        return;
      }

      tbody.innerHTML = pList.map((item, idx) => {
        const bg = idx % 2 === 0 ? '#ffffff' : '#f9fafb';
        const modPills = String(item.Pending_Modules || '').split(',').map(m => {
          const trimmed = m.trim();
          return trimmed ? `<span style="display:inline-block; background:#fee2e2; color:#991b1b; border:1px solid #fca5a5; padding:2px 7px; border-radius:12px; font-size:0.72rem; font-weight:700; margin:2px;">${escapeHtml(trimmed)}</span>` : '';
        }).join('');
        const totAct = item.Total_Activities || nIncl;
        return (
          `<tr style="background:${bg}; border-bottom:1px solid #e5e7eb;">` +
          `<td style="padding:9px 8px; border:1px solid #e5e7eb; color:#64748b; font-weight:700;">${idx + 1}</td>` +
          `<td style="padding:9px 12px; text-align:left; font-weight:800; color:#0f172a; border:1px solid #e5e7eb;">${escapeHtml(item.Mandal)}</td>` +
          `<td style="padding:9px 12px; text-align:left; font-weight:700; color:#1e3a8a; border:1px solid #e5e7eb;">${escapeHtml(item.Gram_Panchayat)}</td>` +
          `<td style="padding:9px 8px; border:1px solid #e5e7eb; font-weight:800; color:#b91c1c;">${escapeHtml(item.Pending_Count)} Pending</td>` +
          `<td style="padding:9px 10px; text-align:left; border:1px solid #e5e7eb;">${modPills}</td>` +
          `<td style="padding:9px 8px; border:1px solid #e5e7eb; font-weight:700; color:#059669;">${escapeHtml(item.Completed_Count)} / ${totAct}</td>` +
          `<td style="padding:9px 8px; border:1px solid #e5e7eb; font-weight:800; color:#dc2626;">${escapeHtml(item.Completion_Rate)}</td>` +
          `</tr>`
        );
      }).join('');
    }

    function filterMasTable() {
      const query = (document.getElementById('mas-table-filter')?.value || '').toLowerCase().trim();
      document.querySelectorAll('#mas-tbody tr').forEach(row => {
        const mandalCell = row.children[1];
        if (mandalCell) row.style.display = mandalCell.innerText.toLowerCase().includes(query) ? '' : 'none';
      });
      document.querySelectorAll('#mas-pending-tbody tr').forEach(row => {
        const mCell = row.children[1];
        const gpCell = row.children[2];
        if (mCell && gpCell) row.style.display = (mCell.innerText + ' ' + gpCell.innerText).toLowerCase().includes(query) ? '' : 'none';
      });
    }

    async function refreshMasAuthStatus(forceCheck) {
      if (isGeneratingMas && !forceCheck) {
        return { stage1: { authenticated: isStage1Authenticated }, dept: { authenticated: isDeptAuthenticated } };
      }
      let stage1 = { authenticated: false };
      let dept = { authenticated: false };
      if (window.DeptSessionManager) {
        stage1 = await window.DeptSessionManager.verifyStage1PortalStatus();
        if (stage1 && stage1.transientError) {
          return { stage1: { authenticated: isStage1Authenticated }, dept: { authenticated: isDeptAuthenticated } };
        }
        if (stage1 && stage1.authenticated) {
          dept = await window.DeptSessionManager.verifyStatus();
          if (dept && dept.status === 'error') {
            return { stage1, dept: { authenticated: isDeptAuthenticated } };
          }
        }
      }
      const prevDept = isDeptAuthenticated;
      updateSessionBannerUI(stage1, dept);
      if (!prevDept && isStage1Authenticated && isDeptAuthenticated && !hasFetchedPortalYears) {
        fetchMasYearsFromPortal(true);
      }
      return { stage1, dept };
    }

    async function bootMasWorkspace() {
      initYearSelector();

      if (window.DeptSessionManager) {
        const homeHref = window.DeptSessionManager.getConsoleHomeUrl();
        const backEl = document.getElementById('mas-back-console-link');
        const brandEl = document.getElementById('mas-brand-home-link');
        if (backEl) backEl.href = homeHref;
        if (brandEl) brandEl.href = homeHref;
      }

      const qp = new URLSearchParams(window.location.search);
      const qpExcluded = new Set(
        (qp.get('excluded_modules') || '').split(',').map(s => s.trim()).filter(Boolean)
      );

      const { stage1 } = await refreshMasAuthStatus();
      if (stage1 && stage1.authenticated) {
        try {
          const res = await consoleApiFetch('/api/reports/mas-consolidated/modules');
          if (res.ok) {
            const payload = await res.json();
            if (payload && payload.success && Array.isArray(payload.modules) && payload.modules.length) {
              allMasModules = payload.modules;
            }
          }
        } catch (e) {}
      }

      renderMasModuleChips(qpExcluded.size ? qpExcluded : null);

      const mSel = document.getElementById('mas-select-month');
      const ySel = document.getElementById('mas-select-year');
      const rtSel = document.getElementById('mas-select-report-type');
      const qpYear = qp.get('year');
      if (mSel && qp.get('month')) mSel.value = qp.get('month');
      if (ySel && qpYear) ySel.value = qpYear;
      if (rtSel && qp.get('report_type')) {
        rtSel.value = qp.get('report_type');
        onMasReportTypeChanged();
      }

      if (isStage1Authenticated && isDeptAuthenticated) {
        await fetchMasYearsFromPortal(true, qpYear || (ySel ? ySel.value : ''));
        if (mSel && qp.get('month')) mSel.value = qp.get('month');
        if (ySel && qpYear) ySel.value = qpYear;
      }

      if (qp.get('auto_generate') === '1' && mSel && mSel.value && isStage1Authenticated && isDeptAuthenticated) {
        await runMasReportGeneration(false);
      }
    }

    document.addEventListener('DOMContentLoaded', bootMasWorkspace);
    setInterval(refreshMasAuthStatus, 15000);
  </script>
</body>
</html>
"""
)
