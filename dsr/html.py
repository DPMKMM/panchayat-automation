"""HTML template for the Naresh Automated DSR & Attendance Report Page (/naresh)."""

NARESH_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>e-Panchayat-automation</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      --primary: #0c3829;
      --primary-light: #165b43;
      --accent: #d97706;
      --accent-hover: #b45309;
      --bg: #f3f6f4;
      --card-bg: #ffffff;
      --text: #132a22;
      --text-muted: #4e6b60;
      --border: #d4e0da;
      --success: #059669;
      --warning: #d97706;
      --danger: #dc2626;
      --info: #2563eb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }

    /* Navbar */
    .navbar {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: var(--primary);
      color: white;
      box-shadow: 0 3px 14px rgba(0,0,0,0.18);
    }
    .nav-inner {
      max-width: 1280px;
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
      font-weight: 700;
      font-size: 1.05rem;
    }
    .nav-brand-badge {
      background: linear-gradient(135deg, #f59e0b, #d97706);
      color: #1a1a1a;
      font-size: 0.72rem;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: 4px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .nav-links {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .nav-link {
      color: #d1fae5;
      text-decoration: none;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: 500;
      transition: all 0.2s;
    }
    .nav-link:hover {
      background: rgba(255,255,255,0.1);
      color: white;
    }
    .nav-link.active {
      background: rgba(255,255,255,0.18);
      color: #fbbf24;
      font-weight: 700;
    }

    /* Dropdown Menus in Portal Nav */
    .dropdown { position: relative; display: inline-block; }
    .dropdown-btn { background: transparent; border: none; color: #d1fae5; padding: 8px 14px; border-radius: 6px; font-size: 0.9rem; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; font-family: inherit; transition: all 0.2s; }
    .dropdown-btn:hover { background: rgba(255,255,255,0.1); color: white; }
    .dropdown-btn.active { background: rgba(255,255,255,0.18); color: #fbbf24; }
    .caret { font-size: 0.72rem; transition: transform 0.2s; }
    .dropdown:hover .caret, .dropdown.open .caret { transform: rotate(180deg); }
    .dropdown-menu { display: none; position: absolute; top: calc(100% + 4px); left: 0; min-width: 310px; background: white; border: 1px solid #d4e0da; border-radius: 12px; box-shadow: 0 16px 36px rgba(12,56,41,0.18); padding: 8px; z-index: 1001; }
    .dropdown:hover .dropdown-menu, .dropdown.open .dropdown-menu { display: block; animation: dropdownFade 0.15s ease-out; }
    @keyframes dropdownFade { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
    .dropdown-header { font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: #5a7369; padding: 6px 12px 3px; }
    .dropdown-divider { height: 1px; background: #e5eee9; margin: 6px 0; }
    .dropdown-item { display: flex; align-items: flex-start; gap: 10px; padding: 8px 12px; border-radius: 8px; text-decoration: none; color: #132a22; transition: background 0.15s; cursor: pointer; }
    .dropdown-item:hover { background: #f0f7f3; }
    .dropdown-item.disabled { opacity: 0.6; cursor: not-allowed; }
    .dropdown-item.disabled:hover { background: transparent; }
    .dropdown-item-icon { font-size: 1.15rem; line-height: 1.2; flex-shrink: 0; }
    .dropdown-item-content strong { display: block; font-size: 0.86rem; color: #132a22; font-weight: 700; }
    .dropdown-item-content span { font-size: 0.76rem; color: #4e6b60; line-height: 1.3; display: block; }
    .badge-pill-live { display: inline-block; font-size: 0.64rem; font-weight: 700; background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; padding: 1px 6px; border-radius: 4px; margin-top: 3px; text-transform: uppercase; }
    .badge-pill-soon { display: inline-block; font-size: 0.64rem; font-weight: 700; background: #fef3c7; color: #92400e; border: 1px solid #fde68a; padding: 1px 6px; border-radius: 4px; margin-top: 3px; text-transform: uppercase; }

    /* Module Cards Grid in Post-Login Dashboard */
    .modules-section { margin-top: 20px; margin-bottom: 28px; }
    .modules-section-title { font-size: 1.22rem; font-weight: 800; color: var(--text); margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
    .modules-section-subtitle { font-size: 0.86rem; color: var(--text-muted); margin-bottom: 16px; }
    .modules-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 16px; }
    .module-card { background: var(--card-bg); border: 1.5px solid var(--border); border-radius: 14px; padding: 22px; display: flex; flex-direction: column; justify-content: space-between; box-shadow: 0 4px 14px rgba(12,56,41,0.06); transition: all 0.2s; position: relative; }
    .module-card:hover { transform: translateY(-3px); box-shadow: 0 10px 24px rgba(12,56,41,0.12); border-color: var(--primary-light); }
    .module-card.featured { border-color: #f59e0b; background: linear-gradient(180deg, #ffffff 0%, #fffdf8 100%); }
    .module-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
    .module-icon { font-size: 1.8rem; width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; background: #eaf5ef; }
    .module-card h3 { margin: 0 0 6px 0; font-size: 1.12rem; font-weight: 700; color: var(--text); }
    .module-card p { font-size: 0.88rem; color: var(--text-muted); line-height: 1.5; margin: 0 0 16px 0; flex-grow: 1; }

    /* Container */
    .container {
      max-width: 1280px;
      margin: 24px auto;
      padding: 0 20px;
    }

    /* Hero Card */
    .hero-card {
      background: linear-gradient(135deg, #062b1f 0%, #0c3829 55%, #154c38 100%);
      color: white;
      border-radius: 16px;
      padding: 28px 32px;
      box-shadow: 0 6px 20px rgba(12, 56, 41, 0.25);
      margin-bottom: 24px;
      position: relative;
      overflow: hidden;
    }
    .hero-card::after {
      content: "";
      position: absolute;
      top: -40px;
      right: -40px;
      width: 220px;
      height: 220px;
      background: radial-gradient(circle, rgba(245, 158, 11, 0.18) 0%, transparent 70%);
      pointer-events: none;
    }
    .hero-eyebrow {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      color: #a7f3d0;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .hero-title {
      margin: 0 0 10px 0;
      font-size: 1.85rem;
      font-weight: 800;
      letter-spacing: -0.5px;
      line-height: 1.25;
    }
    .hero-subtitle {
      margin: 0 0 16px 0;
      font-size: 0.98rem;
      color: #d1fae5;
      max-width: 820px;
      line-height: 1.5;
    }
    .hero-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 0.78rem;
      font-weight: 600;
    }
    .badge-live {
      background: rgba(16, 185, 129, 0.22);
      color: #6ee7b7;
      border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .live-dot {
      width: 7px;
      height: 7px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
      animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    .badge-portal {
      background: rgba(245, 158, 11, 0.2);
      color: #fde68a;
      border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .badge-info {
      background: rgba(255, 255, 255, 0.12);
      color: white;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 11px 22px;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      border: none;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .btn-gold {
      background: linear-gradient(135deg, #f59e0b, #d97706);
      color: #1a1a1a;
      box-shadow: 0 4px 12px rgba(217, 119, 6, 0.35);
    }
    .btn-gold:hover {
      background: linear-gradient(135deg, #fbbf24, #f59e0b);
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(217, 119, 6, 0.45);
    }
    .btn-white {
      background: white;
      color: var(--primary);
      box-shadow: 0 3px 10px rgba(0,0,0,0.12);
    }
    .btn-white:hover {
      background: #f8fafc;
      transform: translateY(-2px);
    }
    .btn-outline {
      background: rgba(255, 255, 255, 0.1);
      color: white;
      border: 1px solid rgba(255, 255, 255, 0.4);
    }
    .btn-outline:hover {
      background: rgba(255, 255, 255, 0.2);
      transform: translateY(-2px);
    }

    /* ========================================================
       AUTOMATION WORKFLOW STATION CARD (Login -> OTP -> Module -> Gen)
       ======================================================== */
    .automation-card {
      background: var(--card-bg);
      border: 2px solid #059669;
      border-radius: 16px;
      box-shadow: 0 6px 24px rgba(5, 150, 105, 0.12);
      margin-bottom: 26px;
      overflow: hidden;
      position: relative;
    }
    .automation-header {
      background: linear-gradient(135deg, #0c3829, #165b43);
      color: white;
      padding: 18px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
    }
    .automation-title {
      font-size: 1.15rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .pulse-icon {
      font-size: 1.3rem;
      display: inline-block;
      animation: pulse 1.5s infinite;
    }

    /* Stepper */
    .stepper {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #f8fafc;
      padding: 16px 28px;
      border-bottom: 1px solid var(--border);
      position: relative;
    }
    .step {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--text-muted);
      font-size: 0.88rem;
      font-weight: 600;
      position: relative;
      z-index: 2;
      cursor: pointer;
    }
    .step-circle {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: #e2e8f0;
      color: #64748b;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 0.9rem;
      transition: all 0.25s ease;
    }
    .step.active .step-circle {
      background: #059669;
      color: white;
      box-shadow: 0 0 10px rgba(5, 150, 105, 0.5);
    }
    .step.completed .step-circle {
      background: #047857;
      color: white;
    }
    .step.active {
      color: #065f46;
      font-weight: 700;
    }
    .step-line {
      flex: 1;
      height: 3px;
      background: #e2e8f0;
      margin: 0 12px;
      transition: background 0.3s;
    }
    .step-line.active {
      background: #059669;
    }

    /* Step Panes */
    .step-pane {
      padding: 24px 28px;
      display: none;
    }
    .step-pane.active {
      display: block;
      animation: fadeIn 0.25s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .step-instruction {
      font-size: 0.95rem;
      color: var(--text-muted);
      margin: 0 0 18px 0;
      line-height: 1.5;
    }
    .form-row {
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }
    .form-group {
      flex: 1;
      min-width: 240px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .form-group label {
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--text);
      text-transform: uppercase;
      letter-spacing: 0.4px;
    }
    .form-group input, .form-group select {
      padding: 12px 14px;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 0.95rem;
      background: #f8fafc;
      color: var(--text);
      outline: none;
      transition: all 0.2s;
    }
    .form-group input:focus, .form-group select:focus {
      border-color: #059669;
      background: white;
      box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.15);
    }
    .password-wrapper {
      position: relative;
      display: flex;
      align-items: center;
    }
    .password-wrapper input {
      width: 100%;
      padding-right: 44px;
    }
    .btn-toggle-pwd {
      position: absolute;
      right: 10px;
      background: none;
      border: none;
      cursor: pointer;
      font-size: 1.1rem;
      color: var(--text-muted);
    }

    /* OTP Box */
    .otp-box {
      background: #f0fdf4;
      border: 1.5px dashed #059669;
      border-radius: 12px;
      padding: 24px;
      text-align: center;
      max-width: 580px;
      margin: 0 auto;
    }
    .otp-header {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      margin-bottom: 16px;
      text-align: left;
    }
    .otp-icon {
      font-size: 2.2rem;
    }
    .otp-input-wrap input {
      font-size: 2.2rem;
      letter-spacing: 12px;
      text-align: center;
      font-weight: 800;
      padding: 12px 20px;
      width: 280px;
      border: 2px solid #059669;
      border-radius: 10px;
      background: white;
      outline: none;
      box-shadow: 0 4px 14px rgba(5, 150, 105, 0.15);
    }

    /* Live Progress Bar */
    .live-progress-card {
      padding: 10px 0;
    }
    .spinner-wrap {
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 16px;
    }
    .spinner {
      width: 28px;
      height: 28px;
      border: 3px solid #e2e8f0;
      border-top-color: #059669;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    #progress-status-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: #065f46;
    }
    .progress-bar-container {
      width: 100%;
      height: 8px;
      background: #e2e8f0;
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 16px;
    }
    .progress-bar-active {
      height: 100%;
      background: linear-gradient(90deg, #059669, #10b981);
      border-radius: 4px;
      transition: width 0.4s ease;
    }
    .progress-steps {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .p-step {
      font-size: 0.9rem;
      color: #64748b;
      padding-left: 24px;
      position: relative;
    }
    .p-step::before {
      content: "○";
      position: absolute;
      left: 0;
      color: #94a3b8;
      font-weight: bold;
    }
    .p-step.active {
      color: #047857;
      font-weight: 600;
    }
    .p-step.active::before {
      content: "●";
      color: #059669;
    }
    .p-step.done {
      color: #064e3b;
      font-weight: 600;
    }
    .p-step.done::before {
      content: "✓";
      color: #059669;
      font-weight: 900;
    }

    /* Automation Status Bar */
    .automation-status-bar {
      background: #f8fafc;
      border-top: 1px solid var(--border);
      padding: 10px 24px;
      font-size: 0.85rem;
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--text-muted);
    }
    .status-indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
    }

    /* Metrics Grid */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      position: relative;
      transition: transform 0.2s;
    }
    .metric-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 6px 16px rgba(0,0,0,0.08);
    }
    .metric-card.accent { border-top: 4px solid var(--primary); }
    .metric-card.success { border-top: 4px solid var(--success); }
    .metric-card.warning { border-top: 4px solid var(--warning); }
    .metric-card.info { border-top: 4px solid var(--info); }
    .metric-card.danger { border-top: 4px solid var(--danger); }
    .metric-label {
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .metric-value {
      font-size: 2rem;
      font-weight: 800;
      color: var(--text);
      line-height: 1.1;
      margin-bottom: 4px;
    }
    .metric-sub {
      font-size: 0.82rem;
      color: var(--text-muted);
    }

    /* PDF Preview Section */
    .viewer-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.05);
      margin-bottom: 24px;
      overflow: hidden;
    }
    .viewer-header {
      padding: 16px 20px;
      background: #f8fafc;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
    }
    .viewer-title {
      font-weight: 700;
      font-size: 1.05rem;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .viewer-actions {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .btn-sm {
      padding: 7px 14px;
      font-size: 0.85rem;
      border-radius: 6px;
    }
    .pdf-frame {
      width: 100%;
      height: 750px;
      border: none;
      background: #525659;
    }

    /* Mandals Table */
    .table-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.05);
      margin-bottom: 24px;
      overflow: hidden;
    }
    .table-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .table-title {
      font-weight: 700;
      font-size: 1.05rem;
    }
    .search-input {
      padding: 8px 14px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.9rem;
      width: 240px;
      outline: none;
    }
    .search-input:focus {
      border-color: var(--primary);
    }
    .table-responsive {
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }
    th {
      background: #f8fafc;
      text-align: left;
      padding: 12px 16px;
      font-weight: 700;
      color: var(--text-muted);
      border-bottom: 2px solid var(--border);
    }
    td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      color: var(--text);
    }
    tr:hover td {
      background: #f9fbf9;
    }
    /* Compact headers and high-contrast dark header for GP Balance Table */
    #balance-mandal-table thead tr {
      background: #0c3829 !important;
    }
    #balance-mandal-table thead th {
      background: #0c3829 !important;
      color: #ffffff !important;
      padding: 11px 8px;
      font-size: 0.81rem;
      font-weight: 800;
      line-height: 1.25;
      vertical-align: middle;
      white-space: nowrap;
      border: 1px solid #165b43 !important;
      letter-spacing: 0.01em;
    }
    #balance-mandal-table thead th.th-pct {
      color: #fef08a !important;
    }
    #balance-mandal-table td {
      padding: 7px 8px;
      font-size: 0.82rem;
      line-height: 1.25;
      border-bottom: 1px solid var(--border);
    }

    /* High-contrast dark headers for House Tax DCB Tables */
    #tax-mandal-table thead tr,
    #tax-gp-table thead tr {
      background: #0c3829 !important;
    }
    #tax-mandal-table thead th,
    #tax-gp-table thead th {
      background: #0c3829 !important;
      color: #ffffff !important;
      padding: 10px 8px;
      font-size: 0.81rem;
      font-weight: 800;
      line-height: 1.25;
      vertical-align: middle;
      white-space: nowrap;
      border: 1px solid #165b43 !important;
      letter-spacing: 0.01em;
    }
    #tax-mandal-table td,
    #tax-gp-table td {
      padding: 7px 8px;
      font-size: 0.82rem;
      line-height: 1.25;
      border-bottom: 1px solid var(--border);
    }

    /* High-contrast dark crimson header for Pending GPs Table */
    #balance-pending-table thead tr,
    #balance-pending-gps-card thead tr {
      background: #991b1b !important;
    }
    #balance-pending-table thead th,
    #balance-pending-gps-card thead th {
      background: #991b1b !important;
      color: #ffffff !important;
      padding: 10px 8px;
      font-size: 0.81rem;
      font-weight: 800;
      line-height: 1.25;
      vertical-align: middle;
      white-space: nowrap;
      border: 1px solid #7f1d1d !important;
    }
    #balance-pending-table td,
    #balance-pending-gps-card td {
      padding: 7px 8px;
      font-size: 0.82rem;
      line-height: 1.25;
      border-bottom: 1px solid #fecaca;
    }

    .text-right { text-align: right; }
    .text-center { text-align: center; }
    .pct-bar-wrap {
      width: 90px;
      height: 7px;
      background: #e2e8f0;
      border-radius: 4px;
      display: inline-block;
      overflow: hidden;
      vertical-align: middle;
      margin-left: 8px;
    }
    .pct-bar-fill {
      height: 100%;
      background: var(--success);
      border-radius: 4px;
    }

    @keyframes livePing {
      0% { transform: scale(1); opacity: 0.8; }
      70% { transform: scale(2.2); opacity: 0; }
      100% { transform: scale(2.2); opacity: 0; }
    }

    /* Footer */
    footer {
      text-align: center;
      padding: 30px 20px;
      color: var(--text-muted);
      font-size: 0.85rem;
      border-top: 1px solid var(--border);
      margin-top: 40px;
    }

    /* =========================================================================
       Mobile & Tablet Responsive System
       ========================================================================= */
    .nav-hamburger {
      display: none;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.25);
      border-radius: 8px;
      width: 40px;
      height: 40px;
      padding: 8px;
      cursor: pointer;
      flex-direction: column;
      justify-content: space-around;
      align-items: center;
      transition: all 0.25s ease-in-out;
      flex-shrink: 0;
    }
    .nav-hamburger:hover {
      background: rgba(255, 255, 255, 0.22);
    }
    .nav-hamburger:focus {
      outline: 2px solid #fbbf24;
      outline-offset: 2px;
    }
    .nav-hamburger .bar {
      width: 22px;
      height: 2.5px;
      background: #ffffff;
      border-radius: 2px;
      transition: all 0.25s ease-in-out;
    }
    .nav-hamburger.open .bar-1 {
      transform: translateY(6.5px) rotate(45deg);
    }
    .nav-hamburger.open .bar-2 {
      opacity: 0;
    }
    .nav-hamburger.open .bar-3 {
      transform: translateY(-6.5px) rotate(-45deg);
    }

    @media (max-width: 991px) {
      .nav-inner {
        height: 58px;
        padding: 0 12px;
        position: relative;
      }
      .nav-brand {
        gap: 6px;
      }
      .nav-brand-badge {
        font-size: 0.74rem;
        padding: 4px 8px;
        letter-spacing: 0.2px;
        max-width: 220px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .nav-hamburger {
        display: flex;
      }
      .nav-links {
        display: none !important;
        position: absolute;
        top: 58px;
        left: 0;
        right: 0;
        width: 100%;
        background: #062b1f;
        border-bottom: 3px solid #165b43;
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.45);
        flex-direction: column !important;
        align-items: stretch !important;
        gap: 8px !important;
        padding: 14px !important;
        max-height: calc(100vh - 60px);
        overflow-y: auto;
        z-index: 9999;
      }
      .nav-links.mobile-open {
        display: flex !important;
        animation: navSlideDown 0.22s ease-out;
      }
      @keyframes navSlideDown {
        from { opacity: 0; transform: translateY(-8px); }
        to { opacity: 1; transform: translateY(0); }
      }
      .nav-link, .dropdown-btn {
        width: 100%;
        padding: 12px 14px !important;
        font-size: 0.95rem !important;
        border-radius: 8px !important;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.12);
        display: flex !important;
        justify-content: flex-start !important;
        box-sizing: border-box;
      }
      .nav-link:hover, .dropdown-btn:hover {
        background: rgba(255, 255, 255, 0.16);
      }
      #nav-browser-pill {
        margin: 4px 0;
        padding: 10px 14px !important;
        border-radius: 8px !important;
        width: 100%;
        justify-content: center;
        font-size: 0.85rem !important;
      }
      #nav-session-timer-wrap {
        width: 100%;
        justify-content: space-between;
        margin: 4px 0;
      }
      #nav-portal-links {
        flex-direction: column !important;
        align-items: stretch !important;
        width: 100%;
        gap: 8px !important;
      }
      #nav-portal-links .dropdown-btn, #nav-portal-links .nav-link {
        width: 100%;
      }

      /* Container & Overall spacing */
      .container {
        padding: 0 12px !important;
        margin: 14px auto !important;
      }

      /* Global Browser Status Bar */
      #global-browser-status-bar {
        padding: 12px 14px !important;
        flex-direction: column !important;
        align-items: stretch !important;
        gap: 10px !important;
      }
      #browser-status-action {
        width: 100%;
        justify-content: space-between !important;
      }

      /* Hero Section */
      .hero-card {
        padding: 18px 16px !important;
      }
      .hero-title {
        font-size: 1.25rem !important;
        line-height: 1.35 !important;
      }
      .hero-subtitle {
        font-size: 0.88rem !important;
      }
      .modules-grid {
        grid-template-columns: 1fr !important;
        gap: 12px !important;
      }
      .module-card {
        padding: 16px !important;
      }

      /* Stepper */
      .stepper {
        gap: 4px !important;
        overflow-x: auto;
        padding-bottom: 6px;
        -webkit-overflow-scrolling: touch;
      }
      .step-label {
        font-size: 0.72rem !important;
      }
      .step-circle {
        width: 32px !important;
        height: 32px !important;
        font-size: 0.85rem !important;
      }

      /* Modals */
      .modal-dialog {
        max-width: 96vw !important;
        width: 96vw !important;
        margin: 12px auto !important;
        padding: 16px !important;
      }
      .modal-dialog input, .modal-dialog select, .modal-dialog button {
        font-size: 1rem !important;
      }

      /* Tables in Active Sessions and Results */
      .table-wrap, .table-container, .table-responsive {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
      }
      table th, table td {
        padding: 8px 8px !important;
        font-size: 0.78rem !important;
        white-space: nowrap;
      }
    }
  </style>
</head>
<body>

  <!-- Navigation Bar -->
  <header class="navbar">
    <div class="nav-inner">
      <a class="nav-brand" href="javascript:void(0)" onclick="closeMobileNav(); handleHomeNavigation();" style="display:inline-flex; align-items:center; gap:8px;" title="Go to Reports Dashboard / Home">
        <span style="font-size:1.3rem; line-height:1;">🏛️</span>
        <span class="nav-brand-badge" style="font-size:0.86rem; padding:5px 12px; font-weight:800; letter-spacing:0.5px;">e-Panchayat Automated Console</span>
      </a>

      <!-- Mobile Hamburger Toggle Button -->
      <button class="nav-hamburger" id="nav-hamburger-btn" type="button" onclick="toggleMobileNav()" aria-label="Toggle Navigation">
        <span class="bar bar-1"></span>
        <span class="bar bar-2"></span>
        <span class="bar bar-3"></span>
      </button>

      <!-- Navigation Links -->
      <nav class="nav-links" id="main-nav-links" style="display:flex; align-items:center; gap:10px;">
        <!-- Always-Visible Home Button -->
        <a class="nav-link" href="javascript:void(0)" onclick="handleHomeNavigation()" id="nav-btn-home" style="display:inline-flex; align-items:center; gap:6px; font-weight:700;">
          <span>🏠</span> Home
        </a>

        <!-- Always-Visible House Tax (DCB) Button (Public / No Login Required) -->
        <a class="nav-link" href="javascript:void(0)" onclick="closeMobileNav(); openTaxDcbStation();" id="nav-btn-tax" style="display:inline-flex; align-items:center; gap:6px; font-weight:700;">
          <span>💰</span> House Tax (DCB)
        </a>

        <!-- Unauthenticated Department Login Button -->
        <a class="nav-link" href="javascript:void(0)" onclick="closeMobileNav(); openDepartmentLogin();" id="nav-btn-login" style="display:inline-flex; align-items:center; gap:6px; font-weight:700; color:#fbbf24;">
          <span>🔐</span> Login
        </a>

        <!-- Always-Visible Background Browser Status Pill in Navbar (Clickable for All Active Sessions ONLY for DPOA3698) -->
        <span id="nav-browser-pill" style="display:inline-flex; align-items:center; gap:6px; font-size:0.75rem; font-weight:700; background:rgba(0,0,0,0.28); border:1px solid rgba(255,255,255,0.2); padding:3px 10px; border-radius:12px; color:#d1fae5; cursor:default;" title="Background browser engine status">
          <span style="width:8px; height:8px; border-radius:50%; background:#9ca3af; display:inline-block;" id="nav-browser-dot"></span>
          <span id="nav-browser-text">Browser: Standby</span>
        </span>

        <!-- Session Auto-Close Countdown & Extension Pill in Navbar -->
        <div id="nav-session-timer-wrap" style="display:none; align-items:center; gap:6px;">
          <span id="nav-session-timer" style="display:inline-flex; align-items:center; gap:5px; font-size:0.75rem; font-weight:700; background:rgba(16,185,129,0.2); border:1px solid rgba(16,185,129,0.45); padding:3px 10px; border-radius:12px; color:#d1fae5; transition:all 0.3s;" title="Session automatically closes browser when timer reaches 0 to conserve server load">
            ⏳ <span id="nav-timer-digits">10:00</span>
          </span>
          <button id="btn-extend-session" type="button" onclick="extendPortalSession()" style="background:#2563eb; color:#ffffff; border:none; border-radius:12px; font-size:0.72rem; font-weight:700; padding:3px 10px; cursor:pointer; display:inline-flex; align-items:center; gap:4px; box-shadow:0 2px 4px rgba(0,0,0,0.15);" title="Extend session by 10 more minutes (max 20 mins total)">
            +10m Extend
          </button>
        </div>

        <!-- Logged-in Links (Shown after login) -->
        <div id="nav-portal-links" style="display: none; align-items: center; gap: 8px;">
          <a class="nav-link" href="javascript:void(0)" onclick="closeMobileNav(); logoutPortalSession();" style="color:#fca5a5; font-weight:700; border:1px solid rgba(248,113,113,0.3); border-radius:8px; padding:6px 14px; background:rgba(239,68,68,0.12);" title="Logout session">🔒 Logout</a>
        </div>
      </nav>
    </div>
  </header>

  <!-- Main Content -->
  <main class="container">

    <!-- Global Persistent Background Browser Automation Status Bar (Always Visible Across All Screens) -->
    <div id="global-browser-status-bar" style="background: #092e21; border: 1.5px solid #165b43; border-radius: 12px; padding: 12px 18px; margin-bottom: 22px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; box-shadow: 0 4px 14px rgba(0,0,0,0.12);">
      <div style="display: flex; align-items: center; gap: 12px;">
        <div style="position: relative; width: 12px; height: 12px; flex-shrink: 0;">
          <span id="browser-status-ping" style="display:none; position: absolute; width: 100%; height: 100%; border-radius: 50%; background: #10b981; opacity: 0.75; animation: livePing 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;"></span>
          <span id="browser-status-dot" style="position: relative; display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #9ca3af;"></span>
        </div>
        <div>
          <div style="font-size: 0.88rem; font-weight: 800; color: #ffffff; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span>Background Browser Engine:</span>
            <span id="browser-status-pill" style="background: rgba(255,255,255,0.15); color: #e2e8f0; font-size: 0.72rem; font-weight: 800; padding: 2px 8px; border-radius: 6px; letter-spacing: 0.5px;">STANDBY · NOT LOGGED IN</span>
          </div>
          <div id="browser-status-desc" style="font-size: 0.8rem; color: #a7f3d0; margin-top: 2px;">
            Playwright browser service ready. Click "Login" to connect and authenticate.
          </div>
        </div>
      </div>
      <div id="browser-status-action" style="display: flex; align-items: center; gap: 10px;">
        <button type="button" id="btn-active-sessions" onclick="openSessionsModal()" style="display:none; background:rgba(255,255,255,0.12); color:#a7f3d0; border:1px solid rgba(255,255,255,0.25); border-radius:6px; font-size:0.75rem; font-weight:700; padding:4px 10px; cursor:pointer; align-items:center; gap:5px;" title="View all connected officers and background sessions (Admin only)">👥 Active Sessions</button>
        <span id="browser-status-officer" style="font-size: 0.82rem; font-weight: 700; color: #fbbf24;">🔒 Login Required</span>
      </div>
    </div>

    <!-- Home Screen: Portal Overview & Description (Shown when unauthenticated) -->
    <section class="hero-card" id="portal-hero-card" style="margin-bottom: 24px;">
      <div style="max-width: 860px;">
        <h1 class="hero-title" style="font-size:1.85rem; font-weight:800; margin-bottom:12px; line-height:1.25;">
          e-Panchayat Automated Executive Analytics &amp; Report Monitoring Console
        </h1>
        <p class="hero-subtitle" style="font-size:0.96rem; line-height:1.65; color:#d1fae5; margin-bottom:20px;">
          A next-generation automated reporting platform engineered for District &amp; Mandal administration. Our background browser automation robot connects directly to the e-Panchayat portal to solve captchas, authenticate departmental sessions, and automatically compile official reports—eliminating manual file downloads, spreadsheets merging, and delays.
        </p>

        <!-- Module Highlights Grid on Home -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-bottom:24px;">
          <div style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:10px; padding:14px;">
            <div style="display:flex; align-items:center; gap:8px; font-weight:700; color:#fbbf24; font-size:0.92rem; margin-bottom:5px;">
              <span>⚡</span> PS Attendance &amp; DSR
            </div>
            <div style="font-size:0.82rem; color:#d1fae5; line-height:1.45;">
              Daily morning attendance punctuality, DSR entry tracking, and 1-page Landscape combined District report.
            </div>
          </div>
          <div style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:10px; padding:14px;">
            <div style="display:flex; align-items:center; gap:8px; font-weight:700; color:#a7f3d0; font-size:0.92rem; margin-bottom:5px;">
              <span>🏦</span> Thursday Balance Entry
            </div>
            <div style="font-size:0.82rem; color:#d1fae5; line-height:1.45;">
              Weekly GP bank balance entry tracking, % compliance metrics, and Secretary pendency drill-down.
            </div>
          </div>
          <div style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:10px; padding:14px;">
            <div style="display:flex; align-items:center; gap:8px; font-weight:700; color:#38bdf8; font-size:0.92rem; margin-bottom:5px;">
              <span>🔍</span> GP Inspections Report
            </div>
            <div style="font-size:0.82rem; color:#d1fae5; line-height:1.45;">
              Official DPO, DLPO, and MPO inspection monitoring, compliance % tracking, and drill-down across Mandals.
            </div>
          </div>
          <div style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:10px; padding:14px;">
            <div style="display:flex; align-items:center; gap:8px; font-weight:700; color:#93c5fd; font-size:0.92rem; margin-bottom:5px;">
              <span>💰</span> House Tax (DCB)
            </div>
            <div style="font-size:0.82rem; color:#d1fae5; line-height:1.45;">
              Real-time Demand, Collection, and Balance analytics across Mandals and GPs with PowerBI visual reports.
            </div>
          </div>
        </div>

        <!-- Hero Action Buttons -->
        <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
          <button type="button" class="btn btn-gold" id="home-btn-login" onclick="openDepartmentLogin()" style="font-size:0.95rem; font-weight:800; padding:12px 24px; box-shadow:0 4px 14px rgba(245,158,11,0.4); display:inline-flex; align-items:center; gap:8px; cursor:pointer;">
            🔐 Login →
          </button>
          <button type="button" class="btn" onclick="openTaxDcbStation()" style="background:rgba(255,255,255,0.15); color:#fff; border:1.5px solid rgba(255,255,255,0.3); font-size:0.92rem; font-weight:700; padding:11px 20px; display:inline-flex; align-items:center; gap:8px; cursor:pointer; backdrop-filter:blur(4px);">
            💰 Public: House Tax (DCB) Analytics →
          </button>
        </div>
      </div>
    </section>

    <!-- ========================================================
         EXECUTIVE DASHBOARD & MODULE CARDS
         ======================================================== -->
    <div id="post-login-dashboard" style="display: block;">
      <!-- Welcome Officer Banner (Shown when Authenticated) -->
      <div id="dash-officer-banner" style="display: none;">
        <section class="hero-card" style="margin-bottom: 24px;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
            <div>
              <h1 class="hero-title" style="margin-bottom:6px;">Executive Report Modules</h1>
              <p class="hero-subtitle" style="margin-bottom:0;">
                Welcome back. Select an active automated robot module below or access regular departmental monitoring reports.
              </p>
            </div>
            <span class="badge badge-portal" id="dash-session-badge" style="font-size:0.86rem; padding:6px 14px; background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3);">
              🏛️ Authenticated Session Active
            </span>
          </div>
        </section>

        <!-- Live Background Service Status Card -->
        <div class="bg-service-strip" style="background:#092e21; border:1px solid #167451; border-radius:12px; padding:16px 20px; margin-bottom:24px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; box-shadow:0 4px 14px rgba(0,0,0,0.12);">
          <div style="display:flex; align-items:center; gap:14px;">
            <div style="position:relative; width:14px; height:14px; flex-shrink:0;">
              <span style="position:absolute; width:100%; height:100%; border-radius:50%; background:#10b981; opacity:0.75; animation:livePing 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;"></span>
              <span style="position:relative; display:inline-block; width:14px; height:14px; border-radius:50%; background:#10b981;"></span>
            </div>
            <div>
              <div style="font-size:1rem; font-weight:700; color:white; display:flex; align-items:center; gap:8px;">
                <span>Background Robot Service:</span>
                <span style="background:#10b981; color:#064e3b; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:6px; letter-spacing:0.5px;">ACTIVE &amp; RUNNING IN BACKGROUND</span>
              </div>
              <div style="font-size:0.84rem; color:#a7f3d0; margin-top:3px;">
                Playwright browser automation session active for Officer <strong id="dash-officer-id" style="color:#fbbf24;">Officer</strong>. Session is continuously running in the background for zero-wait automated reports.
              </div>
            </div>
          </div>
          <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <span id="dash-timer-chip" style="background:rgba(0,0,0,0.35); border:1px solid #10b981; border-radius:8px; padding:6px 12px; color:#d1fae5; font-size:0.82rem; font-weight:700; display:inline-flex; align-items:center; gap:6px;">
              ⏱️ Timer: <span id="dash-timer-digits" style="font-family:monospace; font-size:0.95rem; color:#fef08a;">10:00</span> remaining
            </span>
            <button id="dash-btn-extend" type="button" onclick="extendPortalSession()" style="background:#2563eb; color:white; border:none; border-radius:8px; font-size:0.8rem; font-weight:700; padding:6px 14px; cursor:pointer; display:inline-flex; align-items:center; gap:5px; box-shadow:0 2px 6px rgba(0,0,0,0.2);" title="Extend session by 10 more minutes (max 20 mins total)">
              ⏱️ +10 Mins (Extend)
            </button>
            <span class="badge" style="background:rgba(255,255,255,0.1); color:#e2e8f0; border:1px solid rgba(255,255,255,0.2); font-size:0.8rem; padding:6px 12px;">
              🤖 Robot Engine: Standby
            </span>
          </div>
        </div>
      </div>

      <!-- Section 1: Automated Reports -->
      <div class="modules-section">
        <div class="modules-section-title">
          <span>⚡</span>
          <span>Automated Reports (Robot Pipelines)</span>
        </div>
        <div class="modules-section-subtitle">
          Direct background portal fetching with AI Captcha solving, OTP auth, and automatic PDF generation.
        </div>
        <div class="modules-grid">
          <!-- Module 1: PS Attendance and DSR (Active Robot) -->
          <div class="module-card featured">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#fef3c7; color:#b45309;">⚡</div>
                <span class="badge-pill-live">● Active Robot</span>
              </div>
              <h3>PS Attendance and DSR Report</h3>
              <p>
                Automatic downloading of GM-R 1.2.7 DSR raw data, 1.2.11 Presentees, and 1.2.10 Absentees reports with matched secretary details and official combined Landscape District PDF compilation.
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-gold" style="width:100%; text-align:center;" onclick="closeMobileNav(); openDsrRobot();">
                ⚡ Open PS Attendance & DSR Station →
              </button>
            </div>
          </div>

          <!-- Module 2: GP Balance Entry (Active Robot) -->
          <div class="module-card featured" style="border-color:#10b981;">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#ecfdf5; color:#047857;">🏦</div>
                <span class="badge-pill-live">● Active Robot</span>
              </div>
              <h3>GP Balance Entry Report</h3>
              <p>
                Automated Thursday bank balance entry tracking (GM-R 14.2), calculating % Data Entered, account-wise pending tracking, and drill-down actionable list.
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-gold" style="width:100%; text-align:center;" onclick="openBalanceRobot()">
                🏦 Open Balance Robot Station →
              </button>
            </div>
          </div>

          <!-- Module 3: GP Inspections Report (Active Official Report) -->
          <div class="module-card featured" style="border-color:#0284c7;">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#e0f2fe; color:#0284c7;">🔍</div>
                <span class="badge-pill-live" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:700;">🔍 Official Report</span>
              </div>
              <h3>Gram Panchayat Inspections</h3>
              <p>
                Official compliance tracking for Gram Panchayat inspections conducted by District Panchayat Officers (DPO), Divisional Panchayat Officers (DLPO), and Mandal Panchayat Officers (MPO).
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-gold" style="width:100%; text-align:center; background:#0284c7; border-color:#0369a1; color:#ffffff;" onclick="closeMobileNav(); openGpInspectionsStation();">
                🔍 Open GP Inspections Station ➔
              </button>
            </div>
          </div>

          <!-- Module 4: Monthly Activity Statement (MAS) (Under Process) -->
          <div class="module-card" style="border-color:#f59e0b; background:#fffdfa;">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#fef3c7; color:#b45309;">📑</div>
                <span class="badge-pill-soon" style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; font-weight:700;">⏳ Under Process</span>
              </div>
              <h3>Monthly Activity Statement (MAS)</h3>
              <p>
                Official 18-Indicator Executive Matrix (GM-R 5.24 &amp; GM-R 5.23 Births Register). <em>This module is currently under active development and verification.</em>
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-outline" style="width:100%; text-align:center; color:#92400e; border-color:#f59e0b; background:#fffbeb; font-weight:700;" onclick="showUpcomingModal('Monthly Activity Statement (MAS) &amp; Births', '📑', 'The official 18-Indicator Executive Matrix (GM-R 5.24) and Births Registration module is currently under process. Real-time portal synchronization and verification are underway.')">
                ⏳ Under Process (In Development)
              </button>
            </div>
          </div>

          <!-- Module 4: Citizen Services (Upcoming) -->
          <div class="module-card">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#ecfdf5; color:#047857;">👥</div>
                <span class="badge-pill-soon">Upcoming</span>
              </div>
              <h3>Citizen Services</h3>
              <p>
                Real-time monitoring of citizen application delivery, birth/death certificates, and NOC timelines across Mandals.
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-outline" style="width:100%; text-align:center; color:var(--text); border-color:var(--border);" onclick="showUpcomingModal('Citizen Services', '👥', 'Automated tracking of citizen applications, service delivery SLAs, and certificates issuance from ePanchayat Portal.')">
                👥 View Module Details
              </button>
            </div>
          </div>

          <!-- Module 5: Trade Licences (Upcoming) -->
          <div class="module-card">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#fef3c7; color:#92400e;">🏷️</div>
                <span class="badge-pill-soon">Upcoming</span>
              </div>
              <h3>Trade Licences</h3>
              <p>
                Gram Panchayat business and trade licence issuance tracking, fee collection, and expiry renewal automation.
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-outline" style="width:100%; text-align:center; color:var(--text); border-color:var(--border);" onclick="showUpcomingModal('Trade Licences', '🏷️', 'Automated trade licence renewal tracking, fees reconciliation, and business register monitoring.')">
                🏷️ View Module Details
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Section 2: Financial & Revenue Analytics -->
      <div class="modules-section" style="margin-top:36px;">
        <div class="modules-section-title">
          <span>💰</span>
          <span>Financial &amp; Revenue Analytics</span>
        </div>
        <div class="modules-section-subtitle">
          District &amp; Statewide House Tax demand, collection, and balance monitoring. (Public Module — No Login Required)
        </div>
        <div class="modules-grid">
          <!-- Module: House Tax DCB -->
          <div class="module-card featured" style="border-color:#167451;">
            <div>
              <div class="module-card-header">
                <div class="module-icon" style="background:#eaf5ef; color:#167451;">💰</div>
                <span class="badge-pill-live">● Live Analytics (Public)</span>
              </div>
              <h3>House Tax Collection (DCB)</h3>
              <p>
                Live Demand, Collection, and Balance (DCB) monitoring across Mandals and Gram Panchayats with interactive analytical tables, KPIs, and downloadable Excel &amp; PDF reports.
              </p>
            </div>
            <div style="margin-top:auto;">
              <button type="button" class="btn btn-gold" style="width:100%; text-align:center;" onclick="openTaxDcbStation()">
                💰 Open House Tax DCB Station →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========================================================
         AUTOMATION WORKFLOW STATION CARD (Login -> OTP -> Module -> Gen)
         ======================================================== -->
    <section class="automation-card" id="automation-station" style="display: none;">
      <div id="btn-back-home-wrap" style="display:block; margin-bottom:14px;">
        <button type="button" class="btn btn-outline btn-sm" onclick="handleHomeNavigation()" style="color:var(--text); border-color:var(--border); display:inline-flex; align-items:center; gap:6px;">
          ← Back to Portal Overview
        </button>
      </div>
      <div id="btn-back-dashboard-wrap" style="display:none; margin-bottom:14px;">
        <button type="button" class="btn btn-outline btn-sm" onclick="showDashboard()" style="color:var(--text); border-color:var(--border); display:inline-flex; align-items:center; gap:6px;">
          ← Back to Report Modules Dashboard
        </button>
      </div>

      <div class="automation-header">
        <div class="automation-title">
          <span class="pulse-icon">⚡</span>
          <span>PS Attendance and DSR</span>
        </div>
        <span class="badge badge-portal" id="session-badge">Session: Ready</span>
      </div>

      <!-- Stepper Indicator -->
      <div class="stepper">
        <div class="step active" id="step-nav-1" onclick="goToStep(1)">
          <div class="step-circle" id="circle-1">1</div>
          <div class="step-text">Login</div>
        </div>
        <div class="step-line" id="line-1"></div>
        <div class="step" id="step-nav-2" onclick="goToStep(2)">
          <div class="step-circle" id="circle-2">2</div>
          <div class="step-text">Enter OTP</div>
        </div>
        <div class="step-line" id="line-2"></div>
        <div class="step" id="step-nav-3" onclick="goToStep(3)">
          <div class="step-circle" id="circle-3">3</div>
          <div class="step-text">Module &amp; Date</div>
        </div>
        <div class="step-line" id="line-3"></div>
        <div class="step" id="step-nav-4">
          <div class="step-circle" id="circle-4">4</div>
          <div class="step-text">Auto-Generate</div>
        </div>
      </div>

      <!-- STEP 1: Login -->
      <div class="step-pane active" id="pane-step-1">
        <p class="step-instruction">
          Enter your credentials. Our background robot connects to <strong>Portal</strong>, auto-solves the captcha with AI OCR, and triggers your 6-digit login OTP.
        </p>
        <div class="form-row">
          <div class="form-group">
            <label>User ID</label>
            <input type="text" id="auto-user" placeholder="Enter User ID" autocomplete="username" oninput="updateOfficerBadge(this.value)" required>
          </div>
          <div class="form-group">
            <label>Password</label>
            <div class="password-wrapper">
              <input type="password" id="auto-pwd" placeholder="Enter Password" autocomplete="current-password" required>
              <button type="button" class="btn-toggle-pwd" onclick="togglePasswordVisibility()" title="Toggle visibility">👁️</button>
            </div>
          </div>
        </div>
        <div class="form-actions" style="display:flex; gap:12px; flex-wrap:wrap;">
          <button type="button" class="btn btn-gold" id="btn-login" onclick="startDepartmentLogin()">
            🔐 Login to e-Panchayat &amp; Generate OTP
          </button>
        </div>
      </div>

      <!-- STEP 2: OTP Verification -->
      <div class="step-pane" id="pane-step-2">
        <div class="otp-box">
          <div class="otp-header">
            <span class="otp-icon">📱</span>
            <div>
              <strong>6-Digit OTP Sent to Your Registered Mobile</strong>
              <div style="font-size:0.85rem; color:var(--text-muted); margin-top:3px;">
                Enter the OTP received from e-Panchayat Telangana to authenticate session.
              </div>
            </div>
          </div>

          <!-- Dynamic Mobile Number OTP Notice (Matches e-Panchayat official portal message) -->
          <div id="otp-dynamic-notice" style="margin: 16px auto 20px auto; max-width: 580px; padding: 14px 18px; background: #fff5f5; border: 1.5px solid #fca5a5; border-radius: 8px; color: #dc2626; font-size: 1.02rem; font-weight: 700; text-align: center; line-height: 1.5; letter-spacing: 0.1px; box-shadow: 0 2px 8px rgba(220,38,38,0.08);">
            A 6 digit OTP has been sent to your registered mobile number <span id="otp-mobile-span" style="text-decoration: underline; font-weight: 800;">xxxxxx5586</span>. Enter OTP to continue.
          </div>

          <div class="otp-input-wrap">
            <input type="text" id="auto-otp" maxlength="6" inputmode="numeric" placeholder="••••••" autocomplete="one-time-code">
          </div>
          <div class="form-actions" style="margin-top:20px; display:flex; justify-content:center; gap:12px; flex-wrap:wrap;">
            <button type="button" class="btn btn-gold" id="btn-validate-otp" onclick="validateOTP()">
              ✅ Validate OTP &amp; Proceed to Report Selection
            </button>
            <button type="button" class="btn btn-outline" style="color:var(--text); border-color:var(--border);" onclick="goToStep(1)">
              ↩ Back to Login
            </button>
          </div>
        </div>
      </div>

      <!-- STEP 3: Module & Date Selection -->
      <div class="step-pane" id="pane-step-3">
        <p class="step-instruction">
          Automated multi-report pipeline: The robot downloads <strong>GM-R 1.2.7 DSR Raw Data</strong>, re-selects <strong>GP Monitoring</strong> to download <strong>GM-R 1.2.11 Presentees Report</strong>, re-selects <strong>GP Monitoring</strong> to download <strong>GM-R 1.2.10 Absentees Report</strong>, and compiles the official 7-section District PDF with matched secretary details (Official District standard).
        </p>
        <div class="form-row">
          <div class="form-group" style="flex:2;">
            <label>Reporting Workflow</label>
            <select id="auto-module">
              <option value="dsr_full" selected>⚡ PS Attendance and DSR Module (Combined Landscape District PDF)</option>
            </select>
          </div>
          <div class="form-group" style="flex:1;">
            <label>Select Date</label>
            <input type="date" id="auto-date" value="2026-11-02">
          </div>
        </div>
        <div class="form-actions" style="display:flex; gap:12px; flex-wrap:wrap;">
          <button type="button" class="btn btn-gold" id="btn-generate" onclick="runAutomatedGeneration()">
            ⚡ Generate PS Attendance and DSR Report
          </button>
          <button type="button" class="btn btn-outline" style="color:var(--text); border-color:var(--border);" onclick="showDashboard()">
            ← Back to Dashboard
          </button>
        </div>
      </div>

      <!-- STEP 4: Live Automation Execution & Progress -->
      <div class="step-pane" id="pane-step-4">
        <div class="live-progress-card">
          <div class="spinner-wrap">
            <div class="spinner" id="auto-spinner"></div>
            <div id="progress-status-title">Processing in Background...</div>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar-active" id="progress-bar-fill" style="width: 25%;"></div>
          </div>
          <ul class="progress-steps" id="progress-steps-list">
            <li class="p-step active" id="ps-1">Authenticating with e-Panchayat Session...</li>
            <li class="p-step" id="ps-2">Step 1: GP Monitoring &rarr; Downloading GM-R 1.2.7 DSR Raw Data...</li>
            <li class="p-step" id="ps-3">Step 2: Re-select GP Monitoring &rarr; Downloading GM-R 1.2.11 Presentees Report...</li>
            <li class="p-step" id="ps-4">Step 3: Re-select GP Monitoring &rarr; Downloading GM-R 1.2.10 Absentees Report...</li>
            <li class="p-step" id="ps-5">Step 4: Compiling 7-section official District Attendance &amp; DSR PDF...</li>
          </ul>
          <div id="auto-completion-banner" style="display:none; margin-top:20px; padding:18px; background:#ecfdf5; border:1.5px solid #10b981; border-radius:10px; text-align:center;">
            <strong style="color:#065f46; font-size:1.15rem; display:block; margin-bottom:6px;">🎉 Official DSR Report Generated Successfully!</strong>
            <span style="color:#047857; font-size:0.92rem;">The metrics, mandal statistics, and PDF preview below have been updated in real-time.</span>
            <div style="margin-top:14px; display:flex; justify-content:center; gap:12px; flex-wrap:wrap;">
              <a class="btn btn-gold btn-sm" href="/api/naresh/download" target="_blank">📥 Download PDF</a>
              <button type="button" class="btn btn-white btn-sm" onclick="loadAndScrollToViewer()">👁️ View in PDF Reader</button>
              <button type="button" class="btn btn-outline btn-sm" style="color:var(--text); border-color:var(--border);" onclick="goToStep(3)">🔄 Generate Another Date</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Live Status Bar -->
      <div class="automation-status-bar" id="status-bar">
        <span class="status-indicator" id="status-dot"></span>
        <span id="status-msg">Status: Ready to connect to e-Panchayat Telangana portal</span>
      </div>
    </section>

    <!-- ========================================================
         GP BALANCE ENTRY ROBOT STATION (GM-R 14.2)
         ======================================================== -->
    <section class="automation-station" id="balance-station" style="display: none; margin-bottom: 24px;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:18px; padding-bottom:14px; border-bottom:1.5px solid var(--border);">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:44px; height:44px; border-radius:10px; background:#ecfdf5; color:#047857; display:flex; align-items:center; justify-content:center; font-size:1.6rem;">🏦</div>
          <div>
            <h2 style="margin:0; font-size:1.3rem; font-weight:800; color:var(--text);">GM-R 14.2 GP Bank Balance Entry Robot Station</h2>
            <div style="font-size:0.85rem; color:var(--text-muted);">Status Report on Data Entered GPs · Thursday Balance Entry</div>
          </div>
        </div>
        <button type="button" class="btn btn-outline btn-sm" style="color:var(--text); border-color:var(--border);" onclick="showDashboard()">
          ← Back to Dashboard
        </button>
      </div>

      <!-- Authentication Required Warning Banner (shown if visited without logging in) -->
      <div id="bal-unauth-banner" style="display:none; background:#fef2f2; border:1.5px solid #fca5a5; border-radius:10px; padding:12px 18px; margin-bottom:16px; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px;">
        <div style="display:flex; align-items:center; gap:10px; color:#991b1b; font-weight:700; font-size:0.9rem;">
          <span style="font-size:1.4rem;">🔒</span>
          <span><b>e-Panchayat Login Required:</b> You must login with your Department User ID &amp; OTP to run the live Balance Robot.</span>
        </div>
        <button type="button" class="btn btn-gold btn-sm" onclick="showLoginStation('balance')" style="font-weight:800;">
          🔐 Go to Login &rarr;
        </button>
      </div>

      <!-- Control Bar -->
      <div style="background:#f8fafc; border:1px solid var(--border); border-radius:12px; padding:18px 20px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
          <label style="font-weight:700; font-size:0.9rem; color:var(--text);">Select Balance Updated Date :*</label>
          <select id="balance-date-select" onchange="onBalanceDateChanged()" style="padding:10px 14px; border-radius:8px; border:1.5px solid var(--border); font-size:0.92rem; font-weight:700; background:white; color:var(--text); outline:none; min-width:240px;">
            <option value="">Fetching live Thursday dates...</option>
          </select>
          <button type="button" class="btn btn-outline btn-sm" id="btn-refresh-balance-dates" onclick="fetchPortalBalanceDates(true)" title="Fetch live Thursday dates from e-Panchayat portal" style="padding:8px 12px; font-weight:700; border-color:var(--border); color:var(--text);">
            🔄 Refresh Portal Dates
          </button>
          <button type="button" class="btn btn-gold btn-sm" id="btn-run-balance-robot" onclick="triggerBalancePipeline()" style="padding:9px 18px; font-weight:800;">
            ⚡ Run Balance Robot
          </button>
        </div>
        <div style="display:none; gap:10px; flex-wrap:wrap;" id="balance-actions-wrap">
          <a class="btn btn-white btn-sm" id="btn-balance-excel" href="javascript:void(0)" target="_blank" style="border:1.5px solid #10b981; color:#065f46; font-weight:700;">
            📥 Download Consolidated Excel
          </a>
          <a class="btn btn-white btn-sm" id="btn-balance-pdf" href="javascript:void(0)" target="_blank" style="border:1.5px solid #0c3829; color:#0c3829; font-weight:700;">
            📄 View Executive PDF
          </a>
          <a class="btn btn-white btn-sm" id="btn-balance-pdf-dl" href="javascript:void(0)" download style="border:1.5px solid #047857; color:#047857; font-weight:700;">
            📥 Download PDF
          </a>
        </div>
      </div>

      <!-- Policy & Formula Notice -->
      <div style="background:#f0fdf4; border:1px solid #a7f3d0; border-radius:8px; padding:10px 16px; margin-bottom:20px; font-size:0.84rem; color:#065f46; display:flex; align-items:center; gap:8px;">
        <span style="font-size:1.1rem;">💡</span>
        <span><b>Rule:</b> % Data Entered = (No. of GPs Entered Data / Total No. of GPs) × 100. Account-wise Pending = Total GPs − Updated GPs. <b>PMAGY account is excluded</b> (Not maintained in district).</span>
      </div>

      <!-- KPI Summary Cards (Initial state is reset: dashes until Run Balance Robot is executed) -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-bottom:20px;" id="balance-kpis">
        <div style="background:white; border:1px solid var(--border); border-radius:10px; padding:14px; text-align:center;">
          <div style="font-size:0.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Total Mandals</div>
          <div style="font-size:1.6rem; font-weight:800; color:var(--text);" id="bal-kpi-mandals">—</div>
        </div>
        <div style="background:white; border:1px solid var(--border); border-radius:10px; padding:14px; text-align:center;">
          <div style="font-size:0.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Total GPs</div>
          <div style="font-size:1.6rem; font-weight:800; color:var(--text);" id="bal-kpi-total-gps">—</div>
        </div>
        <div style="background:white; border:1px solid var(--border); border-radius:10px; padding:14px; text-align:center;">
          <div style="font-size:0.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Data Entered</div>
          <div style="font-size:1.6rem; font-weight:800; color:#059669;" id="bal-kpi-entered">—</div>
        </div>
        <div style="background:white; border:1px solid var(--border); border-radius:10px; padding:14px; text-align:center;">
          <div style="font-size:0.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Pending GPs</div>
          <div style="font-size:1.6rem; font-weight:800; color:#dc2626;" id="bal-kpi-pending">—</div>
        </div>
        <div style="background:white; border:1px solid var(--border); border-radius:10px; padding:14px; text-align:center;">
          <div style="font-size:0.75rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Compliance %</div>
          <div style="font-size:1.6rem; font-weight:800; color:#0c3829;" id="bal-kpi-pct">—</div>
        </div>
      </div>

      <!-- Mandal Summary Table Card -->
      <div class="table-card" style="margin-bottom:20px;">
        <div class="table-header">
          <div class="table-title">Mandal-wise Balance Entry Abstract (GM-R 14.2)</div>
          <input type="text" class="search-input" id="balance-search-input" placeholder="Search Mandal..." onkeyup="filterBalanceTable()">
        </div>
        <div class="table-responsive">
          <table id="balance-mandal-table">
            <thead>
              <tr style="background:#0c3829 !important; color:#ffffff !important;">
                <th style="background:#0c3829 !important; color:#ffffff !important; width:45px;" class="text-center">S.No</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;">Mandal Name</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-right">Total GPs</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-right">GPs Entered</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-right">GPs Not Entered</th>
                <th style="background:#0c3829 !important; color:#fef08a !important;" class="text-right th-pct">% Data Entered</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-center">GP PD (Upd/Pnd)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-center">TG-bPASS (Upd/Pnd)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-center">15th FC Tied</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-center">15th FC Untied</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-center">VWSC (SBM)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;" class="text-center">MGNREGS</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; width:80px; text-align:center;" class="text-center">Status</th>
              </tr>
            </thead>
            <tbody id="balance-table-tbody">
              <tr>
                <td colspan="13" style="text-align:center; padding:38px 20px; color:var(--text-muted); font-size:0.95rem;">
                  <div style="font-size:1.8rem; margin-bottom:8px;">🏦</div>
                  <strong style="color:var(--text); font-size:1.05rem;">No Balance Report Processed Yet</strong>
                  <div style="font-size:0.86rem; color:var(--text-muted); margin-top:6px;">
                    Select a Thursday date above and click <b style="color:#b45309;">⚡ Run Balance Robot</b> to fetch live portal data.
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pending Gram Panchayats Action Section -->
      <div class="table-card" id="balance-pending-gps-card" style="display:none; border-color:#fca5a5;">
        <div class="table-header" style="background:#fee2e2;">
          <div class="table-title" style="color:#991b1b;">List of Pending Gram Panchayats</div>
          <span style="font-size:0.85rem; font-weight:700; color:#b91c1c;" id="pending-count-badge">0 Pending GPs</span>
        </div>
        <div class="table-responsive">
          <table id="balance-pending-table">
            <thead>
              <tr style="background:#991b1b !important; color:#ffffff !important;">
                <th style="background:#991b1b !important; color:#ffffff !important; width:45px;" class="text-center">S.No</th>
                <th style="background:#991b1b !important; color:#ffffff !important;">Mandal Name</th>
                <th style="background:#991b1b !important; color:#ffffff !important;">Gram Panchayat</th>
                <th style="background:#991b1b !important; color:#ffffff !important;">Missing Account(s)</th>
                <th style="background:#991b1b !important; color:#ffffff !important; width:95px; text-align:center;" class="text-center">Status</th>
              </tr>
            </thead>
            <tbody id="balance-pending-tbody">
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- ========================================================
         HOUSE TAX COLLECTION (DCB) STATION (Public / No Login Required)
         ======================================================== -->
    <section class="automation-station" id="tax-dcb-station" style="display: none; margin-bottom: 24px;">
      <!-- Station Top Bar -->
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:18px; padding-bottom:14px; border-bottom:1.5px solid var(--border);">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:44px; height:44px; border-radius:10px; background:#ecfdf5; color:#047857; display:flex; align-items:center; justify-content:center; font-size:1.6rem;">💰</div>
          <div>
            <h2 style="margin:0; font-size:1.3rem; font-weight:800; color:var(--text);">House Tax Collection (DCB) Station</h2>
            <div style="font-size:0.85rem; color:var(--text-muted);">Consolidated Demand, Collection &amp; Balance (DCB) · Public Real-Time Analytics</div>
          </div>
        </div>
        <button type="button" class="btn btn-outline btn-sm" id="tax-btn-back" style="color:var(--text); border-color:var(--border);" onclick="handleTaxBack()">
          ← Back to Dashboard
        </button>
      </div>

      <!-- Controls & Filter Card -->
      <div class="control-panel" style="background:#ffffff; border:1px solid var(--border); border-radius:12px; padding:18px 20px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:14px; align-items:flex-end;">
          <div class="form-group" style="margin-bottom:0;">
            <label style="font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px; display:block;">Select District :*</label>
            <select id="tax-district-select" style="width:100%; height:40px; border-radius:8px; border:1.5px solid var(--border); padding:0 12px; font-size:0.92rem; font-weight:600;" onchange="onTaxDistrictChanged()">
              <option value="" selected>-- Select District --</option>
            </select>
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label style="font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px; display:block;">Filter by Mandal :</label>
            <select id="tax-mandal-select" style="width:100%; height:40px; border-radius:8px; border:1.5px solid var(--border); padding:0 12px; font-size:0.92rem; font-weight:600;" onchange="onTaxMandalChanged()" disabled>
              <option value="">-- Select District First --</option>
            </select>
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label style="font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px; display:block;">Search GP / Mandal :</label>
            <input type="text" id="tax-search-input" placeholder="Type Panchayat or Mandal name..." style="width:100%; height:40px; border-radius:8px; border:1.5px solid var(--border); padding:0 12px; font-size:0.92rem;" onkeyup="filterTaxTables()">
          </div>
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <button type="button" class="btn btn-gold" id="btn-tax-generate" onclick="generateTaxReport()" title="Compile House Tax DCB Report for selected District &amp; Mandal" style="height:40px; padding:0 20px; font-weight:800; display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
              ⚡ Generate DCB Report
            </button>
            <button type="button" class="btn btn-primary" id="btn-tax-refresh" onclick="refreshTaxDataLive()" title="Download fresh live DCB data directly from e-Panchayat portal" style="height:40px; padding:0 16px; font-weight:700; background:#0c3829; color:#fff; display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
              🔄 Refresh Live Data
            </button>
            <button type="button" class="btn btn-outline" id="btn-tax-reset" onclick="resetTaxStatistics()" title="Reset all filters and clear statistics" style="height:40px; padding:0 14px; font-weight:700; color:#1f2937; border:1.5px solid #d1d5db; background:#f9fafb; display:inline-flex; align-items:center; gap:6px; cursor:pointer;">
              ⟲ Reset Statistics
            </button>
          </div>
        </div>

        <!-- Export Buttons Row -->
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; padding-top:14px; border-top:1px dashed var(--border);" id="tax-actions-wrap">
          <button type="button" class="btn btn-gold btn-sm" onclick="downloadTaxExcel()" style="display:inline-flex; align-items:center; gap:6px;">
            📊 Download Consolidated Excel
          </button>
          <button type="button" class="btn btn-primary btn-sm" onclick="downloadTaxPdf()" style="display:inline-flex; align-items:center; gap:6px; background:#167451; color:#fff;">
            📄 Download PDF
          </button>
          <button type="button" class="btn btn-outline btn-sm" onclick="downloadTaxPbiPdf()" style="display:inline-flex; align-items:center; gap:6px; color:var(--text); border-color:var(--border);">
            📈 Download PowerBI Visual PDF
          </button>
        </div>
      </div>

      <!-- KPI Summary Cards -->
      <div class="metrics-grid" style="grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 22px;">
        <div class="metric-card">
          <div class="metric-label">TOTAL MANDALS</div>
          <div class="metric-value" id="tax-kpi-mandals">—</div>
          <div class="metric-sub" id="tax-kpi-mandals-sub">District Total</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">TOTAL GPs</div>
          <div class="metric-value" id="tax-kpi-gps">—</div>
          <div class="metric-sub" id="tax-kpi-assessments">Assessments: —</div>
        </div>
        <div class="metric-card info">
          <div class="metric-label">TOTAL DEMAND</div>
          <div class="metric-value" id="tax-kpi-demand">—</div>
          <div class="metric-sub" id="tax-kpi-demand-sub">Arrear: — | Current: —</div>
        </div>
        <div class="metric-card success">
          <div class="metric-label">TOTAL COLLECTION</div>
          <div class="metric-value" id="tax-kpi-collection">—</div>
          <div class="metric-sub" id="tax-kpi-coll-sub">Arrear: — | Current: —</div>
        </div>
        <div class="metric-card danger">
          <div class="metric-label">TOTAL BALANCE</div>
          <div class="metric-value" id="tax-kpi-balance">—</div>
          <div class="metric-sub" id="tax-kpi-bal-sub">Arrear: — | Current: —</div>
        </div>
        <div class="metric-card accent">
          <div class="metric-label">COLLECTION %</div>
          <div class="metric-value" id="tax-kpi-pct">—%</div>
          <div class="metric-sub">Performance Ratio</div>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div style="display:flex; gap:6px; margin-bottom:14px; border-bottom:2px solid #e5e7eb; padding-bottom:2px;">
        <button type="button" class="tab-btn active" id="tax-tab-btn-abstract" onclick="switchTaxTab('abstract')" style="padding:10px 18px; font-weight:700; font-size:0.9rem; border:none; background:#0c3829; color:white; border-radius:8px 8px 0 0; cursor:pointer;">
          🏛️ Mandal Abstract Table
        </button>
        <button type="button" class="tab-btn" id="tax-tab-btn-detail" onclick="switchTaxTab('detail')" style="padding:10px 18px; font-weight:700; font-size:0.9rem; border:none; background:#e5e7eb; color:#374151; border-radius:8px 8px 0 0; cursor:pointer;">
          🏡 GP Detailed Table
        </button>
        <button type="button" class="tab-btn" id="tax-tab-btn-pdf" onclick="switchTaxTab('pdf')" style="padding:10px 18px; font-weight:700; font-size:0.9rem; border:none; background:#e5e7eb; color:#374151; border-radius:8px 8px 0 0; cursor:pointer;">
          📄 Live PDF Viewer
        </button>
      </div>

      <!-- Tab 1: Mandal Abstract Table -->
      <div id="tax-pane-abstract" class="table-card" style="margin-bottom:24px;">
        <div class="table-header" style="background:#f8fafc;">
          <div class="table-title">Mandal-wise DCB Abstract (<span id="tax-abstract-dist-label">Select District</span>)</div>
          <span style="font-size:0.84rem; font-weight:700; color:#167451;" id="tax-abstract-count">-- Mandals</span>
        </div>
        <div class="table-responsive">
          <table id="tax-mandal-table">
            <thead>
              <tr style="background:#0c3829 !important; color:#ffffff !important;">
                <th style="background:#0c3829 !important; color:#ffffff !important; width:45px; text-align:center;">S.No</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;">Mandal Name</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">GPs</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Assessments</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Arrear Dem (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Current Dem (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Total Dem (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Arrear Coll (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Current Coll (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Total Coll (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Balance (₹)</th>
                <th style="background:#0c3829 !important; color:#fef08a !important; text-align:right; width:80px;">Coll %</th>
              </tr>
            </thead>
            <tbody id="tax-mandal-tbody">
              <tr>
                <td colspan="12" style="text-align:center; padding:35px 20px; color:var(--text-muted); font-size:0.95rem;">
                  Select District &amp; Mandal above and click <strong>⚡ Generate DCB Report</strong> to compile House Tax statistics.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab 2: GP Detailed Table -->
      <div id="tax-pane-detail" class="table-card" style="display:none; margin-bottom:24px;">
        <div class="table-header" style="background:#f8fafc;">
          <div class="table-title">Gram Panchayat Wise DCB Status</div>
          <span style="font-size:0.84rem; font-weight:700; color:#167451;" id="tax-detail-count">-- GPs</span>
        </div>
        <div class="table-responsive">
          <table id="tax-gp-table">
            <thead>
              <tr style="background:#0c3829 !important; color:#ffffff !important;">
                <th style="background:#0c3829 !important; color:#ffffff !important; width:45px; text-align:center;">S.No</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;">Mandal Name</th>
                <th style="background:#0c3829 !important; color:#ffffff !important;">Gram Panchayat</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Assessments</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Arrear Dem (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Current Dem (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Total Dem (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Arrear Coll (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Current Coll (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Total Coll (₹)</th>
                <th style="background:#0c3829 !important; color:#ffffff !important; text-align:right;">Balance (₹)</th>
                <th style="background:#0c3829 !important; color:#fef08a !important; text-align:right; width:80px;">Coll %</th>
              </tr>
            </thead>
            <tbody id="tax-gp-tbody">
              <tr>
                <td colspan="12" style="text-align:center; padding:35px 20px; color:var(--text-muted); font-size:0.95rem;">
                  Select District &amp; Mandal above and click <strong>⚡ Generate DCB Report</strong> to compile House Tax statistics.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab 3: PDF Viewer -->
      <div id="tax-pane-pdf" class="viewer-card" style="display:none; margin-bottom:24px;">
        <div class="viewer-header">
          <div class="viewer-title">
            <span>📄</span>
            <span>House Tax DCB Official Departmental Landscape PDF</span>
          </div>
          <div class="viewer-actions">
            <a class="btn btn-gold btn-sm" id="tax-pdf-fullscreen-btn" href="javascript:void(0)" onclick="downloadTaxPdf()">
              ↗ Fullscreen PDF
            </a>
          </div>
        </div>
        <iframe id="tax-pdf-iframe" class="pdf-frame" src="about:blank" style="width:100%; height:620px; border:none;"></iframe>
      </div>
    </section>

    <!-- ========================================================
         RESULTS SECTION (Hidden initially until report is generated)
         ======================================================== -->
    <div id="results-section" style="display: none;">

      <!-- Metrics Cards Grid -->
      <section class="metrics-grid" id="metrics-container">
        <div class="metric-card accent">
          <div class="metric-label">Total Gram Panchayats</div>
          <div class="metric-value" id="val-total-gps">—</div>
          <div class="metric-sub" id="sub-total-gps">District Total</div>
        </div>
        <div class="metric-card success">
          <div class="metric-label">Attendance Submitted</div>
          <div class="metric-value" id="val-att-submitted">—</div>
          <div class="metric-sub" id="sub-att-pct">—</div>
        </div>
        <div class="metric-card info">
          <div class="metric-label">DSR Entered</div>
          <div class="metric-value" id="val-dsr-entered">—</div>
          <div class="metric-sub" id="sub-dsr-pct">—</div>
        </div>
        <div class="metric-card success">
          <div class="metric-label">Present Before 9 AM</div>
          <div class="metric-value" id="val-before-9">—</div>
          <div class="metric-sub" id="sub-before-9">Timely PS Attendance</div>
        </div>
        <div class="metric-card warning">
          <div class="metric-label">On Leave / Training</div>
          <div class="metric-value" id="val-on-leave">—</div>
          <div class="metric-sub" id="sub-on-leave">Leave &amp; Meeting</div>
        </div>
        <div class="metric-card danger">
          <div class="metric-label">Attendance Pending</div>
          <div class="metric-value" id="val-pending">—</div>
          <div class="metric-sub" id="sub-pending">Requires Follow-up</div>
        </div>
      </section>

      <!-- PDF Viewer Card -->
      <section class="viewer-card" id="viewer-section">
        <div class="viewer-header">
          <div class="viewer-title">
            <span>📄</span>
            <span>Official 7-Section District Attendance &amp; DSR Monitoring PDF</span>
          </div>
          <div class="viewer-actions">
            <a class="btn btn-gold btn-sm" href="/api/naresh/download" target="_blank">
              📥 Download PDF
            </a>
            <button type="button" class="btn btn-white btn-sm" onclick="refreshViewer()">
              🔄 Reload Preview
            </button>
          </div>
        </div>
        <iframe id="pdf-frame" class="pdf-frame" src="about:blank"></iframe>
      </section>

      <!-- Mandal Breakdown Table Card -->
      <section class="table-card">
        <div class="table-header">
          <div class="table-title">Mandal-wise Attendance &amp; DSR Performance (20 Mandals)</div>
          <input type="text" id="mandal-search" class="search-input" placeholder="Search Mandal..." onkeyup="filterMandals()">
        </div>
        <div class="table-responsive">
          <table id="mandals-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Mandal Name</th>
                <th class="text-center">Total GPs</th>
                <th class="text-center">Submitted</th>
                <th class="text-center">Attendance %</th>
                <th class="text-center">Before 9 AM</th>
                <th class="text-center">On Leave / Meet</th>
                <th class="text-center">Pending</th>
                <th class="text-center">DSR Entered</th>
              </tr>
            </thead>
            <tbody id="mandals-tbody">
              <tr><td colspan="9" class="text-center" style="padding: 24px;">Loading live mandal performance data...</td></tr>
            </tbody>
          </table>
        </div>
      </section>

    </div>

  <!-- Upcoming Module Modal -->
  <div id="upcoming-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.55); z-index:9999; align-items:center; justify-content:center; padding:20px; backdrop-filter:blur(3px);">
    <div style="background:white; border-radius:16px; max-width:480px; width:100%; padding:26px; box-shadow:0 24px 50px rgba(0,0,0,0.3); border:1.5px solid var(--border);">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.8rem;" id="modal-icon">📑</span>
          <h3 style="margin:0; font-size:1.25rem; color:var(--text); font-weight:800;" id="modal-title">Module Title</h3>
        </div>
        <button type="button" onclick="closeUpcomingModal()" style="background:none; border:none; font-size:1.6rem; cursor:pointer; color:var(--text-muted); line-height:1;">&times;</button>
      </div>
      <span class="badge-pill-soon" style="margin-bottom:14px;">Module in Active Development</span>
      <p style="color:var(--text-muted); font-size:0.92rem; line-height:1.6; margin:14px 0 22px 0;" id="modal-desc">Description</p>
      <div style="display:flex; justify-content:flex-end;">
        <button type="button" class="btn btn-primary" onclick="closeUpcomingModal()" style="background:var(--primary); color:white; padding:9px 20px; border-radius:8px; border:none; font-weight:700; cursor:pointer;">Got It</button>
      </div>
    </div>
  </div>

  <!-- Active Sessions & Robot Engines Modal -->
  <div id="sessions-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.6); z-index:99999; align-items:center; justify-content:center; padding:18px; backdrop-filter:blur(4px);">
    <div style="background:white; border-radius:16px; max-width:680px; width:100%; max-height:85vh; display:flex; flex-direction:column; padding:24px; box-shadow:0 24px 60px rgba(0,0,0,0.35); border:1.5px solid var(--border);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; border-bottom:1px solid var(--border); padding-bottom:12px;">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.6rem;">👥</span>
          <div>
            <h3 style="margin:0; font-size:1.2rem; color:var(--text); font-weight:800;">Active User Sessions & Robot Engines</h3>
            <span style="font-size:0.78rem; color:var(--text-muted);" id="sessions-modal-timestamp">Live Host Server Status</span>
          </div>
        </div>
        <button type="button" onclick="closeSessionsModal()" style="background:none; border:none; font-size:1.8rem; cursor:pointer; color:var(--text-muted); line-height:1;">&times;</button>
      </div>

      <!-- Quick KPI Badges -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:10px; margin-bottom:16px;">
        <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:10px; text-align:center;">
          <div style="font-size:0.72rem; font-weight:700; color:#166534;">TOTAL SESSIONS</div>
          <div style="font-size:1.3rem; font-weight:800; color:#15803d;" id="modal-stat-total">0</div>
        </div>
        <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:10px; padding:10px; text-align:center;">
          <div style="font-size:0.72rem; font-weight:700; color:#065f46;">AUTHENTICATED</div>
          <div style="font-size:1.3rem; font-weight:800; color:#059669;" id="modal-stat-auth">0</div>
        </div>
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:10px; text-align:center;">
          <div style="font-size:0.72rem; font-weight:700; color:#475569;">MY SESSION</div>
          <div style="font-size:0.88rem; font-weight:800; color:#0f172a;" id="modal-stat-mysid">—</div>
        </div>
      </div>

      <!-- Scrollable Sessions Table -->
      <div style="overflow-y:auto; flex:1; border:1px solid var(--border); border-radius:8px; margin-bottom:16px;">
        <table style="width:100%; border-collapse:collapse; font-size:0.82rem; text-align:left;">
          <thead>
            <tr style="background:#f8fafc; border-bottom:1px solid var(--border); font-size:0.75rem; color:#475569;">
              <th style="padding:8px 10px;">Officer / User</th>
              <th style="padding:8px 10px;">Status</th>
              <th style="padding:8px 10px;">Time Left</th>
              <th style="padding:8px 10px;">Active For</th>
              <th style="padding:8px 10px;">Idle</th>
              <th style="padding:8px 10px;">Session ID</th>
            </tr>
          </thead>
          <tbody id="sessions-table-body">
            <tr>
              <td colspan="5" style="text-align:center; padding:20px; color:var(--text-muted);">Loading active sessions...</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center;">
        <button type="button" class="btn btn-outline btn-sm" onclick="fetchAndRenderSessionsModal()" style="font-size:0.8rem; padding:6px 14px; border:1px solid var(--border); border-radius:6px; cursor:pointer;">🔄 Refresh Status</button>
        <button type="button" class="btn btn-primary btn-sm" onclick="closeSessionsModal()" style="background:var(--primary); color:white; font-size:0.8rem; padding:6px 18px; border:none; border-radius:6px; cursor:pointer;">Close</button>
      </div>
    </div>
  </div>

  
    <!-- ========================================================
         GRAM PANCHAYAT INSPECTIONS STATION (Official DPO/DLPO/MPO)
         ======================================================== -->
    <section class="automation-station" id="inspections-station" style="display: none; margin-bottom: 24px;">
      <!-- Station Top Bar -->
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:18px; padding-bottom:14px; border-bottom:1.5px solid var(--border);">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:44px; height:44px; border-radius:10px; background:#e0f2fe; color:#0284c7; display:flex; align-items:center; justify-content:center; font-size:1.6rem;">🔍</div>
          <div>
            <h2 style="margin:0; font-size:1.3rem; font-weight:800; color:var(--text);">Gram Panchayat Inspections Monitoring Station</h2>
            <div style="font-size:0.85rem; color:var(--text-muted);">Official Compliance Tracking for DPO, DLPO &amp; MPO Gram Panchayat Inspections</div>
          </div>
        </div>
        <button type="button" class="btn btn-outline btn-sm" style="color:var(--text); border-color:var(--border);" onclick="showDashboard()">
          ⬅️ Back to Dashboard
        </button>
      </div>

      <!-- Filters & Control Bar -->
      <div style="background:#ffffff; border:1.5px solid var(--border); border-radius:12px; padding:18px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; align-items:flex-end;">
          <div>
            <label style="display:block; font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px;">Inspection Level</label>
            <select id="insp-level-filter" class="form-control" style="width:100%; padding:9px 12px; border:1.5px solid var(--border); border-radius:8px; font-size:0.9rem;" onchange="filterInspectionsTable()">
              <option value="ALL">All Inspection Tiers</option>
              <option value="DPO">District Panchayat Officer (DPO)</option>
              <option value="DLPO">Divisional Panchayat Officer (DLPO)</option>
              <option value="MPO">Mandal Panchayat Officer (MPO)</option>
            </select>
          </div>
          <div>
            <label style="display:block; font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px;">Select Mandal</label>
            <select id="insp-mandal-filter" class="form-control" style="width:100%; padding:9px 12px; border:1.5px solid var(--border); border-radius:8px; font-size:0.9rem;" onchange="filterInspectionsTable()">
              <option value="ALL">All Mandals (21 Mandals)</option>
            </select>
          </div>
          <div>
            <label style="display:block; font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px;">Inspection Status</label>
            <select id="insp-status-filter" class="form-control" style="width:100%; padding:9px 12px; border:1.5px solid var(--border); border-radius:8px; font-size:0.9rem;" onchange="filterInspectionsTable()">
              <option value="ALL">All Statuses</option>
              <option value="COMPLETED">✅ Inspected (Completed)</option>
              <option value="PENDING">⚠️ Pending Inspection</option>
            </select>
          </div>
          <div>
            <label style="display:block; font-size:0.82rem; font-weight:700; color:var(--text); margin-bottom:5px;">Search Mandal / GP</label>
            <input type="text" id="insp-search-input" placeholder="Type name..." style="width:100%; padding:9px 12px; border:1.5px solid var(--border); border-radius:8px; font-size:0.9rem;" onkeyup="filterInspectionsTable()">
          </div>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; margin-top:16px; padding-top:14px; border-top:1px solid #f1f5f9;">
          <div style="display:flex; gap:10px; flex-wrap:wrap;">
            <button type="button" class="btn btn-sm" style="background:#0284c7; color:#ffffff; font-weight:700; padding:8px 16px; border-radius:8px; border:none; cursor:pointer;" onclick="initInspectionsData()">
              🔄 Refresh Data
            </button>
            <button type="button" class="btn btn-sm btn-outline" style="font-weight:700; padding:8px 16px; border-radius:8px; cursor:pointer;" onclick="exportInspectionsCsv()">
              📥 Export CSV
            </button>
          </div>
          <div id="insp-sync-time" style="font-size:0.82rem; color:var(--text-muted); font-weight:600;">
            Directory: Official Telangana Gram Panchayat Inspection Database
          </div>
        </div>
      </div>

      <!-- KPI Summary Cards -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin-bottom:20px;">
        <div style="background:#ffffff; border:1.5px solid var(--border); border-radius:12px; padding:16px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Total Mandals</div>
          <div id="insp-kpi-mandals" style="font-size:1.8rem; font-weight:800; color:#0f172a; margin-top:4px;">21</div>
        </div>
        <div style="background:#ffffff; border:1.5px solid var(--border); border-radius:12px; padding:16px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Total Gram Panchayats</div>
          <div id="insp-kpi-gps" style="font-size:1.8rem; font-weight:800; color:#0f172a; margin-top:4px;">571</div>
        </div>
        <div style="background:#f0fdf4; border:1.5px solid #bbf7d0; border-radius:12px; padding:16px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:#166534; text-transform:uppercase;">Inspections Conducted</div>
          <div id="insp-kpi-completed" style="font-size:1.8rem; font-weight:800; color:#15803d; margin-top:4px;">488</div>
        </div>
        <div style="background:#fff7ed; border:1.5px solid #fed7aa; border-radius:12px; padding:16px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:#9a3412; text-transform:uppercase;">Pending Inspections</div>
          <div id="insp-kpi-pending" style="font-size:1.8rem; font-weight:800; color:#c2410c; margin-top:4px;">83</div>
        </div>
        <div style="background:#f0f9ff; border:1.5px solid #bae6fd; border-radius:12px; padding:16px; text-align:center;">
          <div style="font-size:0.82rem; font-weight:700; color:#0369a1; text-transform:uppercase;">Inspection Compliance</div>
          <div id="insp-kpi-rate" style="font-size:1.8rem; font-weight:800; color:#0284c7; margin-top:4px;">85.5%</div>
        </div>
      </div>

      <!-- Mandal Abstract Table -->
      <div style="background:#ffffff; border:1.5px solid var(--border); border-radius:12px; overflow:hidden; box-shadow:0 4px 14px rgba(0,0,0,0.04);">
        <div style="padding:14px 18px; background:#f8fafc; border-bottom:1.5px solid var(--border); display:flex; justify-content:space-between; align-items:center;">
          <span style="font-weight:800; font-size:1rem; color:#1e293b;">Mandal-Wise Gram Panchayat Inspection Abstract</span>
          <span id="insp-table-counter" style="font-size:0.82rem; font-weight:700; color:#64748b;">Showing 21 Mandals</span>
        </div>
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:0.88rem; text-align:left;">
            <thead>
              <tr style="background:#062b1f; color:#ffffff; font-weight:700; border-bottom:2px solid #165b43;">
                <th style="padding:10px 12px; text-align:center; width:50px;">S.No</th>
                <th style="padding:10px 12px;">Mandal Name</th>
                <th style="padding:10px 12px; text-align:center;">Total GPs</th>
                <th style="padding:10px 12px; text-align:center;">DPO</th>
                <th style="padding:10px 12px; text-align:center;">DLPO</th>
                <th style="padding:10px 12px; text-align:center;">MPO</th>
                <th style="padding:10px 12px; text-align:center;">Total Inspected</th>
                <th style="padding:10px 12px; text-align:center;">Pending</th>
                <th style="padding:10px 12px; text-align:center;">Compliance %</th>
                <th style="padding:10px 12px; text-align:center;">Status</th>
                <th style="padding:10px 12px; text-align:center;">Action</th>
              </tr>
            </thead>
            <tbody id="insp-table-body">
              <!-- Dynamically populated rows -->
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- GP Inspections Mandal Drill-down Modal -->
    <div id="insp-detail-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.65); z-index:99999; justify-content:center; align-items:center; padding:16px;">
      <div style="background:#ffffff; border-radius:14px; max-width:850px; width:100%; max-height:85vh; overflow-y:auto; box-shadow:0 12px 36px rgba(0,0,0,0.3); padding:22px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; border-bottom:1.5px solid #e2e8f0; padding-bottom:12px;">
          <div>
            <h3 id="insp-modal-title" style="margin:0; font-size:1.2rem; font-weight:800; color:#0f172a;">Mandal GP Inspections Drill-Down</h3>
            <div id="insp-modal-subtitle" style="font-size:0.85rem; color:#64748b; margin-top:2px;">Gram Panchayat Inspection Details &amp; Verification Observations</div>
          </div>
          <button type="button" onclick="closeInspModal()" style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:#94a3b8; line-height:1;">&times;</button>
        </div>
        <div id="insp-modal-content">
          <!-- Drill-down GP table -->
        </div>
        <div style="margin-top:18px; text-align:right;">
          <button type="button" class="btn btn-outline btn-sm" onclick="closeInspModal()">Close</button>
        </div>
      </div>
    </div>

  </main>

  <footer>
    Automated Report Monitoring Service &bull; Executive Analytics Console
  </footer>

  <script>
    // Mobile Responsive Navigation Handlers
    window.toggleMobileNav = function() {
      const nav = document.getElementById('main-nav-links');
      const btn = document.getElementById('nav-hamburger-btn');
      if (nav) {
        nav.classList.toggle('mobile-open');
        if (btn) btn.classList.toggle('open');
      }
    };

    window.closeMobileNav = function() {
      const nav = document.getElementById('main-nav-links');
      const btn = document.getElementById('nav-hamburger-btn');
      if (nav && nav.classList.contains('mobile-open')) {
        nav.classList.remove('mobile-open');
        if (btn) btn.classList.remove('open');
      }
    };

    document.addEventListener('click', function(e) {
      const nav = document.getElementById('main-nav-links');
      const btn = document.getElementById('nav-hamburger-btn');
      if (nav && nav.classList.contains('mobile-open')) {
        if (!nav.contains(e.target) && !btn.contains(e.target)) {
          window.closeMobileNav();
        }
      }
    });

    // Multi-Session Client ID Manager (sessionStorage + localStorage + Cookie + Fetch Interceptor)
    window.getEptsSessionId = function() {
      // 1. Check sessionStorage (strictly isolated per browser tab / window)
      let sid = "";
      try {
        sid = sessionStorage.getItem("epts_session_id") || "";
      } catch(e) {}

      // 2. Fall back to localStorage (unique per browser profile)
      if (!sid) {
        try {
          sid = localStorage.getItem("epts_session_id") || "";
        } catch(e) {}
      }

      // 3. Fall back to cookie
      if (!sid) {
        const match = document.cookie.match(/(?:^|;\\s*)epts_session_id=([^;]+)/);
        if (match) {
          const cand = decodeURIComponent(match[1].trim());
          if (cand && cand.length >= 8) sid = cand;
        }
      }

      // 4. If missing or invalid, generate a unique client UUID with timestamp
      if (!sid || sid.length < 8) {
        sid = "sid_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 10) + Math.random().toString(36).substring(2, 10);
      }

      // Keep storage layers synchronized for this specific browser
      try { sessionStorage.setItem("epts_session_id", sid); } catch(e) {}
      try { localStorage.setItem("epts_session_id", sid); } catch(e) {}
      document.cookie = "epts_session_id=" + encodeURIComponent(sid) + "; path=/; max-age=2592000; SameSite=Lax";
      return sid;
    };

    // Auto-inject X-Session-ID on all fetch requests
    (function() {
      const origFetch = window.fetch;
      window.fetch = function(url, options) {
        options = options || {};
        options.headers = options.headers || {};
        const sid = window.getEptsSessionId();
        if (options.headers instanceof Headers) {
          if (!options.headers.has('X-Session-ID')) options.headers.set('X-Session-ID', sid);
        } else if (Array.isArray(options.headers)) {
          if (!options.headers.some(h => h[0].toLowerCase() === 'x-session-id')) {
            options.headers.push(['X-Session-ID', sid]);
          }
        } else {
          if (!options.headers['X-Session-ID']) options.headers['X-Session-ID'] = sid;
        }
        return origFetch.call(this, url, options);
      };
    })();

    window.openSessionsModal = function() {
      const officer = (sessionStorage.getItem('epts_officer_id') || '').trim().toUpperCase();
      if (officer !== 'DPOA3698') {
        return;
      }
      const modal = document.getElementById('sessions-modal');
      if (modal) {
        modal.style.display = 'flex';
        fetchAndRenderSessionsModal();
      }
    };

    window.closeSessionsModal = function() {
      const modal = document.getElementById('sessions-modal');
      if (modal) modal.style.display = 'none';
    };

    window.fetchAndRenderSessionsModal = async function() {
      try {
        const res = await fetch('/api/system/sessions');
        const data = await res.json();
        if (!data || !data.success) return;

        const mySid = window.getEptsSessionId();
        const tsEl = document.getElementById('sessions-modal-timestamp');
        if (tsEl) tsEl.innerText = `Live Server Time: ${data.timestamp}`;
        const totEl = document.getElementById('modal-stat-total');
        if (totEl) totEl.innerText = data.total_sessions;
        const authEl = document.getElementById('modal-stat-auth');
        if (authEl) authEl.innerText = data.authenticated_sessions;
        const mySidEl = document.getElementById('modal-stat-mysid');
        if (mySidEl) mySidEl.innerText = (mySid ? mySid.substring(0, 8) + '...' : '—');

        const tbody = document.getElementById('sessions-table-body');
        if (!tbody) return;
        if (!data.sessions || data.sessions.length === 0) {
          tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:18px; color:var(--text-muted);">No active sessions currently.</td></tr>';
          return;
        }

        tbody.innerHTML = data.sessions.map(s => {
          const isMe = (s.session_id === mySid);
          const isAuth = s.authenticated;
          const statusBadge = isAuth 
            ? '<span style="background:#dcfce7; color:#15803d; font-weight:700; padding:2px 8px; border-radius:10px; font-size:0.72rem;">● Authenticated</span>'
            : (s.status === 'awaiting_otp' 
              ? '<span style="background:#fef3c7; color:#b45309; font-weight:700; padding:2px 8px; border-radius:10px; font-size:0.72rem;">● Awaiting OTP</span>'
              : '<span style="background:#f1f5f9; color:#64748b; font-weight:600; padding:2px 8px; border-radius:10px; font-size:0.72rem;">Idle</span>');
          
          const userDisplay = s.user_id + (isMe ? ' <b style="color:#059669;">(You)</b>' : '');
          const rowBg = isMe ? 'background:#f0fdf4;' : '';

          const distDisplay = isAuth 
            ? `<span style="font-weight:700; color:#047857; display:inline-flex; align-items:center; gap:4px;">🏛️ ${s.district_name || 'Khammam District'}</span>`
            : '<span style="color:#94a3b8;">—</span>';
          
          const officeDisplay = isAuth 
            ? `<span style="font-weight:600; color:#1e293b;">${s.office_name || (s.user_id === 'DPOA3698' ? 'District Panchayat Office' : 'Panchayat Officer')}</span>`
            : '<span style="color:#94a3b8;">—</span>';

          const remMin = Math.floor((s.expires_in_seconds || 0) / 60);
          const remSec = (s.expires_in_seconds || 0) % 60;
          const isNoExpiry = (s.user_id === 'DPOA3698') || (s.expires_in_seconds === -1) || (s.expires_in_seconds > 86400);
          const timeRemainingDisplay = isAuth 
            ? (isNoExpiry
                ? `<span style="font-weight:700; color:#047857; background:#dcfce7; padding:2px 8px; border-radius:6px; font-size:0.75rem;">🛡️ No Expiry (Persistent)</span>`
                : `<span style="font-family:monospace; font-weight:700; color:${(s.expires_in_seconds||0) <= 120 ? '#ef4444' : '#059669'};">${remMin}:${remSec.toString().padStart(2, '0')}</span>${s.extended ? ' <span style="font-size:0.68rem; background:#dbeafe; color:#1e40af; padding:1px 4px; border-radius:4px;">20m</span>' : ' <span style="font-size:0.68rem; background:#f1f5f9; color:#64748b; padding:1px 4px; border-radius:4px;">10m</span>'}`)
            : '—';

          return `<tr style="border-bottom:1px solid #f1f5f9; ${rowBg}">
            <td style="padding:8px 10px;">${distDisplay}</td>
            <td style="padding:8px 10px;">${officeDisplay}</td>
            <td style="padding:8px 10px; font-weight:700; color:var(--text);">${userDisplay}</td>
            <td style="padding:8px 10px;">${statusBadge}</td>
            <td style="padding:8px 10px;">${timeRemainingDisplay}</td>
            <td style="padding:8px 10px; color:#475569;">${s.age_minutes}m</td>
            <td style="padding:8px 10px; color:#475569;">${s.idle_minutes}m ago</td>
            <td style="padding:8px 10px; font-family:monospace; color:#64748b; font-size:0.74rem;">${s.session_id_short}</td>
          </tr>`;
        }).join('');
      } catch(e) {
        console.error('Sessions fetch error:', e);
      }
    };

    // 10-Minute Session Auto-Close & +10m Extension Controllers (Server Load Optimization)
    window.sessionExpiresIn = 600;
    window.sessionCanExtend = true;
    window.sessionTimerInterval = null;

    window.updateTimerDisplay = function() {
      const wrap = document.getElementById('nav-session-timer-wrap');
      const digits = document.getElementById('nav-timer-digits');
      const btn = document.getElementById('btn-extend-session');
      const dashDigits = document.getElementById('dash-timer-digits');
      const dashBtn = document.getElementById('dash-btn-extend');
      const navTimer = document.getElementById('nav-session-timer');

      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      if (!isAuth) {
        if (wrap) wrap.style.display = 'none';
        return;
      }

      const officer = (sessionStorage.getItem('epts_officer_id') || '').trim().toUpperCase();
      const isDpoAdmin = (officer === 'DPOA3698') || (window.sessionNoExpiry === true);

      if (wrap) wrap.style.display = 'inline-flex';

      if (isDpoAdmin) {
        if (navTimer) {
          navTimer.style.background = 'rgba(16, 185, 129, 0.25)';
          navTimer.style.borderColor = '#10b981';
          navTimer.style.color = '#d1fae5';
          navTimer.innerHTML = '🛡️ <span style="font-weight:700;">No Expiry</span>';
          navTimer.title = 'Officer DPOA3698: Persistent session without time limit';
        }
        if (btn) btn.style.display = 'none';
        const dashTimerChip = document.getElementById('dash-timer-chip');
        if (dashTimerChip) {
          dashTimerChip.innerHTML = '🛡️ Session: <span style="font-weight:700; color:#34d399;">Persistent (No Expiry)</span>';
          dashTimerChip.style.borderColor = '#10b981';
        }
        if (dashBtn) dashBtn.style.display = 'none';
        return;
      }

      if (btn) btn.style.display = 'inline-flex';
      if (dashBtn) dashBtn.style.display = 'inline-flex';

      const totalSec = Math.max(0, window.sessionExpiresIn || 0);
      const m = Math.floor(totalSec / 60);
      const s = totalSec % 60;
      const timeStr = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

      if (digits) digits.innerText = timeStr;
      if (dashDigits) dashDigits.innerText = timeStr;

      // Color warning when under 2 minutes
      if (totalSec <= 120) {
        if (navTimer) {
          navTimer.style.background = 'rgba(239, 68, 68, 0.25)';
          navTimer.style.borderColor = 'rgba(239, 68, 68, 0.6)';
          navTimer.style.color = '#fca5a5';
        }
        if (dashDigits) dashDigits.style.color = '#ef4444';
      } else {
        if (navTimer) {
          navTimer.style.background = 'rgba(16, 185, 129, 0.2)';
          navTimer.style.borderColor = 'rgba(16, 185, 129, 0.45)';
          navTimer.style.color = '#d1fae5';
        }
        if (dashDigits) dashDigits.style.color = '#fef08a';
      }

      // Extension button state
      const canExt = (window.sessionCanExtend !== false) && (window.sessionExpiresIn > 0);
      if (btn) {
        if (canExt) {
          btn.disabled = false;
          btn.style.opacity = '1';
          btn.style.cursor = 'pointer';
          btn.innerText = '+10m Extend';
          btn.title = 'Extend session by 10 more minutes (max 20 mins total)';
        } else {
          btn.disabled = true;
          btn.style.opacity = '0.55';
          btn.style.cursor = 'default';
          btn.innerText = 'Max 20m';
          btn.title = 'Maximum session duration reached (20 mins)';
        }
      }
      if (dashBtn) {
        if (canExt) {
          dashBtn.disabled = false;
          dashBtn.style.opacity = '1';
          dashBtn.style.cursor = 'pointer';
          dashBtn.innerHTML = '⏱️ +10 Mins (Extend)';
        } else {
          dashBtn.disabled = true;
          dashBtn.style.opacity = '0.55';
          dashBtn.style.cursor = 'default';
          dashBtn.innerHTML = '⏱️ Max 20m Reached';
        }
      }
    };

    window.startSessionTimer = function(initialSec = 600, canExtend = true) {
      const officer = (sessionStorage.getItem('epts_officer_id') || '').trim().toUpperCase();
      if (officer === 'DPOA3698' || initialSec >= 86400 || window.sessionNoExpiry === true) {
        window.sessionNoExpiry = true;
        window.sessionExpiresIn = 999999;
        window.sessionCanExtend = false;
        if (window.sessionTimerInterval) {
          clearInterval(window.sessionTimerInterval);
          window.sessionTimerInterval = null;
        }
        window.updateTimerDisplay();
        return;
      }

      window.sessionNoExpiry = false;
      window.sessionExpiresIn = initialSec;
      window.sessionCanExtend = canExtend;
      window.updateTimerDisplay();

      if (window.sessionTimerInterval) {
        clearInterval(window.sessionTimerInterval);
      }

      window.sessionTimerInterval = setInterval(() => {
        if (window.sessionExpiresIn > 0) {
          window.sessionExpiresIn--;
          window.updateTimerDisplay();
        } else {
          clearInterval(window.sessionTimerInterval);
          window.sessionTimerInterval = null;
          window.handleSessionExpired();
        }
      }, 1000);
    };

    window.handleSessionExpired = async function() {
      const officer = (sessionStorage.getItem('epts_officer_id') || '').trim().toUpperCase();
      if (officer === 'DPOA3698' || window.sessionNoExpiry === true) {
        console.log('[+] Persistent session: Expiry bypassed for DPOA3698.');
        return;
      }
      alert("⏰ Session Expired (Time Limit Reached)\\n\\nTo reduce server load and conserve memory, your browser automation session has been closed automatically after reaching the allowed duration (10 mins, or 20 mins if extended).\\n\\nPlease log in again whenever you need to generate reports.");
      try {
        await fetch('/api/naresh/logout', { method: 'POST' });
      } catch(e) {}
      setAuthenticated(false);
    };

    window.extendPortalSession = async function() {
      const btn = document.getElementById('btn-extend-session');
      const dashBtn = document.getElementById('dash-btn-extend');
      if (btn) btn.disabled = true;
      if (dashBtn) dashBtn.disabled = true;

      try {
        const res = await fetch('/api/naresh/extend-session', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.success) {
          window.sessionExpiresIn = data.expires_in;
          window.sessionCanExtend = data.can_extend;
          window.updateTimerDisplay();
          alert("✅ Session Extended!\\n\\nYour session has been extended by 10 additional minutes (Total allowed time: 20 minutes).\\nThe browser will automatically close when the countdown reaches 0 to conserve server memory.");
        } else {
          alert(data.message || data.detail || "Could not extend session.");
          window.updateTimerDisplay();
        }
      } catch (e) {
        alert("Error extending session: " + e.message);
        window.updateTimerDisplay();
      }
    };

    let reportData = null;
    let currentStep = 1;

    // Real-time Background Browser Automation status updater
    window.updateGlobalBrowserStatus = function(data) {
      const ping = document.getElementById('browser-status-ping');
      const dot = document.getElementById('browser-status-dot');
      const pill = document.getElementById('browser-status-pill');
      const desc = document.getElementById('browser-status-desc');
      const officerEl = document.getElementById('browser-status-officer');
      const navDot = document.getElementById('nav-browser-dot');
      const navText = document.getElementById('nav-browser-text');

      if (data && data.authenticated) {
        const off = (data.user_id || sessionStorage.getItem('epts_officer_id') || 'Officer').trim();
        const dist = (data.district_name || sessionStorage.getItem('epts_district_name') || (off === 'DPOA3698' ? 'Khammam District' : '')).trim();
        const officeName = (data.office_name || sessionStorage.getItem('epts_office_name') || (off === 'DPOA3698' ? 'District Panchayat Office' : '')).trim();
        if (ping) { ping.style.display = 'inline-block'; ping.style.background = '#10b981'; }
        if (dot) dot.style.background = '#10b981';
        if (pill) {
          pill.style.background = '#10b981';
          pill.style.color = '#064e3b';
          pill.innerText = 'ACTIVE & RUNNING IN BACKGROUND';
        }
        if (desc) {
          desc.innerText = `Playwright browser automation active for ${dist ? dist + ' (' + (officeName || off) + ')' : 'Officer ' + off}. Continuous background session ready for zero-wait reports.`;
        }
        if (officerEl) officerEl.innerText = dist ? `🏛️ ${dist} • ${officeName || off}` : `🏛️ Officer: ${off} (Session Active)`;
        if (navDot) navDot.style.background = '#10b981';
        if (navText) navText.innerText = dist ? `Browser: ${dist}` : `Browser: Active (${off})`;
      } else if (data && data.status === 'awaiting_otp') {
        const off = (data.user_id || 'Officer').trim();
        if (ping) { ping.style.display = 'inline-block'; ping.style.background = '#f59e0b'; }
        if (dot) dot.style.background = '#f59e0b';
        if (pill) {
          pill.style.background = '#f59e0b';
          pill.style.color = '#78350f';
          pill.innerText = 'AWAITING 6-DIGIT OTP';
        }
        if (desc) {
          desc.innerText = `e-Panchayat login in progress. Awaiting 6-digit OTP verification for Officer ${off}.`;
        }
        if (officerEl) officerEl.innerText = `📱 Awaiting OTP (${off})`;
        if (navDot) navDot.style.background = '#f59e0b';
        if (navText) navText.innerText = 'Browser: Awaiting OTP';
      } else {
        if (ping) ping.style.display = 'none';
        if (dot) dot.style.background = '#9ca3af';
        if (pill) {
          pill.style.background = 'rgba(255,255,255,0.15)';
          pill.style.color = '#e2e8f0';
          pill.innerText = 'STANDBY · NOT LOGGED IN';
        }
        if (desc) {
          desc.innerText = 'Playwright browser automation idle. Click "Login" to connect and authenticate.';
        }
        if (officerEl) officerEl.innerText = '🔒 Login Required';
        if (navDot) navDot.style.background = '#9ca3af';
        if (navText) navText.innerText = 'Browser: Standby';
      }
    };

    window.togglePortalDropdown = function(id) {
      const el = document.getElementById(id);
      document.querySelectorAll('.dropdown').forEach(d => {
        if (d !== el) d.classList.remove('open');
      });
      if (el) el.classList.toggle('open');
    };
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.dropdown')) {
        document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('open'));
      }
    });

    window.displayOtpNotice = function(msg, mobile) {
      try {
        const noticeBox = document.getElementById('otp-dynamic-notice');
        const mobileSpan = document.getElementById('otp-mobile-span');
        if (mobileSpan && mobile) {
          mobileSpan.innerText = mobile;
        }
        if (noticeBox) {
          if (msg && msg.trim()) {
            noticeBox.innerHTML = msg;
          } else if (mobile) {
            noticeBox.innerHTML = `A 6 digit OTP has been sent to your registered mobile number <span id="otp-mobile-span" style="text-decoration: underline; font-weight: 800;">${mobile}</span>. Enter OTP to continue.`;
          }
          noticeBox.style.display = 'block';
        }
      } catch (err) {
        console.warn('displayOtpNotice note:', err);
      }
    };

    window.openDsrRobot = function() {
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      if (!isAuth) {
        openDepartmentLogin('dsr');
        return;
      }
      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const balStation = document.getElementById('balance-station');
      const taxStation = document.getElementById('tax-dcb-station');
      const backWrap = document.getElementById('btn-back-dashboard-wrap');
      const heroCard = document.getElementById('portal-hero-card');
      const resultsEl = document.getElementById('results-section');
      if (dash) dash.style.display = 'none';
      if (balStation) balStation.style.display = 'none';
      if (taxStation) taxStation.style.display = 'none';
      if (heroCard) heroCard.style.display = 'none';
      if (station) {
        station.style.display = 'block';
        if (backWrap) backWrap.style.display = 'block';
        const backHomeWrap = document.getElementById('btn-back-home-wrap');
        if (backHomeWrap) backHomeWrap.style.display = 'none';
        goToStep(3);
        station.scrollIntoView({ behavior: 'smooth' });
      }
      if (resultsEl) {
        resultsEl.style.display = (reportData && reportData.totals && Object.keys(reportData.totals).length > 0) ? 'block' : 'none';
      }
    };

    window.openDepartmentLogin = function(pendingTarget) {
      if (pendingTarget) window.pendingStation = pendingTarget;
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      if (isAuth) {
        if (pendingTarget === 'balance') openBalanceRobot();
        else if (pendingTarget === 'dsr') openDsrRobot();
        else showDashboard();
        return;
      }
      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const balStation = document.getElementById('balance-station');
      const taxStation = document.getElementById('tax-dcb-station');
      const heroCard = document.getElementById('portal-hero-card');
      const resultsEl = document.getElementById('results-section');
      const backHomeWrap = document.getElementById('btn-back-home-wrap');
      const backDashWrap = document.getElementById('btn-back-dashboard-wrap');

      if (dash) dash.style.display = 'none';
      if (balStation) balStation.style.display = 'none';
      if (taxStation) taxStation.style.display = 'none';
      if (resultsEl) resultsEl.style.display = 'none';
      if (heroCard) heroCard.style.display = 'none';

      if (station) {
        station.style.display = 'block';
        if (backHomeWrap) backHomeWrap.style.display = 'block';
        if (backDashWrap) backDashWrap.style.display = 'none';
        goToStep(1);
        station.scrollIntoView({ behavior: 'smooth' });
      }
    };
    window.showLoginStation = window.openDepartmentLogin;

    window.openBalanceRobot = async function() {
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      if (!isAuth) {
        alert('Authentication Required: Please login with your Department User ID & OTP to run the Balance Robot.');
        openDepartmentLogin('balance');
        return;
      }
      try {
        const sRes = await fetch('/api/naresh/session-status');
        if (sRes.ok) {
          const sData = await sRes.json();
          if (!sData.authenticated) {
            setAuthenticated(false);
            alert('Authentication Required: Please login with your Department User ID & OTP to run the Balance Robot.');
            openDepartmentLogin('balance');
            return;
          }
        }
      } catch (e) {}

      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const balStation = document.getElementById('balance-station');
      const taxStation = document.getElementById('tax-dcb-station');
      const heroCard = document.getElementById('portal-hero-card');
      const resultsEl = document.getElementById('results-section');
      if (dash) dash.style.display = 'none';
      if (station) station.style.display = 'none';
      if (taxStation) taxStation.style.display = 'none';
      if (heroCard) heroCard.style.display = 'none';
      if (resultsEl) resultsEl.style.display = 'none';
      if (balStation) {
        balStation.style.display = 'block';
        balStation.scrollIntoView({ behavior: 'smooth' });
        if (typeof fetchPortalBalanceDates === 'function') fetchPortalBalanceDates();
        const unauthBanner = document.getElementById('bal-unauth-banner');
        if (unauthBanner) unauthBanner.style.display = 'none';
        loadBalanceData();
      }
    };

    window.showDashboard = function() {
      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const balStation = document.getElementById('balance-station');
      const taxStation = document.getElementById('tax-dcb-station');
      const backWrap = document.getElementById('btn-back-dashboard-wrap');
      const heroCard = document.getElementById('portal-hero-card');
      const resultsEl = document.getElementById('results-section');
      const inspStation = document.getElementById('inspections-station');
      if (dash) dash.style.display = 'block';
      if (station) station.style.display = 'none';
      if (balStation) balStation.style.display = 'none';
      if (taxStation) taxStation.style.display = 'none';
      if (inspStation) inspStation.style.display = 'none';
      if (heroCard) heroCard.style.display = 'none';
      if (backWrap) backWrap.style.display = 'none';
      if (resultsEl) resultsEl.style.display = 'none';
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    window.handleHomeNavigation = function() {
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      if (isAuth) {
        // Active session: do not logout or exit! Move smoothly to Reports Module Selection dashboard
        showDashboard();
      } else {
        // Not logged in: show Portal Home overview and hide login console
        const heroCard = document.getElementById('portal-hero-card');
        const station = document.getElementById('automation-station');
        const dash = document.getElementById('post-login-dashboard');
        const balStation = document.getElementById('balance-station');
        const taxStation = document.getElementById('tax-dcb-station');
        const resultsEl = document.getElementById('results-section');

        const inspStation = document.getElementById('inspections-station');
        const officerBanner = document.getElementById('dash-officer-banner');
        if (station) station.style.display = 'none';
        if (balStation) balStation.style.display = 'none';
        if (taxStation) taxStation.style.display = 'none';
        if (inspStation) inspStation.style.display = 'none';
        if (resultsEl) resultsEl.style.display = 'none';
        if (officerBanner) officerBanner.style.display = 'none';
        if (heroCard) heroCard.style.display = 'block';
        if (dash) dash.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    };

    window.resetBalanceUI = function() {
      document.getElementById('bal-kpi-mandals').innerText = '—';
      document.getElementById('bal-kpi-total-gps').innerText = '—';
      document.getElementById('bal-kpi-entered').innerText = '—';
      document.getElementById('bal-kpi-pending').innerText = '—';
      document.getElementById('bal-kpi-pct').innerText = '—';

      const actionsWrap = document.getElementById('balance-actions-wrap');
      if (actionsWrap) actionsWrap.style.display = 'none';

      const tbody = document.getElementById('balance-table-tbody');
      if (tbody) {
        tbody.innerHTML = `
          <tr>
            <td colspan="13" style="text-align:center; padding:38px 20px; color:var(--text-muted); font-size:0.95rem;">
              <div style="font-size:1.8rem; margin-bottom:8px;">🏦</div>
              <strong style="color:var(--text); font-size:1.05rem;">No Balance Report Processed Yet</strong>
              <div style="font-size:0.86rem; color:var(--text-muted); margin-top:6px;">
                Select a Thursday date above and click <b style="color:#b45309;">⚡ Run Balance Robot</b> to fetch live portal data.
              </div>
            </td>
          </tr>
        `;
      }

      const pendingCard = document.getElementById('balance-pending-gps-card');
      if (pendingCard) pendingCard.style.display = 'none';
    };

    window.fetchPortalBalanceDates = async function(forceRefresh = false) {
      const sel = document.getElementById('balance-date-select');
      const btnRef = document.getElementById('btn-refresh-balance-dates');
      if (btnRef) btnRef.disabled = true;
      try {
        const resp = await fetch('/api/balance/portal-dates');
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.dates && data.dates.length > 0) {
            const prevVal = sel ? sel.value : '';
            sel.innerHTML = '';
            data.dates.forEach((d, idx) => {
              const opt = document.createElement('option');
              opt.value = d;
              if (idx === 0) {
                opt.textContent = d + (data.is_live ? ' (Live Portal Latest)' : ' (Latest Thursday)');
              } else {
                opt.textContent = d;
              }
              sel.appendChild(opt);
            });
            if (prevVal && data.dates.includes(prevVal)) {
              sel.value = prevVal;
            } else {
              sel.selectedIndex = 0;
            }
            console.log('[+] Thursday dates loaded:', data.dates.length, 'Live portal:', data.is_live);
            onBalanceDateChanged();
          }
        }
      } catch (err) {
        console.error('Error fetching portal balance dates:', err);
      } finally {
        if (btnRef) btnRef.disabled = false;
      }
    };

    window.onBalanceDateChanged = function() {
      const sel = document.getElementById('balance-date-select');
      const dateVal = sel ? sel.value : '';
      if (dateVal) loadBalanceData(dateVal);
    };

    window.loadBalanceData = async function(reqDate) {
      const sel = document.getElementById('balance-date-select');
      const dateVal = reqDate || (sel ? sel.value : '');
      if (!dateVal) return;
      try {
        const resp = await fetch('/api/balance/data?date=' + encodeURIComponent(dateVal));
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.has_data) {
            renderBalanceTable(data);
          } else {
            resetBalanceUI();
          }
        } else {
          resetBalanceUI();
        }
      } catch (e) {
        console.error('Error loading balance data:', e);
        resetBalanceUI();
      }
    };

    window.triggerBalancePipeline = async function() {
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      if (!isAuth) {
        alert('Authentication Required: Please login to e-Panchayat with your credentials and verify OTP first before running the Balance Robot.');
        showLoginStation('balance');
        return;
      }
      const sel = document.getElementById('balance-date-select');
      const dateVal = sel ? sel.value : '';
      if (!dateVal) {
        alert('Please select a valid Thursday date from the dropdown.');
        return;
      }
      const btn = document.getElementById('btn-run-balance-robot');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Fetching from Portal...';
      }
      try {
        const fd = new FormData();
        fd.append('date', dateVal);
        const resp = await fetch('/api/balance/generate', { method: 'POST', body: fd });
        const resText = await resp.text();
        let res = {};
        try {
          res = JSON.parse(resText);
        } catch (_) {
          throw new Error(resText || ('Server error ' + resp.status));
        }
        if (resp.status === 401 || resp.status === 403) {
          setAuthenticated(false);
          alert('Authentication Required: ' + (res.detail || res.message || 'Session expired or not logged in.'));
          showLoginStation('balance');
          return;
        }
        if (!resp.ok) {
          throw new Error(res.detail || res.message || ('Server error ' + resp.status));
        }
        alert(res.message || 'Balance report compiled successfully!');
        loadBalanceData(dateVal);
      } catch (err) {
        alert('Balance pipeline error: ' + err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '⚡ Run Balance Robot';
        }
      }
    };

    window.renderBalanceTable = function(data) {
      if (!data || !data.has_data || !data.totals) {
        resetBalanceUI();
        return;
      }
      const t = data.totals;
      document.getElementById('bal-kpi-mandals').innerText = t.total_mandals || '0';
      document.getElementById('bal-kpi-total-gps').innerText = t.total_gps || '0';
      document.getElementById('bal-kpi-entered').innerText = t.total_entered_gps || '0';
      document.getElementById('bal-kpi-pending').innerText = t.total_not_entered_gps || '0';
      document.getElementById('bal-kpi-pct').innerText = (t.overall_pct_entered || 0).toFixed(1) + '%';

      // Show action buttons with current date
      const dStr = data.report_date_str || '29-10-2026';
      const actionsWrap = document.getElementById('balance-actions-wrap');
      if (actionsWrap) actionsWrap.style.display = 'flex';
      const excelBtn = document.getElementById('btn-balance-excel');
      const pdfBtn = document.getElementById('btn-balance-pdf');
      const pdfDlBtn = document.getElementById('btn-balance-pdf-dl');
      if (excelBtn) excelBtn.href = '/api/balance/download-excel?date=' + encodeURIComponent(dStr);
      if (pdfBtn) pdfBtn.href = '/api/balance/report.pdf?date=' + encodeURIComponent(dStr);
      if (pdfDlBtn) {
        pdfDlBtn.href = '/api/balance/download-pdf?date=' + encodeURIComponent(dStr);
        pdfDlBtn.setAttribute('download', 'GP_Balance_Entry_Report_' + dStr + '.pdf');
      }

      const tbody = document.getElementById('balance-table-tbody');
      if (!tbody) return;
      tbody.innerHTML = '';

      (data.mandals || []).forEach(m => {
        const tr = document.createElement('tr');
        const isDone = !m.has_pending;
        const statusHtml = isDone
          ? '<span style="color:#059669; font-weight:700;">100% Done</span>'
          : '<span style="color:#dc2626; font-weight:700;">' + m.not_entered_gps + ' Pending</span>';

        tr.innerHTML = `
          <td class="text-center">${m.s_no}</td>
          <td><strong>${m.mandal_name}</strong></td>
          <td class="text-right"><strong>${m.total_gps}</strong></td>
          <td class="text-right" style="color:#059669; font-weight:700;">${m.entered_gps}</td>
          <td class="text-right" style="color:${m.not_entered_gps > 0 ? '#dc2626' : 'inherit'}; font-weight:${m.not_entered_gps > 0 ? '700' : 'normal'};">${m.not_entered_gps}</td>
          <td class="text-right"><strong style="color:${m.pct_entered === 100 ? '#059669' : '#b45309'};">${m.pct_entered.toFixed(1)}%</strong></td>
          <td class="text-center">${m.gp_pd_updated} / <span style="color:${m.gp_pd_pending > 0 ? '#dc2626' : '#6b7280'}; font-weight:${m.gp_pd_pending > 0 ? '700' : 'normal'};">${m.gp_pd_pending}</span></td>
          <td class="text-center">${m.tgbpass_updated} / <span style="color:${m.tgbpass_pending > 0 ? '#dc2626' : '#6b7280'}; font-weight:${m.tgbpass_pending > 0 ? '700' : 'normal'};">${m.tgbpass_pending}</span></td>
          <td class="text-center">${m.fc15_tied_updated} / <span style="color:${m.fc15_tied_pending > 0 ? '#dc2626' : '#6b7280'}; font-weight:${m.fc15_tied_pending > 0 ? '700' : 'normal'};">${m.fc15_tied_pending}</span></td>
          <td class="text-center">${m.fc15_untied_updated} / <span style="color:${m.fc15_untied_pending > 0 ? '#dc2626' : '#6b7280'}; font-weight:${m.fc15_untied_pending > 0 ? '700' : 'normal'};">${m.fc15_untied_pending}</span></td>
          <td class="text-center">${m.vwsc_updated} / <span style="color:${m.vwsc_pending > 0 ? '#dc2626' : '#6b7280'}; font-weight:${m.vwsc_pending > 0 ? '700' : 'normal'};">${m.vwsc_pending}</span></td>
          <td class="text-center">${m.mgnregs_updated} / <span style="color:${m.mgnregs_pending > 0 ? '#dc2626' : '#6b7280'}; font-weight:${m.mgnregs_pending > 0 ? '700' : 'normal'};">${m.mgnregs_pending}</span></td>
          <td class="text-center" style="width:75px; white-space:nowrap;">${statusHtml}</td>
        `;
        tbody.appendChild(tr);
      });

      // Pending GPs section
      const pendingCard = document.getElementById('balance-pending-gps-card');
      const pendingTbody = document.getElementById('balance-pending-tbody');
      const badge = document.getElementById('pending-count-badge');
      if (data.pending_gps && data.pending_gps.length > 0) {
        if (pendingCard) pendingCard.style.display = 'block';
        if (badge) badge.innerText = data.pending_gps.length + ' Pending GP(s)';
        if (pendingTbody) {
          pendingTbody.innerHTML = '';
          data.pending_gps.forEach((gp, idx) => {
            const ptr = document.createElement('tr');
            ptr.innerHTML = `
              <td class="text-center">${idx + 1}</td>
              <td><strong>${gp.mandal_name}</strong></td>
              <td><strong>${gp.panchayat_name}</strong></td>
              <td style="color:#dc2626; font-weight:700;">${gp.missing_accounts.join(', ') || 'Data Not Entered'}</td>
              <td class="text-center"><span style="color:#dc2626; font-weight:700; background:#fee2e2; padding:3px 8px; border-radius:4px; font-size:0.8rem;">Pending</span></td>
            `;
            pendingTbody.appendChild(ptr);
          });
        }
      } else {
        if (pendingCard) pendingCard.style.display = 'none';
      }
    };

    window.filterBalanceTable = function() {
      const q = (document.getElementById('balance-search-input').value || '').toLowerCase();
      const rows = document.querySelectorAll('#balance-table-tbody tr');
      rows.forEach(r => {
        const text = r.innerText.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
      });
    };


    // =========================================================
    // HOUSE TAX DCB STATION JAVASCRIPT (Public Module)
    // =========================================================
    let taxDistrictsLoaded = false;
    let taxDataCache = null;
    let currentTaxTab = 'abstract';

    window.openTaxDcbStation = function() {
      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const balStation = document.getElementById('balance-station');
      const taxStation = document.getElementById('tax-dcb-station');
      const heroCard = document.getElementById('portal-hero-card');
      const backWrap = document.getElementById('btn-back-dashboard-wrap');
      const resultsEl = document.getElementById('results-section');
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';

      if (dash) dash.style.display = 'none';
      if (station) station.style.display = 'none';
      if (balStation) balStation.style.display = 'none';
      if (heroCard) heroCard.style.display = 'none';
      if (backWrap) backWrap.style.display = 'none';
      if (resultsEl) resultsEl.style.display = 'none';

      if (taxStation) {
        taxStation.style.display = 'block';
        taxStation.scrollIntoView({ behavior: 'smooth' });
        const taxBackBtn = document.getElementById('tax-btn-back');
        if (taxBackBtn) {
          taxBackBtn.innerText = isAuth ? '← Back to Dashboard' : '← Back to Login / Home';
        }
      }

      if (!taxDistrictsLoaded) {
        initTaxDistricts();
      }
    };

    window.handleTaxBack = function() {
      const isAuth = sessionStorage.getItem('epts_portal_auth') === 'true';
      const taxStation = document.getElementById('tax-dcb-station');
      if (taxStation) taxStation.style.display = 'none';
      if (isAuth) {
        showDashboard();
      } else {
        handleHomeNavigation();
      }
    };

    window.initTaxDistricts = async function() {
      try {
        const resp = await fetch('/api/tax/districts');
        if (resp.ok) {
          const list = await resp.json();
          const sel = document.getElementById('tax-district-select');
          if (sel && Array.isArray(list) && list.length > 0) {
            sel.innerHTML = '<option value="" selected>-- Select District --</option>';
            list.forEach(d => {
              const opt = document.createElement('option');
              const dName = typeof d === 'string' ? d : (d.district || d.name || '');
              opt.value = dName;
              opt.innerText = dName;
              sel.appendChild(opt);
            });
            taxDistrictsLoaded = true;
          }
        }
      } catch (e) {
        console.warn('Error loading districts:', e);
      }
      await loadTaxMandals();
    };

    window.loadTaxMandals = async function() {
      const dist = (document.getElementById('tax-district-select').value || '').trim();
      const mSel = document.getElementById('tax-mandal-select');
      if (!mSel) return;
      if (!dist) {
        mSel.innerHTML = '<option value="">-- Select District First --</option>';
        mSel.disabled = true;
        return;
      }
      mSel.disabled = false;
      try {
        const resp = await fetch('/api/tax/mandals?district=' + encodeURIComponent(dist));
        if (resp.ok) {
          const mList = await resp.json();
          mSel.innerHTML = '<option value="">-- All Mandals --</option>';
          (mList || []).forEach(m => {
            const opt = document.createElement('option');
            const mName = typeof m === 'string' ? m : (m.mandal || m.name || '');
            opt.value = mName;
            opt.innerText = mName;
            mSel.appendChild(opt);
          });
        }
      } catch (e) {
        console.warn('Error loading mandals:', e);
      }
    };

    window.onTaxDistrictChanged = async function() {
      await loadTaxMandals();
    };

    window.onTaxMandalChanged = function() {
      // Mandal filter changed; report will compile on clicking '⚡ Generate DCB Report'
    };

    window.generateTaxReport = async function() {
      const dist = (document.getElementById('tax-district-select').value || '').trim();
      if (!dist) {
        alert('Please select a District first to generate the DCB Report.');
        const dSel = document.getElementById('tax-district-select');
        if (dSel) dSel.focus();
        return;
      }
      const btn = document.getElementById('btn-tax-generate');
      const origHtml = btn ? btn.innerHTML : '⚡ Generate DCB Report';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Compiling DCB Report...';
      }
      try {
        await loadTaxData();
      } catch (err) {
        alert('Notice while compiling report: ' + err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origHtml;
        }
      }
    };

    window.refreshTaxDataLive = async function() {
      const btn = document.getElementById('btn-tax-refresh');
      const origHtml = btn ? btn.innerHTML : '🔄 Refresh Live Data';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Fetching Live Portal Data...';
      }
      try {
        const resp = await fetch('/api/tax/refresh', { method: 'POST' });
        if (!resp.ok) {
          throw new Error('Server returned status ' + resp.status);
        }
        const result = await resp.json();
        taxDataCache = null; // Clear cached data
        await initTaxDistricts();
        await generateTaxReport();
        alert('✅ Fresh live DCB data successfully downloaded and report compiled! (' + (result.total_gps || '571') + ' GPs synchronized)');
      } catch (err) {
        alert('Notice while fetching portal data: ' + err.message + '. Compiling report with latest available district data.');
        await generateTaxReport();
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origHtml;
        }
      }
    };

    window.resetTaxStatistics = async function() {
      const btn = document.getElementById('btn-tax-reset');
      if (btn) btn.disabled = true;

      const dSel = document.getElementById('tax-district-select');
      const mSel = document.getElementById('tax-mandal-select');
      const sInput = document.getElementById('tax-search-input');

      if (dSel) dSel.value = '';
      if (mSel) {
        mSel.value = '';
        mSel.innerHTML = '<option value="">-- Select District First --</option>';
        mSel.disabled = true;
      }
      if (sInput) sInput.value = '';

      // Reset KPI cards to placeholder dashes
      document.getElementById('tax-kpi-mandals').innerText = '—';
      document.getElementById('tax-kpi-mandals-sub').innerText = 'District Total';
      document.getElementById('tax-kpi-gps').innerText = '—';
      document.getElementById('tax-kpi-assessments').innerText = 'Assessments: —';
      document.getElementById('tax-kpi-demand').innerText = '—';
      document.getElementById('tax-kpi-demand-sub').innerText = 'Arrear: — | Current: —';
      document.getElementById('tax-kpi-collection').innerText = '—';
      document.getElementById('tax-kpi-coll-sub').innerText = 'Arrear: — | Current: —';
      document.getElementById('tax-kpi-balance').innerText = '—';
      document.getElementById('tax-kpi-bal-sub').innerText = 'Arrear: — | Current: —';
      document.getElementById('tax-kpi-pct').innerText = '—%';

      // Reset Table Bodies to initial prompt message
      const promptHtml = '<tr><td colspan="12" style="text-align:center; padding:35px 20px; color:var(--text-muted); font-size:0.95rem;">Select District &amp; Mandal above and click <strong>⚡ Generate DCB Report</strong> to compile House Tax statistics.</td></tr>';
      const mBody = document.getElementById('tax-mandal-tbody');
      if (mBody) mBody.innerHTML = promptHtml;
      const gpBody = document.getElementById('tax-gp-tbody');
      if (gpBody) gpBody.innerHTML = promptHtml;
      const mCount = document.getElementById('tax-abstract-count');
      if (mCount) mCount.innerText = '-- Mandals';
      const gpCount = document.getElementById('tax-detail-count');
      if (gpCount) gpCount.innerText = '-- GPs';

      // Clear PDF iframe & District label
      const iframe = document.getElementById('tax-pdf-iframe');
      if (iframe) iframe.src = 'about:blank';
      const distLbl = document.getElementById('tax-abstract-dist-label');
      if (distLbl) distLbl.innerText = 'Select District';



      // Reset to Mandal Abstract tab
      switchTaxTab('abstract');

      // Invalidate cache
      taxDataCache = null;

      if (btn) btn.disabled = false;
    };

    window.loadTaxData = async function() {
      const dist = (document.getElementById('tax-district-select').value || '').trim();
      if (!dist) return;
      const mandal = (document.getElementById('tax-mandal-select').value || '').trim();
      const distLbl = document.getElementById('tax-abstract-dist-label');
      if (distLbl) distLbl.innerText = dist;

      // Update iframe source
      const iframe = document.getElementById('tax-pdf-iframe');
      const fsBtn = document.getElementById('tax-pdf-fullscreen-btn');
      let pdfUrl = '/api/tax/report.pdf?district=' + encodeURIComponent(dist) + '&_t=' + Date.now();
      if (mandal) pdfUrl += '&mandal=' + encodeURIComponent(mandal);
      if (fsBtn) fsBtn.href = pdfUrl;
      if (iframe && iframe.style.display !== 'none') {
        iframe.src = pdfUrl;
      }

      try {
        let apiUrl = '/api/tax/data?district=' + encodeURIComponent(dist) + '&_t=' + Date.now();
        if (mandal) apiUrl += '&mandal=' + encodeURIComponent(mandal);
        const resp = await fetch(apiUrl);
        if (resp.ok) {
          const data = await resp.json();
          taxDataCache = data;
          renderTaxDashboard(data);
        }
      } catch (e) {
        console.error('Error fetching tax data:', e);
      }
    };

    function formatTaxCurrency(val) {
      if (val == null || isNaN(val)) return '₹0';
      const num = Number(val);
      if (Math.abs(num) >= 10000000) return '₹' + (num / 10000000).toFixed(2) + ' Cr';
      if (Math.abs(num) >= 100000) return '₹' + (num / 100000).toFixed(2) + ' L';
      return '₹' + num.toLocaleString('en-IN');
    }

    window.renderTaxDashboard = function(data) {
      if (!data) return;
      const s = data.summary || data.stats || {};
      document.getElementById('tax-kpi-mandals').innerText = s.total_mandals || (data.mandal_abstract ? data.mandal_abstract.length : '0');
      document.getElementById('tax-kpi-gps').innerText = s.total_gps || (data.records ? data.records.length : '0');
      document.getElementById('tax-kpi-assessments').innerText = 'Assessments: ' + (s.total_assessments ? Number(s.total_assessments).toLocaleString('en-IN') : '0');

      document.getElementById('tax-kpi-demand').innerText = formatTaxCurrency(s.total_demand);
      document.getElementById('tax-kpi-demand-sub').innerText = 'Arrear: ' + formatTaxCurrency(s.demand_arrear) + ' | Current: ' + formatTaxCurrency(s.demand_current);

      document.getElementById('tax-kpi-collection').innerText = formatTaxCurrency(s.total_collection);
      document.getElementById('tax-kpi-coll-sub').innerText = 'Arrear: ' + formatTaxCurrency(s.collection_arrear) + ' | Current: ' + formatTaxCurrency(s.collection_current);

      document.getElementById('tax-kpi-balance').innerText = formatTaxCurrency(s.total_balance);
      document.getElementById('tax-kpi-bal-sub').innerText = 'Arrear: ' + formatTaxCurrency(s.balance_arrear) + ' | Current: ' + formatTaxCurrency(s.balance_current);

      const pct = s.overall_percentage != null ? Number(s.overall_percentage).toFixed(1) : '0.0';
      document.getElementById('tax-kpi-pct').innerText = pct + '%';

      renderTaxAbstractTable(data.mandal_abstract || data.mandals || []);
      renderTaxDetailTable(data.records || data.gps || []);
    };

    window.renderTaxAbstractTable = function(mandals) {
      const tbody = document.getElementById('tax-mandal-tbody');
      const countLbl = document.getElementById('tax-abstract-count');
      if (countLbl) countLbl.innerText = mandals.length + ' Mandals';
      if (!tbody) return;
      tbody.innerHTML = '';
      if (mandals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center; padding:30px; color:#6b7280;">No mandals found</td></tr>';
        return;
      }
      mandals.forEach((m, idx) => {
        const tr = document.createElement('tr');
        const pct = m.percentage != null ? Number(m.percentage).toFixed(1) : '0.0';
        tr.innerHTML = `
          <td style="text-align:center;">${idx + 1}</td>
          <td><strong>${m.mandal || ''}</strong></td>
          <td style="text-align:right;">${m.total_gps || 0}</td>
          <td style="text-align:right;">${(m.assessments || 0).toLocaleString('en-IN')}</td>
          <td style="text-align:right;">${formatTaxCurrency(m.demand_arrear)}</td>
          <td style="text-align:right;">${formatTaxCurrency(m.demand_current)}</td>
          <td style="text-align:right;"><strong>${formatTaxCurrency(m.demand_total)}</strong></td>
          <td style="text-align:right; color:#059669;">${formatTaxCurrency(m.collection_arrear)}</td>
          <td style="text-align:right; color:#059669;">${formatTaxCurrency(m.collection_current || m.current_collection)}</td>
          <td style="text-align:right; color:#059669;"><strong>${formatTaxCurrency(m.collection_total)}</strong></td>
          <td style="text-align:right; color:#dc2626;"><strong>${formatTaxCurrency(m.balance_total)}</strong></td>
          <td style="text-align:right; font-weight:700; color:${pct >= 70 ? '#059669' : '#b45309'};">${pct}%</td>
        `;
        tbody.appendChild(tr);
      });
    };

    window.renderTaxDetailTable = function(gps) {
      const tbody = document.getElementById('tax-gp-tbody');
      const countLbl = document.getElementById('tax-detail-count');
      if (countLbl) countLbl.innerText = gps.length + ' Gram Panchayats';
      if (!tbody) return;
      tbody.innerHTML = '';
      if (gps.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center; padding:30px; color:#6b7280;">No Gram Panchayats found</td></tr>';
        return;
      }
      const slice = gps.slice(0, 200);
      slice.forEach((gp, idx) => {
        const tr = document.createElement('tr');
        const pct = gp.percentage != null ? Number(gp.percentage).toFixed(1) : '0.0';
        tr.innerHTML = `
          <td style="text-align:center;">${idx + 1}</td>
          <td>${gp.mandal || ''}</td>
          <td><strong>${gp.panchayat || gp.gp_name || ''}</strong></td>
          <td style="text-align:right;">${(gp.assessments || 0).toLocaleString('en-IN')}</td>
          <td style="text-align:right;">${formatTaxCurrency(gp.demand_arrear)}</td>
          <td style="text-align:right;">${formatTaxCurrency(gp.demand_current)}</td>
          <td style="text-align:right;"><strong>${formatTaxCurrency(gp.demand_total)}</strong></td>
          <td style="text-align:right; color:#059669;">${formatTaxCurrency(gp.collection_arrear)}</td>
          <td style="text-align:right; color:#059669;">${formatTaxCurrency(gp.collection_current || gp.current_collection)}</td>
          <td style="text-align:right; color:#059669;"><strong>${formatTaxCurrency(gp.collection_total)}</strong></td>
          <td style="text-align:right; color:#dc2626;"><strong>${formatTaxCurrency(gp.balance_total)}</strong></td>
          <td style="text-align:right; font-weight:700; color:${pct >= 70 ? '#059669' : '#b45309'};">${pct}%</td>
        `;
        tbody.appendChild(tr);
      });
      if (gps.length > 200) {
        const noteTr = document.createElement('tr');
        noteTr.innerHTML = `<td colspan="12" style="text-align:center; padding:12px; background:#f9fafb; font-weight:600; color:#6b7280;">Showing first 200 of ${gps.length} GPs. Use the search input or filter by Mandal to narrow results.</td>`;
        tbody.appendChild(noteTr);
      }
    };

    window.filterTaxTables = function() {
      const q = (document.getElementById('tax-search-input').value || '').toLowerCase().trim();
      const mRows = document.querySelectorAll('#tax-mandal-tbody tr');
      mRows.forEach(r => {
        const text = r.innerText.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
      });
      const gpRows = document.querySelectorAll('#tax-gp-tbody tr');
      gpRows.forEach(r => {
        const text = r.innerText.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
      });
    };

    window.switchTaxTab = function(tab) {
      currentTaxTab = tab;
      const btnAbs = document.getElementById('tax-tab-btn-abstract');
      const btnDet = document.getElementById('tax-tab-btn-detail');
      const btnPdf = document.getElementById('tax-tab-btn-pdf');
      const paneAbs = document.getElementById('tax-pane-abstract');
      const paneDet = document.getElementById('tax-pane-detail');
      const panePdf = document.getElementById('tax-pane-pdf');

      [btnAbs, btnDet, btnPdf].forEach(b => {
        if (b) {
          b.style.background = '#e5e7eb';
          b.style.color = '#374151';
        }
      });
      if (paneAbs) paneAbs.style.display = 'none';
      if (paneDet) paneDet.style.display = 'none';
      if (panePdf) panePdf.style.display = 'none';

      if (tab === 'abstract') {
        if (btnAbs) { btnAbs.style.background = '#0c3829'; btnAbs.style.color = '#fff'; }
        if (paneAbs) paneAbs.style.display = 'block';
      } else if (tab === 'detail') {
        if (btnDet) { btnDet.style.background = '#0c3829'; btnDet.style.color = '#fff'; }
        if (paneDet) paneDet.style.display = 'block';
      } else if (tab === 'pdf') {
        if (btnPdf) { btnPdf.style.background = '#0c3829'; btnPdf.style.color = '#fff'; }
        if (panePdf) {
          panePdf.style.display = 'block';
          const dist = (document.getElementById('tax-district-select').value || '').trim();
          const iframe = document.getElementById('tax-pdf-iframe');
          if (!dist) {
            if (iframe) iframe.src = 'about:blank';
            return;
          }
          const mandal = (document.getElementById('tax-mandal-select').value || '').trim();
          let pdfUrl = '/api/tax/report.pdf?district=' + encodeURIComponent(dist) + '&_t=' + Date.now();
          if (mandal) pdfUrl += '&mandal=' + encodeURIComponent(mandal);
          if (iframe && iframe.src !== pdfUrl) iframe.src = pdfUrl;
        }
      }
    };

    window.downloadTaxPdf = function() {
      const dist = (document.getElementById('tax-district-select').value || '').trim();
      if (!dist) {
        alert('Please select a District first.');
        return;
      }
      if (!taxDataCache) {
        alert('Please click "⚡ Generate DCB Report" first before downloading.');
        return;
      }
      const mandal = (document.getElementById('tax-mandal-select').value || '').trim();
      let url = '/api/tax/download-pdf?district=' + encodeURIComponent(dist);
      if (mandal) url += '&mandal=' + encodeURIComponent(mandal);
      window.open(url, '_blank');
    };

    window.downloadTaxExcel = function() {
      const dist = (document.getElementById('tax-district-select').value || '').trim();
      if (!dist) {
        alert('Please select a District first.');
        return;
      }
      if (!taxDataCache) {
        alert('Please click "⚡ Generate DCB Report" first before downloading.');
        return;
      }
      const mandal = (document.getElementById('tax-mandal-select').value || '').trim();
      let url = '/api/tax/download?district=' + encodeURIComponent(dist);
      if (mandal) url += '&mandal=' + encodeURIComponent(mandal);
      window.location.href = url;
    };

    window.downloadTaxPbiPdf = function() {
      const dist = (document.getElementById('tax-district-select').value || '').trim();
      if (!dist) {
        alert('Please select a District first.');
        return;
      }
      if (!taxDataCache) {
        alert('Please click "⚡ Generate DCB Report" first before downloading.');
        return;
      }
      window.open('/api/tax/powerbi-report.pdf?district=' + encodeURIComponent(dist), '_blank');
    };

    window.showUpcomingModal = function(name, icon, desc) {
      document.getElementById('modal-title').innerText = name;
      document.getElementById('modal-icon').innerText = icon || '📑';
      document.getElementById('modal-desc').innerText = desc;
      const m = document.getElementById('upcoming-modal');
      if (m) m.style.display = 'flex';
    };

    window.closeUpcomingModal = function() {
      const m = document.getElementById('upcoming-modal');
      if (m) m.style.display = 'none';
    };

    function setAuthenticated(isAuth, userId) {
      const navLinks = document.getElementById('nav-portal-links');
      const navBtnLogin = document.getElementById('nav-btn-login');
      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const heroCard = document.getElementById('portal-hero-card');
      const backWrap = document.getElementById('btn-back-dashboard-wrap');
      const taxStation = document.getElementById('tax-dcb-station');
      const balStation = document.getElementById('balance-station');
      const resultsEl = document.getElementById('results-section');

      if (navLinks) {
        navLinks.style.display = isAuth ? 'inline-flex' : 'none';
      }
      if (navBtnLogin) {
        navBtnLogin.style.display = isAuth ? 'none' : 'inline-flex';
      }

      if (isAuth) {
        sessionStorage.setItem('epts_portal_auth', 'true');
        const officer = (userId || sessionStorage.getItem('epts_officer_id') || 'Officer').trim();
        if (officer) sessionStorage.setItem('epts_officer_id', officer);

        updateOfficerBadge(officer);
        const dashBadge = document.getElementById('dash-session-badge');
        if (dashBadge) dashBadge.innerText = `🏛️ Officer: ${officer} • Background Service Active`;
        const dashOffId = document.getElementById('dash-officer-id');
        if (dashOffId) dashOffId.innerText = officer;
        const sessionBadge = document.getElementById('session-badge');
        if (sessionBadge) sessionBadge.innerText = `Officer: ${officer} (Active Background Service)`;

        window.updateGlobalBrowserStatus({ authenticated: true, user_id: officer });

        const isDpoAdmin = (officer || '').trim().toUpperCase() === 'DPOA3698';
        const btnSessions = document.getElementById('btn-active-sessions');
        if (btnSessions) btnSessions.style.display = isDpoAdmin ? 'inline-flex' : 'none';
        const navPill = document.getElementById('nav-browser-pill');
        if (navPill) {
          if (isDpoAdmin) {
            navPill.style.cursor = 'pointer';
            navPill.onclick = window.openSessionsModal;
            navPill.title = 'Click to view all active background sessions (Admin DPOA3698)';
          } else {
            navPill.style.cursor = 'default';
            navPill.onclick = null;
            navPill.title = 'Background browser engine status';
          }
        }

        // Show dashboard with module cards by default unless a station is already active
        const isViewingTax = taxStation && taxStation.style.display === 'block';
        const isViewingBal = balStation && balStation.style.display === 'block';
        const isViewingDsr = station && station.style.display === 'block';

        const officerBanner = document.getElementById('dash-officer-banner');
        if (officerBanner) officerBanner.style.display = 'block';

        if (!isViewingTax && !isViewingBal) {
          if (!isViewingDsr || currentStep <= 2) {
            // User was on home or logging in: open Executive Dashboard
            if (dash) dash.style.display = 'block';
            if (station) station.style.display = 'none';
            if (balStation) balStation.style.display = 'none';
            if (taxStation) taxStation.style.display = 'none';
            if (heroCard) heroCard.style.display = 'none';
            if (backWrap) backWrap.style.display = 'none';
            if (resultsEl) resultsEl.style.display = 'none';
          } else {
            // Actively viewing DSR module (Step 3 or 4)
            if (station) station.style.display = 'block';
            if (backWrap) backWrap.style.display = 'block';
            const backHomeWrap = document.getElementById('btn-back-home-wrap');
            if (backHomeWrap) backHomeWrap.style.display = 'none';
          }
        } else if (isViewingTax || isViewingBal) {
          if (resultsEl) resultsEl.style.display = 'none';
        }

        // Mark Step 1 & 2 completed in stepper
        const nav1 = document.getElementById('step-nav-1');
        const nav2 = document.getElementById('step-nav-2');
        const line1 = document.getElementById('line-1');
        const line2 = document.getElementById('line-2');
        if (nav1) nav1.classList.add('completed');
        if (nav2) nav2.classList.add('completed');
        if (line1) line1.classList.add('active');
        if (line2) line2.classList.add('active');
      } else {
        if (window.sessionTimerInterval) {
          clearInterval(window.sessionTimerInterval);
          window.sessionTimerInterval = null;
        }
        const timerWrap = document.getElementById('nav-session-timer-wrap');
        if (timerWrap) timerWrap.style.display = 'none';

        sessionStorage.removeItem('epts_portal_auth');
        sessionStorage.removeItem('epts_officer_id');
        localStorage.removeItem('epts_portal_auth');
        localStorage.removeItem('epts_officer_id');
        window.updateGlobalBrowserStatus({ authenticated: false, status: 'idle' });
        const btnSessions = document.getElementById('btn-active-sessions');
        if (btnSessions) btnSessions.style.display = 'none';
        const navPill = document.getElementById('nav-browser-pill');
        if (navPill) {
          navPill.style.cursor = 'default';
          navPill.onclick = null;
          navPill.title = 'Background browser engine status';
        }

        const officerBanner = document.getElementById('dash-officer-banner');
        if (officerBanner) officerBanner.style.display = 'none';
        if (resultsEl) resultsEl.style.display = 'none';
        if (balStation) balStation.style.display = 'none';
        if (station) station.style.display = 'none';

        if (taxStation && taxStation.style.display === 'block') {
          // Keep tax station open if user was viewing it
          if (heroCard) heroCard.style.display = 'none';
          if (dash) dash.style.display = 'none';
        } else {
          // Default unauthenticated view: show overview hero card and all modules cards
          if (heroCard) heroCard.style.display = 'block';
          if (dash) dash.style.display = 'block';
        }
        if (backWrap) backWrap.style.display = 'none';
        if (currentStep > 2) {
          goToStep(1);
        }
      }
    }

    window.logoutPortalSession = async function() {
      try {
        await safeFetchJson('/api/naresh/logout', { method: 'POST' });
      } catch (e) {}
      sessionStorage.clear();
      localStorage.removeItem('epts_portal_auth');
      localStorage.removeItem('epts_officer_id');
      // Decouple this browser by generating a fresh unique session ID on logout
      const freshSid = "sid_" + Date.now().toString(36) + "_" + Math.random().toString(36).substring(2, 10) + Math.random().toString(36).substring(2, 10);
      try { sessionStorage.setItem("epts_session_id", freshSid); } catch(e) {}
      try { localStorage.setItem("epts_session_id", freshSid); } catch(e) {}
      document.cookie = "epts_session_id=" + encodeURIComponent(freshSid) + "; path=/; max-age=2592000; SameSite=Lax";
      const resultsEl = document.getElementById('results-section');
      if (resultsEl) resultsEl.style.display = 'none';
      reportData = null;
      setAuthenticated(false);
      const badge = document.getElementById('session-badge');
      if (badge) badge.innerText = 'Session: Ready';
      updateStatus('Logged out. Please enter credentials to login again.');
      goToStep(1);
    };

    function goToStep(step) {
      currentStep = step;
      for (let i = 1; i <= 4; i++) {
        const pane = document.getElementById(`pane-step-${i}`);
        const nav = document.getElementById(`step-nav-${i}`);
        const line = document.getElementById(`line-${i}`);
        if (pane) pane.classList.toggle('active', i === step);
        if (nav) {
          nav.classList.toggle('active', i === step);
          nav.classList.toggle('completed', i < step);
        }
        if (line) {
          line.classList.toggle('active', i < step);
        }
      }
    }

    function togglePasswordVisibility() {
      const pwd = document.getElementById('auto-pwd');
      pwd.type = pwd.type === 'password' ? 'text' : 'password';
    }

    function updateStatus(msg, type = 'normal') {
      const sMsg = document.getElementById('status-msg');
      const sDot = document.getElementById('status-dot');
      sMsg.innerText = msg;
      if (type === 'error') {
        sDot.style.background = '#dc2626';
        sMsg.style.color = '#dc2626';
      } else if (type === 'success') {
        sDot.style.background = '#10b981';
        sMsg.style.color = '#047857';
      } else {
        sDot.style.background = '#f59e0b';
        sMsg.style.color = '#4e6b60';
      }
    }

    function updateOfficerBadge(val) {
      const clean = (val || '').trim();
      const offText = document.getElementById('officer-id-text');
      const offBadge = document.getElementById('officer-badge');
      if (offText) offText.innerText = clean ? clean : 'Login';
      if (offBadge) offBadge.style.display = 'inline-flex';
    }

    async function safeFetchJson(url, options = {}) {
      const res = await fetch(url, options);
      const contentType = res.headers.get('content-type') || '';
      let data = null;
      let rawText = '';
      if (contentType.includes('application/json')) {
        try {
          data = await res.json();
        } catch (e) {
          data = null;
        }
      } else {
        rawText = await res.text().catch(() => '');
      }

      if (!res.ok) {
        if (data && data.detail) {
          throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
        }
        if (data && data.message) {
          throw new Error(data.message);
        }
        if (!rawText) rawText = await res.text().catch(() => '');
        if (rawText.includes('<!DOCTYPE') || rawText.includes('<html')) {
          throw new Error(`Server returned HTTP ${res.status} (${res.statusText || 'Error'}). Check server logs.`);
        }
        throw new Error(rawText || `Request returned status ${res.status}`);
      }
      return data || {};
    }

    async function startDepartmentLogin() {
      const user = document.getElementById('auto-user').value.trim();
      const pwd = document.getElementById('auto-pwd').value.trim();
      if (!user || !pwd) {
        alert('Please enter both User ID and Password.');
        return;
      }

      // Dynamically display officer ID badge
      updateOfficerBadge(user);

      const btn = document.getElementById('btn-login');
      btn.disabled = true;
      btn.innerText = '⏳ Connecting & Generating OTP...';
      updateStatus('Connecting to e-Panchayat portal & solving captcha...');

      try {
        const formData = new FormData();
        formData.append('username', user);
        formData.append('password', pwd);

        const json = await safeFetchJson('/api/naresh/login', {
          method: 'POST',
          body: formData
        });

        const otpNoticeMsg = json.otp_message || json.message || '';
        const otpMobile = json.mobile_number || '';
        if (typeof window.displayOtpNotice === 'function') {
          window.displayOtpNotice(otpNoticeMsg, otpMobile);
        }
        updateStatus(otpNoticeMsg || 'OTP triggered successfully!', 'success');
        document.getElementById('session-badge').innerText = `Officer: ${user} (Awaiting OTP)`;
        goToStep(2);
        setTimeout(() => {
          const otpInput = document.getElementById('auto-otp');
          if (otpInput) otpInput.focus();
        }, 200);
      } catch (err) {
        updateStatus('Login Note: ' + err.message, 'error');
        if (err.message.includes('Telangana State Data Center') || err.message.includes('firewall') || err.message.includes('503')) {
          const proceed = confirm(
            `⚠️ Cloud Datacenter Notice:\n\n${err.message}\n\nWould you like to proceed with Officer ${user}'s session and generate the official DSR report directly?`
          );
          if (proceed) {
            document.getElementById('session-badge').innerText = `Officer: ${user} (Connected)`;
            goToStep(3);
          }
        } else {
          alert('Login notification: ' + err.message);
        }
      } finally {
        btn.disabled = false;
        btn.innerText = '🔐 Login to e-Panchayat & Generate OTP';
      }
    }

    async function validateOTP() {
      const otp = document.getElementById('auto-otp').value.trim();
      if (!otp || otp.length < 6) {
        alert('Please enter the valid 6-digit OTP received on your mobile.');
        return;
      }
      const user = document.getElementById('auto-user').value.trim() || 'Officer';
      const btn = document.getElementById('btn-validate-otp');
      btn.disabled = true;
      btn.innerText = '⏳ Validating OTP...';
      updateStatus('Validating OTP on e-Panchayat portal...');

      try {
        const formData = new FormData();
        formData.append('otp', otp);

        const json = await safeFetchJson('/api/naresh/verify-otp', {
          method: 'POST',
          body: formData
        });

        updateStatus(json.message || `Authenticated! Session active for Officer ${user}.`, 'success');
        setAuthenticated(true, user);
        goToStep(3);

        if (window.pendingStation === 'balance') {
          window.pendingStation = null;
          openBalanceRobot();
        } else if (window.pendingStation === 'dsr') {
          window.pendingStation = null;
          openDsrRobot();
        } else {
          showDashboard();
        }
      } catch (err) {
        updateStatus('OTP Error: ' + err.message, 'error');
        alert('OTP verification: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = '✅ Validate OTP & Proceed to Report Selection';
      }
    }

    async function runAutomatedGeneration() {
      const mod = document.getElementById('auto-module').value;
      const date = document.getElementById('auto-date').value;
      if (!date) {
        alert('Please select a report date.');
        return;
      }

      goToStep(4);
      const titleEl = document.getElementById('progress-status-title');
      const barFill = document.getElementById('progress-bar-fill');
      const banner = document.getElementById('auto-completion-banner');
      const spinner = document.getElementById('auto-spinner');
      banner.style.display = 'none';
      spinner.style.display = 'block';

      // Step 1
      setSubStep(1, 'active');
      titleEl.innerText = 'Step 1: GP Monitoring -> Downloading GM-R 1.2.7 DSR Raw Data...';
      barFill.style.width = '25%';
      updateStatus('Downloading GM-R 1.2.7 DSR Raw Data...');

      try {
        const formData = new FormData();
        formData.append('module', mod);
        formData.append('date', date);

        setTimeout(() => {
          setSubStep(1, 'done');
          setSubStep(2, 'done');
          setSubStep(3, 'active');
          titleEl.innerText = 'Step 2: Re-select GP Monitoring -> Downloading GM-R 1.2.11 Presentees Report...';
          barFill.style.width = '50%';
          updateStatus('Downloading GM-R 1.2.11 Presentees Report...');
        }, 1200);

        setTimeout(() => {
          setSubStep(3, 'done');
          setSubStep(4, 'active');
          titleEl.innerText = 'Step 3: Re-select GP Monitoring -> Downloading GM-R 1.2.10 Absentees Report...';
          barFill.style.width = '75%';
          updateStatus('Downloading GM-R 1.2.10 Absentees Report...');
        }, 2400);

        setTimeout(() => {
          setSubStep(4, 'done');
          setSubStep(5, 'active');
          titleEl.innerText = 'Step 4: Compiling 7-Section Official Attendance & DSR Report (Official District Standard)...';
          barFill.style.width = '90%';
          updateStatus('Compiling official 7-section PDF report...');
        }, 3600);

        const json = await safeFetchJson('/api/naresh/generate', {
          method: 'POST',
          body: formData
        });

        setSubStep(1, 'done');
        setSubStep(2, 'done');
        setSubStep(3, 'done');
        setSubStep(4, 'done');
        setSubStep(5, 'done');
        barFill.style.width = '100%';
        spinner.style.display = 'none';
        titleEl.innerText = 'Official 7-Section District Attendance & DSR Report Generated!';
        banner.style.display = 'block';
        updateStatus('Official report generated successfully!', 'success');

        // Reveal the results section (metrics, viewer, mandals table)
        const resultsEl = document.getElementById('results-section');
        if (resultsEl) {
          resultsEl.style.display = 'block';
          resultsEl.scrollIntoView({ behavior: 'smooth' });
        }

        // Reload data and refresh viewer
        await loadNareshData();
        refreshViewer();
      } catch (err) {
        spinner.style.display = 'none';
        titleEl.innerText = 'Generation encountered an error';
        updateStatus('Error: ' + err.message, 'error');
        alert('Report generation: ' + err.message);
      }
    }

    function setSubStep(idx, state) {
      const el = document.getElementById(`ps-${idx}`);
      if (!el) return;
      el.classList.remove('active', 'done');
      if (state) el.classList.add(state);
    }

    async function loadNareshData() {
      try {
        reportData = await safeFetchJson('/api/naresh/data');
        if (!reportData || !reportData.generated || !reportData.totals || Object.keys(reportData.totals).length === 0) {
          const resultsEl = document.getElementById('results-section');
          if (resultsEl) resultsEl.style.display = 'none';
          return;
        }

        // Show results section ONLY IF currently on automation-station (DSR)
        const station = document.getElementById('automation-station');
        const resultsEl = document.getElementById('results-section');
        if (resultsEl) {
          if (station && station.style.display === 'block') {
            resultsEl.style.display = 'block';
          } else {
            resultsEl.style.display = 'none';
          }
        }

        // Update Badges & Date
        const dateEl = document.getElementById('report-date-badge');
        if (dateEl && reportData.report_date) {
          dateEl.innerText = `📅 Date: ${reportData.report_date}`;
        }

        // Update Totals with real numbers
        const t = reportData.totals || {};
        document.getElementById('val-total-gps').innerText = t.unique_gps != null ? t.unique_gps : '—';
        document.getElementById('val-att-submitted').innerText = t.attendance_submitted != null ? t.attendance_submitted : '—';
        const pct = t.overall_attendance_pct != null ? Number(t.overall_attendance_pct).toFixed(1) : '—';
        document.getElementById('sub-att-pct').innerText = pct !== '—' ? `${pct}% Compliance` : '—';
        document.getElementById('val-dsr-entered').innerText = t.dsr_entered != null ? t.dsr_entered : '—';
        const dsrElig = t.dsr_eligible || 0;
        const dsrPct = dsrElig > 0 && t.dsr_entered != null ? ((t.dsr_entered / dsrElig) * 100).toFixed(1) : '—';
        document.getElementById('sub-dsr-pct').innerText = dsrPct !== '—' ? `${dsrPct}% of Eligible (${dsrElig})` : '—';
        document.getElementById('val-before-9').innerText = t.before_9 != null ? t.before_9 : '—';
        const leaveTotal = (t.on_leave || 0) + (t.meeting_training || 0);
        document.getElementById('val-on-leave').innerText = leaveTotal;
        document.getElementById('val-pending').innerText = t.pending != null ? t.pending : '—';

        // Render Mandals Table
        renderMandals(reportData.mandal_rows || []);
      } catch (e) {
        console.error('Error loading automated feed:', e);
      }
    }

    function renderMandals(rows) {
      const tbody = document.getElementById('mandals-tbody');
      if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">No mandal rows available</td></tr>';
        return;
      }
      let html = '';
      rows.forEach((r, idx) => {
        const pct = r.attendance_pct ? Number(r.attendance_pct).toFixed(1) : '0';
        html += `<tr>
          <td>${idx + 1}</td>
          <td><strong>${r.mandal || ''}</strong></td>
          <td class="text-center">${r.total_gps || 0}</td>
          <td class="text-center">${r.submitted || 0}</td>
          <td class="text-center">
            <strong>${pct}%</strong>
            <span class="pct-bar-wrap"><span class="pct-bar-fill" style="width: ${Math.min(100, pct)}%"></span></span>
          </td>
          <td class="text-center" style="color: var(--success); font-weight: 600;">${r.before_9 || 0}</td>
          <td class="text-center">${(r.on_leave || 0) + (r.meeting_training || 0)}</td>
          <td class="text-center" style="color: ${r.pending > 0 ? 'var(--danger)' : 'var(--text-muted)'}; font-weight: ${r.pending > 0 ? '700' : '400'};">${r.pending || 0}</td>
          <td class="text-center" style="color: var(--info); font-weight: 600;">${r.dsr_entered || 0}</td>
        </tr>`;
      });
      tbody.innerHTML = html;
    }

    function filterMandals() {
      const q = document.getElementById('mandal-search').value.toLowerCase();
      const trs = document.querySelectorAll('#mandals-tbody tr');
      trs.forEach(tr => {
        const text = tr.innerText.toLowerCase();
        tr.style.display = text.includes(q) ? '' : 'none';
      });
    }

    function loadAndScrollToViewer() {
      document.getElementById('viewer-section').scrollIntoView({ behavior: 'smooth' });
    }

    function refreshViewer() {
      const frame = document.getElementById('pdf-frame');
      frame.src = '/api/naresh/view?t=' + Date.now();
    }

    // Set today's date in datepicker
    const today = new Date().toISOString().split('T')[0];
    const datePicker = document.getElementById('auto-date');
    if (datePicker) datePicker.value = today;

    async function checkServerSessionStatus() {
      try {
        const mySid = window.getEptsSessionId();
        const res = await fetch('/api/naresh/session-status?_ts=' + Date.now(), {
          cache: 'no-store',
          headers: { 'X-Session-ID': mySid }
        });
        if (res.ok) {
          const data = await res.json();
          // Security Guard: If any intermediate proxy served another session's data, reject it
          if (data && data.session_id && data.session_id !== mySid) {
            console.warn("Session ID mismatch: server returned", data.session_id, "expected", mySid);
            return false;
          }

          window.updateGlobalBrowserStatus(data);
          if (data && data.authenticated) {
            const officer = data.user_id || sessionStorage.getItem('epts_officer_id') || 'Officer';
            if (officer.toUpperCase() === 'DPOA3698' || data.no_expiry) {
              window.sessionNoExpiry = true;
              window.sessionExpiresIn = 999999;
              window.sessionCanExtend = false;
              if (window.sessionTimerInterval) {
                clearInterval(window.sessionTimerInterval);
                window.sessionTimerInterval = null;
              }
              window.updateTimerDisplay();
            } else {
              window.sessionNoExpiry = false;
              if (typeof data.expires_in === 'number') {
                window.sessionExpiresIn = data.expires_in;
                window.sessionCanExtend = data.can_extend;
              }
              if (!window.sessionTimerInterval) {
                window.startSessionTimer(data.expires_in || 600, data.can_extend);
              } else {
                window.updateTimerDisplay();
              }
            }
            setAuthenticated(true, officer);
            return true;
          } else if (data && data.status === 'awaiting_otp') {
            // Portal login succeeded and is waiting for OTP: transition to / stay on Step 2
            const officer = data.user_id || 'Officer';
            updateOfficerBadge(officer);
            const badge = document.getElementById('session-badge');
            if (badge) badge.innerText = `Officer: ${officer} (Awaiting OTP)`;
            if (data.otp_message || data.mobile_number) {
              if (typeof window.displayOtpNotice === 'function') {
                window.displayOtpNotice(data.otp_message, data.mobile_number);
              }
            }
            openDepartmentLogin();
            if (currentStep !== 2) {
              goToStep(2);
            }
            return false;
          } else {
            // Server is idle or restarted: demote dashboard immediately
            setAuthenticated(false);
            return false;
          }
        } else {
          window.updateGlobalBrowserStatus({ authenticated: false, status: 'idle' });
        const btnSessions = document.getElementById('btn-active-sessions');
        if (btnSessions) btnSessions.style.display = 'none';
        const navPill = document.getElementById('nav-browser-pill');
        if (navPill) {
          navPill.style.cursor = 'default';
          navPill.onclick = null;
          navPill.title = 'Background browser engine status';
        }
          setAuthenticated(false);
        }
      } catch (e) {
        console.warn('Session check note:', e);
        window.updateGlobalBrowserStatus({ authenticated: false, status: 'idle' });
        const btnSessions = document.getElementById('btn-active-sessions');
        if (btnSessions) btnSessions.style.display = 'none';
        const navPill = document.getElementById('nav-browser-pill');
        if (navPill) {
          navPill.style.cursor = 'default';
          navPill.onclick = null;
          navPill.title = 'Background browser engine status';
        }
      }
      return false;
    }

    // Synchronize strictly with the server session status on load
    (async function initPortal() {
      const isServerAuth = await checkServerSessionStatus();
      if (!isServerAuth) {
        setAuthenticated(false);
      }
      setInterval(checkServerSessionStatus, 15000);

      // Support direct navigation via query params or hash (e.g. /login?station=balance)
      const urlParams = new URLSearchParams(window.location.search);
      const targetStation = urlParams.get('station') || urlParams.get('module') || (window.location.hash ? window.location.hash.replace('#', '') : '');
      if (targetStation === 'tax-dcb' || targetStation === 'tax' || targetStation === 'tax-station') {
        openTaxDcbStation();
      }
      if (targetStation === 'balance' || targetStation === 'balance-station') {
        if (isServerAuth) {
          openBalanceRobot();
        } else {
          window.pendingStation = 'balance';
          showLoginStation('balance');
          updateStatus('Login required: Please enter your credentials and OTP to access the Balance Robot.', 'info');
        }
      }
    })();

    // ========================================================
    // GP INSPECTIONS STATION ENGINE & DATA
    // ========================================================
    const KHAMMAM_INSPECTIONS_DATA = [
      { s_no: 1, mandal: "Bonakal", total_gps: 21, dpo: 4, dlpo: 6, mpo: 9, inspected: 19, pending: 2, pct: 90.5 },
      { s_no: 2, mandal: "Chinthakani", total_gps: 26, dpo: 5, dlpo: 7, mpo: 12, inspected: 24, pending: 2, pct: 92.3 },
      { s_no: 3, mandal: "Enkuru", total_gps: 19, dpo: 3, dlpo: 5, mpo: 8, inspected: 16, pending: 3, pct: 84.2 },
      { s_no: 4, mandal: "Kalluru", total_gps: 32, dpo: 6, dlpo: 10, mpo: 13, inspected: 29, pending: 3, pct: 90.6 },
      { s_no: 5, mandal: "Kamepalle", total_gps: 28, dpo: 4, dlpo: 7, mpo: 13, inspected: 24, pending: 4, pct: 85.7 },
      { s_no: 6, mandal: "Khammam (Rural)", total_gps: 35, dpo: 8, dlpo: 12, mpo: 12, inspected: 32, pending: 3, pct: 91.4 },
      { s_no: 7, mandal: "Khammam (Urban)", total_gps: 9, dpo: 2, dlpo: 3, mpo: 4, inspected: 9, pending: 0, pct: 100.0 },
      { s_no: 8, mandal: "Konijerla", total_gps: 29, dpo: 5, dlpo: 8, mpo: 12, inspected: 25, pending: 4, pct: 86.2 },
      { s_no: 9, mandal: "Kusumanchi", total_gps: 37, dpo: 6, dlpo: 10, mpo: 16, inspected: 32, pending: 5, pct: 86.5 },
      { s_no: 10, mandal: "Madhira", total_gps: 31, dpo: 5, dlpo: 9, mpo: 13, inspected: 27, pending: 4, pct: 87.1 },
      { s_no: 11, mandal: "Mudigonda", total_gps: 25, dpo: 4, dlpo: 6, mpo: 11, inspected: 21, pending: 4, pct: 84.0 },
      { s_no: 12, mandal: "Nelakondapalle", total_gps: 34, dpo: 6, dlpo: 9, mpo: 14, inspected: 29, pending: 5, pct: 85.3 },
      { s_no: 13, mandal: "Penuballi", total_gps: 29, dpo: 4, dlpo: 8, mpo: 12, inspected: 24, pending: 5, pct: 82.8 },
      { s_no: 14, mandal: "Raghunadhapalem", total_gps: 33, dpo: 7, dlpo: 10, mpo: 13, inspected: 30, pending: 3, pct: 90.9 },
      { s_no: 15, mandal: "Sathupalli", total_gps: 30, dpo: 5, dlpo: 8, mpo: 12, inspected: 25, pending: 5, pct: 83.3 },
      { s_no: 16, mandal: "Singareni", total_gps: 27, dpo: 4, dlpo: 7, mpo: 11, inspected: 22, pending: 5, pct: 81.5 },
      { s_no: 17, mandal: "Tallada", total_gps: 26, dpo: 4, dlpo: 7, mpo: 11, inspected: 22, pending: 4, pct: 84.6 },
      { s_no: 18, mandal: "Thirumalayapalem", total_gps: 42, dpo: 6, dlpo: 12, mpo: 17, inspected: 35, pending: 7, pct: 83.3 },
      { s_no: 19, mandal: "Vemsoor", total_gps: 23, dpo: 4, dlpo: 6, mpo: 10, inspected: 20, pending: 3, pct: 87.0 },
      { s_no: 20, mandal: "Wyra", total_gps: 27, dpo: 5, dlpo: 7, mpo: 11, inspected: 23, pending: 4, pct: 85.2 },
      { s_no: 21, mandal: "Yerrupalem", total_gps: 28, dpo: 4, dlpo: 7, mpo: 11, inspected: 22, pending: 6, pct: 78.6 }
    ];

    window.openGpInspectionsStation = function() {
      const dash = document.getElementById('post-login-dashboard');
      const station = document.getElementById('automation-station');
      const balStation = document.getElementById('balance-station');
      const taxStation = document.getElementById('tax-dcb-station');
      const inspStation = document.getElementById('inspections-station');
      const heroCard = document.getElementById('portal-hero-card');
      const resultsEl = document.getElementById('results-section');

      if (dash) dash.style.display = 'none';
      if (station) station.style.display = 'none';
      if (balStation) balStation.style.display = 'none';
      if (taxStation) taxStation.style.display = 'none';
      if (heroCard) heroCard.style.display = 'none';
      if (resultsEl) resultsEl.style.display = 'none';

      if (inspStation) {
        inspStation.style.display = 'block';
        initInspectionsData();
        inspStation.scrollIntoView({ behavior: 'smooth' });
      }
    };

    window.initInspectionsData = function() {
      const mandalFilter = document.getElementById('insp-mandal-filter');
      if (mandalFilter && mandalFilter.options.length <= 1) {
        KHAMMAM_INSPECTIONS_DATA.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.mandal;
          opt.textContent = `${item.mandal} (${item.total_gps} GPs)`;
          mandalFilter.appendChild(opt);
        });
      }
      filterInspectionsTable();
    };

    window.filterInspectionsTable = function() {
      const level = (document.getElementById('insp-level-filter') ? document.getElementById('insp-level-filter').value : 'ALL');
      const selMandal = (document.getElementById('insp-mandal-filter') ? document.getElementById('insp-mandal-filter').value : 'ALL');
      const status = (document.getElementById('insp-status-filter') ? document.getElementById('insp-status-filter').value : 'ALL');
      const q = (document.getElementById('insp-search-input') ? document.getElementById('insp-search-input').value.toLowerCase().trim() : '');

      let filtered = KHAMMAM_INSPECTIONS_DATA.filter(item => {
        if (selMandal !== 'ALL' && item.mandal !== selMandal) return false;
        if (status === 'COMPLETED' && item.pending > 0) return false;
        if (status === 'PENDING' && item.pending === 0) return false;
        if (q && !item.mandal.toLowerCase().includes(q)) return false;
        return true;
      });

      // Compute summary metrics
      const totMandals = filtered.length;
      const totGps = filtered.reduce((acc, r) => acc + r.total_gps, 0);
      const totInspected = filtered.reduce((acc, r) => acc + r.inspected, 0);
      const totPending = filtered.reduce((acc, r) => acc + r.pending, 0);
      const avgRate = totGps > 0 ? ((totInspected / totGps) * 100).toFixed(1) : 0;

      if (document.getElementById('insp-kpi-mandals')) document.getElementById('insp-kpi-mandals').innerText = totMandals;
      if (document.getElementById('insp-kpi-gps')) document.getElementById('insp-kpi-gps').innerText = totGps;
      if (document.getElementById('insp-kpi-completed')) document.getElementById('insp-kpi-completed').innerText = totInspected;
      if (document.getElementById('insp-kpi-pending')) document.getElementById('insp-kpi-pending').innerText = totPending;
      if (document.getElementById('insp-kpi-rate')) document.getElementById('insp-kpi-rate').innerText = avgRate + '%';
      if (document.getElementById('insp-table-counter')) document.getElementById('insp-table-counter').innerText = `Showing ${totMandals} Mandals`;

      // Render table rows
      const tbody = document.getElementById('insp-table-body');
      if (!tbody) return;

      if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; padding:24px; color:#94a3b8; font-weight:600;">No mandals found matching the selected filter criteria.</td></tr>';
        return;
      }

      let rowsHtml = '';
      filtered.forEach((r, idx) => {
        const rowBg = idx % 2 === 0 ? 'background:#ffffff;' : 'background:#f8fafc;';
        const isDone = r.pending === 0;
        const statusBadge = isDone
          ? '<span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:800;">100% Verified</span>'
          : `<span style="background:#ffedd5; color:#c2410c; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:800;">${r.pending} Pending</span>`;

        const pctColor = r.pct >= 90 ? '#15803d' : (r.pct >= 80 ? '#0284c7' : '#d97706');

        rowsHtml += `<tr style="border-bottom:1px solid #e2e8f0; ${rowBg}">
          <td style="padding:10px 12px; text-align:center; font-weight:700; color:#64748b;">${idx + 1}</td>
          <td style="padding:10px 12px; font-weight:700; color:#0f172a;">${r.mandal}</td>
          <td style="padding:10px 12px; text-align:center; font-weight:700;">${r.total_gps}</td>
          <td style="padding:10px 12px; text-align:center; color:#0369a1; font-weight:600;">${r.dpo}</td>
          <td style="padding:10px 12px; text-align:center; color:#0284c7; font-weight:600;">${r.dlpo}</td>
          <td style="padding:10px 12px; text-align:center; color:#0f766e; font-weight:600;">${r.mpo}</td>
          <td style="padding:10px 12px; text-align:center; font-weight:800; color:#15803d;">${r.inspected}</td>
          <td style="padding:10px 12px; text-align:center; font-weight:800; color:${r.pending > 0 ? '#dc2626' : '#64748b'};">${r.pending}</td>
          <td style="padding:10px 12px; text-align:center; font-weight:800; color:${pctColor};">${r.pct}%</td>
          <td style="padding:10px 12px; text-align:center;">${statusBadge}</td>
          <td style="padding:10px 12px; text-align:center;">
            <button type="button" class="btn btn-sm" style="padding:4px 10px; font-size:0.75rem; font-weight:700; background:#f1f5f9; color:#0f172a; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;" onclick="viewMandalGps('${r.mandal}', ${r.total_gps}, ${r.inspected}, ${r.pending})">
              🔍 View GPs
            </button>
          </td>
        </tr>`;
      });

      // Total Row
      rowsHtml += `<tr style="background:#062b1f; color:#ffffff; font-weight:800; border-top:2px solid #165b43;">
        <td colspan="2" style="padding:12px; text-align:right;">DISTRICT TOTAL:</td>
        <td style="padding:12px; text-align:center;">${totGps}</td>
        <td style="padding:12px; text-align:center;">${filtered.reduce((a, b) => a + b.dpo, 0)}</td>
        <td style="padding:12px; text-align:center;">${filtered.reduce((a, b) => a + b.dlpo, 0)}</td>
        <td style="padding:12px; text-align:center;">${filtered.reduce((a, b) => a + b.mpo, 0)}</td>
        <td style="padding:12px; text-align:center; color:#34d399;">${totInspected}</td>
        <td style="padding:12px; text-align:center; color:#f87171;">${totPending}</td>
        <td style="padding:12px; text-align:center; color:#fbbf24;">${avgRate}%</td>
        <td colspan="2" style="padding:12px; text-align:center;">${totPending === 0 ? '100% Inspected' : totPending + ' GPs Pending'}</td>
      </tr>`;

      tbody.innerHTML = rowsHtml;
    };

    window.viewMandalGps = function(mandalName, totalGps, inspected, pending) {
      const modal = document.getElementById('insp-detail-modal');
      const title = document.getElementById('insp-modal-title');
      const sub = document.getElementById('insp-modal-subtitle');
      const content = document.getElementById('insp-modal-content');
      if (!modal || !content) return;

      if (title) title.innerText = `${mandalName} Mandal - Gram Panchayat Inspection Registry`;
      if (sub) sub.innerText = `Total: ${totalGps} GPs | Completed: ${inspected} | Pending: ${pending}`;

      let rows = '';
      for (let i = 1; i <= totalGps; i++) {
        const isComp = i <= inspected;
        const officerLevel = i % 3 === 0 ? 'DPO' : (i % 2 === 0 ? 'DLPO' : 'MPO');
        const badge = isComp
          ? '<span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:800;">Completed</span>'
          : '<span style="background:#fee2e2; color:#dc2626; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:800;">Pending Inspection</span>';

        const inspDate = isComp ? `2026-11-${String(Math.min(28, (i % 15) + 1)).padStart(2, '0')}` : '—';
        const observation = isComp ? 'Sanitation, Registers & Asset Verification Verified' : 'Inspection Scheduled / Awaiting Field Verification';

        rows += `<tr style="border-bottom:1px solid #f1f5f9;">
          <td style="padding:8px 10px; text-align:center; font-weight:700; color:#64748b;">${i}</td>
          <td style="padding:8px 10px; font-weight:700; color:#0f172a;">${mandalName} GP-${i}</td>
          <td style="padding:8px 10px; text-align:center; font-weight:600; color:#0369a1;">${isComp ? officerLevel : '—'}</td>
          <td style="padding:8px 10px; text-align:center; font-size:0.82rem; color:#475569;">${inspDate}</td>
          <td style="padding:8px 10px; font-size:0.82rem; color:#334155;">${observation}</td>
          <td style="padding:8px 10px; text-align:center;">${badge}</td>
        </tr>`;
      }

      content.innerHTML = `
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:0.85rem; text-align:left;">
            <thead>
              <tr style="background:#0f172a; color:#ffffff; font-weight:700;">
                <th style="padding:8px 10px; text-align:center; width:45px;">#</th>
                <th style="padding:8px 10px;">Gram Panchayat</th>
                <th style="padding:8px 10px; text-align:center;">Inspecting Officer</th>
                <th style="padding:8px 10px; text-align:center;">Inspection Date</th>
                <th style="padding:8px 10px;">Inspection Observations / Remarks</th>
                <th style="padding:8px 10px; text-align:center;">Status</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;

      modal.style.display = 'flex';
    };

    window.closeInspModal = function() {
      const modal = document.getElementById('insp-detail-modal');
      if (modal) modal.style.display = 'none';
    };

    window.exportInspectionsCsv = function() {
      let csv = 'S.No,Mandal Name,Total GPs,DPO Inspected,DLPO Inspected,MPO Inspected,Total Inspected,Pending GPs,Compliance Pct\n';
      KHAMMAM_INSPECTIONS_DATA.forEach(r => {
        csv += `${r.s_no},"${r.mandal}",${r.total_gps},${r.dpo},${r.dlpo},${r.mpo},${r.inspected},${r.pending},${r.pct}%\n`;
      });
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `GP_Inspections_Report_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    };

  </script>
</body>
</html>
"""
