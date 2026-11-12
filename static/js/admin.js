/**
 * e-Panchayat Automation — Administrator Governance Dashboard Controller
 * Manages Overview KPIs, Users & Platform Access, 9-Flag Access Policy,
 * Officer Feedback Inbox, and Firebase Identity Posture.
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

  var POLICY_GROUPS = [
    {
      title: 'Platform Availability & Launch Controls',
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

  function currentUserIsAdmin() {
    var isAdmHost = typeof window.isAdminHost === 'function' && window.isAdminHost();
    if (!isAdmHost) return false;
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
    var station = document.getElementById('admin-dashboard-station');
    if (station) {
      station.style.display = 'block';
      station.scrollIntoView({ behavior: 'smooth' });
    }
    showAdminAlert('');
    window.switchAdminTab('overview');
  };

  window.switchAdminTab = function (tab) {
    var tabs = ['overview', 'users', 'policy', 'feedback'];
    var activeTab = tabs.indexOf(tab) !== -1 ? tab : 'overview';

    tabs.forEach(function (t) {
      var btn = document.getElementById('admin-tab-' + t);
      var pane = document.getElementById('admin-pane-' + t);
      if (btn) btn.classList.toggle('active', t === activeTab);
      if (pane) pane.style.display = t === activeTab ? 'block' : 'none';
    });

    if (activeTab === 'overview') window.loadAdminOverview();
    else if (activeTab === 'users') window.loadAdminUsers();
    else if (activeTab === 'policy') window.loadAdminPolicy();
    else if (activeTab === 'feedback') window.loadAdminFeedback();
  };

  window.loadAdminOverview = async function () {
    try {
      var data = await window.safeFetchJson('/api/admin/overview');
      var s = data.stats || {};
      var usageList = Array.isArray(s.module_usage) ? s.module_usage : [];
      var eventTotal = usageList.reduce(function (acc, item) {
        return acc + Number(item.count || 0);
      }, 0);

      var el;
      el = document.getElementById('adm-kpi-users'); if (el) el.textContent = s.total_users != null ? s.total_users : '0';
      el = document.getElementById('adm-kpi-active'); if (el) el.textContent = s.active_users != null ? s.active_users : '0';
      el = document.getElementById('adm-kpi-completed'); if (el) el.textContent = s.completed_profiles != null ? s.completed_profiles : '0';
      el = document.getElementById('adm-kpi-events'); if (el) el.textContent = eventTotal;
      el = document.getElementById('adm-kpi-feedback'); if (el) el.textContent = 'Feedback Count: ' + (s.total_feedback != null ? s.total_feedback : 0);

      var grid = document.getElementById('admin-breakdown-grid');
      if (!grid) return;

      var desigRows = (s.by_designation || []).map(function (item) {
        return '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;">' +
          '<span>' + esc(item.designation || 'Pending') + '</span>' +
          '<strong>' + esc(item.count || 0) + '</strong></div>';
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No designation data recorded yet.</div>';

      var roleRows = (s.by_role || []).map(function (item) {
        return '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;">' +
          '<span>' + esc(item.role || 'Pending') + '</span>' +
          '<strong>' + esc(item.count || 0) + '</strong></div>';
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No role data recorded yet.</div>';

      var sessionRows = (s.active_sessions || []).map(function (item) {
        var label = item.app_scope === 'console' ? 'Platform 2 (Console)' : 'Platform 1 (Portal)';
        return '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;">' +
          '<span>' + esc(label) + '</span>' +
          '<strong>' + esc(item.count || 0) + '</strong></div>';
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No active scoped sessions.</div>';

      var modRows = usageList.slice(0, 6).map(function (item) {
        return '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;">' +
          '<span>' + esc((item.platform_scope || 'portal') + ' · ' + (item.module || 'action')) + '</span>' +
          '<strong>' + esc(item.count || 0) + '</strong></div>';
      }).join('') || '<div style="color:#64748b; font-size:0.84rem;">No usage events in the past 30 days.</div>';

      var fb = data.firebase || {};
      var fsLabel = fb.firestore_mode === 'live_firestore'
        ? 'Connected (asia-south1)'
        : (fb.firestore_mode === 'emulator' ? 'Firebase Emulator' : 'Dev In-Memory');
      grid.innerHTML =
        '<div class="admin-section-card">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">Users by Designation</h4>' +
          desigRows +
        '</div>' +
        '<div class="admin-section-card">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">Users by Operational Level</h4>' +
          roleRows +
        '</div>' +
        '<div class="admin-section-card">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">Scoped Sessions &amp; 30-Day Events</h4>' +
          '<div style="font-size:0.75rem; font-weight:800; color:#64748b; text-transform:uppercase; margin-bottom:4px;">Active Scoped Sessions</div>' +
          sessionRows +
          '<div style="font-size:0.75rem; font-weight:800; color:#64748b; text-transform:uppercase; margin:10px 0 4px;">Top Module Usage</div>' +
          modRows +
        '</div>' +
        '<div class="admin-section-card">' +
          '<h4 style="margin:0 0 10px; color:#064e3b;">Firebase Auth &amp; Firestore Posture</h4>' +
          '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;"><span>Environment</span><strong>' + esc(data.environment || 'development') + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;"><span>Workspace Retention</span><strong>' + esc(data.temp_retention_hours != null ? data.temp_retention_hours : 24) + ' hrs</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;"><span>Firebase Auth</span><strong>' + (fb.auth_configured !== false ? 'Enabled (' + esc(fb.project_id || 'epanchayat-automation-tg') + ')' : 'Not Configured') + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #f1f5f9;"><span>Cloud Firestore</span><strong>' + esc(fsLabel) + '</strong></div>' +
          '<div style="display:flex; justify-content:space-between; padding:4px 0;"><span>Disabled Accounts</span><strong>' + esc(s.disabled_users != null ? s.disabled_users : 0) + '</strong></div>' +
        '</div>';
    } catch (err) {
      showAdminAlert('Failed to load administrator overview: ' + err.message, 'error');
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
      var statusEl = tr.querySelector('[data-field="account_status"]');
      var portalEl = tr.querySelector('[data-field="can_access_portal"]');
      var consoleEl = tr.querySelector('[data-field="can_access_console"]');
      var adminEl = tr.querySelector('[data-field="is_admin"]');

      var payload = {
        designation: desigEl ? desigEl.value : '',
        role: roleEl ? roleEl.value : '',
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

    var qs = new URLSearchParams();
    if (search) qs.set('search', search);
    if (desig) qs.set('designation', desig);
    if (role) qs.set('role', role);
    if (status) qs.set('account_status', status);

    try {
      var data = await window.safeFetchJson('/api/admin/users?' + qs.toString());
      var users = Array.isArray(data.users) ? data.users : [];
      var countEl = document.getElementById('admin-users-count');
      if (countEl) countEl.textContent = String(data.total != null ? data.total : users.length);

      var tbody = document.getElementById('admin-users-tbody');
      if (!tbody) return;
      if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center" style="padding:24px; color:#64748b;">No officer accounts match the selected filter.</td></tr>';
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

        return (
          '<tr data-user-id="' + esc(u.user_id) + '">' +
            '<td>' +
              '<div style="font-weight:700; color:#0f172a;">' + esc(u.name || 'Officer') + '</div>' +
              '<div style="font-size:0.78rem; color:#475569;">' + esc(u.gmail || '') + '</div>' +
            '</td>' +
            '<td style="font-family:monospace; font-size:0.82rem;">' + esc(u.mobile_number || '—') + '</td>' +
            '<td><select data-field="designation" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.82rem;">' + desigOptions + '</select></td>' +
            '<td><select data-field="role" style="padding:5px 8px; border:1px solid var(--border); border-radius:6px; font-size:0.82rem;">' + roleOptions + '</select></td>' +
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
