"""HTML template for the Services Overview Hub (/services).

Showcases all active and upcoming automation modules for e-Panchayat Automation:
- State Format DSR Report (14-Column Matrix)
- PS Attendance & DSR Report Robot (Daily Morning)
- Automated Multi-Days DSR Robot
- Thursday GP Bank & Cash Balance Tracking (GM-R 14.2)
- Gram Panchayat Weekly Inspections (GM-R 39.1)
- Monthly Activity Statement (MAS & Births Register)
- Live House Tax DCB Analytics (Real-Time Portal)
- Pending Mobile Number Assessments (Lookup Reconciliation)
- Manual Offline Reports (Daily & Multi-Day DSR)
- Excel & Data Studio (70+ Tools)
- All-in-One PDF Studio (14 Tools)
- Official Softwares & Drivers Hub
- Citizen Services & Trade Licences
"""

from __future__ import annotations


def get_services_page_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Services &amp; Modules Hub | e-Panchayat Automation</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220%22%3E<text y=%2226%22 font-size=%2226%22>🏛️</text></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #064e3b;
      --primary-dark: #022c22;
      --primary-light: #065f46;
      --accent-gold: #f59e0b;
      --accent-gold-hover: #d97706;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #475569;
      --border: #e2e8f0;
      --success: #059669;
      --info: #0284c7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
    }
    .navbar {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: var(--primary);
      color: white;
      box-shadow: 0 4px 16px rgba(0,0,0,0.15);
    }
    .nav-inner {
      max-width: 1200px;
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
      gap: 10px;
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
      gap: 10px;
      align-items: center;
    }
    .nav-link {
      color: #d1fae5;
      text-decoration: none;
      padding: 7px 12px;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: 600;
      transition: all 0.2s;
    }
    .nav-link:hover {
      background: rgba(255,255,255,0.12);
      color: white;
    }
    .hero-banner {
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
      color: white;
      padding: 48px 20px 42px;
      text-align: center;
      border-bottom: 3px solid var(--accent-gold);
    }
    .hero-title {
      font-size: 2.2rem;
      font-weight: 800;
      margin: 0 0 10px;
      letter-spacing: -0.5px;
    }
    .hero-subtitle {
      font-size: 1.05rem;
      color: #d1fae5;
      max-width: 820px;
      margin: 0 auto;
      line-height: 1.5;
    }
    .page-container {
      max-width: 1180px;
      margin: -24px auto 60px;
      padding: 0 20px;
    }
    .hub-intro-card {
      background: var(--card-bg);
      border-radius: 14px;
      border: 1px solid var(--border);
      padding: 32px 36px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.06);
      margin-bottom: 32px;
    }
    .section-heading-wrap {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 36px;
      margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 2px solid var(--border);
    }
    .section-heading-wrap:first-of-type {
      margin-top: 10px;
    }
    .section-icon-badge {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      flex-shrink: 0;
    }
    .section-title {
      font-size: 1.25rem;
      font-weight: 800;
      color: #0f172a;
      margin: 0;
    }
    .section-desc {
      font-size: 0.86rem;
      color: var(--text-muted);
      margin: 2px 0 0;
    }
    .service-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 20px;
      margin-top: 14px;
    }
    .service-card {
      background: #ffffff;
      border: 1.5px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 3px 12px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
    }
    .service-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 24px rgba(0,0,0,0.08);
      border-color: #cbd5e1;
    }
    .service-card.featured-green {
      border-color: #a7f3d0;
      background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
    }
    .service-card.featured-blue {
      border-color: #bae6fd;
      background: linear-gradient(180deg, #ffffff 0%, #f0f9ff 100%);
    }
    .service-card.featured-gold {
      border-color: #fde68a;
      background: linear-gradient(180deg, #ffffff 0%, #fffdf8 100%);
    }
    .service-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .service-icon {
      width: 46px;
      height: 46px;
      border-radius: 10px;
      font-size: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .status-badge {
      font-size: 0.72rem;
      font-weight: 800;
      padding: 4px 10px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      white-space: nowrap;
    }
    .status-live {
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #86efac;
    }
    .status-active {
      background: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
    }
    .status-tool {
      background: #f1f5f9;
      color: #334155;
      border: 1px solid #cbd5e1;
    }
    .status-upcoming {
      background: #fef3c7;
      color: #b45309;
      border: 1px solid #fde68a;
    }
    .service-card h3 {
      font-size: 1.15rem;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 8px;
    }
    .service-card p {
      font-size: 0.89rem;
      color: #475569;
      line-height: 1.55;
      margin: 0;
      flex-grow: 1;
    }
    .faq-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 22px 26px;
      margin-bottom: 16px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    .faq-question {
      font-size: 1.02rem;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .faq-answer {
      font-size: 0.92rem;
      color: #334155;
      line-height: 1.6;
    }
    footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 32px 20px;
      font-size: 0.88rem;
      border-top: 1px solid #1e293b;
    }
    @media (max-width: 768px) {
      .hero-title { font-size: 1.65rem; }
      .hub-intro-card { padding: 22px 18px; }
      .nav-inner { height: auto; min-height: 58px; padding: 10px 14px; flex-wrap: wrap; gap: 8px; }
      .nav-brand { flex-wrap: wrap; gap: 6px; }
      .nav-links { width: 100%; justify-content: flex-start; flex-wrap: wrap; gap: 6px; }
      .service-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header class="navbar">
    <div class="nav-inner">
      <a class="nav-brand" href="/">
        <span>🏛️</span>
        <span class="nav-brand-badge">e-Panchayat Automation</span>
        <span id="subpage-console-pill" style="display:none; align-items:center; background:rgba(255,255,255,0.16); border:1px solid rgba(251,191,36,0.6); color:#fde68a; font-size:0.7rem; font-weight:800; padding:3px 8px; border-radius:999px; letter-spacing:0.35px; text-transform:uppercase;">e-Panchayat Automation Console</span>
      </a>
      <nav class="nav-links">
        <a class="nav-link" href="/">🏠 Home</a>
        <a class="nav-link" href="/services" style="color:#fbbf24; font-weight:700;">📑 Services</a>
        <a class="nav-link" href="/login" style="color:#fbbf24;">🔐 Login</a>
      </nav>
    </div>
  </header>

  <section class="hero-banner">
    <div style="font-size:0.82rem; font-weight:800; color:#fde68a; letter-spacing:0.4px; text-transform:uppercase; margin-bottom:6px;">
      Welcome to Panchayat Automation
    </div>
    <h1 class="hero-title">Services &amp; Modules Hub</h1>
    <p class="hero-subtitle" style="font-weight:700; color:#ffffff; margin-bottom:8px;">
      Simplifying Panchayat Administration through Smart Reporting and Automation.
    </p>
    <p class="hero-subtitle" style="font-size:0.95rem;">
      Autonomous background robots, daily &amp; multi-day attendance analytics, weekly balance audits, inspection target tracking, and live revenue governance.
    </p>
  </section>

  <div class="page-container">
    <div class="hub-intro-card">
      <h2 style="font-size:1.5rem; color:#064e3b; margin:0 0 10px; font-weight:800;">
        Executive Service Architecture
      </h2>
      <p style="color:#475569; font-size:0.96rem; margin:0 0 20px; line-height:1.6;">
        e-Panchayat Automation eliminates tedious manual portal clicking by running background headless browser robots equipped with AI OCR captcha solvers and secure OTP authentication. Explore the complete active and upcoming analytical modules available on the platform below.
      </p>

      <!-- Category 1: Automated Reports Robots -->
      <div class="section-heading-wrap">
        <div class="section-icon-badge" style="background:#eff6ff; color:#1d4ed8;">⚡</div>
        <div>
          <h3 class="section-title">Automated Reports Robots</h3>
          <div class="section-desc">Single-click automated background scrapers that log in, navigate sub-menus, extract portal registers, and compile official PDF/Excel reports.</div>
        </div>
      </div>

      <div class="service-grid">
        <!-- 1. State Format DSR Report -->
        <div class="service-card featured-blue">
          <div class="service-card-header">
            <div class="service-icon" style="background:#eff6ff; color:#1d4ed8;">🏛️</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>State Format DSR Report</h3>
          <p>
            Official State Government 14-column mandal-wise attendance matrix with hourly arrival time buckets (6–9 AM, 9–10 AM, 10–11 AM, 11–12 Noon, After 12), % before 9 AM punctuality tracking, full-time working PS evaluation, and instant Landscape PDF &amp; styled Excel downloads. Fixed to current date.
          </p>
        </div>

        <!-- 2. Daily PS Attendance & DSR Report -->
        <div class="service-card featured-green">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#059669;">⚡</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>PS Attendance &amp; DSR Report</h3>
          <p>
            Automated multi-report extraction of GM-R 1.2.7 DSR raw data, 1.2.11 Presentees, and 1.2.10 Absentees. Features custom cutoff times (e.g. 9:00 AM), 5 sorting options, matched secretary details, and 6-section Landscape District PDF compilation within 30–45 seconds.
          </p>
        </div>

        <!-- 3. Automated Multi-Days DSR Robot -->
        <div class="service-card featured-green">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#059669;">📅</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>Multi-Day Attendance &amp; DSR Report</h3>
          <p>
            Automated date-range extraction of daily GM-R 1.2.7 raw data with automatic Sunday and Second Saturday exclusion, custom public holiday filtering, and complete multi-day consolidation into District Date-Wise, Mandal Date-Wise, and GP Period Summaries in PDF &amp; multi-sheet Excel.
          </p>
        </div>

        <!-- 4. Thursday GP Bank Balance Report -->
        <div class="service-card featured-green">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#047857;">🏦</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>Thursday GP Bank Balance Report</h3>
          <p>
            Automated compliance tracking for Thursday bank and cash balance entries (GM-R 14.2). Automatically extracts General Fund, SFC, 15th Finance Commission (Tied &amp; Untied), and TGBPASS accounts across all Panchayats, tracking % Data Entered and pending entries.
          </p>
        </div>

        <!-- 5. Gram Panchayat Inspections -->
        <div class="service-card featured-blue">
          <div class="service-card-header">
            <div class="service-icon" style="background:#e0f2fe; color:#0284c7;">🔍</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>Gram Panchayat Inspections</h3>
          <p>
            Automated GM-R 39.1 weekly inspection consolidation across MPO, MPDO, DLPO, DPO, CEO, and Deputy CEO designations. Features Submitted-only filtering, designation-based targets, balance tracking, dual counting modes (Attendence Date-Time vs. Monday selection), and Portrait A4 PDF &amp; Excel reports.
          </p>
        </div>

        <!-- 6. Monthly Activity Statement (MAS) -->
        <div class="service-card featured-green">
          <div class="service-card-header">
            <div class="service-icon" style="background:#dcfce7; color:#15803d;">📑</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>Monthly Activity Statement (MAS)</h3>
          <p>
            Official 18-Indicator Executive Matrix combining GM-R 5.24 Performance and GM-R 5.23 Births Register. Compiles the 2-page Legal Landscape PDF and 5-sheet styled Excel workbook using the shared Console EPTS session with zero duplicate logins.
          </p>
        </div>
      </div>

      <!-- Category 2: Revenue Governance & Data Reconciliation -->
      <div class="section-heading-wrap">
        <div class="section-icon-badge" style="background:#ecfdf5; color:#059669;">💰</div>
        <div>
          <h3 class="section-title">Revenue Governance &amp; Reconciliation</h3>
          <div class="section-desc">Public real-time tax monitoring and offline assessment reconciliation tools to ensure revenue accuracy and 100% data coverage.</div>
        </div>
      </div>

      <div class="service-grid">
        <!-- 7. House Tax Demand Collection Balance -->
        <div class="service-card featured-green">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#059669;">💰</div>
            <span class="status-badge status-live">100% Live Portal</span>
          </div>
          <h3>House Tax Demand Collection Balance</h3>
          <p>
            Real-time scraped analytics from the Telangana e-Panchayat tax server. Displays arrear demand, current assessments, collections, balances, and collection rates across all Mandals and Panchayats with zero login required, interactive drill-downs, and PowerBI-styled executive PDF/Excel exports.
          </p>
        </div>

        <!-- 8. Updation of Mobile Numbers to Assessments -->
        <div class="service-card featured-blue">
          <div class="service-card-header">
            <div class="service-icon" style="background:#eff6ff; color:#1d4ed8;">📱</div>
            <span class="status-badge status-active">Active Engine</span>
          </div>
          <h3>Pending Mobile Number Assessments (Lookup)</h3>
          <p>
            Reconciles Gram Panchayat House Tax Demand Register against the official Mobile Numbers Updated Report. Automatically detects missing mobile seeding by Assessment Number, computes coverage percentage, and produces styled Portrait A4 PDF and audit Excel workbooks.
          </p>
        </div>

        <!-- 9. Manual Offline Reports -->
        <div class="service-card">
          <div class="service-card-header">
            <div class="service-icon" style="background:#f1f5f9; color:#475569;">📊</div>
            <span class="status-badge status-tool">Offline Engine</span>
          </div>
          <h3>Manual DSR Offline Compilers</h3>
          <p>
            Upload previously downloaded GM-R 1.2.7 DSR spreadsheets along with optional Presentees and Absentees files to generate 6-Section Landscape District or 2-Page Mandal PDF reports instantly without requiring active portal credentials.
          </p>
        </div>
      </div>

      <!-- Category 3: Productivity Studios & Driver Hub -->
      <div class="section-heading-wrap">
        <div class="section-icon-badge" style="background:#f1f5f9; color:#334155;">🛠️</div>
        <div>
          <h3 class="section-title">Productivity Studios &amp; Driver Hub</h3>
          <div class="section-desc">Self-hosted officer tools for spreadsheet transformation, document security, and government portal desktop prerequisites.</div>
        </div>
      </div>

      <div class="service-grid">
        <!-- 10. Excel & Data Studio -->
        <div class="service-card">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#047857;">📊</div>
            <span class="status-badge status-tool">70+ Tools</span>
          </div>
          <h3>Excel &amp; Data Studio</h3>
          <p>
            Comprehensive in-browser spreadsheet suite: format converter, file merger, workbook comparator, column normalizer, date transformer, Bank/QuickBooks format exporter, and full-featured interactive grid editor for government data files.
          </p>
        </div>

        <!-- 11. All-in-One PDF Studio -->
        <div class="service-card">
          <div class="service-card-header">
            <div class="service-icon" style="background:#fef2f2; color:#b91c1c;">📄</div>
            <span class="status-badge status-tool">14 Tools</span>
          </div>
          <h3>All-in-One PDF Studio</h3>
          <p>
            Professional PDF document utilities: merge, split, compress, rotate, reorder, convert to/from images and documents, watermark, password-protect, and searchable RapidOCR for official government circulars, orders, and notices.
          </p>
        </div>

        <!-- 12. Official Softwares & Drivers Hub -->
        <div class="service-card">
          <div class="service-card-header">
            <div class="service-icon" style="background:#f0f9ff; color:#0369a1;">💻</div>
            <span class="status-badge status-tool">Downloads Hub</span>
          </div>
          <h3>Official Softwares &amp; Drivers Hub</h3>
          <p>
            One-stop curated repository of official biometric device drivers (Morpho, Mantra, Startek, SecuGen), RD services, Java DSC runtimes, Crystal Reports ASP.NET engines, and Telugu unicode typing tools for Panchayat field computers.
          </p>
        </div>
      </div>

      <!-- Category 4: Roadmap & Upcoming Modules -->
      <div class="section-heading-wrap">
        <div class="section-icon-badge" style="background:#fffbeb; color:#b45309;">🚀</div>
        <div>
          <h3 class="section-title">Roadmap &amp; Upcoming Modules</h3>
          <div class="section-desc">Next-generation governance tools currently in design and integration for state and district administration.</div>
        </div>
      </div>

      <div class="service-grid">
        <!-- 13. Citizen Services Monitoring -->
        <div class="service-card featured-gold">
          <div class="service-card-header">
            <div class="service-icon" style="background:#fef3c7; color:#b45309;">👥</div>
            <span class="status-badge status-upcoming">Roadmap &bull; Coming Soon</span>
          </div>
          <h3>Citizen Services Monitoring</h3>
          <p>
            Real-time tracking of citizen application delivery, birth and death certificate issuance, mutation requests, and statutory NOC timelines across Mandals to ensure zero pendency and full citizen satisfaction.
          </p>
        </div>

        <!-- 14. Trade Licences Automation -->
        <div class="service-card featured-gold">
          <div class="service-card-header">
            <div class="service-icon" style="background:#fef3c7; color:#b45309;">🏷️</div>
            <span class="status-badge status-upcoming">Roadmap &bull; Coming Soon</span>
          </div>
          <h3>Trade Licences Automation</h3>
          <p>
            Gram Panchayat business and trade licence issuance tracking, fee collection, renewal reminders, and commercial establishment assessment compliance automation across all Mandals.
          </p>
        </div>
      </div>
    </div>

    <!-- Frequently Asked Questions (FAQ) Section -->
    <div style="background:#ffffff; border-radius:14px; border:1px solid var(--border); padding:32px 36px; box-shadow:0 4px 20px rgba(0,0,0,0.06);">
      <h2 style="font-size:1.5rem; color:#064e3b; margin:0 0 20px; font-weight:800;">
        Frequently Asked Questions (FAQ)
      </h2>

      <div class="faq-card">
        <div class="faq-question">❓ What is the purpose of e-Panchayat Automation?</div>
        <div class="faq-answer">
          Manual compilation of attendance, DSR, inspections, and balance registers takes hours every day and requires navigating complex portal sub-menus. e-Panchayat Automation executes multi-step downloads in parallel in the background, applies automated absentees matching and target evaluations, and compiles ready-to-present executive PDF and Excel reports within 30–45 seconds.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ Which modules run automatically via robots versus offline manual upload?</div>
        <div class="faq-answer">
          Robots (such as State Format DSR, PS Attendance DSR, Multi-Days DSR, Thursday GP Balance, Inspections GM-R 39.1, and MAS) connect directly to the portal session to download and process files automatically. Offline reconciliation tools (such as Pending Mobile Number Assessments and Manual DSR) allow officers to upload exported spreadsheets and generate instant audit reports without logging in.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ Are there any service or usage charges?</div>
        <div class="faq-answer">
          This platform is an independent productivity and analytics companion built to streamline Panchayat, Mandal, and District reporting workflows.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ How is data security and confidentiality ensured?</div>
        <div class="faq-answer">
          All browser automation sessions run in isolated sandboxes with end-to-end TLS 1.3 encryption. Passwords and OTPs are relayed directly to the state server and are purged from system memory upon session completion or logout.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ Can generated reports be exported to Excel and PDF?</div>
        <div class="faq-answer">
          Yes. Every automated and manual module provides official government-standard PDF deliverables (formatted in landscape or portrait as required by state review standards) along with styled, formula-enabled Excel workbooks for deep analytical drill-downs.
        </div>
      </div>
    </div>
  </div>

  <footer>
    <div style="max-width:1200px; margin:0 auto; padding:6px 10px; text-align:center; line-height:1.55;">
      <strong style="display:block; font-size:0.95rem; font-weight:800; color:#f8fafc;">e-Panchayat Automation</strong>
      <div style="font-size:0.84rem; color:#cbd5e1; margin-top:2px;">Simplifying Panchayat Administration through Smart Reporting and Automation.</div>
    </div>
  </footer>
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
</html>
"""
