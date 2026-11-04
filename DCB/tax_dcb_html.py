"""HTML template for the House Tax DCB Consolidation & PDF Report Viewer."""

TAX_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telangana ePanchayat · House Tax DCB Consolidation</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #f4f7f6;
      color: #15332b;
      line-height: 1.5;
    }

    /* Navbar */
    .navbar {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: #0c3829;
      color: white;
      box-shadow: 0 2px 12px rgba(0,0,0,0.15);
    }
    .nav-inner {
      max-width: 1240px;
      margin: 0 auto;
      padding: 0 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 64px;
    }
    .nav-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      color: white;
    }
    .nav-brand-logo { font-size: 1.7rem; line-height: 1; }
    .nav-brand-titles { display: flex; flex-direction: column; }
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
      letter-spacing: -0.01em;
      color: #ffffff;
    }
    .nav-menu { display: flex; align-items: center; gap: 10px; }
    .nav-link {
      color: #d4e8de;
      text-decoration: none;
      padding: 8px 14px;
      font-weight: 600;
      font-size: 0.92rem;
      border-radius: 8px;
      transition: all 0.15s;
    }
    .nav-link:hover { color: white; background: rgba(255,255,255,0.1); }
    .nav-link.active { color: white; background: #167451; }

    /* Layout */
    main {
      max-width: 1240px;
      margin: 24px auto 60px;
      padding: 0 20px;
    }

    /* Header Banner */
    .hero-strip {
      background: linear-gradient(135deg, #0d3d2c 0%, #167451 100%);
      color: white;
      border-radius: 16px;
      padding: 24px 28px;
      box-shadow: 0 10px 28px rgba(12,56,41,0.14);
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }
    .hero-info h1 {
      margin: 4px 0 6px;
      font-size: 1.65rem;
      font-weight: 800;
      letter-spacing: -0.01em;
    }
    .hero-info p {
      margin: 0;
      font-size: 0.92rem;
      color: #d8f3e5;
    }
    .hero-badge {
      display: inline-block;
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.25);
      color: #c4f2dc;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 3px 8px;
      border-radius: 5px;
    }

    /* Filter & Controls Bar */
    .controls-card {
      background: white;
      border: 1px solid #d9e6df;
      border-radius: 14px;
      padding: 20px 24px;
      box-shadow: 0 6px 20px rgba(23,59,43,0.04);
      margin-bottom: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .controls-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      align-items: flex-end;
    }
    .control-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .control-label {
      font-size: 0.84rem;
      font-weight: 700;
      color: #274b3f;
    }
    select, input[type="text"] {
      padding: 10px 12px;
      border: 1px solid #c2d6cc;
      border-radius: 8px;
      font-size: 0.92rem;
      color: #15332b;
      background: #fafcfb;
      font-family: inherit;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    select:focus, input[type="text"]:focus {
      border-color: #167451;
      box-shadow: 0 0 0 3px rgba(22, 116, 81, 0.15);
      background: white;
    }
    .actions-bar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      padding-top: 14px;
      border-top: 1px solid #edf4f0;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 10px 16px;
      font-size: 0.88rem;
      font-weight: 700;
      border-radius: 8px;
      text-decoration: none;
      cursor: pointer;
      border: none;
      font-family: inherit;
      transition: all 0.15s;
    }
    .btn-primary { background: #167451; color: white; }
    .btn-primary:hover { background: #115d40; }
    .btn-secondary { background: #eaf5ef; color: #167451; border: 1px solid #b9ddcb; }
    .btn-secondary:hover { background: #d7ede1; }
    .btn-pdf { background: #0b5ed7; color: white; }
    .btn-pdf:hover { background: #0948a5; }
    .btn-outline { background: white; color: #2e5445; border: 1px solid #cfe0d7; }
    .btn-outline:hover { background: #f3f9f6; }

    /* KPI Summary Cards */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }
    .kpi-card {
      background: white;
      border: 1px solid #d9e6df;
      border-radius: 12px;
      padding: 16px 18px;
      box-shadow: 0 4px 16px rgba(23,59,43,0.04);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .kpi-title {
      font-size: 0.74rem;
      font-weight: 700;
      color: #627f74;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }
    .kpi-val {
      font-size: 1.45rem;
      font-weight: 800;
      color: #123d2e;
      line-height: 1.2;
    }
    .kpi-sub {
      font-size: 0.76rem;
      color: #7a948b;
      margin-top: 4px;
    }
    .kpi-card.kpi-highlight {
      border: 2px solid #167451;
      background: #fbfdfc;
    }
    .kpi-card.kpi-highlight .kpi-val {
      color: #167451;
    }

    /* Content Tabs */
    .tabs-wrap {
      display: flex;
      gap: 8px;
      margin-bottom: 16px;
      border-bottom: 2px solid #dbe6e0;
    }
    .tab-item {
      padding: 10px 18px;
      font-size: 0.94rem;
      font-weight: 700;
      color: #557267;
      background: transparent;
      border: none;
      border-radius: 8px 8px 0 0;
      cursor: pointer;
      transition: all 0.15s;
      border-bottom: 3px solid transparent;
      margin-bottom: -2px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .tab-item:hover { color: #167451; background: #eef6f2; }
    .tab-item.active {
      color: #167451;
      border-bottom: 3px solid #167451;
      background: #eaf5ef;
    }

    .tab-pane { display: none; }
    .tab-pane.active { display: block; }

    /* PDF Viewer Container */
    .pdf-viewer-card {
      background: white;
      border: 1px solid #d9e6df;
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 8px 24px rgba(23,59,43,0.06);
    }
    .pdf-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 12px;
      margin-bottom: 12px;
      border-bottom: 1px solid #eef3f0;
      flex-wrap: wrap;
      gap: 10px;
    }
    .pdf-toolbar-info {
      font-size: 0.9rem;
      font-weight: 700;
      color: #1c4b3a;
    }
    .pdf-iframe {
      width: 100%;
      height: 820px;
      border: 1px solid #cfe0d7;
      border-radius: 8px;
      background: #525659;
    }

    /* Table Card */
    .table-card {
      background: white;
      border: 1px solid #d9e6df;
      border-radius: 14px;
      padding: 20px;
      box-shadow: 0 8px 24px rgba(23,59,43,0.05);
      overflow-x: auto;
    }
    .table-header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
      flex-wrap: wrap;
      gap: 10px;
    }
    .table-title {
      font-size: 1.05rem;
      font-weight: 750;
      color: #15332b;
      margin: 0;
    }
    table.data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      text-align: left;
    }
    table.data-table th, table.data-table td {
      padding: 9px 12px;
      border: 1px solid #e0ebe5;
    }
    table.data-table th {
      background: #f2f7f4;
      color: #1b4938;
      font-weight: 700;
      white-space: nowrap;
    }
    table.data-table tbody tr:hover {
      background: #f8fcfa;
    }
    .num-cell {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .center-cell {
      text-align: center;
    }
    .pct-line-col {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      width: 62px;
      margin: 0 auto;
    }
    .pct-line-val {
      font-weight: 800;
      font-size: 0.82rem;
      color: #111827;
      line-height: 1.1;
    }
    .pct-line-track {
      width: 100%;
      height: 5px;
      background: #e2e8f0;
      border-radius: 3px;
      overflow: hidden;
    }
    .pct-line-fill {
      height: 100%;
      border-radius: 3px;
      transition: width 0.35s ease;
    }
    .pct-meter {
      position: relative;
      width: 68px;
      height: 22px;
      margin: 0 auto;
      background: #edf2ef;
      border: 1px solid #cbd5cf;
      border-radius: 5px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: inset 0 1px 2px rgba(0,0,0,0.06);
    }
    .pct-meter-fill {
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      border-radius: 4px;
      transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .pct-meter-text {
      position: relative;
      z-index: 2;
      font-weight: 800;
      font-size: 0.78rem;
      color: #111827;
      text-shadow: 0 0 3px rgba(255, 255, 255, 0.95), 0 0 1px #ffffff;
      letter-spacing: -0.01em;
    }
    .pct-badge {
      display: inline-block;
      min-width: 42px;
      padding: 2px 7px;
      border-radius: 5px;
      font-weight: 750;
      font-size: 0.82rem;
      color: white;
      text-align: center;
      background: #16874e;
    }
    .total-row {
      font-weight: 750;
      background: #eef6f2 !important;
      border-top: 2px solid #167451;
    }

    /* Pagination */
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 14px;
      margin-top: 12px;
      border-top: 1px solid #edf4f0;
      font-size: 0.86rem;
      color: #557267;
      flex-wrap: wrap;
      gap: 10px;
    }
    .pagination-btns {
      display: flex;
      gap: 6px;
    }
    .page-btn {
      padding: 5px 12px;
      border: 1px solid #cfe0d7;
      background: white;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.84rem;
      font-weight: 600;
      color: #167451;
    }
    .page-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    /* Status Banner */
    .status-alert {
      display: none;
      padding: 10px 14px;
      border-radius: 8px;
      margin-bottom: 14px;
      font-size: 0.88rem;
      font-weight: 600;
    }
    .status-alert.info { display: block; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .status-alert.success { display: block; background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .status-alert.error { display: block; background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }

    /* Floating Mobile Download Toast & Notification Center */
    .download-toast-container {
      position: fixed;
      bottom: 22px;
      left: 50%;
      transform: translateX(-50%);
      width: calc(100% - 28px);
      max-width: 480px;
      z-index: 999999;
      pointer-events: none;
    }
    .download-toast-card {
      pointer-events: auto;
      background: #0f172a;
      color: #f8fafc;
      border: 1.5px solid #334155;
      border-radius: 14px;
      box-shadow: 0 16px 38px rgba(0, 0, 0, 0.45), 0 4px 14px rgba(0, 0, 0, 0.25);
      overflow: hidden;
      animation: toastSlideUp 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
      backdrop-filter: blur(8px);
    }
    @keyframes toastSlideUp {
      from { opacity: 0; transform: translateY(28px) scale(0.96); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .download-toast-card.toast-exit {
      animation: toastSlideDown 0.28s cubic-bezier(0.4, 0, 1, 1) forwards;
    }
    @keyframes toastSlideDown {
      from { opacity: 1; transform: translateY(0) scale(1); }
      to { opacity: 0; transform: translateY(28px) scale(0.96); }
    }
    .download-toast-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 13px 16px;
    }
    .download-toast-icon-wrap {
      flex-shrink: 0;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      background: rgba(255, 255, 255, 0.08);
    }
    .download-toast-icon-wrap.loading {
      background: rgba(14, 165, 233, 0.18);
      color: #38bdf8;
    }
    .download-toast-icon-wrap.success {
      background: rgba(34, 197, 94, 0.22);
      color: #4ade80;
    }
    .download-toast-icon-wrap.error {
      background: rgba(239, 68, 68, 0.22);
      color: #f87171;
    }
    .download-toast-body {
      flex: 1;
      min-width: 0;
    }
    .download-toast-title {
      font-weight: 700;
      font-size: 0.94rem;
      line-height: 1.25;
      color: #ffffff;
    }
    .download-toast-subtitle {
      font-size: 0.8rem;
      color: #94a3b8;
      margin-top: 3px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .download-toast-close {
      background: transparent;
      border: none;
      color: #94a3b8;
      font-size: 1.4rem;
      line-height: 1;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 6px;
      transition: all 0.15s;
    }
    .download-toast-close:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.1);
    }
    .download-toast-actions {
      display: flex;
      gap: 8px;
      padding: 0 16px 14px 16px;
    }
    .download-toast-btn-open {
      flex: 1;
      background: #16a34a;
      color: white;
      border: none;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: background 0.15s;
      text-decoration: none;
    }
    .download-toast-btn-open:hover, .download-toast-btn-open:active {
      background: #15803d;
    }
    .download-toast-btn-dismiss {
      background: rgba(255, 255, 255, 0.1);
      color: #e2e8f0;
      border: 1px solid rgba(255, 255, 255, 0.15);
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .download-toast-btn-dismiss:hover {
      background: rgba(255, 255, 255, 0.2);
    }
    .download-toast-progress {
      height: 3px;
      background: linear-gradient(90deg, #10b981, #06b6d4);
      width: 100%;
      transform-origin: left;
    }
    .download-toast-progress.loading {
      animation: toastProgressPulse 1.5s infinite;
    }
    @keyframes toastProgressPulse {
      0% { transform: scaleX(0.1); opacity: 0.6; }
      50% { transform: scaleX(0.8); opacity: 1; }
      100% { transform: scaleX(1); opacity: 0.4; }
    }
    .toast-spinner {
      width: 20px;
      height: 20px;
      border: 2.5px solid rgba(255, 255, 255, 0.2);
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: toastSpin 0.75s linear infinite;
    }
    @keyframes toastSpin {
      to { transform: rotate(360deg); }
    }
    @media (max-width: 600px) {
      .download-toast-container {
        bottom: 14px;
        width: calc(100% - 20px);
      }
      .download-toast-card {
        border-radius: 12px;
      }
      .download-toast-header {
        padding: 12px 14px;
        gap: 10px;
      }
      .download-toast-icon-wrap {
        width: 34px;
        height: 34px;
        font-size: 1.1rem;
      }
      .download-toast-title {
        font-size: 0.9rem;
      }
      .download-toast-subtitle {
        font-size: 0.76rem;
      }
      .download-toast-actions {
        padding: 0 14px 12px 14px;
      }
      .download-toast-btn-open {
        font-size: 0.84rem;
        padding: 9px 12px;
      }
    }

    footer {
      border-top: 1px solid #dce6e1;
      margin-top: 60px;
      padding: 22px 20px;
      text-align: center;
      color: #5a7369;
      font-size: 0.84rem;
      background: white;
    }

    /* Power BI Executive Visual Report Styles */
    .pbi-container {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
      margin-bottom: 30px;
    }
    .pbi-toolbar-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      padding-bottom: 12px;
      margin-bottom: 12px;
      border-bottom: 1px solid #cbd5e1;
    }
    .pbi-badge {
      display: inline-block;
      background: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 750;
      letter-spacing: 0.04em;
    }
    .pbi-canvas-card {
      background: #ffffff;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    /* District Header Banner (Page 1) */
    .pbi-banner-district {
      background: #D2E3FC;
      border: 1.5px solid #85AEE0;
      border-radius: 4px;
      padding: 12px 20px;
      text-align: center;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .pbi-banner-district-title {
      font-size: 1.35rem;
      font-weight: 900;
      color: #0f172a;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    }
    /* Mandal Header Banner (Page 2) */
    .pbi-banner-mandal {
      background: #FEF9C3;
      border: 1.5px solid #FACC15;
      border-radius: 4px;
      padding: 10px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .pbi-banner-mandal-title {
      font-size: 1.30rem;
      font-weight: 900;
      color: #DC2626;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    }
    .pbi-slicer-container {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .pbi-slicer-select {
      background: #ffffff;
      border: 1.5px solid #94A3B8;
      border-radius: 4px;
      padding: 5px 12px;
      font-size: 0.90rem;
      font-weight: 700;
      color: #0f172a;
      outline: none;
      cursor: pointer;
    }
    .pbi-slicer-select:focus {
      border-color: #0284c7;
      box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.2);
    }
    /* Cards inside PBI Canvas */
    .pbi-card {
      background: #ffffff;
      border: 1px solid #d1d5db;
      border-radius: 4px;
      padding: 12px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
    }
    .pbi-card-title {
      font-size: 0.92rem;
      font-weight: 800;
      color: #0f172a;
      margin-bottom: 8px;
      padding-bottom: 4px;
      border-bottom: 1px solid #f1f5f9;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    }
    /* Table Styling */
    .pbi-table-wrap {
      overflow-y: auto;
      overflow-x: auto;
      width: 100%;
    }
    .pbi-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.80rem;
      border: 1px solid #000000;
      font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    }
    .pbi-table th {
      position: sticky;
      top: 0;
      background: #ffffff;
      color: #0f172a;
      font-weight: 800;
      padding: 5px 6px;
      border: 1px solid #000000;
      text-align: left;
      font-size: 0.77rem;
      white-space: nowrap !important;
      z-index: 5;
    }
    .pbi-table td {
      padding: 3px 6px;
      border: 1px solid #000000;
      color: #1e293b;
      white-space: nowrap;
    }
    .pbi-table tbody tr:hover {
      background: #f8fafc;
    }
    .pbi-pct-heatmap-cell {
      text-align: center !important;
      font-weight: 800 !important;
      font-size: 0.88rem !important;
      padding: 3px 2px !important;
      border: 1px solid #000000 !important;
      letter-spacing: -0.2px;
      line-height: 1.2;
    }
    .pbi-pct-heatmap-badge {
      display: inline-block;
      min-width: 44px;
      padding: 2px 6px;
      font-weight: 800;
      font-size: 0.82rem;
      text-align: center;
      border-radius: 4px;
      border: 1px solid #000000;
    }
    /* Power BI Data Bars */
    .pbi-databar-td {
      position: relative;
      padding: 2px 4px !important;
      text-align: right;
      min-width: 80px;
    }
    .pbi-databar-wrap {
      position: relative;
      width: 100%;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding-right: 4px;
      border-radius: 2px;
      overflow: hidden;
    }
    .pbi-databar-fill {
      position: absolute;
      left: 0;
      top: 1px;
      bottom: 1px;
      background: #3B82F6;
      opacity: 0.65;
      border-radius: 2px;
      transition: width 0.3s ease;
    }
    .pbi-databar-val {
      position: relative;
      z-index: 2;
      font-weight: 850;
      font-size: 0.76rem;
      color: #0f172a;
    }
    /* SVG Gauge */
    .gauge-svg {
      width: 100%;
      max-width: 230px;
      height: auto;
      display: block;
      margin: 0 auto;
    }
    @media (max-width: 1024px) {
      .pbi-row {
        flex-direction: column !important;
      }
    }
    @media print {
      @page {
        size: A4 landscape;
        margin: 4mm 6mm;
      }
      *, *::before, *::after {
        box-sizing: border-box !important;
      }
      html, body {
        width: 100% !important;
        height: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        background: white !important;
        overflow: hidden !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }
      .navbar, .hero-strip, .controls-card, .kpi-grid, .tabs-wrap, #pane-pdf, #pane-abstract, #pane-detail, .pbi-toolbar-bar, #status-box, footer {
        display: none !important;
      }
      #pane-visual {
        display: block !important;
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
        page-break-after: avoid !important;
        break-after: avoid !important;
      }
      .pbi-container {
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        background: white !important;
        width: 100% !important;
        max-width: 100% !important;
      }
      #pbi-canvas-export {
        display: flex !important;
        flex-direction: column !important;
        padding: 0 !important;
        width: 100% !important;
        max-width: 100% !important;
        height: auto !important;
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        page-break-after: avoid !important;
        break-after: avoid !important;
      }
      .pbi-banner {
        padding: 3px 6px !important;
        margin-bottom: 4px !important;
        font-size: 0.95rem !important;
        border-width: 1px !important;
      }
      .pbi-row {
        display: flex !important;
        flex-direction: row !important;
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        margin-top: 4px !important;
        gap: 6px !important;
      }
      .pbi-card {
        page-break-inside: avoid !important;
        break-inside: avoid !important;
        padding: 4px 6px !important;
        box-shadow: none !important;
        border: 1px solid #CBD5E1 !important;
      }
      .pbi-card-title {
        font-size: 0.72rem !important;
        margin-bottom: 2px !important;
      }
      /* Row 1 tight height for single page landscape print */
      .pbi-table-wrap {
        max-height: 235px !important;
        overflow: hidden !important;
      }
      .pbi-table th, .pbi-table td {
        padding: 2px 4px !important;
        font-size: 0.68rem !important;
      }
      #chart-dist-clustered {
        height: 235px !important;
        max-height: 235px !important;
      }
      /* Row 2 tight height for print */
      #chart-dist-ranking, #chart-dist-donut {
        height: 165px !important;
        max-height: 165px !important;
      }
      .gauge-svg {
        height: 120px !important;
        max-height: 120px !important;
      }
      .gauge-center-text {
        font-size: 26px !important;
      }
    }
  </style>
</head>
<body>
  <!-- Navbar -->
  <header class="navbar">
    <div class="nav-inner">
      <a class="nav-brand" href="/">
        <span class="nav-brand-logo">🏛️</span>
        <div class="nav-brand-titles">
          <span class="nav-brand-main">Panchayat Raj Analytics Reports</span>
        </div>
      </a>
      <nav class="nav-menu">
        <a class="nav-link" href="/">🏠 Home</a>
        <a class="nav-link" href="/reports/ps-attendance">📋 PS Attendance</a>
        <a class="nav-link active" href="/reports/tax-dcb">💰 House Tax (DCB) Report</a>
      </nav>
    </div>
  </header>

  <main>
    <!-- Hero Banner -->
    <section class="hero-strip">
      <div class="hero-info">
        <span class="hero-badge">ePanchayat Departmental Live Data</span>
        <h1>Gram Panchayat Wise DCB Status Report</h1>
        <p>Consolidated Demand, Collection, and Balance (DCB) for House Tax across all Mandals and Gram Panchayats</p>
      </div>
    </section>

    <div id="status-box" class="status-alert"></div>

    <!-- Controls Bar -->
    <section class="controls-card">
      <div class="controls-grid">
        <div class="control-group">
          <label class="control-label" for="district-select">1. Select District <span style="color:#c92a2a">*</span></label>
          <select id="district-select">
            <option value="" selected disabled>-- Select District --</option>
          </select>
        </div>

        <div class="control-group">
          <label class="control-label" for="mandal-select">2. Filter by Mandal</label>
          <select id="mandal-select" disabled>
            <option value="all">-- Select District First --</option>
          </select>
        </div>

        <div class="control-group">
          <label class="control-label" for="search-input">3. Instant Search GP or Mandal</label>
          <input type="text" id="search-input" placeholder="Type Panchayat or Mandal name...">
        </div>

        <div class="control-group" style="justify-content: flex-end;">
          <button type="button" id="btn-generate-report" class="btn btn-primary" style="padding: 10px 22px; font-weight:700; font-size:0.95rem; height:42px; display:flex; align-items:center; justify-content:center; gap:8px;" onclick="onGenerateReportClick()">
            <span>⚡</span> Generate Report
          </button>
        </div>
      </div>

      <div class="actions-bar" id="actions-bar" style="display: none;">
        <button type="button" id="btn-download-pbi-pdf" class="btn btn-primary" onclick="downloadPowerBiPdf(this)" style="display:flex; align-items:center; gap:6px;">
          📥 Download Power BI Report (PDF)
        </button>
        <button type="button" id="btn-download-pdf" class="btn btn-pdf" style="display:flex; align-items:center; gap:6px;">
          📄 Download PDF Report
        </button>
        <button type="button" id="btn-download-excel" class="btn btn-secondary" style="display:flex; align-items:center; gap:6px;">
          📊 Download Consolidated Excel (.xlsx)
        </button>
        <button type="button" id="btn-visual-report" class="btn btn-secondary" onclick="openVisualReport()" style="display:flex; align-items:center; gap:6px;">
          📊 Executive Visual Report (Power BI View)
        </button>
        <button type="button" id="btn-refresh" class="btn btn-outline" onclick="refreshLiveData()">
          🔄 Refresh Live from Portal
        </button>
      </div>
    </section>

    <!-- KPI Summary Cards -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-title">Total Mandals</span>
        <div class="kpi-val" id="kpi-mandals">--</div>
        <div class="kpi-sub" id="kpi-district-name">Khammam District</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Total Gram Panchayats</span>
        <div class="kpi-val" id="kpi-gps">--</div>
        <div class="kpi-sub" id="kpi-assessments">-- Assessments</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Total Demand</span>
        <div class="kpi-val" id="kpi-demand">₹ --</div>
        <div class="kpi-sub" id="kpi-demand-breakdown">Arrear: -- | Current: --</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Total Collection</span>
        <div class="kpi-val" id="kpi-collection">₹ --</div>
        <div class="kpi-sub" id="kpi-coll-breakdown">Arrear: -- | Current: --</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-title">Balance Outstanding</span>
        <div class="kpi-val" id="kpi-balance">₹ --</div>
        <div class="kpi-sub" id="kpi-bal-breakdown">Arrear: -- | Current: --</div>
      </div>
      <div class="kpi-card kpi-highlight">
        <span class="kpi-title">Overall Collection %</span>
        <div class="kpi-val" id="kpi-pct">-- %</div>
        <div class="kpi-sub">Target: 100%</div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-wrap">
      <button type="button" class="tab-item active" onclick="switchTab('visual')" id="tab-btn-visual">
        📊 Executive Visual Report (Power BI View)
      </button>
      <button type="button" class="tab-item" onclick="switchTab('pdf')" id="tab-btn-pdf">
        📄 Official Landscape PDF Viewer
      </button>
      <button type="button" class="tab-item" onclick="switchTab('abstract')">
        🏛️ Mandal Wise Consolidated Abstract
      </button>
      <button type="button" class="tab-item" onclick="switchTab('detail')">
        📋 Gram Panchayat Wise Detailed DCB Table
      </button>
    </div>

    <!-- PANE 1: Embedded PDF Viewer -->
    <div id="pane-pdf" class="tab-pane">
      <div class="pdf-viewer-card">
        <div class="pdf-toolbar" id="pdf-toolbar" style="display: none;">
          <div class="pdf-toolbar-info">
            Official Departmental Landscape Format · Generated for <span id="pdf-dist-label">--</span>
          </div>
          <div style="display:flex; gap:8px;">
            <a id="btn-fullscreen-pdf" href="#" target="_blank" class="btn btn-pdf" style="padding:6px 12px; font-size:0.82rem;">
              ↗ Open in Full Screen / Native Viewer
            </a>
            <button type="button" class="btn btn-outline" style="padding:6px 12px; font-size:0.82rem;" onclick="reloadPdfViewer()">
              🔄 Reload PDF
            </button>
          </div>
        </div>
        <div id="pdf-placeholder" style="text-align:center; padding:70px 20px; color:#557267;">
          <div style="font-size:3.2rem; margin-bottom:12px;">🏛️</div>
          <h3 style="font-size:1.3rem; font-weight:700; margin-bottom:8px; color:#173b2b;">Please Select a District</h3>
          <p style="max-width:520px; margin:0 auto; font-size:0.92rem; line-height:1.5; color:#557267;">
            Select a <strong>District</strong> from the controls above (and optionally a specific <strong>Mandal</strong>), then click the <strong>⚡ Generate Report</strong> button to load the official PDF report and consolidated DCB data.
          </p>
        </div>
        <iframe id="pdf-frame" class="pdf-iframe" style="display:none;" src="about:blank"></iframe>
      </div>
    </div>

    <!-- PANE 2: Executive Visual Report (Power BI Canvas) -->
    <div id="pane-visual" class="tab-pane active">
      <div class="pbi-container">
        <!-- Power BI Toolbar Strip -->
        <div class="pbi-toolbar-bar">
          <div style="display:flex; align-items:center; gap:10px;">
            <span class="pbi-badge">Power BI Architecture</span>
            <span id="pbi-view-indicator" style="font-size:0.86rem; font-weight:750; color:#1e293b;">--</span>
          </div>
          <div class="pbi-header-tools" style="display:flex; align-items:center; gap:8px;">
            <button type="button" class="btn btn-primary" style="padding:6px 14px; font-size:0.82rem; display:flex; align-items:center; gap:6px;" onclick="downloadPowerBiPdf(this)">
              📥 Download Power BI PDF
            </button>
            <button type="button" class="btn btn-outline" style="padding:6px 12px; font-size:0.82rem;" onclick="window.print()">
              🖨️ Print Dashboard
            </button>
          </div>
        </div>

        <!-- Initial Placeholder when District is not generated yet -->
        <div id="pbi-placeholder" style="text-align:center; padding:70px 20px; color:#557267;">
          <div style="font-size:3.2rem; margin-bottom:12px;">📊</div>
          <h3 style="font-size:1.3rem; font-weight:700; margin-bottom:8px; color:#173b2b;">Please Select a District</h3>
          <p style="max-width:520px; margin:0 auto; font-size:0.92rem; line-height:1.5; color:#557267;">
            Select a District (and optionally a Mandal) above, then click <strong>⚡ Generate Report</strong> to load the full Power BI style interactive report and charts.
          </p>
        </div>

        <!-- Exportable Power BI Canvas Container -->
        <div id="pbi-canvas-export" style="display:none; background:#ffffff; border-radius:8px; padding:8px;">
          
          <!-- ======================================================== -->
          <!-- LAYOUT 1: DISTRICT LEVEL REPORT (Page 1 of Power BI)   -->
          <!-- ======================================================== -->
          <div id="pbi-district-view" style="display:none;">
            <!-- Header Banner (Soft Blue #D2E3FC) -->
            <div class="pbi-banner-district">
              <div class="pbi-banner-district-title" id="pbi-dist-banner-title">
                DEMAND, COLLECTION, BALANCE OF KHAMMAM DISTRICT
              </div>
            </div>

            <!-- Top Row: Mandal Table (Left) + Clustered DCB by Mandal (Right) -->
            <div class="pbi-row" style="display:flex; gap:12px; margin-top:10px;">
              <!-- Left: Mandal DCB Summary Table with Data Bars -->
              <div class="pbi-card" style="flex:1 1 48%; min-width:0; padding:10px;">
                <div class="pbi-table-wrap" style="max-height:295px; overflow-y:auto;">
                  <table class="pbi-table" id="pbi-dist-table">
                    <thead>
                      <tr>
                        <th style="width:23%;">Mandal Name</th>
                        <th class="num-cell" style="width:13%;">No of GPs</th>
                        <th class="num-cell" style="width:16%;">Demand</th>
                        <th class="num-cell" style="width:16%;">Collection</th>
                        <th class="num-cell" style="width:16%;">Balance</th>
                        <th class="center-cell" style="width:12%; white-space:nowrap; cursor:pointer;" onclick="togglePbiSort('percentage')">%</th>
                      </tr>
                    </thead>
                    <tbody id="pbi-dist-table-body">
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- Right: Demand, Collection and Balance by Mandal Clustered Column Chart -->
              <div class="pbi-card" style="flex:1 1 52%; min-width:0; padding:10px;">
                <div class="pbi-card-title">Demand, Collection and Balance by Mandal</div>
                <div style="flex:1; min-height:285px; max-height:285px; position:relative;">
                  <canvas id="chart-dist-clustered"></canvas>
                </div>
              </div>
            </div>

            <!-- Bottom Row: Percentage Ranking (Left) + Donut (Mid) + Gauge (Right) -->
            <div class="pbi-row" style="display:flex; gap:12px; margin-top:10px;">
              <!-- Bottom Left: PERCENTAGE OF COLLECTION BY MANDAL -->
              <div class="pbi-card" style="flex:1 1 45%; min-width:0; padding:10px;">
                <div class="pbi-card-title">PERCENTAGE OF COLLECTION BY MANDAL</div>
                <div style="flex:1; min-height:215px; max-height:215px; position:relative;">
                  <canvas id="chart-dist-ranking"></canvas>
                </div>
              </div>

              <!-- Bottom Middle: DCB Breakdown Donut -->
              <div class="pbi-card" style="flex:1 1 27%; min-width:0; padding:10px; align-items:center; justify-content:center;">
                <div style="flex:1; min-height:215px; max-height:215px; width:100%; display:flex; align-items:center; justify-content:center; position:relative;">
                  <canvas id="chart-dist-donut"></canvas>
                </div>
              </div>

              <!-- Bottom Right: DISTRICT TAX COLLECTION % Gauge -->
              <div class="pbi-card" style="flex:1 1 28%; min-width:0; padding:10px; align-items:center; justify-content:center;">
                <div style="color:#DC2626; font-weight:850; font-size:1.0rem; margin-bottom:4px; text-align:center; letter-spacing:0.02em;">
                  DISTRICT TAX COLLECTION %
                </div>
                <div style="width:100%; max-width:230px; margin:0 auto; text-align:center;">
                  <svg id="svg-dist-gauge" viewBox="0 0 200 135" class="gauge-svg"></svg>
                </div>
              </div>
            </div>
          </div>

          <!-- ======================================================== -->
          <!-- LAYOUT 2: MANDAL LEVEL REPORT (Pages 2-21 of Power BI) -->
          <!-- ======================================================== -->
          <div id="pbi-mandal-view" style="display:none;">
            <!-- Header Banner (Soft Yellow #FEF9C3 with Red Title & Slicer) -->
            <div class="pbi-banner-mandal">
              <div class="pbi-banner-mandal-title" id="pbi-mandal-banner-title">
                DEMAND - COLLECTION - BALANCE OF BONAKAL MANDAL
              </div>
              <div class="pbi-slicer-container">
                <select id="pbi-mandal-slicer-select" class="pbi-slicer-select" onchange="onPbiMandalSlicerSelect(this.value)">
                  <!-- Options filled dynamically -->
                </select>
              </div>
            </div>

            <!-- Two-Column Layout (38% Left / 62% Right) -->
            <div class="pbi-row" style="display:flex; gap:12px; margin-top:10px;">
              <!-- Left Column: GP Table (Top) + MANDAL % Gauge (Bottom) -->
              <div style="flex:1 1 38%; min-width:0; display:flex; flex-direction:column; gap:12px;">
                <!-- GP DCB Table with Data Bars -->
                <div class="pbi-card" style="padding:10px;">
                  <div class="pbi-table-wrap" style="max-height:310px; overflow-y:auto;">
                    <table class="pbi-table" id="pbi-mandal-table">
                      <thead>
                        <tr>
                          <th style="width:30%;">Panchayat</th>
                          <th class="num-cell" style="width:18%;">Demand</th>
                          <th class="num-cell" style="width:18%;">Collection</th>
                          <th class="num-cell" style="width:18%;">Balance</th>
                          <th class="center-cell" style="width:14%; white-space:nowrap; cursor:pointer;" onclick="togglePbiMandalSort('percentage')">%</th>
                        </tr>
                      </thead>
                      <tbody id="pbi-mandal-table-body">
                      </tbody>
                    </table>
                  </div>
                </div>

                <!-- MANDAL % Gauge -->
                <div class="pbi-card" style="padding:10px; align-items:center; justify-content:center;">
                  <div style="color:#0F172A; font-weight:850; font-size:1.0rem; margin-bottom:4px; text-align:center; letter-spacing:0.02em;">
                    MANDAL %
                  </div>
                  <div style="width:100%; max-width:230px; margin:0 auto; text-align:center;">
                    <svg id="svg-mandal-gauge" viewBox="0 0 200 135" class="gauge-svg"></svg>
                  </div>
                </div>
              </div>

              <!-- Right Column: GP Wise Collection % (Top) + Panchayat wise DCB (Bottom) -->
              <div style="flex:1 1 62%; min-width:0; display:flex; flex-direction:column; gap:12px;">
                <!-- Top Chart: GP Wise Collection percentage -->
                <div class="pbi-card" style="padding:10px;">
                  <div class="pbi-card-title">GP Wise Collection percentage</div>
                  <div style="flex:1; min-height:230px; max-height:230px; position:relative;">
                    <canvas id="chart-mandal-ranking"></canvas>
                  </div>
                </div>

                <!-- Bottom Chart: Panchayat wise Demand, Collection and Balance -->
                <div class="pbi-card" style="padding:10px;">
                  <div class="pbi-card-title">Panchayat wise Demand, Collection and Balance</div>
                  <div style="flex:1; min-height:240px; max-height:240px; position:relative;">
                    <canvas id="chart-mandal-dcb"></canvas>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- PANE 2: Mandal Abstract Table -->
    <div id="pane-abstract" class="tab-pane">
      <div class="table-card">
        <div class="table-header-row">
          <h2 class="table-title">Mandal Wise DCB Abstract (Consolidated Summary)</h2>
          <span style="font-size:0.86rem; color:#557267;" id="mandal-count-label">-- Mandals</span>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th class="center-cell" style="width:50px;">S.No</th>
              <th>Mandal Name</th>
              <th class="num-cell">Total GPs</th>
              <th class="num-cell">Assessments</th>
              <th class="num-cell">Demand Arrear (₹)</th>
              <th class="num-cell">Demand Current (₹)</th>
              <th class="num-cell">Demand Total (₹)</th>
              <th class="num-cell">Collection Arrear (₹)</th>
              <th class="num-cell">Collection Current (₹)</th>
              <th class="num-cell">Collection Total (₹)</th>
              <th class="num-cell">Balance Arrear (₹)</th>
              <th class="num-cell">Balance Current (₹)</th>
              <th class="num-cell">Balance Total (₹)</th>
              <th class="center-cell">% Coll</th>
            </tr>
          </thead>
          <tbody id="mandal-table-body">
            <tr><td colspan="14" class="center-cell" style="padding:28px; color:#557267;">Please select a District and click <strong>⚡ Generate Report</strong> to display Mandal summary.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- PANE 3: Gram Panchayat Detail Table -->
    <div id="pane-detail" class="tab-pane">
      <div class="table-card">
        <div class="table-header-row">
          <h2 class="table-title">Gram Panchayat Wise Detailed DCB Table</h2>
          <span style="font-size:0.86rem; color:#557267;" id="gp-count-label">-- GPs found</span>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th class="center-cell" style="width:45px;">S.No</th>
              <th>Mandal</th>
              <th>Gram Panchayat</th>
              <th class="num-cell">Assessments</th>
              <th class="num-cell">Demand Arrear (₹)</th>
              <th class="num-cell">Demand Current (₹)</th>
              <th class="num-cell">Demand Total (₹)</th>
              <th class="num-cell">Collection Arrear (₹)</th>
              <th class="num-cell">Collection Current (₹)</th>
              <th class="num-cell">Collection Total (₹)</th>
              <th class="num-cell">Balance Total (₹)</th>
              <th class="center-cell">% Coll</th>
            </tr>
          </thead>
          <tbody id="gp-table-body">
            <tr><td colspan="12" class="center-cell" style="padding:28px; color:#557267;">Please select a District and click <strong>⚡ Generate Report</strong> to display Gram Panchayat details.</td></tr>
          </tbody>
        </table>

        <div class="pagination-bar">
          <span id="page-info">Showing 0-0 of 0</span>
          <div class="pagination-btns">
            <button type="button" class="page-btn" id="btn-prev" onclick="changePage(-1)">← Previous</button>
            <button type="button" class="page-btn" id="btn-next" onclick="changePage(1)">Next →</button>
          </div>
        </div>
      </div>
    </div>
  </main>

  <!-- Floating Mobile Download Notification Center -->
  <div id="download-toast-container" class="download-toast-container" style="display:none;" role="alert" aria-live="assertive">
    <div class="download-toast-card">
      <div class="download-toast-header">
        <div id="download-toast-icon" class="download-toast-icon-wrap loading">
          <div class="toast-spinner"></div>
        </div>
        <div class="download-toast-body">
          <div id="download-toast-title" class="download-toast-title">Downloading Report...</div>
          <div id="download-toast-subtitle" class="download-toast-subtitle">Preparing file, please wait...</div>
        </div>
        <button type="button" class="download-toast-close" onclick="dismissDownloadToast()" aria-label="Close notification">&times;</button>
      </div>
      <div id="download-toast-actions" class="download-toast-actions" style="display:none;">
        <button type="button" id="download-toast-open-btn" class="download-toast-btn-open">
          <span>👁️</span> Open / View PDF
        </button>
        <button type="button" class="download-toast-btn-dismiss" onclick="dismissDownloadToast()">
          Dismiss
        </button>
      </div>
      <div id="download-toast-progress-bar" class="download-toast-progress loading"></div>
    </div>
  </div>

  <footer>
    Executive Analytics &amp; Monitoring Portal Owned, maintained and updated by DPM Khammam
  </footer>

  <script>
    let allRecords = [];
    let filteredRecords = [];
    let mandalAbstract = [];
    let currentPage = 1;
    const PAGE_SIZE = 50;

    function formatInr(val) {
      if (val === null || val === undefined || isNaN(val)) return '0';
      const n = Math.round(Number(val));
      return n.toLocaleString('en-IN');
    }

    function getGradientColor(pct) {
      pct = Math.max(0, Math.min(100, Number(pct) || 0));
      let r, g, b;
      if (pct <= 50) {
        const t = pct / 50;
        r = Math.round(220 + t * (234 - 220));
        g = Math.round(38 + t * (179 - 38));
        b = Math.round(38 + t * (8 - 38));
      } else {
        const t = (pct - 50) / 50;
        r = Math.round(234 + t * (22 - 234));
        g = Math.round(179 + t * (163 - 179));
        b = Math.round(8 + t * (74 - 8));
      }
      const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      const textCol = lum > 0.55 ? '#000000' : '#FFFFFF';
      return { bg: `rgb(${r}, ${g}, ${b})`, text: textCol };
    }

    function getPbiHeatmapStyle(pctVal) {
      const p = Math.max(0, Math.min(100, Number(pctVal) || 0));
      const cMin = [216, 59, 1];   // #D83B01
      const cMid = [233, 173, 9];  // #E9AD09
      const cMax = [16, 124, 65];  // #107C41
      let rgb;
      if (p <= 50) {
        const t = p / 50;
        rgb = [
          Math.round(cMin[0] + (cMid[0] - cMin[0]) * t),
          Math.round(cMin[1] + (cMid[1] - cMin[1]) * t),
          Math.round(cMin[2] + (cMid[2] - cMin[2]) * t)
        ];
      } else {
        const t = (p - 50) / 50;
        rgb = [
          Math.round(cMid[0] + (cMax[0] - cMid[0]) * t),
          Math.round(cMid[1] + (cMax[1] - cMid[1]) * t),
          Math.round(cMid[2] + (cMax[2] - cMid[2]) * t)
        ];
      }
      const bg = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
      const lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2];
      const fg = lum >= 138 ? '#000000' : '#FFFFFF';
      return { bg, fg, val: Math.round(p) };
    }

    function renderPctCell(pctVal) {
      const hm = getPbiHeatmapStyle(pctVal);
      return `<div class="pbi-pct-heatmap-badge" style="background:${hm.bg}; color:${hm.fg};">${hm.val}%</div>`;
    }

    function switchTab(tab) {
      document.querySelectorAll('.tab-item').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      const activeBtn = Array.from(document.querySelectorAll('.tab-item')).find(b => b.getAttribute('onclick')?.includes(`'${tab}'`));
      if (activeBtn) activeBtn.classList.add('active');
      const targetPane = document.getElementById('pane-' + tab);
      if (targetPane) targetPane.classList.add('active');

      if (tab === 'visual') {
        if (chartClustered) chartClustered.resize();
        if (chartRanking) chartRanking.resize();
        if (chartPie) chartPie.resize();
      }
    }

    function openVisualReport() {
      switchTab('visual');
      const target = document.getElementById('pane-visual');
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    function reloadPdfViewer() {
      const dist = document.getElementById('district-select').value;
      if (!dist) return;
      const mandal = document.getElementById('mandal-select').value;
      const encDist = encodeURIComponent(dist);
      const isAllMandals = !mandal || mandal === 'all';
      const mandalParam = isAllMandals ? '' : `&mandal=${encodeURIComponent(mandal)}`;
      const frame = document.getElementById('pdf-frame');
      frame.src = `/api/tax/report.pdf?district=${encDist}${mandalParam}&t=${Date.now()}`;
    }

    // Load available districts from API (no auto-selection)
    async function initDistricts() {
      try {
        const res = await fetch('/api/tax/districts');
        const districts = await res.json();
        const sel = document.getElementById('district-select');
        sel.innerHTML = '<option value="" selected disabled>-- Select District --</option>';

        districts.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d.district;
          opt.textContent = `${d.district} (${d.gps_count} GPs)`;
          sel.appendChild(opt);
        });

        const mandalSel = document.getElementById('mandal-select');
        mandalSel.innerHTML = '<option value="all">-- Select District First --</option>';
        mandalSel.disabled = true;

        showStatus('Please select a District and click Generate Report to begin.', 'info');
      } catch (err) {
        showStatus('Error loading districts: ' + err.message, 'error');
      }
    }

    function getTodayDateStr() {
      const now = new Date();
      const d = String(now.getDate()).padStart(2, '0');
      const m = String(now.getMonth() + 1).padStart(2, '0');
      const y = now.getFullYear();
      return `${d}-${m}-${y}`;
    }

    function updateActionLinks() {
      const dist = document.getElementById('district-select').value;
      if (!dist) return;
      const mandal = document.getElementById('mandal-select').value;
      const encDist = encodeURIComponent(dist);
      const isAllMandals = !mandal || mandal === 'all';
      const mandalParam = isAllMandals ? '' : `&mandal=${encodeURIComponent(mandal)}`;

      const pdfUrl = `/api/tax/report.pdf?district=${encDist}${mandalParam}`;
      const pdfDlUrl = `/api/tax/download-pdf?district=${encDist}${mandalParam}`;
      const excelUrl = `/api/tax/download?district=${encDist}${mandalParam}&format=xlsx`;
      const csvUrl = `/api/tax/download?district=${encDist}${mandalParam}&format=csv`;

      const viewPdfBtn = document.getElementById('btn-view-pdf');
      if (viewPdfBtn) viewPdfBtn.href = pdfUrl;
      const dlPdfBtn = document.getElementById('btn-download-pdf');
      if (dlPdfBtn) {
        dlPdfBtn.onclick = (e) => {
          e.preventDefault();
          const dateStr = getTodayDateStr();
          const fname = isAllMandals ? `${dist}_House_Tax_DCB_Report_${dateStr}.pdf` : `${dist}_${mandal}_House_Tax_DCB_Report_${dateStr}.pdf`;
          const lbl = isAllMandals ? `Official DCB PDF (${dist} District)` : `Official DCB PDF (${mandal} Mandal)`;
          triggerManagedDownload(pdfDlUrl, fname, lbl, dlPdfBtn);
        };
      }
      const dlExcelBtn = document.getElementById('btn-download-excel');
      if (dlExcelBtn) {
        dlExcelBtn.onclick = (e) => {
          e.preventDefault();
          const dateStr = getTodayDateStr();
          triggerManagedDownload(excelUrl, `${dist}_House_Tax_DCB_${dateStr}.xlsx`, 'Consolidated Excel', dlExcelBtn);
        };
      }
      const dlCsvBtn = document.getElementById('btn-download-csv');
      if (dlCsvBtn) dlCsvBtn.href = csvUrl;
      const fsPdfBtn = document.getElementById('btn-fullscreen-pdf');
      if (fsPdfBtn) fsPdfBtn.href = pdfUrl;

      const label = isAllMandals ? `${dist} District` : `${mandal} Mandal (${dist} District)`;
      document.getElementById('pdf-dist-label').textContent = label;
      document.getElementById('pdf-frame').src = pdfUrl;
    }

    async function onDistrictChanged() {
      const dist = document.getElementById('district-select').value;
      const mandalSel = document.getElementById('mandal-select');
      if (!dist) {
        mandalSel.innerHTML = '<option value="all">-- Select District First --</option>';
        mandalSel.disabled = true;
        return;
      }
      mandalSel.disabled = false;
      await loadMandals(dist);
      showStatus(`Selected ${dist} District. Click '⚡ Generate Report' to view report and analytics.`, 'info');
    }

    async function onGenerateReportClick() {
      const dist = document.getElementById('district-select').value;
      if (!dist) {
        showStatus('Please select a District first.', 'error');
        document.getElementById('district-select').focus();
        return;
      }
      const mandal = document.getElementById('mandal-select').value;

      const newUrl = new URL(window.location);
      newUrl.searchParams.set('district', dist);
      if (mandal && mandal !== 'all') {
        newUrl.searchParams.set('mandal', mandal);
      } else {
        newUrl.searchParams.delete('mandal');
      }
      window.history.replaceState({}, '', newUrl);

      // Reveal action toolbar & PDF frame & Visual Analytics content
      const actionsBar = document.getElementById('actions-bar');
      if (actionsBar) actionsBar.style.display = 'flex';

      const pdfToolbar = document.getElementById('pdf-toolbar');
      if (pdfToolbar) pdfToolbar.style.display = 'flex';
      const placeholder = document.getElementById('pdf-placeholder');
      if (placeholder) placeholder.style.display = 'none';
      const frame = document.getElementById('pdf-frame');
      if (frame) frame.style.display = 'block';

      const pbiPlaceholder = document.getElementById('pbi-placeholder');
      if (pbiPlaceholder) pbiPlaceholder.style.display = 'none';
      const pbiCanvasExport = document.getElementById('pbi-canvas-export');
      if (pbiCanvasExport) pbiCanvasExport.style.display = 'block';

      updateActionLinks();
      await loadData(dist);
    }

    async function loadMandals(dist) {
      try {
        const res = await fetch(`/api/tax/mandals?district=${encodeURIComponent(dist)}`);
        const mandals = await res.json();
        const sel = document.getElementById('mandal-select');
        sel.innerHTML = '<option value="all">-- All Mandals (Consolidated) --</option>';
        mandals.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m;
          opt.textContent = m;
          sel.appendChild(opt);
        });
      } catch (err) {
        console.error('Error loading mandals', err);
      }
    }

    async function loadData(dist) {
      try {
        showStatus(`Loading consolidated data for ${dist}...`, 'info');
        const mandal = document.getElementById('mandal-select').value;
        const res = await fetch(`/api/tax/data?district=${encodeURIComponent(dist)}&mandal=${encodeURIComponent(mandal)}`);
        const data = await res.json();

        // Summary KPI
        const s = data.summary;
        document.getElementById('kpi-mandals').textContent = s.total_mandals;
        document.getElementById('kpi-district-name').textContent = s.district + (s.mandal !== 'All Mandals' ? ` · ${s.mandal}` : ' District');
        document.getElementById('kpi-gps').textContent = s.total_gps;
        document.getElementById('kpi-assessments').textContent = formatInr(s.total_assessments) + ' Assessments';
        document.getElementById('kpi-demand').textContent = '₹ ' + formatInr(s.total_demand);
        document.getElementById('kpi-demand-breakdown').textContent = `Arrear: ₹ ${formatInr(s.demand_arrear)} | Current: ₹ ${formatInr(s.demand_current)}`;
        document.getElementById('kpi-collection').textContent = '₹ ' + formatInr(s.total_collection);
        document.getElementById('kpi-coll-breakdown').textContent = `Arrear: ₹ ${formatInr(s.collection_arrear)} | Current: ₹ ${formatInr(s.collection_current)}`;
        document.getElementById('kpi-balance').textContent = '₹ ' + formatInr(s.total_balance);
        document.getElementById('kpi-bal-breakdown').textContent = `Arrear: ₹ ${formatInr(s.balance_arrear)} | Current: ₹ ${formatInr(s.balance_current)}`;
        document.getElementById('kpi-pct').textContent = s.overall_percentage + ' %';

        allRecords = data.records || [];
        mandalAbstract = data.mandal_abstract || [];
        filteredRecords = [...allRecords];

        renderMandalTable(mandalAbstract, s);
        applyFilter();
        renderExecutiveVisualReport(data);
        hideStatus();
      } catch (err) {
        showStatus('Error fetching data: ' + err.message, 'error');
      }
    }

    const pbiDataLabelsPlugin = {
      id: 'pbiDataLabels',
      afterDatasetsDraw(chart) {
        const { ctx } = chart;
        chart.data.datasets.forEach((dataset, i) => {
          if (dataset.hideDataLabels) return;
          const meta = chart.getDatasetMeta(i);
          meta.data.forEach((bar, index) => {
            const val = dataset.data[index];
            if (val === undefined || val === null) return;
            ctx.save();
            ctx.fillStyle = '#0f172a';
            ctx.font = 'bold 9px system-ui, -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(String(val), bar.x, bar.y - 3);
            ctx.restore();
          });
        });
      }
    };

    function drawPbiGauge(svgId, percentage, titleText, titleColor, minText, maxText) {
      const p = Math.max(0, Math.min(100, Number(percentage) || 0));
      const r = 75;
      const semiCirc = Math.PI * r; // ~235.62
      const offset = semiCirc * (1.0 - p / 100.0);

      const svg = document.getElementById(svgId);
      if (!svg) return;

      svg.innerHTML = `
        <!-- Background Track -->
        <path d="M 25 110 A 75 75 0 0 1 175 110" fill="none" stroke="#E9EDF2" stroke-width="22" stroke-linecap="butt"/>
        <!-- Blue Progress Arc -->
        <path d="M 25 110 A 75 75 0 0 1 175 110" fill="none" stroke="#0078D4" stroke-width="22" stroke-linecap="butt"
              stroke-dasharray="235.62" stroke-dashoffset="${offset.toFixed(2)}"/>
        <!-- Center Percentage -->
        <text x="100" y="104" font-size="28" font-weight="900" fill="#2E0854" font-family="system-ui, -apple-system, sans-serif" text-anchor="middle">
          ${p.toFixed(2)}
        </text>
        <!-- Range Labels -->
        <text x="25" y="128" font-size="11" font-weight="700" fill="#1E293B" font-family="system-ui, -apple-system, sans-serif" text-anchor="middle">
          ${minText}
        </text>
        <text x="175" y="128" font-size="11" font-weight="700" fill="#1E293B" font-family="system-ui, -apple-system, sans-serif" text-anchor="middle">
          ${maxText}
        </text>
      `;
    }

    let chartDistClustered = null;
    let chartDistRanking = null;
    let chartDistDonut = null;
    let chartMandalRanking = null;
    let chartMandalDcb = null;

    function onPbiMandalSlicerSelect(val) {
      const mainSel = document.getElementById('mandal-select');
      if (mainSel) mainSel.value = val;
      const dist = document.getElementById('district-select').value;
      updateActionLinks();
      loadData(dist);
    }

    let _currentBlobUrl = null;
    let _toastTimer = null;

    function requestNotificationPermission() {
      if ('Notification' in window && Notification.permission === 'default') {
        try { Notification.requestPermission(); } catch(e){}
      }
    }

    function dismissDownloadToast() {
      const container = document.getElementById('download-toast-container');
      const card = container ? container.querySelector('.download-toast-card') : null;
      if (!container || !card) return;
      card.classList.add('toast-exit');
      setTimeout(() => {
        container.style.display = 'none';
        card.classList.remove('toast-exit');
      }, 260);
      if (_toastTimer) {
        clearTimeout(_toastTimer);
        _toastTimer = null;
      }
    }

    async function triggerManagedDownload(url, defaultFilename, friendlyLabel, triggerBtn = null) {
      requestNotificationPermission();

      const container = document.getElementById('download-toast-container');
      const iconWrap = document.getElementById('download-toast-icon');
      const titleEl = document.getElementById('download-toast-title');
      const subtitleEl = document.getElementById('download-toast-subtitle');
      const actionsEl = document.getElementById('download-toast-actions');
      const openBtn = document.getElementById('download-toast-open-btn');
      const progressBar = document.getElementById('download-toast-progress-bar');

      if (_toastTimer) {
        clearTimeout(_toastTimer);
        _toastTimer = null;
      }

      container.style.display = 'block';
      const card = container.querySelector('.download-toast-card');
      if (card) card.classList.remove('toast-exit');

      iconWrap.className = 'download-toast-icon-wrap loading';
      iconWrap.innerHTML = '<div class="toast-spinner"></div>';
      titleEl.textContent = 'Downloading ' + (friendlyLabel || 'Report') + '...';
      subtitleEl.textContent = 'Preparing ' + defaultFilename + '...';
      actionsEl.style.display = 'none';
      progressBar.style.display = 'block';
      progressBar.className = 'download-toast-progress loading';

      showStatus(`Preparing and downloading ${defaultFilename}... Please wait.`, 'info');

      let origBtnHtml = '';
      if (triggerBtn) {
        triggerBtn.disabled = true;
        origBtnHtml = triggerBtn.innerHTML;
        triggerBtn.innerHTML = '⏳ Downloading...';
      }

      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Server returned HTTP ${response.status}`);
        }

        let finalFilename = defaultFilename;
        const disposition = response.headers.get('Content-Disposition') || '';
        const match = /filename\\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
        if (match && match[1]) {
          finalFilename = decodeURIComponent(match[1]).trim();
        }

        const blob = await response.blob();

        if (_currentBlobUrl) {
          try { URL.revokeObjectURL(_currentBlobUrl); } catch(e){}
        }
        _currentBlobUrl = URL.createObjectURL(blob);

        // Trigger file download to device Downloads folder
        const link = document.createElement('a');
        link.href = _currentBlobUrl;
        link.download = finalFilename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Haptic vibration feedback on mobile
        if (navigator.vibrate) {
          try { navigator.vibrate([120, 60, 120]); } catch(e){}
        }

        // Web Notification API
        if ('Notification' in window && Notification.permission === 'granted') {
          try {
            new Notification('Download Complete', {
              body: `${finalFilename} has been saved to your device.`,
              icon: '/favicon.ico'
            });
          } catch(e){}
        }

        // Success state in floating toast
        iconWrap.className = 'download-toast-icon-wrap success';
        iconWrap.innerHTML = '✅';
        titleEl.textContent = 'Download Complete!';
        subtitleEl.textContent = `${finalFilename} saved to Downloads.`;
        progressBar.style.display = 'none';

        showStatus(`✅ ${finalFilename} downloaded successfully!`, 'success');

        actionsEl.style.display = 'flex';
        if (finalFilename.toLowerCase().endsWith('.pdf')) {
          openBtn.style.display = 'flex';
          openBtn.onclick = function() {
            window.open(_currentBlobUrl, '_blank');
          };
        } else {
          openBtn.style.display = 'none';
        }

        _toastTimer = setTimeout(() => {
          dismissDownloadToast();
          hideStatus();
        }, 14000);

      } catch (err) {
        console.error('Download failed:', err);
        iconWrap.className = 'download-toast-icon-wrap error';
        iconWrap.innerHTML = '❌';
        titleEl.textContent = 'Download Failed';
        subtitleEl.textContent = err.message || 'Error downloading file. Please try again.';
        progressBar.style.display = 'none';
        actionsEl.style.display = 'flex';
        openBtn.style.display = 'none';
        showStatus('Download failed: ' + (err.message || 'Network error'), 'error');

        _toastTimer = setTimeout(() => {
          dismissDownloadToast();
        }, 8000);
      } finally {
        if (triggerBtn) {
          triggerBtn.disabled = false;
          triggerBtn.innerHTML = origBtnHtml;
        }
      }
    }

    function downloadPowerBiPdf(triggerBtn = null) {
      const dist = document.getElementById('district-select').value;
      if (!dist) {
        showStatus('Please select a district and click Generate Report first.', 'error');
        return;
      }
      const mandal = document.getElementById('mandal-select').value;
      const isDistrictView = (mandal === 'all' || !mandal);
      const mandalParam = isDistrictView ? '' : `&mandal=${encodeURIComponent(mandal)}`;

      const dlUrl = `/api/tax/powerbi-report.pdf?district=${encodeURIComponent(dist)}${mandalParam}`;
      const dateStr = getTodayDateStr();
      const fname = isDistrictView ? `${dist}_PowerBI_DCB_Report_${dateStr}.pdf` : `${dist}_${mandal}_PowerBI_DCB_Report_${dateStr}.pdf`;
      const label = isDistrictView ? `Power BI Report (${dist} + All Mandals)` : `Power BI Report (${mandal} Mandal)`;

      const btn = triggerBtn || document.getElementById('btn-download-pbi-pdf');
      triggerManagedDownload(dlUrl, fname, label, btn);
    }

    let pbiSortAsc = true;
    function togglePbiSort() {
      if (!window._lastPbiData) return;
      pbiSortAsc = !pbiSortAsc;
      renderExecutiveVisualReport(window._lastPbiData);
    }

    let pbiMandalSortAsc = false; // default descending to show top GPs first like Image 2
    function togglePbiMandalSort() {
      if (!window._lastPbiData) return;
      pbiMandalSortAsc = !pbiMandalSortAsc;
      renderExecutiveVisualReport(window._lastPbiData);
    }

    function renderExecutiveVisualReport(data) {
      if (!data || !data.summary) return;
      window._lastPbiData = data;
      const s = data.summary;
      const dist = s.district || 'District';
      const mandal = s.mandal;
      const isDistrictView = (mandal === 'all' || mandal === 'All Mandals' || !mandal);

      const placeholder = document.getElementById('pbi-placeholder');
      if (placeholder) placeholder.style.display = 'none';
      const canvasExport = document.getElementById('pbi-canvas-export');
      if (canvasExport) canvasExport.style.display = 'block';

      const distView = document.getElementById('pbi-district-view');
      const mandalView = document.getElementById('pbi-mandal-view');
      const indicator = document.getElementById('pbi-view-indicator');

      if (isDistrictView) {
        // Show District View, Hide Mandal View
        if (distView) distView.style.display = 'block';
        if (mandalView) mandalView.style.display = 'none';
        if (indicator) indicator.textContent = `${dist} District DCB Overview (Mandal Abstract)`;

        const distTitle = document.getElementById('pbi-dist-banner-title');
        if (distTitle) distTitle.textContent = `DEMAND, COLLECTION, BALANCE OF ${dist.toUpperCase()} DISTRICT`;

        // 1. Populate District Summary Table (sortable)
        const distMandals = (data.mandal_abstract || []).map(m => ({
          name: m.mandal,
          gps: m.total_gps,
          demand: Number(m.demand_total) || 0,
          collection: Number(m.collection_total) || 0,
          balance: Number(m.balance_total) || 0,
          percentage: Number(m.percentage) || 0,
        })).sort((a, b) => pbiSortAsc ? a.percentage - b.percentage : b.percentage - a.percentage);

        let distTbodyHtml = '';
        distMandals.forEach(m => {
          const hm = getPbiHeatmapStyle(m.percentage);
          distTbodyHtml += `<tr>
            <td><strong>${m.name}</strong></td>
            <td class="num-cell">${m.gps}</td>
            <td class="num-cell">${formatInr(m.demand)}</td>
            <td class="num-cell" style="color:#107C41; font-weight:700;">${formatInr(m.collection)}</td>
            <td class="num-cell" style="color:#D83B01;">${formatInr(m.balance)}</td>
            <td class="pbi-pct-heatmap-cell" style="background:${hm.bg}; color:${hm.fg};">${hm.val}</td>
          </tr>`;
        });
        const totPct = Number(s.overall_percentage) || 0;
        const totHm = getPbiHeatmapStyle(totPct);
        distTbodyHtml += `<tr class="total-row" style="background:#F1F5F9; font-weight:800; border-top:2px solid #000000;">
          <td><strong>Total</strong></td>
          <td class="num-cell">${s.total_gps}</td>
          <td class="num-cell">${formatInr(s.total_demand)}</td>
          <td class="num-cell" style="color:#107C41;">${formatInr(s.total_collection)}</td>
          <td class="num-cell" style="color:#D83B01;">${formatInr(s.total_balance)}</td>
          <td class="pbi-pct-heatmap-cell" style="background:${totHm.bg}; color:${totHm.fg};">${totHm.val}</td>
        </tr>`;
        const tbodyDist = document.getElementById('pbi-dist-table-body');
        if (tbodyDist) tbodyDist.innerHTML = distTbodyHtml;

        // 2. Render District Gauge (DISTRICT TAX COLLECTION %)
        drawPbiGauge('svg-dist-gauge', totPct, 'DISTRICT TAX COLLECTION %', '#DC2626', '0', '100');

        // 3. Render District Charts with Chart.js
        if (typeof Chart !== 'undefined') {
          // Chart 1: Clustered DCB by Mandal
          const canvasClustered = document.getElementById('chart-dist-clustered');
          if (canvasClustered) {
            if (chartDistClustered) chartDistClustered.destroy();
            const mAlphabetical = [...distMandals].sort((a, b) => a.name.localeCompare(b.name));
            chartDistClustered = new Chart(canvasClustered.getContext('2d'), {
              type: 'bar',
              data: {
                labels: mAlphabetical.map(m => m.name),
                datasets: [
                  { label: 'Demand', data: mAlphabetical.map(m => m.demand), backgroundColor: '#0078D4', borderRadius: 2, hideDataLabels: true },
                  { label: 'Collection', data: mAlphabetical.map(m => m.collection), backgroundColor: '#107C41', borderRadius: 2, hideDataLabels: true },
                  { label: 'Balance', data: mAlphabetical.map(m => m.balance), backgroundColor: '#D83B01', borderRadius: 2, hideDataLabels: true },
                ]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'top', align: 'center', labels: { boxWidth: 10, font: { size: 10, weight: 'bold' } } },
                  tooltip: {
                    callbacks: { label: (ctx) => `${ctx.dataset.label}: ₹ ${formatInr(ctx.raw)}` }
                  }
                },
                scales: {
                  x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 55 } },
                  y: {
                    ticks: {
                      callback: (val) => val >= 10000000 ? (val / 10000000).toFixed(1) + ' Cr' : val >= 100000 ? (val / 100000).toFixed(1) + ' L' : val
                    }
                  }
                }
              }
            });
          }

          // Chart 2: PERCENTAGE OF COLLECTION BY MANDAL (Sorted Descending, with data labels)
          const canvasRanking = document.getElementById('chart-dist-ranking');
          if (canvasRanking) {
            if (chartDistRanking) chartDistRanking.destroy();
            const mRanking = [...distMandals].sort((a, b) => b.percentage - a.percentage);
            chartDistRanking = new Chart(canvasRanking.getContext('2d'), {
              type: 'bar',
              data: {
                labels: mRanking.map(m => m.name),
                datasets: [{
                  label: 'Collection %',
                  data: mRanking.map(m => Math.round(m.percentage)),
                  backgroundColor: '#0078D4',
                  borderRadius: 2
                }]
              },
              plugins: [pbiDataLabelsPlugin],
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { display: false },
                  tooltip: { callbacks: { label: (ctx) => `Collection: ${ctx.raw}%` } }
                },
                scales: {
                  x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 55 } },
                  y: { min: 0, max: 100, ticks: { callback: (val) => val + '%' } }
                }
              }
            });
          }

          // Chart 3: Overall DCB Breakdown Donut
          const canvasDonut = document.getElementById('chart-dist-donut');
          if (canvasDonut) {
            if (chartDistDonut) chartDistDonut.destroy();
            chartDistDonut = new Chart(canvasDonut.getContext('2d'), {
              type: 'doughnut',
              data: {
                labels: ['Demand', 'Collection', 'Balance'],
                datasets: [{
                  data: [s.total_demand, s.total_collection, s.total_balance],
                  backgroundColor: ['#002060', '#008000', '#ED7D31'],
                  borderWidth: 2,
                  borderColor: '#ffffff'
                }]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'top', labels: { boxWidth: 10, padding: 12, font: { size: 10, weight: 'bold' } } },
                  tooltip: {
                    callbacks: {
                      label: (ctx) => `${ctx.label}: ₹ ${formatInr(ctx.raw)}`
                    }
                  }
                },
                cutout: '54%'
              }
            });
          }
        }
      } else {
        // Show Mandal View, Hide District View
        if (distView) distView.style.display = 'none';
        if (mandalView) mandalView.style.display = 'block';
        if (indicator) indicator.textContent = `${dist} District · ${mandal} Mandal DCB Analytics`;

        const mandalTitle = document.getElementById('pbi-mandal-banner-title');
        if (mandalTitle) mandalTitle.textContent = `DEMAND - COLLECTION - BALANCE OF ${mandal.toUpperCase()} MANDAL`;

        // Populate Mandal Slicer dropdown
        const slicerSelect = document.getElementById('pbi-mandal-slicer-select');
        if (slicerSelect) {
          const mainMandalSelect = document.getElementById('mandal-select');
          if (mainMandalSelect) {
            slicerSelect.innerHTML = '';
            Array.from(mainMandalSelect.options).forEach(opt => {
              const o = document.createElement('option');
              o.value = opt.value;
              o.textContent = opt.value === 'all' ? '🏛️ All Mandals (District Overview)' : opt.textContent;
              if (opt.value === mandal) o.selected = true;
              slicerSelect.appendChild(o);
            });
          }
        }

        // 1. Populate Mandal GP Table (sortable, default descending by Collection % matching Image 2)
        const gpRecords = (data.records || []).map(r => ({
          name: r.panchayat,
          demand: Number(r.demand_total) || 0,
          collection: Number(r.collection_total) || 0,
          balance: Number(r.balance_total) || 0,
          percentage: Number(r.calc_percentage !== undefined ? r.calc_percentage : r.percentage) || 0
        })).sort((a, b) => pbiMandalSortAsc ? a.percentage - b.percentage : b.percentage - a.percentage);

        let mandalTbodyHtml = '';
        gpRecords.forEach(gp => {
          const hm = getPbiHeatmapStyle(gp.percentage);
          mandalTbodyHtml += `<tr>
            <td><strong>${gp.name}</strong></td>
            <td class="num-cell">${formatInr(gp.demand)}</td>
            <td class="num-cell" style="color:#107C41; font-weight:700;">${formatInr(gp.collection)}</td>
            <td class="num-cell" style="color:#D83B01;">${formatInr(gp.balance)}</td>
            <td class="pbi-pct-heatmap-cell" style="background:${hm.bg}; color:${hm.fg};">${hm.val}</td>
          </tr>`;
        });
        const mTotPct = Number(s.overall_percentage) || 0;
        const mTotHm = getPbiHeatmapStyle(mTotPct);
        mandalTbodyHtml += `<tr class="total-row" style="background:#F1F5F9; font-weight:800; border-top:2px solid #000000;">
          <td><strong>Total</strong></td>
          <td class="num-cell">${formatInr(s.total_demand)}</td>
          <td class="num-cell" style="color:#107C41;">${formatInr(s.total_collection)}</td>
          <td class="num-cell" style="color:#D83B01;">${formatInr(s.total_balance)}</td>
          <td class="pbi-pct-heatmap-cell" style="background:${mTotHm.bg}; color:${mTotHm.fg};">${mTotHm.val}</td>
        </tr>`;
        const tbodyMandal = document.getElementById('pbi-mandal-table-body');
        if (tbodyMandal) tbodyMandal.innerHTML = mandalTbodyHtml;

        // 2. Render Mandal Gauge (MANDAL %)
        drawPbiGauge('svg-mandal-gauge', mTotPct, 'MANDAL %', '#0F172A', '0.00', '100.00');

        // 3. Render Mandal Charts
        if (typeof Chart !== 'undefined') {
          // Chart 1: GP Wise Collection percentage (Sorted Descending, with data labels)
          const canvasMandalRanking = document.getElementById('chart-mandal-ranking');
          if (canvasMandalRanking) {
            if (chartMandalRanking) chartMandalRanking.destroy();
            const gpRanking = [...gpRecords].sort((a, b) => b.percentage - a.percentage);
            chartMandalRanking = new Chart(canvasMandalRanking.getContext('2d'), {
              type: 'bar',
              data: {
                labels: gpRanking.map(g => g.name),
                datasets: [{
                  label: 'Collection %',
                  data: gpRanking.map(g => Math.round(g.percentage)),
                  backgroundColor: '#0078D4',
                  borderRadius: 2
                }]
              },
              plugins: [pbiDataLabelsPlugin],
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { display: false },
                  tooltip: { callbacks: { label: (ctx) => `Collection: ${ctx.raw}%` } }
                },
                scales: {
                  x: { grid: { display: false }, ticks: { font: { size: 8.5 }, maxRotation: 55 } },
                  y: { min: 0, max: 100, ticks: { callback: (val) => val + '%' } }
                }
              }
            });
          }

          // Chart 2: Panchayat wise Demand, Collection and Balance (Demand=Red, Collection=Green, Balance=Blue)
          const canvasMandalDcb = document.getElementById('chart-mandal-dcb');
          if (canvasMandalDcb) {
            if (chartMandalDcb) chartMandalDcb.destroy();
            const gpOrder = [...gpRecords].sort((a, b) => a.name.localeCompare(b.name));
            chartMandalDcb = new Chart(canvasMandalDcb.getContext('2d'), {
              type: 'bar',
              data: {
                labels: gpOrder.map(g => g.name),
                datasets: [
                  { label: 'Demand', data: gpOrder.map(g => g.demand), backgroundColor: '#DC2626', borderRadius: 2, hideDataLabels: true },
                  { label: 'Collection', data: gpOrder.map(g => g.collection), backgroundColor: '#16A34A', borderRadius: 2, hideDataLabels: true },
                  { label: 'Balance', data: gpOrder.map(g => g.balance), backgroundColor: '#2563EB', borderRadius: 2, hideDataLabels: true },
                ]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'top', align: 'center', labels: { boxWidth: 10, font: { size: 10, weight: 'bold' } } },
                  tooltip: {
                    callbacks: { label: (ctx) => `${ctx.dataset.label}: ₹ ${formatInr(ctx.raw)}` }
                  }
                },
                scales: {
                  x: { grid: { display: false }, ticks: { font: { size: 8.5 }, maxRotation: 55 } },
                  y: {
                    ticks: {
                      callback: (val) => val >= 100000 ? (val / 100000).toFixed(1) + ' L' : val
                    }
                  }
                }
              }
            });
          }
        }
      }
    }

    function renderMandalTable(abstractList, summary) {
      const tbody = document.getElementById('mandal-table-body');
      document.getElementById('mandal-count-label').textContent = `${abstractList.length} Mandals Consolidated`;

      if (!abstractList || abstractList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="14" class="center-cell" style="padding:20px;">No mandal records found.</td></tr>';
        return;
      }

      // Sort Mandal-wise consolidated abstract in ascending order based on % Collection
      abstractList.sort((a, b) => (Number(a.percentage) || 0) - (Number(b.percentage) || 0));

      let html = '';
      abstractList.forEach((m, idx) => {
        const mPct = Math.round(m.percentage);
        const { bg, text } = getGradientColor(mPct);
        html += `<tr>
          <td class="center-cell">${idx + 1}</td>
          <td><strong>${m.mandal}</strong></td>
          <td class="num-cell">${m.total_gps}</td>
          <td class="num-cell">${formatInr(m.assessments)}</td>
          <td class="num-cell">${formatInr(m.demand_arrear)}</td>
          <td class="num-cell">${formatInr(m.demand_current)}</td>
          <td class="num-cell"><strong>${formatInr(m.demand_total)}</strong></td>
          <td class="num-cell">${formatInr(m.collection_arrear)}</td>
          <td class="num-cell">${formatInr(m.collection_current)}</td>
          <td class="num-cell"><strong>${formatInr(m.collection_total)}</strong></td>
          <td class="num-cell">${formatInr(m.balance_arrear)}</td>
          <td class="num-cell">${formatInr(m.balance_current)}</td>
          <td class="num-cell"><strong>${formatInr(m.balance_total)}</strong></td>
          <td class="center-cell">${renderPctCell(mPct)}</td>
        </tr>`;
      });

      // Total row
      const totColor = getGradientColor(summary.overall_percentage);
      html += `<tr class="total-row">
        <td class="center-cell">Σ</td>
        <td><strong>Total (${summary.district})</strong></td>
        <td class="num-cell">${summary.total_gps}</td>
        <td class="num-cell">${formatInr(summary.total_assessments)}</td>
        <td class="num-cell">${formatInr(summary.demand_arrear)}</td>
        <td class="num-cell">${formatInr(summary.demand_current)}</td>
        <td class="num-cell"><strong>${formatInr(summary.total_demand)}</strong></td>
        <td class="num-cell">${formatInr(summary.collection_arrear)}</td>
        <td class="num-cell">${formatInr(summary.collection_current)}</td>
        <td class="num-cell"><strong>${formatInr(summary.total_collection)}</strong></td>
        <td class="num-cell">${formatInr(summary.balance_arrear)}</td>
        <td class="num-cell">${formatInr(summary.balance_current)}</td>
        <td class="num-cell"><strong>${formatInr(summary.total_balance)}</strong></td>
        <td class="center-cell">${renderPctCell(summary.overall_percentage)}</td>
      </tr>`;

      tbody.innerHTML = html;
    }

    function applyFilter() {
      const q = document.getElementById('search-input').value.toLowerCase().trim();
      const mandalSel = document.getElementById('mandal-select').value.toLowerCase();

      filteredRecords = allRecords.filter(r => {
        const matchesMandal = (mandalSel === 'all') || (r.mandal.toLowerCase() === mandalSel);
        const matchesQuery = !q || r.panchayat.toLowerCase().includes(q) || r.mandal.toLowerCase().includes(q);
        return matchesMandal && matchesQuery;
      });

      currentPage = 1;
      renderGpTable();
    }

    function renderGpTable() {
      const tbody = document.getElementById('gp-table-body');
      const total = filteredRecords.length;
      document.getElementById('gp-count-label').textContent = `${total} Gram Panchayats`;

      if (total === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="center-cell" style="padding:20px;">No Gram Panchayats matching search.</td></tr>';
        document.getElementById('page-info').textContent = 'Showing 0-0 of 0';
        document.getElementById('btn-prev').disabled = true;
        document.getElementById('btn-next').disabled = true;
        return;
      }

      const start = (currentPage - 1) * PAGE_SIZE;
      const end = Math.min(start + PAGE_SIZE, total);
      const pageRows = filteredRecords.slice(start, end);

      let html = '';
      pageRows.forEach((r, idx) => {
        const pct = Math.round(r.calc_percentage || 0);
        const { bg, text } = getGradientColor(pct);
        html += `<tr>
          <td class="center-cell">${start + idx + 1}</td>
          <td>${r.mandal}</td>
          <td><strong>${r.panchayat}</strong></td>
          <td class="num-cell">${formatInr(r.assessments)}</td>
          <td class="num-cell">${formatInr(r.demand_arrear)}</td>
          <td class="num-cell">${formatInr(r.demand_current)}</td>
          <td class="num-cell"><strong>${formatInr(r.demand_total)}</strong></td>
          <td class="num-cell">${formatInr(r.collection_arrear)}</td>
          <td class="num-cell">${formatInr(r.collection_current)}</td>
          <td class="num-cell"><strong>${formatInr(r.collection_total)}</strong></td>
          <td class="num-cell"><strong>${formatInr(r.balance_total)}</strong></td>
          <td class="center-cell">${renderPctCell(pct)}</td>
        </tr>`;
      });

      tbody.innerHTML = html;
      document.getElementById('page-info').textContent = `Showing ${start + 1}-${end} of ${total}`;
      document.getElementById('btn-prev').disabled = currentPage <= 1;
      document.getElementById('btn-next').disabled = end >= total;
    }

    function changePage(delta) {
      currentPage += delta;
      renderGpTable();
    }

    async function refreshLiveData() {
      const btn = document.getElementById('btn-refresh');
      btn.disabled = true;
      btn.textContent = '⏳ Refreshing from epanchayat...';
      showStatus('Downloading latest live DCB data from ePanchayat Telangana portal...', 'info');

      try {
        const res = await fetch('/api/tax/refresh', { method: 'POST' });
        const resData = await res.json();
        showStatus(`Fresh data synced! Total ${resData.total_gps} GPs updated across state.`, 'success');
        const dist = document.getElementById('district-select').value;
        await loadData(dist);
        reloadPdfViewer();
      } catch (err) {
        showStatus('Failed to refresh data: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Refresh Live from Portal';
      }
    }

    function showStatus(msg, type = 'info') {
      const el = document.getElementById('status-box');
      el.className = 'status-alert ' + type;
      el.textContent = msg;
    }
    function hideStatus() {
      const el = document.getElementById('status-box');
      el.className = 'status-alert';
      el.textContent = '';
    }

    document.getElementById('district-select').addEventListener('change', onDistrictChanged);
    document.getElementById('mandal-select').addEventListener('change', () => {
      const dist = document.getElementById('district-select').value;
      if (dist) {
        showStatus('Mandal selected. Click ⚡ Generate Report to view report.', 'info');
      }
    });
    document.getElementById('search-input').addEventListener('input', applyFilter);

    // Initial run
    initDistricts();
  </script>
</body>
</html>
"""
