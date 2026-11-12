"""HTML Template for Manual Attendance / DSR Upload Page."""

UPLOAD_PAGE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PS Attendance &amp; DSR Analytics | e-Panchayat Automation Console</title>
  <style>
    :root { color-scheme: light; font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f3f7f5; color: #15332b; line-height: 1.5; }

    /* Top Navigation Bar */
    .navbar { position: sticky; top: 0; z-index: 1000; background: #0c3829; color: white; box-shadow: 0 2px 12px rgba(0,0,0,0.15); }
    .nav-inner { max-width: 1080px; margin: 0 auto; padding: 0 20px; display: flex; align-items: center; justify-content: space-between; height: 64px; }
    .nav-brand { display: flex; align-items: center; gap: 12px; text-decoration: none; color: white; cursor: pointer; }
    .nav-brand-logo { font-size: 1.7rem; line-height: 1; }
    .nav-brand-titles { display: flex; flex-direction: column; }
    .nav-brand-sup { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #8cd6b7; }
    .nav-brand-main { font-size: 1.05rem; font-weight: 800; letter-spacing: -0.01em; color: #ffffff; }

    .nav-menu { display: flex; align-items: center; gap: 6px; }
    .nav-link { color: #d4e8de; text-decoration: none; padding: 8px 14px; font-weight: 600; font-size: 0.92rem; border-radius: 8px; transition: all 0.15s; cursor: pointer; }
    .nav-link:hover { color: white; background: rgba(255,255,255,0.1); }
    .nav-link.active { color: white; background: #167451; }

    /* Submenu Dropdown */
    .dropdown { position: relative; display: inline-block; }
    .dropdown-btn { background: transparent; border: none; color: #d4e8de; padding: 8px 14px; font-weight: 600; font-size: 0.92rem; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.15s; font-family: inherit; }
    .dropdown-btn:hover { color: white; background: rgba(255,255,255,0.1); }
    .dropdown-btn.active { color: white; background: #167451; }
    .caret { font-size: 0.75rem; transition: transform 0.2s; }
    .dropdown:hover .caret, .dropdown.open .caret { transform: rotate(180deg); }

    .dropdown-menu { display: none; position: absolute; top: calc(100% + 4px); right: 0; min-width: 320px; background: white; border: 1px solid #d9e6df; border-radius: 14px; box-shadow: 0 16px 36px rgba(12,56,41,0.18); padding: 8px; z-index: 1001; }
    .dropdown:hover .dropdown-menu, .dropdown.open .dropdown-menu { display: block; animation: dropdownFade 0.15s ease-out; }
    @keyframes dropdownFade { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

    .dropdown-header { font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; color: #5a7369; padding: 8px 12px 4px; }
    .dropdown-divider { height: 1px; background: #e5eee9; margin: 6px 0; }
    .dropdown-item { display: flex; align-items: flex-start; gap: 10px; padding: 9px 12px; border-radius: 9px; text-decoration: none; color: #15332b; transition: background 0.15s; cursor: pointer; }
    .dropdown-item:hover { background: #f0f7f3; }
    .dropdown-item-icon { font-size: 1.25rem; line-height: 1.2; flex-shrink: 0; }
    .dropdown-item-content strong { display: block; font-size: 0.88rem; color: #15332b; font-weight: 700; }
    .dropdown-item-content span { font-size: 0.78rem; color: #5a7369; line-height: 1.35; display: block; }
    .dropdown-item.disabled { opacity: 0.65; cursor: not-allowed; background: transparent !important; }
    .badge-soon { display: inline-block; font-size: 0.68rem; font-weight: 700; background: #fef3c7; color: #92400e; padding: 1px 6px; border-radius: 4px; margin-top: 3px; text-transform: uppercase; letter-spacing: 0.04em; }

    /* Layout Container */
    main { max-width: 1080px; margin: 30px auto 60px; padding: 0 20px; }
    .page-view { display: none; }
    .page-view.active { display: block; }

    /* HOME VIEW STYLES */
    .hero-banner { background: linear-gradient(135deg, #0d3d2c 0%, #167451 100%); color: white; border-radius: 20px; padding: clamp(28px, 5vw, 44px); box-shadow: 0 16px 40px rgba(12,56,41,0.16); margin-bottom: 28px; position: relative; overflow: hidden; }
    .hero-banner::after { content: ""; position: absolute; right: -50px; bottom: -50px; width: 260px; height: 260px; background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%); border-radius: 50%; pointer-events: none; }
    .hero-badge { display: inline-block; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); color: #c4f2dc; font-size: 0.76rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; padding: 4px 10px; border-radius: 6px; margin-bottom: 12px; }
    .hero-title { margin: 0 0 10px; font-size: clamp(1.8rem, 4vw, 2.4rem); font-weight: 800; line-height: 1.2; letter-spacing: -0.02em; }
    .hero-desc { font-size: 1.02rem; line-height: 1.6; color: #e1f3ea; margin: 0; max-width: 760px; }

    .section-heading { display: flex; align-items: baseline; justify-content: space-between; margin: 34px 0 16px; }
    .section-heading h2 { margin: 0; font-size: 1.45rem; font-weight: 800; color: #15332b; letter-spacing: -0.01em; }
    .section-heading span { font-size: 0.88rem; color: #5a7369; font-weight: 500; }

    /* Module Cards Grid */
    .modules-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
    .module-card { background: white; border: 1px solid #d9e6df; border-radius: 18px; padding: 24px; box-shadow: 0 10px 30px rgba(23,59,43,0.06); display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s; position: relative; }
    .module-card:hover { transform: translateY(-3px); box-shadow: 0 16px 36px rgba(23,59,43,0.12); }
    .module-card.active-module { border: 2px solid #167451; background: #ffffff; }

    .module-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
    .module-icon-wrap { font-size: 2rem; width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: #eaf5ef; }
    .module-badge { font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 8px; border-radius: 6px; }
    .badge-live { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
    .badge-planned { background: #f3f4f6; color: #4b5563; border: 1px solid #e5e7eb; }

    .module-card h3 { margin: 0 0 8px; font-size: 1.2rem; font-weight: 700; color: #15332b; }
    .module-card p { font-size: 0.9rem; color: #4d665e; line-height: 1.55; margin: 0 0 18px; flex-grow: 1; }
    .module-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: auto; }

    .btn-action { display: inline-flex; align-items: center; gap: 6px; padding: 10px 16px; font-size: 0.88rem; font-weight: 700; border-radius: 8px; text-decoration: none; cursor: pointer; border: none; font-family: inherit; transition: background 0.15s; }
    .btn-primary { background: #167451; color: white; }
    .btn-primary:hover { background: #125e41; }
    .btn-secondary { background: #eaf5ef; color: #167451; border: 1px solid #b9ddcb; }
    .btn-secondary:hover { background: #d7ede1; }
    .btn-disabled { background: #f3f4f6; color: #9ca3af; cursor: not-allowed; border: 1px solid #e5e7eb; }

    /* Guidelines Notice Card on Home */
    .info-card { background: white; border: 1px solid #d9e6df; border-radius: 18px; padding: 26px; margin-top: 28px; box-shadow: 0 10px 30px rgba(23,59,43,0.05); }
    .info-card h3 { margin: 0 0 12px; font-size: 1.15rem; color: #15332b; }
    .guideline-list { margin: 0; padding-left: 20px; color: #486158; font-size: 0.92rem; line-height: 1.7; }

    /* REPORT VIEW STYLES */
    .breadcrumb-bar { margin-bottom: 16px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .back-btn { display: inline-flex; align-items: center; gap: 6px; color: #167451; text-decoration: none; font-weight: 700; font-size: 0.92rem; padding: 7px 14px; background: white; border: 1px solid #cfe0d7; border-radius: 8px; transition: background 0.15s; cursor: pointer; font-family: inherit; }
    .back-btn:hover { background: #eaf5ef; }

    .report-card { background: white; border: 1px solid #d9e6df; border-radius: 18px; padding: clamp(24px, 5vw, 42px); box-shadow: 0 14px 40px #173b2b12; max-width: 860px; margin: 0 auto; }
    .eyebrow { color: #247558; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; font-size: .8rem; }
    h1 { margin: 10px 0 6px; font-size: clamp(1.8rem, 4.5vw, 2.3rem); line-height: 1.15; }
    p.intro { line-height: 1.6; color: #486158; margin-top: 0; margin-bottom: 20px; }
    
    /* Navigation Tabs inside report */
    .tabs-header { display: flex; gap: 8px; margin: 20px 0 24px; border-bottom: 2px solid #e1ebe5; }
    .tab-btn { background: transparent; border: none; padding: 11px 20px; font-size: 0.98rem; font-weight: 700; color: #5a7369; cursor: pointer; border-radius: 8px 8px 0 0; transition: all .15s; border-bottom: 3px solid transparent; margin-bottom: -2px; font-family: inherit; }
    .tab-btn:hover { color: #167451; background: #f0f7f3; }
    .tab-btn.active { color: #167451; border-bottom: 3px solid #167451; background: #eef6f2; }

    .tab-content { display: none; }
    .tab-content.active { display: block; }

    .field-group { margin: 18px 0; }
    label { display: block; margin: 0 0 6px; font-weight: 650; font-size: 0.95rem; }
    .req { color: #c92a2a; }
    .badge { font-size: 0.74rem; font-weight: 700; padding: 2px 7px; border-radius: 5px; margin-left: 6px; text-transform: uppercase; letter-spacing: .04em; }
    .badge-rec { background: #e3f5eb; color: #167451; }
    .badge-opt { background: #fff3d6; color: #855c06; }
    .hint { font-size: 0.82rem; color: #5a7369; margin-top: 5px; line-height: 1.45; }
    input[type="file"], input[type="text"], select { width: 100%; box-sizing: border-box; padding: 11px 13px; border: 1px solid #bfd1c7; border-radius: 9px; background: white; color: #15332b; font-size: 0.95rem; font-family: inherit; }
    input[type="file"] { background: #fbfdfc; }
    button[type="submit"] { display: inline-block; border: 0; border-radius: 10px; background: #167451; color: white; padding: 13px 22px; font-weight: 700; font-size: 1rem; text-decoration: none; cursor: pointer; transition: background .15s; font-family: inherit; }
    button[type="submit"]:hover { background: #125e41; }
    button[type="submit"]:disabled { opacity: .6; cursor: wait; }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 24px; }
    .notice { margin: 16px 0; padding: 12px 14px; border-radius: 10px; background: #eef6f2; border-left: 4px solid #167451; color: #1b4938; line-height: 1.5; font-size: 0.88rem; }
    
    /* Inline Status & Alert Banners */
    .message { display: none; margin-top: 16px; padding: 13px 16px; border-radius: 10px; font-weight: 600; font-size: 0.92rem; line-height: 1.5; animation: fadeIn 0.2s ease-in; }
    .message.active { display: block; }
    .message.info { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .message.success { background: #dcfce7; color: #14532d; border: 1.5px solid #86efac; box-shadow: 0 4px 14px rgba(22, 116, 81, 0.08); }
    .message.error { background: #fee2e2; color: #991b1b; border: 1.5px solid #fca5a5; }
    .message-content { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
    .message-text { display: flex; align-items: center; gap: 10px; flex: 1; }
    .message-btn-open { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 6px; background: #167451; color: white; text-decoration: none; font-size: 0.84rem; font-weight: 700; cursor: pointer; border: none; transition: background 0.15s; }
    .message-btn-open:hover { background: #115d40; }

    /* Floating Download Toast & Notification Center */
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
      pointer-events: auto !important;
      -webkit-tap-highlight-color: transparent;
    }
    .download-toast-close:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.1);
    }
    .download-toast-actions {
      display: flex;
      gap: 8px;
      padding: 0 16px 14px 16px;
      pointer-events: auto !important;
    }
    .download-toast-btn-open {
      flex: 1;
      background: #16a34a;
      color: white !important;
      border: none;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: background 0.15s;
      text-decoration: none;
      pointer-events: auto !important;
      -webkit-tap-highlight-color: transparent;
    }
    .download-toast-btn-open:hover, .download-toast-btn-open:active {
      background: #15803d;
      color: white !important;
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
      pointer-events: auto !important;
      -webkit-tap-highlight-color: transparent;
    }
    .download-toast-btn-dismiss:hover, .download-toast-btn-dismiss:active {
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
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(-4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .fine-print { border-top: 1px solid #e5eee9; margin-top: 26px; padding-top: 18px; font-size: 0.88rem; color: #627b72; line-height: 1.55; }

    /* Footer */
    footer { border-top: 1px solid #dce6e1; margin-top: 60px; padding: 22px 20px; text-align: center; color: #5a7369; font-size: 0.84rem; background: white; }

    @media (max-width: 768px) {
      .nav-inner { height: auto; min-height: 58px; padding: 8px 12px; flex-wrap: wrap; gap: 6px; }
      .nav-brand { gap: 8px; }
      .nav-brand-main { font-size: 0.94rem; }
      .nav-menu { width: 100%; justify-content: flex-start; flex-wrap: wrap; gap: 4px; }
      .nav-brand-sup { display: none; }
      .nav-link, .dropdown-btn { padding: 7px 10px; font-size: 0.84rem; }
      .dropdown-menu { min-width: 270px; left: 0; right: auto; }
      .hero-banner { padding: 22px; }
    }
  </style>
</head>
<body>
  <!-- Top Navigation Bar -->
  <header class="navbar">
    <div class="nav-inner">
      <a class="nav-brand" href="#home" onclick="navigateTo('home'); return false;">
        <span class="nav-brand-logo">🏛️</span>
        <div class="nav-brand-titles" style="flex-direction:row; align-items:center; gap:8px; flex-wrap:wrap;">
          <span class="nav-brand-main">e-Panchayat Automation</span>
          <span id="subpage-console-pill" style="display:none; align-items:center; background:rgba(255,255,255,0.16); border:1px solid rgba(251,191,36,0.65); color:#fde68a; font-size:0.68rem; font-weight:800; padding:2px 8px; border-radius:999px; letter-spacing:0.35px; text-transform:uppercase;">e-Panchayat Automation Console</span>
        </div>
      </a>
      <nav class="nav-menu">
        <a class="nav-link" id="nav-main-portal" href="/">Main Dashboard</a>
        <a class="nav-link active" id="nav-home" href="#home" onclick="navigateTo('home'); return false;">Home</a>
        
        <!-- Reports Submenu Dropdown -->
        <div class="dropdown" id="reports-dropdown-container">
          <button type="button" class="dropdown-btn" id="nav-reports-btn" onclick="toggleDropdown()">
            Reports &amp; Analytics <span class="caret">▾</span>
          </button>
          <div class="dropdown-menu" id="reports-dropdown-menu">
            <div class="dropdown-header">Active Reports</div>
            <a class="dropdown-item" href="#reports-district" onclick="navigateTo('reports', 'district'); return false;">
              <span class="dropdown-item-icon">🏢</span>
              <div class="dropdown-item-content">
                <strong>District Level Monitoring</strong>
                <span>7-Section Comprehensive District PDF Report</span>
              </div>
            </a>
            <a class="dropdown-item" href="#reports-mandal" onclick="navigateTo('reports', 'mandal'); return false;">
              <span class="dropdown-item-icon">🏛️</span>
              <div class="dropdown-item-content">
                <strong>Mandal Level Monitoring</strong>
                <span>Focused 2-Page Mandal Officer PDF Report</span>
              </div>
            </a>
            <a class="dropdown-item" href="#reports-multiday" onclick="navigateTo('reports', 'multiday'); return false;">
              <span class="dropdown-item-icon">📅</span>
              <div class="dropdown-item-content">
                <strong>Multiple Days DSR Report</strong>
                <span>Consolidated Multi-Date PDF &amp; Excel Matrix</span>
                <span class="badge-soon">Upcoming</span>
              </div>
            </a>

            <div class="dropdown-divider"></div>
            <div class="dropdown-header">Tax &amp; DCB Analytics</div>

            <a class="dropdown-item" href="/reports/tax-dcb">
              <span class="dropdown-item-icon">💰</span>
              <div class="dropdown-item-content">
                <strong>House Tax Collection (DCB) Report</strong>
                <span>Live Demand, Collection &amp; Balance Analytics &amp; PDF</span>
                <span class="badge-live" style="margin-top:3px; display:inline-block; font-size:0.65rem; padding:1px 5px; border-radius:4px;">● Live</span>
              </div>
            </a>
          </div>
        </div>
      </nav>
    </div>
  </header>

  <main>
    <!-- VIEW 1: Home Dashboard -->
    <div id="view-home" class="page-view active">
      <section class="hero-banner">
        <span class="hero-badge">Welcome to e-Panchayat Automation · e-Panchayat Automation Console</span>
        <h1 class="hero-title">e-Panchayat Automation Console · Monitoring &amp; Reports</h1>
        <p style="margin:0 0 10px; font-size:1rem; font-weight:700; color:#fde68a;">
          Simplifying Panchayat Administration through Smart Reporting and Automation.
        </p>
        <p class="hero-desc">
          An independent Panchayat administration and analytics platform designed to empower District Officers and Mandal Officers with automated performance monitoring, daily morning attendance tracking, compliance management, and real-time administrative status analytics.
        </p>
      </section>

      <div class="section-heading">
        <h2>Departmental Reporting Modules</h2>
        <span>Select an active module or explore upcoming tools</span>
      </div>

      <div class="modules-grid">
        <!-- Module 1: PS Attendance & DSR Analytics (ACTIVE) -->
        <div class="module-card active-module">
          <div>
            <div class="module-card-header">
              <div class="module-icon-wrap">📋</div>
              <span class="module-badge badge-live">● Active · Live</span>
            </div>
            <h3>PS Attendance &amp; DSR Analytics</h3>
            <p>
              Upload portal exports to verify Panchayat Secretary morning attendance and Daily Status Report (DSR) entries. Generates official executive PDF reports for District Officers and Mandal MPOs/MPDOs with late submissions (after 9 AM) highlighted in red.
            </p>
          </div>
          <div class="module-actions">
            <button type="button" class="btn-action btn-primary" onclick="navigateTo('reports', 'district')">
              🏢 District Monitoring
            </button>
            <button type="button" class="btn-action btn-secondary" onclick="navigateTo('reports', 'mandal')">
              🏛️ Mandal Monitoring
            </button>
            <button type="button" class="btn-action btn-secondary" onclick="navigateTo('reports', 'multiday')">
              📅 Multiple Days DSR <span class="badge-soon" style="margin-top:0; margin-left:4px;">Upcoming</span>
            </button>
          </div>
        </div>

        <!-- Module 2: Tax Collection (ACTIVE) -->
        <div class="module-card active-module">
          <div>
            <div class="module-card-header">
              <div class="module-icon-wrap">💰</div>
              <span class="module-badge badge-live">● Active · Live</span>
            </div>
            <h3>House Tax Collection (DCB) Report</h3>
            <p>
              Live Demand, Collection, and Balance (DCB) monitoring with interactive Power BI visual-based analytical reports. Mandal-wise and District-level PDF reports are available for comprehensive monitoring, performance analysis
            </p>
          </div>
          <div class="module-actions">
            <a href="/reports/tax-dcb" class="btn-action btn-primary">
              📊 View DCB Analytics
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- VIEW 2: Report Tool (PS Attendance & DSR Analytics) -->
    <div id="view-reports" class="page-view">
      <div class="breadcrumb-bar">
        <a class="back-btn" href="/">🏠 Main Dashboard</a>
        <button type="button" class="back-btn" onclick="navigateTo('home')">
          ← Back to Home Dashboard
        </button>
      </div>

      <section class="report-card">
        <div class="eyebrow" id="page-eyebrow">e-Panchayat Automation Console &bull; Independent Reporting &amp; Analytics Workspace</div>
        <h1>PS Attendance &amp; DSR Analytics</h1>
        <p class="intro">Generate official Gram Panchayat morning attendance and DSR analytics reports directly from your uploaded portal exports.</p>
        
        <!-- Top Level Tabs -->
        <div class="tabs-header" role="tablist">
          <button type="button" class="tab-btn active" id="tab-btn-district" onclick="switchMonitoringTab('district')">
            🏢 District Level Monitoring
          </button>
          <button type="button" class="tab-btn" id="tab-btn-mandal" onclick="switchMonitoringTab('mandal')">
            🏛️ Mandal Level Monitoring
          </button>
          <button type="button" class="tab-btn" id="tab-btn-multiday" onclick="switchMonitoringTab('multiday')">
            📅 Multiple Days DSR <span class="badge-soon" style="margin-top:0; margin-left:4px;">Upcoming</span>
          </button>
        </div>

        <!-- TAB 1: District Level Monitoring -->
        <div id="tab-district" class="tab-content active">
          <div class="notice">
            <strong>District Monitoring:</strong> Automatically detects your District, all Mandals, and Gram Panchayats directly from the uploaded raw data file. When Presentees and Absentees files are provided, secretary details (Name, Mobile, Nature of Posting) are dynamically matched by LGD code.
          </div>

          <form id="upload-form" class="district-form">
            <div class="field-group">
              <label for="attendance-file">1. Attendance &amp; DSR Raw Data File <span class="req">*</span></label>
              <input id="attendance-file" name="file" type="file" required>
              <div class="hint">Upload web-downloaded report or portal export (.xls, .xlsx, .csv, or HTML table).</div>
            </div>

            <div class="field-group">
              <label for="presentees-file">2. Presentees PS Details File <span class="badge badge-rec">Recommended</span></label>
              <input id="presentees-file" name="presentees_file" type="file">
              <div class="hint">Export of present secretaries with Panchayat LGD Code, PS Name, Designation, Nature of Posting, and Mobile Number.</div>
            </div>

            <div class="field-group">
              <label for="absentees-file">3. Absentees PS Details File <span class="badge badge-opt">Optional</span></label>
              <input id="absentees-file" name="absentees_file" type="file">
              <div class="hint">Export of absent secretaries. Not required if all secretaries submitted attendance.</div>
            </div>

            <div class="field-group">
              <label for="district-page-layout">4. PDF Page Layout (Sections 2–6)</label>
              <select id="district-page-layout" name="page_layout" style="width:100%; padding:11px 13px; border:1px solid #bfd1c7; border-radius:9px; background:white; color:#15332b; font-size:0.95rem; font-family:inherit;">
                <option value="individual" selected>Individual Pages (Default — Separate Page per Report)</option>
                <option value="continuous">Continuation Page (Continue After Previous Table Ends)</option>
              </select>
              <div class="hint">Mandal Abstract stays on Page 1. Choose separate pages per section or continuous flow after each table ends.</div>
            </div>

            <div class="field-group" id="district-report-sections-box">
              <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
                <label style="margin:0;">5. Select Reports to Include</label>
                <label for="dist-sec-all" style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; background:#ecfdf5; border:1px solid #6ee7b7; color:#065f46; font-size:0.82rem; font-weight:700; cursor:pointer; user-select:none; margin:0;">
                  <input type="checkbox" id="dist-sec-all" checked onchange="toggleDistrictSections(this.checked)" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>All Reports</span>
                </label>
              </div>
              <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(250px, 1fr)); gap:8px;">
                <label for="dist-sec-abstract" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #bfd1c7; border-radius:8px; background:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; margin:0;">
                  <input type="checkbox" id="dist-sec-abstract" class="dist-sec-chk" value="abstract" checked onchange="syncDistrictSectionsAll()" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>MANDAL-WISE ATTENDANCE &amp; DSR ABSTRACT REPORT</span>
                </label>
                <label for="dist-sec-att-pending" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #bfd1c7; border-radius:8px; background:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; margin:0;">
                  <input type="checkbox" id="dist-sec-att-pending" class="dist-sec-chk" value="attendance_pending" checked onchange="syncDistrictSectionsAll()" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>ATTENDANCE PENDING GPs</span>
                </label>
                <label for="dist-sec-dsr-pending" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #bfd1c7; border-radius:8px; background:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; margin:0;">
                  <input type="checkbox" id="dist-sec-dsr-pending" class="dist-sec-chk" value="dsr_pending" checked onchange="syncDistrictSectionsAll()" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>DSR PENDING GPs</span>
                </label>
                <label for="dist-sec-leave" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #bfd1c7; border-radius:8px; background:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; margin:0;">
                  <input type="checkbox" id="dist-sec-leave" class="dist-sec-chk" value="leave" checked onchange="syncDistrictSectionsAll()" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>SECRETARIES REPORTED AS LEAVE</span>
                </label>
                <label for="dist-sec-meeting" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #bfd1c7; border-radius:8px; background:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; margin:0;">
                  <input type="checkbox" id="dist-sec-meeting" class="dist-sec-chk" value="meeting_training" checked onchange="syncDistrictSectionsAll()" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>SECRETARIES REPORTED AS TRAINING / MEETING</span>
                </label>
                <label for="dist-sec-after9" style="display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid #bfd1c7; border-radius:8px; background:#ffffff; font-size:0.82rem; font-weight:600; cursor:pointer; margin:0;">
                  <input type="checkbox" id="dist-sec-after9" class="dist-sec-chk" value="after_cutoff" checked onchange="syncDistrictSectionsAll()" style="width:15px; height:15px; accent-color:#0f766e; margin:0;">
                  <span>GPs THAT SUBMITTED ATTENDANCE AFTER 9 AM</span>
                </label>
              </div>
              <div class="hint">By default all reports are selected. Uncheck sections to generate only specific reports.</div>
            </div>

            <div class="actions">
              <button id="generate-button" type="submit">Generate and download report</button>
            </div>
            <div id="report-message" class="message" role="status" aria-live="polite"></div>
          </form>
        </div>

        <!-- TAB 2: Mandal Level Monitoring -->
        <div id="tab-mandal" class="tab-content">
          <div class="notice">
            <strong>Mandal Monitoring:</strong> Designed specifically for Mandal officers. Upload <strong>only your RAW data file</strong>. Your Mandal is detected automatically to generate the 2-page report: <strong>Page 1</strong> with Mandal Abstract Summary, Attendance Pending GPs, DSR Pending GPs, and GPs Submitted Attendance After 9 AM; <strong>Page 2</strong> with complete Gram Panchayat Attendance &amp; DSR Status (with times after 9:00 AM and pending DSR highlighted in red).
          </div>

          <form id="mandal-form">
            <div class="field-group">
              <label for="mandal-attendance-file">1. Attendance &amp; DSR Raw Data File <span class="req">*</span></label>
              <input id="mandal-attendance-file" name="file" type="file" required>
              <div class="hint">Upload your attendance raw data file (.xls, .xlsx, .csv, or portal export). Mandal name is auto-detected directly from the file.</div>
            </div>

            <div class="field-group">
              <label for="mandal-display">2. Uploaded Mandal</label>
              <input id="mandal-display" type="text" readonly placeholder="Mandal name will appear here automatically after upload..." style="font-weight: 600; color: #167451; background: #fbfdfc;">
              <input type="hidden" id="mandal-select" name="mandal_name">
              <div class="hint" id="mandal-detect-hint">Mandal name detected from the uploaded raw data file.</div>
            </div>

            <div class="field-group">
              <label for="mandal-page-layout">3. PDF Page Layout</label>
              <select id="mandal-page-layout" name="page_layout" style="width:100%; padding:11px 13px; border:1px solid #bfd1c7; border-radius:9px; background:white; color:#15332b; font-size:0.95rem; font-family:inherit;">
                <option value="individual" selected>Individual Pages (Default — Separate Page per Report)</option>
                <option value="continuous">Continuation Page (Continue After Previous Table Ends)</option>
              </select>
              <div class="hint">Keep Section 5 on a separate page or continue directly after the previous table ends.</div>
            </div>

            <div class="actions">
              <button id="mandal-generate-button" type="submit">Generate Mandal Report (PDF)</button>
            </div>
            <div id="mandal-report-message" class="message" role="status" aria-live="polite"></div>
          </form>
        </div>

        <!-- TAB 3: Multiple Days DSR Monitoring -->
        <div id="tab-multiday" class="tab-content">
          <div class="notice">
            <strong>Multiple Days DSR Consolidation:</strong> Select two or more daily GM-R 1.2.7 Attendance &amp; DSR spreadsheets (or a multi-date file) along with optional Presentees and Absentees directories to generate a consolidated <strong>Multi-Day Abstract PDF</strong> and <strong>4-Sheet Excel Workbook</strong> tracking punctuality, DSR completion, and recurring defaulters.
          </div>

          <form id="multiday-form">
            <div class="field-group">
              <label for="multiday-files">1. Daily Attendance &amp; DSR Raw Data Files (Select Multiple) <span class="req">*</span></label>
              <input id="multiday-files" name="files" type="file" multiple required>
              <div class="hint" id="multiday-files-hint">Hold Ctrl / Shift (or select multiple files in your picker) to upload 2 or more daily exports (.xls, .xlsx, .csv, or portal HTML tables).</div>
            </div>

            <div class="field-group">
              <label for="multiday-presentees-file">2. Presentees PS Details File <span class="badge badge-rec">Recommended</span></label>
              <input id="multiday-presentees-file" name="presentees_file" type="file">
              <div class="hint">Enriches Panchayat Secretary Name, Mobile Number, Designation, and Nature of Posting across all selected dates.</div>
            </div>

            <div class="field-group">
              <label for="multiday-absentees-file">3. Absentees PS Details File <span class="badge badge-opt">Optional</span></label>
              <input id="multiday-absentees-file" name="absentees_file" type="file">
              <div class="hint">Optional directory for completing contact details of absent secretaries.</div>
            </div>

            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:14px;">
              <div class="field-group" style="margin:0;">
                <label for="multiday-mandal">4. Mandal Filter <span class="badge badge-opt">Optional</span></label>
                <input id="multiday-mandal" name="mandal_name" type="text" placeholder="Leave blank for District (or type Mandal name)">
              </div>
              <div class="field-group" style="margin:0;">
                <label for="multiday-cutoff">5. Cutoff Time</label>
                <input id="multiday-cutoff" name="cutoff_time" type="time" value="09:00" style="width:100%; box-sizing:border-box; padding:11px 13px; border:1px solid #bfd1c7; border-radius:9px; background:white; color:#15332b; font-size:0.95rem; font-family:inherit;">
              </div>
            </div>

            <div class="actions">
              <button id="multiday-generate-button" type="submit">Generate Multiple Days DSR Report (PDF &amp; Excel)</button>
            </div>
            <div id="multiday-report-message" class="message" role="status" aria-live="polite"></div>
          </form>
        </div>

        <p class="fine-print">Supported formats: Excel (.xls, .xlsx), CSV, or portal HTML tables exported with a .xls extension. The PDF report downloads automatically once analytics finish.</p>
      </section>
    </div>
  </main>

  <!-- Floating Mobile/Desktop Download Notification Center -->
  <div id="download-toast-container" class="download-toast-container" style="display:none;" role="alert" aria-live="assertive">
    <div class="download-toast-card">
      <div class="download-toast-header">
        <div id="download-toast-icon" class="download-toast-icon-wrap loading">
          <div class="toast-spinner"></div>
        </div>
        <div class="download-toast-body">
          <div id="download-toast-title" class="download-toast-title">e-Panchayat Automation · Generating DSR Report...</div>
          <div id="download-toast-subtitle" class="download-toast-subtitle">Processing attendance data, please wait...</div>
        </div>
        <button type="button" id="download-toast-close-btn" class="download-toast-close" onclick="window.dismissDownloadToast &amp;&amp; window.dismissDownloadToast()" aria-label="Close notification">&times;</button>
      </div>
      <div id="download-toast-actions" class="download-toast-actions" style="display:none;">
        <button type="button" id="download-toast-pdf-btn" class="download-toast-btn-open" style="background:#1d4ed8; display:none;">
          <span>📥</span> Download PDF
        </button>
        <a id="download-toast-open-btn" class="download-toast-btn-open" href="#" target="_blank" rel="noopener noreferrer">
          <span>📄</span> Open / View PDF
        </a>
        <button type="button" id="download-toast-dismiss-btn" class="download-toast-btn-dismiss" onclick="window.dismissDownloadToast &amp;&amp; window.dismissDownloadToast()">
          Dismiss
        </button>
      </div>
      <div id="download-toast-progress-bar" class="download-toast-progress loading"></div>
    </div>
  </div>

  <footer>
    <div style="max-width:1080px; margin:0 auto; padding:6px 10px; text-align:center; line-height:1.55;">
      <strong style="display:block; font-size:0.95rem; font-weight:800; color:#0c3829;">e-Panchayat Automation</strong>
      <div style="font-size:0.84rem; color:#486158; margin-top:2px;">Simplifying Panchayat Administration through Smart Reporting and Automation.</div>
    </div>
  </footer>

  <script>
    (() => {
      // View Navigation
      window.navigateTo = function(view, tab, anchor, skipHashUpdate) {
        const homeView = document.getElementById('view-home');
        const reportsView = document.getElementById('view-reports');
        const navHome = document.getElementById('nav-home');
        const navReportsBtn = document.getElementById('nav-reports-btn');
        closeDropdown();

        if (view === 'reports') {
          homeView.classList.remove('active');
          reportsView.classList.add('active');
          navHome.classList.remove('active');
          navReportsBtn.classList.add('active');
          const targetHash = tab ? `#reports-${tab}` : '#reports';
          if (tab) {
            window.switchMonitoringTab(tab);
          }
          if (!skipHashUpdate && window.location.hash !== targetHash) {
            window.location.hash = targetHash;
          }
          if (!skipHashUpdate) window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
          reportsView.classList.remove('active');
          homeView.classList.add('active');
          navHome.classList.add('active');
          navReportsBtn.classList.remove('active');
          if (anchor) {
            const anchorHash = `#${anchor}`;
            if (!skipHashUpdate && window.location.hash !== anchorHash) {
              window.location.hash = anchorHash;
            }
            const el = document.getElementById(anchor);
            if (el) el.scrollIntoView({ behavior: 'smooth' });
          } else {
            if (!skipHashUpdate && window.location.hash && window.location.hash !== '#home') {
              window.location.hash = '#home';
            }
            if (!skipHashUpdate) window.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }
      };

      // Dropdown toggle
      const dropdownContainer = document.getElementById('reports-dropdown-container');
      window.toggleDropdown = function() {
        dropdownContainer.classList.toggle('open');
      };
      function closeDropdown() {
        dropdownContainer.classList.remove('open');
      }
      document.addEventListener('click', (e) => {
        if (!dropdownContainer.contains(e.target)) {
          closeDropdown();
        }
      });

      // Hash routing
      function handleHash(isInitialLoad) {
        const hash = window.location.hash.toLowerCase();
        const isInit = isInitialLoad === true;
        if (hash.startsWith('#reports-multiday')) {
          window.navigateTo('reports', 'multiday', null, isInit);
        } else if (hash.startsWith('#reports-mandal')) {
          window.navigateTo('reports', 'mandal', null, isInit);
        } else if (hash.startsWith('#reports-district') || hash.startsWith('#reports')) {
          window.navigateTo('reports', 'district', null, isInit);
        } else if (hash === '#guidelines' || hash === '#guidelines-section') {
          window.navigateTo('home', null, 'guidelines-section', isInit);
        } else {
          window.navigateTo('home', null, null, isInit || !hash);
        }
      }
      window.addEventListener('hashchange', () => handleHash(false));

      // Tab switching inside report
      window.switchMonitoringTab = function(mode) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        if (mode === 'multiday') {
          document.getElementById('tab-btn-multiday').classList.add('active');
          document.getElementById('tab-multiday').classList.add('active');
        } else if (mode === 'mandal') {
          document.getElementById('tab-btn-mandal').classList.add('active');
          document.getElementById('tab-mandal').classList.add('active');
        } else {
          document.getElementById('tab-btn-district').classList.add('active');
          document.getElementById('tab-district').classList.add('active');
        }
      };

      // State for active download toast & blobs
      let _activeBlobUrl = null;
      let _toastTimer = null;

      function requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
          try { Notification.requestPermission(); } catch(e){}
        }
      }

      window.dismissDownloadToast = function() {
        const container = document.getElementById('download-toast-container');
        const card = container ? container.querySelector('.download-toast-card') : null;
        if (!container) return;
        if (card) {
          card.classList.add('toast-exit');
          setTimeout(() => {
            container.style.display = 'none';
            card.classList.remove('toast-exit');
          }, 260);
        } else {
          container.style.display = 'none';
        }
        if (_toastTimer) {
          clearTimeout(_toastTimer);
          _toastTimer = null;
        }
      };

      function dismissDownloadToast() {
        window.dismissDownloadToast();
      }

      function showToastLoading(title, subtitle) {
        requestNotificationPermission();
        const container = document.getElementById('download-toast-container');
        const iconWrap = document.getElementById('download-toast-icon');
        const titleEl = document.getElementById('download-toast-title');
        const subtitleEl = document.getElementById('download-toast-subtitle');
        const actionsEl = document.getElementById('download-toast-actions');
        const progressBar = document.getElementById('download-toast-progress-bar');
        if (!container) return;

        if (_toastTimer) {
          clearTimeout(_toastTimer);
          _toastTimer = null;
        }

        container.style.display = 'block';
        const card = container.querySelector('.download-toast-card');
        if (card) card.classList.remove('toast-exit');

        iconWrap.className = 'download-toast-icon-wrap loading';
        iconWrap.innerHTML = '<div class="toast-spinner"></div>';
        titleEl.textContent = title || 'e-Panchayat Automation · Generating Report...';
        subtitleEl.textContent = subtitle || 'e-Panchayat Automation is processing attendance data, please wait...';
        actionsEl.style.display = 'none';
        progressBar.style.display = 'block';
        progressBar.className = 'download-toast-progress loading';
      }

      function showToastSuccess(title, subtitle, filename, viewUrl, onDownloadPdf = null) {
        const container = document.getElementById('download-toast-container');
        const iconWrap = document.getElementById('download-toast-icon');
        const titleEl = document.getElementById('download-toast-title');
        const subtitleEl = document.getElementById('download-toast-subtitle');
        const actionsEl = document.getElementById('download-toast-actions');
        const openBtn = document.getElementById('download-toast-open-btn');
        const pdfBtn = document.getElementById('download-toast-pdf-btn');
        const progressBar = document.getElementById('download-toast-progress-bar');
        if (!container) return;

        iconWrap.className = 'download-toast-icon-wrap success';
        iconWrap.innerHTML = '✅';
        titleEl.textContent = title || 'Download Complete!';
        subtitleEl.textContent = subtitle || `${filename} saved to Downloads.`;
        progressBar.style.display = 'none';
        actionsEl.style.display = 'flex';

        if (pdfBtn) {
          if (onDownloadPdf) {
            pdfBtn.style.display = 'inline-flex';
            pdfBtn.onclick = onDownloadPdf;
          } else {
            pdfBtn.style.display = 'none';
          }
        }

        if (viewUrl) {
          openBtn.style.display = 'inline-flex';
          openBtn.href = viewUrl;
          openBtn.onclick = null;
        } else {
          openBtn.style.display = 'none';
        }

        if ('Notification' in window && Notification.permission === 'granted') {
          try {
            new Notification('DSR Report Downloaded', {
              body: `${filename} has been saved to your downloads.`,
            });
          } catch(e){}
        }

        if (_toastTimer) clearTimeout(_toastTimer);
        _toastTimer = setTimeout(() => {
          window.dismissDownloadToast();
        }, 16000);
      }

      function showToastError(title, subtitle) {
        const container = document.getElementById('download-toast-container');
        const iconWrap = document.getElementById('download-toast-icon');
        const titleEl = document.getElementById('download-toast-title');
        const subtitleEl = document.getElementById('download-toast-subtitle');
        const actionsEl = document.getElementById('download-toast-actions');
        const openBtn = document.getElementById('download-toast-open-btn');
        const pdfBtn = document.getElementById('download-toast-pdf-btn');
        const progressBar = document.getElementById('download-toast-progress-bar');
        if (!container) return;

        iconWrap.className = 'download-toast-icon-wrap error';
        iconWrap.innerHTML = '⚠️';
        titleEl.textContent = title || 'Report Generation Failed';
        subtitleEl.textContent = subtitle || 'An error occurred while generating the report.';
        progressBar.style.display = 'none';
        actionsEl.style.display = 'flex';
        openBtn.style.display = 'none';
        if (pdfBtn) pdfBtn.style.display = 'none';

        if (_toastTimer) clearTimeout(_toastTimer);
        _toastTimer = setTimeout(() => {
          window.dismissDownloadToast();
        }, 8000);
      }

      function showMessage(element, messageHtml, status = 'info', extraActionsHtml = '') {
        if (!element) return;
        if (status === true) status = 'success';
        if (status === false) status = 'error';

        element.className = `message active ${status}`;
        if (status === 'success') {
          element.innerHTML = `
            <div class="message-content">
              <div class="message-text">
                <span style="font-size:1.35rem; line-height:1;">✅</span>
                <div style="flex:1;">${messageHtml}</div>
              </div>
              ${extraActionsHtml ? `<div class="message-actions-wrap" style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">${extraActionsHtml}</div>` : ''}
            </div>
          `;
        } else if (status === 'error') {
          element.innerHTML = `
            <div class="message-content">
              <div class="message-text">
                <span style="font-size:1.25rem; line-height:1;">⚠️</span>
                <div style="font-weight:600; color:#991b1b;">${messageHtml}</div>
              </div>
            </div>
          `;
        } else {
          element.innerHTML = `
            <div class="message-content">
              <div class="message-text">
                <span style="font-size:1.25rem; line-height:1;">⏳</span>
                <div style="font-weight:600; color:#0369a1;">${messageHtml}</div>
              </div>
            </div>
          `;
        }
      }

      window.downloadReportPdf = async function(jobId, fallbackPdfName) {
        showToastLoading('Downloading PDF Report...', 'Fetching generated PDF document…');
        try {
          const pdfResponse = await fetch(`/api/web/reports/${encodeURIComponent(jobId)}/download`, {
            credentials: 'same-origin'
          });
          if (!pdfResponse.ok) await readResponse(pdfResponse);
          const blob = await pdfResponse.blob();
          const objectUrl = URL.createObjectURL(blob);
          const disposition = pdfResponse.headers.get('Content-Disposition') || '';
          const fileName = /filename="?([^";]+)"?/i.exec(disposition)?.[1] || fallbackPdfName || 'Attendance_Report.pdf';

          const link = document.createElement('a');
          link.href = objectUrl;
          link.download = fileName;
          document.body.appendChild(link);
          link.click();
          link.remove();
          showToastSuccess('PDF Download Complete!', `${fileName} saved to Downloads.`, fileName, `/api/web/reports/${encodeURIComponent(jobId)}/view`);
          setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
        } catch (err) {
          showToastError('PDF Download Failed', err.message || 'Could not download PDF.');
        }
      };

      async function readResponse(response) {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = body.detail;
          const message = typeof detail === 'string' ? detail : (detail?.message || 'The request failed.');
          throw new Error(message);
        }
        return body;
      }

      async function apiJson(url, options = {}) {
        const response = await fetch(url, { credentials: 'same-origin', ...options });
        return readResponse(response);
      }

      // Dynamic Mandal detection when Mandal file is chosen
      const mandalFileInput = document.getElementById('mandal-attendance-file');
      const mandalDisplay = document.getElementById('mandal-display');
      const mandalSelect = document.getElementById('mandal-select');
      const mandalDetectHint = document.getElementById('mandal-detect-hint');

      mandalFileInput.addEventListener('change', async () => {
        const file = mandalFileInput.files[0];
        if (!file) return;
        mandalDisplay.value = 'Detecting Mandal from file…';
        mandalDetectHint.textContent = 'Reading uploaded file…';
        try {
          const data = new FormData();
          data.append('file', file);
          const meta = await apiJson('/api/web/detect-mandals', { method: 'POST', body: data });
          if (meta.mandals && meta.mandals.length > 0) {
            const mandalName = meta.mandals[0];
            mandalDisplay.value = mandalName;
            mandalSelect.value = mandalName;
            mandalDetectHint.textContent = `Detected District: ${meta.district_name || 'Telangana'} | Uploaded Mandal: ${mandalName}`;
          } else {
            mandalDisplay.value = 'No mandal found';
            mandalSelect.value = '';
            mandalDetectHint.textContent = 'Could not detect mandal in the file.';
          }
        } catch (err) {
          mandalDisplay.value = 'Failed to detect mandal';
          mandalSelect.value = '';
          mandalDetectHint.textContent = err.message || 'Error detecting mandal.';
        }
      });

      // Generic job runner
      async function runReportJob(formData, submitBtn, messageEl, fallbackFilename) {
        submitBtn.disabled = true;
        const isMandal = formData.get('report_mode') === 'mandal';
        const modeLabel = isMandal ? 'Mandal' : 'District';
        showToastLoading(`Generating ${modeLabel} DSR Report...`, 'Uploading attendance data to analytics engine...');
        showMessage(messageEl, `Uploading and processing ${modeLabel.toLowerCase()} attendance data…`, 'info');
        try {
          let job = await apiJson('/api/web/reports', { method: 'POST', body: formData });
          const jobId = job.job_id;
          if (!jobId) throw new Error('The service did not return a report job ID.');
          let attempts = 0;
          while (job.status === 'Submitted' || job.status === 'Processing') {
            const statusDetail = job.status === 'Processing' ? 'Analyzing GP attendance & generating PDF…' : 'Queued in processing pipeline…';
            showToastLoading(`Processing ${modeLabel} DSR Report...`, statusDetail);
            showMessage(messageEl, `Report ${job.status.toLowerCase()}… (${statusDetail})`, 'info');
            if (attempts++ > 180) throw new Error('The report is taking too long. Please try again later.');
            await new Promise(resolve => setTimeout(resolve, 2000));
            job = await apiJson(`/api/web/reports/${encodeURIComponent(jobId)}`);
          }
          if (job.status !== 'Completed') throw new Error(job.notes || 'The report job did not complete.');

          const pdfViewUrl = `/api/web/reports/${encodeURIComponent(jobId)}/view`;
          const pdfFallbackName = job.download_filename || fallbackFilename;

          if (isMandal) {
            // Mandal mode: Automatically download Page 2 (GP ATTENDANCE & DSR REPORT) in JPEG format
            showToastLoading('Downloading JPEG Report...', 'Fetching Page 2 (GP Attendance & DSR Report) image…');
            showMessage(messageEl, 'Report ready! Fetching Page 2 GP Attendance & DSR Report in JPEG format…', 'info');

            const imgResponse = await fetch(`/api/web/reports/${encodeURIComponent(jobId)}/download-image?page=2`, {
              credentials: 'same-origin'
            });
            if (!imgResponse.ok) await readResponse(imgResponse);
            const imgBlob = await imgResponse.blob();
            const imgObjectUrl = URL.createObjectURL(imgBlob);

            const imgDisposition = imgResponse.headers.get('Content-Disposition') || '';
            const imgFileName = /filename="?([^";]+)"?/i.exec(imgDisposition)?.[1] || `${pdfFallbackName.replace(/\.pdf$/i, '')}_GP_Attendance_DSR.jpg`;

            const link = document.createElement('a');
            link.href = imgObjectUrl;
            link.download = imgFileName;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(imgObjectUrl), 60000);

            // Show success message with prominent Download PDF button
            const actionButtonsHtml = `
              <button type="button" onclick="window.downloadReportPdf('${encodeURIComponent(jobId)}', '${pdfFallbackName}')" class="message-btn-open" style="background:#1d4ed8;">
                <span>📥</span> Download PDF
              </button>
              <a href="${pdfViewUrl}" target="_blank" rel="noopener noreferrer" class="message-btn-open">
                <span>📄</span> Open PDF
              </a>
              <a href="/api/web/reports/${encodeURIComponent(jobId)}/page-image?page=2&inline=true" target="_blank" rel="noopener noreferrer" class="message-btn-open" style="background:#0f766e;">
                <span>🖼️</span> View JPEG
              </a>
            `;

            const msgHtml = `
              <div style="font-weight:700; color:#14532d; font-size:0.95rem;">
                GP ATTENDANCE &amp; DSR REPORT (Page 2) downloaded automatically in JPEG format!
              </div>
              <div style="font-size:0.82rem; font-weight:500; color:#166534; margin-top:3px;">
                📁 ${imgFileName} &bull; Click &ldquo;Download PDF&rdquo; below to download the full PDF report.
              </div>
            `;

            showMessage(messageEl, msgHtml, 'success', actionButtonsHtml);
            showToastSuccess(
              'JPEG Report Downloaded!',
              `${imgFileName} saved to Downloads. Click 'Download PDF' for full document.`,
              imgFileName,
              pdfViewUrl,
              () => window.downloadReportPdf(jobId, pdfFallbackName)
            );
          } else {
            // District mode: Automatically download PDF
            showToastLoading('Downloading PDF Report...', 'Fetching generated document...');
            showMessage(messageEl, 'Report ready! Fetching and downloading PDF…', 'info');

            const pdfResponse = await fetch(`/api/web/reports/${encodeURIComponent(jobId)}/download`, {
              credentials: 'same-origin'
            });
            if (!pdfResponse.ok) await readResponse(pdfResponse);
            const blob = await pdfResponse.blob();

            if (_activeBlobUrl) {
              try { URL.revokeObjectURL(_activeBlobUrl); } catch(e){}
            }
            const objectUrl = URL.createObjectURL(blob);
            _activeBlobUrl = objectUrl;

            const disposition = pdfResponse.headers.get('Content-Disposition') || '';
            const fileName = /filename="?([^";]+)"?/i.exec(disposition)?.[1] || fallbackFilename;

            const link = document.createElement('a');
            link.href = objectUrl;
            link.download = fileName;
            document.body.appendChild(link);
            link.click();
            link.remove();

            const actionButtonsHtml = `
              <a href="${pdfViewUrl}" target="_blank" rel="noopener noreferrer" class="message-btn-open">
                <span>📄</span> Open PDF
              </a>
            `;
            const msgHtml = `
              <div style="font-weight:700; color:#14532d;">District PS Attendance Report downloaded successfully!</div>
              <div style="font-size:0.82rem; font-weight:500; color:#166534; margin-top:2px;">📁 ${fileName}</div>
            `;
            showMessage(messageEl, msgHtml, 'success', actionButtonsHtml);
            showToastSuccess('Download Complete!', `${fileName} saved to Downloads.`, fileName, pdfViewUrl);

            setTimeout(() => {
              if (_activeBlobUrl === objectUrl) {
                URL.revokeObjectURL(objectUrl);
                _activeBlobUrl = null;
              }
            }, 300000);
          }
        } catch (error) {
          const errMsg = error.message || 'Report generation failed.';
          showToastError('Report Generation Failed', errMsg);
          showMessage(messageEl, errMsg, 'error');
        } finally {
          submitBtn.disabled = false;
        }
      }

      window.toggleDistrictSections = (isChecked) => {
        document.querySelectorAll('.dist-sec-chk').forEach((chk) => { chk.checked = Boolean(isChecked); });
      };
      window.syncDistrictSectionsAll = () => {
        const items = Array.from(document.querySelectorAll('.dist-sec-chk'));
        const allChk = document.getElementById('dist-sec-all');
        if (allChk && items.length) {
          allChk.checked = items.every((c) => c.checked);
        }
      };

      // District form submission
      document.getElementById('upload-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const file = document.getElementById('attendance-file').files[0];
        if (!file) return;
        const data = new FormData();
        data.append('file', file);
        data.append('report_mode', 'district');
        const pres = document.getElementById('presentees-file').files[0];
        if (pres) data.append('presentees_file', pres);
        const abs = document.getElementById('absentees-file').files[0];
        if (abs) data.append('absentees_file', abs);
        const layout = (document.getElementById('district-page-layout') && document.getElementById('district-page-layout').value) || 'individual';
        const secItems = Array.from(document.querySelectorAll('.dist-sec-chk'));
        const checkedSecs = secItems.filter((c) => c.checked).map((c) => c.value);
        if (secItems.length && !checkedSecs.length) {
          showMessage(document.getElementById('report-message'), 'Please select at least one report section to generate.', 'error');
          return;
        }
        data.append('page_layout', layout);
        data.append('include_sections', checkedSecs.length === secItems.length ? 'all' : checkedSecs.join(','));
        runReportJob(data, document.getElementById('generate-button'), document.getElementById('report-message'), 'District_PS_Attendance_Report.pdf');
      });

      // Mandal form submission
      document.getElementById('mandal-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const file = mandalFileInput.files[0];
        if (!file) return;
        const mandalName = mandalSelect.value || mandalDisplay.value || '';
        const data = new FormData();
        data.append('file', file);
        data.append('report_mode', 'mandal');
        const layout = (document.getElementById('mandal-page-layout') && document.getElementById('mandal-page-layout').value) || 'individual';
        data.append('page_layout', layout);
        if (mandalName && mandalName !== 'No mandal found' && mandalName !== 'Failed to detect mandal' && mandalName !== 'Detecting Mandal from file…') {
          data.append('mandal_name', mandalName);
        }
        runReportJob(data, document.getElementById('mandal-generate-button'), document.getElementById('mandal-report-message'), `${mandalName || 'Mandal'}_Attendance_Report.pdf`);
      });

      const multidayFilesInput = document.getElementById('multiday-files');
      const multidayHint = document.getElementById('multiday-files-hint');
      if (multidayFilesInput && multidayHint) {
        multidayFilesInput.addEventListener('change', () => {
          const fl = Array.from(multidayFilesInput.files || []);
          multidayHint.textContent = fl.length
            ? `Selected ${fl.length} file(s): ${fl.map(f => f.name).join(', ')}`
            : 'Hold Ctrl / Shift (or select multiple files in your picker) to upload 2 or more daily exports (.xls, .xlsx, .csv, or portal HTML tables).';
        });
      }

      const multidayForm = document.getElementById('multiday-form');
      if (multidayForm) {
        multidayForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const selectedFiles = Array.from((multidayFilesInput && multidayFilesInput.files) || []);
          if (!selectedFiles.length) return;
          const submitBtn = document.getElementById('multiday-generate-button');
          const msgEl = document.getElementById('multiday-report-message');
          submitBtn.disabled = true;
          showToastLoading('Generating Multiple Days DSR Report...', `Consolidating ${selectedFiles.length} attendance file(s)...`);
          showMessage(msgEl, `Processing ${selectedFiles.length} daily file(s) and compiling consolidated PDF &amp; Excel…`, 'info');
          try {
            const fd = new FormData();
            selectedFiles.forEach((f) => fd.append('files', f));
            const pFile = document.getElementById('multiday-presentees-file').files[0];
            if (pFile) fd.append('presentees_file', pFile);
            const aFile = document.getElementById('multiday-absentees-file').files[0];
            if (aFile) fd.append('absentees_file', aFile);
            const mFilter = (document.getElementById('multiday-mandal').value || '').trim();
            if (mFilter) fd.append('mandal_name', mFilter);
            const cTime = (document.getElementById('multiday-cutoff').value || '09:00').trim();
            fd.append('cutoff_time', cTime);

            const job = await apiJson('/api/web/multi-day-reports', { method: 'POST', body: fd });
            const jobId = job.job_id;
            if (!jobId) throw new Error('The service did not return a report job ID.');

            const pdfRes = await fetch(`/api/web/reports/${encodeURIComponent(jobId)}/download`, { credentials: 'same-origin' });
            if (!pdfRes.ok) await readResponse(pdfRes);
            const pdfBlob = await pdfRes.blob();
            const pdfObjUrl = URL.createObjectURL(pdfBlob);
            const pdfName = job.download_filename || 'MultiDay_DSR_Report.pdf';
            const link = document.createElement('a');
            link.href = pdfObjUrl;
            link.download = pdfName;
            document.body.appendChild(link);
            link.click();
            link.remove();

            const pdfViewUrl = `/api/web/reports/${encodeURIComponent(jobId)}/view`;
            const excelDlUrl = `/api/web/reports/${encodeURIComponent(jobId)}/download-excel`;
            const excelName = job.excel_filename || 'MultiDay_DSR_Report.xlsx';
            const actionButtonsHtml = `
              <a href="${pdfViewUrl}" target="_blank" rel="noopener noreferrer" class="message-btn-open">
                <span>📄</span> Open PDF
              </a>
              <a href="${excelDlUrl}" download="${excelName}" class="message-btn-open" style="background:#0f766e;">
                <span>📊</span> Download Excel
              </a>
            `;
            const summaryTxt = `Multi-Day Consolidated Report (${job.days_count || 1} day(s): ${job.date_range || ''}, ${job.unique_gp_count || 0} GPs) compiled successfully!`;
            const msgHtml = `
              <div style="font-weight:700; color:#14532d;">${summaryTxt}</div>
              <div style="font-size:0.82rem; font-weight:500; color:#166534; margin-top:2px;">📁 ${pdfName} &bull; 📊 ${excelName}</div>
            `;
            showMessage(msgEl, msgHtml, 'success', actionButtonsHtml);
            showToastSuccess('Multi-Day Report Ready!', `${pdfName} downloaded.`, pdfName, pdfViewUrl);
            setTimeout(() => URL.revokeObjectURL(pdfObjUrl), 300000);
          } catch (err) {
            const errMsg = err.message || 'Multi-day report generation failed.';
            showToastError('Multi-Day Report Failed', errMsg);
            showMessage(msgEl, errMsg, 'error');
          } finally {
            submitBtn.disabled = false;
          }
        });
      }

      // Wire direct event listeners for toast dismissal
      const closeBtn = document.getElementById('download-toast-close-btn');
      if (closeBtn) closeBtn.onclick = () => window.dismissDownloadToast();
      const dismissBtn = document.getElementById('download-toast-dismiss-btn');
      if (dismissBtn) dismissBtn.onclick = () => window.dismissDownloadToast();

      // Handle initial route on page load
      handleHash(true);
    })();
  </script>
  <script>
    (() => {
      try {
        const sp = new URLSearchParams(window.location.search || '');
        const siteVal = (sp.get('site') || '').trim().toLowerCase();
        if (!siteVal || (siteVal !== 'console' && siteVal !== 'reports' && siteVal !== 'portal')) return;
        document.querySelectorAll('a[href]').forEach((a) => {
          const href = a.getAttribute('href') || '';
          if (!href.startsWith('/') || href.startsWith('//') || href.startsWith('/api/')) return;
          const parsed = new URL(href, window.location.origin);
          if (!parsed.searchParams.has('site')) {
            parsed.searchParams.set('site', siteVal);
            a.setAttribute('href', parsed.pathname + parsed.search + parsed.hash);
          }
        });
      } catch (e) {}
    })();
  </script>
</body>
</html>"""
