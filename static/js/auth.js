/**
 * e-Panchayat Automation — Dual-Domain Authentication, Branding & Shell Controller
 * Scopes: Platform 1 ('portal' -> panchayatautomation.in) & Platform 2 ('console' -> reports.panchayatautomation.in)
 */
(function () {
  'use strict';

  var PLATFORM_NAME = 'e-Panchayat Automation';
  var CONSOLE_NAME = 'e-Panchayat Automation Console';
  var WELCOME_MESSAGE = 'Welcome to ' + PLATFORM_NAME;
  var DESIGNATIONS = ['DPO', 'DPM', 'DLPO', 'MPDO', 'MPO', 'PS', 'DEO'];
  var ROLES = ['Mandal Level', 'Division Level', 'District Level'];

  window.FIREBASE_CONFIG = null;
  window.isPortalAuthenticated = false;
  window.currentAccessPolicy = {};
  window._profileModalMode = 'register';

  var noticeTimer = null;
  var confirmResolver = null;

  // ---------------------------------------------------------------------------
  // Scope, Origin & HTML Escaping Utilities
  // ---------------------------------------------------------------------------

  window.escapeHtml = function (str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  window.isAdminHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    return host.indexOf('admin.') === 0 || host.indexOf('www.admin.') === 0;
  };

  window.isProdCustomDomain = function () {
    var host = (window.location.hostname || '').toLowerCase();
    return host === 'panchayatautomation.in' || host === 'www.panchayatautomation.in' || host.slice(-23) === '.panchayatautomation.in';
  };

  window.isReportsHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    return (
      host.indexOf('autoreports.') === 0 ||
      host.indexOf('www.autoreports.') === 0 ||
      host.indexOf('reports.') === 0 ||
      host.indexOf('www.reports.') === 0
    );
  };

  window.isManualHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    return host.indexOf('manualreports.') === 0 || host.indexOf('www.manualreports.') === 0;
  };

  window.isToolsHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    return host.indexOf('tools.') === 0 || host.indexOf('www.tools.') === 0;
  };

  window.getDedicatedPageSection = function () {
    if (window.isReportsHost()) return 'automated';
    if (window.isManualHost()) return 'manual';
    if (window.isToolsHost()) return 'tools';
    var path = (window.location.pathname || '').toLowerCase();
    if (path === '/autoreports' || path === '/eptauto' || path === '/naresh' || path.indexOf('/reports') === 0 || path === '/mas') {
      return 'automated';
    }
    if (path === '/manualreports') return 'manual';
    if (path === '/tools' || path.indexOf('/tools/') === 0) return 'tools';
    return null;
  };

  window.getSectionUrl = function (section) {
    var s = String(section || '').trim().toLowerCase();
    if (window.isProdCustomDomain()) {
      if (s === 'automated') return 'https://www.autoreports.panchayatautomation.in/';
      if (s === 'manual') return 'https://www.manualreports.panchayatautomation.in/';
      if (s === 'tools') return 'https://www.tools.panchayatautomation.in/';
      return 'https://panchayatautomation.in/';
    }
    if (s === 'automated') return '/autoreports?site=console';
    if (s === 'manual') return '/manualreports';
    if (s === 'tools') return '/tools';
    return '/';
  };

  window.isConsoleScope = function () {
    if (window.isReportsHost()) return true;
    var path = (window.location.pathname || '').toLowerCase();
    if (path.indexOf('/reports') === 0 || path === '/mas' || path === '/autoreports' || path === '/eptauto' || path === '/naresh') return true;
    try {
      var site = (new URLSearchParams(window.location.search).get('site') || '').trim().toLowerCase();
      if (site === 'reports' || site === 'console') return true;
      if (site === 'portal') return false;
    } catch (e) {}
    return false;
  };

  window.getPlatformScope = function () {
    return window.isConsoleScope() ? 'console' : 'portal';
  };

  function tokenStorageKey(scope) {
    return scope === 'console' ? 'console_token' : 'portal_token';
  }

  function authFlagKey(scope) {
    return scope === 'console' ? 'portal_auth_console' : 'portal_auth_portal';
  }

  function userStorageKey(scope) {
    return scope === 'console' ? 'portal_user_console' : 'portal_user_portal';
  }

  window.getScopedAuthToken = function (scope) {
    var sc = scope || window.getPlatformScope();
    try {
      return sessionStorage.getItem(tokenStorageKey(sc)) || '';
    } catch (e) {
      return '';
    }
  };

  window.setScopedAuthToken = function (token, scope) {
    var sc = scope || window.getPlatformScope();
    try {
      if (token) {
        sessionStorage.setItem(tokenStorageKey(sc), String(token));
      } else {
        sessionStorage.removeItem(tokenStorageKey(sc));
      }
    } catch (e) {}
  };

  window.getScopedUser = function (scope) {
    var sc = scope || window.getPlatformScope();
    try {
      return JSON.parse(sessionStorage.getItem(userStorageKey(sc)) || 'null');
    } catch (e) {
      return null;
    }
  };

  window.setScopedUser = function (user, scope) {
    var sc = scope || window.getPlatformScope();
    try {
      if (user) {
        sessionStorage.setItem(authFlagKey(sc), 'true');
        sessionStorage.setItem(userStorageKey(sc), JSON.stringify(user));
      } else {
        sessionStorage.removeItem(authFlagKey(sc));
        sessionStorage.removeItem(userStorageKey(sc));
      }
    } catch (e) {}
  };

  window.clearScopeSessionStorage = function (scope) {
    var sc = scope || window.getPlatformScope();
    try {
      sessionStorage.removeItem(tokenStorageKey(sc));
      sessionStorage.removeItem(authFlagKey(sc));
      sessionStorage.removeItem(userStorageKey(sc));
      if (sc === 'console') {
        sessionStorage.removeItem('epts_portal_auth');
        sessionStorage.removeItem('epts_dept_session');
        sessionStorage.removeItem('epts_officer_id');
        sessionStorage.removeItem('epts_user_level');
        sessionStorage.removeItem('epts_mandal_name');
        sessionStorage.removeItem('epts_district_name');
        sessionStorage.removeItem('epts_office_name');
      }
    } catch (e) {}
  };

  // ---------------------------------------------------------------------------
  // Client Session ID & Scoped Fetch Interceptor (Same-Origin Only)
  // ---------------------------------------------------------------------------

  window.getEptsSessionId = function () {
    if (window.DeptSessionManager && typeof window.DeptSessionManager.getSessionId === 'function') {
      return window.DeptSessionManager.getSessionId();
    }
    var sid = '';
    try {
      sid = sessionStorage.getItem('epts_session_id') || '';
    } catch (e) {}
    if (!sid) {
      try {
        sid = localStorage.getItem('epts_session_id') || '';
      } catch (e) {}
    }
    if (!sid || sid.length < 8) {
      sid =
        'sid_' +
        Date.now().toString(36) +
        '_' +
        Math.random().toString(36).substring(2, 10) +
        Math.random().toString(36).substring(2, 10);
    }
    try {
      sessionStorage.setItem('epts_session_id', sid);
    } catch (e) {}
    try {
      localStorage.setItem('epts_session_id', sid);
    } catch (e) {}
    return sid;
  };

  function _hasClientStoredSid() {
    try {
      var s1 = sessionStorage.getItem('epts_session_id') || '';
      var s2 = localStorage.getItem('epts_session_id') || '';
      return s1.length >= 8 || s2.length >= 8;
    } catch (e) {
      return false;
    }
  }

  (function wrapSameOriginFetch() {
    var origFetch = window.fetch;
    if (!origFetch) return;
    window.fetch = function (resource, init) {
      var urlStr = '';
      if (typeof resource === 'string') {
        urlStr = resource;
      } else if (resource && typeof resource.url === 'string') {
        urlStr = resource.url;
      }

      var isSameOrigin = false;
      try {
        if (!urlStr || urlStr.charAt(0) === '/') {
          isSameOrigin = true;
        } else {
          var parsed = new URL(urlStr, window.location.origin);
          isSameOrigin = parsed.origin === window.location.origin;
        }
      } catch (e) {
        isSameOrigin = false;
      }

      if (!isSameOrigin) {
        return origFetch.call(this, resource, init);
      }

      var opts = init ? Object.assign({}, init) : {};
      var headers = new Headers(opts.headers || {});
      var scope = window.getPlatformScope();
      var scopedTok = window.getScopedAuthToken(scope);
      var isPortalBootCall = urlStr.indexOf('/api/auth/portal-status') !== -1 || urlStr.indexOf('/api/auth/me') !== -1;

      if (!headers.has('X-Session-ID') && (_hasClientStoredSid() || !isPortalBootCall)) {
        headers.set('X-Session-ID', window.getEptsSessionId());
      }
      if (!headers.has('X-Platform-Scope')) {
        headers.set('X-Platform-Scope', scope);
      }
      if (scopedTok) {
        if (scope === 'console' && !headers.has('X-Console-Token')) {
          headers.set('X-Console-Token', scopedTok);
        } else if (scope === 'portal' && !headers.has('X-Portal-Token')) {
          headers.set('X-Portal-Token', scopedTok);
        }
      }
      opts.headers = headers;
      if (!opts.credentials) {
        opts.credentials = 'same-origin';
      }
      return origFetch.call(this, resource, opts);
    };
  })();

  window.safeFetchJson = async function (url, options) {
    var res = await fetch(url, options || {});
    var contentType = res.headers.get('content-type') || '';
    var data = null;
    var rawText = '';
    if (contentType.indexOf('application/json') !== -1) {
      try {
        data = await res.json();
      } catch (e) {
        data = null;
      }
    } else {
      rawText = await res.text().catch(function () {
        return '';
      });
    }

    if (!res.ok) {
      var errMsg = '';
      if (data && data.detail) {
        errMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      } else if (data && data.message) {
        errMsg = data.message;
      } else {
        if (!rawText) {
          rawText = await res.text().catch(function () {
            return '';
          });
        }
        if (rawText.indexOf('<!DOCTYPE') !== -1 || rawText.indexOf('<html') !== -1) {
          errMsg = 'Server returned HTTP ' + res.status + ' (' + (res.statusText || 'Error') + ').';
        } else {
          errMsg = rawText || 'Request failed with HTTP ' + res.status;
        }
      }
      var err = new Error(errMsg);
      err.status = res.status;
      err.deptAuthRequired = res.headers.get('X-Dept-Auth-Required') === 'true' || res.status === 401;
      throw err;
    }
    return data || {};
  };

  // ---------------------------------------------------------------------------
  // Non-Blocking Notice Banner, Confirmation Modal & Navigation Controls
  // ---------------------------------------------------------------------------

  window.showPortalNotice = function (message, type, autoHideMs) {
    var banner = document.getElementById('portal-notice-banner');
    var textEl = document.getElementById('portal-notice-text');
    if (!banner || !textEl) return;
    if (noticeTimer) {
      clearTimeout(noticeTimer);
      noticeTimer = null;
    }
    var kind = type || 'info';
    banner.className = 'portal-notice-banner ' + kind;
    textEl.textContent = String(message || '');
    banner.style.display = 'flex';
    var hideMs = typeof autoHideMs === 'number' ? autoHideMs : 6500;
    if (hideMs > 0) {
      noticeTimer = setTimeout(function () {
        window.clearPortalNotice();
      }, hideMs);
    }
  };

  window.clearPortalNotice = function () {
    var banner = document.getElementById('portal-notice-banner');
    if (banner) banner.style.display = 'none';
    if (noticeTimer) {
      clearTimeout(noticeTimer);
      noticeTimer = null;
    }
  };

  window.showConfirmModal = function (optsOrTitle, maybeMessage, extraOpts) {
    var modal = document.getElementById('portal-confirm-modal');
    var titleEl = document.getElementById('confirm-modal-title');
    var msgEl = document.getElementById('confirm-modal-message');
    var okBtn = document.getElementById('confirm-modal-ok');
    var cancelBtn = document.getElementById('confirm-modal-cancel');
    if (!modal || !okBtn || !cancelBtn) {
      return Promise.resolve(false);
    }
    if (confirmResolver) {
      confirmResolver(false);
      confirmResolver = null;
    }
    var cfg = {};
    if (optsOrTitle && typeof optsOrTitle === 'object') {
      cfg = optsOrTitle;
    } else {
      cfg = Object.assign(
        {
          title: optsOrTitle ? String(optsOrTitle) : '',
          message: maybeMessage ? String(maybeMessage) : '',
        },
        extraOpts && typeof extraOpts === 'object' ? extraOpts : {}
      );
    }
    if (titleEl) titleEl.textContent = cfg.title || 'Confirm Action';
    if (msgEl) msgEl.textContent = cfg.message || 'Please confirm to proceed.';
    okBtn.textContent = cfg.confirmLabel || 'Confirm';
    cancelBtn.textContent = cfg.cancelLabel || 'Cancel';
    okBtn.className = cfg.danger ? 'btn btn-danger btn-sm' : 'btn btn-gold btn-sm';
    modal.style.display = 'flex';

    return new Promise(function (resolve) {
      confirmResolver = resolve;
      okBtn.onclick = function () {
        modal.style.display = 'none';
        var r = confirmResolver;
        confirmResolver = null;
        if (r) r(true);
      };
      cancelBtn.onclick = function () {
        modal.style.display = 'none';
        var r = confirmResolver;
        confirmResolver = null;
        if (r) r(false);
      };
    });
  };

  window.toggleMobileNav = function () {
    var nav = document.getElementById('main-nav-links');
    var btn = document.getElementById('nav-hamburger-btn');
    if (!nav) return;
    var isOpen = nav.classList.toggle('mobile-open');
    if (btn) btn.classList.toggle('open', isOpen);
  };

  window.closeMobileNav = function () {
    var nav = document.getElementById('main-nav-links');
    var btn = document.getElementById('nav-hamburger-btn');
    if (nav) nav.classList.remove('mobile-open');
    if (btn) btn.classList.remove('open');
  };

  function closeModalByIdSafely(id) {
    var m = document.getElementById(id);
    if (!m || m.style.display !== 'flex') return;
    var closerMap = {
      'dept-login-modal': window.closeDepartmentLoginModal,
      'privacy-legal-modal': window.closePrivacyLegalModal,
      'feedback-modal': window.closeFeedbackModal,
      'upcoming-modal': window.closeUpcomingModal,
      'sessions-modal': window.closeSessionsModal,
      'insp-detail-modal': window.closeInspModal,
    };
    var closer = closerMap[id];
    if (typeof closer === 'function') {
      closer();
    } else {
      m.style.display = 'none';
    }
  }

  document.addEventListener('click', function (e) {
    var nav = document.getElementById('main-nav-links');
    var btn = document.getElementById('nav-hamburger-btn');
    if (nav && nav.classList.contains('mobile-open')) {
      if (!nav.contains(e.target) && (!btn || !btn.contains(e.target))) {
        window.closeMobileNav();
      }
    }
    var confirmModal = document.getElementById('portal-confirm-modal');
    if (confirmModal && e.target === confirmModal) {
      confirmModal.style.display = 'none';
      if (confirmResolver) {
        var r = confirmResolver;
        confirmResolver = null;
        r(false);
      }
    }
    ['upcoming-modal', 'sessions-modal', 'insp-detail-modal', 'privacy-legal-modal', 'feedback-modal', 'dept-login-modal'].forEach(function (id) {
      var m = document.getElementById(id);
      if (m && e.target === m) {
        closeModalByIdSafely(id);
      }
    });
    var profModal = document.getElementById('officer-profile-modal');
    if (profModal && e.target === profModal && window._profileModalMode === 'view') {
      profModal.style.display = 'none';
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    window.closeMobileNav();
    var confirmModal = document.getElementById('portal-confirm-modal');
    if (confirmModal && confirmModal.style.display === 'flex') {
      confirmModal.style.display = 'none';
      if (confirmResolver) {
        var r = confirmResolver;
        confirmResolver = null;
        r(false);
      }
    }
    ['upcoming-modal', 'sessions-modal', 'insp-detail-modal', 'privacy-legal-modal', 'feedback-modal', 'dept-login-modal'].forEach(function (id) {
      closeModalByIdSafely(id);
    });
    if (window._profileModalMode === 'view') {
      var profModal = document.getElementById('officer-profile-modal');
      if (profModal && profModal.style.display === 'flex') profModal.style.display = 'none';
    }
  });

  // ---------------------------------------------------------------------------
  // Station Visibility & Dual-Domain Branding / Links
  // ---------------------------------------------------------------------------

  window.hideAllStations = function () {
    [
      'portal-hero-card',
      'post-login-dashboard',
      'admin-dashboard-station',
      'automation-station',
      'balance-station',
      'tax-dcb-station',
      'inspections-station',
      'results-section',
      'btn-back-dashboard-wrap',
    ].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
  };

  window.updatePlatformUrlLinks = function () {
    var onReports = window.isReportsHost();
    var onManual = window.isManualHost();
    var onTools = window.isToolsHost();
    var dedSection = window.getDedicatedPageSection();
    var isCon = window.isConsoleScope();
    var consoleDest = window.getSectionUrl('automated');
    var manualDest = window.getSectionUrl('manual');
    var toolsDest = window.getSectionUrl('tools');
    var switchLink = document.getElementById('login-switch-platform-link');
    var navConsoleSwitch = document.getElementById('nav-btn-console-switch');
    var heroCrossLink = document.getElementById('dash-hero-cross-link');
    var deptOpenConsole = document.getElementById('dept-modal-open-console-link');
    var scopedSubpageLinks = [
      { id: 'nav-btn-services', base: '/services' },
      { id: 'console-mas-link', base: '/reports/mas' },
      { id: 'login-services-link', base: '/services' },
      { id: 'privacy-fullpage-link', base: '/privacy-legal' },
      { id: 'btn-open-tool-excel', base: '/tools/excel' },
      { id: 'btn-open-tool-pdf', base: '/tools/pdf' },
      { id: 'btn-open-studio-workspace', base: '/reports/ps-attendance', hash: '#reports' },
      { id: 'btn-launch-free-dsr', base: '/reports/ps-attendance', hash: '#reports' },
    ];
    scopedSubpageLinks.forEach(function (cfg) {
      var el = document.getElementById(cfg.id);
      if (!el) return;
      var suffix = cfg.hash || '';
      if (onReports || !isCon) {
        el.href = cfg.base + suffix;
      } else {
        el.href = cfg.base + '?site=console' + suffix;
      }
    });

    var secNavLinks = [
      { id: 'login-link-autoreports', sec: 'automated', href: consoleDest },
      { id: 'login-link-manualreports', sec: 'manual', href: manualDest },
      { id: 'login-link-tools', sec: 'tools', href: toolsDest },
    ];
    secNavLinks.forEach(function (item) {
      var a = document.getElementById(item.id);
      if (!a) return;
      a.href = item.href;
      a.style.display = dedSection === item.sec ? 'none' : 'inline-flex';
    });

    if (onReports) {
      if (switchLink) {
        switchLink.href = manualDest;
        switchLink.textContent = 'Open Manual Reports ↗';
      }
      if (navConsoleSwitch) navConsoleSwitch.href = consoleDest;
      if (heroCrossLink) heroCrossLink.href = manualDest;
      if (deptOpenConsole) deptOpenConsole.href = '/';
    } else if (onManual) {
      if (switchLink) {
        switchLink.href = consoleDest;
        switchLink.textContent = 'Open Automated Reports ↗';
      }
      if (navConsoleSwitch) navConsoleSwitch.href = consoleDest;
      if (heroCrossLink) heroCrossLink.href = consoleDest;
      if (deptOpenConsole) deptOpenConsole.href = consoleDest;
    } else if (onTools) {
      if (switchLink) {
        switchLink.href = manualDest;
        switchLink.textContent = 'Open Manual Reports ↗';
      }
      if (navConsoleSwitch) navConsoleSwitch.href = consoleDest;
      if (heroCrossLink) heroCrossLink.href = manualDest;
      if (deptOpenConsole) deptOpenConsole.href = consoleDest;
    } else {
      if (switchLink) {
        switchLink.href = isCon ? '/?site=portal' : consoleDest;
        switchLink.textContent = isCon ? 'Open Reporting Portal ↗' : 'Open Console ↗';
      }
      if (navConsoleSwitch) navConsoleSwitch.href = consoleDest;
      if (heroCrossLink) heroCrossLink.href = isCon ? '/?site=portal' : consoleDest;
      if (deptOpenConsole) deptOpenConsole.href = isCon ? '/?site=console' : '/';
    }
  };

  window.applyPlatformScopeBranding = function () {
    var section = window.getDedicatedPageSection() || (window.isConsoleScope() ? 'automated' : '');
    var isConsole = section === 'automated';
    var brandingMap = {
      automated: {
        docTitle: CONSOLE_NAME + ' | ' + PLATFORM_NAME,
        chipText: CONSOLE_NAME,
        showChip: true,
        heroName: CONSOLE_NAME,
        loginSub: 'Sign in with your Google account to access the ' + CONSOLE_NAME,
        dashTitle: CONSOLE_NAME + ' · Executive Report Modules',
        dashSub: 'Connect your Departmental e-Panchayat login or launch automated portal reporting robots below.',
      },
      manual: {
        docTitle: 'Manual Reports | ' + PLATFORM_NAME,
        chipText: 'Manual Reports Studio',
        showChip: true,
        heroName: 'e-Panchayat Manual Reports',
        loginSub: 'Sign in with your Google account to access Manual Reports',
        dashTitle: PLATFORM_NAME + ' · Manual Reporting Workspace',
        dashSub: 'Offline spreadsheet processing and Live House Tax DCB analytics with zero e-Panchayat portal login.',
      },
      tools: {
        docTitle: 'Tools Studio | ' + PLATFORM_NAME,
        chipText: 'Tools & Utilities Studio',
        showChip: true,
        heroName: 'e-Panchayat Tools & Utilities Studio',
        loginSub: 'Sign in with your Google account to access Excel & PDF Tools Studio',
        dashTitle: PLATFORM_NAME + ' · Tools & Utility Studios',
        dashSub: 'Launch spreadsheet converters, cleaners, banking formatters, and PDF utilities directly inside your workspace.',
      },
    };
    var cfg = brandingMap[section] || {
      docTitle: PLATFORM_NAME,
      chipText: CONSOLE_NAME,
      showChip: false,
      heroName: WELCOME_MESSAGE,
      loginSub: 'Sign in with your Google account to access ' + PLATFORM_NAME,
      dashTitle: PLATFORM_NAME + ' · Executive Report Modules',
      dashSub: 'Select a reporting module below to upload spreadsheets, analyze metrics, and generate official PDF and Excel outputs.',
    };

    document.title = cfg.docTitle;
    var displayInline = cfg.showChip ? 'inline-flex' : 'none';
    ['hero-console-chip', 'login-console-badge'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.style.display = displayInline;
        el.textContent = cfg.chipText;
      }
    });

    var heroName = document.getElementById('hero-platform-name');
    if (heroName) heroName.textContent = cfg.heroName;

    var loginSub = document.getElementById('login-panel-subtitle');
    if (loginSub) loginSub.textContent = cfg.loginSub;

    var dashTitle = document.getElementById('dash-hero-title');
    if (dashTitle) dashTitle.textContent = cfg.dashTitle;

    var dashSub = document.getElementById('dash-scope-subtitle');
    if (dashSub) dashSub.textContent = cfg.dashSub;

    var crossTitle = document.getElementById('dash-hero-cross-title');
    var crossDesc = document.getElementById('dash-hero-cross-desc');
    var crossLink = document.getElementById('dash-hero-cross-link');
    if (crossTitle) {
      crossTitle.textContent = isConsole
        ? '📊 Prefer Offline Manual Reports Without Portal OTP Login?'
        : '🤖 Need Departmental Portal Scraping & Robot Automation?';
    }
    if (crossDesc) {
      crossDesc.textContent = isConsole
        ? 'Switch back to e-Panchayat Automation Portal for instant Excel-to-PDF and Excel-to-Workbook Manual Reports.'
        : 'Switch to the e-Panchayat Automation Console for live EPTS Captcha/OTP Login, DSR Robot & Balance Robot Automation.';
    }
    if (crossLink) {
      crossLink.textContent = isConsole
        ? '📊 Open Manual Reports Portal →'
        : '🏛️ Open e-Panchayat Automation Console →';
    }
  };

  // ---------------------------------------------------------------------------
  // Dynamic Access Policy Enforcement on Cards & Pills
  // ---------------------------------------------------------------------------

  var DEFAULT_BADGE_LABELS = {
    module_dsr_excel: '',
    module_dcb_live: '● Live Analytics',
    module_dsr_automation: '● Active Robot',
    module_gp_balance_automation: '● Active Robot',
    module_mas_automation: '● Live',
  };

  var UPCOMING_BADGE_LABELS = {
    module_dsr_multiday: 'Upcoming',
  };

  window.applyAccessPolicyUi = function (policy) {
    var flags = policy && policy.flags ? policy.flags : policy || {};
    window.currentAccessPolicy = Object.assign({}, flags);

    var policyKeys = Object.keys(DEFAULT_BADGE_LABELS).concat(Object.keys(UPCOMING_BADGE_LABELS));
    policyKeys.forEach(function (key) {
      var isUpcoming = Object.prototype.hasOwnProperty.call(UPCOMING_BADGE_LABELS, key);
      var enabled = flags[key] !== false;
      var card = document.getElementById('card-policy-' + key);
      var badge = document.getElementById('badge-policy-' + key);
      if (card) {
        card.classList.toggle('policy-disabled', !enabled);
        var btns = card.querySelectorAll('button, a.btn');
        btns.forEach(function (b) {
          if (b.tagName === 'BUTTON') {
            b.disabled = !enabled;
          } else {
            b.style.pointerEvents = enabled ? '' : 'none';
            b.style.opacity = enabled ? '' : '0.6';
            if (enabled) {
              b.removeAttribute('aria-disabled');
              b.removeAttribute('tabindex');
            } else {
              b.setAttribute('aria-disabled', 'true');
              b.setAttribute('tabindex', '-1');
            }
          }
        });
      }
      if (badge) {
        if (!enabled) {
          badge.style.display = 'inline-flex';
          badge.className = 'badge-pill-soon';
          badge.textContent = '⏸ Paused by Admin';
        } else if (isUpcoming) {
          badge.style.display = 'inline-flex';
          badge.className = 'badge-pill-soon';
          badge.textContent = UPCOMING_BADGE_LABELS[key];
        } else if (DEFAULT_BADGE_LABELS[key]) {
          badge.style.display = 'inline-flex';
          badge.className = 'badge-pill-live';
          badge.textContent = DEFAULT_BADGE_LABELS[key];
        } else {
          badge.style.display = 'none';
          badge.textContent = '';
        }
      }
    });

    var consoleTaxCard = document.getElementById('console-tax-card');
    if (consoleTaxCard) {
      var liveEnabled = flags.module_dcb_live !== false;
      consoleTaxCard.classList.toggle('policy-disabled', !liveEnabled);
      consoleTaxCard.querySelectorAll('button').forEach(function (b) {
        b.disabled = !liveEnabled;
      });
    }

    var badgeAutoMode = document.getElementById('badge-automated-mode-access');
    var noteAutoSub = document.getElementById('automated-subscription-note');
    var subRequired = flags.automated_subscription_required === true;
    var u = typeof window.getScopedUser === 'function' ? window.getScopedUser() : null;
    var hasSub = Boolean(u && (u.has_automated_subscription || u.subscription_status === 'active'));
    if (badgeAutoMode) {
      if (flags.console_enabled === false) {
        badgeAutoMode.style.display = 'inline-flex';
        badgeAutoMode.className = 'badge-pill-soon';
        badgeAutoMode.textContent = '⏸ Paused by Admin';
      } else if (subRequired && !hasSub) {
        badgeAutoMode.style.display = 'inline-flex';
        badgeAutoMode.className = 'badge-pill-soon';
        badgeAutoMode.textContent = '🔒 Subscription Required';
      } else if (subRequired && hasSub) {
        badgeAutoMode.style.display = 'inline-flex';
        badgeAutoMode.className = 'badge-pill-live';
        badgeAutoMode.textContent = '● Subscription Active';
      } else {
        badgeAutoMode.style.display = 'none';
        badgeAutoMode.textContent = '';
      }
    }
    if (noteAutoSub) {
      if (subRequired && !hasSub) {
        noteAutoSub.style.display = 'block';
        noteAutoSub.style.background = '#fef2f2';
        noteAutoSub.style.borderColor = '#fca5a5';
        noteAutoSub.style.color = '#991b1b';
        noteAutoSub.textContent = '🔒 Active subscription required to access Automated Reports Console.';
      } else {
        noteAutoSub.style.display = 'none';
        noteAutoSub.textContent = '';
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Firebase Authentication (Google Sign-In Provider)
  // ---------------------------------------------------------------------------

  function showLoginAlert(message, type) {
    var box = document.getElementById('portal-login-alert');
    if (!box) return;
    if (!message) {
      box.style.display = 'none';
      return;
    }
    var kind = type || 'error';
    if (kind === 'success') {
      box.style.background = '#ecfdf5';
      box.style.border = '1.5px solid #6ee7b7';
      box.style.color = '#065f46';
    } else if (kind === 'warning') {
      box.style.background = '#fffbeb';
      box.style.border = '1.5px solid #fcd34d';
      box.style.color = '#92400e';
    } else {
      box.style.background = '#fef2f2';
      box.style.border = '1.5px solid #f87171';
      box.style.color = '#991b1b';
    }
    box.textContent = String(message);
    box.style.display = 'block';
  }

  window.renderAuthErrorFromQuery = function () {
    var err = '';
    try {
      err = (new URLSearchParams(window.location.search).get('error') || '').trim();
    } catch (e) {
      return;
    }
    if (!err) return;

    var messages = {
      account_disabled: 'Your account has been disabled by an administrator. Please contact district support.',
      access_restricted: 'Access to this platform is currently restricted for your account.',
      platform_disabled: 'This platform is temporarily paused by administrator policy.',
      cancelled: 'Google Sign-In was cancelled before completion.',
      access_denied: 'Google Sign-In permission was declined.',
      auth_failed: 'Firebase authentication failed. Please retry with your official Google account.',
    };
    var msg = messages[err] || 'Authentication error: ' + err.replace(/_/g, ' ');
    showLoginAlert(msg, 'error');
    window.showPortalNotice(msg, 'error', 9000);
  };

  function setGoogleButtonBusy(isBusy, labelText) {
    var btn = document.getElementById('btn-google-login-action');
    if (!btn) return;
    btn.disabled = Boolean(isBusy);
    var span = btn.querySelector('span');
    if (span) {
      span.textContent = isBusy ? (labelText || 'Connecting to Firebase...') : 'Sign in with Google';
    }
  }

  window.exchangeFirebaseIdToken = async function (idToken) {
    if (!idToken) {
      showLoginAlert('Firebase did not return an identity token. Please try again.', 'error');
      return false;
    }
    setGoogleButtonBusy(true, 'Verifying Officer Account...');
    try {
      var res = await fetch('/api/auth/firebase-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken }),
      });
      var data = await res.json().catch(function () {
        return { success: false, message: 'Unexpected server response (HTTP ' + res.status + ').' };
      });
      if (res.ok && data && data.success) {
        window.handleFirebaseLoginSuccess(data);
        return true;
      }
      var errMsg = (data && (data.message || data.detail)) || 'Firebase login verification failed.';
      showLoginAlert(errMsg, 'error');
      window.showPortalNotice(errMsg, 'error');
      return false;
    } catch (err) {
      var netMsg = 'Authentication error: ' + (err && err.message ? err.message : 'Network failure');
      showLoginAlert(netMsg, 'error');
      window.showPortalNotice(netMsg, 'error');
      return false;
    } finally {
      setGoogleButtonBusy(false);
    }
  };

  window.triggerGoogleSignIn = async function () {
    showLoginAlert('');
    if (!window.FirebasePortalAuth || typeof window.FirebasePortalAuth.signInWithGoogle !== 'function') {
      showLoginAlert('Firebase Authentication SDK is still initializing. Please try again in a moment.', 'warning');
      return;
    }
    setGoogleButtonBusy(true, 'Signing in with Google...');
    try {
      var result = await window.FirebasePortalAuth.signInWithGoogle();
      if (result && result.redirected) {
        return;
      }
      if (result && result.idToken) {
        await window.exchangeFirebaseIdToken(result.idToken);
      }
    } catch (err) {
      var code = err && err.code ? String(err.code) : '';
      var msg = '';
      if (code === 'auth/popup-closed-by-user' || code === 'auth/cancelled-popup-request') {
        msg = 'Google Sign-In popup was closed before completing login.';
        showLoginAlert(msg, 'warning');
      } else if (code === 'auth/unauthorized-domain') {
        msg = 'This domain is not yet added under Firebase Authentication Authorized Domains: ' + window.location.hostname;
        showLoginAlert(msg, 'error');
      } else if (code === 'auth/network-request-failed') {
        msg = 'Network error connecting to Firebase Authentication. Check your internet connection.';
        showLoginAlert(msg, 'error');
      } else {
        msg = 'Firebase Sign-In failed: ' + ((err && err.message) || code || 'Unknown error');
        showLoginAlert(msg, 'error');
      }
    } finally {
      setGoogleButtonBusy(false);
    }
  };

  window.handleFirebaseLoginSuccess = function (data) {
    var scope = (data && data.platform_scope) || window.getPlatformScope();
    if (data && data.token) {
      window.setScopedAuthToken(data.token, scope);
    }
    var user = (data && data.user) || {};
    window.setScopedUser(user, scope);
    window.currentWorkspaceMode = null;
    try { sessionStorage.removeItem('epts_workspace_mode'); } catch (e) {}
    showLoginAlert('');
    window.setPortalUI(true, user);

    var isCompleted = Boolean(user.profile_completed);
    if (!isCompleted || !user.designation || !user.mobile_number) {
      window.showOfficerProfileModal(user, { allowClose: false });
      return;
    }
    window.proceedAfterPortalAuth();
  };

  window.handleGoogleLoginSuccess = window.handleFirebaseLoginSuccess;

  window.proceedAfterPortalAuth = async function () {
    var urlSp = new URLSearchParams(window.location.search || '');
    var mgr = window.DeptSessionManager;
    var pending = mgr ? mgr.peekPendingAction() : null;
    if (!pending && urlSp.get('dept_login') === '1') {
      pending = {
        module: (urlSp.get('pending_module') || '').trim().toLowerCase(),
        reason: (urlSp.get('reason') || 'required').trim().toLowerCase(),
        autoGenerate: urlSp.get('auto_generate') === '1',
        params: {},
      };
    }

    var target = (urlSp.get('station') || urlSp.get('module') || '').trim().toLowerCase();
    var reqMode = (urlSp.get('mode') || '').trim().toLowerCase();
    var savedMode = '';
    try { savedMode = (sessionStorage.getItem('epts_workspace_mode') || '').trim().toLowerCase(); } catch (e) {}

    if ((pending && pending.module) || target === 'dsr' || target === 'balance' || target === 'balance-station' || target === 'mas' || reqMode === 'automated' || urlSp.get('dept_login') === '1') {
      window.selectWorkspaceMode('automated', { skipScroll: true });
    } else if (reqMode === 'manual' || target === 'dsr_excel' || target === 'manual-reports' || target === 'multiday') {
      window.selectWorkspaceMode('manual', { skipScroll: true });
    } else if (savedMode === 'manual' || savedMode === 'automated') {
      window.selectWorkspaceMode(savedMode, { skipScroll: true });
    } else {
      window.showWorkspaceModeSelector();
    }

    var deptAuthed = false;
    if (typeof window.initConsoleAfterPortalAuth === 'function') {
      deptAuthed = Boolean(await window.initConsoleAfterPortalAuth());
    }

    if (pending && pending.module) {
      if (deptAuthed && typeof window.resumePendingDepartmentAction === 'function') {
        if (mgr) mgr.consumePendingAction();
        await window.resumePendingDepartmentAction(pending);
      } else if (typeof window.openDepartmentLoginModal === 'function') {
        window.openDepartmentLoginModal(pending);
      }
      return;
    }

    if (urlSp.get('dept_login') === '1' && !deptAuthed && typeof window.openDepartmentLoginModal === 'function') {
      window.openDepartmentLoginModal();
    }
  };

  // ---------------------------------------------------------------------------
  // Officer Profile Registration & Edit View
  // ---------------------------------------------------------------------------

  window.syncDesignationToRole = function (desig) {
    var roleEl = document.getElementById('prof-role');
    if (!roleEl) return;
    if (desig === 'DPO' || desig === 'DPM') {
      roleEl.value = 'District Level';
    } else if (desig === 'DLPO') {
      roleEl.value = 'Division Level';
    } else if (['MPDO', 'MPO', 'PS', 'DEO'].indexOf(desig) !== -1) {
      roleEl.value = 'Mandal Level';
    }
  };

  window.closeOfficerProfileModal = function () {
    if (window._profileModalMode !== 'view') return;
    var modal = document.getElementById('officer-profile-modal');
    if (modal) modal.style.display = 'none';
  };

  window.openOfficerProfileView = function () {
    var userData = window.getScopedUser();
    if (!userData) {
      userData = {
        name: (document.getElementById('nav-user-name') && document.getElementById('nav-user-name').textContent) || '',
        designation: (document.getElementById('nav-user-desig') && document.getElementById('nav-user-desig').textContent) || '',
        role: (document.getElementById('nav-user-role') && document.getElementById('nav-user-role').textContent) || '',
        gmail: (document.getElementById('nav-user-gmail') && document.getElementById('nav-user-gmail').textContent) || '',
      };
    }
    window.showOfficerProfileModal(userData, { allowClose: true });
  };

  window.showOfficerProfileModal = function (userData, options) {
    var modal = document.getElementById('officer-profile-modal');
    if (!modal) return;
    var allowClose = Boolean(options && options.allowClose);
    window._profileModalMode = allowClose ? 'view' : 'register';

    var closeBtn = document.getElementById('prof-modal-close-btn');
    if (closeBtn) closeBtn.style.display = allowClose ? 'inline-block' : 'none';

    var titleEl = document.getElementById('prof-modal-title');
    if (titleEl) titleEl.textContent = allowClose ? 'Officer Profile' : 'User Profile Registration';

    var subEl = document.getElementById('prof-modal-subtitle');
    if (subEl) {
      subEl.textContent = allowClose
        ? 'View or update your ' + PLATFORM_NAME + ' officer profile'
        : 'Complete your official ' + PLATFORM_NAME + ' details to activate your account';
    }

    var saveBtn = document.getElementById('btn-save-profile');
    if (saveBtn) {
      saveBtn.innerHTML = allowClose
        ? '<span>💾</span> Save Profile Changes →'
        : '<span>📝</span> Submit / Complete Registration →';
    }

    var nameEl = document.getElementById('prof-name');
    var gmailEl = document.getElementById('prof-gmail');
    var phoneEl = document.getElementById('prof-phone');
    var desigEl = document.getElementById('prof-desig');
    var roleEl = document.getElementById('prof-role');

    if (nameEl) nameEl.value = (userData && userData.name) || '';
    if (gmailEl) gmailEl.value = (userData && (userData.gmail || userData.email)) || '';
    if (phoneEl) phoneEl.value = (userData && (userData.mobile_number || userData.phone)) || '';

    if (desigEl) {
      var uDesig = userData && userData.designation;
      if (uDesig && DESIGNATIONS.indexOf(uDesig) !== -1) {
        desigEl.value = uDesig;
      } else {
        desigEl.selectedIndex = 0;
      }
    }
    if (roleEl) {
      var uRole = userData && userData.role;
      if (uRole && ROLES.indexOf(uRole) !== -1) {
        roleEl.value = uRole;
      } else if (desigEl && desigEl.value) {
        window.syncDesignationToRole(desigEl.value);
      } else {
        roleEl.selectedIndex = 0;
      }
    }

    var alertEl = document.getElementById('profile-modal-alert');
    if (alertEl) alertEl.style.display = 'none';
    modal.style.display = 'flex';
  };

  window.handleOfficerProfileSubmit = async function (e) {
    if (e) e.preventDefault();
    var name = (document.getElementById('prof-name') && document.getElementById('prof-name').value || '').trim();
    var designation = (document.getElementById('prof-desig') && document.getElementById('prof-desig').value || '').trim();
    var role = (document.getElementById('prof-role') && document.getElementById('prof-role').value || '').trim();
    var phone = (document.getElementById('prof-phone') && document.getElementById('prof-phone').value || '').trim();
    var alertBox = document.getElementById('profile-modal-alert');
    var btn = document.getElementById('btn-save-profile');

    var showProfAlert = function (msg, isErr) {
      if (!alertBox) return;
      alertBox.style.display = 'block';
      alertBox.style.background = isErr ? '#fef2f2' : '#ecfdf5';
      alertBox.style.border = isErr ? '1.5px solid #f87171' : '1.5px solid #34d399';
      alertBox.style.color = isErr ? '#991b1b' : '#065f46';
      alertBox.textContent = msg;
    };

    if (!name) {
      showProfAlert('Please enter your Full Name.', true);
      return;
    }
    if (!designation) {
      showProfAlert('Please select your official Designation (DPO, DPM, DLPO, MPDO, MPO, PS, DEO).', true);
      return;
    }
    if (!role) {
      showProfAlert('Please select your Role / Access Level (Mandal Level, Division Level, District Level).', true);
      return;
    }
    var mobileClean = phone.replace(/[^0-9]/g, '');
    if (!/^[6-9][0-9]{9}$/.test(mobileClean)) {
      showProfAlert('Please enter a valid 10-digit Indian Mobile Number starting with 6, 7, 8, or 9.', true);
      return;
    }

    var wasEditMode = window._profileModalMode === 'view';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Saving Profile Details...';
    }
    if (alertBox) alertBox.style.display = 'none';

    try {
      var res = await fetch('/api/auth/register-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          designation: designation,
          role: role,
          mobile_number: mobileClean,
        }),
      });
      var data = await res.json().catch(function () {
        return { success: false, message: 'Server error while saving profile.' };
      });
      if (res.ok && data && data.success && data.user) {
        var sc = (data && data.platform_scope) || window.getPlatformScope();
        if (data.token) window.setScopedAuthToken(data.token, sc);
        window.setScopedUser(data.user, sc);
        window.setPortalUI(true, data.user);
        var modal = document.getElementById('officer-profile-modal');
        if (modal) modal.style.display = 'none';

        if (wasEditMode) {
          window.showPortalNotice('Officer profile updated successfully.', 'success');
        } else {
          window.showPortalNotice('Registration completed. ' + PLATFORM_NAME + ' dashboard activated!', 'success');
          await window.proceedAfterPortalAuth();
        }
      } else {
        showProfAlert((data && (data.message || data.detail)) || 'Failed to save profile details.', true);
      }
    } catch (err) {
      showProfAlert('Error saving profile: ' + err.message, true);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = window._profileModalMode === 'view'
          ? '<span>💾</span> Save Profile Changes →'
          : '<span>📝</span> Submit / Complete Registration →';
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Header UI, Dashboard Toggle & Scoped Logout
  // ---------------------------------------------------------------------------

  window.updateHeaderUserInfo = function (user) {
    var bar = document.getElementById('nav-officer-profile-bar');
    if (!bar) return;
    if (!user) {
      bar.style.display = 'none';
      return;
    }
    bar.style.display = 'flex';
    var nameEl = document.getElementById('nav-user-name');
    var desigEl = document.getElementById('nav-user-desig');
    var roleEl = document.getElementById('nav-user-role');
    var gmailEl = document.getElementById('nav-user-gmail');
    var avatarEl = document.getElementById('nav-user-avatar');
    var iconFallback = document.getElementById('nav-user-icon-fallback');

    if (nameEl) nameEl.textContent = user.name || 'Officer';
    if (desigEl) desigEl.textContent = user.designation || 'OFFICER';
    if (roleEl) roleEl.textContent = user.role || 'Mandal Level';
    if (gmailEl) gmailEl.textContent = user.gmail || user.email || '';

    if (user.profile_picture && avatarEl) {
      avatarEl.src = user.profile_picture;
      avatarEl.style.display = 'inline-block';
      if (iconFallback) iconFallback.style.display = 'none';
    } else {
      if (avatarEl) avatarEl.style.display = 'none';
      if (iconFallback) iconFallback.style.display = 'inline';
    }
  };

  window.applyScreenVisualState = function (stateName, user) {
    var body = document.body;
    if (!body) return;
    body.classList.remove(
      'state-home-login',
      'state-workspace-hub',
      'state-manual-page',
      'state-tools-page',
      'state-automation-page'
    );
    var resolved = stateName || 'state-home-login';
    body.classList.add(resolved);

    var eyebrow = document.getElementById('dash-welcome-eyebrow');
    var titleEl = document.getElementById('dash-hero-title');
    var taglineEl = document.getElementById('dash-tagline');
    var subEl = document.getElementById('dash-scope-subtitle');
    var hubBarTitle = document.getElementById('hub-bar-title');
    var hubBarSub = document.getElementById('hub-bar-sub');

    if (subEl) subEl.style.display = (resolved === 'state-automation-page') ? 'none' : 'block';

    if (resolved === 'state-workspace-hub') {
      var officerFirst = (user && user.name) ? user.name.trim() : '';
      if (eyebrow) eyebrow.textContent = '🧭 OFFICER WORKSPACE HUB';
      if (titleEl) {
        titleEl.textContent = officerFirst
          ? ('Welcome, ' + officerFirst + ' · Select Your Reporting Workspace')
          : 'Select Your Reporting & Utility Workspace';
      }
      if (taglineEl) taglineEl.textContent = 'Unified Panchayat Administration Hub — Choose a Workspace Below to Continue.';
      if (subEl) subEl.textContent = 'Pick Manual Excel Reports (offline), Automated Reports (live portal robots), or Tools & Utility Studios.';
      if (hubBarTitle) hubBarTitle.textContent = PLATFORM_NAME + ' · Workspace Selector';
      if (hubBarSub) hubBarSub.textContent = 'Signed in and ready — select Manual Reports, Automated Reports, or Tools.';
    } else if (resolved === 'state-manual-page') {
      if (eyebrow) eyebrow.textContent = '📊 MANUAL EXCEL REPORTS STUDIO';
      if (titleEl) titleEl.textContent = PLATFORM_NAME + ' · Manual Reporting Workspace';
      if (taglineEl) taglineEl.textContent = 'Upload GM-R Excel spreadsheets directly for instant District & Mandal reports.';
      if (subEl) subEl.textContent = 'Offline spreadsheet processing and Live House Tax DCB analytics with zero e-Panchayat portal login.';
      if (hubBarTitle) hubBarTitle.textContent = PLATFORM_NAME + ' · Manual Reports';
      if (hubBarSub) hubBarSub.textContent = 'Offline Excel report generation & Live DCB analytics workspace.';
    } else if (resolved === 'state-tools-page') {
      if (eyebrow) eyebrow.textContent = '🧰 DOCUMENT & DATA UTILITIES STUDIO';
      if (titleEl) titleEl.textContent = PLATFORM_NAME + ' · Tools & Utility Studios';
      if (taglineEl) taglineEl.textContent = 'Self-hosted Excel & Data Studio (70+ Tools) and All-in-One PDF Studio (14 Tools).';
      if (subEl) subEl.textContent = 'Launch spreadsheet converters, cleaners, banking formatters, and PDF utilities directly inside your workspace.';
      if (hubBarTitle) hubBarTitle.textContent = PLATFORM_NAME + ' · Tools Studio';
      if (hubBarSub) hubBarSub.textContent = 'Spreadsheet manipulation and PDF document tools workspace.';
    } else if (resolved === 'state-automation-page') {
      if (eyebrow) eyebrow.textContent = '⚡ AUTOMATION COMMAND CENTER';
      if (titleEl) titleEl.textContent = CONSOLE_NAME;
      if (taglineEl) taglineEl.textContent = 'Autonomous portal reporting for District & Mandal governance.';
    }
  };

  window.setPortalUI = function (isAuth, user) {
    window.isPortalAuthenticated = Boolean(isAuth);

    var isConsole = window.isConsoleScope();
    var heroCard = document.getElementById('portal-hero-card');
    var btnHome = document.getElementById('nav-btn-home');
    var btnStudio = document.getElementById('nav-btn-free-studio');
    var btnConsoleSwitch = document.getElementById('nav-btn-console-switch');
    var btnAdmin = document.getElementById('nav-btn-admin-dashboard');
    var btnServices = document.getElementById('nav-btn-services');
    var btnPrivacy = document.getElementById('nav-btn-privacy');
    var btnFeedback = document.getElementById('nav-btn-feedback');
    var btnLogout = document.getElementById('nav-btn-portal-logout');
    var btnDeptLogin = document.getElementById('nav-btn-dept-login');
    var btnDisconn = document.getElementById('nav-btn-disconnect-epts');
    var globalBar = document.getElementById('global-browser-status-bar');
    var dash = document.getElementById('post-login-dashboard');
    var portalSec = document.getElementById('portal-modules-section');
    var consoleSec = document.getElementById('console-modules-section');
    var officerBanner = document.getElementById('dash-officer-banner');
    var dashBadge = document.getElementById('dash-session-badge');
    var dashCrossBox = document.getElementById('dash-hero-cross-box');
    var loginSwitchLink = document.getElementById('login-switch-platform-link');
    var dcbSec = document.getElementById('live-dcb-analytics-section');

    window.updateHeaderUserInfo(isAuth ? user : null);

    if (loginSwitchLink) {
      loginSwitchLink.style.display = (window.isReportsHost() || window.isManualHost() || window.isToolsHost()) ? 'inline' : 'none';
    }
    if (dashCrossBox) {
      dashCrossBox.style.display = 'none';
    }

    var profileDone = Boolean(
      isAuth &&
      user &&
      user.profile_completed &&
      user.designation &&
      user.mobile_number
    );

    if (isAuth) {
      if (heroCard) heroCard.style.display = profileDone ? 'none' : 'flex';
      if (btnHome) btnHome.style.display = profileDone ? 'inline-flex' : 'none';
      if (btnLogout) btnLogout.style.display = 'inline-flex';
      // Services, Privacy & Legal, and Feedback show on pre-login homepage / Console login screen
      if (btnServices) btnServices.style.display = 'none';
      if (btnPrivacy) btnPrivacy.style.display = 'none';
      if (btnFeedback) btnFeedback.style.display = 'none';
      if (btnAdmin) btnAdmin.style.display = (window.isAdminHost() && profileDone && user && user.is_admin) ? 'inline-flex' : 'none';
      if (btnStudio) btnStudio.style.display = profileDone ? 'inline-flex' : 'none';
      if (btnConsoleSwitch) btnConsoleSwitch.style.display = 'none';

      var modeSel = document.getElementById('workspace-mode-selector');
      var btnSwitchMode = document.getElementById('btn-switch-workspace-mode');
      var toolsSec = document.getElementById('tools-modules-section');
      if (!profileDone) {
        if (btnDeptLogin) btnDeptLogin.style.display = 'none';
        if (btnDisconn) btnDisconn.style.display = 'none';
        if (globalBar) globalBar.style.display = 'none';
        if (officerBanner) officerBanner.style.display = 'none';
        if (modeSel) modeSel.style.display = 'none';
        if (btnSwitchMode) btnSwitchMode.style.display = 'none';
        if (portalSec) portalSec.style.display = 'none';
        if (consoleSec) consoleSec.style.display = 'none';
        if (toolsSec) toolsSec.style.display = 'none';
        if (dcbSec) dcbSec.style.display = 'none';
        if (dash) dash.style.display = 'none';
        window.applyScreenVisualState('state-home-login', user);
      } else {
        if (globalBar) globalBar.style.display = 'flex';
        if (dash) dash.style.display = 'block';
        var activeMode = window.currentWorkspaceMode;
        if (activeMode === 'manual') {
          if (modeSel) modeSel.style.display = 'none';
          if (portalSec) portalSec.style.display = 'block';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'none';
          if (dcbSec) dcbSec.style.display = 'block';
          if (btnSwitchMode) btnSwitchMode.style.display = 'inline-flex';
          if (btnDeptLogin) btnDeptLogin.style.display = sessionStorage.getItem('epts_portal_auth') === 'true' ? 'inline-flex' : 'none';
          if (dashBadge) dashBadge.textContent = '📊 Manual Reports Mode';
          window.applyScreenVisualState('state-manual-page', user);
        } else if (activeMode === 'automated') {
          if (modeSel) modeSel.style.display = 'none';
          if (portalSec) portalSec.style.display = 'none';
          if (consoleSec) consoleSec.style.display = 'block';
          if (toolsSec) toolsSec.style.display = 'none';
          if (dcbSec) dcbSec.style.display = 'block';
          if (btnSwitchMode) btnSwitchMode.style.display = 'inline-flex';
          if (btnDeptLogin) btnDeptLogin.style.display = 'inline-flex';
          if (dashBadge) {
            dashBadge.textContent =
              sessionStorage.getItem('epts_portal_auth') === 'true'
                ? '🏛️ Departmental Session Active'
                : '⚡ Automated Reports Console Mode';
          }
          window.applyScreenVisualState('state-automation-page', user);
        } else if (activeMode === 'tools') {
          if (modeSel) modeSel.style.display = 'none';
          if (portalSec) portalSec.style.display = 'none';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'block';
          if (dcbSec) dcbSec.style.display = 'none';
          if (btnSwitchMode) btnSwitchMode.style.display = 'inline-flex';
          if (btnDeptLogin) btnDeptLogin.style.display = sessionStorage.getItem('epts_portal_auth') === 'true' ? 'inline-flex' : 'none';
          if (dashBadge) dashBadge.textContent = '🧰 Tools & Utilities Studio';
          window.applyScreenVisualState('state-tools-page', user);
        } else {
          if (modeSel) modeSel.style.display = 'block';
          if (portalSec) portalSec.style.display = 'none';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'none';
          if (dcbSec) dcbSec.style.display = 'none';
          if (btnSwitchMode) btnSwitchMode.style.display = 'none';
          if (btnDeptLogin) btnDeptLogin.style.display = sessionStorage.getItem('epts_portal_auth') === 'true' ? 'inline-flex' : 'none';
          if (dashBadge) dashBadge.textContent = '🟢 Choose Reporting Mode';
          window.applyScreenVisualState('state-workspace-hub', user);
        }
      }
    } else {
      window.currentWorkspaceMode = null;
      window.hideAllStations();
      var modeSelOut = document.getElementById('workspace-mode-selector');
      var btnSwitchOut = document.getElementById('btn-switch-workspace-mode');
      var toolsOut = document.getElementById('tools-modules-section');
      if (modeSelOut) modeSelOut.style.display = 'none';
      if (btnSwitchOut) btnSwitchOut.style.display = 'none';
      if (toolsOut) toolsOut.style.display = 'none';
      if (heroCard) heroCard.style.display = 'flex';
      if (btnHome) btnHome.style.display = 'none';
      if (btnStudio) btnStudio.style.display = 'none';
      if (btnConsoleSwitch) btnConsoleSwitch.style.display = 'none';
      if (btnAdmin) btnAdmin.style.display = 'none';
      if (btnLogout) btnLogout.style.display = 'none';
      if (btnDeptLogin) btnDeptLogin.style.display = 'none';
      if (btnDisconn) btnDisconn.style.display = 'none';
      if (globalBar) globalBar.style.display = 'none';
      if (officerBanner) officerBanner.style.display = 'none';
      if (portalSec) portalSec.style.display = 'none';
      if (consoleSec) consoleSec.style.display = 'none';
      if (dcbSec) dcbSec.style.display = 'none';
      if (dash) dash.style.display = 'none';
      if (btnServices) btnServices.style.display = 'inline-flex';
      if (btnPrivacy) btnPrivacy.style.display = 'inline-flex';
      if (btnFeedback) btnFeedback.style.display = 'inline-flex';
      window.applyScreenVisualState('state-home-login', null);
    }
  };

  window.showWorkspaceModeSelector = function () {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return;
    }
    var u = window.getScopedUser();
    var profileDone = Boolean(u && u.profile_completed && u.designation && u.mobile_number);
    if (!profileDone) {
      window.setPortalUI(true, u);
      window.showOfficerProfileModal(u || {}, { allowClose: false });
      return;
    }
    window.currentWorkspaceMode = null;
    try { sessionStorage.removeItem('epts_workspace_mode'); } catch (e) {}
    window.hideAllStations();
    window.setPortalUI(true, u);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  window.selectWorkspaceMode = function (mode, options) {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return false;
    }
    var u = window.getScopedUser();
    var rawMode = String(mode || '').trim().toLowerCase();
    var m = rawMode === 'automated' ? 'automated' : (rawMode === 'tools' ? 'tools' : 'manual');

    if (m === 'automated') {
      var flags = window.currentAccessPolicy || {};
      var subReq = flags.automated_subscription_required === true;
      var hasSub = Boolean(u && (u.has_automated_subscription || u.subscription_status === 'active'));
      if (flags.console_enabled === false || (u && u.can_access_automated === false) || (subReq && !hasSub)) {
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice('Automated Reports Console requires an active subscription. Manual Reports remain freely available.', 'warning');
        }
        return false;
      }
    }

    var isDirectClick = !(options && options.fromInit);
    if (isDirectClick && window.isProdCustomDomain()) {
      if (m === 'manual' && !window.isManualHost()) {
        window.location.href = 'https://www.manualreports.panchayatautomation.in/';
        return true;
      }
      if (m === 'automated' && !window.isReportsHost()) {
        window.location.href = 'https://www.autoreports.panchayatautomation.in/';
        return true;
      }
      if (m === 'tools' && !window.isToolsHost()) {
        window.location.href = 'https://www.tools.panchayatautomation.in/';
        return true;
      }
    }

    window.currentWorkspaceMode = m;
    try { sessionStorage.setItem('epts_workspace_mode', m); } catch (e) {}
    window.hideAllStations();
    window.setPortalUI(true, u);
    if (!(options && options.skipScroll)) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    return true;
  };

  window.showDashboard = function () {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return;
    }
    var u = window.getScopedUser();
    var profileDone = Boolean(u && u.profile_completed && u.designation && u.mobile_number);
    if (!profileDone) {
      window.setPortalUI(true, u);
      window.showOfficerProfileModal(u || {}, { allowClose: false });
      return;
    }
    window.hideAllStations();
    window.setPortalUI(true, u);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  window.handleHomeNavigation = function () {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return;
    }
    var dedSection = window.getDedicatedPageSection();
    if (dedSection) {
      window.selectWorkspaceMode(dedSection, { fromInit: true });
      return;
    }
    window.showWorkspaceModeSelector();
  };

  window.logoutPortalApp = async function () {
    var sc = window.getPlatformScope();
    var dedSection = window.getDedicatedPageSection();
    window.currentWorkspaceMode = null;
    try { sessionStorage.removeItem('epts_workspace_mode'); } catch (e) {}
    if (typeof window.stopConsoleSessionPolling === 'function') {
      window.stopConsoleSessionPolling();
    }
    if (window.FirebasePortalAuth && typeof window.FirebasePortalAuth.signOut === 'function') {
      try {
        await window.FirebasePortalAuth.signOut();
      } catch (e) {}
    }
    try {
      await fetch('/api/auth/portal-logout', { method: 'POST' });
    } catch (e) {}
    window.clearScopeSessionStorage(sc);
    window.setPortalUI(false, null);
    var dest = '/';
    if (dedSection) {
      dest = (window.isReportsHost() || window.isManualHost() || window.isToolsHost())
        ? '/'
        : window.getSectionUrl(dedSection);
    } else if (sc === 'console' && !window.isReportsHost()) {
      dest = '/?site=console';
    }
    window.location.replace(dest);
  };

  // ---------------------------------------------------------------------------
  // Privacy & Feedback Modals
  // ---------------------------------------------------------------------------

  window.openPrivacyLegalModal = function () {
    var modal = document.getElementById('privacy-legal-modal');
    if (modal) modal.style.display = 'flex';
  };

  window.closePrivacyLegalModal = function () {
    var modal = document.getElementById('privacy-legal-modal');
    if (modal) modal.style.display = 'none';
  };

  window.openFeedbackModal = function () {
    var modal = document.getElementById('feedback-modal');
    if (!modal) return;
    var user = window.getScopedUser() || {};
    var fbName = document.getElementById('fb-name');
    var fbDesig = document.getElementById('fb-desig');
    if (fbName && user.name) fbName.value = user.name;
    if (fbDesig && user.designation && DESIGNATIONS.indexOf(user.designation) !== -1) {
      fbDesig.value = user.designation;
    }
    var alertEl = document.getElementById('feedback-alert');
    if (alertEl) alertEl.style.display = 'none';
    modal.style.display = 'flex';
  };

  window.closeFeedbackModal = function () {
    var modal = document.getElementById('feedback-modal');
    if (modal) modal.style.display = 'none';
  };

  window.handleFeedbackSubmit = async function (e) {
    if (e) e.preventDefault();
    var name = (document.getElementById('fb-name') && document.getElementById('fb-name').value || '').trim();
    var designation = (document.getElementById('fb-desig') && document.getElementById('fb-desig').value || '').trim();
    var category = (document.getElementById('fb-category') && document.getElementById('fb-category').value || '').trim();
    var message = (document.getElementById('fb-message') && document.getElementById('fb-message').value || '').trim();
    var alertBox = document.getElementById('feedback-alert');
    var btn = document.getElementById('btn-submit-feedback');

    var showFbAlert = function (txt, ok) {
      if (!alertBox) return;
      alertBox.style.display = 'block';
      alertBox.style.background = ok ? '#ecfdf5' : '#fef2f2';
      alertBox.style.border = ok ? '1px solid #6ee7b7' : '1px solid #fca5a5';
      alertBox.style.color = ok ? '#065f46' : '#991b1b';
      alertBox.textContent = txt;
    };

    if (!message) {
      showFbAlert('Please enter your message or feedback.', false);
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳</span> Submitting Feedback...';
    }

    try {
      var res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          designation: designation,
          category: category,
          message: message,
          rating: 5,
        }),
      });
      var data = await res.json().catch(function () {
        return { success: false, message: 'Server returned invalid response.' };
      });
      if (res.ok && data && data.success) {
        showFbAlert('✓ ' + (data.message || 'Feedback submitted successfully!'), true);
        setTimeout(function () {
          window.closeFeedbackModal();
          var msgArea = document.getElementById('fb-message');
          if (msgArea) msgArea.value = '';
        }, 1200);
      } else {
        showFbAlert((data && data.message) || 'Failed to submit feedback.', false);
      }
    } catch (err) {
      showFbAlert('Error submitting feedback: ' + err.message, false);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>📤</span> Submit Feedback';
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Boot Initialization
  // ---------------------------------------------------------------------------

  async function initPortal() {
    window.updatePlatformUrlLinks();
    window.applyPlatformScopeBranding();
    window.renderAuthErrorFromQuery();

    var isPortalAuth = false;
    var portalUser = null;
    var scope = window.getPlatformScope();

    try {
      var pRes = await fetch('/api/auth/portal-status');
      if (pRes.ok) {
        var pData = await pRes.json();
        if (pData && pData.epts_session_id && window.DeptSessionManager) {
          window.DeptSessionManager.adoptServerSessionId(pData.epts_session_id);
        } else {
          window.getEptsSessionId();
        }
        window.FIREBASE_CONFIG = pData.firebase_config || null;
        if (pData.access_policy) {
          window.applyAccessPolicyUi(pData.access_policy);
        }

        if (window.FirebasePortalAuth && pData.firebase_config) {
          try {
            window.FirebasePortalAuth.init(pData.firebase_config, pData.auth_emulator_host);
            if (!pData.authenticated && typeof window.FirebasePortalAuth.consumeRedirectSignIn === 'function') {
              var redirResult = await window.FirebasePortalAuth.consumeRedirectSignIn();
              if (redirResult && redirResult.idToken) {
                var fRes = await fetch('/api/auth/firebase-login', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ id_token: redirResult.idToken }),
                });
                if (fRes.ok) {
                  var fData = await fRes.json();
                  if (fData && fData.success && fData.user) {
                    pData.authenticated = true;
                    pData.user = fData.user;
                  }
                }
              }
            }
          } catch (fbErr) {
            console.warn('Firebase Auth SDK initialization note:', fbErr);
          }
        }

        if (pData.authenticated && pData.user) {
          isPortalAuth = true;
          portalUser = pData.user;
          window.setScopedUser(portalUser, scope);
        } else {
          window.setScopedUser(null, scope);
        }
      }
    } catch (e) {
      console.warn('Portal auth status check note:', e);
    }

    window.setPortalUI(isPortalAuth, portalUser);

    var urlParams = new URLSearchParams(window.location.search);
    var hashVal = window.location.hash ? window.location.hash.replace('#', '') : '';
    var target = (urlParams.get('station') || urlParams.get('module') || hashVal || '').trim().toLowerCase();

    if (window.DeptSessionManager) {
      var parsedPending = window.DeptSessionManager.parsePendingFromUrl(window.location.search);
      if (parsedPending) {
        window.DeptSessionManager.savePendingAction(parsedPending);
      }
    }

    if (!isPortalAuth) {
      return;
    }

    var isCompleted = Boolean(portalUser && portalUser.profile_completed);
    if (!isCompleted || !portalUser.designation || !portalUser.mobile_number) {
      window.showOfficerProfileModal(portalUser, { allowClose: false });
      return;
    }

    await window.proceedAfterPortalAuth();

    var dedSection = window.getDedicatedPageSection();
    if (dedSection && (!target || !(window.DeptSessionManager && urlParams.get('pending_module')))) {
      if (dedSection === 'manual' || dedSection === 'tools') {
        window.selectWorkspaceMode(dedSection, { skipScroll: true, fromInit: true });
      } else if (dedSection === 'automated' && !urlParams.get('mode') && !target) {
        window.selectWorkspaceMode('automated', { skipScroll: true, fromInit: true });
      }
    }

    if (!target || (window.DeptSessionManager && urlParams.get('pending_module'))) return;

    if (target === 'multiday' || target === 'multi-day' || target === 'dsr_multiday') {
      if (typeof window.showUpcomingModal === 'function') {
        window.showUpcomingModal('Multiple Days DSR & Attendance Reports', '📅', 'Multi-Day Attendance & DSR consolidation across custom date ranges is marked as Upcoming. Daily PS Attendance & DSR PDF generation remains active and ready.');
      }
    } else if (target === 'dsr_excel' || target === 'manual-reports' || target === 'manual_reports') {
      window.location.href = '/reports/ps-attendance#reports';
    } else if (target === 'tax-dcb' || target === 'tax' || target === 'tax-station') {
      if (typeof window.openTaxDcbStation === 'function') await window.openTaxDcbStation();
    } else if (target === 'inspections') {
      if (typeof window.showUpcomingModal === 'function') {
        window.showUpcomingModal('Gram Panchayat Inspections', '🔍', 'Compliance monitoring of Gram Panchayat field inspections conducted by DPO, DLPO, and MPO tiers with Mandal filters, GP drill-down, and automated portal synchronization.');
      }
    } else if (target === 'admin' && window.isAdminHost() && portalUser && portalUser.is_admin) {
      if (typeof window.openAdminDashboardStation === 'function') window.openAdminDashboardStation();
    } else if (target === 'balance' || target === 'balance-station') {
      if (typeof window.openBalanceRobot === 'function') await window.openBalanceRobot();
    } else if (target === 'dsr') {
      if (typeof window.openDsrRobot === 'function') await window.openDsrRobot();
    } else if (target === 'mas') {
      if (typeof window.openMasRobot === 'function') await window.openMasRobot();
    }
  }

  document.addEventListener('DOMContentLoaded', initPortal);
})();
