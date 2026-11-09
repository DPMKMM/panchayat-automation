"""HTML templates for Privacy Policy, Terms of Service, and Services Hub.

Designed to match the dark-green and gold executive aesthetic of e-Panchayat Automation.
"""

from __future__ import annotations


COMMON_HEAD = """
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
    .nav-link.active {
      background: rgba(255,255,255,0.18);
      color: #fbbf24;
    }
    .hero-banner {
      background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
      color: white;
      padding: 48px 20px 40px;
      text-align: center;
      border-bottom: 3px solid var(--accent-gold);
    }
    .hero-title {
      font-size: 2.1rem;
      font-weight: 800;
      margin: 0 0 10px;
      letter-spacing: -0.5px;
    }
    .hero-subtitle {
      font-size: 1.05rem;
      color: #d1fae5;
      max-width: 780px;
      margin: 0 auto;
      line-height: 1.5;
    }
    .page-container {
      max-width: 1080px;
      margin: -24px auto 60px;
      padding: 0 20px;
    }
    .legal-card {
      background: var(--card-bg);
      border-radius: 14px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.06);
      border: 1px solid var(--border);
      padding: 40px 44px;
    }
    .effective-date {
      display: inline-block;
      background: #ecfdf5;
      color: #065f46;
      border: 1px solid #a7f3d0;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.82rem;
      font-weight: 700;
      margin-bottom: 24px;
    }
    .legal-section {
      margin-bottom: 32px;
    }
    .legal-section h2 {
      font-size: 1.25rem;
      color: var(--primary);
      margin: 0 0 12px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 1.5px solid #f1f5f9;
      padding-bottom: 8px;
    }
    .legal-section p {
      color: #334155;
      font-size: 0.95rem;
      line-height: 1.65;
      margin: 0 0 12px;
    }
    .legal-section ul {
      margin: 8px 0 16px 20px;
      padding: 0;
      color: #334155;
      font-size: 0.95rem;
    }
    .legal-section li {
      margin-bottom: 8px;
      line-height: 1.55;
    }
    .notice-box {
      background: #f8fafc;
      border-left: 4px solid var(--accent-gold);
      padding: 14px 18px;
      border-radius: 6px;
      margin: 16px 0;
      font-size: 0.9rem;
      color: #1e293b;
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
      .legal-card { padding: 24px 20px; }
      .hero-title { font-size: 1.6rem; }
      .nav-inner { padding: 0 14px; }
      .footer-inner { flex-direction: column; text-align: center; }
    }
  </style>
"""

COMMON_NAV = """
  <header class="navbar">
    <div class="nav-inner">
      <a class="nav-brand" href="/">
        <span>🏛️</span>
        <span class="nav-brand-badge">e-Panchayat Automation</span>
      </a>
      <nav class="nav-links">
        <a class="nav-link" href="/">🏠 Home</a>
        <a class="nav-link" href="/services-inspections-bal">📑 Services Hub</a>
        <a class="nav-link" href="/#tax-station">💰 House Tax (DCB)</a>
        <a class="nav-link" href="/privacy">🛡️ Privacy</a>
        <a class="nav-link" href="/terms">⚖️ Terms</a>
        <a class="nav-link" href="/login" style="color:#fbbf24;">🔐 Login</a>
      </nav>
    </div>
  </header>
"""

COMMON_FOOTER = """
  <footer>
    <div class="footer-inner">
      <div>
        <strong>e-Panchayat Automated Console</strong> &bull; Executive Analytics Platform
        <div style="font-size:0.78rem; color:#64748b; margin-top:4px;">
          Dedicated administrative companion tool for Telangana Panchayat Raj &amp; Rural Development officers.
        </div>
      </div>
      <div class="footer-links">
        <a href="/">Home</a>
        <a href="/services-inspections-bal">Services Hub</a>
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Terms of Service</a>
        <a href="/#tax-station">House Tax (DCB)</a>
        <a href="/login">Officer Login</a>
      </div>
    </div>
  </footer>
"""


def get_privacy_html() -> str:
    """Returns the Privacy Policy HTML page."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <title>Privacy Policy | e-Panchayat Automation Platform</title>
  {COMMON_HEAD}
</head>
<body>
  {COMMON_NAV}

  <section class="hero-banner">
    <h1 class="hero-title">Privacy Policy</h1>
    <p class="hero-subtitle">
      Transparent data handling, strict session isolation, and departmental privacy standards for Panchayat, Mandal, and District officers.
    </p>
  </section>

  <div class="page-container">
    <div class="legal-card">
      <div class="effective-date">📅 Effective Date: November 2026 &bull; Version 4.0</div>

      <div class="notice-box">
        <strong>Executive Summary:</strong> e-Panchayat Automation is an administrative companion system designed to streamline report generation. We do not sell, rent, or permanently retain portal login passwords or citizen personal data. All scraping and file processing occur in temporary, isolated browser sessions with automated memory purges.
      </div>

      <div class="legal-section">
        <h2>1. Information We Collect and Process</h2>
        <p>To provide automated scraping and instant report generation, our platform processes only the minimum data required:</p>
        <ul>
          <li><strong>e-Panchayat Portal Authentication:</strong> When you login, your departmental user ID, password, and the 6-digit one-time password (OTP) are relayed securely over encrypted TLS connections to the official e-Panchayat portal (<code>epanchayat.telangana.gov.in</code>). Credentials are used strictly in-memory to establish an authenticated browser session and are <strong>never stored permanently in plaintext</strong>.</li>
          <li><strong>Uploaded or Downloaded Reporting Files:</strong> Raw reports including Daily Status Report (GM-R 1.2.7), Presentees (GM-R 1.2.11), Absentees (GM-R 1.2.10), Thursday Bank Balances (GM-R 14.2), and House Tax Demand Collection Balance data are processed in ephemeral, session-specific scratch storage.</li>
          <li><strong>Session Identifiers:</strong> A pseudorandom, cryptographically secure 128-bit session token (<code>epts_session_id</code>) is generated per browser profile to ensure complete multi-user isolation.</li>
          <li><strong>Technical Logs:</strong> Minimal anonymous technical logs (request timestamps, HTTP status codes, error codes) are maintained to troubleshoot State Data Center connectivity issues and prevent denial-of-service abuse.</li>
        </ul>
      </div>

      <div class="legal-section">
        <h2>2. How We Use Information</h2>
        <p>Data processed through this platform is used exclusively for:</p>
        <ul>
          <li>Authenticating your session with the Telangana e-Panchayat server.</li>
          <li>Automating the retrieval of official morning attendance, DSR registers, GP bank balances, and House Tax metrics.</li>
          <li>Compiling formatted Executive Reports, 1-page landscape combined district abstracts, and drill-down tables.</li>
          <li>Preventing State Data Center server overload through a 3-minute safety micro-cache with an exclusive on-demand bypass for authorized district administrators (<code>DPOA3698</code>).</li>
        </ul>
      </div>

      <div class="legal-section">
        <h2>3. Data Security & Storage Isolation</h2>
        <p>We implement rigorous defense-in-depth security measures to protect governance data:</p>
        <ul>
          <li><strong>Process Isolation:</strong> Each officer session operates in an independent, isolated browser context and sandbox directory. Other users cannot access or view your downloads.</li>
          <li><strong>Automatic Session Expiry:</strong> Regular sessions automatically close after inactivity, purging temporary portal caches. Authorized district administrative sessions retain state with encrypted session keepalives.</li>
          <li><strong>Cryptographic Protection:</strong> All communication between your client device and our service utilizes TLS 1.3 / HTTPS 256-bit encryption. Strict Anti-Clickjacking (<code>X-Frame-Options: SAMEORIGIN</code>), Anti-Sniffing (<code>nosniff</code>), and Content Security headers are enforced on every response.</li>
          <li><strong>No Permanent Citizen Data Storage:</strong> Citizen birth/death details, individual tax payments, and secretary personal numbers are not persisted in external marketing databases or sold to third parties.</li>
        </ul>
      </div>

      <div class="legal-section">
        <h2>4. Non-Affiliation & Independent Utility Disclaimer</h2>
        <p>
          e-Panchayat Automation (<code>panchayatautomation.in</code>) is an independent automation and reporting companion platform developed to assist Panchayat Raj &amp; Rural Development officers in compiling statutory reviews. It is not an official portal of the Government of Telangana or the National Informatics Centre (NIC). It operates solely as an authorized user-agent client connecting to the official portal on behalf of authenticated officers.
        </p>
      </div>

      <div class="legal-section">
        <h2>5. Cookies & Local Storage</h2>
        <p>
          Our platform does not use advertising cookies, commercial tracking pixels, or cross-site tracking scripts. We utilize only essential session storage (<code>sessionStorage</code> and <code>localStorage</code>) to maintain your active station navigation and store your anonymous session token with <code>SameSite=Lax</code> and <code>HttpOnly</code> flags.
        </p>
      </div>

      <div class="legal-section">
        <h2>6. Officer Rights & Session Termination</h2>
        <p>
          You have full control over your active session. Clicking <strong>🔒 Logout</strong> immediately terminates the underlying background browser instance, revokes active portal cookies, and deletes cached report files from the server's working directory.
        </p>
      </div>

      <div class="legal-section">
        <h2>7. Policy Updates</h2>
        <p>
          This policy may be updated periodically to reflect new administrative modules (such as Multi-Day Attendance analysis or MAS updates). Revisions will be published on this page with an updated effective date.
        </p>
      </div>

      <div class="legal-section">
        <h2>8. Contact & Support</h2>
        <p>
          For technical inquiries, departmental integration questions, or feedback regarding data security, please reach out through the official Executive Analytics Console or contact the platform administrator at:
        </p>
        <div style="background:#f1f5f9; padding:12px 18px; border-radius:8px; font-weight:600; color:#1e293b; display:inline-block;">
          📧 Platform Administration: <code>admin@panchayatautomation.in</code> &bull; Khammam District Console
        </div>
      </div>
    </div>
  </div>

  {COMMON_FOOTER}
</body>
</html>
"""


def get_terms_html() -> str:
    """Returns the Terms of Service HTML page."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <title>Terms of Service | e-Panchayat Automation Platform</title>
  {COMMON_HEAD}
</head>
<body>
  {COMMON_NAV}

  <section class="hero-banner">
    <h1 class="hero-title">Terms of Service</h1>
    <p class="hero-subtitle">
      Operational guidelines, permitted administrative use, and service commitments for Panchayat, Mandal, and District officers.
    </p>
  </section>

  <div class="page-container">
    <div class="legal-card">
      <div class="effective-date">📅 Effective Date: November 2026 &bull; Version 4.0</div>

      <div class="notice-box">
        <strong>Welcome to e-Panchayat Automation:</strong> By accessing <code>panchayatautomation.in</code>, you agree to comply with these Terms of Service. This platform is provided to streamline daily governance workflows, punctuality tracking, and financial analytics for authorized officers.
      </div>

      <div class="legal-section">
        <h2>1. Permitted Use & Officer Eligibility</h2>
        <p>
          This platform is designed for authorized departmental personnel of the Panchayat Raj &amp; Rural Development Department, Telangana, including:
        </p>
        <ul>
          <li>District Panchayat Officers (DPO) and Divisional Panchayat Officers (DLPO).</li>
          <li>Mandal Panchayat Officers (MPO) and Mandal Parishad Development Officers (MPDO).</li>
          <li>Panchayat Secretaries (PS) and departmental executive analytics staff.</li>
        </ul>
        <p>
          You agree to use this platform strictly for authorized administrative reviews, attendance verification, Thursday bank balance reconciliation, House Tax collection tracking, and official report preparation.
        </p>
      </div>

      <div class="legal-section">
        <h2>2. User Obligations & Account Security</h2>
        <p>When using e-Panchayat Automation, you agree to:</p>
        <ul>
          <li>Authenticate only with your own valid, authorized e-Panchayat portal credentials.</li>
          <li>Keep your login OTP confidential and never share active browser sessions with unauthorized third parties.</li>
          <li>Not use this platform to flood the State Data Center (SDC) with automated high-frequency request loops outside sanctioned report compilation.</li>
          <li>Not upload corrupted, malicious, or unauthorized binary files intended to disrupt background server processes.</li>
        </ul>
      </div>

      <div class="legal-section">
        <h2>3. Ownership & Intellectual Property</h2>
        <p>
          All proprietary background automation algorithms, AI OCR captcha solving pipelines, report layout templates, and web user interfaces remain the intellectual property of the platform developer. 
        </p>
        <p>
          Reports generated through the platform (including PDF abstracts and Excel workbooks) are compiled for the administrative benefit of the District Administration and may be freely distributed for departmental monitoring and review meetings.
        </p>
      </div>

      <div class="legal-section">
        <h2>4. Data Accuracy & Verification Disclaimer</h2>
        <p>
          Automated reports generated by this tool directly reflect data recorded on the official Telangana e-Panchayat portal (<code>epanchayat.telangana.gov.in</code>). While our background algorithms perform rigorous absentees matching, cross-referencing, and LGD validation, officers are advised to verify critical statutory submissions against portal records before presenting them in formal government proceedings.
        </p>
      </div>

      <div class="legal-section">
        <h2>5. Service Availability & State Data Center Dependencies</h2>
        <p>
          Because our platform connects in real-time to the Telangana State Data Center:
        </p>
        <ul>
          <li>Portal maintenance windows, firewall throttling, or 503 Gateway outages on the state server may occasionally delay report fetching.</li>
          <li>Our system implements automatic retry loops and micro-caching to mitigate portal downtime.</li>
          <li>We reserve the right to deploy scheduled updates to support new portal modules (e.g. Multi-Day DSR, MAS Births Register, and Inspections).</li>
        </ul>
      </div>

      <div class="legal-section">
        <h2>6. Limitation of Liability</h2>
        <p>
          In no event shall the developers or administrators of e-Panchayat Automation be liable for any indirect, incidental, or operational delays arising from state portal server failures, network dropouts, or unauthorized misuse of login credentials.
        </p>
      </div>

      <div class="legal-section">
        <h2>7. Continuous Improvements & Feature Roadmap</h2>
        <p>
          e-Panchayat Automation is continually evolving. New modules—such as <strong>Multi-Day Attendance &amp; DSR trend analysis</strong>, <strong>18-Indicator Monthly Activity Statement (MAS)</strong>, and <strong>MPO/DLPO GP Inspections registries</strong>—are released iteratively to provide comprehensive governance automation.
        </p>
      </div>

      <div class="legal-section">
        <h2>8. Contact & Administration</h2>
        <p>
          For questions regarding these Terms of Service or to report operational issues, please contact the platform administration console at <code>admin@panchayatautomation.in</code>.
        </p>
      </div>
    </div>
  </div>

  {COMMON_FOOTER}
</body>
</html>
"""


def get_services_hub_html() -> str:
    """Returns the Services & Inspections Overview Hub HTML page."""
    return f"""<!doctype html>
<html lang="en">
<head>
  <title>Services & Modules Hub | e-Panchayat Automation</title>
  {COMMON_HEAD}
  <style>
    .service-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 20px;
      margin-top: 24px;
    }}
    .service-card {{
      background: #ffffff;
      border: 1.5px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 4px 14px rgba(0,0,0,0.04);
      display: flex;
      flex-direction: column;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .service-card:hover {{
      transform: translateY(-3px);
      box-shadow: 0 8px 24px rgba(0,0,0,0.08);
      border-color: #cbd5e1;
    }}
    .service-card.featured {{
      border-color: #10b981;
      background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
    }}
    .service-card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }}
    .service-icon {{
      width: 48px;
      height: 48px;
      border-radius: 10px;
      background: #ecfdf5;
      color: #059669;
      font-size: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .status-badge {{
      font-size: 0.74rem;
      font-weight: 800;
      padding: 3px 10px;
      border-radius: 12px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
    }}
    .status-live {{
      background: #dcfce7;
      color: #15803d;
      border: 1px solid #86efac;
    }}
    .status-upcoming {{
      background: #fef3c7;
      color: #b45309;
      border: 1px solid #fde68a;
    }}
    .status-active {{
      background: #e0f2fe;
      color: #0369a1;
      border: 1px solid #bae6fd;
    }}
    .service-card h3 {{
      font-size: 1.2rem;
      font-weight: 700;
      color: #0f172a;
      margin: 0 0 8px;
    }}
    .service-card p {{
      font-size: 0.9rem;
      color: #475569;
      line-height: 1.55;
      margin: 0 0 16px;
      flex-grow: 1;
    }}
    .service-meta {{
      font-size: 0.82rem;
      background: #f8fafc;
      border-radius: 6px;
      padding: 10px 12px;
      margin-bottom: 18px;
      border: 1px solid #edf2f7;
    }}
    .service-meta div {{
      margin-bottom: 4px;
    }}
    .service-meta div:last-child {{
      margin-bottom: 0;
    }}
    .btn-service {{
      display: block;
      text-align: center;
      text-decoration: none;
      padding: 10px 16px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.9rem;
      transition: all 0.2s;
    }}
    .btn-service-primary {{
      background: #064e3b;
      color: white;
    }}
    .btn-service-primary:hover {{
      background: #065f46;
      color: #fbbf24;
    }}
    .btn-service-outline {{
      background: #ffffff;
      color: #065f46;
      border: 1.5px solid #065f46;
    }}
    .btn-service-outline:hover {{
      background: #ecfdf5;
    }}
    .faq-card {{
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 16px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }}
    .faq-question {{
      font-size: 1.05rem;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .faq-answer {{
      font-size: 0.92rem;
      color: #334155;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  {COMMON_NAV}

  <section class="hero-banner">
    <h1 class="hero-title">Services &amp; Modules Hub</h1>
    <p class="hero-subtitle">
      Automated robot pipelines, daily &amp; multi-day attendance analytics, weekly balance tracking, and real-time governance monitoring.
    </p>
  </section>

  <div class="page-container">
    <div style="background:#ffffff; border-radius:14px; border:1px solid var(--border); padding:32px 36px; box-shadow:0 4px 20px rgba(0,0,0,0.06); margin-bottom:32px;">
      <h2 style="font-size:1.5rem; color:#064e3b; margin:0 0 10px; font-weight:800;">
        Executive Service Architecture
      </h2>
      <p style="color:#475569; font-size:0.96rem; margin:0 0 20px; line-height:1.6;">
        e-Panchayat Automation eliminates manual portal clicking by running background headless browser robots equipped with AI OCR captcha solvers and OTP authentication. Choose an active pipeline below or review upcoming analytical modules.
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
          <div class="service-meta">
            <div><strong>Frequency:</strong> Daily Morning (8:00 AM – 11:00 AM)</div>
            <div><strong>Outputs:</strong> 1-Page Landscape PDF, Exception Tables</div>
          </div>
          <a href="/?station=dsr" class="btn-service btn-service-primary">Launch Attendance Robot →</a>
        </div>

        <!-- Service 2: Multi-Day Attendance & DSR Report (Upcoming Roadmap) -->
        <div class="service-card" style="border-color:#f59e0b; background:#fffdf8;">
          <div class="service-card-header">
            <div class="service-icon" style="background:#fef3c7; color:#b45309;">📅</div>
            <span class="status-badge status-upcoming">Roadmap &bull; In Dev</span>
          </div>
          <h3>Multi-Day Attendance &amp; DSR Analysis</h3>
          <p>
            Track attendance consistency across multiple days, weekly intervals, or custom date ranges. Identifies habitual absentees, chronic late submitters, and mandal-wise attendance trend graphs across Khammam District.
          </p>
          <div class="service-meta">
            <div><strong>Capability:</strong> Multi-Date Range Scraping &amp; Aggregation</div>
            <div><strong>Feature:</strong> Trend Heatmaps &amp; Chronic Pendency Lists</div>
          </div>
          <a href="javascript:alert('Multi-Day Attendance & DSR Module is currently in active development and will be released in the upcoming update!');" class="btn-service btn-service-outline" style="border-color:#f59e0b; color:#b45309;">View Multi-Day Details</a>
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
          <div class="service-meta">
            <div><strong>Frequency:</strong> Weekly Every Thursday</div>
            <div><strong>Outputs:</strong> Legal 2-Page PDF &amp; Filterable Excel</div>
          </div>
          <a href="/?station=balance" class="btn-service btn-service-primary">Launch Balance Robot →</a>
        </div>

        <!-- Service 4: Gram Panchayat Inspections -->
        <div class="service-card">
          <div class="service-card-header">
            <div class="service-icon" style="background:#e0f2fe; color:#0284c7;">🔍</div>
            <span class="status-badge status-active">Official Report</span>
          </div>
          <h3>Gram Panchayat Inspections</h3>
          <p>
            Comprehensive compliance monitoring of field inspections conducted by District Panchayat Officers (DPO), Divisional Panchayat Officers (DLPO), and Mandal Panchayat Officers (MPO) with GP drill-down observations.
          </p>
          <div class="service-meta">
            <div><strong>Tracking:</strong> DPO, DLPO, MPO Field Visits</div>
            <div><strong>Outputs:</strong> Interactive Table &amp; CSV Export</div>
          </div>
          <a href="/?station=inspections" class="btn-service btn-service-primary">Open Inspections Station →</a>
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
          <div class="service-meta">
            <div><strong>Access:</strong> Public / No Login Required</div>
            <div><strong>Outputs:</strong> PowerBI Visual Report, PDF, Excel</div>
          </div>
          <a href="/#tax-station" class="btn-service btn-service-primary">Open House Tax DCB →</a>
        </div>

        <!-- Service 6: Monthly Activity Statement (MAS) -->
        <div class="service-card" style="border-color:#f59e0b; background:#fffdf8;">
          <div class="service-card-header">
            <div class="service-icon" style="background:#fef3c7; color:#b45309;">📑</div>
            <span class="status-badge status-upcoming">Under Process</span>
          </div>
          <h3>Monthly Activity Statement (MAS)</h3>
          <p>
            Official 18-Indicator Executive Matrix (GM-R 5.24 &amp; GM-R 5.23 Births Register). Compiles the 2-page legal district abstract and 58-column formatted Excel workbook.
          </p>
          <div class="service-meta">
            <div><strong>Frequency:</strong> Monthly Governance Review</div>
            <div><strong>Status:</strong> Verification &amp; Portal Sync in Progress</div>
          </div>
          <a href="/reports/mas" class="btn-service btn-service-outline">View MAS Station →</a>
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
        <div class="faq-question">❓ Are there any subscription or usage charges?</div>
        <div class="faq-answer">
          No. This platform is 100% free of cost for all Panchayat Raj, Mandal, and District officers in Telangana. It is built as a departmental public service utility to streamline governance analytics.
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

  {COMMON_FOOTER}
</body>
</html>
"""
