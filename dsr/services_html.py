"""HTML template for the Services Overview Hub (/services).

Showcases all active and upcoming automation modules for e-Panchayat Automation:
- PS Attendance & DSR Report (Daily Morning)
- Multi-Day Attendance & DSR Analysis (Custom Date Ranges)
- Thursday GP Bank & Cash Balance Tracking (GM-R 14.2)
- Gram Panchayat Inspections (DPO, DLPO, MPO)
- House Tax DCB Analytics (Live Portal)
- Monthly Activity Statement (MAS & Births Register)
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
      max-width: 1140px;
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
    .service-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 20px;
      margin-top: 24px;
    }
    .service-card {
      background: #ffffff;
      border: 1.5px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .service-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 24px rgba(0,0,0,0.08);
      border-color: #cbd5e1;
    }
    .service-card.featured {
      border-color: #10b981;
      background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
    }
    .service-card.upcoming-highlight {
      border-color: #f59e0b;
      background: linear-gradient(180deg, #ffffff 0%, #fffdf8 100%);
    }
    .service-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .service-icon {
      width: 48px;
      height: 48px;
      border-radius: 10px;
      font-size: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .status-badge {
      font-size: 0.74rem;
      font-weight: 800;
      padding: 3px 10px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
    }
    .status-live {
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #86efac;
    }
    .status-upcoming {
      background: #fef3c7;
      color: #b45309;
      border: 1px solid #fde68a;
    }
    .status-active {
      background: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
    }
    .service-card h3 {
      font-size: 1.2rem;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 8px;
    }
    .service-card p {
      font-size: 0.9rem;
      color: #475569;
      line-height: 1.55;
      margin: 0;
      flex-grow: 1;
    }
    .service-meta {
      font-size: 0.82rem;
      background: #f8fafc;
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 18px;
      border: 1px solid #edf2f7;
    }
    .service-meta div {
      margin-bottom: 4px;
    }
    .service-meta div:last-child {
      margin-bottom: 0;
    }
    .btn-service {
      display: block;
      text-align: center;
      text-decoration: none;
      padding: 10px 16px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.9rem;
      transition: all 0.2s;
    }
    .btn-service-primary {
      background: #064e3b;
      color: white;
    }
    .btn-service-primary:hover {
      background: #065f46;
      color: #fbbf24;
    }
    .btn-service-outline {
      background: #ffffff;
      color: #064e3b;
      border: 1.5px solid #064e3b;
    }
    .btn-service-outline:hover {
      background: #ecfdf5;
    }
    .faq-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 16px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    .faq-question {
      font-size: 1.05rem;
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
    .footer-inner {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }
    .footer-links {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .footer-links a {
      color: #cbd5e1;
      text-decoration: none;
      transition: color 0.2s;
    }
    .footer-links a:hover {
      color: #fbbf24;
    }
    @media (max-width: 768px) {
      .hero-title { font-size: 1.65rem; }
      .hub-intro-card { padding: 22px 18px; }
      .nav-inner { height: auto; min-height: 58px; padding: 10px 14px; flex-wrap: wrap; gap: 8px; }
      .nav-brand { flex-wrap: wrap; gap: 6px; }
      .nav-links { width: 100%; justify-content: flex-start; flex-wrap: wrap; gap: 6px; }
      .footer-inner { flex-direction: column; text-align: center; }
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
      Welcome to e-Panchayat Automation
    </div>
    <h1 class="hero-title">Services &amp; Modules Hub</h1>
    <p class="hero-subtitle" style="font-weight:700; color:#ffffff; margin-bottom:8px;">
      Simplifying Panchayat Administration through Smart Reporting and Automation.
    </p>
    <p class="hero-subtitle" style="font-size:0.95rem;">
      Automated background robot pipelines, daily &amp; multi-day attendance analytics, weekly balance tracking, and real-time governance monitoring.
    </p>
  </section>

  <div class="page-container">
    <div class="hub-intro-card">
      <h2 style="font-size:1.5rem; color:#064e3b; margin:0 0 10px; font-weight:800;">
        Executive Service Architecture
      </h2>
      <p style="color:#475569; font-size:0.96rem; margin:0 0 20px; line-height:1.6;">
        e-Panchayat Automation eliminates manual portal clicking by running background headless browser robots equipped with AI OCR captcha solvers and OTP authentication. Review the active and upcoming analytical modules available after login below.
      </p>

      <div class="service-grid">
        <!-- Service 1: Daily PS Attendance & DSR Report -->
        <div class="service-card featured">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#059669;">⚡</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>PS Attendance &amp; DSR Report</h3>
          <p>
            Automated multi-report extraction of GM-R 1.2.7 DSR raw data, 1.2.11 Presentees, and 1.2.10 Absentees. Features custom cutoff times (e.g. 9:00 AM), 5 sorting options, matched secretary details, and 6-section Landscape District PDF compilation.
          </p>
        </div>

        <!-- Service 2: Multi-Day Attendance & DSR Report (Roadmap & Development) -->
        <div class="service-card upcoming-highlight">
          <div class="service-card-header">
            <div class="service-icon" style="background:#fef3c7; color:#b45309;">📅</div>
            <span class="status-badge status-upcoming">Roadmap &bull; Coming Soon</span>
          </div>
          <h3>Multi-Day Attendance &amp; DSR Report</h3>
          <p>
            Aggregate and analyze attendance trends across multiple days, weekly intervals, or custom date ranges. Automatically correlates daily punctuality, identifies chronic absentees, and prepares consolidated multi-day review sheets for DPO and DLPO, MPO reviews.
          </p>
        </div>

        <!-- Service 3: GP Thursday Bank Balance Tracking -->
        <div class="service-card featured">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#047857;">🏦</div>
            <span class="status-badge status-live">Active Robot</span>
          </div>
          <h3>Thursday GP Bank Balance Report</h3>
          <p>
            Automated compliance tracking for Thursday bank and cash balance entries (GM-R 14.2). Scrapes General Fund, SFC, 15th Finance Commission (Tied &amp; Untied), and TGBPASS accounts across all 589 Panchayats.
          </p>
        </div>

        <!-- Service 4: Gram Panchayat Inspections -->
        <div class="service-card upcoming-highlight">
          <div class="service-card-header">
            <div class="service-icon" style="background:#e0f2fe; color:#0284c7;">🔍</div>
            <span class="status-badge status-upcoming">Roadmap &bull; Coming Soon</span>
          </div>
          <h3>Gram Panchayat Inspections</h3>
          <p>
            Comprehensive compliance monitoring of field inspections conducted by District Panchayat Officers (DPO), Divisional Panchayat Officers (DLPO), and Mandal Panchayat Officers (MPO) with GP drill-down observations.
          </p>
        </div>

        <!-- Service 5: House Tax Collection (DCB) -->
        <div class="service-card featured">
          <div class="service-card-header">
            <div class="service-icon" style="background:#ecfdf5; color:#059669;">💰</div>
            <span class="status-badge status-live">100% Live Portal</span>
          </div>
          <h3>House Tax Demand Collection Balance</h3>
          <p>
            Real-time scraped analytics from the Telangana e-Panchayat tax server. Displays arrear demand, current assessments, collections, balances, and collection rates across all 20 Mandals and 589 Panchayats with zero login required.
          </p>
        </div>

        <!-- Service 6: Monthly Activity Statement (MAS) -->
        <div class="service-card" style="border-color:#059669; background:#f0fdf4;">
          <div class="service-card-header">
            <div class="service-icon" style="background:#dcfce7; color:#15803d;">📑</div>
            <span class="status-badge status-live">● Live &amp; Integrated</span>
          </div>
          <h3>Monthly Activity Statement (MAS)</h3>
          <p>
            Official 18-Indicator Executive Matrix (GM-R 5.24 &amp; GM-R 5.23 Births Register). Compiles the 2-page Legal Landscape PDF and 5-sheet styled Excel workbook using the shared Console EPTS session.
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
          Manual compilation of attendance, DSR, and balance registers takes hours every morning and requires logging into multiple portal sub-menus. e-Panchayat Automation executes these multi-step downloads in parallel in the background, applies automated absentees matching, and compiles ready-to-present executive PDF reports within 30–45 seconds.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ Are there any service or usage charges?</div>
        <div class="faq-answer">
          This platform is an independent productivity and analytics companion built to streamline Panchayat, Mandal, and District reporting workflows.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ When will Multi-Day Attendance &amp; DSR be available?</div>
        <div class="faq-answer">
          The Multi-Day Attendance &amp; DSR module is currently in active development. It will enable officers to select a date range (e.g. 1st to 7th of the month) and automatically download and aggregate multi-day attendance registers into a unified trend report.
        </div>
      </div>

      <div class="faq-card">
        <div class="faq-question">❓ How is data security and confidentiality ensured?</div>
        <div class="faq-answer">
          All browser automation sessions run in isolated sandboxes with end-to-end TLS 1.3 encryption. Passwords and OTPs are relayed directly to the state server and are purged from system memory upon session completion or logout.
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
