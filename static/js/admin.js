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
      keys: ['module_dsr_excel', 'module_dsr_multiday'],
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
    var tabs = ['overview', 'tools', 'users', 'subscriptions', 'policy', 'feedback'];
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
    else if (activeAdminTab === 'subscriptions') window.loadAdminSubscriptions();
    else if (activeAdminTab === 'policy') window.loadAdminPolicy();
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

      var roleRows = (s.by_role || []).map(function (item) {
        return '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;">' +
          '<span>' + esc(item.role || 'Pending') + '</span>' +
          '<strong>' + esc(item.count || 0) + '</strong></div>';
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No role data yet.</div>';

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
          '<h4 style="margin:0 0 10px; color:#064e3b;">👥 Registered by Designation &amp; Role</h4>' +
          desigRows +
          '<div style="margin-top:10px; padding-top:8px; border-top:1px dashed #cbd5e1;">' + roleRows + '</div>' +
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

  window.loadAdminToolUsage = async function () {
    var daysEl = document.getElementById('admin-tools-days');
    var days = daysEl ? daysEl.value : '30';
    try {
      var data = await window.safeFetchJson('/api/admin/tool-usage?days=' + encodeURIComponent(days));
      var tools = Array.isArray(data.tool_usage) ? data.tool_usage : [];
      var cats = Array.isArray(data.category_usage) ? data.category_usage : [];
      var recent = Array.isArray(data.recent_activity) ? data.recent_activity : [];

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

      var countEl = document.getElementById('admin-tools-count');
      if (countEl) countEl.textContent = String(tools.length);
      var tbody = document.getElementById('admin-tools-tbody');
      if (tbody) {
        if (tools.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center" style="padding:20px; color:#64748b;">No tool runs recorded in this window.</td></tr>';
        } else {
          tbody.innerHTML = tools.map(function (t) {
            return (
              '<tr>' +
                '<td><strong>' + esc(t.tool_name || t.tool_id) + '</strong><div style="font-size:0.74rem; color:#64748b;"><code>' + esc(t.tool_id) + '</code></div></td>' +
                '<td><span class="badge-role-pill">' + esc(t.category || 'Tools') + '</span></td>' +
                '<td class="text-center"><strong>' + esc(t.count || 0) + '</strong></td>' +
                '<td class="text-center">' + esc(t.unique_users || 0) + '</td>' +
                '<td style="font-size:0.8rem; color:#475569;">' + esc(formatShortDate(t.last_used_at)) + '</td>' +
              '</tr>'
            );
          }).join('');
        }
      }

      var recCount = document.getElementById('admin-recent-count');
      if (recCount) recCount.textContent = String(recent.length);
      var recBody = document.getElementById('admin-recent-tbody');
      if (recBody) {
        if (recent.length === 0) {
          recBody.innerHTML = '<tr><td colspan="5" class="text-center" style="padding:20px; color:#64748b;">No recent activity events yet.</td></tr>';
        } else {
          recBody.innerHTML = recent.map(function (ev) {
            return (
              '<tr>' +
                '<td style="white-space:nowrap; font-size:0.78rem; color:#475569;">' + esc(formatShortDate(ev.created_at)) + '</td>' +
                '<td><div style="font-weight:700;">' + esc(ev.user_name || 'Guest') + '</div><div style="font-size:0.75rem; color:#64748b;">' + esc(ev.gmail || '—') + '</div></td>' +
                '<td><strong>' + esc(ev.tool_name || ev.tool_id) + '</strong></td>' +
                '<td><span class="badge-role-pill">' + esc(ev.category || '') + '</span></td>' +
                '<td style="font-size:0.78rem; color:#475569;">' + esc(ev.details || ev.action || '—') + '</td>' +
              '</tr>'
            );
          }).join('');
        }
      }
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
      var roleEl = tr.querySelector('[data-field="role"]');
      var subEl = tr.querySelector('[data-field="subscription_status"]');
      var statusEl = tr.querySelector('[data-field="account_status"]');
      var portalEl = tr.querySelector('[data-field="can_access_portal"]');
      var consoleEl = tr.querySelector('[data-field="can_access_console"]');
      var adminEl = tr.querySelector('[data-field="is_admin"]');

      var subVal = subEl ? subEl.value : 'free_preview';
      var payload = {
        designation: desigEl ? desigEl.value : '',
        role: roleEl ? roleEl.value : '',
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
  }

  window.loadAdminUsers = async function () {
    bindUsersTableActions();
    var search = ((document.getElementById('admin-user-search') && document.getElementById('admin-user-search').value) || '').trim();
    var desig = ((document.getElementById('admin-filter-desig') && document.getElementById('admin-filter-desig').value) || '').trim();
    var role = ((document.getElementById('admin-filter-role') && document.getElementById('admin-filter-role').value) || '').trim();
    var status = ((document.getElementById('admin-filter-status') && document.getElementById('admin-filter-status').value) || '').trim();
    var subFilter = ((document.getElementById('admin-filter-sub') && document.getElementById('admin-filter-sub').value) || '').trim().toLowerCase();

    var qs = new URLSearchParams();
    if (search) qs.set('search', search);
    if (desig) qs.set('designation', desig);
    if (role) qs.set('role', role);
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
        var desigOptions = '<option value="">Pending</option>' + DESIGNATIONS.map(function (d) {
          return '<option value="' + d + '"' + (u.designation === d ? ' selected' : '') + '>' + d + '</option>';
        }).join('');
        var roleOptions = '<option value="">Pending</option>' + ROLES.map(function (r) {
          return '<option value="' + esc(r) + '"' + (u.role === r ? ' selected' : '') + '>' + esc(r) + '</option>';
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
            '<td><select data-field="designation" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.82rem;">' + desigOptions + '</select></td>' +
            '<td><select data-field="role" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.82rem;">' + roleOptions + '</select></td>' +
            '<td style="font-size:0.76rem; color:#475569;">' + esc(formatShortDate(u.last_login || u.registration_date)) + '</td>' +
            '<td><select data-field="subscription_status" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.8rem;">' + subOptions + '</select></td>' +
            '<td><select data-field="account_status" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.82rem;">' + statusOptions + '</select></td>' +
            '<td class="text-center"><input type="checkbox" data-field="can_access_portal"' + (u.can_access_portal !== false ? ' checked' : '') + '></td>' +
            '<td class="text-center"><input type="checkbox" data-field="can_access_console"' + (u.can_access_console !== false ? ' checked' : '') + '></td>' +
            '<td class="text-center"><input type="checkbox" data-field="is_admin"' + (u.is_admin ? ' checked' : '') + '></td>' +
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

  window.loadAdminFeedback = async function () {
    try {
      var res = await window.safeFetchJson('/api/admin/feedback');
      var rows = Array.isArray(res.feedback) ? res.feedback : [];
      var countEl = document.getElementById('admin-feedback-count');
      if (countEl) countEl.textContent = String(res.count != null ? res.count : rows.length);

      var tbody = document.getElementById('admin-feedback-tbody');
      if (!tbody) return;
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center" style="padding:24px; color:#64748b;">No officer feedback submissions yet.</td></tr>';
        return;
      }

      tbody.innerHTML = rows.map(function (fb) {
        return (
          '<tr>' +
            '<td style="white-space:nowrap; font-size:0.8rem; color:#475569;">' + esc(formatShortDate(fb.created_at)) + '</td>' +
            '<td>' +
              '<div style="font-weight:700; color:#0f172a;">' + esc(fb.name || 'Officer') + '</div>' +
              '<div style="font-size:0.78rem; color:#64748b;">' + esc(fb.email || '—') + '</div>' +
            '</td>' +
            '<td style="font-size:0.82rem;">' + esc([fb.designation, fb.role].filter(Boolean).join(' · ') || '—') + '</td>' +
            '<td><span class="badge-pill-live">' + esc(fb.category || 'General Feedback') + '</span></td>' +
            '<td style="max-width:420px; white-space:pre-wrap; font-size:0.85rem;">' + esc(fb.message || '') + '</td>' +
          '</tr>'
        );
      }).join('');
    } catch (err) {
      showAdminAlert('Failed to load feedback inbox: ' + err.message, 'error');
    }
  };
})();
