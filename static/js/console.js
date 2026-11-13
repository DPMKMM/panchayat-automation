/**
 * e-Panchayat Automation Console & Shared Station Controller
 * Stage 2 Departmental Login/OTP, DSR Robot, Balance Robot, House Tax DCB,
 * GP Inspections, Active Sessions Modal, and Non-Blocking Notices.
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

  var inspCurrentReport = null;
  var inspWeeksCache = [];

  var consolePollTimer = null;
  var genProgressInterval = null;
  var genStartTime = 0;
  var targetDurationSec = 45;
  var currentPct = 0;
  var stepTimeouts = [];
  var deptAutoCloseTimer = null;
  var deptLoginInProgress = false;
  var lastDeptVerifyResult = null;
  var dsrGenerationInFlight = false;
  var balanceGenerationInFlight = false;

  var reportData = null;
  var currentStep = 1;
  var taxDistrictsLoaded = false;
  var taxDataCache = null;
  var currentTaxTab = 'abstract';
  var inspFilteredCache = [];

  window.isDeptAuthenticated = false;
  window.pendingStation = null;
  window.sessionExpiresIn = 999999;
  window.sessionNoExpiry = true;
  window.sessionCanExtend = false;
  window.sessionTimerInterval = null;
  window.currentMandalRows = [];
  window.currentSortKey = 'before_9';
  window.currentSortAsc = true;

  function showNotice(msg, type) {
    if (typeof window.showPortalNotice === 'function') {
      window.showPortalNotice(msg, type || 'info');
    }
  }

  function showModalAlert(elId, msg, isErr) {
    var el = document.getElementById(elId);
    if (!el) return;
    if (!msg) {
      el.style.display = 'none';
      el.textContent = '';
      return;
    }
    el.style.display = 'block';
    el.style.background = isErr === false ? '#ecfdf5' : '#fef2f2';
    el.style.color = isErr === false ? '#065f46' : '#dc2626';
    el.style.border = isErr === false ? '1px solid #a7f3d0' : '1px solid #fecaca';
    el.textContent = msg;
  }

  function localDateStr() {
    var d = new Date();
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function sanitizeTel(phone) {
    return String(phone || '').replace(/[^0-9+]/g, '');
  }

  function clearStepTimeouts() {
    while (stepTimeouts.length) {
      clearTimeout(stepTimeouts.pop());
    }
  }

  function clearEptsStorageOnly() {
    reportData = null;
    window.currentMandalName = '';
    window.currentUserLevel = 'district';
    ['results-section', 'state-format-results', 'auto-multi-results-section', 'inspections-results-card', 'balance-results-card'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    if (window.DeptSessionManager && typeof window.DeptSessionManager.clearEptsMetadata === 'function') {
      window.DeptSessionManager.clearEptsMetadata();
      return;
    }
    var keys = [
      'epts_portal_auth',
      'epts_dept_session',
      'epts_officer_id',
      'epts_user_level',
      'epts_mandal_name',
      'epts_district_name',
      'epts_office_name',
      'epts_session_id',
    ];
    keys.forEach(function (k) {
      try { sessionStorage.removeItem(k); } catch (e) {}
      try { localStorage.removeItem(k); } catch (e) {}
    });
  }

  function clearDeptCredentialInputs() {
    ['dept-modal-pwd', 'dept-modal-otp-input', 'auto-pwd', 'auto-otp'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = '';
    });
  }

  function isVisibleBlock(id) {
    var el = document.getElementById(id);
    return Boolean(el && el.style.display && el.style.display !== 'none');
  }

  // ---------------------------------------------------------------------------
  // Console Initialization & Polling Lifecycle
  // ---------------------------------------------------------------------------

  window.initConsoleAfterPortalAuth = async function () {
    var datePicker = document.getElementById('auto-date');
    if (datePicker) {
      datePicker.value = localDateStr();
    }

    var consoleLink = document.getElementById('dept-modal-open-console-link');
    if (consoleLink && !consoleLink.dataset.consoleBound) {
      consoleLink.dataset.consoleBound = '1';
      consoleLink.addEventListener('click', function (ev) {
        if (window.isConsoleScope && window.isConsoleScope()) {
          ev.preventDefault();
          window.closeDepartmentLoginModal();
          if (typeof window.showDashboard === 'function') {
            window.showDashboard();
          }
        }
      });
    }

    if (consolePollTimer) {
      clearInterval(consolePollTimer);
      consolePollTimer = null;
    }

    var authed = await window.checkServerSessionStatus();

    consolePollTimer = setInterval(function () {
      if (window.isPortalAuthenticated) {
        window.checkServerSessionStatus();
      }
    }, 15000);

    return authed;
  };

  window.stopConsoleSessionPolling = function () {
    if (consolePollTimer) {
      clearInterval(consolePollTimer);
      consolePollTimer = null;
    }
    if (genProgressInterval) {
      clearInterval(genProgressInterval);
      genProgressInterval = null;
    }
    if (deptAutoCloseTimer) {
      clearTimeout(deptAutoCloseTimer);
      deptAutoCloseTimer = null;
    }
    clearStepTimeouts();
    deptLoginInProgress = false;
  };

  // ---------------------------------------------------------------------------
  // Stage 2 Departmental Browser Status & Auth State
  // ---------------------------------------------------------------------------

  window.updateTimerDisplay = function () {
    var wrap = document.getElementById('nav-session-timer-wrap');
    var btn = document.getElementById('btn-extend-session');
    var dashBtn = document.getElementById('dash-btn-extend');
    var navTimer = document.getElementById('nav-session-timer');
    var dashTimerChip = document.getElementById('dash-timer-chip');

    var isAuth = false;
    try { isAuth = sessionStorage.getItem('epts_portal_auth') === 'true'; } catch (e) {}
    if (!isAuth) {
      if (wrap) wrap.style.display = 'none';
      return;
    }

    if (wrap) wrap.style.display = 'inline-flex';
    if (btn) btn.style.display = 'none';
    if (dashBtn) dashBtn.style.display = 'none';

    if (navTimer) {
      navTimer.style.background = 'rgba(16, 185, 129, 0.25)';
      navTimer.style.borderColor = '#10b981';
      navTimer.style.color = '#d1fae5';
      navTimer.innerHTML = '🛡️ <span style="font-weight:700;">No Expiry</span>';
      navTimer.title = 'Persistent session: No time restriction';
    }
    if (dashTimerChip) {
      dashTimerChip.innerHTML = '🛡️ Session: <span style="font-weight:700; color:#34d399;">Persistent (No Expiry)</span>';
      dashTimerChip.style.borderColor = '#10b981';
    }
  };

  window.startSessionTimer = function () {
    window.sessionNoExpiry = true;
    window.sessionExpiresIn = 999999;
    window.sessionCanExtend = false;
    if (window.sessionTimerInterval) {
      clearInterval(window.sessionTimerInterval);
      window.sessionTimerInterval = null;
    }
    window.updateTimerDisplay();
  };

  window.extendPortalSession = async function () {
    try {
      await fetch('/api/naresh/extend-session', { method: 'POST' });
    } catch (e) {}
    window.sessionExpiresIn = 999999;
    window.sessionNoExpiry = true;
    window.sessionCanExtend = false;
    window.updateTimerDisplay();
    showNotice('Departmental background browser session remains persistent while open.', 'success');
  };

  window.updateGlobalBrowserStatus = function (data) {
    var ping = document.getElementById('browser-status-ping');
    var dot = document.getElementById('browser-status-dot');
    var pill = document.getElementById('browser-status-pill');
    var desc = document.getElementById('browser-status-desc');
    var officerEl = document.getElementById('browser-status-officer');
    var deptDot = document.getElementById('nav-dept-login-dot');
    var deptText = document.getElementById('nav-dept-login-text');
    var navDot = document.getElementById('nav-browser-dot');
    var navText = document.getElementById('nav-browser-text');
    var deptBtn = document.getElementById('nav-btn-dept-login');

    if (data && data.authenticated) {
      var off = '';
      try { off = sessionStorage.getItem('epts_officer_id') || ''; } catch (e) {}
      off = String(data.user_id || off || 'Officer').trim();
      window.isDeptAuthenticated = true;
      try { sessionStorage.setItem('epts_dept_session', 'true'); } catch (e) {}
      if (deptDot) {
        deptDot.style.background = '#10b981';
        deptDot.style.boxShadow = '0 0 8px #10b981';
      }
      var savedDist = '';
      var savedOffice = '';
      try {
        savedDist = sessionStorage.getItem('epts_district_name') || '';
        savedOffice = sessionStorage.getItem('epts_office_name') || '';
      } catch (e) {}
      var dist = String(data.district_name || savedDist || '').trim();
      var officeName = String(data.office_name || savedOffice || '').trim();

      if (deptText) deptText.textContent = 'Active: ' + off;
      if (deptBtn) {
        deptBtn.style.background = 'linear-gradient(135deg, #065f46, #047857)';
        deptBtn.title = 'e-Panchayat Session Active (' + off + (dist ? ' · ' + dist : '') + ')';
      }

      if (ping) { ping.style.display = 'inline-block'; ping.style.background = '#10b981'; }
      if (dot) dot.style.background = '#10b981';
      if (pill) {
        pill.style.background = '#10b981';
        pill.style.color = '#064e3b';
        pill.textContent = 'ACTIVE · PERSISTENT';
      }
      if (desc) {
        desc.textContent = 'Connected to ' + (officeName || dist || 'e-Panchayat Portal') + ' for zero-wait reports.';
      }
      if (officerEl) {
        officerEl.textContent = dist ? ('🏛️ ' + dist) : '';
        officerEl.style.display = dist ? 'inline-flex' : 'none';
      }
      if (navDot) navDot.style.background = '#10b981';
      if (navText) navText.textContent = dist ? ('Browser: ' + dist) : ('Browser: Active (' + off + ')');
    } else if (data && data.status === 'awaiting_otp') {
      var pendingOff = String(data.user_id || 'Officer').trim();
      if (ping) { ping.style.display = 'inline-block'; ping.style.background = '#f59e0b'; }
      if (dot) dot.style.background = '#f59e0b';
      if (pill) {
        pill.style.background = '#f59e0b';
        pill.style.color = '#78350f';
        pill.textContent = 'AWAITING 6-DIGIT OTP';
      }
      if (desc) {
        desc.textContent = 'e-Panchayat login in progress. Awaiting 6-digit OTP verification for Officer ' + pendingOff + '.';
      }
      if (officerEl) {
        officerEl.style.display = 'inline-flex';
        officerEl.textContent = '📱 Awaiting OTP (' + pendingOff + ')';
      }
      if (navDot) navDot.style.background = '#f59e0b';
      if (navText) navText.textContent = 'Browser: Awaiting OTP';
    } else {
      if (ping) ping.style.display = 'none';
      if (dot) dot.style.background = '#9ca3af';
      if (pill) {
        pill.style.background = data && data.status === 'expired' ? '#fef3c7' : 'rgba(255,255,255,0.15)';
        pill.style.color = data && data.status === 'expired' ? '#92400e' : '#e2e8f0';
        pill.textContent = data && data.status === 'expired' ? 'SESSION EXPIRED · RE-LOGIN' : 'STANDBY · NOT LOGGED IN';
      }
      if (desc) {
        desc.textContent = data && data.status === 'expired'
          ? 'Your Department Login session has expired. Click "Department Login" or any module to re-connect once.'
          : 'e-Panchayat Automation browser engine ready. Click "Department Login" to connect and authenticate.';
      }
      if (officerEl) {
        officerEl.style.display = 'inline-flex';
        officerEl.textContent = '🔒 Login Required';
      }
      if (deptDot) {
        deptDot.style.background = '#fcd34d';
        deptDot.style.boxShadow = 'none';
      }
      if (deptText) deptText.textContent = 'Department Login';
      if (deptBtn) {
        deptBtn.style.background = 'linear-gradient(135deg, #059669, #047857)';
        deptBtn.title = 'Click to connect official e-Panchayat Departmental Login';
      }
      if (navDot) navDot.style.background = '#9ca3af';
      if (navText) navText.textContent = 'Department Login';
    }
  };

  function setAuthenticated(isAuth, userId, sessionInfo, isExpired) {
    var dpoaFreshWrap = document.getElementById('dpoa-fresh-toggle-wrap');
    var btnSessions = document.getElementById('btn-active-sessions');
    var navPill = document.getElementById('nav-browser-pill');
    var btnDisconn = document.getElementById('nav-btn-disconnect-epts');
    var dashBadge = document.getElementById('dash-session-badge');
    var officerBanner = document.getElementById('dash-officer-banner');
    var dashOffId = document.getElementById('dash-officer-id');
    var sessionBadge = document.getElementById('session-badge');

    if (isAuth) {
      var savedOfficer = '';
      var savedLevel = '';
      var savedMandal = '';
      var savedDistrict = '';
      var savedOffice = '';
      try {
        savedOfficer = sessionStorage.getItem('epts_officer_id') || '';
        savedLevel = sessionStorage.getItem('epts_user_level') || '';
        savedMandal = sessionStorage.getItem('epts_mandal_name') || '';
        savedDistrict = sessionStorage.getItem('epts_district_name') || '';
        savedOffice = sessionStorage.getItem('epts_office_name') || '';
      } catch (e) {}

      var officer = String(userId || savedOfficer || 'Officer').trim();
      var uLevel = String((sessionInfo && sessionInfo.user_level) || (userId ? 'district' : savedLevel) || 'district').trim();

      // If switching officers or if user level changed, wipe previous cached reports and mandal state immediately
      var officerChanged = Boolean(savedOfficer && officer && savedOfficer.toLowerCase() !== officer.toLowerCase());
      if (officerChanged) {
        savedMandal = '';
        reportData = null;
        ['results-section', 'state-format-results', 'auto-multi-results-section', 'inspections-results-card', 'balance-results-card'].forEach(function (id) {
          var el = document.getElementById(id);
          if (el) el.style.display = 'none';
        });
      }

      var mName = '';
      if (uLevel === 'mandal') {
        mName = String((sessionInfo && sessionInfo.mandal_name) || savedMandal || '').trim();
      }

      var dName = String((sessionInfo && sessionInfo.district_name) || savedDistrict || '').trim();
      var oName = String((sessionInfo && sessionInfo.office_name) || savedOffice || '').trim();

      window.isDeptAuthenticated = true;
      window.currentUserLevel = uLevel;
      window.currentMandalName = mName;
      window.currentDistrictName = dName;

      try {
        sessionStorage.setItem('epts_portal_auth', 'true');
        sessionStorage.setItem('epts_dept_session', 'true');
        sessionStorage.setItem('epts_officer_id', officer);
        sessionStorage.setItem('epts_user_level', uLevel);
        if (mName) {
          sessionStorage.setItem('epts_mandal_name', mName);
        } else {
          sessionStorage.removeItem('epts_mandal_name');
        }
        if (dName) sessionStorage.setItem('epts_district_name', dName);
        if (oName) sessionStorage.setItem('epts_office_name', oName);
      } catch (e) {}

      window.updateOfficerBadge(officer);
      window.updateTimerDisplay();
      window.updateGlobalBrowserStatus({
        authenticated: true,
        user_id: officer,
        user_level: uLevel,
        mandal_name: mName,
        district_name: dName,
        office_name: oName,
      });

      if (dashBadge) {
        if (uLevel === 'mandal') {
          dashBadge.textContent = '🏛️ ' + (mName || 'Mandal') + ' Level';
        } else if (uLevel === 'division') {
          dashBadge.textContent = '🏢 ' + ((sessionInfo && sessionInfo.division_name) || 'Division') + ' Level';
        } else {
          dashBadge.textContent = '🟢 EPTS Connected';
        }
      }

      var roleHeadline = document.getElementById('dash-role-headline');
      var roleSubtext = document.getElementById('dash-role-subtext');
      if (roleHeadline && roleSubtext) {
        if (uLevel === 'mandal') {
          roleHeadline.textContent = 'Active Operational Level: Mandal Level (' + (mName || 'Mandal') + ')';
          roleSubtext.textContent = 'Focused Gram Panchayat reports active. Multi-mandal abstract comparison suppressed.';
        } else if (uLevel === 'division') {
          roleHeadline.textContent = 'Active Operational Level: Divisional Level (' + ((sessionInfo && sessionInfo.division_name) || 'Division') + ')';
          roleSubtext.textContent = 'Divisional multi-mandal monitoring and Gram Panchayat drill-downs enabled.';
        } else {
          roleHeadline.textContent = 'Active Operational Level: District Level (' + dName + ')';
          roleSubtext.textContent = 'District-wide Mandal comparative analytics and Gram Panchayat drill-downs enabled.';
        }
      }

      if (dashOffId) {
        dashOffId.textContent = officer + (uLevel === 'mandal' && mName ? ' (' + mName + ' Mandal)' : '');
      }
      if (sessionBadge) {
        sessionBadge.textContent = 'Officer: ' + officer + ' (' + uLevel.toUpperCase() + ') Active';
      }
      if (officerBanner) {
        officerBanner.style.display = 'none';
      }

      if (dpoaFreshWrap) dpoaFreshWrap.style.display = 'none';
      if (btnSessions) btnSessions.style.display = 'none';
      if (navPill) {
        navPill.style.cursor = 'default';
        navPill.onclick = null;
        navPill.title = 'Background browser engine status';
      }
      if (btnDisconn) btnDisconn.style.display = 'inline-flex';

      var nav1 = document.getElementById('step-nav-1');
      var nav2 = document.getElementById('step-nav-2');
      var line1 = document.getElementById('line-1');
      var line2 = document.getElementById('line-2');
      if (nav1) nav1.classList.add('completed');
      if (nav2) nav2.classList.add('completed');
      if (line1) line1.classList.add('active');
      if (line2) line2.classList.add('active');
    } else {
      if (window.sessionTimerInterval) {
        clearInterval(window.sessionTimerInterval);
        window.sessionTimerInterval = null;
      }
      window.isDeptAuthenticated = false;
      clearEptsStorageOnly();

      var timerWrap = document.getElementById('nav-session-timer-wrap');
      if (timerWrap) timerWrap.style.display = 'none';
      if (dpoaFreshWrap) dpoaFreshWrap.style.display = 'none';
      if (btnSessions) btnSessions.style.display = 'none';
      if (navPill) {
        navPill.style.cursor = 'default';
        navPill.onclick = null;
        navPill.title = 'Background browser engine status';
      }
      if (btnDisconn) btnDisconn.style.display = 'none';
      if (officerBanner) officerBanner.style.display = 'none';
      if (dashBadge) {
        if (window.currentWorkspaceMode === 'manual') {
          dashBadge.textContent = '📊 Manual Reports Mode';
        } else if (window.currentWorkspaceMode === 'automated') {
          dashBadge.textContent = '⚡ Automated Reports Console Mode';
        } else if (window.currentWorkspaceMode === 'tools') {
          dashBadge.textContent = '🧰 Tools & Utilities Studio';
        } else {
          dashBadge.textContent = '🟢 Choose Reporting Mode';
        }
      }
      if (sessionBadge) sessionBadge.textContent = 'Session: Ready';

      window.updateGlobalBrowserStatus({ authenticated: false, status: isExpired ? 'expired' : 'idle' });

      // Never hide #post-login-dashboard or yank user out of dashboard/admin/tax/inspections
      if (window.isPortalAuthenticated && (isVisibleBlock('automation-station') || isVisibleBlock('balance-station'))) {
        if (typeof window.showDashboard === 'function') {
          window.showDashboard();
        }
      }
    }
  }

  function renderDeptModalOtpPrompt(otpMessage, mobileNumber) {
    var mob = String(mobileNumber || 'registered mobile').trim();
    var msgP = otpMsgEl();
    if (msgP) {
      var noticeStr = String(
        otpMessage || ('A 6 digit OTP has been sent to your registered mobile number ' + mob + '. Enter OTP to continue.')
      );
      if (mob && noticeStr.indexOf(mob) !== -1) {
        var idx = noticeStr.indexOf(mob);
        msgP.innerHTML =
          esc(noticeStr.slice(0, idx)) +
          '<strong id="dept-modal-mobile-span">' + esc(mob) + '</strong>' +
          esc(noticeStr.slice(idx + mob.length));
      } else {
        msgP.innerHTML = esc(noticeStr) + ' <strong id="dept-modal-mobile-span">' + esc(mob) + '</strong>';
      }
    } else if (mobSpanEl()) {
      mobSpanEl().textContent = mob;
    }
  }

  window.checkServerSessionStatus = async function () {
    try {
      var verified = null;
      var data = {};
      if (window.DeptSessionManager && typeof window.DeptSessionManager.verifyStatus === 'function') {
        verified = await window.DeptSessionManager.verifyStatus();
        lastDeptVerifyResult = verified;
        data = verified.data || {};
        if (!verified.ok) {
          setAuthenticated(false, '', null, Boolean(verified.expired));
          return false;
        }
      } else {
        var mySid = typeof window.getEptsSessionId === 'function' ? window.getEptsSessionId() : '';
        var res = await fetch('/api/naresh/session-status?_ts=' + Date.now(), {
          cache: 'no-store',
          headers: mySid ? { 'X-Session-ID': mySid } : {},
        });
        if (!res.ok) {
          setAuthenticated(false, '', null, false);
          return false;
        }
        data = await res.json();
        if (data && data.session_id && mySid && data.session_id !== mySid) {
          return false;
        }
        lastDeptVerifyResult = {
          ok: true,
          authenticated: Boolean(data && data.authenticated),
          expired: Boolean(data && (data.expired || data.status === 'expired')),
          status: (data && data.status) || 'idle',
          user_id: (data && data.user_id) || '',
          data: data,
        };
      }

      window.updateGlobalBrowserStatus(data);

      if (data && data.authenticated) {
        deptLoginInProgress = false;
        var savedOff = '';
        try { savedOff = sessionStorage.getItem('epts_officer_id') || ''; } catch (e) {}
        var officer = data.user_id || savedOff || 'Officer';
        window.sessionNoExpiry = true;
        window.sessionExpiresIn = 999999;
        window.sessionCanExtend = false;
        if (window.sessionTimerInterval) {
          clearInterval(window.sessionTimerInterval);
          window.sessionTimerInterval = null;
        }
        setAuthenticated(true, officer, data);
        return true;
      }

      if (data && data.status === 'awaiting_otp') {
        var otpOff = data.user_id || 'Officer';
        window.updateOfficerBadge(otpOff);
        var badge = document.getElementById('session-badge');
        if (badge) badge.textContent = 'Officer: ' + otpOff + ' (Awaiting OTP)';
        if (data.otp_message || data.mobile_number) {
          window.displayOtpNotice(data.otp_message, data.mobile_number);
        }

        // Only open/switch the OTP modal if login was initiated or modal/station is already open
        var modalEl = document.getElementById('dept-login-modal');
        var modalOpen = modalEl && modalEl.style.display === 'flex';
        if (deptLoginInProgress || modalOpen) {
          renderDeptModalOtpPrompt(data.otp_message, data.mobile_number);
          if (!modalOpen && modalEl) {
            modalEl.style.display = 'flex';
          }
          window.switchDeptModalStep(2);
        } else if (isVisibleBlock('automation-station') && currentStep !== 2) {
          window.goToStep(2);
        }
        return false;
      }

      var wasExpired = Boolean(data && (data.expired || data.status === 'expired'));
      setAuthenticated(false, '', null, wasExpired);
      return false;
    } catch (e) {
      window.updateGlobalBrowserStatus({ authenticated: false, status: 'idle' });
      return false;
    }
  };

  function mobSpanEl() {
    return document.getElementById('dept-modal-mobile-span');
  }

  function otpMsgEl() {
    return document.getElementById('dept-modal-otp-msg');
  }

  // ---------------------------------------------------------------------------
  // Stage 2 Departmental Login Modal
  // ---------------------------------------------------------------------------

  function captureModuleParams(moduleName, overrideParams) {
    var mod = String(moduleName || '').trim().toLowerCase();
    var merged = {};
    if (mod === 'dsr') {
      var modEl = document.getElementById('auto-module');
      var dateEl = document.getElementById('auto-date');
      var cutoffEl = document.getElementById('auto-cutoff-time');
      var sortEl = document.getElementById('auto-sort-by');
      var layoutEl = document.getElementById('auto-page-layout');
      var freshEl = document.getElementById('chk-force-fresh');
      merged.auto_module = (modEl && modEl.value) || 'dsr_full';
      merged.auto_date = (dateEl && dateEl.value) || localDateStr();
      merged.cutoff_time = (cutoffEl && cutoffEl.value) || '09:00';
      merged.sort_by = (sortEl && sortEl.value) || 'before_9';
      merged.page_layout = (layoutEl && layoutEl.value) || 'individual';
      merged.include_sections = getSelectedDsrSectionsValue();
      merged.force_fresh = Boolean(freshEl && freshEl.checked);
    } else if (mod === 'balance') {
      var balEl = document.getElementById('balance-date-select');
      var pmagyEl = document.getElementById('chk-balance-include-pmagy');
      if (balEl && balEl.value) merged.balance_date = balEl.value;
      merged.include_pmagy = Boolean(pmagyEl && pmagyEl.checked);
    } else if (mod === 'tax-dcb') {
      var dEl = document.getElementById('tax-district-select');
      var mEl = document.getElementById('tax-mandal-select');
      if (dEl && dEl.value) merged.district = dEl.value;
      if (mEl && mEl.value) merged.mandal = mEl.value;
    } else if (mod === 'inspections') {
      var desEl = document.getElementById('insp-designation');
      var fwEl = document.getElementById('insp-from-week');
      var twEl = document.getElementById('insp-to-week');
      if (desEl && desEl.value) merged.designation = desEl.value;
      if (fwEl && fwEl.value) merged.from_week = fwEl.value;
      if (twEl && twEl.value) merged.to_week = twEl.value;
    } else if (mod === 'auto-multi-dsr' || mod === 'auto-multiday') {
      var sEl = document.getElementById('auto-multi-start-date');
      var eEl = document.getElementById('auto-multi-end-date');
      if (sEl && sEl.value) merged.start_date = sEl.value;
      if (eEl && eEl.value) merged.end_date = eEl.value;
    }
    if (overrideParams && typeof overrideParams === 'object') {
      Object.keys(overrideParams).forEach(function (k) {
        if (overrideParams[k] !== undefined && overrideParams[k] !== null && overrideParams[k] !== '') {
          merged[k] = overrideParams[k];
        }
      });
    }
    return merged;
  }

  function applyDsrParams(params) {
    if (!params || typeof params !== 'object') return;
    var modEl = document.getElementById('auto-module');
    var dateEl = document.getElementById('auto-date');
    var cutoffEl = document.getElementById('auto-cutoff-time');
    var sortEl = document.getElementById('auto-sort-by');
    var layoutEl = document.getElementById('auto-page-layout');
    var freshEl = document.getElementById('chk-force-fresh');
    if (modEl && params.auto_module) modEl.value = params.auto_module;
    if (dateEl) {
      dateEl.value = params.auto_date || params.date || dateEl.value || localDateStr();
    }
    if (cutoffEl && params.cutoff_time) {
      cutoffEl.value = params.cutoff_time;
      window.updateCutoffLabelInUi(params.cutoff_time);
    }
    if (sortEl && params.sort_by) sortEl.value = params.sort_by;
    if (layoutEl && params.page_layout) layoutEl.value = params.page_layout;
    if (params.include_sections) applyDsrSectionsSelection(params.include_sections);
    if (freshEl && params.force_fresh !== undefined) {
      freshEl.checked = params.force_fresh === true || params.force_fresh === 'true' || params.force_fresh === '1';
    }
  }

  function normalizePendingTarget(pendingTargetOrObj) {
    if (!pendingTargetOrObj) return null;
    if (typeof pendingTargetOrObj === 'string') {
      return {
        module: pendingTargetOrObj.trim().toLowerCase(),
        autoGenerate: false,
        reason: (lastDeptVerifyResult && lastDeptVerifyResult.expired) ? 'expired' : 'required',
        params: captureModuleParams(pendingTargetOrObj),
      };
    }
    if (typeof pendingTargetOrObj === 'object' && pendingTargetOrObj.module) {
      return {
        module: String(pendingTargetOrObj.module).trim().toLowerCase(),
        returnUrl: pendingTargetOrObj.returnUrl || '',
        autoGenerate: pendingTargetOrObj.autoGenerate === true,
        reason: pendingTargetOrObj.reason || 'required',
        params: pendingTargetOrObj.params || captureModuleParams(pendingTargetOrObj.module),
      };
    }
    return null;
  }

  window.ensureDepartmentSession = async function (moduleName, options) {
    var opts = options || {};
    var params = captureModuleParams(moduleName, opts.params);
    var isAuthed = await window.checkServerSessionStatus();
    if (isAuthed) {
      return true;
    }

    var expired = Boolean(lastDeptVerifyResult && lastDeptVerifyResult.expired);
    var pending = {
      module: String(moduleName || '').trim().toLowerCase(),
      returnUrl: opts.returnUrl || '',
      autoGenerate: opts.autoGenerate === true,
      reason: expired ? 'expired' : 'required',
      params: params,
    };

    if (window.DeptSessionManager) {
      window.DeptSessionManager.savePendingAction(pending);
    }
    var noticeText = expired
      ? 'Department Login session has expired. Please authenticate once, then select your report options.'
      : 'Department Login & OTP is required to access automated reports.';
    showNotice(noticeText, 'info');
    window.openDepartmentLoginModal(pending);
    return false;
  };

  function handleDepartmentSessionExpiredError(err, moduleName, overrideParams) {
    var msg = String((err && err.message) || '');
    var lower = msg.toLowerCase();
    var isAuthErr = Boolean(
      (err && (err.status === 401 || err.deptAuthRequired)) ||
      lower.indexOf('login') !== -1 ||
      lower.indexOf('otp') !== -1 ||
      lower.indexOf('expired') !== -1
    );
    if (!isAuthErr) return false;

    setAuthenticated(false);
    var pending = {
      module: String(moduleName || '').trim().toLowerCase(),
      autoGenerate: false,
      reason: 'expired',
      params: captureModuleParams(moduleName, overrideParams),
    };
    if (window.DeptSessionManager) {
      window.DeptSessionManager.savePendingAction(pending);
    }
    window.openDepartmentLoginModal(pending);
    return true;
  }

  window.resumePendingDepartmentAction = async function (pending) {
    if (!pending || !pending.module) return false;
    var mod = String(pending.module).trim().toLowerCase();
    var params = pending.params || {};
    var autoGen = pending.autoGenerate === true;

    if (mod === 'balance' || mod === 'balance-station') {
      await window.openBalanceRobot({
        skipAuthCheck: true,
        autoGenerate: autoGen,
        params: params,
      });
      return true;
    }
    if (mod === 'dsr') {
      await window.openDsrRobot({
        skipAuthCheck: true,
        autoGenerate: autoGen,
        params: params,
      });
      return true;
    }
    if (mod === 'tax-dcb' || mod === 'tax' || mod === 'tax-station') {
      if (pending.returnUrl) {
        window.location.href = pending.returnUrl;
        return true;
      }
      await window.openTaxDcbStation({
        skipAuthCheck: true,
        autoGenerate: autoGen,
        params: params,
      });
      return true;
    }
    if (mod === 'mas' || mod === 'mas-consolidated') {
      window.location.href = pending.returnUrl || window.getMasWorkspaceUrl(params, autoGen);
      return true;
    }
    if (mod === 'inspections') {
      await window.openGpInspectionsStation({
        skipAuthCheck: true,
        autoGenerate: autoGen,
        params: params,
      });
      return true;
    }
    if (mod === 'auto-multi-dsr' || mod === 'auto-multiday' || mod === 'auto-multi') {
      await window.openAutoMultiDsrStation({
        skipAuthCheck: true,
        autoGenerate: autoGen,
        params: params,
      });
      return true;
    }
    return false;
  };

  window.handleNavDeptLoginClick = function () {
    window.openDepartmentLoginModal();
  };

  window.openDepartmentLoginModal = function (pendingTarget) {
    var pendingObj = normalizePendingTarget(pendingTarget);
    if (pendingObj) {
      window.pendingStation = pendingObj.module;
      if (window.DeptSessionManager) {
        window.DeptSessionManager.savePendingAction(pendingObj);
      }
    }
    var modal = document.getElementById('dept-login-modal');
    if (!modal) return;

    if (deptAutoCloseTimer) {
      clearTimeout(deptAutoCloseTimer);
      deptAutoCloseTimer = null;
    }

    var isDeptAuth = window.isDeptAuthenticated === true;
    try {
      isDeptAuth = isDeptAuth || sessionStorage.getItem('epts_dept_session') === 'true';
    } catch (e) {}

    if (isDeptAuth) {
      var off = 'Officer';
      try { off = sessionStorage.getItem('epts_officer_id') || 'Officer'; } catch (e) {}
      var succMsg = document.getElementById('dept-modal-success-msg');
      if (succMsg) {
        succMsg.textContent = 'Official e-Panchayat session active for Officer ' + off + '. Background automation engine is ready.';
      }
      window.switchDeptModalStep('success');
    } else {
      resetDeptLoginProgress();
      window.switchDeptModalStep(1);
      if (pendingObj && pendingObj.reason === 'expired') {
        showModalAlert('dept-modal-alert-1', 'Your Department Login session has expired. Authenticate once, then select your report options.', true);
      } else if (pendingObj && pendingObj.module) {
        showModalAlert('dept-modal-alert-1', 'Complete Department Login once to unlock all modules, then choose your options and generate your report.', false);
      }
    }

    modal.style.display = 'flex';
    var userInp = document.getElementById('dept-modal-user');
    if (userInp) userInp.value = '';
    var pwdInp = document.getElementById('dept-modal-pwd');
    if (pwdInp) pwdInp.value = '';
  };

  window.openDepartmentLogin = function (pendingTarget) {
    window.openDepartmentLoginModal(pendingTarget);
  };
  window.showLoginStation = window.openDepartmentLoginModal;

  function renderDeptLoginProgress(logs, elapsedSec, fallbackLabel) {
    var box = document.getElementById('dept-modal-live-progress');
    var list = document.getElementById('dept-modal-progress-list');
    var elapsedEl = document.getElementById('dept-modal-progress-elapsed');
    if (box) box.style.display = 'block';
    if (elapsedEl) elapsedEl.textContent = (elapsedSec || 0) + 's';
    if (!list) return;

    if (!logs || !logs.length) {
      var initLabel = String(fallbackLabel || 'Opening Browser').replace(/\.\.\.+$/, '');
      list.innerHTML = '<div style="color:#0f766e; font-weight:700;">⏳ ' + esc(initLabel) + '...</div>';
      return;
    }

    list.innerHTML = logs.map(function (item) {
      var st = item.status || 'done';
      var icon = st === 'done' ? '✓' : (st === 'error' ? '✕' : '⏳');
      var color = st === 'done' ? '#047857' : (st === 'error' ? '#dc2626' : '#0f766e');
      var weight = st === 'active' ? '800' : (st === 'error' ? '700' : '600');
      var cleanTxt = String(item.text || '').replace(/\.\.\.+$/, '');
      var suffix = st === 'active' ? '...' : '';
      return '<div style="color:' + color + '; font-weight:' + weight + ';">' + icon + ' ' + esc(cleanTxt) + suffix + '</div>';
    }).join('');
    list.scrollTop = list.scrollHeight;
  }

  function resetDeptLoginProgress() {
    var box = document.getElementById('dept-modal-live-progress');
    var list = document.getElementById('dept-modal-progress-list');
    var elapsedEl = document.getElementById('dept-modal-progress-elapsed');
    if (box) box.style.display = 'none';
    if (list) list.innerHTML = '';
    if (elapsedEl) elapsedEl.textContent = '0s';
  }

  function _isOnConsoleRouteOrHost() {
    try {
      if (typeof window.isReportsHost === 'function' && window.isReportsHost()) return true;
      var path = (window.location.pathname || '').toLowerCase();
      if (
        path === '/autoreports' ||
        path === '/eptauto' ||
        path === '/naresh' ||
        path === '/mas' ||
        path.indexOf('/reports') === 0
      ) {
        return true;
      }
      var sp = new URLSearchParams(window.location.search || '');
      var site = (sp.get('site') || '').trim().toLowerCase();
      var mode = (sp.get('mode') || '').trim().toLowerCase();
      if (
        site === 'console' ||
        site === 'reports' ||
        mode === 'automated' ||
        sp.get('dept_login') === '1' ||
        Boolean(sp.get('pending_module'))
      ) {
        return true;
      }
    } catch (e) {}
    return false;
  }

  window.closeDepartmentLoginModal = function (options) {
    if (deptAutoCloseTimer) {
      clearTimeout(deptAutoCloseTimer);
      deptAutoCloseTimer = null;
    }
    clearDeptCredentialInputs();
    resetDeptLoginProgress();
    var modal = document.getElementById('dept-login-modal');
    if (modal) modal.style.display = 'none';

    var allowStay = Boolean(options && options.allowStay === true);
    var isDeptAuth = window.isDeptAuthenticated === true;
    try {
      isDeptAuth = isDeptAuth || sessionStorage.getItem('epts_dept_session') === 'true';
    } catch (e) {}

    if (allowStay || isDeptAuth) {
      return;
    }

    // Never expose or stay inside the Automation Console when Department Login is dismissed unauthenticated
    window.pendingStation = null;
    if (window.DeptSessionManager && typeof window.DeptSessionManager.consumePendingAction === 'function') {
      window.DeptSessionManager.consumePendingAction();
    }
    window.currentWorkspaceMode = null;
    try { sessionStorage.removeItem('epts_workspace_mode'); } catch (e) {}

    var consoleSec = document.getElementById('console-modules-section');
    var globalBar = document.getElementById('global-browser-status-bar');
    if (consoleSec) consoleSec.style.display = 'none';
    if (globalBar) globalBar.style.display = 'none';

    if (_isOnConsoleRouteOrHost()) {
      var dash = document.getElementById('post-login-dashboard');
      if (dash) dash.style.display = 'none';
      var homeUrl = (typeof window.getSectionUrl === 'function')
        ? window.getSectionUrl('home')
        : ((typeof window.isProdCustomDomain === 'function' && window.isProdCustomDomain()) ? 'https://panchayatautomation.in/' : '/');
      window.location.replace(homeUrl);
      return;
    }

    if (typeof window.showWorkspaceModeSelector === 'function') {
      window.showWorkspaceModeSelector();
    }
  };

  window.switchDeptModalStep = function (step) {
    var s1 = document.getElementById('dept-modal-step-1');
    var s2 = document.getElementById('dept-modal-step-2');
    var sSuccess = document.getElementById('dept-modal-step-success');
    if (s1) s1.style.display = step === 1 ? 'block' : 'none';
    if (s2) s2.style.display = step === 2 ? 'block' : 'none';
    if (sSuccess) sSuccess.style.display = step === 'success' ? 'block' : 'none';

    showModalAlert('dept-modal-alert-1', '');
    showModalAlert('dept-modal-alert-2', '');
  };

  function _deptFetch(url, options) {
    if (window.DeptSessionManager && typeof window.DeptSessionManager.consoleFetch === 'function') {
      return window.DeptSessionManager.consoleFetch(url, options);
    }
    var opts = options ? Object.assign({}, options) : {};
    var headers = new Headers(opts.headers || {});
    var sid = typeof window.getEptsSessionId === 'function' ? window.getEptsSessionId() : '';
    if (sid && !headers.has('X-Session-ID')) headers.set('X-Session-ID', sid);
    opts.headers = headers;
    if (!opts.credentials) opts.credentials = 'same-origin';
    return fetch(url, opts);
  }

  window.toggleDeptModalPwdVisibility = function () {
    var p = document.getElementById('dept-modal-pwd');
    if (!p) return;
    p.type = p.type === 'password' ? 'text' : 'password';
  };

  window.handleDeptModalCredsSubmit = async function (event) {
    if (event) event.preventDefault();
    var user = ((document.getElementById('dept-modal-user') && document.getElementById('dept-modal-user').value) || '').trim();
    var pwd = ((document.getElementById('dept-modal-pwd') && document.getElementById('dept-modal-pwd').value) || '').trim();
    var btn = document.getElementById('btn-dept-modal-login');
    var btnText = document.getElementById('btn-dept-modal-login-text');

    if (!user || !pwd) {
      showModalAlert('dept-modal-alert-1', 'Please enter both User ID and Password.', true);
      return;
    }

    deptLoginInProgress = true;
    if (btn) btn.disabled = true;
    var elapsedSec = 0;
    var latestLogs = [];
    var latestButtonStep = 'Opening Browser...';
    if (btnText) btnText.textContent = latestButtonStep;
    showModalAlert('dept-modal-alert-1', '');
    renderDeptLoginProgress([], 0, 'Opening Browser');

    var waitTimer = setInterval(function () {
      elapsedSec += 1;
      if (btnText) btnText.textContent = latestButtonStep + ' (' + elapsedSec + 's)';
      renderDeptLoginProgress(latestLogs, elapsedSec, latestButtonStep);
    }, 1000);

    var progressPoller = setInterval(async function () {
      try {
        var pResp = await _deptFetch('/api/naresh/login-progress?_ts=' + Date.now(), { cache: 'no-store' });
        if (!pResp.ok) return;
        var pData = await pResp.json().catch(function () { return null; });
        if (pData && Array.isArray(pData.logs) && pData.logs.length) {
          latestLogs = pData.logs;
          if (pData.current) {
            var curText = String(pData.current).replace(/^\[[*+\-!]\]\s*/, '').replace(/\.\.\.+$/, '');
            latestButtonStep = curText + (pData.done || pData.error ? '' : '...');
            if (latestButtonStep.length > 48) latestButtonStep = latestButtonStep.slice(0, 45) + '...';
          }
          renderDeptLoginProgress(latestLogs, Math.max(elapsedSec, pData.elapsed || 0), latestButtonStep);
        }
      } catch (e) {}
    }, 450);

    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var abortTimer = controller ? setTimeout(function () { controller.abort(); }, 75000) : null;

    try {
      var formData = new FormData();
      formData.append('username', user);
      formData.append('password', pwd);

      var fetchOpts = { method: 'POST', body: formData };
      if (controller) fetchOpts.signal = controller.signal;
      var res = await _deptFetch('/api/naresh/login', fetchOpts);
      var rawText = await res.text().catch(function () { return ''; });
      var data = {};
      if (rawText) {
        try { data = JSON.parse(rawText); } catch (e) { data = {}; }
      }

      if (res.ok && (data.success || data.step === 'otp_required')) {
        resetDeptLoginProgress();
        try { sessionStorage.setItem('epts_officer_id', user); } catch (e) {}
        var pwdEl = document.getElementById('dept-modal-pwd');
        if (pwdEl) pwdEl.value = '';
        renderDeptModalOtpPrompt(data.otp_message, data.mobile_number);
        window.switchDeptModalStep(2);
        var otpInput = document.getElementById('dept-modal-otp-input');
        if (otpInput) {
          otpInput.value = '';
          setTimeout(function () { otpInput.focus(); }, 150);
        }
      } else {
        deptLoginInProgress = false;
        var lastProgErr = '';
        if (Array.isArray(latestLogs)) {
          for (var li = latestLogs.length - 1; li >= 0; li--) {
            if (latestLogs[li] && latestLogs[li].status === 'error' && latestLogs[li].text) {
              lastProgErr = String(latestLogs[li].text);
              break;
            }
          }
        }
        var fallbackMsg = lastProgErr || (
          (rawText && rawText.indexOf('<') === -1)
            ? rawText.trim().slice(0, 220)
            : ('e-Panchayat login service returned HTTP ' + res.status + '. Please try again.')
        );
        showModalAlert('dept-modal-alert-1', data.detail || data.message || fallbackMsg, true);
      }
    } catch (err) {
      deptLoginInProgress = false;
      var errMsg = (err && err.name === 'AbortError')
        ? 'Portal request timed out after 75s. Please try again.'
        : ('Connection error: ' + err.message);
      showModalAlert('dept-modal-alert-1', errMsg, true);
    } finally {
      clearInterval(waitTimer);
      clearInterval(progressPoller);
      if (abortTimer) clearTimeout(abortTimer);
      if (btn) btn.disabled = false;
      if (btnText) btnText.textContent = 'Connect to e-Panchayat & Generate OTP →';
    }
  };

  window.handleDeptModalOtpSubmit = async function (event) {
    if (event) event.preventDefault();
    var rawOtp = (document.getElementById('dept-modal-otp-input') && document.getElementById('dept-modal-otp-input').value) || '';
    var otp = rawOtp.replace(/\D/g, '');
    var btn = document.getElementById('btn-dept-modal-verify-otp');
    var btnText = document.getElementById('btn-dept-modal-verify-text');

    if (otp.length !== 6) {
      showModalAlert('dept-modal-alert-2', 'Please enter a valid 6-digit numeric OTP.', true);
      return;
    }

    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = 'Validating OTP...';
    showModalAlert('dept-modal-alert-2', '');

    try {
      var formData = new FormData();
      formData.append('otp', otp);

      var res = await _deptFetch('/api/naresh/verify-otp', {
        method: 'POST',
        body: formData,
      });
      var data = await res.json().catch(function () { return {}; });

      if (res.ok && data.success) {
        deptLoginInProgress = false;
        var savedOff = '';
        var modalUser = (document.getElementById('dept-modal-user') && document.getElementById('dept-modal-user').value) || '';
        try { savedOff = sessionStorage.getItem('epts_officer_id') || ''; } catch (e) {}
        var user = data.user_id || modalUser || savedOff || 'Officer';

        window.isDeptAuthenticated = true;
        try {
          sessionStorage.setItem('epts_dept_session', 'true');
          sessionStorage.setItem('epts_portal_auth', 'true');
          sessionStorage.setItem('epts_officer_id', user);
        } catch (e) {}

        setAuthenticated(true, user, data);
        showNotice('Departmental session connected for Officer ' + user + '.', 'success');

        var succMsg = document.getElementById('dept-modal-success-msg');
        if (succMsg) {
          var lvlLabel = data.user_level === 'mandal' && data.mandal_name
            ? ('Mandal Level (' + data.mandal_name + ')')
            : (data.user_level === 'division' ? 'Divisional Level' : 'District Level');
          succMsg.textContent = 'Official e-Panchayat session connected for Officer ' + user + ' (' + lvlLabel + '). Background automation is active.';
        }

        var target = window.pendingStation;
        window.pendingStation = null;
        var pendingObj = window.DeptSessionManager ? window.DeptSessionManager.consumePendingAction() : null;
        if (!pendingObj && target) {
          pendingObj = { module: target, autoGenerate: false, params: {} };
        }
        clearDeptCredentialInputs();

        if (pendingObj && pendingObj.module) {
          window.closeDepartmentLoginModal();
          await window.resumePendingDepartmentAction(pendingObj);
          return;
        }

        window.switchDeptModalStep('success');
        deptAutoCloseTimer = setTimeout(function () {
          window.closeDepartmentLoginModal();
        }, 2500);
      } else {
        showModalAlert('dept-modal-alert-2', data.detail || data.message || 'OTP verification failed. Please try again.', true);
      }
    } catch (err) {
      showModalAlert('dept-modal-alert-2', 'Verification error: ' + err.message, true);
    } finally {
      if (btn) btn.disabled = false;
      if (btnText) btnText.textContent = '✓ Validate OTP & Connect Session';
    }
  };

  window.disconnectEptsSession = async function () {
    var confirmed = typeof window.showConfirmModal === 'function'
      ? await window.showConfirmModal({
        title: 'Disconnect Departmental Session',
        message: 'Disconnect the e-Panchayat departmental session? You will need to re-enter your User ID & OTP to run fresh automated portal downloads.',
        confirmLabel: 'Disconnect',
        danger: true,
      })
      : true;
    if (!confirmed) return;

    try {
      await window.safeFetchJson('/api/naresh/logout', { method: 'POST' });
    } catch (e) {}

    clearEptsStorageOnly();
    clearDeptCredentialInputs();
    if (window.DeptSessionManager) {
      window.DeptSessionManager.clearPendingAction();
    }
    reportData = null;
    deptLoginInProgress = false;
    setAuthenticated(false);
    ['results-section', 'state-format-results', 'auto-multi-results-section', 'inspections-results-card', 'balance-results-card'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    showNotice('Disconnected from e-Panchayat departmental session and closed background browser.', 'info');
  };

  window.logoutPortalSession = window.disconnectEptsSession;

  // ---------------------------------------------------------------------------
  // DSR Robot Station (#automation-station + #results-section)
  // ---------------------------------------------------------------------------

  window.openDsrRobot = async function (options) {
    var opts = options || {};
    if (!opts.skipAuthCheck) {
      var ok = await window.ensureDepartmentSession('dsr', {
        autoGenerate: opts.autoGenerate === true,
        params: opts.params,
      });
      if (!ok) return;
    }

    if (opts.params) {
      applyDsrParams(opts.params);
    } else {
      var dateInput = document.getElementById('auto-date');
      if (dateInput && !dateInput.value) dateInput.value = localDateStr();
    }

    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var station = document.getElementById('automation-station');
    var backWrap = document.getElementById('btn-back-dashboard-wrap');
    var backHomeWrap = document.getElementById('btn-back-home-wrap');
    var resultsEl = document.getElementById('results-section');

    if (station) {
      station.style.display = 'block';
      if (backWrap) backWrap.style.display = 'block';
      if (backHomeWrap) backHomeWrap.style.display = 'none';
      window.goToStep(3);
      station.scrollIntoView({ behavior: 'smooth' });
    }
    if (resultsEl) {
      resultsEl.style.display = (reportData && reportData.totals && Object.keys(reportData.totals).length > 0) ? 'block' : 'none';
    }

    if (opts.autoGenerate === true) {
      await window.runAutomatedGeneration();
    } else if (typeof window.updateStatus === 'function') {
      window.updateStatus('Station ready — choose Report Date, Cutoff Time & Sort Order, then click Generate Report.');
    }
  };

  window.getMasWorkspaceUrl = function (params, autoGen) {
    var base = (window.DeptSessionManager && typeof window.DeptSessionManager.buildScopedUrl === 'function')
      ? window.DeptSessionManager.buildScopedUrl('/reports/mas')
      : (window.isReportsHost && window.isReportsHost() ? '/reports/mas' : '/reports/mas?site=console');
    if (window.DeptSessionManager && typeof window.DeptSessionManager.appendSessionParam === 'function') {
      base = window.DeptSessionManager.appendSessionParam(base);
    }
    if (!params && !autoGen) return base;
    try {
      var u = new URL(base, window.location.origin);
      if (autoGen && params && params.month) u.searchParams.set('auto_generate', '1');
      if (params && typeof params === 'object') {
        ['month', 'year', 'report_type', 'excluded_modules'].forEach(function (k) {
          if (params[k] !== undefined && params[k] !== null && String(params[k]).trim() !== '') {
            u.searchParams.set(k, String(params[k]).trim());
          }
        });
      }
      return u.pathname + u.search;
    } catch (e) {
      return base;
    }
  };

  window.openMasRobot = async function (evOrOpts, maybeOpts) {
    var ev = (evOrOpts && typeof evOrOpts.preventDefault === 'function') ? evOrOpts : null;
    var opts = ev ? (maybeOpts || {}) : (evOrOpts || {});
    if (ev) ev.preventDefault();

    var dest = window.getMasWorkspaceUrl(opts.params, opts.autoGenerate);
    if (!window.isPortalAuthenticated) {
      window.location.href = dest;
      return false;
    }
    if (!opts.skipAuthCheck && window.isDeptAuthenticated !== true) {
      var ok = await window.ensureDepartmentSession('mas', {
        autoGenerate: opts.autoGenerate === true,
        returnUrl: dest,
        params: opts.params,
      });
      if (!ok) return false;
    }
    window.location.href = dest;
    return false;
  };

  window.goToStep = function (step) {
    currentStep = step;
    for (var i = 1; i <= 4; i++) {
      var pane = document.getElementById('pane-step-' + i);
      var nav = document.getElementById('step-nav-' + i);
      var line = document.getElementById('line-' + i);
      if (pane) pane.classList.toggle('active', i === step);
      if (nav) {
        nav.classList.toggle('active', i === step);
        nav.classList.toggle('completed', i < step);
      }
      if (line) {
        line.classList.toggle('active', i < step);
      }
    }
    if (step === 3) {
      var dpoaFreshWrap = document.getElementById('dpoa-fresh-toggle-wrap');
      if (dpoaFreshWrap) dpoaFreshWrap.style.display = 'none';
    }
  };

  window.onStepperNavClick = function (step) {
    if (step === 1 || step === 2) {
      if (window.isDeptAuthenticated === true) {
        if (typeof window.openDepartmentLoginModal === 'function') {
          window.openDepartmentLoginModal();
        }
        return;
      }
      if (step === 2 && currentStep < 2) {
        showNotice('Please enter e-Panchayat credentials in Login before entering OTP.', 'info');
        return;
      }
      window.goToStep(step);
      return;
    }
    if (step === 3) {
      if (window.isDeptAuthenticated !== true) {
        window.ensureDepartmentSession('dsr');
        return;
      }
      window.goToStep(3);
    }
  };

  window.togglePasswordVisibility = function () {
    var pwd = document.getElementById('auto-pwd');
    if (pwd) {
      pwd.type = pwd.type === 'password' ? 'text' : 'password';
    }
  };

  window.updateStatus = function (msg, type) {
    var sMsg = document.getElementById('status-msg');
    var sDot = document.getElementById('status-dot');
    if (!sMsg) return;
    sMsg.textContent = msg || '';
    if (type === 'error') {
      if (sDot) sDot.style.background = '#dc2626';
      sMsg.style.color = '#dc2626';
    } else if (type === 'success') {
      if (sDot) sDot.style.background = '#10b981';
      sMsg.style.color = '#047857';
    } else {
      if (sDot) sDot.style.background = '#f59e0b';
      sMsg.style.color = '#4e6b60';
    }
  };

  window.updateOfficerBadge = function (val) {
    var clean = (val || '').trim();
    var offText = document.getElementById('officer-id-text');
    var offBadge = document.getElementById('officer-badge');
    if (offText) offText.textContent = clean || 'Login';
    if (offBadge) offBadge.style.display = 'inline-flex';
  };

  window.displayOtpNotice = function (msg, mobile) {
    try {
      var noticeBox = document.getElementById('otp-dynamic-notice');
      var mobStr = String(mobile || '').trim();
      var textStr = String(msg || '').trim();
      if (!noticeBox) return;
      if (textStr) {
        noticeBox.textContent = textStr;
      } else if (mobStr) {
        noticeBox.innerHTML =
          'A 6 digit OTP has been sent to your registered mobile number ' +
          '<span id="otp-mobile-span" style="text-decoration: underline; font-weight: 800;">' + esc(mobStr) + '</span>' +
          '. Enter OTP to continue.';
      }
      noticeBox.style.display = 'block';
    } catch (e) {}
  };

  window.startDepartmentLogin = async function () {
    var userEl = document.getElementById('auto-user');
    var pwdEl = document.getElementById('auto-pwd');
    var user = (userEl && userEl.value || '').trim();
    var pwd = (pwdEl && pwdEl.value || '').trim();
    if (!user || !pwd) {
      showNotice('Please enter both e-Panchayat User ID and Password.', 'error');
      return;
    }

    window.updateOfficerBadge(user);
    var btn = document.getElementById('btn-login');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Logging in...';
    }
    window.updateStatus('Logging in to e-Panchayat & solving captcha...');

    try {
      var formData = new FormData();
      formData.append('username', user);
      formData.append('password', pwd);

      var json = await window.safeFetchJson('/api/naresh/login', {
        method: 'POST',
        body: formData,
      });

      var otpNoticeMsg = json.otp_message || json.message || '';
      var otpMobile = json.mobile_number || '';
      window.displayOtpNotice(otpNoticeMsg, otpMobile);
      window.updateStatus(otpNoticeMsg || 'OTP triggered successfully!', 'success');
      showNotice(otpNoticeMsg || '6-digit OTP triggered for Officer ' + user + '.', 'success');
      var badge = document.getElementById('session-badge');
      if (badge) badge.textContent = 'Officer: ' + user + ' (Awaiting OTP)';
      window.goToStep(2);
      setTimeout(function () {
        var otpInput = document.getElementById('auto-otp');
        if (otpInput) otpInput.focus();
      }, 200);
    } catch (err) {
      window.updateStatus('Login Note: ' + err.message, 'error');
      showNotice('Department login: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '🔐 Connect to e-Panchayat & Generate OTP';
      }
    }
  };

  window.validateOTP = async function () {
    var otpEl = document.getElementById('auto-otp');
    var otp = ((otpEl && otpEl.value) || '').replace(/\D/g, '');
    if (otp.length !== 6) {
      showNotice('Please enter a valid 6-digit numeric OTP.', 'error');
      return;
    }
    var user = ((document.getElementById('auto-user') && document.getElementById('auto-user').value) || 'Officer').trim();
    var btn = document.getElementById('btn-validate-otp');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Validating OTP...';
    }
    window.updateStatus('Validating OTP on e-Panchayat portal...');

    try {
      var formData = new FormData();
      formData.append('otp', otp);

      var json = await window.safeFetchJson('/api/naresh/verify-otp', {
        method: 'POST',
        body: formData,
      });

      var activeUser = json.user_id || user;
      window.updateStatus(json.message || 'Authenticated! Session active for Officer ' + activeUser + '.', 'success');
      showNotice(json.message || 'Session active for Officer ' + activeUser + '.', 'success');
      clearDeptCredentialInputs();
      setAuthenticated(true, activeUser, json);
      window.goToStep(3);

      var pendingObj = window.DeptSessionManager ? window.DeptSessionManager.consumePendingAction() : null;
      if (!pendingObj && window.pendingStation) {
        pendingObj = { module: window.pendingStation, autoGenerate: false, params: {} };
      }
      window.pendingStation = null;
      if (pendingObj && pendingObj.module) {
        await window.resumePendingDepartmentAction(pendingObj);
      }
    } catch (err) {
      window.updateStatus('OTP Error: ' + err.message, 'error');
      showNotice('OTP verification: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '✅ Validate OTP & Proceed to Report Selection';
      }
    }
  };

  window.updateCutoffLabelInUi = function (timeVal) {
    if (!timeVal) return;
    var parts = timeVal.split(':');
    var hr = parseInt(parts[0], 10);
    var min = parseInt(parts[1], 10);
    var ampm = hr >= 12 ? 'PM' : 'AM';
    hr = hr % 12 || 12;
    var formatted = min === 0 ? (hr + ' ' + ampm) : (hr + ':' + (min < 10 ? '0' + min : min) + ' ' + ampm);
    var opt = document.getElementById('opt-sort-cutoff');
    if (opt) {
      opt.textContent = '1. Sort based on before ' + formatted + ' or entered time (Punctuality %)';
    }
    var lblSec = document.getElementById('lbl-sec-after-cutoff');
    if (lblSec) {
      lblSec.textContent = 'GPs THAT SUBMITTED ATTENDANCE AFTER ' + formatted;
    }
  };

  window.toggleAllDsrSections = function (isChecked) {
    document.querySelectorAll('.auto-sec-chk').forEach(function (chk) {
      chk.checked = Boolean(isChecked);
    });
  };

  window.syncAllDsrSectionsCheckbox = function () {
    var items = Array.prototype.slice.call(document.querySelectorAll('.auto-sec-chk'));
    var allChk = document.getElementById('auto-sec-all');
    if (!allChk || !items.length) return;
    allChk.checked = items.every(function (chk) { return chk.checked; });
  };

  function getSelectedDsrSectionsValue() {
    var items = Array.prototype.slice.call(document.querySelectorAll('.auto-sec-chk'));
    if (!items.length) return 'all';
    var checked = items.filter(function (chk) { return chk.checked; }).map(function (chk) { return chk.value; });
    if (checked.length === items.length) return 'all';
    if (checked.length === 0) return '';
    return checked.join(',');
  }

  function applyDsrSectionsSelection(val) {
    var items = Array.prototype.slice.call(document.querySelectorAll('.auto-sec-chk'));
    if (!items.length) return;
    var raw = String(val || 'all').trim().toLowerCase();
    if (!raw || raw === 'all') {
      window.toggleAllDsrSections(true);
      window.syncAllDsrSectionsCheckbox();
      return;
    }
    var wanted = raw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    items.forEach(function (chk) {
      chk.checked = wanted.indexOf(chk.value) !== -1;
    });
    window.syncAllDsrSectionsCheckbox();
  }

  function formatMinSec(totalSec) {
    var s = Math.max(0, Math.floor(totalSec));
    var m = Math.floor(s / 60);
    var remS = s % 60;
    return (m < 10 ? '0' + m : String(m)) + ':' + (remS < 10 ? '0' + remS : String(remS));
  }

  function startProgressTimer() {
    if (genProgressInterval) clearInterval(genProgressInterval);
    genStartTime = Date.now();
    targetDurationSec = 45;
    currentPct = 0;

    var elapsedEl = document.getElementById('val-elapsed-time');
    var expectedEl = document.getElementById('val-expected-time');
    var pctEl = document.getElementById('spinner-pct-text');
    var barFill = document.getElementById('progress-bar-fill');
    var spinner = document.getElementById('auto-spinner');

    if (elapsedEl) elapsedEl.textContent = '00:00';
    if (expectedEl) expectedEl.textContent = formatMinSec(targetDurationSec);
    if (pctEl) pctEl.textContent = '0%';
    if (barFill) barFill.style.width = '0%';
    if (spinner) {
      spinner.style.display = 'block';
      spinner.style.animation = 'spin 1s linear infinite';
    }

    genProgressInterval = setInterval(function () {
      var elapsedSec = Math.floor((Date.now() - genStartTime) / 1000);
      if (elapsedEl) elapsedEl.textContent = formatMinSec(elapsedSec);
      if (elapsedSec >= targetDurationSec - 3) {
        targetDurationSec = elapsedSec + 6;
      }
      var remainingSec = Math.max(0, targetDurationSec - elapsedSec);
      if (expectedEl) expectedEl.textContent = formatMinSec(remainingSec);

      var computedPct = 0;
      if (elapsedSec < 10) {
        computedPct = 5 + (elapsedSec / 10) * 30;
      } else if (elapsedSec < 22) {
        computedPct = 35 + ((elapsedSec - 10) / 12) * 25;
      } else if (elapsedSec < 34) {
        computedPct = 60 + ((elapsedSec - 22) / 12) * 22;
      } else {
        var extraSec = elapsedSec - 34;
        computedPct = 82 + (extraSec / (extraSec + 8)) * 14;
      }
      if (computedPct > currentPct && currentPct < 96) {
        currentPct = Math.min(96, computedPct);
      }
      var roundedPct = Math.round(currentPct);
      if (pctEl) pctEl.textContent = roundedPct + '%';
      if (barFill) barFill.style.width = roundedPct + '%';
    }, 200);
  }

  function completeProgressTimer() {
    if (genProgressInterval) {
      clearInterval(genProgressInterval);
      genProgressInterval = null;
    }
    currentPct = 100;
    var expectedEl = document.getElementById('val-expected-time');
    var pctEl = document.getElementById('spinner-pct-text');
    var barFill = document.getElementById('progress-bar-fill');
    var spinner = document.getElementById('auto-spinner');
    if (expectedEl) expectedEl.textContent = '00:00';
    if (pctEl) pctEl.textContent = '100%';
    if (barFill) barFill.style.width = '100%';
    if (spinner) spinner.style.animation = 'none';
  }

  function stopProgressTimerOnError() {
    if (genProgressInterval) {
      clearInterval(genProgressInterval);
      genProgressInterval = null;
    }
    var expectedEl = document.getElementById('val-expected-time');
    var spinner = document.getElementById('auto-spinner');
    if (expectedEl) expectedEl.textContent = '--:--';
    if (spinner) spinner.style.animation = 'none';
  }

  function setSubStep(idx, state) {
    var el = document.getElementById('ps-' + idx);
    if (!el) return;
    el.classList.remove('active', 'done');
    if (state) el.classList.add(state);
  }

  window.runAutomatedGeneration = async function () {
    if (dsrGenerationInFlight) return;
    var mod = (document.getElementById('auto-module') && document.getElementById('auto-module').value) || 'dsr_full';
    var date = (document.getElementById('auto-date') && document.getElementById('auto-date').value) || '';
    var cutoffTime = (document.getElementById('auto-cutoff-time') && document.getElementById('auto-cutoff-time').value) || '09:00';
    var sortBy = (document.getElementById('auto-sort-by') && document.getElementById('auto-sort-by').value) || 'before_9';
    var pageLayout = (document.getElementById('auto-page-layout') && document.getElementById('auto-page-layout').value) || 'individual';
    var includeSections = getSelectedDsrSectionsValue();

    if (!includeSections) {
      showNotice('Please select at least one report section to generate.', 'error');
      return;
    }

    if (!date) {
      showNotice('Please select a report date before running the DSR Robot.', 'error');
      return;
    }

    dsrGenerationInFlight = true;
    window.goToStep(4);
    startProgressTimer();
    clearStepTimeouts();

    var titleEl = document.getElementById('progress-status-title');
    var subTitleEl = document.getElementById('progress-status-sub');
    var banner = document.getElementById('auto-completion-banner');
    if (banner) banner.style.display = 'none';

    setSubStep(1, 'active');
    if (titleEl) titleEl.textContent = 'Step 1: GP Monitoring -> Downloading GM-R 1.2.7 DSR Raw Data...';
    if (subTitleEl) subTitleEl.textContent = 'Downloading morning attendance and DSR raw data records...';
    window.updateStatus('Downloading GM-R 1.2.7 DSR Raw Data...');

    try {
      var formData = new FormData();
      formData.append('module', mod);
      formData.append('date', date);
      formData.append('cutoff_time', cutoffTime);
      formData.append('sort_by', sortBy);
      formData.append('page_layout', pageLayout);
      formData.append('include_sections', includeSections);
      var chkExcludeIncharge = document.getElementById('auto-exclude-incharge');
      if (chkExcludeIncharge && chkExcludeIncharge.checked) {
        formData.append('exclude_incharge', 'true');
      }
      var chkFresh = document.getElementById('chk-force-fresh');
      if (chkFresh && chkFresh.checked) {
        formData.append('force_fresh', 'true');
      }

      stepTimeouts.push(setTimeout(function () {
        setSubStep(1, 'done');
        setSubStep(2, 'done');
        setSubStep(3, 'active');
        if (titleEl) titleEl.textContent = 'Step 2: Re-select GP Monitoring -> Downloading GM-R 1.2.11 Presentees Report...';
        if (subTitleEl) subTitleEl.textContent = 'Matching Panchayat Secretary details and mobile numbers...';
        window.updateStatus('Downloading GM-R 1.2.11 Presentees Report...');
      }, 1200));

      stepTimeouts.push(setTimeout(function () {
        setSubStep(3, 'done');
        setSubStep(4, 'active');
        if (titleEl) titleEl.textContent = 'Step 3: Re-select GP Monitoring -> Downloading GM-R 1.2.10 Absentees Report...';
        if (subTitleEl) subTitleEl.textContent = 'Extracting leave, training, and meeting secretary logs...';
        window.updateStatus('Downloading GM-R 1.2.10 Absentees Report...');
      }, 2400));

      stepTimeouts.push(setTimeout(function () {
        setSubStep(4, 'done');
        setSubStep(5, 'active');
        if (titleEl) titleEl.textContent = 'Step 4: Compiling 6-Section Official Attendance & DSR Report...';
        if (subTitleEl) subTitleEl.textContent = 'Aggregating metrics, calculating punctuality, and compiling landscape PDF...';
        window.updateStatus('Compiling official 6-section PDF report...');
      }, 3600));

      await window.safeFetchJson('/api/naresh/generate', {
        method: 'POST',
        body: formData,
      });

      clearStepTimeouts();
      completeProgressTimer();

      for (var s = 1; s <= 5; s++) setSubStep(s, 'done');
      if (titleEl) titleEl.textContent = 'Official 6-Section District Attendance & DSR Report Generated!';
      if (subTitleEl) subTitleEl.textContent = 'All 6 sections successfully compiled and ready for review.';
      if (banner) banner.style.display = 'block';
      window.updateStatus('Official report generated successfully!', 'success');
      showNotice('Official 6-Section Attendance & DSR report generated successfully.', 'success');

      var resultsEl = document.getElementById('results-section');
      if (resultsEl) {
        resultsEl.style.display = 'block';
        resultsEl.scrollIntoView({ behavior: 'smooth' });
      }

      await window.loadNareshData();
      window.refreshViewer();
    } catch (err) {
      clearStepTimeouts();
      stopProgressTimerOnError();
      if (titleEl) titleEl.textContent = 'Generation encountered an error';
      if (subTitleEl) subTitleEl.textContent = err.message || 'Error occurred';
      window.updateStatus('Error: ' + err.message, 'error');
      if (!handleDepartmentSessionExpiredError(err, 'dsr', {
        auto_module: mod,
        auto_date: date,
        cutoff_time: cutoffTime,
        sort_by: sortBy,
        page_layout: pageLayout,
        include_sections: includeSections,
      })) {
        showNotice('DSR report generation error: ' + err.message, 'error');
      }
    } finally {
      dsrGenerationInFlight = false;
    }
  };

  window.loadNareshData = async function () {
    try {
      reportData = await window.safeFetchJson('/api/naresh/data');
      var resultsEl = document.getElementById('results-section');
      if (!reportData || !reportData.generated || !reportData.totals || Object.keys(reportData.totals).length === 0) {
        if (resultsEl) resultsEl.style.display = 'none';
        return;
      }

      var station = document.getElementById('automation-station');
      if (resultsEl) {
        resultsEl.style.display = (station && station.style.display === 'block') ? 'block' : 'none';
      }

      var dateEl = document.getElementById('report-date-badge');
      if (dateEl && reportData.report_date) {
        var timeLabel = reportData.generated_time ? (' (' + reportData.generated_time + ')') : '';
        dateEl.textContent = '📅 Date: ' + reportData.report_date + timeLabel;
      }

      var cleanDist = String(reportData.district_name || 'Khammam').replace(/\s+/g, '_');
      var reportDt = String(reportData.report_date || '').replace(/\s+/g, '-');
      var timeStamp = reportData.generated_timestamp || '';
      var dlFilename = reportData.download_filename || (cleanDist + '_PS_Attendance_and_DSR_Report_' + reportDt + (timeStamp ? '_' + timeStamp : '') + '.pdf');
      var dlHref = window.DeptSessionManager
        ? window.DeptSessionManager.appendSessionParam('/api/naresh/download')
        : '/api/naresh/download';
      var btnAuto = document.getElementById('btn-auto-download-pdf');
      if (btnAuto) {
        btnAuto.setAttribute('download', dlFilename);
        btnAuto.setAttribute('href', dlHref);
      }
      var btnViewer = document.getElementById('btn-viewer-download-pdf');
      if (btnViewer) {
        btnViewer.setAttribute('download', dlFilename);
        btnViewer.setAttribute('href', dlHref);
      }

      var t = reportData.totals || {};
      var el;
      el = document.getElementById('val-total-gps'); if (el) el.textContent = t.unique_gps != null ? t.unique_gps : '—';
      el = document.getElementById('val-att-submitted'); if (el) el.textContent = t.attendance_submitted != null ? t.attendance_submitted : '—';
      var pct = t.overall_attendance_pct != null ? Number(t.overall_attendance_pct).toFixed(1) : '—';
      el = document.getElementById('sub-att-pct'); if (el) el.textContent = pct !== '—' ? (pct + '% Compliance') : '—';
      el = document.getElementById('val-dsr-entered'); if (el) el.textContent = t.dsr_entered != null ? t.dsr_entered : '—';
      var dsrElig = t.dsr_eligible || 0;
      var dsrPct = dsrElig > 0 && t.dsr_entered != null ? ((t.dsr_entered / dsrElig) * 100).toFixed(1) : '—';
      el = document.getElementById('sub-dsr-pct'); if (el) el.textContent = dsrPct !== '—' ? (dsrPct + '% of Eligible (' + dsrElig + ')') : '—';
      el = document.getElementById('val-before-9'); if (el) el.textContent = t.before_9 != null ? t.before_9 : '—';
      el = document.getElementById('val-on-leave'); if (el) el.textContent = (t.on_leave || 0) + (t.meeting_training || 0);
      el = document.getElementById('val-pending'); if (el) el.textContent = t.pending != null ? t.pending : '—';

      var isMandal = Boolean(reportData.is_mandal_level);
      window.isMandalLevelDsr = isMandal;
      var countLabel = document.getElementById('mandals-count-label');
      var mandalSearch = document.getElementById('mandal-search');
      var sortSel = document.getElementById('online-sort-selector');
      var sortWrap = sortSel ? sortSel.parentElement : null;

      if (isMandal) {
        var mandalName = reportData.mandal_name || 'Mandal';
        if (countLabel) countLabel.textContent = (reportData.gp_rows || []).length + ' Gram Panchayats (' + mandalName + ' Mandal)';
        if (mandalSearch) mandalSearch.placeholder = 'Search GP or Secretary in ' + mandalName + '...';
        if (sortWrap) sortWrap.style.display = 'none';
        renderMandalGpsTable(reportData.gp_rows || []);
      } else {
        if (sortWrap) sortWrap.style.display = 'flex';
        if (mandalSearch) mandalSearch.placeholder = 'Search Mandal...';
        window.currentMandalRows = reportData.mandal_rows || [];
        if (countLabel && window.currentMandalRows.length > 0) {
          countLabel.textContent = window.currentMandalRows.length + ' Mandals';
        }
        var cutoffLbl = (reportData.totals && reportData.totals.cutoff_label) ? reportData.totals.cutoff_label : '9 AM';
        var thCutoff = document.getElementById('th-cutoff-header');
        if (thCutoff) thCutoff.textContent = 'Before ' + cutoffLbl;
        if (sortSel && reportData.totals && reportData.totals.sort_by) {
          sortSel.value = reportData.totals.sort_by;
        }
        renderMandals(window.currentMandalRows);
      }
    } catch (e) {}
  };

  window.sortOnlineMandalsTable = function (sortKey) {
    if (!window.currentMandalRows || window.currentMandalRows.length === 0) return;
    var sel = document.getElementById('online-sort-selector');
    if (sel && sel.value !== sortKey && ['before_9', 'overall_att_pct', 'dsr_pct', 'att_pending', 'dsr_pending', 'mandal'].indexOf(sortKey) !== -1) {
      sel.value = sortKey;
    }

    if (window.currentSortKey === sortKey) {
      window.currentSortAsc = !window.currentSortAsc;
    } else {
      window.currentSortKey = sortKey;
      window.currentSortAsc = (sortKey !== 'att_pending' && sortKey !== 'dsr_pending');
    }

    var rows = window.currentMandalRows.slice();
    rows.sort(function (a, b) {
      if (sortKey === 'mandal') {
        return window.currentSortAsc
          ? String(a.mandal || '').localeCompare(String(b.mandal || ''))
          : String(b.mandal || '').localeCompare(String(a.mandal || ''));
      }
      var valA = 0;
      var valB = 0;
      if (sortKey === 'before_9') {
        valA = Number(a.before_9_pct || 0);
        valB = Number(b.before_9_pct || 0);
      } else if (sortKey === 'overall_att_pct' || sortKey === 'attendance_pct') {
        valA = Number(a.attendance_pct || 0);
        valB = Number(b.attendance_pct || 0);
      } else if (sortKey === 'dsr_pct') {
        valA = Number(a.dsr_pct || 0);
        valB = Number(b.dsr_pct || 0);
      } else if (sortKey === 'att_pending' || sortKey === 'pending') {
        valA = Number(a.pending || 0);
        valB = Number(b.pending || 0);
      } else if (sortKey === 'dsr_pending') {
        valA = Number(a.dsr_pending || 0);
        valB = Number(b.dsr_pending || 0);
      } else if (sortKey === 'total_gps') {
        valA = Number(a.total_gps || 0);
        valB = Number(b.total_gps || 0);
      } else if (sortKey === 'submitted') {
        valA = Number(a.submitted || 0);
        valB = Number(b.submitted || 0);
      } else if (sortKey === 'on_leave') {
        valA = Number(a.on_leave || 0) + Number(a.meeting_training || 0);
        valB = Number(b.on_leave || 0) + Number(b.meeting_training || 0);
      } else if (sortKey === 'dsr_entered') {
        valA = Number(a.dsr_entered || 0);
        valB = Number(b.dsr_entered || 0);
      } else {
        valA = Number(a.serial || 0);
        valB = Number(b.serial || 0);
      }
      if (valA < valB) return window.currentSortAsc ? -1 : 1;
      if (valA > valB) return window.currentSortAsc ? 1 : -1;
      return String(a.mandal || '').localeCompare(String(b.mandal || ''));
    });
    renderMandals(rows);
  };

  function renderMandalGpsTable(gps) {
    window.currentMandalGps = gps || [];
    var thead = document.querySelector('#mandals-table thead');
    if (thead) {
      thead.innerHTML =
        '<tr>' +
          '<th class="text-center" style="width:45px;">#</th>' +
          '<th>Gram Panchayat Name</th>' +
          '<th>Panchayat Secretary</th>' +
          '<th>Mobile</th>' +
          '<th class="text-center">Punch Status</th>' +
          '<th class="text-center">Punch Time</th>' +
          '<th class="text-center">DSR Status</th>' +
        '</tr>';
    }
    var tbody = document.getElementById('mandals-tbody');
    if (!tbody) return;
    if (!gps || gps.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center" style="padding:24px;">e-Panchayat Automation: No Gram Panchayat records available for this mandal.</td></tr>';
      return;
    }

    tbody.innerHTML = gps.map(function (r, idx) {
      var statusBadge;
      if (r.submitted) {
        if (r.on_leave) {
          statusBadge = '<span style="background:#fef3c7; color:#92400e; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">On Leave</span>';
        } else if (r.meeting_training) {
          statusBadge = '<span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">Meeting/Training</span>';
        } else {
          statusBadge = '<span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">Present</span>';
        }
      } else {
        statusBadge = '<span style="background:#fee2e2; color:#dc2626; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">Attendance Pending</span>';
      }

      var timeBadge;
      if (r.submitted) {
        var safeTime = esc(r.time_only || '—');
        timeBadge = r.before_9
          ? '<span style="color:#15803d; font-weight:700;">' + safeTime + ' (On Time)</span>'
          : '<span style="color:#d97706; font-weight:700;">' + safeTime + ' (After Cutoff)</span>';
      } else {
        timeBadge = '<span style="color:#94a3b8;">—</span>';
      }

      var dsrBadge;
      if (r.dsr_entered) {
        dsrBadge = '<span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">DSR Entered</span>';
      } else if (r.dsr_eligible) {
        dsrBadge = '<span style="background:#fee2e2; color:#dc2626; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">DSR Pending</span>';
      } else {
        dsrBadge = '<span style="color:#94a3b8;">—</span>';
      }

      var tel = sanitizeTel(r.mobile);
      var phoneLink = (tel && r.mobile !== '—')
        ? '<a href="tel:' + esc(tel) + '" style="color:#0284c7; text-decoration:none; font-weight:600;">📞 ' + esc(r.mobile) + '</a>'
        : '<span style="color:#94a3b8;">—</span>';

      return (
        '<tr>' +
          '<td class="text-center">' + (idx + 1) + '</td>' +
          '<td><strong>' + esc(r.gp || '') + '</strong></td>' +
          '<td>' + esc(r.ps_name || 'Panchayat Secretary') + '</td>' +
          '<td>' + phoneLink + '</td>' +
          '<td class="text-center">' + statusBadge + '</td>' +
          '<td class="text-center">' + timeBadge + '</td>' +
          '<td class="text-center">' + dsrBadge + '</td>' +
        '</tr>'
      );
    }).join('');
    window.filterMandals();
  }

  function renderMandals(rows) {
    var thead = document.querySelector('#mandals-table thead');
    if (thead) {
      thead.innerHTML =
        '<tr>' +
          '<th style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'serial\')" title="Sort by S.No"># ⇕</th>' +
          '<th style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'mandal\')" title="Sort by Mandal Name">Mandal Name ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'total_gps\')" title="Sort by Total GPs">Total GPs ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'submitted\')" title="Sort by Submitted">Submitted ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'overall_att_pct\')" title="Sort by Attendance %">Attendance % ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'before_9\')" title="Sort by Before Cutoff Time"><span id="th-cutoff-header">Before 9 AM</span> ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'on_leave\')" title="Sort by On Leave">On Leave / Meet ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'att_pending\')" title="Sort by Pending Attendance">Pending ⇕</th>' +
          '<th class="text-center" style="cursor:pointer;" onclick="sortOnlineMandalsTable(\'dsr_entered\')" title="Sort by DSR Entered">DSR Entered ⇕</th>' +
        '</tr>';
    }
    var tbody = document.getElementById('mandals-tbody');
    if (!tbody) return;
    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center">e-Panchayat Automation: No mandal rows available.</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function (r, idx) {
      var pctNum = r.attendance_pct != null ? Number(r.attendance_pct) : 0;
      var pct = pctNum.toFixed(1);
      var pend = Number(r.pending || 0);
      return (
        '<tr>' +
          '<td>' + (idx + 1) + '</td>' +
          '<td><strong>' + esc(r.mandal || '') + '</strong></td>' +
          '<td class="text-center">' + esc(r.total_gps || 0) + '</td>' +
          '<td class="text-center">' + esc(r.submitted || 0) + '</td>' +
          '<td class="text-center">' +
            '<strong>' + esc(pct) + '%</strong>' +
            '<span class="pct-bar-wrap"><span class="pct-bar-fill" style="width:' + Math.min(100, pctNum) + '%"></span></span>' +
          '</td>' +
          '<td class="text-center" style="color:var(--success); font-weight:600;">' + esc(r.before_9 || 0) + '</td>' +
          '<td class="text-center">' + esc((r.on_leave || 0) + (r.meeting_training || 0)) + '</td>' +
          '<td class="text-center" style="color:' + (pend > 0 ? 'var(--danger)' : 'var(--text-muted)') + '; font-weight:' + (pend > 0 ? '700' : '400') + ';">' + esc(pend) + '</td>' +
          '<td class="text-center" style="color:var(--info); font-weight:600;">' + esc(r.dsr_entered || 0) + '</td>' +
        '</tr>'
      );
    }).join('');
    window.filterMandals();
  }

  window.filterMandals = function () {
    var inp = document.getElementById('mandal-search');
    var q = (inp ? inp.value : '').toLowerCase();
    document.querySelectorAll('#mandals-tbody tr').forEach(function (tr) {
      var text = (tr.innerText || tr.textContent || '').toLowerCase();
      tr.style.display = text.indexOf(q) !== -1 ? '' : 'none';
    });
  };

  window.loadAndScrollToViewer = function () {
    var el = document.getElementById('viewer-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  window.refreshViewer = function () {
    var frame = document.getElementById('pdf-frame');
    if (!frame) return;
    var base = window.DeptSessionManager
      ? window.DeptSessionManager.appendSessionParam('/api/naresh/view')
      : '/api/naresh/view';
    frame.src = base + (base.indexOf('?') === -1 ? '?t=' : '&t=') + Date.now();
  };

  // ---------------------------------------------------------------------------
  // Balance Robot Station (GM-R 14.2)
  // ---------------------------------------------------------------------------

  function isBalancePmagyIncluded() {
    var chk = document.getElementById('chk-balance-include-pmagy');
    return Boolean(chk && chk.checked);
  }

  function updateBalancePmagyRuleNote(includePmagy) {
    var note = document.getElementById('balance-pmagy-rule-note');
    var lbl = document.getElementById('lbl-balance-include-pmagy');
    if (note) {
      note.innerHTML = includePmagy
        ? '<b>PMAGY account is included</b> (Pradhan Mantri Adarsh Gram Yojana counted in compliance &amp; pending totals).'
        : '<b>PMAGY account is excluded</b> (Check &ldquo;Include PMAGY&rdquo; above to include it).';
    }
    if (lbl) {
      lbl.style.borderColor = includePmagy ? '#059669' : 'var(--border)';
      lbl.style.background = includePmagy ? '#ecfdf5' : '#ffffff';
      lbl.style.color = includePmagy ? '#065f46' : 'var(--text)';
    }
  }

  function buildBalanceMandalThead(includePmagy) {
    return (
      '<tr style="background:#0c3829 !important; color:#ffffff !important;">' +
        '<th class="text-center" style="width:45px;">S.No</th>' +
        '<th>Mandal Name</th>' +
        '<th class="text-right">Total GPs</th>' +
        '<th class="text-right">GPs Entered</th>' +
        '<th class="text-right">GPs Not Entered</th>' +
        '<th class="text-right th-pct">% Data Entered</th>' +
        '<th class="text-center">GP PD (Upd/Pnd)</th>' +
        '<th class="text-center">TG-bPASS (Upd/Pnd)</th>' +
        '<th class="text-center">15th FC Tied</th>' +
        '<th class="text-center">15th FC Untied</th>' +
        (includePmagy ? '<th class="text-center">PMAGY</th>' : '') +
        '<th class="text-center">VWSC (SBM)</th>' +
        '<th class="text-center">MGNREGS</th>' +
        '<th class="text-center" style="width:80px;">Status</th>' +
      '</tr>'
    );
  }

  window.onBalancePmagyChanged = async function () {
    var inc = isBalancePmagyIncluded();
    updateBalancePmagyRuleNote(inc);
    var sel = document.getElementById('balance-date-select');
    var dateVal = sel ? sel.value : '';
    if (dateVal) {
      await window.loadBalanceData(dateVal);
    } else {
      window.resetBalanceUI();
    }
  };

  window.resetBalanceUI = function () {
    ['bal-kpi-mandals', 'bal-kpi-total-gps', 'bal-kpi-entered', 'bal-kpi-pending', 'bal-kpi-pct'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = '—';
    });

    var incPmagy = isBalancePmagyIncluded();
    updateBalancePmagyRuleNote(incPmagy);

    var actionsWrap = document.getElementById('balance-actions-wrap');
    if (actionsWrap) actionsWrap.style.display = 'none';

    var thead = document.querySelector('#balance-mandal-table thead');
    if (thead) thead.innerHTML = buildBalanceMandalThead(incPmagy);

    var colSpan = incPmagy ? 14 : 13;
    var tbody = document.getElementById('balance-table-tbody');
    if (tbody) {
      tbody.innerHTML =
        '<tr>' +
          '<td colspan="' + colSpan + '" style="text-align:center; padding:38px 20px; color:var(--text-muted); font-size:0.95rem;">' +
            '<div style="font-size:1.8rem; margin-bottom:8px;">🏦</div>' +
            '<strong style="color:var(--text); font-size:1.05rem;">No Balance Report Processed Yet</strong>' +
            '<div style="font-size:0.86rem; color:var(--text-muted); margin-top:6px;">' +
              'e-Panchayat Automation is ready — select a Thursday date above and click <b style="color:#b45309;">⚡ Run Balance Robot</b> to fetch live portal data.' +
            '</div>' +
          '</td>' +
        '</tr>';
    }

    var pendingCard = document.getElementById('balance-pending-gps-card');
    if (pendingCard) pendingCard.style.display = 'none';
  };

  window.openBalanceRobot = async function (options) {
    var opts = options || {};
    if (!opts.skipAuthCheck) {
      var ok = await window.ensureDepartmentSession('balance', {
        autoGenerate: opts.autoGenerate === true,
        params: opts.params,
      });
      if (!ok) return;
    }

    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var balStation = document.getElementById('balance-station');
    if (balStation) {
      balStation.style.display = 'block';
      balStation.scrollIntoView({ behavior: 'smooth' });
      var unauthBanner = document.getElementById('bal-unauth-banner');
      if (unauthBanner) unauthBanner.style.display = 'none';
      var chkPmagy = document.getElementById('chk-balance-include-pmagy');
      if (chkPmagy && opts.params && opts.params.include_pmagy !== undefined) {
        chkPmagy.checked = opts.params.include_pmagy === true || opts.params.include_pmagy === 'true' || opts.params.include_pmagy === '1';
      }
      updateBalancePmagyRuleNote(isBalancePmagyIncluded());
      var preferredDate = opts.params && opts.params.balance_date ? opts.params.balance_date : '';
      await window.fetchPortalBalanceDates(false, preferredDate);
      if (opts.autoGenerate === true) {
        await window.triggerBalancePipeline();
      } else {
        await window.loadBalanceData();
      }
    }
  };

  window.fetchPortalBalanceDates = async function (showToast, preferredDate) {
    var sel = document.getElementById('balance-date-select');
    var btnRef = document.getElementById('btn-refresh-balance-dates');
    if (btnRef) btnRef.disabled = true;
    try {
      var data = await window.safeFetchJson('/api/balance/portal-dates');
      if (sel && data && Array.isArray(data.dates) && data.dates.length > 0) {
        var prevVal = preferredDate || sel.value;
        sel.innerHTML = '';
        data.dates.forEach(function (d, idx) {
          var opt = document.createElement('option');
          opt.value = d;
          opt.textContent = idx === 0
            ? d + (data.is_live ? ' (Live Portal Latest)' : ' (Latest Thursday)')
            : d;
          sel.appendChild(opt);
        });
        if (prevVal && data.dates.indexOf(prevVal) !== -1) {
          sel.value = prevVal;
        } else {
          sel.selectedIndex = 0;
        }
        window.onBalanceDateChanged();
      }
    } catch (err) {
      if (!handleDepartmentSessionExpiredError(err, 'balance', preferredDate ? { balance_date: preferredDate } : {})) {
        showNotice('Could not load Thursday balance dates: ' + err.message, 'error');
      }
    } finally {
      if (btnRef) btnRef.disabled = false;
    }
  };

  window.onBalanceDateChanged = function () {
    var sel = document.getElementById('balance-date-select');
    var dateVal = sel ? sel.value : '';
    if (dateVal) window.loadBalanceData(dateVal);
  };

  window.loadBalanceData = async function (reqDate) {
    var sel = document.getElementById('balance-date-select');
    var dateVal = reqDate || (sel ? sel.value : '');
    if (!dateVal) return;
    var incPmagy = isBalancePmagyIncluded();
    try {
      var data = await window.safeFetchJson(
        '/api/balance/data?date=' + encodeURIComponent(dateVal) + '&include_pmagy=' + (incPmagy ? '1' : '0')
      );
      if (data && data.has_data) {
        window.renderBalanceTable(data);
        if (incPmagy && data.scraped_with_pmagy === false && typeof window.updateStatus === 'function') {
          window.updateStatus('PMAGY included from summary counts — click ⚡ Run Balance Robot for full live GP-level PMAGY drill-down.');
        }
      } else {
        window.resetBalanceUI();
      }
    } catch (err) {
      handleDepartmentSessionExpiredError(err, 'balance', { balance_date: dateVal, include_pmagy: incPmagy });
      window.resetBalanceUI();
    }
  };

  var balProgressInterval = null;
  function startBalanceProgressTimer(estSeconds) {
    if (balProgressInterval) clearInterval(balProgressInterval);
    var card = document.getElementById('balance-progress-card');
    var elapEl = document.getElementById('balance-elapsed-time');
    var estEl = document.getElementById('balance-estimated-time');
    var pctEl = document.getElementById('balance-progress-pct');
    var fillEl = document.getElementById('balance-progress-fill');
    var statusEl = document.getElementById('balance-status-text');
    var startMs = Date.now();
    var targetSec = Math.max(10, estSeconds || 25);

    if (card) card.style.display = 'block';
    if (elapEl) elapEl.textContent = '00:00';
    if (estEl) estEl.textContent = formatMinSec(targetSec);
    if (pctEl) pctEl.textContent = '0%';
    if (fillEl) fillEl.style.width = '0%';
    if (statusEl) statusEl.textContent = 'Connecting to GM-R 14.2 and downloading Thursday balances...';

    balProgressInterval = setInterval(function () {
      var elapsed = Math.floor((Date.now() - startMs) / 1000);
      if (elapEl) elapEl.textContent = formatMinSec(elapsed);
      if (elapsed >= targetSec - 2) targetSec = elapsed + 5;
      if (estEl) estEl.textContent = formatMinSec(Math.max(0, targetSec - elapsed));
      var pct = Math.min(96, Math.round((elapsed / Math.max(1, targetSec)) * 96));
      if (pctEl) pctEl.textContent = pct + '%';
      if (fillEl) fillEl.style.width = pct + '%';
    }, 250);
  }

  function finishBalanceProgressTimer(success) {
    if (balProgressInterval) {
      clearInterval(balProgressInterval);
      balProgressInterval = null;
    }
    var estEl = document.getElementById('balance-estimated-time');
    var pctEl = document.getElementById('balance-progress-pct');
    var fillEl = document.getElementById('balance-progress-fill');
    var statusEl = document.getElementById('balance-status-text');
    var card = document.getElementById('balance-progress-card');
    if (success) {
      if (estEl) estEl.textContent = '00:00';
      if (pctEl) pctEl.textContent = '100%';
      if (fillEl) fillEl.style.width = '100%';
      if (statusEl) statusEl.textContent = 'Balance report compiled successfully!';
      setTimeout(function () {
        if (card) card.style.display = 'none';
      }, 1500);
    } else {
      if (estEl) estEl.textContent = '--:--';
      if (statusEl) statusEl.textContent = 'Balance compilation halted.';
    }
  }

  window.triggerBalancePipeline = async function () {
    if (balanceGenerationInFlight) return;
    var ok = await window.ensureDepartmentSession('balance', { autoGenerate: false });
    if (!ok) return;

    var sel = document.getElementById('balance-date-select');
    var dateVal = sel ? sel.value : '';
    if (!dateVal) {
      showNotice('Please select a valid Thursday date from the dropdown.', 'error');
      return;
    }

    var incPmagy = isBalancePmagyIncluded();
    balanceGenerationInFlight = true;
    startBalanceProgressTimer(25);
    var btn = document.getElementById('btn-run-balance-robot');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Fetching Thursday balance data from Portal...';
    }
    try {
      var fd = new FormData();
      fd.append('date', dateVal);
      fd.append('include_pmagy', incPmagy ? 'true' : 'false');
      var res = await window.safeFetchJson('/api/balance/generate', {
        method: 'POST',
        body: fd,
      });
      finishBalanceProgressTimer(true);
      showNotice(res.message || 'Balance report compiled successfully!', 'success');
      await window.loadBalanceData(dateVal);
    } catch (err) {
      finishBalanceProgressTimer(false);
      if (!handleDepartmentSessionExpiredError(err, 'balance', { balance_date: dateVal, include_pmagy: incPmagy })) {
        showNotice('Balance robot: ' + (err.message || 'Balance pipeline failed.'), 'error');
      }
    } finally {
      balanceGenerationInFlight = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = '⚡ Run Balance Robot';
      }
    }
  };

  window.renderBalanceTable = function (data) {
    if (!data || !data.has_data || !data.totals) {
      window.resetBalanceUI();
      return;
    }
    var showPmagy = Boolean(data.include_pmagy);
    updateBalancePmagyRuleNote(showPmagy);

    var t = data.totals;
    var el;
    el = document.getElementById('bal-kpi-mandals'); if (el) el.textContent = t.total_mandals != null ? t.total_mandals : '0';
    el = document.getElementById('bal-kpi-total-gps'); if (el) el.textContent = t.total_gps != null ? t.total_gps : '0';
    el = document.getElementById('bal-kpi-entered'); if (el) el.textContent = t.total_entered_gps != null ? t.total_entered_gps : '0';
    el = document.getElementById('bal-kpi-pending'); if (el) el.textContent = t.total_not_entered_gps != null ? t.total_not_entered_gps : '0';
    el = document.getElementById('bal-kpi-pct'); if (el) el.textContent = Number(t.overall_pct_entered || 0).toFixed(1) + '%';

    var dStr = data.report_date_str || '';
    var pmagyQ = '&include_pmagy=' + (showPmagy ? '1' : '0');
    var actionsWrap = document.getElementById('balance-actions-wrap');
    if (actionsWrap) actionsWrap.style.display = 'flex';
    var excelBtn = document.getElementById('btn-balance-excel');
    var pdfBtn = document.getElementById('btn-balance-pdf');
    var pdfDlBtn = document.getElementById('btn-balance-pdf-dl');
    var appendSess = window.DeptSessionManager ? window.DeptSessionManager.appendSessionParam : function (u) { return u; };
    if (excelBtn) excelBtn.href = appendSess('/api/balance/download-excel?date=' + encodeURIComponent(dStr) + pmagyQ);
    if (pdfBtn) pdfBtn.href = appendSess('/api/balance/report.pdf?date=' + encodeURIComponent(dStr) + pmagyQ);
    if (pdfDlBtn) {
      pdfDlBtn.href = appendSess('/api/balance/download-pdf?date=' + encodeURIComponent(dStr) + pmagyQ);
      pdfDlBtn.setAttribute('download', 'GP_Balance_Entry_Report_' + dStr + '.pdf');
    }

    var tbody = document.getElementById('balance-table-tbody');
    var thead = document.querySelector('#balance-mandal-table thead');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (data.is_mandal_level) {
      var mandalKpi = document.getElementById('bal-kpi-mandals');
      if (mandalKpi) mandalKpi.textContent = data.mandal_name || 'Mandal';
      if (thead) {
        thead.innerHTML =
          '<tr style="background:#0c3829 !important; color:#ffffff !important;">' +
            '<th class="text-center" style="width:40px;">#</th>' +
            '<th>Gram Panchayat Name</th>' +
            '<th class="text-center" style="width:90px;">Entry Status</th>' +
            '<th class="text-center">GP PD</th>' +
            '<th class="text-center">TG-bPASS</th>' +
            '<th class="text-center">15th Tied</th>' +
            '<th class="text-center">15th Untied</th>' +
            (showPmagy ? '<th class="text-center">PMAGY</th>' : '') +
            '<th class="text-center">VWSC</th>' +
            '<th class="text-center">MGNREGS</th>' +
            '<th>Missing Bank Account(s)</th>' +
            '<th>Panchayat Secretary &amp; Phone</th>' +
          '</tr>';
      }

      var rows = data.gp_rows || [];
      if (rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="' + (showPmagy ? 12 : 11) + '" class="text-center" style="padding:24px;">No GP records available for this mandal.</td></tr>';
      } else {
        tbody.innerHTML = rows.map(function (gp, idx) {
          var isDone = !gp.is_pending;
          var statusHtml = isDone
            ? '<span style="color:#059669; font-weight:700; background:#dcfce7; padding:2px 8px; border-radius:4px; font-size:0.75rem;">100% Done</span>'
            : '<span style="color:#dc2626; font-weight:700; background:#fee2e2; padding:2px 8px; border-radius:4px; font-size:0.75rem;">Pending</span>';
          var checkCell = function (val) {
            var y = ['yes', '1', 'true', 'done', 'y'].indexOf(String(val).trim().toLowerCase()) !== -1;
            return y
              ? '<span style="color:#059669; font-weight:700;">✓ Yes</span>'
              : '<span style="color:#dc2626; font-weight:700;">✗ No</span>';
          };
          var missList = Array.isArray(gp.missing_accounts) ? gp.missing_accounts : [];
          var missTxt = missList.length > 0
            ? '<span style="color:#dc2626; font-weight:700; font-size:0.8rem;">' + esc(missList.join(', ')) + '</span>'
            : '<span style="color:#64748b; font-size:0.8rem;">—</span>';
          var tel = sanitizeTel(gp.secretary_phone);
          var phoneTxt = (tel && gp.secretary_phone !== '—')
            ? '<a href="tel:' + esc(tel) + '" style="color:#0284c7; font-weight:600; text-decoration:none;">📞 ' + esc(gp.secretary_phone) + '</a>'
            : '—';
          var secTxt = '<div style="font-weight:700; font-size:0.82rem;">' + esc(gp.secretary_name || 'PS') + '</div><div style="font-size:0.75rem;">' + phoneTxt + '</div>';

          return (
            '<tr>' +
              '<td class="text-center">' + (idx + 1) + '</td>' +
              '<td><strong>' + esc(gp.panchayat_name || '') + '</strong></td>' +
              '<td class="text-center">' + statusHtml + '</td>' +
              '<td class="text-center">' + checkCell(gp.gp_pd) + '</td>' +
              '<td class="text-center">' + checkCell(gp.tgbpass) + '</td>' +
              '<td class="text-center">' + checkCell(gp.fc15_tied) + '</td>' +
              '<td class="text-center">' + checkCell(gp.fc15_untied) + '</td>' +
              (showPmagy ? '<td class="text-center">' + checkCell(gp.pmagy) + '</td>' : '') +
              '<td class="text-center">' + checkCell(gp.vwsc) + '</td>' +
              '<td class="text-center">' + checkCell(gp.mgnregs) + '</td>' +
              '<td>' + missTxt + '</td>' +
              '<td>' + secTxt + '</td>' +
            '</tr>'
          );
        }).join('');
      }
    } else {
      if (thead) {
        thead.innerHTML = buildBalanceMandalThead(showPmagy);
      }

      tbody.innerHTML = (data.mandals || []).map(function (m, idx) {
        var isDone = !m.has_pending;
        var pendNum = Number(m.not_entered_gps || 0);
        var pctNum = Number(m.pct_entered || 0);
        var statusHtml = isDone
          ? '<span style="color:#059669; font-weight:700;">100% Done</span>'
          : '<span style="color:#dc2626; font-weight:700;">' + esc(pendNum) + ' Pending</span>';
        var pairCell = function (upd, pnd) {
          var pn = Number(pnd || 0);
          return esc(upd || 0) + ' / <span style="color:' + (pn > 0 ? '#dc2626' : '#6b7280') + '; font-weight:' + (pn > 0 ? '700' : 'normal') + ';">' + esc(pn) + '</span>';
        };

        return (
          '<tr>' +
            '<td class="text-center">' + esc(m.s_no != null ? m.s_no : idx + 1) + '</td>' +
            '<td><strong>' + esc(m.mandal_name || '') + '</strong></td>' +
            '<td class="text-right"><strong>' + esc(m.total_gps || 0) + '</strong></td>' +
            '<td class="text-right" style="color:#059669; font-weight:700;">' + esc(m.entered_gps || 0) + '</td>' +
            '<td class="text-right" style="color:' + (pendNum > 0 ? '#dc2626' : '#475569') + '; font-weight:' + (pendNum > 0 ? '700' : '600') + ';">' + esc(pendNum) + '</td>' +
            '<td class="text-right"><strong style="color:' + (pctNum === 100 ? '#059669' : '#b45309') + ';">' + esc(pctNum.toFixed(1)) + '%</strong></td>' +
            '<td class="text-center">' + pairCell(m.gp_pd_updated, m.gp_pd_pending) + '</td>' +
            '<td class="text-center">' + pairCell(m.tgbpass_updated, m.tgbpass_pending) + '</td>' +
            '<td class="text-center">' + pairCell(m.fc15_tied_updated, m.fc15_tied_pending) + '</td>' +
            '<td class="text-center">' + pairCell(m.fc15_untied_updated, m.fc15_untied_pending) + '</td>' +
            (showPmagy ? '<td class="text-center">' + pairCell(m.pmagy_updated, m.pmagy_pending) + '</td>' : '') +
            '<td class="text-center">' + pairCell(m.vwsc_updated, m.vwsc_pending) + '</td>' +
            '<td class="text-center">' + pairCell(m.mgnregs_updated, m.mgnregs_pending) + '</td>' +
            '<td class="text-center" style="width:80px; white-space:nowrap;">' + statusHtml + '</td>' +
          '</tr>'
        );
      }).join('');
    }

    var pendingCard = document.getElementById('balance-pending-gps-card');
    var pendingTbody = document.getElementById('balance-pending-tbody');
    var badge = document.getElementById('pending-count-badge');
    if (Array.isArray(data.pending_gps) && data.pending_gps.length > 0) {
      if (pendingCard) pendingCard.style.display = 'block';
      if (badge) badge.textContent = data.pending_gps.length + ' Pending GP(s)';
      if (pendingTbody) {
        pendingTbody.innerHTML = data.pending_gps.map(function (gp, idx) {
          var missing = Array.isArray(gp.missing_accounts) ? gp.missing_accounts.join(', ') : '';
          return (
            '<tr>' +
              '<td class="text-center">' + (idx + 1) + '</td>' +
              '<td><strong>' + esc(gp.mandal_name || '') + '</strong></td>' +
              '<td><strong>' + esc(gp.panchayat_name || '') + '</strong></td>' +
              '<td style="color:#dc2626; font-weight:700;">' + esc(missing || 'Data Not Entered') + '</td>' +
              '<td class="text-center"><span style="color:#dc2626; font-weight:700; background:#fee2e2; padding:3px 8px; border-radius:4px; font-size:0.8rem;">Pending</span></td>' +
            '</tr>'
          );
        }).join('');
      }
    } else if (pendingCard) {
      pendingCard.style.display = 'none';
    }
  };

  window.filterBalanceTable = function () {
    var inp = document.getElementById('balance-search-input');
    var q = (inp ? inp.value : '').toLowerCase();
    document.querySelectorAll('#balance-table-tbody tr').forEach(function (r) {
      var text = (r.innerText || r.textContent || '').toLowerCase();
      r.style.display = text.indexOf(q) !== -1 ? '' : 'none';
    });
  };

  // ---------------------------------------------------------------------------
  // House Tax Collection (DCB) Station (Shared across Platform 1 & Console)
  // ---------------------------------------------------------------------------

  function resolveTaxDefaultDistrictName(sel) {
    if (!sel || !sel.options) return '';
    var savedDist = '';
    try { savedDist = sessionStorage.getItem('epts_district_name') || ''; } catch (e) {}
    var cand = savedDist.replace(/\bDistrict\b/ig, '').trim().toLowerCase();
    var firstValid = '';
    for (var i = 0; i < sel.options.length; i++) {
      var val = String(sel.options[i].value || '').trim();
      if (!val) continue;
      if (!firstValid) firstValid = val;
      if (cand && val.toLowerCase() === cand) return val;
      if (cand && (val.toLowerCase().indexOf(cand) !== -1 || cand.indexOf(val.toLowerCase()) !== -1)) return val;
    }
    return cand ? firstValid : '';
  }

  window.openTaxDcbStation = async function (options) {
    var opts = options || {};
    var isConsole = typeof window.isConsoleScope === 'function' && window.isConsoleScope();
    if (isConsole && !opts.skipAuthCheck) {
      var ok = await window.ensureDepartmentSession('tax-dcb', {
        autoGenerate: opts.autoGenerate === true,
        params: opts.params,
      });
      if (!ok) return;
    }

    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var taxStation = document.getElementById('tax-dcb-station');
    if (taxStation) {
      taxStation.style.display = 'block';
      taxStation.scrollIntoView({ behavior: 'smooth' });
      var taxBackBtn = document.getElementById('tax-btn-back');
      if (taxBackBtn) {
        var canReturnDash = !isConsole || window.isPortalAuthenticated;
        taxBackBtn.textContent = canReturnDash ? '← Back to Dashboard' : '← Back to Login / Home';
      }
    }
    if (!taxDistrictsLoaded) {
      await window.initTaxDistricts();
    }

    if (isConsole) {
      var dSel = document.getElementById('tax-district-select');
      var mSel = document.getElementById('tax-mandal-select');
      var preferredDist = (opts.params && opts.params.district) || (dSel && dSel.value) || resolveTaxDefaultDistrictName(dSel);
      if (dSel && preferredDist) {
        for (var i = 0; i < dSel.options.length; i++) {
          if (String(dSel.options[i].value).toLowerCase() === String(preferredDist).toLowerCase()) {
            dSel.value = dSel.options[i].value;
            break;
          }
        }
        await window.loadTaxMandals();
        if (mSel && opts.params && opts.params.mandal) {
          mSel.value = opts.params.mandal;
        }
        if (dSel.value && opts.autoGenerate === true) {
          await window.generateTaxReport();
        }
      }
    }
  };

  window.handleTaxBack = function () {
    var taxStation = document.getElementById('tax-dcb-station');
    if (taxStation) taxStation.style.display = 'none';
    var canReturnDash = (typeof window.isConsoleScope === 'function' && !window.isConsoleScope()) || window.isPortalAuthenticated;
    if (canReturnDash && typeof window.showDashboard === 'function') {
      window.showDashboard();
    } else if (typeof window.handleHomeNavigation === 'function') {
      window.handleHomeNavigation();
    }
  };

  window.initTaxDistricts = async function () {
    try {
      var list = await window.safeFetchJson('/api/tax/districts');
      var sel = document.getElementById('tax-district-select');
      if (sel && Array.isArray(list) && list.length > 0) {
        sel.innerHTML = '<option value="" selected>-- Select District --</option>';
        list.forEach(function (d) {
          var opt = document.createElement('option');
          var dName = typeof d === 'string' ? d : (d.district || d.name || '');
          opt.value = dName;
          opt.textContent = dName;
          sel.appendChild(opt);
        });
        taxDistrictsLoaded = true;
      }
    } catch (e) {}
    await window.loadTaxMandals();
  };

  window.loadTaxMandals = async function () {
    var distEl = document.getElementById('tax-district-select');
    var mSel = document.getElementById('tax-mandal-select');
    var dist = (distEl ? distEl.value : '').trim();
    if (!mSel) return;
    if (!dist) {
      mSel.innerHTML = '<option value="">-- Select District First --</option>';
      mSel.disabled = true;
      return;
    }
    mSel.disabled = false;
    try {
      var mList = await window.safeFetchJson('/api/tax/mandals?district=' + encodeURIComponent(dist));
      mSel.innerHTML = '<option value="">-- All Mandals --</option>';
      (Array.isArray(mList) ? mList : []).forEach(function (m) {
        var opt = document.createElement('option');
        var mName = typeof m === 'string' ? m : (m.mandal || m.name || '');
        opt.value = mName;
        opt.textContent = mName;
        mSel.appendChild(opt);
      });
    } catch (e) {}
  };

  window.onTaxDistrictChanged = async function () {
    await window.loadTaxMandals();
  };

  window.onTaxMandalChanged = function () {};

  var taxProgressInterval = null;
  function startTaxProgressTimer(title, estSeconds) {
    if (taxProgressInterval) clearInterval(taxProgressInterval);
    var card = document.getElementById('tax-progress-card');
    var elapEl = document.getElementById('tax-elapsed-time');
    var estEl = document.getElementById('tax-estimated-time');
    var pctEl = document.getElementById('tax-progress-pct');
    var fillEl = document.getElementById('tax-progress-fill');
    var statusEl = document.getElementById('tax-status-text');
    var startMs = Date.now();
    var targetSec = Math.max(6, estSeconds || 12);

    if (card) card.style.display = 'block';
    if (elapEl) elapEl.textContent = '00:00';
    if (estEl) estEl.textContent = formatMinSec(targetSec);
    if (pctEl) pctEl.textContent = '0%';
    if (fillEl) fillEl.style.width = '0%';
    if (statusEl) statusEl.textContent = title || 'Compiling DCB Ledger...';

    taxProgressInterval = setInterval(function () {
      var elapsed = Math.floor((Date.now() - startMs) / 1000);
      if (elapEl) elapEl.textContent = formatMinSec(elapsed);
      if (elapsed >= targetSec - 2) targetSec = elapsed + 4;
      if (estEl) estEl.textContent = formatMinSec(Math.max(0, targetSec - elapsed));
      var pct = Math.min(96, Math.round((elapsed / Math.max(1, targetSec)) * 96));
      if (pctEl) pctEl.textContent = pct + '%';
      if (fillEl) fillEl.style.width = pct + '%';
    }, 250);
  }

  function finishTaxProgressTimer(success) {
    if (taxProgressInterval) {
      clearInterval(taxProgressInterval);
      taxProgressInterval = null;
    }
    var estEl = document.getElementById('tax-estimated-time');
    var pctEl = document.getElementById('tax-progress-pct');
    var fillEl = document.getElementById('tax-progress-fill');
    var statusEl = document.getElementById('tax-status-text');
    var card = document.getElementById('tax-progress-card');
    if (success) {
      if (estEl) estEl.textContent = '00:00';
      if (pctEl) pctEl.textContent = '100%';
      if (fillEl) fillEl.style.width = '100%';
      if (statusEl) statusEl.textContent = 'DCB report compiled successfully!';
      setTimeout(function () {
        if (card) card.style.display = 'none';
      }, 1200);
    } else {
      if (estEl) estEl.textContent = '--:--';
      if (statusEl) statusEl.textContent = 'DCB processing halted.';
    }
  }

  window.generateTaxReport = async function () {
    var distEl = document.getElementById('tax-district-select');
    var dist = (distEl ? distEl.value : '').trim();
    if (!dist) {
      showNotice('Please select a District first to generate the DCB Report.', 'error');
      if (distEl) distEl.focus();
      return;
    }
    var btn = document.getElementById('btn-tax-generate');
    var origHtml = btn ? btn.innerHTML : '⚡ Generate DCB Report';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Compiling DCB Report...';
    }
    startTaxProgressTimer('Compiling House Tax DCB Report for ' + dist + '...', 12);
    try {
      await window.loadTaxData();
      finishTaxProgressTimer(true);
    } catch (err) {
      finishTaxProgressTimer(false);
      if (!(typeof window.isConsoleScope === 'function' && window.isConsoleScope() && handleDepartmentSessionExpiredError(err, 'tax-dcb'))) {
        showNotice('Failed to compile DCB report: ' + err.message, 'error');
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
  };

  window.refreshTaxDataLive = async function () {
    var btn = document.getElementById('btn-tax-refresh');
    var origHtml = btn ? btn.innerHTML : '🔄 Refresh Live Data';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Fetching Live Portal Data...';
    }
    startTaxProgressTimer('Synchronizing fresh live DCB data from e-Panchayat portal...', 20);
    try {
      var result = await window.safeFetchJson('/api/tax/refresh', { method: 'POST' });
      taxDataCache = null;
      await window.initTaxDistricts();
      var dist = ((document.getElementById('tax-district-select') && document.getElementById('tax-district-select').value) || '').trim();
      if (dist) {
        await window.loadTaxData();
      }
      finishTaxProgressTimer(true);
      showNotice('Fresh live DCB data synchronized (' + (result.total_gps || 0) + ' GP rows).', 'success');
    } catch (err) {
      finishTaxProgressTimer(false);
      showNotice('Notice while refreshing live tax data: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
  };

  window.resetTaxStatistics = function () {
    var dSel = document.getElementById('tax-district-select');
    var mSel = document.getElementById('tax-mandal-select');
    var sInput = document.getElementById('tax-search-input');

    if (dSel) dSel.value = '';
    if (mSel) {
      mSel.value = '';
      mSel.innerHTML = '<option value="">-- Select District First --</option>';
      mSel.disabled = true;
    }
    if (sInput) sInput.value = '';

    var map = {
      'tax-kpi-mandals': '—',
      'tax-kpi-mandals-sub': 'District Total',
      'tax-kpi-gps': '—',
      'tax-kpi-assessments': 'Assessments: —',
      'tax-kpi-demand': '—',
      'tax-kpi-demand-sub': 'Arrear: — | Current: —',
      'tax-kpi-collection': '—',
      'tax-kpi-coll-sub': 'Arrear: — | Current: —',
      'tax-kpi-balance': '—',
      'tax-kpi-bal-sub': 'Arrear: — | Current: —',
      'tax-kpi-pct': '—%',
      'tax-abstract-count': '-- Mandals',
      'tax-detail-count': '-- GPs',
      'tax-abstract-dist-label': 'Select District',
    };
    Object.keys(map).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.textContent = map[id];
    });

    var promptHtml = '<tr><td colspan="12" style="text-align:center; padding:35px 20px; color:var(--text-muted); font-size:0.95rem;">e-Panchayat Automation is ready — select District &amp; Mandal above and click <strong>⚡ Generate DCB Report</strong> to compile House Tax statistics.</td></tr>';
    var mBody = document.getElementById('tax-mandal-tbody');
    if (mBody) mBody.innerHTML = promptHtml;
    var gpBody = document.getElementById('tax-gp-tbody');
    if (gpBody) gpBody.innerHTML = promptHtml;

    var iframe = document.getElementById('tax-pdf-iframe');
    if (iframe) iframe.src = 'about:blank';

    window.switchTaxTab('abstract');
    taxDataCache = null;
  };

  window.loadTaxData = async function () {
    var dist = ((document.getElementById('tax-district-select') && document.getElementById('tax-district-select').value) || '').trim();
    if (!dist) return;
    var mandal = ((document.getElementById('tax-mandal-select') && document.getElementById('tax-mandal-select').value) || '').trim();
    var distLbl = document.getElementById('tax-abstract-dist-label');
    if (distLbl) distLbl.textContent = dist;

    var pdfUrl = buildTaxInlinePdfUrl(dist, mandal);
    var fsBtn = document.getElementById('tax-pdf-fullscreen-btn');
    if (fsBtn) fsBtn.href = pdfUrl;
    var iframe = document.getElementById('tax-pdf-iframe');
    if (iframe && currentTaxTab === 'pdf') {
      iframe.src = pdfUrl;
    }

    var apiUrl = '/api/tax/data?district=' + encodeURIComponent(dist) + '&_t=' + Date.now();
    if (mandal) apiUrl += '&mandal=' + encodeURIComponent(mandal);
    var data = await window.safeFetchJson(apiUrl);
    taxDataCache = data;
    window.renderTaxDashboard(data);
  };

  function formatTaxCurrency(val) {
    if (val === null || val === undefined || isNaN(val)) return '₹0';
    var num = Number(val);
    if (Math.abs(num) >= 10000000) return '₹' + (num / 10000000).toFixed(2) + ' Cr';
    if (Math.abs(num) >= 100000) return '₹' + (num / 100000).toFixed(2) + ' L';
    return '₹' + num.toLocaleString('en-IN');
  }

  window.renderTaxDashboard = function (data) {
    if (!data) return;
    var s = data.summary || data.stats || {};
    var el;
    el = document.getElementById('tax-kpi-mandals');
    if (el) el.textContent = s.total_mandals != null ? s.total_mandals : (data.mandal_abstract ? data.mandal_abstract.length : '0');
    el = document.getElementById('tax-kpi-gps');
    if (el) el.textContent = s.total_gps != null ? s.total_gps : (data.records ? data.records.length : '0');
    el = document.getElementById('tax-kpi-assessments');
    if (el) el.textContent = 'Assessments: ' + (s.total_assessments ? Number(s.total_assessments).toLocaleString('en-IN') : '0');

    el = document.getElementById('tax-kpi-demand'); if (el) el.textContent = formatTaxCurrency(s.total_demand);
    el = document.getElementById('tax-kpi-demand-sub'); if (el) el.textContent = 'Arrear: ' + formatTaxCurrency(s.demand_arrear) + ' | Current: ' + formatTaxCurrency(s.demand_current);
    el = document.getElementById('tax-kpi-collection'); if (el) el.textContent = formatTaxCurrency(s.total_collection);
    el = document.getElementById('tax-kpi-coll-sub'); if (el) el.textContent = 'Arrear: ' + formatTaxCurrency(s.collection_arrear) + ' | Current: ' + formatTaxCurrency(s.collection_current);
    el = document.getElementById('tax-kpi-balance'); if (el) el.textContent = formatTaxCurrency(s.total_balance);
    el = document.getElementById('tax-kpi-bal-sub'); if (el) el.textContent = 'Arrear: ' + formatTaxCurrency(s.balance_arrear) + ' | Current: ' + formatTaxCurrency(s.balance_current);

    var pct = s.overall_percentage != null ? Number(s.overall_percentage).toFixed(1) : '0.0';
    el = document.getElementById('tax-kpi-pct'); if (el) el.textContent = pct + '%';

    var mandalRows = data.mandal_abstract || data.mandals || [];
    var gpRows = data.records || data.gps || [];
    window.renderTaxAbstractTable(mandalRows);
    window.renderTaxDetailTable(gpRows);

    if (data.is_mandal_level && mandalRows.length === 0 && currentTaxTab === 'abstract') {
      window.switchTaxTab('detail');
    }
  };

  window.renderTaxAbstractTable = function (mandals) {
    var tbody = document.getElementById('tax-mandal-tbody');
    var countLbl = document.getElementById('tax-abstract-count');
    if (countLbl) countLbl.textContent = mandals.length + ' Mandals';
    if (!tbody) return;
    if (mandals.length === 0) {
      tbody.innerHTML = '<tr><td colspan="12" style="text-align:center; padding:30px; color:#6b7280;">e-Panchayat Automation: No mandals found for the selected filter.</td></tr>';
      return;
    }
    tbody.innerHTML = mandals.map(function (m, idx) {
      var pctNum = m.percentage != null ? Number(m.percentage) : 0;
      return (
        '<tr>' +
          '<td style="text-align:center;">' + (idx + 1) + '</td>' +
          '<td><strong>' + esc(m.mandal || '') + '</strong></td>' +
          '<td style="text-align:right;">' + esc(m.total_gps || 0) + '</td>' +
          '<td style="text-align:right;">' + esc(Number(m.assessments || 0).toLocaleString('en-IN')) + '</td>' +
          '<td style="text-align:right;">' + esc(formatTaxCurrency(m.demand_arrear)) + '</td>' +
          '<td style="text-align:right;">' + esc(formatTaxCurrency(m.demand_current)) + '</td>' +
          '<td style="text-align:right;"><strong>' + esc(formatTaxCurrency(m.demand_total)) + '</strong></td>' +
          '<td style="text-align:right; color:#059669;">' + esc(formatTaxCurrency(m.collection_arrear)) + '</td>' +
          '<td style="text-align:right; color:#059669;">' + esc(formatTaxCurrency(m.collection_current || m.current_collection)) + '</td>' +
          '<td style="text-align:right; color:#059669;"><strong>' + esc(formatTaxCurrency(m.collection_total)) + '</strong></td>' +
          '<td style="text-align:right; color:#dc2626;"><strong>' + esc(formatTaxCurrency(m.balance_total)) + '</strong></td>' +
          '<td style="text-align:right; font-weight:700; color:' + (pctNum >= 70 ? '#059669' : '#b45309') + ';">' + esc(pctNum.toFixed(1)) + '%</td>' +
        '</tr>'
      );
    }).join('');
  };

  window.renderTaxDetailTable = function (gps) {
    var tbody = document.getElementById('tax-gp-tbody');
    var countLbl = document.getElementById('tax-detail-count');
    if (countLbl) countLbl.textContent = gps.length + ' Gram Panchayats';
    if (!tbody) return;
    if (gps.length === 0) {
      tbody.innerHTML = '<tr><td colspan="12" style="text-align:center; padding:30px; color:#6b7280;">e-Panchayat Automation: No Gram Panchayats found for the selected filter.</td></tr>';
      return;
    }
    var slice = gps.slice(0, 200);
    var html = slice.map(function (gp, idx) {
      var pctNum = gp.percentage != null ? Number(gp.percentage) : 0;
      return (
        '<tr>' +
          '<td style="text-align:center;">' + (idx + 1) + '</td>' +
          '<td>' + esc(gp.mandal || '') + '</td>' +
          '<td><strong>' + esc(gp.panchayat || gp.gp_name || '') + '</strong></td>' +
          '<td style="text-align:right;">' + esc(Number(gp.assessments || 0).toLocaleString('en-IN')) + '</td>' +
          '<td style="text-align:right;">' + esc(formatTaxCurrency(gp.demand_arrear)) + '</td>' +
          '<td style="text-align:right;">' + esc(formatTaxCurrency(gp.demand_current)) + '</td>' +
          '<td style="text-align:right;"><strong>' + esc(formatTaxCurrency(gp.demand_total)) + '</strong></td>' +
          '<td style="text-align:right; color:#059669;">' + esc(formatTaxCurrency(gp.collection_arrear)) + '</td>' +
          '<td style="text-align:right; color:#059669;">' + esc(formatTaxCurrency(gp.collection_current || gp.current_collection)) + '</td>' +
          '<td style="text-align:right; color:#059669;"><strong>' + esc(formatTaxCurrency(gp.collection_total)) + '</strong></td>' +
          '<td style="text-align:right; color:#dc2626;"><strong>' + esc(formatTaxCurrency(gp.balance_total)) + '</strong></td>' +
          '<td style="text-align:right; font-weight:700; color:' + (pctNum >= 70 ? '#059669' : '#b45309') + ';">' + esc(pctNum.toFixed(1)) + '%</td>' +
        '</tr>'
      );
    }).join('');
    if (gps.length > 200) {
      html += '<tr><td colspan="12" style="text-align:center; padding:12px; background:#f9fafb; font-weight:600; color:#6b7280;">Showing first 200 of ' + esc(gps.length) + ' GPs. Use Search or Filter by Mandal to narrow results.</td></tr>';
    }
    tbody.innerHTML = html;
  };

  window.filterTaxTables = function () {
    var inp = document.getElementById('tax-search-input');
    var q = (inp ? inp.value : '').toLowerCase().trim();
    ['#tax-mandal-tbody tr', '#tax-gp-tbody tr'].forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (r) {
        var text = (r.innerText || r.textContent || '').toLowerCase();
        r.style.display = text.indexOf(q) !== -1 ? '' : 'none';
      });
    });
  };

  window.switchTaxTab = function (tab) {
    currentTaxTab = tab;
    var btnAbs = document.getElementById('tax-tab-btn-abstract');
    var btnDet = document.getElementById('tax-tab-btn-detail');
    var btnPdf = document.getElementById('tax-tab-btn-pdf');
    var paneAbs = document.getElementById('tax-pane-abstract');
    var paneDet = document.getElementById('tax-pane-detail');
    var panePdf = document.getElementById('tax-pane-pdf');

    [btnAbs, btnDet, btnPdf].forEach(function (b) {
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
        var dist = ((document.getElementById('tax-district-select') && document.getElementById('tax-district-select').value) || '').trim();
        var iframe = document.getElementById('tax-pdf-iframe');
        if (!dist) {
          if (iframe) iframe.src = 'about:blank';
          return;
        }
        var mandal = ((document.getElementById('tax-mandal-select') && document.getElementById('tax-mandal-select').value) || '').trim();
        var pdfUrl = buildTaxInlinePdfUrl(dist, mandal);
        if (iframe && iframe.src !== pdfUrl) iframe.src = pdfUrl;
      }
    }
  };

  function validateTaxSelectionForDownload() {
    var dist = ((document.getElementById('tax-district-select') && document.getElementById('tax-district-select').value) || '').trim();
    if (!dist) {
      showNotice('Please select a District first.', 'error');
      return null;
    }
    if (!taxDataCache) {
      showNotice('Please click "⚡ Generate DCB Report" first before downloading.', 'error');
      return null;
    }
    var mandal = ((document.getElementById('tax-mandal-select') && document.getElementById('tax-mandal-select').value) || '').trim();
    return { dist: dist, mandal: mandal };
  }

  function finalizeTaxAssetUrl(url) {
    if (window.DeptSessionManager && window.DeptSessionManager.isConsoleContext()) {
      return window.DeptSessionManager.appendSessionParam(url);
    }
    return url;
  }

  function buildTaxInlinePdfUrl(dist, mandal) {
    var pdfUrl = '/api/tax/report.pdf?district=' + encodeURIComponent(dist) + '&_t=' + Date.now();
    if (mandal) pdfUrl += '&mandal=' + encodeURIComponent(mandal);
    return finalizeTaxAssetUrl(pdfUrl);
  }

  window.openTaxFullscreenPdf = function (event) {
    var sel = validateTaxSelectionForDownload();
    if (!sel) {
      if (event && typeof event.preventDefault === 'function') event.preventDefault();
      return false;
    }
    var inlineUrl = buildTaxInlinePdfUrl(sel.dist, sel.mandal);
    var fsBtn = document.getElementById('tax-pdf-fullscreen-btn');
    if (fsBtn) fsBtn.href = inlineUrl;
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    window.open(inlineUrl, '_blank', 'noopener,noreferrer');
    return false;
  };

  window.downloadTaxPdf = function () {
    var sel = validateTaxSelectionForDownload();
    if (!sel) return;
    var url = '/api/tax/download-pdf?district=' + encodeURIComponent(sel.dist);
    if (sel.mandal) url += '&mandal=' + encodeURIComponent(sel.mandal);
    window.open(finalizeTaxAssetUrl(url), '_blank');
  };

  window.downloadTaxExcel = function () {
    var sel = validateTaxSelectionForDownload();
    if (!sel) return;
    var url = '/api/tax/download?district=' + encodeURIComponent(sel.dist);
    if (sel.mandal) url += '&mandal=' + encodeURIComponent(sel.mandal);
    window.location.href = finalizeTaxAssetUrl(url);
  };

  window.downloadTaxPbiPdf = function () {
    var sel = validateTaxSelectionForDownload();
    if (!sel) return;
    var url = '/api/tax/powerbi-report.pdf?district=' + encodeURIComponent(sel.dist);
    if (sel.mandal) url += '&mandal=' + encodeURIComponent(sel.mandal);
    window.open(finalizeTaxAssetUrl(url), '_blank');
  };

  // ---------------------------------------------------------------------------
  // GP Inspections Monitoring Station (#inspections-station - GM-R 39.1)
  // ---------------------------------------------------------------------------

  var inspTimerInterval = null;

  function countSelectedInspWeeks(fromWeek, toWeek) {
    if (!inspWeeksCache || !inspWeeksCache.length) return 1;
    var fIdx = -1;
    var tIdx = -1;
    for (var i = 0; i < inspWeeksCache.length; i++) {
      var wv = String(inspWeeksCache[i].value || '').trim();
      var wt = String(inspWeeksCache[i].text || '').trim();
      if (fIdx === -1 && (wv === fromWeek || wt === fromWeek)) fIdx = i;
      if (tIdx === -1 && (wv === toWeek || wt === toWeek)) tIdx = i;
    }
    if (fIdx === -1 && tIdx === -1) return 1;
    if (fIdx === -1 || tIdx === -1) return 1;
    return Math.abs(fIdx - tIdx) + 1;
  }

  function startInspProgressTimer(estSeconds, statusMsg) {
    if (inspTimerInterval) clearInterval(inspTimerInterval);
    var strip = document.getElementById('insp-progress-strip');
    var elapEl = document.getElementById('insp-elapsed-time');
    var estEl = document.getElementById('insp-estimated-time');
    var pctEl = document.getElementById('insp-progress-pct');
    var fillEl = document.getElementById('insp-progress-fill');
    var statusEl = document.getElementById('insp-status-text');
    var startMs = Date.now();
    var targetSec = Math.max(8, estSeconds || 12);

    if (strip) strip.style.display = 'block';
    if (elapEl) elapEl.textContent = '00:00';
    if (estEl) estEl.textContent = formatMinSec(targetSec);
    if (pctEl) pctEl.textContent = '0%';
    if (fillEl) fillEl.style.width = '0%';
    if (statusEl) statusEl.textContent = statusMsg || 'Iterating weeks and compiling GM-R 39.1 inspection reports...';

    inspTimerInterval = setInterval(function () {
      var elapsed = Math.floor((Date.now() - startMs) / 1000);
      if (elapEl) elapEl.textContent = formatMinSec(elapsed);
      if (elapsed >= targetSec - 2) targetSec = elapsed + 5;
      if (estEl) estEl.textContent = formatMinSec(Math.max(0, targetSec - elapsed));
      var pct = Math.min(96, Math.round((elapsed / Math.max(1, targetSec)) * 96));
      if (pctEl) pctEl.textContent = pct + '%';
      if (fillEl) fillEl.style.width = pct + '%';
    }, 250);
  }

  function finishInspProgressTimer(success) {
    if (inspTimerInterval) {
      clearInterval(inspTimerInterval);
      inspTimerInterval = null;
    }
    var estEl = document.getElementById('insp-estimated-time');
    var pctEl = document.getElementById('insp-progress-pct');
    var fillEl = document.getElementById('insp-progress-fill');
    var statusEl = document.getElementById('insp-status-text');
    if (success) {
      if (estEl) estEl.textContent = '00:00';
      if (pctEl) pctEl.textContent = '100%';
      if (fillEl) fillEl.style.width = '100%';
      if (statusEl) statusEl.textContent = 'Inspections abstract compiled successfully!';
    } else {
      if (estEl) estEl.textContent = '--:--';
      if (statusEl) statusEl.textContent = 'Inspections robot halted.';
    }
  }

  function getInspTargetMeta(desig) {
    var d = String(desig || 'MPO').trim();
    if (d === 'MPO' || d === 'MPDO') {
      return { level: 'Mandal', plural: 'Mandals', rule: d + 's Inspection Target: Weekly 4 • Filter: Final Submit Status = Submitted Only' };
    }
    if (d === 'DLPO') {
      return { level: 'Division', plural: 'Divisions', rule: 'DLPOs Inspection Target: Monthly 10 • Filter: Final Submit Status = Submitted Only' };
    }
    return { level: 'District', plural: 'Districts', rule: d + 's Inspection Target: Monthly 5 • Filter: Final Submit Status = Submitted Only' };
  }

  window.updateInspectionTargetBanner = function () {
    var desig = (document.getElementById('insp-designation') && document.getElementById('insp-designation').value) || 'MPO';
    var meta = getInspTargetMeta(desig);
    var bannerText = document.getElementById('insp-target-rule-text');
    var searchLbl = document.getElementById('insp-search-unit-label');
    var colHdr = document.getElementById('insp-col-unit-header');
    var unitsLbl = document.getElementById('insp-kpi-units-label');
    if (bannerText) bannerText.textContent = meta.rule;
    if (searchLbl) searchLbl.textContent = meta.level;
    if (colHdr) colHdr.textContent = meta.level;
    if (unitsLbl && !inspCurrentReport) unitsLbl.textContent = 'Total ' + meta.plural;
  };

  window.resetInspectionsView = function () {
    inspCurrentReport = null;
    inspFilteredCache = [];
    inspActiveMonthKey = 'all';

    var actionsWrap = document.getElementById('insp-actions-wrap');
    if (actionsWrap) actionsWrap.style.display = 'none';

    var monthTabs = document.getElementById('insp-month-tabs');
    if (monthTabs) {
      monthTabs.style.display = 'none';
      monthTabs.innerHTML = '';
    }

    var el;
    el = document.getElementById('insp-kpi-mandals'); if (el) el.textContent = '0';
    el = document.getElementById('insp-kpi-target'); if (el) el.textContent = '0';
    el = document.getElementById('insp-kpi-completed'); if (el) el.textContent = '0';
    el = document.getElementById('insp-kpi-pending'); if (el) el.textContent = '0';
    el = document.getElementById('insp-kpi-rate'); if (el) el.textContent = '0.00%';
    el = document.getElementById('insp-table-counter'); if (el) el.textContent = 'Ready';
    el = document.getElementById('insp-table-title');
    if (el) el.textContent = 'GM-R 39.1 Consolidated Abstract (Final Submit Status: Submitted Only)';

    var tbody = document.getElementById('insp-table-body');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:28px; color:#64748b;">Select Designation &amp; From–To Weeks above and click <strong>⚡ Run Inspections Robot</strong> (or upload weekly Excel files).</td></tr>';
    }

    var searchEl = document.getElementById('insp-search-input');
    if (searchEl) searchEl.value = '';

    var pStrip = document.getElementById('insp-progress-strip');
    if (pStrip) pStrip.style.display = 'none';

    var syncEl = document.getElementById('insp-sync-time');
    if (syncEl) {
      syncEl.textContent = 'Status: Select Officer Designation and click "Fetch Portal Weeks" (or upload GM-R 39.1 weekly Excel files).';
    }

    window.updateInspectionTargetBanner();
  };

  window.openGpInspectionsStation = async function (options) {
    var opts = options || {};
    if (!opts.skipAuthCheck && typeof window.ensureDepartmentSession === 'function') {
      var ok = await window.ensureDepartmentSession('inspections', {
        autoGenerate: opts.autoGenerate === true,
        params: opts.params,
      });
      if (!ok) return;
    }

    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var inspStation = document.getElementById('inspections-station');
    if (inspStation) {
      inspStation.style.display = 'block';
      inspStation.scrollIntoView({ behavior: 'smooth' });
    }

    if (opts.params) {
      var desEl = document.getElementById('insp-designation');
      if (desEl && opts.params.designation) desEl.value = opts.params.designation;
    }

    // Always reset the view so previously generated reports are never automatically displayed
    // and all download options remain strictly hidden until the Run/Generate button is clicked.
    window.resetInspectionsView();

    if (inspWeeksCache.length === 0) {
      await window.fetchInspectionWeeks(false, opts.params);
    }
    if (opts.autoGenerate === true) {
      await window.runInspectionsRobot();
    }
  };

  var inspMonthsCache = [];
  var inspActiveMonthKey = 'all';

  function parseMondayMonthFromWeekText(weekTxt) {
    var m = String(weekTxt || '').match(/(\d{4})[-/](\d{2})[-/](\d{2})/);
    if (!m) return null;
    var dt = new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
    if (isNaN(dt.getTime())) return null;
    // Shift to Monday (Mon=0..Sun=6 via (getDay()+6)%7)
    var offset = (dt.getDay() + 6) % 7;
    dt.setDate(dt.getDate() - offset);
    var yr = dt.getFullYear();
    var mo = dt.getMonth() + 1;
    var key = yr + '-' + (mo < 10 ? '0' + mo : String(mo));
    var names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return { key: key, label: names[mo - 1] + ' ' + yr, year: yr, month: mo };
  }

  function buildInspMonthsFromWeeks(weeks, serverMonths) {
    if (Array.isArray(serverMonths) && serverMonths.length > 0) {
      return serverMonths;
    }
    var byKey = {};
    (weeks || []).forEach(function (w) {
      var meta = parseMondayMonthFromWeekText(w.text || w.value || '');
      if (!meta) return;
      if (!byKey[meta.key]) {
        byKey[meta.key] = { key: meta.key, label: meta.label, year: meta.year, month: meta.month, weeks: [] };
      }
      byKey[meta.key].weeks.push(w);
    });
    return Object.keys(byKey).sort().map(function (k) {
      var item = byKey[k];
      return {
        key: item.key,
        label: item.label,
        year: item.year,
        month: item.month,
        week_count: item.weeks.length,
        from_week: item.weeks[0].text,
        to_week: item.weeks[item.weeks.length - 1].text,
        weeks: item.weeks,
      };
    });
  }

  function countWeeksForMonthRange(fromM, toM) {
    var lo = fromM <= toM ? fromM : toM;
    var hi = fromM <= toM ? toM : fromM;
    var cnt = 0;
    (inspMonthsCache || []).forEach(function (m) {
      if (m.key >= lo && m.key <= hi) cnt += Number(m.week_count || (m.weeks ? m.weeks.length : 0));
    });
    return Math.max(1, cnt);
  }

  window.onInspectionPeriodModeChanged = function () {
    var mode = (document.getElementById('insp-period-mode') && document.getElementById('insp-period-mode').value) || 'weeks';
    var isMonths = mode === 'months';
    var fw = document.getElementById('insp-from-week-wrap');
    var tw = document.getElementById('insp-to-week-wrap');
    var fm = document.getElementById('insp-from-month-wrap');
    var tm = document.getElementById('insp-to-month-wrap');
    var prev = document.getElementById('insp-month-weeks-preview');
    if (fw) fw.style.display = isMonths ? 'none' : 'block';
    if (tw) tw.style.display = isMonths ? 'none' : 'block';
    if (fm) fm.style.display = isMonths ? 'block' : 'none';
    if (tm) tm.style.display = isMonths ? 'block' : 'none';
    if (prev) prev.style.display = isMonths ? 'block' : 'none';
    if (isMonths) window.updateInspectionMonthPreview();
    window.resetInspectionsView();
  };

  window.updateInspectionMonthPreview = function () {
    var prev = document.getElementById('insp-month-weeks-preview');
    if (!prev) return;
    var fm = (document.getElementById('insp-from-month') && document.getElementById('insp-from-month').value) || '';
    var tm = (document.getElementById('insp-to-month') && document.getElementById('insp-to-month').value) || fm;
    if (!fm || !inspMonthsCache.length) {
      prev.textContent = 'Monday-Start Rule: Click "Fetch Portal Weeks" to group weeks into calendar months automatically.';
      return;
    }
    var lo = fm <= tm ? fm : tm;
    var hi = fm <= tm ? tm : fm;
    var matched = inspMonthsCache.filter(function (m) { return m.key >= lo && m.key <= hi; });
    var totalW = matched.reduce(function (a, m) { return a + Number(m.week_count || 0); }, 0);
    var summary = matched.map(function (m) {
      return m.label + ' (' + m.week_count + 'w: ' + m.from_week + (m.to_week && m.to_week !== m.from_week ? ' -> ' + m.to_week : '') + ')';
    }).join(' | ');
    prev.textContent = 'Monday-Allocated Weeks (' + totalW + ' total): ' + (summary || 'None');
  };

  window.onInspectionDesignationChanged = function () {
    window.resetInspectionsView();
    inspWeeksCache = [];
    inspMonthsCache = [];
    if (window.isDeptAuthenticated) {
      window.fetchInspectionWeeks(false);
    }
  };

  window.fetchInspectionWeeks = async function (explicitClick, pendingParams) {
    var syncEl = document.getElementById('insp-sync-time');
    var desEl = document.getElementById('insp-designation');
    var fromEl = document.getElementById('insp-from-week');
    var toEl = document.getElementById('insp-to-week');
    var fmEl = document.getElementById('insp-from-month');
    var tmEl = document.getElementById('insp-to-month');
    var btn = document.getElementById('btn-fetch-insp-weeks');
    var desig = (desEl && desEl.value) || 'MPO';

    if (btn) btn.disabled = true;
    if (syncEl) syncEl.textContent = 'Connecting to GM-R 39.1 inside shared session to load available From–To weeks...';

    try {
      var res = await window.safeFetchJson('/api/inspections/weeks?designation=' + encodeURIComponent(desig));
      var weeks = (res && res.weeks) || [];
      inspWeeksCache = weeks;
      inspMonthsCache = buildInspMonthsFromWeeks(weeks, res && res.months);
      if (fromEl && toEl) {
        if (!weeks.length) {
          fromEl.innerHTML = '<option value="">No weeks found on portal</option>';
          toEl.innerHTML = '<option value="">No weeks found on portal</option>';
        } else {
          var optsHtml = weeks.map(function (w) {
            return '<option value="' + esc(w.value) + '">' + esc(w.text) + '</option>';
          }).join('');
          fromEl.innerHTML = optsHtml;
          toEl.innerHTML = optsHtml;
          if (pendingParams && pendingParams.from_week) fromEl.value = pendingParams.from_week;
          if (pendingParams && pendingParams.to_week) toEl.value = pendingParams.to_week;
        }
      }
      if (fmEl && tmEl) {
        if (!inspMonthsCache.length) {
          fmEl.innerHTML = '<option value="">No months available</option>';
          tmEl.innerHTML = '<option value="">No months available</option>';
        } else {
          var mHtml = inspMonthsCache.map(function (m) {
            return '<option value="' + esc(m.key) + '">' + esc(m.label) + ' (' + esc(m.week_count) + ' Weeks)</option>';
          }).join('');
          fmEl.innerHTML = mHtml;
          tmEl.innerHTML = mHtml;
          fmEl.selectedIndex = Math.max(0, inspMonthsCache.length - 1);
          tmEl.selectedIndex = Math.max(0, inspMonthsCache.length - 1);
          window.updateInspectionMonthPreview();
        }
      }
      if (syncEl) {
        syncEl.textContent = weeks.length
          ? ('Loaded ' + weeks.length + ' weekly inspection period(s) across ' + inspMonthsCache.length + ' month(s) for ' + desig + '. Select Week Range or Month-Wise Range and click Run.')
          : ('GM-R 39.1 returned no weekly options for ' + desig + '.');
      }
      if (explicitClick) showNotice('Loaded ' + weeks.length + ' weeks from GM-R 39.1 for ' + desig + '.', 'success');
    } catch (err) {
      if (handleDepartmentSessionExpiredError(err, 'inspections', { designation: desig })) return;
      if (syncEl) syncEl.textContent = 'Week load note: ' + (err.message || 'Connect Departmental Login first.');
      if (explicitClick) showNotice('Could not load GM-R 39.1 weeks: ' + err.message, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  window.runInspectionsRobot = async function () {
    var desig = (document.getElementById('insp-designation') && document.getElementById('insp-designation').value) || 'MPO';
    var mode = (document.getElementById('insp-period-mode') && document.getElementById('insp-period-mode').value) || 'weeks';
    var fromWeek = (document.getElementById('insp-from-week') && document.getElementById('insp-from-week').value) || '';
    var toWeek = (document.getElementById('insp-to-week') && document.getElementById('insp-to-week').value) || fromWeek;
    var fromMonth = (document.getElementById('insp-from-month') && document.getElementById('insp-from-month').value) || '';
    var toMonth = (document.getElementById('insp-to-month') && document.getElementById('insp-to-month').value) || fromMonth;
    var overrideVal = (document.getElementById('insp-target-override') && document.getElementById('insp-target-override').value) || '';
    var btn = document.getElementById('btn-run-inspections-robot');
    var syncEl = document.getElementById('insp-sync-time');
    var actionsWrap = document.getElementById('insp-actions-wrap');

    // Ensure download options are hidden until generation succeeds
    if (actionsWrap) actionsWrap.style.display = 'none';

    var wkCnt = (mode === 'months' && fromMonth)
      ? countWeeksForMonthRange(fromMonth, toMonth)
      : countSelectedInspWeeks(fromWeek, toWeek);
    startInspProgressTimer(Math.max(10, wkCnt * 4 + 6));

    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '⏳ Running GM-R 39.1 Robot...';
    }
    if (syncEl) syncEl.textContent = 'Iterating ' + wkCnt + ' week(s) in GM-R 39.1, downloading Excel reports, and consolidating Submitted inspections...';

    try {
      var fd = new FormData();
      fd.append('designation', desig);
      if (mode === 'months' && fromMonth) {
        fd.append('from_month', fromMonth);
        fd.append('to_month', toMonth || fromMonth);
      } else {
        if (fromWeek) fd.append('from_week', fromWeek);
        if (toWeek) fd.append('to_week', toWeek);
      }
      if (overrideVal && parseInt(overrideVal, 10) > 0) {
        fd.append('target_override', String(parseInt(overrideVal, 10)));
      }
      var data = await window.safeFetchJson('/api/inspections/generate', {
        method: 'POST',
        body: fd,
      });
      finishInspProgressTimer(true);
      inspActiveMonthKey = 'all';
      window.renderInspectionsReport(data);
      showNotice('Compiled GM-R 39.1 ' + data.designation + ' Inspection Abstract (' + (data.weeks_count || 1) + ' week(s)).', 'success');
    } catch (err) {
      finishInspProgressTimer(false);
      if (actionsWrap) actionsWrap.style.display = 'none';
      if (handleDepartmentSessionExpiredError(err, 'inspections', { designation: desig, from_week: fromWeek, to_week: toWeek })) return;
      if (syncEl) syncEl.textContent = 'Error: ' + err.message;
      showNotice('Inspections Robot error: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '⚡ Run Inspections Robot';
      }
    }
  };

  window.uploadConsolidateInspections = async function (fileList) {
    if (!fileList || !fileList.length) return;
    var actionsWrap = document.getElementById('insp-actions-wrap');
    if (actionsWrap) actionsWrap.style.display = 'none';

    var desig = (document.getElementById('insp-designation') && document.getElementById('insp-designation').value) || 'MPO';
    var overrideVal = (document.getElementById('insp-target-override') && document.getElementById('insp-target-override').value) || '';
    var syncEl = document.getElementById('insp-sync-time');
    if (syncEl) syncEl.textContent = 'Consolidating ' + fileList.length + ' uploaded GM-R 39.1 Excel file(s) (Final Submit Status = Submitted only)...';

    try {
      var fd = new FormData();
      for (var i = 0; i < fileList.length; i++) {
        fd.append('files', fileList[i]);
      }
      fd.append('designation', desig);
      if (overrideVal && parseInt(overrideVal, 10) > 0) {
        fd.append('target_override', String(parseInt(overrideVal, 10)));
      }
      var data = await window.safeFetchJson('/api/inspections/upload-consolidate', {
        method: 'POST',
        body: fd,
      });
      window.renderInspectionsReport(data);
      showNotice('Consolidated ' + fileList.length + ' weekly Excel file(s) successfully.', 'success');
    } catch (err) {
      if (actionsWrap) actionsWrap.style.display = 'none';
      if (syncEl) syncEl.textContent = 'Consolidation error: ' + err.message;
      showNotice('Excel consolidation error: ' + err.message, 'error');
    } finally {
      var inp = document.getElementById('insp-upload-files');
      if (inp) inp.value = '';
    }
  };

  window.selectInspectionMonthTab = function (monthKey) {
    inspActiveMonthKey = monthKey || 'all';
    window.renderInspectionMonthTabs();
    window.filterInspectionsTable();
  };

  window.renderInspectionMonthTabs = function () {
    var wrap = document.getElementById('insp-month-tabs');
    if (!wrap) return;
    var secs = (inspCurrentReport && Array.isArray(inspCurrentReport.monthly_sections))
      ? inspCurrentReport.monthly_sections
      : [];
    if (secs.length === 0) {
      wrap.style.display = 'none';
      wrap.innerHTML = '';
      return;
    }
    wrap.style.display = 'flex';
    var btns = [
      '<button type="button" onclick="selectInspectionMonthTab(\'all\')" class="btn btn-sm" style="padding:6px 12px; border-radius:8px; font-size:0.8rem; font-weight:800; cursor:pointer; ' +
      (inspActiveMonthKey === 'all' ? 'background:#064e3b; color:#ffffff; border:1.5px solid #064e3b;' : 'background:#ffffff; color:#0f172a; border:1.5px solid #cbd5e1;') +
      '">📊 All Months (' + esc(inspCurrentReport.weeks_count || 1) + 'w)</button>'
    ];
    secs.forEach(function (s) {
      var active = inspActiveMonthKey === s.month_key;
      btns.push(
        '<button type="button" onclick="selectInspectionMonthTab(\'' + esc(s.month_key) + '\')" class="btn btn-sm" style="padding:6px 12px; border-radius:8px; font-size:0.8rem; font-weight:800; cursor:pointer; ' +
        (active ? 'background:#1e3a8a; color:#ffffff; border:1.5px solid #1e3a8a;' : 'background:#f8fafc; color:#1e293b; border:1.5px solid #cbd5e1;') +
        '">🗓️ ' + esc(s.month_label) + ' (' + esc(s.week_count) + 'w)</button>'
      );
    });
    wrap.innerHTML = btns.join('');
  };

  window.renderInspectionsReport = function (data) {
    if (!data) return;
    inspCurrentReport = data;
    inspActiveMonthKey = 'all';
    var levelLabel = data.group_label || 'Mandal';
    var plural = levelLabel === 'Mandal' ? 'Mandals' : (levelLabel === 'Division' ? 'Divisions' : 'Districts');

    var el;
    el = document.getElementById('insp-kpi-units-label'); if (el) el.textContent = 'Total ' + plural;
    el = document.getElementById('insp-col-unit-header'); if (el) el.textContent = levelLabel;
    el = document.getElementById('insp-search-unit-label'); if (el) el.textContent = levelLabel;
    el = document.getElementById('insp-target-rule-text');
    if (el) el.textContent = (data.target_rule_desc || '') + ' • Filter: Final Submit Status = Submitted Only';

    var actionsWrap = document.getElementById('insp-actions-wrap');
    if (actionsWrap) actionsWrap.style.display = 'flex';

    var totals = data.totals || {};
    var periodTxt = (data.from_week && data.to_week && data.from_week !== data.to_week)
      ? (data.from_week + ' -> ' + data.to_week)
      : (data.from_week || '');
    var monthPart = data.month_period ? (data.month_period + ' • ') : '';
    var genPart = data.generated_at ? (' • Report Generated On: ' + data.generated_at) : '';
    var syncEl = document.getElementById('insp-sync-time');
    if (syncEl) {
      var logNote = '';
      if ((totals.raw_row_count || 0) === 0 && Array.isArray(data.week_logs) && data.week_logs.length > 0) {
        logNote = ' • Portal Week Status: ' + data.week_logs.map(function (wl) {
          return (wl.week || '') + ' [' + (wl.status || 'unknown') + ']';
        }).join(', ');
      }
      syncEl.textContent =
        'Compiled ' + (data.designation || 'MPO') + ' (' + monthPart + (data.weeks_count || 1) + ' week(s): ' +
        periodTxt + ') • Submitted Considered: ' +
        (totals.submitted_row_count || 0) + ' / Raw: ' + (totals.raw_row_count || 0) +
        ' (Excluded Non-Submitted: ' + (totals.excluded_non_submitted_count || 0) + ')' + genPart + logNote;
    }

    el = document.getElementById('insp-table-title');
    if (el) {
      var dName = String(data.district_name || 'District').trim();
      var distHeading = /district/i.test(dName) ? dName : (dName + ' District');
      el.textContent = distHeading + ' — ' + (data.designation || '') + ' Inspections Abstract (Submitted Only)';
    }

    window.renderInspectionMonthTabs();
    window.filterInspectionsTable();
  };

  window.filterInspectionsTable = function () {
    var rows = [];
    if (inspCurrentReport) {
      if (inspActiveMonthKey !== 'all' && Array.isArray(inspCurrentReport.monthly_sections)) {
        var foundSec = inspCurrentReport.monthly_sections.find(function (s) { return s.month_key === inspActiveMonthKey; });
        if (foundSec) {
          rows = foundSec.rows || [];
          var ruleEl = document.getElementById('insp-target-rule-text');
          if (ruleEl) ruleEl.textContent = foundSec.month_label + ': ' + (foundSec.target_rule_desc || '') + ' • Weeks (' + foundSec.week_count + '): ' + (foundSec.weeks_included || []).join(', ');
        }
      }
      if (!rows.length && inspActiveMonthKey === 'all') {
        rows = inspCurrentReport.rows || [];
        var ruleEl2 = document.getElementById('insp-target-rule-text');
        if (ruleEl2) ruleEl2.textContent = (inspCurrentReport.target_rule_desc || '') + ' • Filter: Final Submit Status = Submitted Only';
      }
    }
    var searchEl = document.getElementById('insp-search-input');
    var q = (searchEl ? searchEl.value : '').toLowerCase().trim();
    var filtered = rows.filter(function (r) {
      if (!q) return true;
      return String(r.unit_name || '').toLowerCase().indexOf(q) !== -1;
    });
    inspFilteredCache = filtered;

    var levelLabel = (inspCurrentReport && inspCurrentReport.group_label) || 'Mandal';
    var plural = levelLabel === 'Mandal' ? 'Mandals' : (levelLabel === 'Division' ? 'Divisions' : 'Districts');

    var totUnits = filtered.length;
    var totTarget = filtered.reduce(function (a, r) { return a + Number(r.target || 0); }, 0);
    var totCompleted = filtered.reduce(function (a, r) { return a + Number(r.completed || 0); }, 0);
    var totBalance = filtered.reduce(function (a, r) { return a + Number(r.balance || 0); }, 0);
    var pct = totTarget > 0 ? ((totCompleted / totTarget) * 100).toFixed(2) : '0.00';

    var el;
    el = document.getElementById('insp-kpi-mandals'); if (el) el.textContent = totUnits;
    el = document.getElementById('insp-kpi-target'); if (el) el.textContent = totTarget;
    el = document.getElementById('insp-kpi-completed'); if (el) el.textContent = totCompleted;
    el = document.getElementById('insp-kpi-pending'); if (el) el.textContent = totBalance;
    el = document.getElementById('insp-kpi-rate'); if (el) el.textContent = pct + '%';
    el = document.getElementById('insp-table-counter'); if (el) el.textContent = 'Showing ' + totUnits + ' ' + plural;

    var tbody = document.getElementById('insp-table-body');
    if (!tbody) return;

    if (!tbody.dataset.inspDelegated) {
      tbody.dataset.inspDelegated = '1';
      tbody.addEventListener('click', function (ev) {
        var btn = ev.target && ev.target.closest ? ev.target.closest('[data-insp-idx]') : null;
        if (!btn) return;
        var rowIdx = parseInt(btn.getAttribute('data-insp-idx'), 10);
        var row = inspFilteredCache[rowIdx];
        if (row) window.viewInspectionUnitDetails(row);
      });
    }

    if (!inspCurrentReport) return;

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:#64748b; font-weight:600;">No submitted inspection records found for the selected criteria.</td></tr>';
      return;
    }

    var rowsHtml = filtered.map(function (r, idx) {
      var rowBg = idx % 2 === 0 ? 'background:#ffffff;' : 'background:#f8fafc;';
      var pctVal = Number(r.pct_completed || 0);
      var pctColor = pctVal >= 100 ? '#15803d' : (pctVal >= 50 ? '#b45309' : '#dc2626');
      var balColor = Number(r.balance || 0) > 0 ? '#dc2626' : '#15803d';
      return (
        '<tr style="border-bottom:1px solid #e2e8f0; ' + rowBg + '">' +
          '<td style="padding:10px 12px; text-align:center; font-weight:700; color:#64748b;">' + (idx + 1) + '</td>' +
          '<td style="padding:10px 12px; font-weight:700; color:#0f172a;">' + esc(r.unit_name) + '</td>' +
          '<td style="padding:10px 12px; text-align:center; font-weight:700;">' + esc(r.target) + '</td>' +
          '<td style="padding:10px 12px; text-align:center; font-weight:800; color:#15803d;">' + esc(r.completed) + '</td>' +
          '<td style="padding:10px 12px; text-align:center; font-weight:800; color:' + balColor + ';">' + esc(r.balance) + '</td>' +
          '<td style="padding:10px 12px; text-align:center; font-weight:800; color:' + pctColor + ';">' + pctVal.toFixed(2) + '%</td>' +
          '<td style="padding:10px 12px; text-align:center;">' +
            '<button type="button" class="btn btn-sm" data-insp-idx="' + idx + '" style="padding:4px 10px; font-size:0.75rem; font-weight:700; background:#f1f5f9; color:#0f172a; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer;">🔍 View (' + esc((r.details || []).length) + ')</button>' +
          '</td>' +
        '</tr>'
      );
    }).join('');

    rowsHtml +=
      '<tr style="background:#062b1f; color:#ffffff; font-weight:800; border-top:2px solid #165b43;">' +
        '<td colspan="2" style="padding:12px; text-align:right;">TOTAL:</td>' +
        '<td style="padding:12px; text-align:center;">' + esc(totTarget) + '</td>' +
        '<td style="padding:12px; text-align:center; color:#34d399;">' + esc(totCompleted) + '</td>' +
        '<td style="padding:12px; text-align:center; color:#f87171;">' + esc(totBalance) + '</td>' +
        '<td style="padding:12px; text-align:center; color:#fbbf24;">' + esc(pct) + '%</td>' +
        '<td style="padding:12px; text-align:center;">' + esc(totCompleted) + ' Submitted</td>' +
      '</tr>';

    tbody.innerHTML = rowsHtml;
  };

  window.viewInspectionUnitDetails = function (row) {
    var modal = document.getElementById('insp-detail-modal');
    var title = document.getElementById('insp-modal-title');
    var sub = document.getElementById('insp-modal-subtitle');
    var content = document.getElementById('insp-modal-content');
    if (!modal || !content) return;

    var levelLabel = (inspCurrentReport && inspCurrentReport.group_label) || 'Mandal';
    var details = row.details || [];
    if (title) title.textContent = row.unit_name + ' ' + levelLabel + ' — Submitted GP Inspections';
    if (sub) {
      sub.textContent =
        'Target: ' + row.target + ' | Completed (Submitted): ' + row.completed +
        ' | Balance: ' + row.balance + ' | ' + Number(row.pct_completed || 0).toFixed(2) + '%';
    }

    if (!details.length) {
      content.innerHTML = '<div style="padding:20px; text-align:center; color:#64748b; font-weight:600;">No Final Submit Status = Submitted records found for ' + esc(row.unit_name) + ' in the selected weeks.</div>';
    } else {
      var trs = details.map(function (rec, idx) {
        return (
          '<tr style="border-bottom:1px solid #f1f5f9;">' +
            '<td style="padding:8px 10px; text-align:center; font-weight:700; color:#64748b;">' + (idx + 1) + '</td>' +
            '<td style="padding:8px 10px; font-weight:600; color:#0f172a;">' + esc(rec.week || '—') + '</td>' +
            '<td style="padding:8px 10px; font-weight:700; color:#0f172a;">' + esc(rec.gp_name || rec.mandal || row.unit_name) + '</td>' +
            '<td style="padding:8px 10px; color:#334155;">' + esc(rec.officer_name || rec.designation || '—') + '</td>' +
            '<td style="padding:8px 10px; text-align:center; color:#475569;">' + esc(rec.inspection_date || '—') + '</td>' +
            '<td style="padding:8px 10px; text-align:center;"><span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:800;">Submitted</span></td>' +
          '</tr>'
        );
      }).join('');
      content.innerHTML =
        '<div style="overflow-x:auto;">' +
          '<table style="width:100%; border-collapse:collapse; font-size:0.85rem; text-align:left;">' +
            '<thead><tr style="background:#0f172a; color:#ffffff; font-weight:700;">' +
              '<th style="padding:8px 10px; text-align:center; width:45px;">#</th>' +
              '<th style="padding:8px 10px;">Week</th>' +
              '<th style="padding:8px 10px;">Gram Panchayat</th>' +
              '<th style="padding:8px 10px;">Officer</th>' +
              '<th style="padding:8px 10px; text-align:center;">Date</th>' +
              '<th style="padding:8px 10px; text-align:center;">Status</th>' +
            '</tr></thead>' +
            '<tbody>' + trs + '</tbody>' +
          '</table>' +
        '</div>';
    }
    modal.style.display = 'flex';
  };

  window.closeInspModal = function () {
    var modal = document.getElementById('insp-detail-modal');
    if (modal) modal.style.display = 'none';
  };

  window.downloadInspectionsArtifact = function (kind) {
    var url = '/api/inspections/download-' + encodeURIComponent(kind || 'pdf');
    if (window.DeptSessionManager && typeof window.DeptSessionManager.appendSessionParam === 'function') {
      url = window.DeptSessionManager.appendSessionParam(url);
    }
    window.open(url, '_blank');
  };

  // ---------------------------------------------------------------------------
  // Upcoming Modal & Active Sessions Modal
  // ---------------------------------------------------------------------------

  window.showUpcomingModal = function (name, icon, desc) {
    var titleEl = document.getElementById('modal-title');
    var iconEl = document.getElementById('modal-icon');
    var descEl = document.getElementById('modal-desc');
    var modal = document.getElementById('upcoming-modal');
    if (titleEl) titleEl.textContent = name || 'Module Title';
    if (iconEl) iconEl.textContent = icon || '📑';
    if (descEl) descEl.textContent = desc || '';
    if (modal) modal.style.display = 'flex';
  };

  window.closeUpcomingModal = function () {
    var modal = document.getElementById('upcoming-modal');
    if (modal) modal.style.display = 'none';
  };

  window.openSessionsModal = function () {
    var u = typeof window.getScopedUser === 'function' ? window.getScopedUser() : null;
    var isAdmHost = typeof window.isAdminHost === 'function' && window.isAdminHost();
    if (!(isAdmHost && u && u.is_admin)) {
      showNotice('Administrator session views are restricted exclusively to https://admin.panchayatautomation.in.', 'error');
      return;
    }
    var modal = document.getElementById('sessions-modal');
    if (modal) {
      modal.style.display = 'flex';
      window.fetchAndRenderSessionsModal();
    }
  };

  window.closeSessionsModal = function () {
    var modal = document.getElementById('sessions-modal');
    if (modal) modal.style.display = 'none';
  };

  window.fetchAndRenderSessionsModal = async function () {
    try {
      var data = await window.safeFetchJson('/api/system/sessions');
      if (!data || !data.success) return;

      var mySid = typeof window.getEptsSessionId === 'function' ? window.getEptsSessionId() : '';
      var el;
      el = document.getElementById('sessions-modal-timestamp'); if (el) el.textContent = 'Live Server Time: ' + (data.timestamp || '');
      el = document.getElementById('modal-stat-total'); if (el) el.textContent = data.total_sessions != null ? data.total_sessions : 0;
      el = document.getElementById('modal-stat-auth'); if (el) el.textContent = data.authenticated_sessions != null ? data.authenticated_sessions : 0;
      el = document.getElementById('modal-stat-mysid'); if (el) el.textContent = mySid ? (mySid.substring(0, 8) + '...') : '—';

      var tbody = document.getElementById('sessions-table-body');
      if (!tbody) return;
      if (!data.sessions || data.sessions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:18px; color:var(--text-muted);">No active sessions currently.</td></tr>';
        return;
      }

      tbody.innerHTML = data.sessions.map(function (s) {
        var isMe = s.session_id === mySid;
        var isAuth = Boolean(s.authenticated);
        var statusBadge = isAuth
          ? '<span style="background:#dcfce7; color:#15803d; font-weight:700; padding:2px 8px; border-radius:10px; font-size:0.72rem;">● Authenticated</span>'
          : (s.status === 'awaiting_otp'
            ? '<span style="background:#fef3c7; color:#b45309; font-weight:700; padding:2px 8px; border-radius:10px; font-size:0.72rem;">● Awaiting OTP</span>'
            : '<span style="background:#f1f5f9; color:#64748b; font-weight:600; padding:2px 8px; border-radius:10px; font-size:0.72rem;">Idle</span>');

        var userDisplay = esc(s.user_id || 'Officer') + (isMe ? ' <b style="color:#059669;">(You)</b>' : '');
        var rowBg = isMe ? 'background:#f0fdf4;' : '';
        var distDisplay = isAuth
          ? '<span style="font-weight:700; color:#047857; display:inline-flex; align-items:center; gap:4px;">🏛️ ' + esc(s.district_name || 'Khammam District') + '</span>'
          : '<span style="color:#94a3b8;">—</span>';
        var officeDisplay = isAuth
          ? '<span style="font-weight:600; color:#1e293b;">' + esc(s.office_name || (s.user_id === 'DPOA3698' ? 'District Panchayat Office' : 'Panchayat Officer')) + '</span>'
          : '<span style="color:#94a3b8;">—</span>';
        var modeDisplay = isAuth
          ? '<span style="font-weight:700; color:#047857; background:#dcfce7; padding:2px 8px; border-radius:6px; font-size:0.75rem;">🛡️ Persistent</span>'
          : '—';

        return (
          '<tr style="border-bottom:1px solid #f1f5f9; ' + rowBg + '">' +
            '<td style="padding:8px 10px;">' + distDisplay + '</td>' +
            '<td style="padding:8px 10px;">' + officeDisplay + '</td>' +
            '<td style="padding:8px 10px; font-weight:700; color:var(--text);">' + userDisplay + '</td>' +
            '<td style="padding:8px 10px;">' + statusBadge + '</td>' +
            '<td style="padding:8px 10px;">' + modeDisplay + '</td>' +
            '<td style="padding:8px 10px; color:#475569;">' + esc(s.age_minutes != null ? s.age_minutes : 0) + 'm</td>' +
            '<td style="padding:8px 10px; color:#475569;">' + esc(s.idle_minutes != null ? s.idle_minutes : 0) + 'm ago</td>' +
            '<td style="padding:8px 10px; font-family:monospace; color:#64748b; font-size:0.74rem;">' + esc(s.session_id_short || '') + '</td>' +
          '</tr>'
        );
      }).join('');
    } catch (e) {}
  };

  // ---------------------------------------------------------------------------
  // Automated Multiple Days DSR & PS Attendance Robot Station (#auto-multi-dsr-station)
  // ---------------------------------------------------------------------------

  var autoMultiPublicHolidays = [];
  var autoMultiCurrentReport = null;
  var autoMultiActiveTab = 'district';
  var autoMultiPollTimer = null;

  window.openAutoMultiDsrStation = async function (options) {
    var opts = options || {};
    if (!opts.skipAuthCheck && typeof window.ensureDepartmentSession === 'function') {
      var ok = await window.ensureDepartmentSession('auto-multi-dsr', {
        autoGenerate: opts.autoGenerate === true,
        params: opts.params,
      });
      if (!ok) return;
    }

    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var stEl = document.getElementById('auto-multi-dsr-station');
    if (stEl) {
      stEl.style.display = 'block';
      stEl.scrollIntoView({ behavior: 'smooth' });
    }

    var sInput = document.getElementById('auto-multi-start-date');
    var eInput = document.getElementById('auto-multi-end-date');
    if (sInput && !sInput.value) {
      var dStart = new Date();
      dStart.setDate(dStart.getDate() - 7);
      sInput.value = dStart.toISOString().split('T')[0];
    }
    if (eInput && !eInput.value) {
      var dEnd = new Date();
      dEnd.setDate(dEnd.getDate() - 1);
      eInput.value = dEnd.toISOString().split('T')[0];
    }

    if (opts.params) {
      if (opts.params.start_date && sInput) sInput.value = opts.params.start_date;
      if (opts.params.end_date && eInput) eInput.value = opts.params.end_date;
    }

    await window.fetchAutoMultiDsrPreview();

    try {
      var sessRes = await window.safeFetchJson('/api/auto-multi-dsr/session-job');
      if (sessRes && sessRes.success && sessRes.job) {
        var j = sessRes.job;
        if (j.status === 'running' || j.status === 'queued') {
          window.startAutoMultiDsrPolling(j.job_id);
        } else if (j.status === 'completed' && j.report_data) {
          window.renderAutoMultiDsrResults(j);
        }
      }
    } catch (e) {}

    if (opts.autoGenerate === true) {
      await window.runAutoMultiDsrRobot();
    }
  };

  window.onAutoMultiDsrDateChange = function () {
    window.fetchAutoMultiDsrPreview();
  };

  window.addAutoMultiDsrPublicHoliday = function () {
    var inp = document.getElementById('auto-multi-pub-holiday-input');
    if (!inp || !inp.value) return;
    var val = inp.value.trim();
    if (autoMultiPublicHolidays.indexOf(val) === -1) {
      autoMultiPublicHolidays.push(val);
      autoMultiPublicHolidays.sort();
    }
    inp.value = '';
    renderAutoMultiPublicHolidayChips();
    window.fetchAutoMultiDsrPreview();
  };

  window.removeAutoMultiDsrPublicHoliday = function (val) {
    autoMultiPublicHolidays = autoMultiPublicHolidays.filter(function (d) { return d !== val; });
    renderAutoMultiPublicHolidayChips();
    window.fetchAutoMultiDsrPreview();
  };

  function renderAutoMultiPublicHolidayChips() {
    var wrap = document.getElementById('auto-multi-pub-holidays-wrap');
    var chips = document.getElementById('auto-multi-pub-holidays-chips');
    if (!wrap || !chips) return;
    if (autoMultiPublicHolidays.length === 0) {
      wrap.style.display = 'none';
      chips.innerHTML = '';
      return;
    }
    wrap.style.display = 'block';
    chips.innerHTML = autoMultiPublicHolidays.map(function (d) {
      return (
        '<span style="background:#fffbeb; border:1px solid #fde68a; color:#92400e; padding:4px 10px; border-radius:999px; font-size:0.8rem; font-weight:700; display:inline-flex; align-items:center; gap:6px;">' +
          '<span>' + esc(d) + '</span>' +
          '<button type="button" onclick="removeAutoMultiDsrPublicHoliday(\'' + esc(d) + '\')" style="background:none; border:none; cursor:pointer; color:#b45309; font-weight:800; font-size:0.9rem; line-height:1; padding:0;">&times;</button>' +
        '</span>'
      );
    }).join('');
  }

  window.fetchAutoMultiDsrPreview = async function () {
    var sInput = document.getElementById('auto-multi-start-date');
    var eInput = document.getElementById('auto-multi-end-date');
    if (!sInput || !eInput || !sInput.value || !eInput.value) return;

    try {
      var res = await window.safeFetchJson('/api/auto-multi-dsr/preview-dates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: sInput.value,
          end_date: eInput.value,
          public_holidays: autoMultiPublicHolidays,
        }),
      });
      if (res && res.success && res.date_analysis) {
        var a = res.date_analysis;
        var elTot = document.getElementById('val-total-calendar-days');
        var elWk = document.getElementById('val-working-days-count');
        var elSun = document.getElementById('val-sundays-count');
        var elSat = document.getElementById('val-second-saturdays-count');
        var elPub = document.getElementById('val-public-holidays-count');
        var listEl = document.getElementById('auto-multi-working-days-list');

        if (elTot) elTot.textContent = a.total_calendar_days;
        if (elWk) elWk.textContent = a.working_days_count;
        if (elSun) elSun.textContent = a.excluded_sundays_count;
        if (elSat) elSat.textContent = a.excluded_second_saturdays_count;
        if (elPub) elPub.textContent = a.excluded_public_holidays_count;

        if (listEl) {
          listEl.innerHTML = (a.working_day_items || []).map(function (item) {
            return (
              '<span style="background:#ffffff; border:1px solid #86efac; color:#14532d; padding:3px 8px; border-radius:6px; font-size:0.75rem; font-weight:700;">' +
                esc(item.display) + ' (' + esc(item.day_name.slice(0, 3)) + ')' +
              '</span>'
            );
          }).join('') || '<span style="color:#991b1b; font-size:0.8rem; font-weight:700;">No working days in range!</span>';
        }
      }
    } catch (e) {}
  };

  window.runAutoMultiDsrRobot = async function () {
    var sInput = document.getElementById('auto-multi-start-date');
    var eInput = document.getElementById('auto-multi-end-date');
    var chkTime = document.getElementById('chk-auto-multi-time-matrix');
    var btn = document.getElementById('btn-run-auto-multi-robot');

    if (!sInput || !eInput || !sInput.value || !eInput.value) {
      showNotice('Please select both Start Date and End Date.', 'warning');
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Starting Robot...';
    }
    var progCard = document.getElementById('auto-multi-progress-card');
    var resCard = document.getElementById('auto-multi-results-section');
    if (progCard) progCard.style.display = 'block';
    if (resCard) resCard.style.display = 'none';

    try {
      var res = await window.safeFetchJson('/api/auto-multi-dsr/start-job', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_date: sInput.value,
          end_date: eInput.value,
          public_holidays: autoMultiPublicHolidays,
          include_time_matrix: Boolean(!chkTime || chkTime.checked),
        }),
      });

      if (!res.success || !res.job_id) {
        throw new Error(res.error || res.detail || 'Could not start robot job.');
      }
      showNotice('Multi-Days DSR Robot started for ' + res.total_working_days + ' working day(s).', 'success');
      window.startAutoMultiDsrPolling(res.job_id);
    } catch (err) {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '⚡ Run Multi-Days DSR Robot';
      }
      if (progCard) progCard.style.display = 'none';
      if (handleDepartmentSessionExpiredError(err, 'auto-multi-dsr', { start_date: sInput.value, end_date: eInput.value })) return;
      showNotice('Robot error: ' + (err.message || err), 'error');
    }
  };

  window.startAutoMultiDsrPolling = function (jobId) {
    if (autoMultiPollTimer) clearInterval(autoMultiPollTimer);
    var btn = document.getElementById('btn-run-auto-multi-robot');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Robot Running...';
    }

    autoMultiPollTimer = setInterval(async function () {
      try {
        var job = await window.safeFetchJson('/api/auto-multi-dsr/jobs/' + encodeURIComponent(jobId));
        if (!job) return;

        var pct = job.progress_pct || 0;
        var fillEl = document.getElementById('auto-multi-progress-fill');
        var badgeEl = document.getElementById('auto-multi-progress-pct-badge');
        var statusEl = document.getElementById('auto-multi-progress-status');
        var statTot = document.getElementById('auto-multi-stat-total');
        var statDone = document.getElementById('auto-multi-stat-done');
        var statFail = document.getElementById('auto-multi-stat-failed');

        if (fillEl) fillEl.style.width = pct + '%';
        if (badgeEl) badgeEl.textContent = pct + '%';
        if (statusEl) statusEl.textContent = job.current_date ? ('Processing ' + job.current_date) : job.status;
        if (statTot) statTot.textContent = job.total_working_days || 0;
        if (statDone) statDone.textContent = job.completed_count || 0;
        if (statFail) statFail.textContent = job.failed_count || 0;

        // Render download logs table
        var tbody = document.getElementById('auto-multi-logs-tbody');
        if (tbody && Array.isArray(job.download_logs)) {
          if (job.download_logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:12px; color:#64748b;">Initializing download tasks...</td></tr>';
          } else {
            tbody.innerHTML = job.download_logs.map(function (log) {
              var stBadge = log.status === 'success'
                ? '<span style="background:#ecfdf5; color:#065f46; padding:2px 8px; border-radius:4px; font-weight:800;">✓ Success</span>'
                : '<span style="background:#fef2f2; color:#991b1b; padding:2px 8px; border-radius:4px; font-weight:800;">✗ Failed</span>';
              var sizeTxt = log.file_size ? (Math.round(log.file_size / 1024) + ' KB') : '—';
              return (
                '<tr style="border-bottom:1px solid #f1f5f9;">' +
                  '<td style="padding:6px 10px; font-weight:700;">' + esc(log.display_date || log.date) + '</td>' +
                  '<td style="padding:6px 10px; color:#64748b;">' + esc(log.portal_date || '') + '</td>' +
                  '<td style="padding:6px 10px;">' + stBadge + '</td>' +
                  '<td style="padding:6px 10px; color:#334155;">' + esc(log.filename || '—') + ' (' + sizeTxt + ')</td>' +
                  '<td style="padding:6px 10px; color:' + (log.error ? '#dc2626' : '#64748b') + ';">' + esc(log.error || 'Downloaded cleanly') + '</td>' +
                '</tr>'
              );
            }).join('');
          }
        }

        if (job.status === 'completed') {
          clearInterval(autoMultiPollTimer);
          autoMultiPollTimer = null;
          if (btn) {
            btn.disabled = false;
            btn.textContent = '⚡ Run Multi-Days DSR Robot';
          }
          showNotice('✅ Multi-Days DSR Robot finished: ' + (job.completed_count || 0) + ' day(s) consolidated successfully.', 'success');
          window.renderAutoMultiDsrResults(job);
        } else if (job.status === 'failed') {
          clearInterval(autoMultiPollTimer);
          autoMultiPollTimer = null;
          if (btn) {
            btn.disabled = false;
            btn.textContent = '⚡ Run Multi-Days DSR Robot';
          }
          showNotice('Multi-Days DSR Robot failed: ' + (job.error || 'Unknown error'), 'error');
        }
      } catch (e) {}
    }, 1500);
  };

  window.renderAutoMultiDsrResults = function (job) {
    if (!job || !job.report_data) return;
    autoMultiCurrentReport = job.report_data;
    var data = job.report_data;
    var s = data.summary || {};

    var resSec = document.getElementById('auto-multi-results-section');
    if (resSec) resSec.style.display = 'block';

    var hEl = document.getElementById('auto-multi-res-heading');
    var subEl = document.getElementById('auto-multi-res-subheading');
    if (hEl) hEl.textContent = (s.dist_name || 'District') + ' — Automated Multi-Days PS Attendance & DSR Abstract';
    if (subEl) {
      subEl.textContent = 'Period: ' + s.start_date + ' to ' + s.end_date + ' • Report Generated On: ' + s.generated_on + ' • Working Days Downloaded: ' + s.working_days_downloaded + '/' + (job.total_working_days || s.total_reporting_days);
    }

    // Set download button URLs
    var dlFullPdf = document.getElementById('btn-auto-multi-dl-full-pdf');
    var dlExcel = document.getElementById('btn-auto-multi-dl-excel');
    var dlExcelLbl = document.getElementById('btn-auto-multi-dl-excel-label');
    var dlDistPdf = document.getElementById('btn-auto-multi-dl-dist-pdf');
    var dlMandalPdf = document.getElementById('btn-auto-multi-dl-mandal-pdf');
    var dlGpPdf = document.getElementById('btn-auto-multi-dl-gp-pdf');
    var dlTimePdf = document.getElementById('btn-auto-multi-dl-time-pdf');
    var timeTabBtn = document.getElementById('btn-auto-multi-tab-time');

    var baseUrls = job.download_urls || {};
    if (dlFullPdf) dlFullPdf.href = baseUrls.pdf || '#';
    if (dlExcel) dlExcel.href = baseUrls.excel || '#';
    if (dlExcelLbl) dlExcelLbl.textContent = (data.time_matrix_columns && data.time_matrix_columns.length) ? 'Download Excel (5 Sheets)' : 'Download Excel (4 Sheets)';
    if (dlDistPdf) dlDistPdf.href = baseUrls.pdf_district || '#';
    if (dlMandalPdf) dlMandalPdf.href = baseUrls.pdf_mandal || '#';
    if (dlGpPdf) dlGpPdf.href = baseUrls.pdf_gp || '#';
    if (dlTimePdf) {
      dlTimePdf.href = baseUrls.pdf_time_matrix || '#';
      dlTimePdf.style.display = (data.time_matrix_columns && data.time_matrix_columns.length) ? 'inline-flex' : 'none';
    }
    if (timeTabBtn) {
      timeTabBtn.style.display = (data.time_matrix_columns && data.time_matrix_columns.length) ? 'inline-flex' : 'none';
    }

    // Render 6 KPI cards
    var kpis = [
      { label: 'District', val: s.dist_name || '-' },
      { label: 'Reporting Period', val: (s.start_date || '') + ' to ' + (s.end_date || '') },
      { label: 'Working Days Downloaded', val: (s.working_days_downloaded || s.total_reporting_days) + ' / ' + (job.total_working_days || s.total_reporting_days) },
      { label: 'Total Mandals', val: s.mandal_count || 0 },
      { label: 'Total Gram Panchayats', val: s.total_gps || 0 },
      { label: 'Overall Before 9 AM %', val: Number(s.overall_before9_pct || 0).toFixed(2) + '%' },
    ];
    var kpiGrid = document.getElementById('auto-multi-kpi-grid');
    if (kpiGrid) {
      kpiGrid.innerHTML = kpis.map(function (k) {
        return (
          '<div class="md-kpi">' +
            '<div class="md-kpi-label">' + esc(k.label) + '</div>' +
            '<div class="md-kpi-val">' + esc(String(k.val)) + '</div>' +
          '</div>'
        );
      }).join('');
    }

    // Populate mandal filter dropdown
    var mSel = document.getElementById('auto-multi-mandal-filter');
    if (mSel) {
      var seen = {};
      (data.gp_rows || []).forEach(function (r) {
        if (r['Mandal Name']) seen[r['Mandal Name']] = true;
      });
      mSel.innerHTML = '<option value="">All Mandals</option>' + Object.keys(seen).sort().map(function (m) {
        return '<option value="' + esc(m) + '">' + esc(m) + '</option>';
      }).join('');
    }

    window.switchAutoMultiDsrTab('district');
    if (resSec) resSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  window.switchAutoMultiDsrTab = function (tab) {
    autoMultiActiveTab = tab || 'district';
    document.querySelectorAll('[data-auto-tab]').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-auto-tab') === autoMultiActiveTab);
    });
    document.querySelectorAll('[data-auto-pdf]').forEach(function (lnk) {
      lnk.classList.toggle('active-pdf', lnk.getAttribute('data-auto-pdf') === autoMultiActiveTab);
    });
    var showFilter = (autoMultiActiveTab === 'mandal' || autoMultiActiveTab === 'gp' || autoMultiActiveTab === 'time_matrix');
    var mSel = document.getElementById('auto-multi-mandal-filter');
    var qInp = document.getElementById('auto-multi-search-input');
    if (mSel) mSel.style.display = showFilter ? 'inline-block' : 'none';
    if (qInp) qInp.style.display = showFilter ? 'inline-block' : 'none';

    window.renderAutoMultiDsrTable();
  };

  window.renderAutoMultiDsrTable = function () {
    if (!autoMultiCurrentReport) return;
    var data = autoMultiCurrentReport;
    var cols = [];
    var rows = [];

    if (autoMultiActiveTab === 'mandal') {
      cols = data.mandal_columns || [];
      rows = data.mandal_rows || [];
    } else if (autoMultiActiveTab === 'gp') {
      cols = data.gp_columns || [];
      rows = data.gp_rows || [];
    } else if (autoMultiActiveTab === 'time_matrix') {
      cols = data.time_matrix_columns || [];
      rows = data.time_matrix_rows || [];
    } else {
      cols = data.district_columns || [];
      rows = data.district_rows || [];
    }

    var mSel = document.getElementById('auto-multi-mandal-filter');
    var qInp = document.getElementById('auto-multi-search-input');
    var mFilter = (mSel && mSel.value || '').trim().toLowerCase();
    var q = (qInp && qInp.value || '').trim().toLowerCase();

    if (autoMultiActiveTab !== 'district' && (mFilter || q)) {
      rows = rows.filter(function (r) {
        if (mFilter && String(r['Mandal Name'] || '').toLowerCase() !== mFilter) return false;
        if (q) {
          var hay = (
            String(r['Mandal Name'] || '') + ' ' +
            String(r['Panchayat Name'] || '') + ' ' +
            String(r['Date'] || '')
          ).toLowerCase();
          if (hay.indexOf(q) === -1) return false;
        }
        return true;
      });
    }

    var thead = document.getElementById('auto-multi-table-head');
    var tbody = document.getElementById('auto-multi-table-body');
    if (thead) {
      thead.innerHTML = '<tr>' + cols.map(function (c) { return '<th>' + esc(c) + '</th>'; }).join('') + '</tr>';
    }

    if (tbody) {
      var leftCols = { 'Mandal Name': true, 'Panchayat Name': true };
      tbody.innerHTML = rows.map(function (r) {
        return '<tr>' + cols.map(function (c) {
          var val = r[c];
          if (c === 'Before 9 AM %') {
            var st = r._before9_style || {};
            return '<td><span class="md-pct-pill" style="' + esc(st.css || '') + '">' + esc(Number(val || 0).toFixed(2) + '%') + '</span></td>';
          }
          if (autoMultiActiveTab === 'time_matrix' && r._time_styles && r._time_styles[c]) {
            var ts = r._time_styles[c] || {};
            return '<td><span class="md-pct-pill" style="min-width:52px; font-variant-numeric:tabular-nums; font-weight:' + (c === 'Average Time' ? '800' : '600') + '; ' + esc(ts.css || '') + '">' + esc(String(val === undefined || val === null ? '' : val)) + '</span></td>';
          }
          if (c === 'After 9 AM %') {
            return '<td>' + esc(Number(val || 0).toFixed(2) + '%') + '</td>';
          }
          if (leftCols[c]) {
            return '<td class="left">' + esc(String(val === undefined || val === null ? '' : val)) + '</td>';
          }
          return '<td>' + esc(String(val === undefined || val === null ? '' : val)) + '</td>';
        }).join('') + '</tr>';
      }).join('') || '<tr><td colspan="' + cols.length + '" style="text-align:center; padding:18px; color:#64748b;">No matching records.</td></tr>';
    }
  };

  window.triggerServerSync = async function (btn) {
    var confirmed = typeof window.showConfirmModal === 'function'
      ? await window.showConfirmModal({
        title: 'Server Code Sync',
        message: 'Sync latest code from GitHub main and restart background service?',
        confirmLabel: 'Sync Code',
      })
      : true;
    if (!confirmed) return;

    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Syncing...';
    }
    try {
      var data = await window.safeFetchJson('/api/system/sync', { method: 'POST' });
      showNotice(data.message || (data.success ? 'Server sync initiated.' : data.error), data.success ? 'success' : 'error');
    } catch (e) {
      showNotice('Server sync request failed: ' + e.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '🔄 Sync Code Now';
      }
    }
  };

  // -------------------------------------------------------------
  // State Format Attendance & DSR Station Logic
  // -------------------------------------------------------------
  var stateFormatTimer = null;
  var stateFormatStartTime = 0;

  window.openStateFormatRobot = async function (options) {
    var opts = options || {};
    if (!opts.skipAuthCheck && typeof window.ensureDepartmentSession === 'function') {
      var ok = await window.ensureDepartmentSession('state-format', {
        autoGenerate: opts.autoGenerate === true,
        params: opts.params,
      });
      if (!ok) return;
    }

    if (typeof window.hideAllStations === 'function') {
      window.hideAllStations();
    }
    var stEl = document.getElementById('state-format-station');
    if (stEl) {
      stEl.style.display = 'block';
      stEl.scrollIntoView({ behavior: 'smooth' });
    }

    var dateInp = document.getElementById('state-format-date');
    if (dateInp && !dateInp.value) {
      var d = new Date();
      dateInp.value = d.toISOString().split('T')[0];
    }

    // Always reset view so previous run is not shown until Run is clicked
    var resEl = document.getElementById('state-format-results');
    if (resEl) resEl.style.display = 'none';
    var progCard = document.getElementById('state-format-progress-card');
    if (progCard) progCard.style.display = 'none';

    if (opts.autoGenerate) {
      window.runStateFormatRobot();
    }
  };

  window.toggleStateFormatManualUpload = function () {
    var drawer = document.getElementById('state-format-manual-drawer');
    if (drawer) {
      drawer.style.display = drawer.style.display === 'none' ? 'block' : 'none';
    }
  };

  function startStateFormatTimer() {
    stopStateFormatTimer();
    stateFormatStartTime = Date.now();
    var timerEl = document.getElementById('state-format-progress-timer');
    stateFormatTimer = setInterval(function () {
      if (!timerEl) return;
      var sec = Math.floor((Date.now() - stateFormatStartTime) / 1000);
      var m = String(Math.floor(sec / 60)).padStart(2, '0');
      var s = String(sec % 60).padStart(2, '0');
      timerEl.textContent = m + ':' + s;
    }, 1000);
  }

  function stopStateFormatTimer() {
    if (stateFormatTimer) {
      clearInterval(stateFormatTimer);
      stateFormatTimer = null;
    }
  }

  window.runStateFormatRobot = async function () {
    var dateVal = (document.getElementById('state-format-date') && document.getElementById('state-format-date').value) || '';
    if (!dateVal) {
      showNotice('Please select a report date before running the State Format Robot.', 'error');
      return;
    }

    var chkEx = document.getElementById('state-format-exclude-incharge');
    var excludeIncharge = chkEx && chkEx.checked ? 'true' : 'false';

    var progCard = document.getElementById('state-format-progress-card');
    var barEl = document.getElementById('state-format-progress-bar');
    var pctEl = document.getElementById('state-format-progress-pct');
    var statEl = document.getElementById('state-format-progress-status');
    var resEl = document.getElementById('state-format-results');
    var btn = document.getElementById('btn-run-state-format');

    if (resEl) resEl.style.display = 'none';
    if (progCard) progCard.style.display = 'block';
    if (barEl) barEl.style.width = '15%';
    if (pctEl) pctEl.textContent = '15%';
    if (statEl) statEl.textContent = 'Connecting to e-Panchayat portal & downloading fresh online reports (GM-R 1.2.7, 1.2.11, 1.2.10)...';
    if (btn) btn.disabled = true;

    startStateFormatTimer();

    var timer1 = setTimeout(function () {
      if (barEl) barEl.style.width = '45%';
      if (pctEl) pctEl.textContent = '45%';
      if (statEl) statEl.textContent = 'Extracting attendance timestamps, postings & arrival time buckets from online data...';
    }, 1500);

    var timer2 = setTimeout(function () {
      if (barEl) barEl.style.width = '75%';
      if (pctEl) pctEl.textContent = '75%';
      if (statEl) statEl.textContent = 'Calculating % before 9 AM from online regular postings and compiling official report...';
    }, 3000);

    try {
      var formData = new FormData();
      formData.append('date', dateVal);
      formData.append('exclude_incharge', excludeIncharge);
      formData.append('force_fresh', 'true');

      var resp = await fetch('/api/dsr/state-format/generate', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        var errJson = await resp.json().catch(function () { return {}; });
        var msg = errJson.detail || ('State Format generation failed (HTTP ' + resp.status + ')');
        if (resp.status === 401 && typeof window.openDsrRobot === 'function') {
          showNotice('e-Panchayat portal session expired or not authenticated. Please login first.', 'error');
          window.openDsrRobot();
          return;
        }
        throw new Error(msg);
      }

      var data = await resp.json();

      clearTimeout(timer1);
      clearTimeout(timer2);
      if (barEl) barEl.style.width = '100%';
      if (pctEl) pctEl.textContent = '100%';
      if (statEl) statEl.textContent = '✓ State Format Report successfully generated and compiled!';

      setTimeout(function () {
        if (progCard) progCard.style.display = 'none';
        window.renderStateFormatTable(data);
      }, 500);

    } catch (err) {
      clearTimeout(timer1);
      clearTimeout(timer2);
      if (statEl) statEl.textContent = '❌ Generation failed: ' + err.message;
      if (pctEl) pctEl.textContent = 'Error';
      showNotice(err.message, 'error');
    } finally {
      stopStateFormatTimer();
      if (btn) btn.disabled = false;
    }
  };

  window.uploadStateFormatFiles = async function () {
    var fileRaw = document.getElementById('state-format-file-raw');
    if (!fileRaw || !fileRaw.files || !fileRaw.files[0]) {
      showNotice('Please select the GM-R 1.2.7 Raw Data File to upload.', 'error');
      return;
    }

    var chkEx = document.getElementById('state-format-exclude-incharge');
    var excludeIncharge = chkEx && chkEx.checked ? 'true' : 'false';

    var filePres = document.getElementById('state-format-file-pres');
    var fileAbs = document.getElementById('state-format-file-abs');

    var formData = new FormData();
    formData.append('file', fileRaw.files[0]);
    if (filePres && filePres.files && filePres.files[0]) {
      formData.append('presentees', filePres.files[0]);
    }
    if (fileAbs && fileAbs.files && fileAbs.files[0]) {
      formData.append('absentees', fileAbs.files[0]);
    }
    formData.append('exclude_incharge', excludeIncharge);

    var progCard = document.getElementById('state-format-progress-card');
    var barEl = document.getElementById('state-format-progress-bar');
    var pctEl = document.getElementById('state-format-progress-pct');
    var statEl = document.getElementById('state-format-progress-status');

    if (progCard) progCard.style.display = 'block';
    if (barEl) barEl.style.width = '50%';
    if (pctEl) pctEl.textContent = '50%';
    if (statEl) statEl.textContent = 'Processing uploaded raw data and generating State Format reports...';

    try {
      var resp = await fetch('/api/web/state-format/upload', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        var errJson = await resp.json().catch(function () { return {}; });
        throw new Error(errJson.detail || ('Upload processing failed (HTTP ' + resp.status + ')'));
      }

      var data = await resp.json();
      if (barEl) barEl.style.width = '100%';
      if (pctEl) pctEl.textContent = '100%';
      if (statEl) statEl.textContent = '✓ Report generated successfully!';

      setTimeout(function () {
        if (progCard) progCard.style.display = 'none';
        window.renderStateFormatTable(data);
      }, 400);

    } catch (err) {
      if (statEl) statEl.textContent = '❌ Failed: ' + err.message;
      showNotice(err.message, 'error');
    }
  };

  window.renderStateFormatTable = function (data) {
    if (!data) return;

    var subEl = document.getElementById('state-format-subtitle-disp');
    if (subEl) subEl.textContent = data.subtitle || '';

    var pdfBtn = document.getElementById('btn-state-format-dl-pdf');
    if (pdfBtn) {
      pdfBtn.href = data.pdf_download_url || '/api/dsr/state-format/download-pdf';
      pdfBtn.download = data.pdf_filename || 'State_Format_Attendance_Report.pdf';
    }

    var xlsBtn = document.getElementById('btn-state-format-dl-excel');
    if (xlsBtn) {
      xlsBtn.href = data.excel_download_url || '/api/dsr/state-format/download-excel';
      xlsBtn.download = data.excel_filename || 'State_Format_Attendance_Report.xlsx';
    }

    var tbody = document.getElementById('state-format-tbody');
    var fmt = function (v) { return (v && Number(v) > 0) ? v : ''; };

    if (tbody) {
      var rowsHtml = '';
      (data.rows || []).forEach(function (r) {
        var pct = Number(r.pct_before_9 || 0);

        rowsHtml += '<tr style="border-bottom:1px solid #cbd5e1;">' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + (r.sl_no || '') + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 8px; text-align:left; font-weight:700;">' + (r.mandal_name || '') + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + (r.total_gps || 0) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px; font-weight:600;">' + (r.full_time_working || 0) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.b_6_9) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.b_9_10) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.b_10_11) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.b_11_12) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.b_after_12) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px; font-weight:800; color:#c00000;">' + pct.toFixed(2) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px; font-weight:700;">' + fmt(r.total_attended) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.meeting_training) + '</td>' +
          '<td style="border-right:1px solid #cbd5e1; padding:6px 4px;">' + fmt(r.on_leave) + '</td>' +
          '<td style="padding:6px 4px;">' + (r.not_reported != null ? r.not_reported : 0) + '</td>' +
          '</tr>';
      });
      tbody.innerHTML = rowsHtml;
    }

    var tfoot = document.getElementById('state-format-tfoot');
    if (tfoot && data.total_row) {
      var tot = data.total_row;
      var totPct = Number(tot.pct_before_9 || 0);
      var totHtml = '<tr style="background:#ffffff; font-weight:800; border-top:1.5px solid #1e293b;">' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;"></td>' +
        '<td style="border-right:1px solid #334155; padding:7px 8px; text-align:left; font-weight:800; font-size:0.9rem;">Total</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.total_gps || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.full_time_working || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.b_6_9 || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.b_9_10 || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.b_10_11 || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.b_11_12 || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.b_after_12 || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px; font-weight:900; color:#c00000;">' + totPct.toFixed(2) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.total_attended || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.meeting_training || 0) + '</td>' +
        '<td style="border-right:1px solid #334155; padding:7px 4px;">' + (tot.on_leave || 0) + '</td>' +
        '<td style="padding:7px 4px;">' + (tot.not_reported != null ? tot.not_reported : 0) + '</td>' +
        '</tr>';

      if (data.percentage_row) {
        var p = data.percentage_row;
        totHtml += '<tr style="background:#ffffff; font-weight:800; color:#c00000; border-top:1px solid #334155; border-bottom:2px double #1e293b;">' +
          '<td style="border-right:1px solid #334155; padding:7px 4px;"></td>' +
          '<td style="border-right:1px solid #334155; padding:7px 8px; text-align:left; font-weight:800; color:#c00000;">Percentage</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px;"></td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px;"></td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.b_6_9 != null ? Number(p.b_6_9).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.b_9_10 != null ? Number(p.b_9_10).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.b_10_11 != null ? Number(p.b_10_11).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.b_11_12 != null ? Number(p.b_11_12).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.b_after_12 != null ? Number(p.b_after_12).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px;"></td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.total_attended != null ? Number(p.total_attended).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.meeting_training != null ? Number(p.meeting_training).toFixed(2) : '') + '</td>' +
          '<td style="border-right:1px solid #334155; padding:7px 4px; color:#c00000;">' + (p.on_leave != null ? Number(p.on_leave).toFixed(2) : '') + '</td>' +
          '<td style="padding:7px 4px; color:#c00000;">' + (p.not_reported != null ? Number(p.not_reported).toFixed(2) : '') + '</td>' +
          '</tr>';
      }

      tfoot.innerHTML = totHtml;
    }

    var resCard = document.getElementById('state-format-results');
    if (resCard) {
      resCard.style.display = 'block';
      resCard.scrollIntoView({ behavior: 'smooth' });
    }
  };
})();
