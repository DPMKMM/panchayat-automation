/**
 * e-Panchayat Automation — Administrator Control Center Controller
 * Manages Registered & Active User KPIs, Live Tool Telemetry, Officer Access Permissions,
 * Subscription Plans & Razorpay Database Ledger, Access Policy Flags, and Feedback Inbox.
 */
(function () {
  'use strict';

  var esc = window.escapeHtml || function (str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  var DESIGNATIONS = ['DPO', 'DPM', 'DLPO', 'MPDO', 'MPO', 'PS', 'DEO'];
  var ROLES = ['Mandal Level', 'Division Level', 'District Level'];
  var STATUSES = ['Active', 'Disabled'];
  var SUB_STATUSES = [
    { value: 'free_preview', label: 'Free Access' },
    { value: 'active', label: 'Subscribed (Active)' },
    { value: 'trial', label: 'Trial' },
    { value: 'cancelled', label: 'Cancelled' },
    { value: 'expired', label: 'Expired' },
  ];

  var POLICY_GROUPS = [
    {
      title: 'Platform Availability & Subscription Enforcement',
      keys: ['free_launch_mode', 'portal_enabled', 'console_enabled', 'automated_subscription_required'],
    },
    {
      title: 'Platform 1 · Manual Reports Modules',
      keys: ['module_dsr_excel', 'module_dsr_multiday', 'module_mobile_updation'],
    },
    {
      title: 'Live Analytics & Console Robot Modules',
      keys: ['module_dcb_live', 'module_dsr_automation', 'module_gp_balance_automation', 'module_mas_automation'],
    },
  ];

  var activeAdminTab = 'overview';

  function showAdminAlert(msg, type) {
    var box = document.getElementById('admin-alert');
    if (!box) return;
    if (!msg) {
      box.className = 'gov-portal-alert';
      box.style.display = 'none';
      box.textContent = '';
      return;
    }
    box.className = 'gov-portal-alert ' + (type || 'info');
    box.style.display = 'block';
    box.textContent = msg;
  }

  function formatShortDate(isoStr) {
    if (!isoStr) return '—';
    try {
      var d = new Date(isoStr);
      if (isNaN(d.getTime())) return String(isoStr).slice(0, 16);
      return d.toLocaleString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return String(isoStr).slice(0, 16);
    }
  }

  function formatInr(val) {
    var num = Number(val || 0);
    if (isNaN(num)) num = 0;
    return '₹' + num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }

  function currentUserIsAdmin() {
    var isAdmRoute = typeof window.isAdminRouteOrHost === 'function'
      ? window.isAdminRouteOrHost()
      : (typeof window.isAdminHost === 'function' && window.isAdminHost());
    if (!isAdmRoute) return false;
    var host = (window.location.hostname || '').toLowerCase();
    var isLocal = host === 'localhost' || host === '127.0.0.1';
    if (!isLocal && typeof window.isAdminHost === 'function' && !window.isAdminHost()) {
      return false;
    }
    var u = typeof window.getScopedUser === 'function' ? window.getScopedUser() : null;
    return Boolean(u && u.is_admin);
  }

  window.openAdminDashboardStation = function () {
    if (!currentUserIsAdmin()) {
      if (typeof window.isProdCustomDomain === 'function' && window.isProdCustomDomain() && (!window.isAdminHost || !window.isAdminHost())) {
        window.location.href = 'https://admin.panchayatautomation.in/';
        return;
      }
      if (typeof window.showPortalNotice === 'function') {
        window.showPortalNotice('Administrator access is hosted separately at https://admin.panchayatautomation.in.', 'error');
      }
      return;
    }
    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var hubLink = document.getElementById('admin-open-user-portal-link');
    if (hubLink) {
      hubLink.href = (typeof window.isProdCustomDomain === 'function' && window.isProdCustomDomain())
        ? 'https://panchayatautomation.in/'
        : '/';
    }
    var station = document.getElementById('admin-dashboard-station');
    if (station) {
      station.style.display = 'block';
    }
    showAdminAlert('');
    window.switchAdminTab('overview');
  };

  window.refreshActiveAdminTab = function () {
    window.switchAdminTab(activeAdminTab);
  };

  window.switchAdminTab = function (tab) {
    var tabs = ['overview', 'tools', 'users', 'dsc', 'subscriptions', 'policy', 'visibility', 'feedback'];
    activeAdminTab = tabs.indexOf(tab) !== -1 ? tab : 'overview';

    tabs.forEach(function (t) {
      var btn = document.getElementById('admin-tab-' + t);
      var pane = document.getElementById('admin-pane-' + t);
      if (btn) btn.classList.toggle('active', t === activeAdminTab);
      if (pane) pane.style.display = t === activeAdminTab ? 'block' : 'none';
    });

    if (activeAdminTab === 'overview') window.loadAdminOverview();
    else if (activeAdminTab === 'tools') window.loadAdminToolUsage();
    else if (activeAdminTab === 'users') window.loadAdminUsers();
    else if (activeAdminTab === 'dsc') window.loadAdminDscTelemetry();
    else if (activeAdminTab === 'subscriptions') window.loadAdminSubscriptions();
    else if (activeAdminTab === 'policy') window.loadAdminPolicy();
    else if (activeAdminTab === 'visibility') window.loadAdminModuleVisibility();
    else if (activeAdminTab === 'feedback') window.loadAdminFeedback();
  };

  window.loadAdminOverview = async function () {
    try {
      var data = await window.safeFetchJson('/api/admin/overview');
      var s = data.stats || {};
      var rzp = data.razorpay || {};
      var fb = data.firebase || {};
      var toolUsage = Array.isArray(s.tool_usage) ? s.tool_usage : [];
      var catUsage = Array.isArray(s.category_usage) ? s.category_usage : [];
      var recentAct = Array.isArray(s.recent_activity) ? s.recent_activity : [];
      var eventTotal = s.total_tool_runs != null
        ? s.total_tool_runs
        : (Array.isArray(s.module_usage) ? s.module_usage.reduce(function (a, b) { return a + Number(b.count || 0); }, 0) : 0);

      var el;
      el = document.getElementById('adm-kpi-users'); if (el) el.textContent = s.total_users != null ? s.total_users : '0';
      el = document.getElementById('adm-tab-users-badge'); if (el) el.textContent = s.total_users != null ? s.total_users : '0';
      el = document.getElementById('adm-kpi-completed'); if (el) el.textContent = s.completed_profiles != null ? s.completed_profiles : '0';
      el = document.getElementById('adm-kpi-active'); if (el) el.textContent = s.active_users != null ? s.active_users : '0';
      el = document.getElementById('adm-kpi-online-sub');
      if (el) {
        el.textContent = 'Online Now: ' + (s.active_users_now || 0) + ' · 24h: ' + (s.active_users_24h || 0) + ' · 7d: ' + (s.active_users_7d || 0);
      }
      el = document.getElementById('adm-kpi-events'); if (el) el.textContent = eventTotal;
      el = document.getElementById('adm-kpi-tools-sub');
      if (el) el.textContent = 'Distinct Tools Used: ' + (s.unique_tools_used != null ? s.unique_tools_used : toolUsage.length);

      el = document.getElementById('adm-kpi-subscribed'); if (el) el.textContent = s.subscribed_users != null ? s.subscribed_users : '0';
      el = document.getElementById('adm-kpi-sub-split');
      if (el) el.textContent = 'Active Paid · Free Tier: ' + (s.free_users != null ? s.free_users : 0);

      el = document.getElementById('adm-kpi-revenue'); if (el) el.textContent = formatInr(s.total_revenue_inr || 0);
      el = document.getElementById('adm-kpi-razorpay-sub');
      if (el) {
        el.textContent = rzp.configured
          ? ('Razorpay Connected (' + (rzp.mode || 'test') + ')')
          : 'Razorpay Ready · Awaiting API Keys';
      }

      el = document.getElementById('adm-kpi-feedback-num'); if (el) el.textContent = s.total_feedback != null ? s.total_feedback : '0';
      el = document.getElementById('adm-kpi-feedback'); if (el) el.textContent = 'Disabled Accounts: ' + (s.disabled_users != null ? s.disabled_users : 0);

      var dsc = data.dsc_telemetry || {};
      el = document.getElementById('adm-kpi-dsc-machines');
      if (el) el.textContent = String(dsc.total_machines != null ? dsc.total_machines : 0);
      el = document.getElementById('adm-tab-dsc-badge');
      if (el) el.textContent = String(dsc.total_machines != null ? dsc.total_machines : 0);
      el = document.getElementById('adm-kpi-dsc-sub');
      if (el) {
        var gh = dsc.github_downloads || {};
        el.textContent = 'Active: ' + (dsc.active_24h || 0) + ' (24h) · Total DLs: ' + (gh.total || 0);
      }

      var grid = document.getElementById('admin-breakdown-grid');
      if (!grid) return;

      var topMax = toolUsage.length > 0 ? Math.max(1, Number(toolUsage[0].count || 1)) : 1;
      var topToolsHtml = toolUsage.slice(0, 8).map(function (t) {
        var pct = Math.min(100, Math.round((Number(t.count || 0) / topMax) * 100));
        return (
          '<div style="margin-bottom:10px;">' +
            '<div style="display:flex; justify-content:space-between; font-size:0.83rem;">' +
              '<span><strong>' + esc(t.tool_name || t.tool_id) + '</strong> <span style="color:#64748b; font-size:0.75rem;">(' + esc(t.category || '') + ')</span></span>' +
              '<strong>' + esc(t.count || 0) + '</strong>' +
            '</div>' +
            '<div class="admin-bar-track"><div class="admin-bar-fill" style="width:' + pct + '%;"></div></div>' +
          '</div>'
        );
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No tool activity logged yet. Open any Excel, PDF, Manual or Automated tool to populate telemetry.</div>';

      var catMax = catUsage.length > 0 ? Math.max(1, Number(catUsage[0].count || 1)) : 1;
      var catRowsHtml = catUsage.map(function (c) {
        var pct = Math.min(100, Math.round((Number(c.count || 0) / catMax) * 100));
        return (
          '<div style="margin-bottom:10px;">' +
            '<div style="display:flex; justify-content:space-between; font-size:0.83rem;">' +
              '<span>' + esc(c.category || 'Other') + '</span>' +
              '<strong>' + esc(c.count || 0) + '</strong>' +
            '</div>' +
            '<div class="admin-bar-track"><div class="admin-bar-fill" style="width:' + pct + '%; background:linear-gradient(90deg, #4f46e5, #3b82f6);"></div></div>' +
          '</div>'
        );
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No category breakdown available yet.</div>';

      var recentHtml = recentAct.slice(0, 8).map(function (ev) {
        return (
          '<div style="display:flex; justify-content:space-between; gap:8px; padding:6px 0; border-bottom:1px solid #f1f5f9; font-size:0.8rem;">' +
            '<div>' +
              '<strong>' + esc(ev.user_name || 'Guest') + '</strong> &rarr; ' +
              '<span style="color:#0369a1; font-weight:700;">' + esc(ev.tool_name || ev.tool_id) + '</span>' +
            '</div>' +
            '<span style="color:#64748b; white-space:nowrap;">' + esc(formatShortDate(ev.created_at)) + '</span>' +
          '</div>'
        );
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No recent tool activity logged yet.</div>';

      var desigRows = (s.by_designation || []).map(function (item) {
        return '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;">' +
          '<span>' + esc(item.designation || 'Pending') + '</span>' +
          '<strong>' + esc(item.count || 0) + '</strong></div>';
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No designation data yet.</div>';

      var fsLabel = fb.firestore_mode === 'live_firestore'
        ? 'Connected (Cloud Firestore)'
        : (fb.firestore_mode === 'emulator' ? 'Firebase Emulator' : 'Local Persisted Store');
      var subGateOn = Boolean(data.access_policy && data.access_policy.flags && data.access_policy.flags.automated_subscription_required);

      grid.innerHTML =
        '<div class="admin-section-card" style="margin-bottom:0;">' +
          '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">' +
            '<h4 style="margin:0; color:#064e3b;">🧰 Most Used Tools (30d)</h4>' +
            '<a href="javascript:void(0)" onclick="switchAdminTab(\'tools\')" style="font-size:0.76rem; font-weight:700; color:#0369a1; text-decoration:none;">View All &rarr;</a>' +
          '</div>' +
          topToolsHtml +
        '</div>' +
        '<div class="admin-section-card" style="margin-bottom:0;">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">📊 Usage by Workspace Category</h4>' +
          catRowsHtml +
        '</div>' +
        '<div class="admin-section-card" style="margin-bottom:0;">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">⚡ Live Officer Tool Activity</h4>' +
          recentHtml +
        '</div>' +
        '<div class="admin-section-card" style="margin-bottom:0;">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">👥 Registered by Designation</h4>' +
          desigRows +
        '</div>' +
        '<div class="admin-section-card" style="margin-bottom:0;">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">💳 Razorpay &amp; Database Posture</h4>' +
          '<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #f1f5f9;"><span>Database Engine</span><strong>' + esc(fsLabel) + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #f1f5f9;"><span>Razorpay Gateway</span><strong>' + (rzp.configured ? ('Ready (' + esc(rzp.mode) + ')') : 'Awaiting API Keys') + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #f1f5f9;"><span>Paid Subscription Gate</span><strong>' + (subGateOn ? 'Enforced' : 'Open Free Rollout') + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #f1f5f9;"><span>Captured Payments</span><strong>' + esc(s.captured_payments_count || 0) + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:5px 0;"><span>Active Live Sessions</span><strong>' + esc(s.active_users_now || 0) + ' officers</strong></div>' +
        '</div>';
    } catch (err) {
      showAdminAlert('Failed to load administrator overview: ' + err.message, 'error');
    }
  };

  window._adminAllRecentActivity = [];

  window.toggleToolOfficersDetail = function (toolId) {
    var subrow = document.getElementById('tool-users-row-' + toolId);
    if (!subrow) return;
    if (subrow.style.display === 'none' || !subrow.style.display) {
      subrow.style.display = 'table-row';
    } else {
      subrow.style.display = 'none';
    }
  };

  window.filterAdminActivityTable = function () {
    var q = ((document.getElementById('admin-act-search') && document.getElementById('admin-act-search').value) || '').trim().toLowerCase();
    var cat = ((document.getElementById('admin-act-cat') && document.getElementById('admin-act-cat').value) || '').trim().toLowerCase();
    var all = window._adminAllRecentActivity || [];

    var filtered = all.filter(function (ev) {
      if (cat && String(ev.category || '').toLowerCase() !== cat) return false;
      if (!q) return true;
      var haystack = [
        ev.user_name || '',
        ev.gmail || '',
        ev.tool_name || '',
        ev.tool_id || '',
        ev.action || '',
        ev.details || '',
        ev.category || '',
        ev.created_at_ist || '',
      ].join(' ').toLowerCase();
      return haystack.indexOf(q) !== -1;
    });

    var countEl = document.getElementById('admin-recent-count');
    if (countEl) countEl.textContent = String(filtered.length);

    var recBody = document.getElementById('admin-recent-tbody');
    if (!recBody) return;

    if (filtered.length === 0) {
      recBody.innerHTML = '<tr><td colspan="5" class="text-center" style="padding:24px; color:#64748b;">No activity events match your filter criteria.</td></tr>';
      return;
    }

    recBody.innerHTML = filtered.map(function (ev) {
      var timeDisplay = esc(ev.created_at_ist || formatShortDate(ev.created_at));
      var timeAgoPill = ev.time_ago ? (' <span style="display:inline-block; font-size:0.72rem; color:#059669; font-weight:700; background:#ecfdf5; padding:1px 6px; border-radius:4px; margin-left:4px;">' + esc(ev.time_ago) + '</span>') : '';
      var detailsText = esc(ev.details || ev.action || '—');
      return (
        '<tr>' +
          '<td style="white-space:nowrap; font-size:0.78rem; color:#334155; font-family:monospace;">' + timeDisplay + timeAgoPill + '</td>' +
          '<td>' +
            '<div style="font-weight:700; color:#0f172a;">' + esc(ev.user_name || 'Guest Officer') + '</div>' +
            '<div style="font-size:0.74rem; color:#64748b;">' + esc(ev.gmail || '—') + (ev.designation ? (' · ' + esc(ev.designation)) : '') + '</div>' +
          '</td>' +
          '<td>' +
            '<div style="font-weight:700; color:#064e3b;">' + esc(ev.tool_name || ev.tool_id) + '</div>' +
            '<div style="font-size:0.72rem; color:#64748b;"><code>' + esc(ev.tool_id || ev.action) + '</code></div>' +
          '</td>' +
          '<td><span class="badge-role-pill">' + esc(ev.category || 'Tools') + '</span></td>' +
          '<td style="font-size:0.8rem; color:#334155; max-width:320px; word-break:break-word;">' + detailsText + '</td>' +
        '</tr>'
      );
    }).join('');
  };

  window.openOfficerActivityModal = async function (userId, fallbackName) {
    var modal = document.getElementById('admin-officer-modal');
    if (!modal) return;

    var nameEl = document.getElementById('adm-officer-modal-name');
    var badgeEl = document.getElementById('adm-officer-modal-badge');
    var subEl = document.getElementById('adm-officer-modal-sub');
    var kpiRuns = document.getElementById('adm-officer-kpi-runs');
    var kpiDistinct = document.getElementById('adm-officer-kpi-distinct');
    var kpiLast = document.getElementById('adm-officer-kpi-last');
    var toolsTbody = document.getElementById('adm-officer-tools-tbody');
    var eventsTbody = document.getElementById('adm-officer-events-tbody');

    if (nameEl) nameEl.textContent = fallbackName || 'Officer Activity';
    if (badgeEl) badgeEl.textContent = 'Loading...';
    if (subEl) subEl.textContent = 'Loading officer details & activity timeline...';
    if (kpiRuns) kpiRuns.textContent = '...';
    if (kpiDistinct) kpiDistinct.textContent = '...';
    if (kpiLast) kpiLast.textContent = '...';
    if (toolsTbody) toolsTbody.innerHTML = '<tr><td colspan="4" class="text-center" style="padding:20px; color:#64748b;">Loading tools breakdown...</td></tr>';
    if (eventsTbody) eventsTbody.innerHTML = '<tr><td colspan="4" class="text-center" style="padding:20px; color:#64748b;">Loading activity logs...</td></tr>';

    modal.style.display = 'flex';

    try {
      var data = await window.safeFetchJson('/api/admin/users/' + encodeURIComponent(userId) + '/activity?days=90');
      var user = data.user || {};
      var summary = data.summary || {};
      var tools = Array.isArray(summary.tools) ? summary.tools : [];
      var events = Array.isArray(data.recent_events) ? data.recent_events : [];

      if (nameEl) nameEl.textContent = user.name || summary.user_name || fallbackName || 'Officer';
      if (badgeEl) badgeEl.textContent = user.designation || 'OFFICER';
      if (subEl) {
        subEl.textContent = (user.gmail || summary.gmail || 'No email') + (user.designation ? (' · ' + user.designation) : '') + (user.mobile_number ? (' · 📱 ' + user.mobile_number) : '');
      }
      if (kpiRuns) kpiRuns.textContent = String(summary.total_runs || events.length || 0);
      if (kpiDistinct) kpiDistinct.textContent = String(summary.distinct_tools || tools.length || 0);
      if (kpiLast) {
        kpiLast.textContent = summary.last_active_at ? formatShortDate(summary.last_active_at) : (events.length > 0 ? (events[0].time_ago || formatShortDate(events[0].created_at)) : 'Never');
      }

      if (toolsTbody) {
        if (tools.length === 0) {
          toolsTbody.innerHTML = '<tr><td colspan="4" class="text-center" style="padding:16px; color:#64748b;">No recorded tool executions for this officer yet.</td></tr>';
        } else {
          toolsTbody.innerHTML = tools.map(function (t) {
            return (
              '<tr>' +
                '<td><strong>' + esc(t.tool_name || t.tool_id) + '</strong><div style="font-size:0.72rem; color:#64748b;"><code>' + esc(t.tool_id) + '</code></div></td>' +
                '<td><span class="badge-role-pill">' + esc(t.category || 'Tools') + '</span></td>' +
                '<td class="text-center"><strong style="color:#059669; font-size:0.95rem;">' + esc(t.count || 0) + '</strong></td>' +
                '<td style="font-size:0.8rem; color:#475569;">' + esc(formatShortDate(t.last_used_at)) + '</td>' +
              '</tr>'
            );
          }).join('');
        }
      }

      if (eventsTbody) {
        if (events.length === 0) {
          eventsTbody.innerHTML = '<tr><td colspan="4" class="text-center" style="padding:16px; color:#64748b;">No recent chronological events found.</td></tr>';
        } else {
          eventsTbody.innerHTML = events.map(function (ev) {
            var tStr = esc(ev.created_at_ist || formatShortDate(ev.created_at));
            var agoPill = ev.time_ago ? (' <span style="font-size:0.72rem; color:#059669; font-weight:700; background:#ecfdf5; padding:1px 5px; border-radius:4px;">' + esc(ev.time_ago) + '</span>') : '';
            return (
              '<tr>' +
                '<td style="white-space:nowrap; font-size:0.78rem; font-family:monospace; color:#334155;">' + tStr + agoPill + '</td>' +
                '<td><strong>' + esc(ev.tool_name || ev.tool_id) + '</strong><div style="font-size:0.72rem; color:#64748b;"><code>' + esc(ev.action || ev.tool_id) + '</code></div></td>' +
                '<td><span class="badge-role-pill">' + esc(ev.category || 'Tools') + '</span></td>' +
                '<td style="font-size:0.8rem; color:#334155;">' + esc(ev.details || ev.action || '—') + '</td>' +
              '</tr>'
            );
          }).join('');
        }
      }
    } catch (err) {
      if (subEl) subEl.textContent = 'Error loading activity: ' + err.message;
    }
  };

  window.closeOfficerActivityModal = function () {
    var modal = document.getElementById('admin-officer-modal');
    if (modal) modal.style.display = 'none';
  };

  window.loadAdminToolUsage = async function () {
    var daysEl = document.getElementById('admin-tools-days');
    var days = daysEl ? daysEl.value : '30';
    try {
      var data = await window.safeFetchJson('/api/admin/tool-usage?days=' + encodeURIComponent(days));
      var tools = Array.isArray(data.tool_usage) ? data.tool_usage : [];
      var userTools = Array.isArray(data.user_tool_usage) ? data.user_tool_usage : [];
      var cats = Array.isArray(data.category_usage) ? data.category_usage : [];
      var recent = Array.isArray(data.recent_activity) ? data.recent_activity : [];

      window._adminAllRecentActivity = recent;

      // Category Summary KPI Cards
      var catGrid = document.getElementById('admin-tools-cat-grid');
      if (catGrid) {
        catGrid.innerHTML = cats.map(function (c) {
          return (
            '<div class="metric-card info" style="margin:0;">' +
              '<div class="metric-label">' + esc(c.category) + '</div>' +
              '<div class="metric-value">' + esc(c.count) + '</div>' +
              '<div class="metric-sub">Tool runs in last ' + esc(days) + 'd</div>' +
            '</div>'
          );
        }).join('') || '';
      }

      // Populate Category filter dropdown if not populated
      var catSelect = document.getElementById('admin-act-cat');
      if (catSelect && catSelect.options.length <= 1) {
        cats.forEach(function (c) {
          var opt = document.createElement('option');
          opt.value = c.category;
          opt.textContent = c.category + ' (' + c.count + ')';
          catSelect.appendChild(opt);
        });
      }

      // 1. Tools Ranking Table
      var countEl = document.getElementById('admin-tools-count');
      if (countEl) countEl.textContent = String(tools.length);
      var tbody = document.getElementById('admin-tools-tbody');
      if (tbody) {
        if (tools.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="padding:24px; color:#64748b;">No tool runs recorded in this window.</td></tr>';
        } else {
          tbody.innerHTML = tools.map(function (t) {
            var usersList = Array.isArray(t.users) ? t.users : [];
            var hasUsers = usersList.length > 0;
            var usersBtn = hasUsers
              ? ('<button type="button" class="btn btn-white btn-xs" onclick="window.toggleToolOfficersDetail(\'' + esc(t.tool_id) + '\')" style="font-size:0.75rem; padding:3px 8px; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;">👥 View Officers (' + t.unique_users + ')</button>')
              : ('<span style="font-size:0.75rem; color:#94a3b8;">None</span>');

            var subTableRows = usersList.map(function (u) {
              return (
                '<tr>' +
                  '<td style="font-weight:700; color:#0f172a;">' + esc(u.user_name || 'Officer') + '<div style="font-size:0.72rem; color:#64748b;">' + esc(u.gmail || '') + '</div></td>' +
                  '<td><span class="badge-role-pill">' + esc(u.designation || 'Officer') + '</span></td>' +
                  '<td class="text-center"><strong style="color:#059669;">' + esc(u.count || 0) + ' runs</strong></td>' +
                  '<td style="font-size:0.78rem; color:#475569;">' + esc(formatShortDate(u.last_used_at)) + '</td>' +
                  '<td class="text-center"><button type="button" class="btn btn-white btn-xs" onclick="window.openOfficerActivityModal(\'' + esc(u.user_id) + '\', \'' + esc(u.user_name || u.gmail) + '\')">📊 Inspect</button></td>' +
                '</tr>'
              );
            }).join('');

            var subrowHtml = hasUsers ? (
              '<tr id="tool-users-row-' + esc(t.tool_id) + '" style="display:none; background:#f8fafc;">' +
                '<td colspan="6" style="padding:12px 16px; border-left:3px solid #059669;">' +
                  '<div style="font-size:0.8rem; font-weight:800; color:#064e3b; margin-bottom:8px;">Officers who ran ' + esc(t.tool_name || t.tool_id) + ':</div>' +
                  '<div class="table-responsive"><table style="background:#ffffff; border-radius:8px; border:1px solid #e2e8f0; font-size:0.82rem;">' +
                    '<thead><tr><th>Officer</th><th>Designation</th><th class="text-center">Times Ran</th><th>Last Ran</th><th class="text-center">Action</th></tr></thead>' +
                    '<tbody>' + subTableRows + '</tbody>' +
                  '</table></div>' +
                '</td>' +
              '</tr>'
            ) : '';

            return (
              '<tr>' +
                '<td><strong>' + esc(t.tool_name || t.tool_id) + '</strong><div style="font-size:0.74rem; color:#64748b;"><code>' + esc(t.tool_id) + '</code></div></td>' +
                '<td><span class="badge-role-pill">' + esc(t.category || 'Tools') + '</span></td>' +
                '<td class="text-center"><strong style="color:#0f172a; font-size:0.96rem;">' + esc(t.count || 0) + '</strong></td>' +
                '<td class="text-center">' + esc(t.unique_users || 0) + '</td>' +
                '<td style="font-size:0.8rem; color:#475569;">' + esc(formatShortDate(t.last_used_at)) + '</td>' +
                '<td class="text-center">' + usersBtn + '</td>' +
              '</tr>' +
              subrowHtml
            );
          }).join('');
        }
      }

      // 2. Officer Leaderboard Table
      var userToolsCountEl = document.getElementById('admin-user-tools-count');
      if (userToolsCountEl) userToolsCountEl.textContent = String(userTools.length);
      var userToolsBody = document.getElementById('admin-user-tools-tbody');
      if (userToolsBody) {
        if (userTools.length === 0) {
          userToolsBody.innerHTML = '<tr><td colspan="7" class="text-center" style="padding:24px; color:#64748b;">No officer tool telemetry recorded in this window.</td></tr>';
        } else {
          userToolsBody.innerHTML = userTools.map(function (u, idx) {
            var rank = idx + 1;
            var medal = rank === 1 ? '🥇 ' : (rank === 2 ? '🥈 ' : (rank === 3 ? '🥉 ' : ''));
            return (
              '<tr>' +
                '<td class="text-center" style="font-weight:800; color:' + (rank <= 3 ? '#b45309' : '#64748b') + ';">' + medal + '#' + rank + '</td>' +
                '<td>' +
                  '<div style="font-weight:700; color:#0f172a;">' + esc(u.user_name || 'Officer') + '</div>' +
                  '<div style="font-size:0.75rem; color:#64748b;">' + esc(u.gmail || '—') + '</div>' +
                '</td>' +
                '<td><span class="badge-role-pill">' + esc(u.designation || 'Officer') + '</span></td>' +
                '<td class="text-center"><strong style="color:#059669; font-size:1.02rem;">' + esc(u.total_runs || 0) + '</strong></td>' +
                '<td class="text-center">' + esc(u.distinct_tools || 0) + '</td>' +
                '<td style="font-size:0.8rem; color:#475569;">' + esc(formatShortDate(u.last_active_at)) + '</td>' +
                '<td class="text-center">' +
                  '<button type="button" class="btn btn-white btn-xs" onclick="window.openOfficerActivityModal(\'' + esc(u.user_id) + '\', \'' + esc(u.user_name || u.gmail) + '\')" style="font-size:0.75rem; padding:4px 9px; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;">' +
                    '📊 Inspect Activity' +
                  '</button>' +
                '</td>' +
              '</tr>'
            );
          }).join('');
        }
      }

      // 3. Live User Activity Stream
      window.filterAdminActivityTable();

    } catch (err) {
      showAdminAlert('Failed to load tool usage analytics: ' + err.message, 'error');
    }
  };

  function bindUsersTableActions() {
    var tbody = document.getElementById('admin-users-tbody');
    if (!tbody || tbody.dataset.adminBound) return;
    tbody.dataset.adminBound = '1';

    tbody.addEventListener('click', async function (ev) {
      var btn = ev.target && ev.target.closest ? ev.target.closest('[data-action="save-user"]') : null;
      if (!btn) return;
      var tr = btn.closest('tr[data-user-id]');
      if (!tr) return;
      var userId = tr.getAttribute('data-user-id') || '';
      if (!userId) return;

      var desigEl = tr.querySelector('[data-field="designation"]');
      var subEl = tr.querySelector('[data-field="subscription_status"]');
      var statusEl = tr.querySelector('[data-field="account_status"]');
      var portalEl = tr.querySelector('[data-field="can_access_portal"]');
      var consoleEl = tr.querySelector('[data-field="can_access_console"]');
      var adminEl = tr.querySelector('[data-field="is_admin"]');

      var subVal = subEl ? subEl.value : 'free_preview';
      var payload = {
        designation: desigEl ? desigEl.value : '',
        subscription_status: subVal,
        has_automated_subscription: subVal === 'active',
        account_status: statusEl ? statusEl.value : 'Active',
        can_access_portal: portalEl ? portalEl.checked : true,
        can_access_console: consoleEl ? consoleEl.checked : true,
        is_admin: adminEl ? adminEl.checked : false,
      };

      btn.disabled = true;
      btn.textContent = 'Saving...';
      showAdminAlert('');

      try {
        var res = await window.safeFetchJson('/api/admin/users/' + encodeURIComponent(userId), {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        showAdminAlert(res.message || 'User account updated successfully.', 'success');
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice(res.message || 'User account updated.', 'success');
        }
        await window.loadAdminUsers();
      } catch (err) {
        showAdminAlert('Update blocked: ' + err.message, 'error');
        btn.disabled = false;
        btn.textContent = '💾 Save';
      }
    });

    tbody.addEventListener('change', async function (ev) {
      var desigSelect = ev.target && ev.target.closest ? ev.target.closest('select[data-field="designation"]') : null;
      if (!desigSelect) return;
      var tr = desigSelect.closest('tr[data-user-id]');
      if (!tr) return;
      var userId = tr.getAttribute('data-user-id');
      if (!userId) return;
      var newDesig = desigSelect.value;
      if (!newDesig) return;

      desigSelect.style.opacity = '0.5';
      try {
        var res = await window.safeFetchJson('/api/admin/users/' + encodeURIComponent(userId), {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ designation: newDesig }),
        });
        showAdminAlert('Designation updated to ' + newDesig + ' for officer.', 'success');
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice('Officer designation updated to ' + newDesig + '.', 'success');
        }
      } catch (err) {
        showAdminAlert('Failed to update designation: ' + err.message, 'error');
      } finally {
        desigSelect.style.opacity = '1';
      }
    });
  }

  window.loadAdminUsers = async function () {
    bindUsersTableActions();
    var search = ((document.getElementById('admin-user-search') && document.getElementById('admin-user-search').value) || '').trim();
    var desig = ((document.getElementById('admin-filter-desig') && document.getElementById('admin-filter-desig').value) || '').trim();
    var status = ((document.getElementById('admin-filter-status') && document.getElementById('admin-filter-status').value) || '').trim();
    var subFilter = ((document.getElementById('admin-filter-sub') && document.getElementById('admin-filter-sub').value) || '').trim().toLowerCase();

    var qs = new URLSearchParams();
    if (search) qs.set('search', search);
    if (desig) qs.set('designation', desig);
    if (status) qs.set('account_status', status);

    try {
      var data = await window.safeFetchJson('/api/admin/users?' + qs.toString());
      var users = Array.isArray(data.users) ? data.users : [];
      if (subFilter) {
        users = users.filter(function (u) {
          var st = String(u.subscription_status || 'free_preview').toLowerCase();
          return st === subFilter;
        });
      }
      var countEl = document.getElementById('admin-users-count');
      if (countEl) countEl.textContent = String(subFilter ? users.length : (data.total != null ? data.total : users.length));

      var tbody = document.getElementById('admin-users-tbody');
      if (!tbody) return;
      if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="text-center" style="padding:24px; color:#64748b;">No officer accounts match the selected filter.</td></tr>';
        return;
      }

      tbody.innerHTML = users.map(function (u) {
        var desigOptions = '<option value="">Select Designation</option>' + DESIGNATIONS.map(function (d) {
          return '<option value="' + d + '"' + (u.designation === d ? ' selected' : '') + '>' + d + '</option>';
        }).join('');
        var statusOptions = STATUSES.map(function (st) {
          return '<option value="' + st + '"' + (u.account_status === st ? ' selected' : '') + '>' + st + '</option>';
        }).join('');
        var curSub = u.has_automated_subscription ? 'active' : String(u.subscription_status || 'free_preview').toLowerCase();
        var subOptions = SUB_STATUSES.map(function (opt) {
          return '<option value="' + opt.value + '"' + (curSub === opt.value ? ' selected' : '') + '>' + esc(opt.label) + '</option>';
        }).join('');

        return (
          '<tr data-user-id="' + esc(u.user_id) + '">' +
            '<td>' +
              '<div style="font-weight:700; color:#0f172a;">' + esc(u.name || 'Officer') + '</div>' +
              '<div style="font-size:0.78rem; color:#475569;">' + esc(u.gmail || '') + '</div>' +
            '</td>' +
            '<td style="font-family:monospace; font-size:0.82rem;">' + esc(u.mobile_number || '—') + '</td>' +
            '<td><select data-field="designation" style="padding:6px 10px; border:1.5px solid #059669; border-radius:6px; font-size:0.82rem; font-weight:700; background:#f0fdf4; color:#064e3b; cursor:pointer;" title="Change Officer Designation">' + desigOptions + '</select></td>' +
            '<td style="font-size:0.76rem; color:#475569;">' + esc(formatShortDate(u.last_login || u.registration_date)) + '</td>' +
            '<td><select data-field="subscription_status" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.8rem;">' + subOptions + '</select></td>' +
            '<td><select data-field="account_status" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.82rem;">' + statusOptions + '</select></td>' +
            '<td class="text-center"><input type="checkbox" data-field="can_access_portal"' + (u.can_access_portal !== false ? ' checked' : '') + '></td>' +
            '<td class="text-center"><input type="checkbox" data-field="can_access_console"' + (u.can_access_console !== false ? ' checked' : '') + '></td>' +
            '<td class="text-center"><input type="checkbox" data-field="is_admin"' + (u.is_admin ? ' checked' : '') + '></td>' +
            '<td class="text-center"><button type="button" class="btn btn-white btn-xs" onclick="window.openOfficerActivityModal(\'' + esc(u.user_id) + '\', \'' + esc(u.name || u.gmail || 'Officer') + '\')" style="font-size:0.75rem; padding:3px 8px; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;" title="View tools used and timestamped history">📊 Activity</button></td>' +
            '<td class="text-center"><button type="button" class="btn btn-primary btn-sm" data-action="save-user">💾 Save</button></td>' +
          '</tr>'
        );
      }).join('');
    } catch (err) {
      showAdminAlert('Failed to load officer directory: ' + err.message, 'error');
    }
  };

  window.loadAdminSubscriptions = async function () {
    try {
      var results = await Promise.all([
        window.safeFetchJson('/api/admin/subscriptions'),
        window.safeFetchJson('/api/admin/users?limit=500'),
      ]);
      var subData = results[0] || {};
      var userData = results[1] || {};
      var rzp = subData.razorpay || {};
      var plans = Array.isArray(subData.plans) ? subData.plans : [];
      var subs = Array.isArray(subData.subscriptions) ? subData.subscriptions : [];
      var payments = Array.isArray(subData.payments) ? subData.payments : [];
      var users = Array.isArray(userData.users) ? userData.users : [];
      var summary = subData.summary || {};

      var rzpText = document.getElementById('admin-razorpay-status-text');
      var rzpBadgeWrap = document.getElementById('admin-razorpay-badge-wrap');
      if (rzpText) {
        rzpText.innerHTML =
          '<div><strong>Gateway Mode:</strong> ' + (rzp.configured ? ('Live / Configured (' + esc(rzp.mode) + ')') : 'Not yet connected — set <code>RAZORPAY_KEY_ID</code>, <code>RAZORPAY_KEY_SECRET</code> &amp; <code>RAZORPAY_WEBHOOK_SECRET</code> in server <code>.env</code> when ready.') + '</div>' +
          '<div style="margin-top:4px;"><strong>Database Ready:</strong> Cloud Firestore collections <code>subscription_plans</code> (' + plans.length + '), <code>subscriptions</code> (' + subs.length + '), <code>payments</code> (' + payments.length + ') &middot; Checkout endpoints <code>/api/billing/razorpay/*</code> ready &middot; Subscribed Users: <strong>' + esc(summary.subscribed_users || 0) + '</strong> &middot; Revenue: <strong>' + esc(formatInr(summary.total_revenue_inr || 0)) + '</strong></div>';
      }
      if (rzpBadgeWrap) {
        rzpBadgeWrap.innerHTML = rzp.configured
          ? '<span class="badge-status-active">● Razorpay Connected</span>'
          : '<span class="badge-sub-active">⏳ Ready for Razorpay Keys</span>';
      }

      var plansListEl = document.getElementById('admin-plans-list');
      if (plansListEl) {
        plansListEl.innerHTML = plans.map(function (p) {
          return (
            '<div style="display:flex; justify-content:space-between; align-items:center; gap:8px; padding:8px 10px; border:1px solid #e2e8f0; border-radius:8px; margin-bottom:8px; background:#f8fafc;">' +
              '<div>' +
                '<div style="font-weight:700; font-size:0.86rem; color:#0f172a;">' + esc(p.name) + ' <span class="' + (p.is_active !== false ? 'badge-status-active' : 'badge-status-disabled') + '">' + (p.is_active !== false ? 'Active' : 'Inactive') + '</span></div>' +
                '<div style="font-size:0.76rem; color:#64748b;"><code>' + esc(p.plan_id) + '</code> &middot; ' + esc(formatInr(p.amount_inr)) + ' / ' + esc(p.duration_days) + ' days</div>' +
              '</div>' +
              '<button type="button" class="btn btn-white btn-sm" onclick="prefillPlanEditor(\'' + esc(p.plan_id) + '\', \'' + esc(p.name) + '\', ' + Number(p.amount_inr || 0) + ', ' + Number(p.duration_days || 30) + ', \'' + esc(p.razorpay_plan_id || '') + '\')">Edit</button>' +
            '</div>'
          );
        }).join('') || '<div style="color:#64748b; font-size:0.82rem;">No subscription plans configured yet.</div>';
      }

      var userSel = document.getElementById('grant-sub-user');
      if (userSel) {
        userSel.innerHTML = '<option value="">-- Select Officer Account --</option>' + users.map(function (u) {
          return '<option value="' + esc(u.user_id) + '">' + esc(u.name || 'Officer') + ' (' + esc(u.gmail) + ')</option>';
        }).join('');
      }
      var planSel = document.getElementById('grant-sub-plan');
      if (planSel) {
        planSel.innerHTML = plans.map(function (p) {
          return '<option value="' + esc(p.plan_id) + '">' + esc(p.name) + ' (' + esc(formatInr(p.amount_inr)) + ')</option>';
        }).join('');
      }

      var subsCount = document.getElementById('admin-subs-count');
      if (subsCount) subsCount.textContent = String(subs.length);
      var subsBody = document.getElementById('admin-subs-tbody');
      if (subsBody) {
        if (subs.length === 0) {
          subsBody.innerHTML = '<tr><td colspan="7" class="text-center" style="padding:20px; color:#64748b;">No subscriptions recorded yet. Grant one above or connect Razorpay to record live checkouts.</td></tr>';
        } else {
          subsBody.innerHTML = subs.map(function (s) {
            var isAct = s.status === 'active';
            var actBtn = isAct
              ? '<button type="button" class="btn btn-danger btn-sm" onclick="revokeAdminSubscription(\'' + esc(s.user_id) + '\')">Revoke</button>'
              : '<span style="color:#64748b; font-size:0.78rem;">—</span>';
            return (
              '<tr>' +
                '<td><div style="font-weight:700;">' + esc(s.user_name || 'Officer') + '</div><div style="font-size:0.76rem; color:#64748b;">' + esc(s.gmail || s.user_id) + '</div></td>' +
                '<td><strong>' + esc(s.plan_name || s.plan_id) + '</strong></td>' +
                '<td>' + esc(formatInr(s.amount_inr)) + '</td>' +
                '<td><code>' + esc(s.provider || 'admin_grant') + '</code></td>' +
                '<td><span class="' + (isAct ? 'badge-status-active' : 'badge-sub-free') + '">' + esc(s.status) + '</span></td>' +
                '<td style="font-size:0.8rem; color:#475569;">' + esc(formatShortDate(s.expires_at)) + '</td>' +
                '<td class="text-center">' + actBtn + '</td>' +
              '</tr>'
            );
          }).join('');
        }
      }

      var payCount = document.getElementById('admin-payments-count');
      if (payCount) payCount.textContent = String(payments.length);
      var payBody = document.getElementById('admin-payments-tbody');
      if (payBody) {
        if (payments.length === 0) {
          payBody.innerHTML = '<tr><td colspan="6" class="text-center" style="padding:20px; color:#64748b;">No Razorpay or payment transactions recorded yet.</td></tr>';
        } else {
          payBody.innerHTML = payments.map(function (p) {
            var refs = [p.razorpay_order_id, p.razorpay_payment_id].filter(Boolean).join(' / ') || p.payment_id;
            return (
              '<tr>' +
                '<td style="font-size:0.78rem; color:#475569;">' + esc(formatShortDate(p.captured_at || p.created_at)) + '</td>' +
                '<td><div style="font-weight:700;">' + esc(p.user_name || 'Officer') + '</div><div style="font-size:0.76rem; color:#64748b;">' + esc(p.gmail || '') + '</div></td>' +
                '<td>' + esc(p.plan_name || p.plan_id) + '</td>' +
                '<td><strong>' + esc(formatInr(p.amount_inr)) + '</strong></td>' +
                '<td style="font-family:monospace; font-size:0.78rem;">' + esc(refs) + '</td>' +
                '<td><span class="' + (p.status === 'captured' ? 'badge-status-active' : 'badge-sub-active') + '">' + esc(p.status) + '</span></td>' +
              '</tr>'
            );
          }).join('');
        }
      }
    } catch (err) {
      showAdminAlert('Failed to load subscriptions database: ' + err.message, 'error');
    }
  };

  window.prefillPlanEditor = function (planId, name, inr, days, rzpId) {
    var setVal = function (id, v) { var el = document.getElementById(id); if (el) el.value = v; };
    setVal('plan-edit-id', planId || '');
    setVal('plan-edit-name', name || '');
    setVal('plan-edit-inr', inr != null ? String(inr) : '');
    setVal('plan-edit-days', days != null ? String(days) : '30');
    setVal('plan-edit-rzp', rzpId || '');
  };

  window.saveAdminSubscriptionPlan = async function () {
    var payload = {
      plan_id: (document.getElementById('plan-edit-id') || {}).value || '',
      name: (document.getElementById('plan-edit-name') || {}).value || '',
      amount_inr: Number((document.getElementById('plan-edit-inr') || {}).value || 0),
      duration_days: Number((document.getElementById('plan-edit-days') || {}).value || 30),
      razorpay_plan_id: (document.getElementById('plan-edit-rzp') || {}).value || '',
      is_active: true,
    };
    try {
      var res = await window.safeFetchJson('/api/admin/plans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      showAdminAlert(res.message || 'Plan saved to database.', 'success');
      await window.loadAdminSubscriptions();
    } catch (err) {
      showAdminAlert('Failed to save plan: ' + err.message, 'error');
    }
  };

  window.grantAdminSubscription = async function () {
    var userId = ((document.getElementById('grant-sub-user') || {}).value || '').trim();
    var planId = ((document.getElementById('grant-sub-plan') || {}).value || 'plan_monthly').trim();
    var daysVal = ((document.getElementById('grant-sub-days') || {}).value || '').trim();
    var notes = ((document.getElementById('grant-sub-notes') || {}).value || '').trim();
    var recordPay = Boolean((document.getElementById('grant-sub-record-pay') || {}).checked);
    if (!userId) {
      showAdminAlert('Select an officer account before activating a subscription.', 'warning');
      return;
    }
    try {
      var res = await window.safeFetchJson('/api/admin/subscriptions/grant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          plan_id: planId,
          duration_days: daysVal ? Number(daysVal) : null,
          notes: notes,
          record_payment: recordPay,
        }),
      });
      showAdminAlert(res.message || 'Subscription activated.', 'success');
      await window.loadAdminSubscriptions();
    } catch (err) {
      showAdminAlert('Failed to grant subscription: ' + err.message, 'error');
    }
  };

  window.revokeAdminSubscription = async function (userId) {
    try {
      var res = await window.safeFetchJson('/api/admin/subscriptions/' + encodeURIComponent(userId) + '/revoke', {
        method: 'POST',
      });
      showAdminAlert(res.message || 'Subscription cancelled.', 'success');
      await window.loadAdminSubscriptions();
    } catch (err) {
      showAdminAlert('Failed to revoke subscription: ' + err.message, 'error');
    }
  };

  window.loadAdminPolicy = async function () {
    try {
      var res = await window.safeFetchJson('/api/admin/policy');
      var flags = res.flags || {};
      var descriptions = res.descriptions || {};
      var meta = res.meta || {};
      window.currentAccessPolicy = flags;

      var grid = document.getElementById('admin-policy-grid');
      if (!grid) return;

      var renderedKeys = {};
      var sectionsHtml = POLICY_GROUPS.map(function (grp) {
        var cards = grp.keys
          .filter(function (k) { return Object.prototype.hasOwnProperty.call(flags, k) || Object.prototype.hasOwnProperty.call(descriptions, k); })
          .map(function (k) {
            renderedKeys[k] = true;
            var mInfo = meta[k] || {};
            var desc = mInfo.description || descriptions[k] || k;
            var updatedMeta = mInfo.updated_at ? ('Updated ' + formatShortDate(mInfo.updated_at) + (mInfo.updated_by ? ' by ' + mInfo.updated_by : '')) : 'Default open free setting';
            var checked = flags[k] !== false ? ' checked' : '';
            return (
              '<label class="policy-toggle-row">' +
                '<div>' +
                  '<div style="font-weight:700; font-size:0.88rem; color:#0f172a;">' + esc(desc) + '</div>' +
                  '<div style="font-size:0.74rem; color:#64748b; margin-top:2px;">Key: <code>' + esc(k) + '</code> &middot; ' + esc(updatedMeta) + '</div>' +
                '</div>' +
                '<input type="checkbox" data-policy-key="' + esc(k) + '"' + checked + ' style="width:18px; height:18px; accent-color:#059669; cursor:pointer; flex-shrink:0;">' +
              '</label>'
            );
          }).join('');
        return '<div class="admin-section-card"><h4 style="margin:0 0 10px; color:#064e3b;">' + esc(grp.title) + '</h4>' + cards + '</div>';
      });

      var remainingKeys = Object.keys(flags).filter(function (k) { return !renderedKeys[k]; });
      if (remainingKeys.length > 0) {
        var extraCards = remainingKeys.map(function (k) {
          var mInfo = meta[k] || {};
          var desc = mInfo.description || descriptions[k] || k;
          var checked = flags[k] !== false ? ' checked' : '';
          return (
            '<label class="policy-toggle-row">' +
              '<div>' +
                '<div style="font-weight:700; font-size:0.88rem; color:#0f172a;">' + esc(desc) + '</div>' +
                '<div style="font-size:0.74rem; color:#64748b; margin-top:2px;">Key: <code>' + esc(k) + '</code></div>' +
              '</div>' +
              '<input type="checkbox" data-policy-key="' + esc(k) + '"' + checked + ' style="width:18px; height:18px; accent-color:#059669; cursor:pointer; flex-shrink:0;">' +
            '</label>'
          );
        }).join('');
        sectionsHtml.push('<div class="admin-section-card"><h4 style="margin:0 0 10px; color:#064e3b;">Additional Settings</h4>' + extraCards + '</div>');
      }

      grid.innerHTML = sectionsHtml.join('');
    } catch (err) {
      showAdminAlert('Failed to load access policy: ' + err.message, 'error');
    }
  };

  window.saveAdminPolicyUpdates = async function () {
    var inputs = document.querySelectorAll('#admin-policy-grid input[data-policy-key]');
    if (!inputs.length) return;
    var flags = {};
    inputs.forEach(function (inp) {
      var k = inp.getAttribute('data-policy-key');
      if (k) flags[k] = Boolean(inp.checked);
    });

    try {
      var res = await window.safeFetchJson('/api/admin/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flags: flags }),
      });
      window.currentAccessPolicy = res.flags || flags;
      if (typeof window.applyAccessPolicyUi === 'function') {
        window.applyAccessPolicyUi();
      }
      showAdminAlert(res.message || 'Platform access policy updated.', 'success');
      if (typeof window.showPortalNotice === 'function') {
        window.showPortalNotice(res.message || 'Platform access policy updated.', 'success');
      }
      await window.loadAdminPolicy();
    } catch (err) {
      showAdminAlert('Failed to update policy: ' + err.message, 'error');
    }
  };

  window.cachedAdminFeedbackRows = [];

  window.loadAdminFeedback = async function () {
    try {
      var res = await window.safeFetchJson('/api/admin/feedback');
      var rows = Array.isArray(res.feedback) ? res.feedback : [];
      window.cachedAdminFeedbackRows = rows;
      var countEl = document.getElementById('admin-feedback-count');
      if (countEl) countEl.textContent = String(res.count != null ? res.count : rows.length);
      window.filterAdminFeedbackRows();
    } catch (err) {
      showAdminAlert('Failed to load feedback inbox: ' + err.message, 'error');
    }
  };

  window.filterAdminFeedbackRows = function () {
    var filterEl = document.getElementById('admin-feedback-filter');
    var val = filterEl ? filterEl.value : 'ALL';
    var rows = window.cachedAdminFeedbackRows || [];
    var filtered = rows.filter(function (fb) {
      if (val === 'ALL') return true;
      if (val === 'PENDING') return !fb.admin_reply;
      if (val === 'REPLIED') return Boolean(fb.admin_reply);
      return true;
    });

    var tbody = document.getElementById('admin-feedback-tbody');
    if (!tbody) return;
    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center" style="padding:24px; color:#64748b;">No feedback submissions match the current filter.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(function (fb) {
      var fId = fb.feedback_id || fb.id || '';
      var hasReply = Boolean(fb.admin_reply);
      return (
        '<tr>' +
          '<td style="white-space:nowrap; font-size:0.8rem; color:#475569;">' + esc(formatShortDate(fb.created_at)) + '</td>' +
          '<td>' +
            '<div style="font-weight:700; color:#0f172a;">' + esc(fb.name || 'Officer') + '</div>' +
            '<div style="font-size:0.76rem; color:#64748b;">' + esc(fb.email || '—') + '</div>' +
          '</td>' +
          '<td style="font-size:0.82rem;"><span class="badge-role-pill">' + esc(fb.designation || 'OFFICER') + '</span></td>' +
          '<td><span class="badge-pill-live">' + esc(fb.category || 'General Feedback') + '</span></td>' +
          '<td style="max-width:340px; white-space:pre-wrap; font-size:0.85rem; color:#1e293b;">' + esc(fb.message || '') + '</td>' +
          '<td>' +
            (hasReply
              ? ('<span style="display:inline-block; background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; font-size:0.72rem; font-weight:800; padding:2px 8px; border-radius:10px;">🛡️ Replied</span>' +
                 '<div style="font-size:0.78rem; color:#047857; margin-top:4px; max-width:240px; white-space:pre-wrap; line-height:1.35;">' + esc(fb.admin_reply) + '</div>' +
                 '<div style="font-size:0.68rem; color:#64748b; margin-top:2px;">by ' + esc(fb.admin_name || 'Admin') + (fb.admin_replied_at ? (' · ' + esc(formatShortDate(fb.admin_replied_at))) : '') + '</div>')
              : '<span style="display:inline-block; background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-size:0.72rem; font-weight:800; padding:2px 8px; border-radius:10px;">⏳ Needs Reply</span>') +
          '</td>' +
          '<td class="text-center" style="white-space:nowrap;">' +
            '<button type="button" class="btn btn-primary btn-sm" onclick="window.openAdminReplyModal(\'' + esc(fId) + '\')" style="background:#059669; border-color:#059669; font-size:0.78rem; padding:4px 10px;">' +
              (hasReply ? '✏️ Edit' : '💬 Reply') +
            '</button>' +
          '</td>' +
        '</tr>'
      );
    }).join('');
  };

  window.openAdminReplyModal = function (feedbackId) {
    var modal = document.getElementById('admin-reply-modal');
    if (!modal) return;
    var list = window.cachedAdminFeedbackRows || [];
    var fb = null;
    for (var i = 0; i < list.length; i++) {
      if ((list[i].feedback_id || list[i].id) === feedbackId) {
        fb = list[i];
        break;
      }
    }
    if (!fb) return;

    var idEl = document.getElementById('admin-reply-feedback-id');
    var offInfo = document.getElementById('admin-reply-officer-info');
    var catBadge = document.getElementById('admin-reply-category-badge');
    var origMsg = document.getElementById('admin-reply-orig-message');
    var txtEl = document.getElementById('admin-reply-textarea');

    if (idEl) idEl.value = feedbackId;
    if (offInfo) offInfo.textContent = (fb.name || 'Officer') + ' (' + (fb.designation || 'OFFICER') + ') · ' + (fb.email || '');
    if (catBadge) catBadge.textContent = fb.category || 'General Feedback';
    if (origMsg) origMsg.textContent = fb.message || '';
    if (txtEl) txtEl.value = fb.admin_reply || '';

    modal.style.display = 'flex';
    if (txtEl) txtEl.focus();
  };

  window.closeAdminReplyModal = function () {
    var modal = document.getElementById('admin-reply-modal');
    if (modal) modal.style.display = 'none';
  };

  window.submitAdminReplyModal = async function () {
    var idEl = document.getElementById('admin-reply-feedback-id');
    var txtEl = document.getElementById('admin-reply-textarea');
    var btn = document.getElementById('btn-save-admin-reply');
    var feedbackId = idEl ? idEl.value : '';
    var reply = txtEl ? txtEl.value.trim() : '';

    if (!feedbackId) return;
    if (!reply) {
      showAdminAlert('Please enter an official response before publishing.', 'warning');
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Publishing...';
    }

    try {
      var res = await window.safeFetchJson('/api/admin/feedback/' + encodeURIComponent(feedbackId) + '/reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply: reply }),
      });
      if (res && res.success) {
        window.closeAdminReplyModal();
        showAdminAlert('✓ Official admin reply published successfully!', 'success');
        await window.loadAdminFeedback();
      } else {
        showAdminAlert((res && res.message) || 'Failed to publish admin reply.', 'error');
      }
    } catch (err) {
      showAdminAlert('Error publishing admin reply: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Publish Reply';
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Module Visibility Management (Hide / View Modules in Officer Workspace)
  // ---------------------------------------------------------------------------

  window.cachedModuleCatalog = [];

  window.loadAdminModuleVisibility = async function () {
    try {
      var res = await window.safeFetchJson('/api/admin/policy');
      var flags = res.flags || {};
      window.currentAccessPolicy = flags;
      var catalog = Array.isArray(res.modules_catalog) ? res.modules_catalog : [];
      window.cachedModuleCatalog = catalog.map(function (m) {
        var visKey = m.visibility_key || ('visible_' + m.id);
        var isVis = Object.prototype.hasOwnProperty.call(flags, visKey)
          ? flags[visKey] !== false
          : (m.visible !== false && flags[m.id] !== false);
        return Object.assign({}, m, { visible: isVis });
      });
      window.renderAdminModuleVisibility();
    } catch (err) {
      showAdminAlert('Failed to load module visibility catalog: ' + err.message, 'error');
    }
  };

  window.renderAdminModuleVisibility = function () {
    var grid = document.getElementById('admin-module-visibility-grid');
    if (!grid) return;

    var catFilter = (document.getElementById('adm-visibility-filter-category') || {}).value || 'ALL';
    var statusFilter = (document.getElementById('adm-visibility-filter-status') || {}).value || 'ALL';
    var searchVal = ((document.getElementById('adm-visibility-search') || {}).value || '').trim().toLowerCase();

    var filtered = window.cachedModuleCatalog.filter(function (m) {
      if (catFilter !== 'ALL' && m.category !== catFilter) return false;
      if (statusFilter === 'VISIBLE' && !m.visible) return false;
      if (statusFilter === 'HIDDEN' && m.visible) return false;
      if (searchVal) {
        var haystack = (m.name + ' ' + (m.description || '') + ' ' + m.id + ' ' + (m.category || '')).toLowerCase();
        if (haystack.indexOf(searchVal) === -1) return false;
      }
      return true;
    });

    var countBadge = document.getElementById('adm-visibility-count-badge');
    if (countBadge) {
      countBadge.textContent = filtered.length + ' of ' + window.cachedModuleCatalog.length + ' Modules';
    }

    if (filtered.length === 0) {
      grid.innerHTML = '<div style="grid-column:1/-1; padding:32px; text-align:center; color:#64748b; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:12px;">No modules match the selected filter criteria.</div>';
      return;
    }

    grid.innerHTML = filtered.map(function (m) {
      var isVis = Boolean(m.visible);
      var cardBorder = isVis ? '1.5px solid #10b981' : '1.5px dashed #f87171';
      var cardBg = isVis ? '#ffffff' : '#fef2f2';
      var icon = m.icon || '📦';
      
      var badgeHtml = isVis
        ? '<span style="display:inline-flex; align-items:center; gap:5px; font-weight:700; color:#065f46; background:#ecfdf5; border:1px solid #a7f3d0; border-radius:12px; padding:3px 10px; font-size:0.75rem;">● 👁️ Visible to Officers</span>'
        : '<span style="display:inline-flex; align-items:center; gap:5px; font-weight:700; color:#991b1b; background:#fee2e2; border:1px solid #fecaca; border-radius:12px; padding:3px 10px; font-size:0.75rem;">● 🙈 Hidden from Officers</span>';

      var toggleBtnHtml = isVis
        ? '<button type="button" class="btn btn-outline btn-sm" onclick="toggleModuleVisibility(\'' + esc(m.id) + '\')" style="border-color:#ef4444; color:#991b1b; background:#ffffff; font-size:0.78rem; font-weight:700; display:inline-flex; align-items:center; gap:4px;">🙈 Hide Module</button>'
        : '<button type="button" class="btn btn-primary btn-sm" onclick="toggleModuleVisibility(\'' + esc(m.id) + '\')" style="background:#059669; border-color:#059669; color:#ffffff; font-size:0.78rem; font-weight:700; display:inline-flex; align-items:center; gap:4px;">👁️ Show Module</button>';

      return (
        '<div class="module-card" style="border:' + cardBorder + '; background:' + cardBg + '; border-radius:12px; padding:16px; display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 2px 8px rgba(0,0,0,0.04); transition:all 0.2s ease;">' +
          '<div>' +
            '<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:8px;">' +
              '<div style="display:flex; align-items:center; gap:8px;">' +
                '<span style="font-size:1.5rem; line-height:1;">' + esc(icon) + '</span>' +
                '<div>' +
                  '<div style="font-weight:800; font-size:0.95rem; color:#0f172a; line-height:1.25;">' + esc(m.name) + '</div>' +
                  '<div style="font-size:0.73rem; color:#64748b; margin-top:2px;">Category: <span style="font-weight:600; color:#0f766e;">' + esc(m.category || 'General') + '</span> &middot; <code>' + esc(m.id) + '</code></div>' +
                '</div>' +
              '</div>' +
              '<label style="display:inline-flex; align-items:center; cursor:pointer;" title="Click to toggle visibility">' +
                '<input type="checkbox" onchange="toggleModuleVisibility(\'' + esc(m.id) + '\')"' + (isVis ? ' checked' : '') + ' style="width:18px; height:18px; accent-color:#059669; cursor:pointer;">' +
              '</label>' +
            '</div>' +
            '<p style="font-size:0.8rem; color:#475569; margin:6px 0 12px 0; line-height:1.45; min-height:42px;">' + esc(m.description || '') + '</p>' +
          '</div>' +
          '<div style="border-top:1px solid #e2e8f0; padding-top:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">' +
            '<div>' + badgeHtml + '</div>' +
            '<div>' + toggleBtnHtml + '</div>' +
          '</div>' +
        '</div>'
      );
    }).join('');
  };

  window.toggleModuleVisibility = function (moduleId) {
    var mod = (window.cachedModuleCatalog || []).find(function (m) { return m.id === moduleId; });
    if (mod) {
      mod.visible = !mod.visible;
      window.renderAdminModuleVisibility();
    }
  };

  window.setAllModulesVisibility = function (visibleBool) {
    (window.cachedModuleCatalog || []).forEach(function (m) {
      m.visible = Boolean(visibleBool);
    });
    window.renderAdminModuleVisibility();
    showAdminAlert(visibleBool ? 'All modules marked VISIBLE. Click "Apply Visibility Changes" to save and publish.' : 'All modules marked HIDDEN. Click "Apply Visibility Changes" to save and publish.', 'info');
  };

  window.filterModuleVisibilityCards = function () {
    window.renderAdminModuleVisibility();
  };

  window.saveAdminModuleVisibility = async function () {
    if (!window.cachedModuleCatalog || !window.cachedModuleCatalog.length) {
      showAdminAlert('No modules available to update.', 'warning');
      return;
    }
    var visibilityMap = {};
    window.cachedModuleCatalog.forEach(function (m) {
      visibilityMap[m.id] = Boolean(m.visible);
    });

    try {
      var res = await window.safeFetchJson('/api/admin/modules/visibility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visibility: visibilityMap }),
      });
      window.currentAccessPolicy = res.flags || window.currentAccessPolicy;
      if (typeof window.applyAccessPolicyUi === 'function') {
        window.applyAccessPolicyUi(res);
      }
      showAdminAlert(res.message || 'Officer Workspace module visibility updated successfully.', 'success');
      if (typeof window.showPortalNotice === 'function') {
        window.showPortalNotice('Officer Workspace module visibility updated.', 'success');
      }
      await window.loadAdminModuleVisibility();
    } catch (err) {
      showAdminAlert('Failed to update module visibility: ' + err.message, 'error');
    }
  };

  // ==============================================================================
  // Tab 8: DSC Signer Bundle Installed Machines & Telemetry Controller
  // ==============================================================================
  window._adminAllDscMachines = [];

  window.loadAdminDscTelemetry = async function () {
    try {
      var data = await window.safeFetchJson('/api/admin/dsc-telemetry');
      var machines = Array.isArray(data.machines) ? data.machines : [];
      window._adminAllDscMachines = machines;

      var gh = data.github_downloads || {};
      var el;
      el = document.getElementById('admin-dsc-total-machines'); if (el) el.textContent = String(data.total_machines || 0);
      el = document.getElementById('admin-dsc-active-24h'); if (el) el.textContent = String(data.active_24h || 0);
      el = document.getElementById('admin-dsc-active-7d'); if (el) el.textContent = String(data.active_7d || 0);
      el = document.getElementById('adm-tab-dsc-badge'); if (el) el.textContent = String(data.total_machines || 0);

      el = document.getElementById('admin-dsc-total-downloads');
      if (el) el.textContent = String(gh.total || 0);
      el = document.getElementById('admin-dsc-downloads-sub');
      if (el) el.textContent = 'Offline: ' + (gh.offline_suite || 0) + ' · Cloud Lite: ' + (gh.cloud_lite || 0);

      window.renderAdminDscRows(machines);
    } catch (err) {
      showAdminAlert('Failed to load DSC machines telemetry: ' + err.message, 'error');
    }
  };

  window.renderAdminDscRows = function (machines) {
    var tbody = document.getElementById('admin-dsc-tbody');
    var countEl = document.getElementById('admin-dsc-count');
    if (!tbody) return;
    if (countEl) countEl.textContent = String(machines.length);

    if (machines.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:24px; color:#64748b;">No DSC Signer bundle installations recorded yet. As Gram Panchayat operators run the installer or self-heal, their verified hardware fingerprints and computer names will appear here automatically.</td></tr>';
      return;
    }

    tbody.innerHTML = machines.map(function (m) {
      var statusClass = 'badge-status-active';
      var st = (m.deployment_status || '').toUpperCase();
      if (st.indexOf('SUCCESS') !== -1 || st.indexOf('VERIFIED') !== -1 || st.indexOf('OPTIMAL') !== -1) {
        statusClass = 'badge-sub-active';
      } else if (st.indexOf('REPAIR') !== -1 || st.indexOf('DRIFT') !== -1 || st.indexOf('WARN') !== -1) {
        statusClass = 'badge-status-disabled';
      }

      var rawVer = String(m.config_version || '1.0.1').replace(/^v+/i, '');
      if (rawVer.indexOf('2026.11') === 0) rawVer = '1.0.0';

      var osName = esc(m.os_name || 'Windows');
      var osVer = esc(m.os_version || '');
      var match = osVer.match(/10\.0\.(\d{5,})/);
      if ((match && parseInt(match[1], 10) >= 22000) || osVer.indexOf('10.0.22') === 0 || osVer.indexOf('10.0.26') === 0 || osVer.indexOf('10.0.23') === 0 || osVer.indexOf('10.0.25') === 0) {
        osName = osName.replace('Windows 10', 'Windows 11');
      }

      var uName = (m.user_name || '').trim();
      var regOwner = (m.registered_owner || '').trim();
      var whoami = (m.whoami || '').trim();
      var alias = (m.custom_alias || '').trim();
      var pcDisplay = esc(m.pc_name || 'Unknown PC');

      var userBadge = '';
      if (whoami || uName) {
        var primaryUser = whoami || uName;
        userBadge = '<div style="font-size:0.75rem; color:#0369a1; font-weight:600; margin-top:3px; display:inline-flex; align-items:center; gap:4px; background:#f0f9ff; padding:2px 8px; border-radius:4px; border:1px solid #bae6fd;">' +
                    '<span>👤</span> ' + esc(primaryUser) + '</div>';
      } else {
        userBadge = '<div style="font-size:0.70rem; color:#94a3b8; margin-top:2px;">👤 <em>Awaiting v1.0.1+ ping</em></div>';
      }

      var nameHtml = '';
      if (alias) {
        nameHtml = '<div style="font-size:0.85rem; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:6px;">' +
                   '🏷️ ' + esc(alias) +
                   ' <button type="button" class="btn btn-ghost btn-xs" style="padding:0 4px; color:#64748b; font-size:0.72rem; border:none; background:transparent; cursor:pointer;" onclick="window.editDscMachineAlias(\'' + esc(m.system_id) + '\', \'' + esc(alias) + '\')" title="Edit friendly name">✏️</button>' +
                   '</div>' +
                   '<div style="font-size:0.74rem; color:#64748b;">PC: ' + pcDisplay + '</div>';
      } else {
        nameHtml = '<div style="font-size:0.85rem; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:6px;">' +
                   pcDisplay +
                   ' <button type="button" class="btn btn-ghost btn-xs" style="padding:1px 6px; color:#64748b; font-size:0.70rem; border:1px dashed #cbd5e1; border-radius:4px; background:#fff; cursor:pointer;" onclick="window.editDscMachineAlias(\'' + esc(m.system_id) + '\', \'\')" title="Add GP Office name or Operator label">+ Label</button>' +
                   '</div>';
      }

      return (
        '<tr>' +
          '<td>' +
            nameHtml +
            userBadge +
            (m.client_ip ? '<div style="font-size:0.70rem; color:#94a3b8; margin-top:2px;">IP: ' + esc(m.client_ip) + '</div>' : '') +
          '</td>' +
          '<td><code style="font-size:0.75rem; background:#f1f5f9; padding:2px 6px; border-radius:4px;">' + esc(m.system_id || '—') + '</code></td>' +
          '<td>' + osName + (osVer ? ' <span style="font-size:0.75rem; color:#64748b;">(' + osVer + ')</span>' : '') + '</td>' +
          '<td><span style="font-size:0.78rem; font-weight:700; color:#0369a1;">v' + esc(rawVer) + '</span></td>' +
          '<td><span class="' + statusClass + '">' + esc(m.deployment_status || 'ACTIVE') + '</span>' +
            (m.details ? '<div style="font-size:0.72rem; color:#64748b; margin-top:2px;">' + esc(m.details) + '</div>' : '') +
          '</td>' +
          '<td style="font-size:0.78rem; color:#64748b;">' + esc(m.first_seen_at || '—') + '</td>' +
          '<td style="font-size:0.78rem; font-weight:600; color:#1e293b;">' + esc(m.last_seen_at || '—') + '</td>' +
          '<td class="text-center"><span class="badge-pill-live" style="background:#e0f2fe; color:#0284c7; border:none; padding:2px 8px;">' + esc(m.ping_count || 1) + '</span></td>' +
        '</tr>'
      );
    }).join('');
  };

  window.filterAdminDscRows = function () {
    var search = ((document.getElementById('admin-dsc-search') && document.getElementById('admin-dsc-search').value) || '').trim().toLowerCase();
    var all = window._adminAllDscMachines || [];
    if (!search) {
      window.renderAdminDscRows(all);
      return;
    }
    var filtered = all.filter(function (m) {
      return (
        (m.pc_name || '').toLowerCase().indexOf(search) !== -1 ||
        (m.whoami || '').toLowerCase().indexOf(search) !== -1 ||
        (m.user_name || '').toLowerCase().indexOf(search) !== -1 ||
        (m.registered_owner || '').toLowerCase().indexOf(search) !== -1 ||
        (m.custom_alias || '').toLowerCase().indexOf(search) !== -1 ||
        (m.system_id || '').toLowerCase().indexOf(search) !== -1 ||
        (m.os_name || '').toLowerCase().indexOf(search) !== -1 ||
        (m.deployment_status || '').toLowerCase().indexOf(search) !== -1
      );
    });
    window.renderAdminDscRows(filtered);
  };

  window.editDscMachineAlias = async function (sysId, currentAlias) {
    var newAlias = prompt('Enter a friendly name or GP Office label for this PC (e.g., "Khammam GP Office - Naresh"):', currentAlias || '');
    if (newAlias === null) return;
    try {
      var res = await window.safeFetchJson('/api/admin/dsc-machine-alias', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_id: sysId, custom_alias: newAlias.trim() })
      });
      if (res && res.success) {
        showAdminAlert('Machine label saved successfully!', 'success');
        window.loadAdminDscTelemetry();
      } else {
        showAdminAlert('Could not save machine label: ' + (res.error || 'Server error'), 'error');
      }
    } catch (e) {
      showAdminAlert('Error saving label: ' + e.message, 'error');
    }
  };
})();
