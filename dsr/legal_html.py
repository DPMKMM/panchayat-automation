"""HTML template for the Privacy Policy & Terms of Service page (/privacy-legal).
Fulfills official departmental transparency and compliance standards.
"""

from __future__ import annotations


def get_privacy_legal_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy &amp; Terms of Service | e-Panchayat Automation</title>
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
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #475569;
      --border: #e2e8f0;
      --success: #059669;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.65;
      padding-bottom: 60px;
    }
    .header {
      background: linear-gradient(135deg, var(--primary-dark) 0%, var(--primary) 100%);
      color: white;
      padding: 30px 20px;
      border-bottom: 4px solid var(--accent-gold);
    }
    .header-inner {
      max-width: 960px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }
    .brand-title {
      font-size: 1.4rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .nav-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.15);
      color: white;
      text-decoration: none;
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 0.88rem;
      font-weight: 700;
      border: 1px solid rgba(255,255,255,0.25);
      transition: all 0.2s;
    }
    .nav-btn:hover {
      background: rgba(255,255,255,0.25);
    }
    .container {
      max-width: 960px;
      margin: 32px auto;
      padding: 0 20px;
    }
    .policy-card {
      background: var(--card-bg);
      border-radius: 14px;
      border: 1px solid var(--border);
      padding: 36px 40px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.04);
      margin-bottom: 28px;
    }
    h1 {
      font-size: 1.9rem;
      font-weight: 800;
      color: var(--primary-dark);
      margin-bottom: 8px;
    }
    h2 {
      font-size: 1.35rem;
      font-weight: 800;
      color: var(--primary);
      margin: 28px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1.5px solid var(--border);
    }
    h3 {
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--text);
      margin: 20px 0 8px;
    }
    p, li {
      color: var(--text-muted);
      font-size: 0.95rem;
      margin-bottom: 12px;
    }
    ul, ol {
      padding-left: 24px;
      margin-bottom: 16px;
    }
    li { margin-bottom: 6px; }
    .callout {
      background: #ecfdf5;
      border-left: 4px solid var(--success);
      padding: 14px 18px;
      border-radius: 0 8px 8px 0;
      margin: 18px 0;
      font-size: 0.92rem;
      color: #064e3b;
    }
    .callout-warning {
      background: #fffbeb;
      border-left: 4px solid var(--accent-gold);
      color: #92400e;
    }
    footer, .footer {
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
      margin-top: 40px;
      padding-top: 18px;
      border-top: 1px solid var(--border);
    }
    @media (max-width: 640px) {
      .header { padding: 20px 14px; }
      .brand-title { font-size: 1.15rem; gap: 8px; }
      .container { margin: 20px auto; padding: 0 12px; }
      .policy-card { padding: 20px 16px; }
      h1 { font-size: 1.45rem; }
    }
  </style>
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <div class="brand-title" style="flex-wrap:wrap;">
        <span>🏛️</span>
        <span>e-Panchayat Automation</span>
        <span id="subpage-console-pill" style="display:none; align-items:center; background:rgba(255,255,255,0.16); border:1px solid rgba(251,191,36,0.65); color:#fde68a; font-size:0.72rem; font-weight:800; padding:3px 9px; border-radius:999px; letter-spacing:0.35px; text-transform:uppercase;">e-Panchayat Automation Console</span>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <a href="/" class="nav-btn">← Back to Portal</a>
        <a href="/services" class="nav-btn">📑 Services Hub</a>
      </div>
    </div>
  </header>

  <main class="container">
    <div class="policy-card">
      <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px; margin-bottom:18px;">
        <div>
          <div style="font-size:0.78rem; font-weight:800; color:#047857; text-transform:uppercase; letter-spacing:0.4px; margin-bottom:4px;">Welcome to e-Panchayat Automation</div>
          <h1>Departmental Privacy Policy &amp; Terms of Service</h1>
          <p style="color:#065f46; font-size:0.9rem; font-weight:700; margin-bottom:4px;">
            Simplifying Panchayat Administration through Smart Reporting and Automation.
          </p>
          <p style="color:#64748b; font-size:0.86rem; font-weight:600;">
            Platform: e-Panchayat Automation • Government of Telangana • Panchayat Raj &amp; Rural Development Department
          </p>
        </div>
        <button onclick="window.print()" class="nav-btn" style="background:#0f172a; border-color:#334155; color:white; cursor:pointer;">
          🖨️ Print Policy
        </button>
      </div>

      <div class="callout">
        <strong>Executive Summary:</strong> e-Panchayat Automation is an administrative companion system designed to streamline report generation, punctuality tracking, and financial analytics for officers of the Panchayat Raj &amp; Rural Development Department, Telangana. We do <strong>not</strong> sell, rent, monetize, or permanently retain portal login passwords or citizen personal data. All automated scraping and report compiling occur in temporary, isolated browser instances with automated memory and scratch file purging.
      </div>

      <h2>Part 1: Privacy Policy</h2>
      
      <h3>1. Information We Process</h3>
      <p>To provide background automated scraping and instant report generation, our platform processes only the minimum data required:</p>
      <ul>
        <li><strong>e-Panchayat Portal Authentication:</strong> Departmental User ID, Password, and the 6-digit One-Time Password (OTP) are relayed securely over encrypted TLS connections directly to the official e-Panchayat portal (<code>epanchayat.telangana.gov.in</code>). Credentials are held in RAM memory only for the duration of the active browser session and are <strong>never stored permanently on disk</strong>.</li>
        <li><strong>Downloaded Reporting Files:</strong> Raw reports including GM-R 1.2.7 DSR data, GM-R 1.2.11 Presentees, GM-R 1.2.10 Absentees, Thursday Bank Balances (GM-R 14.2), and House Tax Demand Collection Balance files are stored in ephemeral session directories and purged upon session logout or timer completion.</li>
        <li><strong>Officer Identity:</strong> Authenticated Google Account UID (Firebase Authentication) and official Gmail address associated with officer designation, role level, and contact mobile in Cloud Firestore.</li>
      </ul>

      <h3>2. Data Security &amp; Storage Isolation</h3>
      <ul>
        <li><strong>Sandboxed Process Isolation:</strong> Each officer session operates in an independent, sandboxed browser context. Officers cannot access or view other officers' active downloads.</li>
        <li><strong>Zero Permanent Password Storage:</strong> e-Panchayat passwords are kept solely in memory-resident browser contexts and purged immediately upon disconnection.</li>
        <li><strong>Cryptographic Protection:</strong> All data transmissions utilize TLS 1.3 encryption. Strict Anti-Clickjacking (<code>X-Frame-Options: SAMEORIGIN</code>) and Anti-Sniffing (<code>X-Content-Type-Options: nosniff</code>) headers are enforced.</li>
        <li><strong>Zero Advertising:</strong> No commercial advertising, tracking pixels, or third-party analytics trackers are used.</li>
      </ul>

      <div class="callout callout-warning">
        <strong>Independent Companion Disclaimer:</strong> e-Panchayat Automation is an independent automation companion developed to assist departmental officers in compiling statutory reviews. It operates solely as an authorized user-agent client connecting to the official portal on behalf of authenticated officers.
      </div>

      <h2>Part 2: Terms of Service</h2>

      <h3>1. Permitted Use &amp; Officer Eligibility</h3>
      <p>This platform is provided exclusively for authorized personnel of the Panchayat Raj &amp; Rural Development Department, Telangana, including:</p>
      <ul>
        <li>District Panchayat Officers (DPO) and Divisional Panchayat Officers (DLPO).</li>
        <li>Mandal Parishad Development Officers (MPDO) and Mandal Panchayat Officers (MPO).</li>
        <li>Panchayat Secretaries (PS) and Data Entry Operators (DEO).</li>
      </ul>
      <p>Officers agree to use this platform strictly for authorized administrative reviews, attendance verification, Thursday bank balance reconciliation, House Tax collection tracking, and official district report preparation.</p>

      <h3>2. User Responsibilities &amp; Account Security</h3>
      <ul>
        <li>Authenticate only with your own valid, authorized e-Panchayat portal credentials.</li>
        <li>Keep login OTPs confidential and never share active browser sessions with unauthorized individuals.</li>
        <li>Do not use the service to flood the State Data Center (SDC) with unauthorized high-frequency script loops.</li>
      </ul>

      <h3>3. Data Accuracy &amp; Verification</h3>
      <p>Automated reports generated by this tool directly reflect data recorded on the official Telangana e-Panchayat portal (<code>epanchayat.telangana.gov.in</code>). While our background algorithms perform rigorous absentees matching, cross-referencing, and LGD validation, officers are advised to verify critical statutory submissions against portal records before presenting them in formal government proceedings.</p>

      <h3>4. Session Termination</h3>
      <p>Clicking <strong>🔒 Disconnect ePanchayat</strong> or <strong>🚪 Logout</strong> immediately terminates the underlying background browser instance, revokes active portal cookies, and deletes cached report files from the server's working directory.</p>
    </div>

    <footer class="footer">
      <div style="max-width:960px; margin:0 auto; padding:6px 10px; text-align:center; line-height:1.55;">
        <strong style="display:block; font-size:0.95rem; font-weight:800; color:#0f172a;">e-Panchayat Automation</strong>
        <div style="font-size:0.84rem; color:#475569; margin-top:2px;">Simplifying Panchayat Administration through Smart Reporting and Automation.</div>
      </div>
    </footer>
  </main>
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
