"""HTML Web Dashboard for Monthly Activity Statement (MAS) Module."""

MAS_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Monthly Activity Statement (MAS) | Khammam District</title>
  <style>
    :root {
      --primary: #0c3829;
      --primary-light: #165b43;
      --accent: #d97706;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #475569;
      --border: #e2e8f0;
      --success: #16a34a;
      --danger: #dc2626;
      --blue: #0284c7;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    /* Navbar */
    .navbar {
      background: var(--primary);
      color: white;
      padding: 0 24px;
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 10px rgba(0,0,0,0.15);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 700;
      font-size: 1.1rem;
      color: white;
      text-decoration: none;
    }
    .badge {
      background: #f59e0b;
      color: #1a1a1a;
      font-size: 0.72rem;
      font-weight: 800;
      padding: 3px 8px;
      border-radius: 4px;
      text-transform: uppercase;
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s;
      border: 1px solid transparent;
    }
    .btn-primary { background: #10b981; color: white; }
    .btn-primary:hover { background: #059669; }
    .btn-outline { background: transparent; border-color: rgba(255,255,255,0.4); color: white; }
    .btn-outline:hover { background: rgba(255,255,255,0.1); border-color: white; }
    .btn-excel { background: #15803d; color: white; }
    .btn-excel:hover { background: #166534; }
    .btn-pdf { background: #b91c1c; color: white; }
    .btn-pdf:hover { background: #991b1b; }

    /* Container */
    .container {
      max-width: 1400px;
      margin: 24px auto;
      padding: 0 20px;
    }

    /* Header Banner */
    .banner {
      background: linear-gradient(135deg, #062b1f 0%, #0c3829 60%, #165b43 100%);
      color: white;
      border-radius: 14px;
      padding: 24px 28px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 4px 15px rgba(12, 56, 41, 0.2);
    }
    .banner h1 { font-size: 1.45rem; font-weight: 800; margin-bottom: 6px; }
    .banner p { color: #d1fae5; font-size: 0.92rem; }
    .banner-actions { display: flex; gap: 10px; }

    /* Stat Cards */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card {
      background: white;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 20px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .stat-label { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 6px; }
    .stat-value { font-size: 1.7rem; font-weight: 800; color: var(--text); }
    .stat-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
    .stat-card.green .stat-value { color: var(--success); }
    .stat-card.red .stat-value { color: var(--danger); }
    .stat-card.blue .stat-value { color: var(--blue); }

    /* Tabs & Content */
    .card {
      background: white;
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.04);
      overflow: hidden;
      margin-bottom: 24px;
    }
    .card-header {
      padding: 16px 20px;
      background: #f1f5f9;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .card-title { font-size: 1.05rem; font-weight: 700; color: var(--text); }
    .pdf-frame {
      width: 100%;
      height: 820px;
      border: none;
      display: block;
    }
  </style>
</head>
<body>

  <!-- Navbar -->
  <header class="navbar">
    <a href="/" class="brand">
      <span>🏛️ ePanchayat Telangana</span>
      <span class="badge">Official MAS Portal</span>
    </a>
    <div class="nav-actions">
      <a href="/" class="btn btn-outline">← Back to Portal</a>
      <a href="/api/mas/report.pdf" target="_blank" class="btn btn-pdf">📄 Open PDF in New Tab</a>
      <a href="/api/mas/export.xlsx" class="btn btn-excel">📊 Download Excel (58 Cols)</a>
    </div>
  </header>

  <main class="container">
    <!-- Header Banner -->
    <div class="banner">
      <div>
        <h1>Monthly Activity Statement (MAS) & Births Register</h1>
        <p>GM-R 5.24 & GM-R 5.23 Compliance Statement — <strong>Khammam District</strong> (Period: <strong>October 2026</strong>)</p>
      </div>
      <div class="banner-actions">
        <a href="/api/mas/report.pdf" download="Khammam_MAS_Report_October_2026.pdf" class="btn btn-pdf">⬇️ Download PDF</a>
        <a href="/api/mas/export.xlsx" class="btn btn-excel">⬇️ Download Excel</a>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Mandals</div>
        <div class="stat-value">20</div>
        <div class="stat-sub">100% Drilled Down Live</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Gram Panchayats</div>
        <div class="stat-value">559</div>
        <div class="stat-sub">Ground-Truth Records</div>
      </div>
      <div class="stat-card blue">
        <div class="stat-label">18 Indicators % Entered</div>
        <div class="stat-value">44.5%</div>
        <div class="stat-sub">District Compliance Index</div>
      </div>
      <div class="stat-card green">
        <div class="stat-label">Births Registered GPs</div>
        <div class="stat-value">544</div>
        <div class="stat-sub">97.3% Achievement</div>
      </div>
      <div class="stat-card red">
        <div class="stat-label">Pending Action GPs</div>
        <div class="stat-value">548</div>
        <div class="stat-sub">Single-line Action List</div>
      </div>
    </div>

    <!-- PDF Viewer Card -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">📄 Official Landscape Legal Report (2-Page Executive Matrix + Single-Line Pending List)</div>
        <div style="display:flex; gap:8px;">
          <a href="/api/mas/report.pdf" target="_blank" class="btn btn-outline" style="color:var(--text); border-color:#cbd5e1;">Open Full Screen ↗</a>
        </div>
      </div>
      <iframe src="/api/mas/report.pdf#toolbar=1&navpanes=1" class="pdf-frame"></iframe>
    </div>
  </main>

</body>
</html>
"""
