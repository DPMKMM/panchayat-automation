/**
 * e-Panchayat Automation — Dual-Domain Authentication, Branding & Shell Controller
 * Scopes: Platform 1 ('portal' -> panchayatautomation.in) & Platform 2 ('console' -> reports.panchayatautomation.in)
 */
(function () {
  'use strict';

  var PLATFORM_NAME = 'e-Panchayat Automation';
  var CONSOLE_NAME = 'e-Panchayat Automation Console';
  var WELCOME_MESSAGE = 'Welcome to ' + PLATFORM_NAME;
  var DESIGNATIONS = ['CITIZEN', 'PS', 'DEO', 'MPO', 'MPDO', 'DLPO', 'DPO', 'DPM', 'OTHER'];
  var ROLES = ['Mandal Level', 'Division Level', 'District Level', 'Citizen'];

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

  window.isAdminRouteOrHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    var isLocal = host === 'localhost' || host === '127.0.0.1' || host === 'testserver';
    var path = (window.location.pathname || '').toLowerCase();
    return window.isAdminHost() || (isLocal && path === '/admin');
  };

  window.isAllowedAdminUIHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    var isLocal = host === 'localhost' || host === '127.0.0.1' || host === 'testserver';
    var path = (window.location.pathname || '').toLowerCase();
    if (window.isAdminHost()) return true;
    if (isLocal && (path === '/admin' || window.__testForceAdminUI === true)) return true;
    return false;
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

  window.isSoftwaresHost = function () {
    var host = (window.location.hostname || '').toLowerCase();
    return host.indexOf('softwares.') === 0 || host.indexOf('www.softwares.') === 0 || host.indexOf('software.') === 0 || host.indexOf('www.software.') === 0;
  };

  window.getDedicatedPageSection = function () {
    if (window.isAdminRouteOrHost()) return 'admin';
    if (window.isReportsHost()) return 'automated';
    if (window.isManualHost()) return 'manual';
    if (window.isToolsHost()) return 'tools';
    if (window.isSoftwaresHost()) return 'softwares';
    var path = (window.location.pathname || '').toLowerCase();
    if (path === '/autoreports' || path === '/eptauto' || path === '/naresh' || path.indexOf('/reports') === 0 || path === '/mas') {
      return 'automated';
    }
    if (path === '/manualreports') return 'manual';
    if (path === '/tools' || path.indexOf('/tools/') === 0) return 'tools';
    if (path === '/softwares' || path.indexOf('/softwares/') === 0 || path === '/software' || path.indexOf('/software/') === 0) return 'softwares';
    return null;
  };

  window.getSectionUrl = function (section) {
    var s = String(section || '').trim().toLowerCase();
    if (window.isProdCustomDomain()) {
      if (s === 'automated') return 'https://autoreports.panchayatautomation.in/';
      if (s === 'manual') return 'https://manualreports.panchayatautomation.in/';
      if (s === 'tools') return 'https://tools.panchayatautomation.in/';
      if (s === 'softwares' || s === 'software') return 'https://softwares.panchayatautomation.in/';
      return 'https://panchayatautomation.in/';
    }
    if (s === 'automated') return '/autoreports?site=console';
    if (s === 'manual') return '/manualreports';
    if (s === 'tools') return '/tools';
    if (s === 'softwares' || s === 'software') return '/softwares';
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
      var tok = sessionStorage.getItem(tokenStorageKey(sc));
      if (!tok) {
        tok = localStorage.getItem('epts_auth_token') || localStorage.getItem(tokenStorageKey(sc)) || '';
      }
      return tok || '';
    } catch (e) {
      return '';
    }
  };

  window.setScopedAuthToken = function (token, scope) {
    var sc = scope || window.getPlatformScope();
    try {
      if (token) {
        sessionStorage.setItem(tokenStorageKey(sc), String(token));
        localStorage.setItem('epts_auth_token', String(token));
        localStorage.setItem(tokenStorageKey(sc), String(token));
      } else {
        sessionStorage.removeItem(tokenStorageKey(sc));
        localStorage.removeItem('epts_auth_token');
        localStorage.removeItem(tokenStorageKey(sc));
      }
    } catch (e) {}
  };

  window.getScopedUser = function (scope) {
    var sc = scope || window.getPlatformScope();
    try {
      var raw = sessionStorage.getItem(userStorageKey(sc));
      if (!raw) {
        raw = localStorage.getItem('epts_auth_user') || localStorage.getItem(userStorageKey(sc));
      }
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  };

  window.setScopedUser = function (user, scope) {
    window.currentUser = user || null;
    var sc = scope || window.getPlatformScope();
    try {
      if (user) {
        var str = JSON.stringify(user);
        sessionStorage.setItem(authFlagKey(sc), 'true');
        sessionStorage.setItem(userStorageKey(sc), str);
        localStorage.setItem('epts_auth_user', str);
        localStorage.setItem(userStorageKey(sc), str);
        localStorage.setItem('epts_logged_in', 'true');
      } else {
        sessionStorage.removeItem(authFlagKey(sc));
        sessionStorage.removeItem(userStorageKey(sc));
        localStorage.removeItem('epts_auth_user');
        localStorage.removeItem(userStorageKey(sc));
        localStorage.removeItem('epts_logged_in');
      }
    } catch (e) {}
  };

  window.clearScopeSessionStorage = function (scope) {
    var sc = scope || window.getPlatformScope();
    try {
      sessionStorage.removeItem(tokenStorageKey(sc));
      sessionStorage.removeItem(authFlagKey(sc));
      sessionStorage.removeItem(userStorageKey(sc));
      localStorage.removeItem('epts_auth_token');
      localStorage.removeItem('epts_auth_user');
      localStorage.removeItem('epts_logged_in');
      localStorage.removeItem(tokenStorageKey(sc));
      localStorage.removeItem(userStorageKey(sc));
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
        if (!headers.has('Authorization')) {
          headers.set('Authorization', 'Bearer ' + scopedTok);
        }
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
      'admin-reply-modal': window.closeAdminReplyModal,
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
    ['upcoming-modal', 'sessions-modal', 'insp-detail-modal', 'privacy-legal-modal', 'feedback-modal', 'admin-reply-modal', 'dept-login-modal'].forEach(function (id) {
      var m = document.getElementById(id);
      if (m && e.target === m) {
        closeModalByIdSafely(id);
      }
    });
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
    ['upcoming-modal', 'sessions-modal', 'insp-detail-modal', 'privacy-legal-modal', 'feedback-modal', 'admin-reply-modal', 'dept-login-modal'].forEach(function (id) {
      closeModalByIdSafely(id);
    });
  });

  // ---------------------------------------------------------------------------
  // Station Visibility & Dual-Domain Branding / Links
  // ---------------------------------------------------------------------------

  window.hideAllStations = function () {
    [
      'portal-hero-card',
      'post-login-dashboard',
      'admin-nonadmin-gate',
      'admin-dashboard-station',
      'automation-station',
      'balance-station',
      'tax-dcb-station',
      'inspections-station',
      'auto-multi-dsr-station',
      'state-format-station',
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
    var onSoftwares = window.isSoftwaresHost();
    var dedSection = window.getDedicatedPageSection();
    var isCon = window.isConsoleScope();
    var consoleDest = window.getSectionUrl('automated');
    var manualDest = window.getSectionUrl('manual');
    var toolsDest = window.getSectionUrl('tools');
    var softwaresDest = window.getSectionUrl('softwares');
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
      { id: 'login-link-softwares', sec: 'softwares', href: softwaresDest },
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

  var MODULE_CARD_MAP = {
    module_dsr_excel: ['card-policy-module_dsr_excel'],
    module_dsr_multiday: ['card-policy-module_dsr_multiday'],
    module_mobile_updation: ['card-policy-module_mobile_updation'],
    module_dsr_automation: ['card-policy-module_dsr_automation'],
    module_state_format: ['card-policy-module_state_format'],
    module_gp_balance_automation: ['card-policy-module_gp_balance_automation'],
    module_mas_automation: ['card-policy-module_mas_automation'],
    module_gp_inspections: ['card-console-gp-inspections', 'card-policy-module_gp_inspections'],
    module_auto_multi_dsr: ['card-console-auto-multi-dsr', 'card-policy-module_auto_multi_dsr'],
    module_citizen_services: ['card-policy-module_citizen_services'],
    module_trade_licences: ['card-policy-module_trade_licences'],
    module_dcb_live: ['card-policy-module_dcb_live', 'console-tax-card'],
    module_excel_studio: ['card-tool-excel', 'card-policy-module_excel_studio'],
    module_pdf_studio: ['card-tool-pdf', 'card-policy-module_pdf_studio'],
    module_softwares_hub: ['card-choose-softwares', 'card-policy-module_softwares_hub']
  };

  var DEFAULT_BADGE_LABELS = {
    module_dsr_excel: '● Live',
    module_dsr_multiday: '● Live',
    module_mobile_updation: '● Live',
    module_dcb_live: '● Live',
    module_dsr_automation: '● Live',
    module_state_format: '● Live',
    module_gp_balance_automation: '● Live',
    module_mas_automation: '● Live',
    module_auto_multi_dsr: '● Live',
    module_gp_inspections: '● Live',
    module_excel_studio: '● Live',
    module_pdf_studio: '● Live',
    module_softwares_hub: '● Live',
    module_citizen_services: '',
    module_trade_licences: 'Upcoming'
  };

  var UPCOMING_BADGE_LABELS = {
    module_trade_licences: 'Upcoming'
  };

  window.applyAccessPolicyUi = function (policy, currentUser) {
    var flags = policy && policy.flags ? policy.flags : policy || {};
    window.currentAccessPolicy = Object.assign({}, flags);

    var u = currentUser || (typeof window.getScopedUser === 'function' ? window.getScopedUser() : null);
    var isAdmin = Boolean(
      (u && u.is_admin) ||
      (typeof window.isCurrentOfficerAdmin === 'function' && window.isCurrentOfficerAdmin()) ||
      (window.currentUser && window.currentUser.is_admin) ||
      (window.portalUser && window.portalUser.is_admin)
    );

    // Apply Module Visibility (Hide / Show) across Officer Workspace
    Object.keys(MODULE_CARD_MAP).forEach(function (mKey) {
      var visKey = 'visible_' + mKey;
      var isVisible = true;
      if (Object.prototype.hasOwnProperty.call(flags, visKey)) {
        isVisible = flags[visKey] !== false;
      } else if (Object.prototype.hasOwnProperty.call(flags, mKey)) {
        isVisible = flags[mKey] !== false;
      }

      var cardIds = MODULE_CARD_MAP[mKey];
      cardIds.forEach(function (cid) {
        var cardEl = document.getElementById(cid);
        if (cardEl) {
          // If admin is logged in, disabled/hidden modules REMAIN VISIBLE for testing
          if (!isVisible && !isAdmin) {
            cardEl.style.display = 'none';
            cardEl.setAttribute('data-admin-hidden', 'true');
            cardEl.removeAttribute('data-admin-preview');
          } else {
            cardEl.style.display = '';
            cardEl.removeAttribute('data-admin-hidden');
            if (!isVisible && isAdmin) {
              cardEl.setAttribute('data-admin-preview', 'hidden');
            } else {
              cardEl.removeAttribute('data-admin-preview');
            }
          }
        }
      });
    });

    ['portal-modules-section', 'console-modules-section', 'tools-utilities-section'].forEach(function (secId) {
      var secEl = document.getElementById(secId);
      if (!secEl) return;
      var allCards = secEl.querySelectorAll('.module-card');
      if (allCards.length > 0) {
        var hiddenCount = secEl.querySelectorAll('.module-card[data-admin-hidden="true"]').length;
        var placeholder = secEl.querySelector('.admin-all-modules-hidden-notice');
        if (hiddenCount >= allCards.length && !isAdmin) {
          if (!placeholder) {
            placeholder = document.createElement('div');
            placeholder.className = 'admin-all-modules-hidden-notice';
            placeholder.style.cssText = 'padding:24px; text-align:center; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:12px; color:#64748b; font-size:0.88rem; margin:10px 0;';
            placeholder.innerHTML = '🔒 All modules in this section are currently set to hidden by Administrator.';
            var grid = secEl.querySelector('.modules-grid');
            if (grid) grid.parentNode.insertBefore(placeholder, grid.nextSibling);
            else secEl.appendChild(placeholder);
          }
          placeholder.style.display = 'block';
        } else if (placeholder) {
          placeholder.style.display = 'none';
        }
      }
    });

    var policyKeys = Object.keys(DEFAULT_BADGE_LABELS).concat(Object.keys(UPCOMING_BADGE_LABELS));
    policyKeys.forEach(function (key) {
      var isUpcoming = Object.prototype.hasOwnProperty.call(UPCOMING_BADGE_LABELS, key) || key === 'module_trade_licences';
      var enabled = flags[key] !== false;
      var visKey = 'visible_' + key;
      var isVis = Object.prototype.hasOwnProperty.call(flags, visKey) ? (flags[visKey] !== false) : true;
      var card = document.getElementById('card-policy-' + key);
      var badge = document.getElementById('badge-policy-' + key);

      // If user is Admin, module is ALWAYS visible and enabled for testing!
      var canInteract = enabled || isAdmin;

      if (card) {
        card.classList.toggle('policy-disabled', !canInteract);
        if (isAdmin && (!enabled || !isVis)) {
          card.classList.add('admin-testing-module');
          card.style.outline = '2px dashed #f59e0b';
          card.style.outlineOffset = '2px';
        } else {
          card.classList.remove('admin-testing-module');
          card.style.outline = '';
          card.style.outlineOffset = '';
        }
        var btns = card.querySelectorAll('button, a.btn');
        btns.forEach(function (b) {
          if (b.tagName === 'BUTTON') {
            b.disabled = !canInteract;
          } else {
            b.style.pointerEvents = canInteract ? '' : 'none';
            b.style.opacity = canInteract ? '' : '0.6';
            if (canInteract) {
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
          if (isAdmin) {
            badge.className = 'badge-pill-soon';
            badge.style.background = '#fef3c7';
            badge.style.color = '#92400e';
            badge.style.border = '1px solid #fde68a';
            badge.innerHTML = '⏸ Paused (Admin Testing Mode)';
            badge.title = 'This module is paused for regular users, but accessible to Admin for testing.';
          } else {
            badge.className = 'badge-pill-soon';
            badge.style.background = '';
            badge.style.color = '';
            badge.style.border = '';
            badge.innerHTML = '⏸ Paused by Admin';
            badge.title = '';
          }
        } else if (!isVis && isAdmin) {
          badge.style.display = 'inline-flex';
          badge.className = 'badge-pill-soon';
          badge.style.background = '#f3e8ff';
          badge.style.color = '#6b21a8';
          badge.style.border = '1px solid #e9d5ff';
          badge.innerHTML = '👁 Hidden (Admin Testing Mode)';
          badge.title = 'This module is hidden from regular users, but visible to Admin for testing.';
        } else if (isUpcoming) {
          badge.style.display = 'inline-flex';
          badge.className = 'badge-pill-soon auto-soon-pill';
          badge.style.background = '';
          badge.style.color = '';
          badge.style.border = '';
          badge.innerHTML = 'Upcoming';
          badge.title = '';
        } else if (DEFAULT_BADGE_LABELS[key]) {
          badge.style.display = 'inline-flex';
          badge.className = 'badge-pill-live auto-live-pill';
          badge.style.background = '';
          badge.style.color = '';
          badge.style.border = '';
          badge.innerHTML = '<span class="auto-pill-dot"></span> Live';
          badge.title = '';
        } else {
          badge.style.display = 'none';
          badge.innerHTML = '';
        }
      }
    });

    var consoleTaxCard = document.getElementById('console-tax-card');
    if (consoleTaxCard) {
      var liveEnabled = (flags.module_dcb_live !== false) || isAdmin;
      consoleTaxCard.classList.toggle('policy-disabled', !liveEnabled);
      consoleTaxCard.querySelectorAll('button').forEach(function (b) {
        b.disabled = !liveEnabled;
      });
      if (isAdmin && flags.module_dcb_live === false) {
        consoleTaxCard.style.outline = '2px dashed #f59e0b';
        consoleTaxCard.style.outlineOffset = '2px';
      } else {
        consoleTaxCard.style.outline = '';
        consoleTaxCard.style.outlineOffset = '';
      }
    }

    var badgeAutoMode = document.getElementById('badge-automated-mode-access');
    var noteAutoSub = document.getElementById('automated-subscription-note');
    var subRequired = flags.automated_subscription_required === true;
    var hasSub = Boolean(u && (u.has_automated_subscription || u.subscription_status === 'active'));
    if (badgeAutoMode) {
      if (flags.console_enabled === false) {
        badgeAutoMode.style.display = 'inline-flex';
        badgeAutoMode.className = 'badge-pill-soon';
        badgeAutoMode.textContent = isAdmin ? '⏸ Paused (Admin Testing)' : '⏸ Paused by Admin';
      } else if (subRequired && !hasSub && !isAdmin) {
        badgeAutoMode.style.display = 'inline-flex';
        badgeAutoMode.className = 'badge-pill-soon';
        badgeAutoMode.textContent = '🔒 Subscription Required';
      } else if ((subRequired && hasSub) || isAdmin) {
        badgeAutoMode.style.display = 'inline-flex';
        badgeAutoMode.className = 'badge-pill-live';
        badgeAutoMode.textContent = isAdmin ? '● Admin Testing Access' : '● Subscription Active';
      } else {
        badgeAutoMode.style.display = 'none';
        badgeAutoMode.textContent = '';
      }
    }
    if (noteAutoSub) {
      if (subRequired && !hasSub && !isAdmin) {
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
    window.proceedAfterPortalAuth();

    var isFirst = Boolean(data && (data.is_first_time || data.is_new));
    if (typeof window.checkAndShowFirstLoginProfilePrompt === 'function') {
      window.checkAndShowFirstLoginProfilePrompt(user, isFirst);
    }
  };

  window.handleGoogleLoginSuccess = window.handleFirebaseLoginSuccess;

  window.onFirebaseAutoAuthState = async function (fbUser, idToken) {
    if (window.isPortalAuthenticated && window.getScopedUser()) {
      return;
    }
    if (!idToken) return;
    try {
      var res = await fetch('/api/auth/firebase-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ id_token: idToken }),
      });
      if (res.ok) {
        var data = await res.json();
        if (data && data.success && data.user) {
          window.handleFirebaseLoginSuccess(data);
        }
      }
    } catch (e) {
      console.warn('Silent auto-login note:', e);
    }
  };

  window.proceedAfterPortalAuth = async function () {
    var urlSp = new URLSearchParams(window.location.search || '');
    var redirectTarget = (urlSp.get('redirect') || urlSp.get('next') || '').trim();
    if (redirectTarget && redirectTarget.startsWith('/') && !redirectTarget.startsWith('//') && !redirectTarget.includes('\\')) {
      window.location.replace(redirectTarget);
      return;
    }

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

    var dedSection = typeof window.getDedicatedPageSection === 'function' ? window.getDedicatedPageSection() : '';
    if (dedSection === 'admin' || target === 'admin' || reqMode === 'admin') {
      window.selectWorkspaceMode('admin', { skipScroll: true, fromInit: true });
    } else if ((pending && pending.module) || target === 'dsr' || target === 'balance' || target === 'balance-station' || target === 'mas' || reqMode === 'automated' || urlSp.get('dept_login') === '1') {
      window.selectWorkspaceMode('automated', { skipScroll: true, fromInit: true });
    } else if (reqMode === 'manual' || target === 'dsr_excel' || target === 'manual-reports' || target === 'multiday') {
      window.selectWorkspaceMode('manual', { skipScroll: true, fromInit: true });
    } else if (reqMode === 'tools') {
      window.selectWorkspaceMode('tools', { skipScroll: true, fromInit: true });
    } else if (reqMode === 'softwares' || reqMode === 'software' || target === 'softwares' || target === 'software') {
      window.selectWorkspaceMode('softwares', { skipScroll: true, fromInit: true });
    } else if (dedSection) {
      window.selectWorkspaceMode(dedSection, { skipScroll: true, fromInit: true });
    } else if (savedMode === 'manual' || savedMode === 'automated' || savedMode === 'tools' || savedMode === 'softwares') {
      window.selectWorkspaceMode(savedMode, { skipScroll: true, fromInit: true });
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

    if (urlSp.get('dept_login') === '1' || window.currentWorkspaceMode === 'automated' || dedSection === 'automated' || reqMode === 'automated') {
      if (!deptAuthed && typeof window.openDepartmentLoginModal === 'function') {
        window.openDepartmentLoginModal();
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Mobile Responsive Navbar Drawer & Handlers
  // ---------------------------------------------------------------------------

  window.toggleMobileNavMenu = function (forceState) {
    var drawer = document.getElementById('ribbon-mobile-drawer');
    var btn = document.getElementById('ribbon-hamburger-btn');
    var backdrop = document.getElementById('ribbon-mobile-backdrop');
    if (!drawer || !btn) return;
    var willOpen = (typeof forceState === 'boolean') ? forceState : !drawer.classList.contains('is-open');
    if (willOpen) {
      drawer.classList.add('is-open');
      btn.classList.add('is-open');
      btn.setAttribute('aria-expanded', 'true');
      drawer.setAttribute('aria-hidden', 'false');
      if (backdrop) backdrop.classList.add('is-open');
      document.body.style.overflow = 'hidden';
    } else {
      drawer.classList.remove('is-open');
      btn.classList.remove('is-open');
      btn.setAttribute('aria-expanded', 'false');
      drawer.setAttribute('aria-hidden', 'true');
      if (backdrop) backdrop.classList.remove('is-open');
      document.body.style.overflow = '';
    }
  };

  window.handleMobileModuleSelect = function (mode) {
    window.toggleMobileNavMenu(false);
    if (typeof window.switchPlatformModule === 'function') {
      window.switchPlatformModule(mode);
    }
  };

  window.handleMobileChangeDesig = function () {
    window.toggleMobileNavMenu(false);
    if (typeof window.openChangeDesignationModal === 'function') {
      window.openChangeDesignationModal();
    }
  };

  window.handleMobileDeptLogin = function () {
    window.toggleMobileNavMenu(false);
    if (typeof window.handleNavDeptLoginClick === 'function') {
      window.handleNavDeptLoginClick();
    }
  };

  window.handleMobileDisconnect = function () {
    window.toggleMobileNavMenu(false);
    if (typeof window.disconnectEptsSession === 'function') {
      window.disconnectEptsSession();
    }
  };

  window.handleMobileAdmin = function () {
    window.toggleMobileNavMenu(false);
    if (!window.isAllowedAdminUIHost()) {
      if (typeof window.isProdCustomDomain === 'function' && window.isProdCustomDomain()) {
        window.location.href = 'https://admin.panchayatautomation.in/';
        return;
      }
    }
    if (typeof window.openAdminDashboardStation === 'function') {
      window.openAdminDashboardStation();
    }
  };

  window.handleMobileFeedback = function () {
    window.toggleMobileNavMenu(false);
    if (typeof window.openFeedbackModal === 'function') {
      window.openFeedbackModal();
    }
  };

  window.handleMobileSignIn = function () {
    window.toggleMobileNavMenu(false);
    if (typeof window.triggerGoogleSignIn === 'function') {
      window.triggerGoogleSignIn();
    }
  };

  window.handleMobileLogout = function () {
    window.toggleMobileNavMenu(false);
    if (typeof window.logoutPortalApp === 'function') {
      window.logoutPortalApp();
    }
  };

  // Close mobile drawer on Escape key or desktop resize
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      window.toggleMobileNavMenu(false);
    }
  });

  window.addEventListener('resize', function () {
    if (window.innerWidth > 860) {
      window.toggleMobileNavMenu(false);
    }
  });

  // ---------------------------------------------------------------------------
  // Header UI, Dashboard Toggle & Scoped Logout
  // ---------------------------------------------------------------------------

  window.updateRibbonActiveModule = function (mode) {
    var raw = String(mode || '').trim().toLowerCase();
    var target = (raw === 'automated' || raw === 'tools' || raw === 'softwares') ? raw : 'manual';
    var modBtns = document.querySelectorAll('.ribbon-mod-btn');
    if (modBtns && modBtns.length) {
      modBtns.forEach(function (btn) {
        var m = btn.getAttribute('data-nav-mode');
        if (m === target) {
          btn.classList.add('active');
          btn.setAttribute('aria-current', 'page');
        } else {
          btn.classList.remove('active');
          btn.removeAttribute('aria-current');
        }
      });
    }
    // Also toggle active labels on mobile cards
    ['manual', 'automated', 'tools', 'softwares'].forEach(function (m) {
      var badge = document.getElementById('mobile-badge-' + m);
      if (badge) {
        badge.style.display = (m === target) ? 'inline-block' : 'none';
      }
    });
  };

  window.switchPlatformModule = function (mode) {
    var raw = String(mode || '').trim().toLowerCase();
    var m = (raw === 'automated' || raw === 'tools' || raw === 'softwares') ? raw : 'manual';

    if (window.isPortalAuthenticated) {
      window.selectWorkspaceMode(m, { isDirectClick: true });
      window.updateRibbonActiveModule(m);
    } else {
      try {
        sessionStorage.setItem('epts_workspace_mode', m);
        localStorage.setItem('epts_workspace_mode', m);
      } catch (e) {}
      window.updateRibbonActiveModule(m);
      try {
        if (window.history && typeof window.history.pushState === 'function') {
          var path = m === 'automated' ? '/autoreports' : (m === 'tools' ? '/tools' : (m === 'softwares' ? '/softwares' : '/manualreports'));
          window.history.pushState(null, '', path);
        }
      } catch (e) {}
      var titles = {
        manual: 'Manual Reports',
        automated: 'Automated Reports',
        tools: 'Tools Studio',
        softwares: 'Official Softwares Hub'
      };
      if (typeof window.showPortalNotice === 'function') {
        window.showPortalNotice('Sign in with your Google account to access ' + (titles[m] || 'this workspace') + '.', 'info');
      }
      var hero = document.getElementById('portal-hero-card');
      if (hero && typeof hero.scrollIntoView === 'function') {
        hero.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  window.formatDateIST = function (isoStr) {
    if (!isoStr) return '';
    try {
      var cleaned = String(isoStr).trim();
      if (cleaned.indexOf('IST') !== -1) return cleaned;
      if (cleaned.endsWith('Z')) cleaned = cleaned.slice(0, -1) + '+00:00';
      var d = new Date(cleaned);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      }) + ' IST';
    } catch (e) {
      return isoStr;
    }
  };

  window.updateHeaderUserInfo = function (user) {
    var bar = document.getElementById('nav-officer-profile-bar');
    var ribbonPill = document.getElementById('ribbon-officer-pill');

    if (!user) {
      if (bar) bar.style.display = 'none';
      if (ribbonPill) ribbonPill.style.display = 'none';
      return;
    }

    var name = user.display_name || user.name || 'Officer';
    var desig = user.effective_designation || (user.designation === 'OTHER' && user.designation_other ? user.designation_other : (user.designation || 'OFFICER'));
    var gmail = user.gmail || user.email || '';
    var lastLoginRaw = user.last_login_ist || user.previous_last_login || user.last_login || '';
    var lastLoginText = lastLoginRaw ? (window.formatDateIST(lastLoginRaw) || lastLoginRaw) : 'Just now';

    // Legacy / In-Flow Header Bar (User Level removed)
    if (bar) {
      bar.style.display = 'flex';
      var nameEl = document.getElementById('nav-user-name');
      var desigEl = document.getElementById('nav-user-desig');
      var gmailEl = document.getElementById('nav-user-gmail');
      var avatarEl = document.getElementById('nav-user-avatar');
      var iconFallback = document.getElementById('nav-user-icon-fallback');

      if (nameEl) nameEl.textContent = name;
      if (desigEl) desigEl.textContent = desig;
      if (gmailEl) gmailEl.textContent = gmail;

      if (user.profile_picture && avatarEl) {
        avatarEl.src = user.profile_picture;
        avatarEl.style.display = 'inline-block';
        if (iconFallback) iconFallback.style.display = 'none';
      } else {
        if (avatarEl) avatarEl.style.display = 'none';
        if (iconFallback) iconFallback.style.display = 'inline';
      }
    }

    // Fixed Top Ribbon Officer Pill (NO User Level)
    if (ribbonPill) {
      ribbonPill.style.display = 'inline-flex';
      var ribName = document.getElementById('ribbon-user-name');
      var ribDesig = document.getElementById('ribbon-user-desig');
      var ribEmail = document.getElementById('ribbon-user-email');
      var ribAvatar = document.getElementById('ribbon-user-avatar');
      var ribIcon = document.getElementById('ribbon-user-icon');
      var ribLastLogin = document.getElementById('ribbon-user-last-login');

      if (ribName) ribName.textContent = name;
      if (ribDesig) ribDesig.textContent = desig + ' ✏️';
      if (ribEmail) ribEmail.textContent = gmail;
      if (ribLastLogin) {
        ribLastLogin.textContent = '🕒 ' + lastLoginText;
        ribLastLogin.style.display = 'block';
      }

      if (user.profile_picture && ribAvatar) {
        ribAvatar.src = user.profile_picture;
        ribAvatar.style.display = 'inline-block';
        if (ribIcon) ribIcon.style.display = 'none';
      } else {
        if (ribAvatar) ribAvatar.style.display = 'none';
        if (ribIcon) ribIcon.style.display = 'inline';
      }
    }

    // Sync Mobile Drawer Officer Profile & Quick Top Bar Status
    var mobName = document.getElementById('mobile-user-name');
    var mobDesig = document.getElementById('mobile-user-desig');
    var mobEmail = document.getElementById('mobile-user-email');
    var mobAvatar = document.getElementById('mobile-user-avatar');
    var mobIcon = document.getElementById('mobile-user-icon');
    var mobQuickName = document.getElementById('ribbon-mobile-quick-name');
    var mobLastLogin = document.getElementById('mobile-user-last-login');

    if (mobName) mobName.textContent = name;
    if (mobDesig) mobDesig.textContent = desig + ' ✏️';
    if (mobEmail) mobEmail.textContent = gmail;
    if (mobLastLogin) {
      mobLastLogin.textContent = '🕒 Last Login: ' + lastLoginText;
      mobLastLogin.style.display = 'block';
    }
    if (mobQuickName) {
      var firstName = (name || '').split(' ')[0] || 'Officer';
      mobQuickName.textContent = firstName;
    }

    var profileLastLoginEl = document.getElementById('profile-field-last-login');
    if (profileLastLoginEl) {
      profileLastLoginEl.textContent = lastLoginText;
    }

    if (user.profile_picture && mobAvatar) {
      mobAvatar.src = user.profile_picture;
      mobAvatar.style.display = 'inline-block';
      if (mobIcon) mobIcon.style.display = 'none';
    } else {
      if (mobAvatar) mobAvatar.style.display = 'none';
      if (mobIcon) mobIcon.style.display = 'inline';
    }
  };

  // ---------------------------------------------------------------------------
  // Email/Password Registration, Sign In & Password Visibility Handlers
  // ---------------------------------------------------------------------------

  window.switchAuthView = function (mode) {
    var loginView = document.getElementById('auth-view-login');
    var regView = document.getElementById('auth-view-register');
    var alertEl = document.getElementById('portal-login-alert');
    if (alertEl) alertEl.style.display = 'none';

    if (mode === 'register') {
      if (loginView) loginView.style.display = 'none';
      if (regView) regView.style.display = 'block';
      var firstInput = document.getElementById('reg-surname');
      if (firstInput) firstInput.focus();
    } else {
      if (regView) regView.style.display = 'none';
      if (loginView) loginView.style.display = 'block';
      var loginInput = document.getElementById('login-email');
      if (loginInput) loginInput.focus();
    }
  };

  window.togglePasswordVisibility = function (inputId, btnEl) {
    var inp = document.getElementById(inputId);
    if (!inp) return;
    if (inp.type === 'password') {
      inp.type = 'text';
      if (btnEl) btnEl.textContent = '🙈';
    } else {
      inp.type = 'password';
      if (btnEl) btnEl.textContent = '👁️';
    }
  };

  window.handleDesignationSelectChange = function (selectEl, otherWrapId) {
    if (!selectEl) return;
    var otherWrap = document.getElementById(otherWrapId);
    if (!otherWrap) return;
    var isOther = (selectEl.value === 'OTHER');
    otherWrap.style.display = isOther ? 'block' : 'none';
    var otherInp = otherWrap.querySelector('input');
    if (otherInp) {
      otherInp.required = isOther;
      if (isOther) otherInp.focus();
    }
  };

  window.handleEmailLogin = async function (e) {
    if (e) e.preventDefault();
    var emailInp = document.getElementById('login-email');
    var pwdInp = document.getElementById('login-password');
    var btn = document.getElementById('btn-email-login');
    var alertEl = document.getElementById('portal-login-alert');

    if (!emailInp || !pwdInp) return;
    var email = (emailInp.value || '').trim();
    var pwd = (pwdInp.value || '');

    function showLoginAlert(msg, isSuccess) {
      if (!alertEl) return;
      alertEl.textContent = msg;
      alertEl.style.display = 'block';
      if (isSuccess) {
        alertEl.style.background = '#f0fdf4';
        alertEl.style.color = '#166534';
        alertEl.style.border = '1px solid #bbf7d0';
      } else {
        alertEl.style.background = '#fef2f2';
        alertEl.style.color = '#991b1b';
        alertEl.style.border = '1px solid #fecaca';
      }
    }

    if (!email || !pwd) {
      showLoginAlert('Please enter both your registered email or username and password.', false);
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Signing in...'; }
    if (alertEl) alertEl.style.display = 'none';

    try {
      var res = await window.safeFetchJson('/api/auth/email-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: pwd })
      });

      if (res && res.success) {
        window.isPortalAuthenticated = true;
        window.currentUser = res.user;
        if (typeof window.applyPortalLoginState === 'function') {
          window.applyPortalLoginState(true, res.user);
        } else if (typeof window.applyScreenVisualState === 'function') {
          window.applyScreenVisualState('workspace', res.user);
        }
        if (typeof window.updateHeaderUserInfo === 'function') {
          window.updateHeaderUserInfo(res.user);
        }
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice(res.message || 'Signed in successfully!', 'success');
        }
        var isFirst = Boolean(res && (res.is_first_time || (res.user && !res.user.profile_completed)));
        if (typeof window.checkAndShowFirstLoginProfilePrompt === 'function') {
          window.checkAndShowFirstLoginProfilePrompt(res.user, isFirst);
        }
        await window.proceedAfterPortalAuth();
      } else {
        var msg = (res && res.message) || 'Sign-in failed. Please verify credentials.';
        showLoginAlert(msg, false);
      }
    } catch (err) {
      showLoginAlert('Connection error: ' + (err.message || 'Could not connect to server.'), false);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'SIGN IN'; }
    }
  };

  window.handleRegistration = async function (e) {
    if (e) e.preventDefault();
    var alertEl = document.getElementById('portal-login-alert');
    var btn = document.getElementById('btn-register-action');

    var fullName = (document.getElementById('reg-full-name') && document.getElementById('reg-full-name').value || '').trim();
    var mobile = (document.getElementById('reg-mobile') && document.getElementById('reg-mobile').value || '').trim();
    var district = (document.getElementById('reg-district') && document.getElementById('reg-district').value || '').trim();
    var mandal = (document.getElementById('reg-mandal') && document.getElementById('reg-mandal').value || '').trim();
    var village = (document.getElementById('reg-village') && document.getElementById('reg-village').value || '').trim();
    var desig = (document.getElementById('reg-designation') && document.getElementById('reg-designation').value || '').trim();
    var desigOther = (document.getElementById('reg-designation-other') && document.getElementById('reg-designation-other').value || '').trim();
    var email = (document.getElementById('reg-email') && document.getElementById('reg-email').value || '').trim();
    var pwd = (document.getElementById('reg-password') && document.getElementById('reg-password').value || '');
    var confirmPwd = (document.getElementById('reg-confirm-password') && document.getElementById('reg-confirm-password').value || '');

    function showRegAlert(msg) {
      if (alertEl) {
        alertEl.textContent = msg;
        alertEl.style.display = 'block';
        alertEl.style.background = '#fef2f2';
        alertEl.style.color = '#991b1b';
        alertEl.style.border = '1px solid #fecaca';
      }
    }

    if (!fullName || fullName.length < 2) {
      showRegAlert('Please enter your full name.');
      return;
    }
    if (!mobile || !/^[6-9]\d{9}$/.test(mobile.replace(/\D/g, ''))) {
      showRegAlert('Please enter a valid 10-digit mobile number.');
      return;
    }
    if (!district) {
      showRegAlert('Please enter your district name.');
      return;
    }
    if (!desig) {
      showRegAlert('Please select your designation.');
      return;
    }
    if (desig === 'OTHER' && !desigOther) {
      showRegAlert('Please specify your designation in the manual text box.');
      return;
    }
    if (!email || email.indexOf('@') === -1) {
      showRegAlert('Please enter a valid email address.');
      return;
    }
    if (pwd !== confirmPwd) {
      showRegAlert('Password and Confirm Password do not match.');
      return;
    }
    if (pwd.length < 6) {
      showRegAlert('Password must be at least 6 characters long.');
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Registering Account...'; }
    if (alertEl) alertEl.style.display = 'none';

    try {
      var res = await window.safeFetchJson('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          name: fullName,
          mobile_number: mobile,
          district: district,
          mandal: mandal,
          village_gp: village,
          designation: desig,
          designation_other: desigOther,
          email: email,
          password: pwd
        })
      });

      if (res && res.success) {
        window.isPortalAuthenticated = true;
        window.currentUser = res.user;
        if (typeof window.applyPortalLoginState === 'function') {
          window.applyPortalLoginState(true, res.user);
        } else if (typeof window.applyScreenVisualState === 'function') {
          window.applyScreenVisualState('workspace', res.user);
        }
        if (typeof window.updateHeaderUserInfo === 'function') {
          window.updateHeaderUserInfo(res.user);
        }
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice(res.message || 'Account registered successfully!', 'success');
        }
        await window.proceedAfterPortalAuth();
      } else {
        showRegAlert((res && res.message) || 'Registration failed. Please check your details.');
      }
    } catch (err) {
      showRegAlert('Connection error: ' + (err.message || 'Could not register account.'));
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'REGISTER NOW'; }
    }
  };

  // ---------------------------------------------------------------------------
  // Comprehensive User Profile & Designation Modal Handlers
  // ---------------------------------------------------------------------------

  window.openUserProfileModal = function (isFirstLoginPrompt) {
    var modal = document.getElementById('user-profile-modal');
    if (!modal) return;
    var u = window.currentUser || (typeof window.getScopedUser === 'function' ? window.getScopedUser() : null) || {};

    var welcomeBanner = document.getElementById('profile-modal-welcome-banner');
    if (welcomeBanner) {
      welcomeBanner.style.display = isFirstLoginPrompt ? 'block' : 'none';
    }

    var fullNameInput = document.getElementById('profile-field-full-name');
    var mobile = document.getElementById('profile-field-mobile');
    var district = document.getElementById('profile-field-district');
    var mandal = document.getElementById('profile-field-mandal');
    var village = document.getElementById('profile-field-village');
    var desig = document.getElementById('profile-field-designation');
    var desigOther = document.getElementById('profile-field-designation-other');
    var emailDisp = document.getElementById('profile-field-account-email');
    var authTag = document.getElementById('profile-field-auth-provider-tag');
    var lastLoginEl = document.getElementById('profile-field-last-login');
    var alertEl = document.getElementById('user-profile-alert');
    if (alertEl) alertEl.style.display = 'none';

    if (fullNameInput) fullNameInput.value = u.full_name || u.name || u.display_name || '';
    if (mobile) mobile.value = u.mobile_number || u.phone || '';
    if (district) district.value = u.district || '';
    if (mandal) mandal.value = u.mandal || '';
    if (village) village.value = u.village_gp || u.village || '';

    if (desig) {
      var dVal = (u.designation || 'CITIZEN').toUpperCase();
      if (dVal === 'COLLECTOR' || dVal === 'SPECIAL OFFICER') dVal = 'OTHER';
      desig.value = dVal;
      window.handleDesignationSelectChange(desig, 'profile-field-designation-other-wrap');
    }
    if (desigOther) desigOther.value = u.designation_other || '';

    if (emailDisp) emailDisp.textContent = u.gmail || u.email || 'Registered User';
    if (authTag) {
      var isGoogle = (u.auth_provider === 'google' || (u.firebase_uid && !u.firebase_uid.startsWith('email:')));
      authTag.textContent = isGoogle ? 'Google Account' : 'Email & Password Account';
    }
    if (lastLoginEl) {
      var ll = u.last_login_ist || (window.formatDateIST ? window.formatDateIST(u.previous_last_login || u.last_login) : (u.last_login || 'Just now'));
      lastLoginEl.textContent = ll || 'Just now';
    }

    modal.style.display = 'flex';
  };

  window.closeUserProfileModal = function () {
    var modal = document.getElementById('user-profile-modal');
    if (modal) modal.style.display = 'none';
    if (window.currentUser && window.currentUser.user_id) {
      try {
        localStorage.setItem('profile_prompt_dismissed_' + window.currentUser.user_id, '1');
      } catch (e) {}
    }
  };

  window.checkAndShowFirstLoginProfilePrompt = function (user, isFirstTime) {
    if (!user || !user.user_id) return;
    var uid = user.user_id;
    var seenKey = 'profile_prompt_dismissed_' + uid;
    var isDismissed = false;
    try {
      isDismissed = localStorage.getItem(seenKey) === '1';
    } catch (e) {}

    // Show popup if explicitly first time, or if profile is incomplete and user hasn't dismissed it
    var isProfileIncomplete = !user.profile_completed || !user.designation || !user.mobile_number;
    if ((isFirstTime || isProfileIncomplete) && !isDismissed) {
      setTimeout(function () {
        if (typeof window.openUserProfileModal === 'function') {
          window.openUserProfileModal(true);
        }
      }, 700);
    }
  };

  window.openChangeDesignationModal = window.openUserProfileModal;
  window.closeChangeDesignationModal = window.closeUserProfileModal;

  window.submitUpdateProfile = async function (e) {
    if (e) e.preventDefault();
    var alertEl = document.getElementById('user-profile-alert');
    var btn = document.getElementById('btn-save-profile');

    var fullName = (document.getElementById('profile-field-full-name') && document.getElementById('profile-field-full-name').value || '').trim();
    var mobile = (document.getElementById('profile-field-mobile') && document.getElementById('profile-field-mobile').value || '').trim();
    var district = (document.getElementById('profile-field-district') && document.getElementById('profile-field-district').value || '').trim();
    var mandal = (document.getElementById('profile-field-mandal') && document.getElementById('profile-field-mandal').value || '').trim();
    var village = (document.getElementById('profile-field-village') && document.getElementById('profile-field-village').value || '').trim();
    var desig = (document.getElementById('profile-field-designation') && document.getElementById('profile-field-designation').value || '').trim();
    var desigOther = (document.getElementById('profile-field-designation-other') && document.getElementById('profile-field-designation-other').value || '').trim();

    if (!fullName || fullName.length < 2) {
      if (alertEl) {
        alertEl.textContent = 'Please enter your full name.';
        alertEl.style.display = 'block';
        alertEl.style.background = '#fef2f2';
        alertEl.style.color = '#991b1b';
        alertEl.style.border = '1px solid #fecaca';
      }
      return;
    }
    if (desig === 'OTHER' && !desigOther) {
      if (alertEl) {
        alertEl.textContent = 'Please enter your designation in the manual specification field.';
        alertEl.style.display = 'block';
        alertEl.style.background = '#fef2f2';
        alertEl.style.color = '#991b1b';
        alertEl.style.border = '1px solid #fecaca';
      }
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Saving Profile...'; }
    if (alertEl) alertEl.style.display = 'none';

    try {
      var res = await window.safeFetchJson('/api/auth/update-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          name: fullName,
          mobile_number: mobile,
          district: district,
          mandal: mandal,
          village_gp: village,
          designation: desig,
          designation_other: desigOther
        })
      });

      if (res && res.success) {
        window.currentUser = res.user;
        if (typeof window.setScopedUser === 'function') {
          window.setScopedUser(res.user);
        }
        if (typeof window.updateHeaderUserInfo === 'function') {
          window.updateHeaderUserInfo(res.user);
        }

        // Keep modal form inputs fresh with newly saved values
        var fNameEl = document.getElementById('profile-field-full-name');
        var mobEl = document.getElementById('profile-field-mobile');
        var distEl = document.getElementById('profile-field-district');
        var mandEl = document.getElementById('profile-field-mandal');
        var villEl = document.getElementById('profile-field-village');
        var desigEl = document.getElementById('profile-field-designation');
        var desigOtherEl = document.getElementById('profile-field-designation-other');
        if (fNameEl) fNameEl.value = res.user.full_name || res.user.name || '';
        if (mobEl) mobEl.value = res.user.mobile_number || res.user.phone || '';
        if (distEl) distEl.value = res.user.district || '';
        if (mandEl) mandEl.value = res.user.mandal || '';
        if (villEl) villEl.value = res.user.village_gp || res.user.village || '';
        if (desigEl && res.user.designation) {
          desigEl.value = res.user.designation;
          window.handleDesignationSelectChange(desigEl, 'profile-field-designation-other-wrap');
        }
        if (desigOtherEl) desigOtherEl.value = res.user.designation_other || '';

        window.closeUserProfileModal();
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice(res.message || 'Profile updated successfully!', 'success');
        }
      } else {
        if (alertEl) {
          alertEl.textContent = (res && res.message) || 'Failed to update profile.';
          alertEl.style.display = 'block';
          alertEl.style.background = '#fef2f2';
          alertEl.style.color = '#991b1b';
          alertEl.style.border = '1px solid #fecaca';
        }
      }
    } catch (err) {
      if (alertEl) {
        alertEl.textContent = 'Error updating profile: ' + (err.message || 'Unknown error');
        alertEl.style.display = 'block';
        alertEl.style.background = '#fef2f2';
        alertEl.style.color = '#991b1b';
        alertEl.style.border = '1px solid #fecaca';
      }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Save Profile Details'; }
    }
  };

  window.submitChangeDesignation = window.submitUpdateProfile;

  window.applyScreenVisualState = function (stateName, user) {
    var body = document.body;
    if (!body) return;
    body.classList.remove(
      'state-home-login',
      'state-workspace-hub',
      'state-manual-page',
      'state-tools-page',
      'state-softwares-page',
      'state-automation-page',
      'state-admin-page'
    );
    var resolved = stateName || 'state-home-login';
    body.classList.add(resolved);

    var ribbonEl = document.getElementById('site-top-ribbon');
    if (resolved === 'state-home-login') {
      body.classList.remove('state-logged-in');
      if (ribbonEl) ribbonEl.style.display = 'none';
    } else {
      body.classList.add('state-logged-in');
      if (ribbonEl) ribbonEl.style.display = 'block';
    }

    var eyebrow = document.getElementById('dash-welcome-eyebrow');
    var titleEl = document.getElementById('dash-hero-title');
    var taglineEl = document.getElementById('dash-tagline');
    var subEl = document.getElementById('dash-scope-subtitle');
    var hubBarTitle = document.getElementById('hub-bar-title');
    var hubBarSub = document.getElementById('hub-bar-sub');

    if (subEl) subEl.style.display = (resolved === 'state-automation-page') ? 'none' : 'block';

    if (resolved === 'state-admin-page') {
      if (eyebrow) eyebrow.textContent = '🛡️ ADMINISTRATOR CONTROL CENTER';
      if (titleEl) titleEl.textContent = PLATFORM_NAME + ' · Admin Analytics & Subscriptions';
      if (taglineEl) taglineEl.textContent = 'Live User Telemetry, Tool Usage Tracking & Razorpay Subscription Governance.';
      if (subEl) subEl.textContent = 'Monitor registered and active officers, tool adoption, paid subscriptions, and platform availability.';
      if (hubBarTitle) hubBarTitle.textContent = PLATFORM_NAME + ' · Admin Control Center';
      if (hubBarSub) hubBarSub.textContent = 'Administrator analytics, user management, tool usage & Razorpay database.';
    } else if (resolved === 'state-workspace-hub') {
      var officerFirst = (user && user.name) ? user.name.trim() : '';
      if (eyebrow) eyebrow.textContent = '🧭 OFFICER WORKSPACE HUB';
      if (titleEl) {
        titleEl.textContent = officerFirst
          ? ('Welcome, ' + officerFirst + ' · Select Your Reporting Workspace')
          : 'Select Your Reporting & Utility Workspace';
      }
      if (taglineEl) taglineEl.textContent = 'Unified Panchayat Administration Hub — Choose a Workspace Below to Continue.';
      if (subEl) subEl.textContent = 'Pick Manual Excel Reports (offline), Automated Reports (live portal robots), Document Tools, or Softwares.';
      if (hubBarTitle) hubBarTitle.textContent = PLATFORM_NAME + ' · Workspace Selector';
      if (hubBarSub) hubBarSub.textContent = 'Signed in and ready — select Manual Reports, Automated Reports, Tools, or Softwares.';
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
    } else if (resolved === 'state-softwares-page') {
      if (eyebrow) eyebrow.textContent = '💻 OFFICIAL SOFTWARES & DRIVERS';
      if (titleEl) titleEl.textContent = PLATFORM_NAME + ' · Official Softwares & Drivers Hub';
      if (taglineEl) taglineEl.textContent = 'Biometric Drivers, Java DSC Token Environments, Telugu Typing & Government Utilities.';
      if (subEl) subEl.textContent = 'Download official device drivers, biometric RD services, Java DSC environments, Telugu typing software, and government desktop utilities.';
      if (hubBarTitle) hubBarTitle.textContent = PLATFORM_NAME + ' · Softwares Hub';
      if (hubBarSub) hubBarSub.textContent = 'Official desktop software, biometric drivers & government utilities.';
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

    var profileDone = Boolean(isAuth && user);

    // Sync Fixed Top Ribbon Actions & Officer Display
    var ribPill = document.getElementById('ribbon-officer-pill');
    var ribLogout = document.getElementById('ribbon-btn-logout');
    var ribSignin = document.getElementById('ribbon-btn-signin');
    var ribAdmin = document.getElementById('ribbon-btn-admin');
    var ribDept = document.getElementById('ribbon-btn-dept-login');
    var ribDisconn = document.getElementById('ribbon-btn-disconnect-epts');

    // Sync Mobile Drawer Elements & Mobile Quick Header
    var mobAuthBox = document.getElementById('mobile-drawer-auth-box');
    var mobSignin = document.getElementById('mobile-btn-signin');
    var mobLogout = document.getElementById('mobile-btn-logout');
    var mobAdmin = document.getElementById('mobile-btn-admin');
    var mobDept = document.getElementById('mobile-btn-dept-login');
    var mobDisconn = document.getElementById('mobile-btn-disconnect-epts');
    var mobQuickOfficer = document.getElementById('ribbon-mobile-quick-officer');
    var mobQuickLogout = document.getElementById('ribbon-mobile-quick-logout');
    var mobQuickSignin = document.getElementById('ribbon-mobile-quick-signin');

    var ribEl = document.getElementById('site-top-ribbon');
    if (isAuth && profileDone) {
      if (ribEl) ribEl.style.display = 'block';
      if (document.body) {
        document.body.classList.add('state-logged-in');
        document.body.classList.remove('state-home-login');
      }
      if (ribPill) ribPill.style.display = 'inline-flex';
      if (ribLogout) ribLogout.style.display = 'inline-flex';
      if (ribSignin) ribSignin.style.display = 'none';

      // Admin option is exclusively restricted to admin.panchayatautomation.in
      var showAdminInNav = Boolean(window.isAllowedAdminUIHost() && user && user.is_admin);
      if (ribAdmin) ribAdmin.style.display = showAdminInNav ? 'inline-flex' : 'none';

      var deptActive = sessionStorage.getItem('epts_portal_auth') === 'true' || window.isDeptAuthenticated === true;
      if (ribDept) {
        ribDept.style.display = (window.currentWorkspaceMode === 'automated' || deptActive) ? 'inline-flex' : 'none';
      }
      if (ribDisconn) {
        ribDisconn.style.display = deptActive ? 'inline-flex' : 'none';
      }

      // Mobile sync
      if (mobAuthBox) mobAuthBox.style.display = 'block';
      if (mobSignin) mobSignin.style.display = 'none';
      if (mobLogout) mobLogout.style.display = 'flex';
      if (mobAdmin) mobAdmin.style.display = showAdminInNav ? 'flex' : 'none';
      if (mobDept) mobDept.style.display = (window.currentWorkspaceMode === 'automated' || deptActive) ? 'flex' : 'none';
      if (mobDisconn) mobDisconn.style.display = deptActive ? 'flex' : 'none';
      if (mobQuickOfficer) mobQuickOfficer.style.display = 'inline-flex';
      if (mobQuickLogout) mobQuickLogout.style.display = 'inline-flex';
      if (mobQuickSignin) mobQuickSignin.style.display = 'none';
    } else {
      if (ribEl) ribEl.style.display = 'none';
      if (document.body) {
        document.body.classList.remove('state-logged-in');
        document.body.classList.add('state-home-login');
      }
      if (ribPill) ribPill.style.display = 'none';
      if (ribLogout) ribLogout.style.display = 'none';
      if (ribSignin) ribSignin.style.display = 'inline-flex';
      if (ribAdmin) ribAdmin.style.display = 'none';
      if (ribDept) ribDept.style.display = 'none';
      if (ribDisconn) ribDisconn.style.display = 'none';

      // Mobile sync
      if (mobAuthBox) mobAuthBox.style.display = 'none';
      if (mobSignin) mobSignin.style.display = 'flex';
      if (mobLogout) mobLogout.style.display = 'none';
      if (mobAdmin) mobAdmin.style.display = 'none';
      if (mobDept) mobDept.style.display = 'none';
      if (mobDisconn) mobDisconn.style.display = 'none';
      if (mobQuickOfficer) mobQuickOfficer.style.display = 'none';
      if (mobQuickLogout) mobQuickLogout.style.display = 'none';
      if (mobQuickSignin) mobQuickSignin.style.display = 'inline-flex';
    }

    var activeRibbonMode = window.currentWorkspaceMode || window.getDedicatedPageSection() || 'manual';
    if (typeof window.updateRibbonActiveModule === 'function') {
      window.updateRibbonActiveModule(activeRibbonMode);
    }

    if (document.body) {
      document.body.classList.remove('state-auth-resolving');
    }
    if (isAuth) {
      if (heroCard) heroCard.style.display = profileDone ? 'none' : 'flex';
      if (btnHome) btnHome.style.display = profileDone ? 'inline-flex' : 'none';
      if (btnLogout) btnLogout.style.display = 'inline-flex';
      // Services, Privacy & Legal, and Feedback show on pre-login homepage / Console login screen
      if (btnServices) btnServices.style.display = 'none';
      if (btnPrivacy) btnPrivacy.style.display = 'none';
      if (btnFeedback) btnFeedback.style.display = 'none';
      if (btnAdmin) btnAdmin.style.display = showAdminInNav ? 'inline-flex' : 'none';
      if (btnStudio) btnStudio.style.display = profileDone ? 'inline-flex' : 'none';
      if (btnConsoleSwitch) btnConsoleSwitch.style.display = 'none';

      var modeSel = document.getElementById('workspace-mode-selector');
      var btnSwitchMode = document.getElementById('btn-switch-workspace-mode');
      var toolsSec = document.getElementById('tools-modules-section');
      var softwaresSec = document.getElementById('softwares-modules-section');
      var onSoftwaresRoute = (typeof window.getDedicatedPageSection === 'function' && window.getDedicatedPageSection() === 'softwares');
      if (!profileDone && !onSoftwaresRoute) {
        if (btnDeptLogin) btnDeptLogin.style.display = 'none';
        if (btnDisconn) btnDisconn.style.display = 'none';
        if (globalBar) globalBar.style.display = 'none';
        if (officerBanner) officerBanner.style.display = 'none';
        if (modeSel) modeSel.style.display = 'none';
        if (btnSwitchMode) btnSwitchMode.style.display = 'none';
        if (portalSec) portalSec.style.display = 'none';
        if (consoleSec) consoleSec.style.display = 'none';
        if (toolsSec) toolsSec.style.display = 'none';
        if (softwaresSec) softwaresSec.style.display = 'none';
        if (dcbSec) dcbSec.style.display = 'none';
        if (dash) dash.style.display = 'none';
        window.applyScreenVisualState('state-home-login', user);
      } else if (!profileDone && onSoftwaresRoute) {
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
        if (heroCard) heroCard.style.display = 'none';
        if (dash) dash.style.display = 'block';
        if (softwaresSec) softwaresSec.style.display = 'block';
        if (dashBadge) dashBadge.textContent = '💻 Official Softwares & Drivers';
        window.applyScreenVisualState('state-softwares-page', user);
        if (typeof window.handleSoftwareDirectLink === 'function') {
          setTimeout(function () { window.handleSoftwareDirectLink(); }, 120);
        }
      } else {
        if (globalBar) globalBar.style.display = 'flex';
        var activeMode = window.currentWorkspaceMode;
        if (activeMode === 'admin' || window.isAdminRouteOrHost()) {
          if (dash) dash.style.display = 'none';
          if (modeSel) modeSel.style.display = 'none';
          if (portalSec) portalSec.style.display = 'none';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'none';
          if (softwaresSec) softwaresSec.style.display = 'none';
          if (dcbSec) dcbSec.style.display = 'none';
          if (btnSwitchMode) btnSwitchMode.style.display = 'none';
          if (btnDeptLogin) btnDeptLogin.style.display = 'none';
          window.applyScreenVisualState('state-admin-page', user);
        } else {
          if (dash) dash.style.display = 'block';
          if (activeMode === 'manual') {
          if (modeSel) modeSel.style.display = 'none';
          if (portalSec) portalSec.style.display = 'block';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'none';
          if (softwaresSec) softwaresSec.style.display = 'none';
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
          if (softwaresSec) softwaresSec.style.display = 'none';
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
          if (softwaresSec) softwaresSec.style.display = 'none';
          if (dcbSec) dcbSec.style.display = 'none';
          if (btnSwitchMode) btnSwitchMode.style.display = 'inline-flex';
          if (btnDeptLogin) btnDeptLogin.style.display = sessionStorage.getItem('epts_portal_auth') === 'true' ? 'inline-flex' : 'none';
          if (dashBadge) dashBadge.textContent = '🧰 Tools & Utilities Studio';
          window.applyScreenVisualState('state-tools-page', user);
        } else if (activeMode === 'softwares') {
          if (modeSel) modeSel.style.display = 'none';
          if (portalSec) portalSec.style.display = 'none';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'none';
          if (softwaresSec) softwaresSec.style.display = 'block';
          if (dcbSec) dcbSec.style.display = 'none';
          if (btnSwitchMode) btnSwitchMode.style.display = 'inline-flex';
          if (btnDeptLogin) btnDeptLogin.style.display = sessionStorage.getItem('epts_portal_auth') === 'true' ? 'inline-flex' : 'none';
          if (dashBadge) dashBadge.textContent = '💻 Official Softwares & Drivers';
          window.applyScreenVisualState('state-softwares-page', user);
          if (typeof window.handleSoftwareDirectLink === 'function') {
            setTimeout(function () { window.handleSoftwareDirectLink(); }, 100);
          }
        } else {
          if (modeSel) modeSel.style.display = 'block';
          if (portalSec) portalSec.style.display = 'none';
          if (consoleSec) consoleSec.style.display = 'none';
          if (toolsSec) toolsSec.style.display = 'none';
          if (softwaresSec) softwaresSec.style.display = 'none';
          if (dcbSec) dcbSec.style.display = 'none';
          if (btnSwitchMode) btnSwitchMode.style.display = 'none';
          if (btnDeptLogin) btnDeptLogin.style.display = sessionStorage.getItem('epts_portal_auth') === 'true' ? 'inline-flex' : 'none';
          if (dashBadge) dashBadge.textContent = '🟢 Choose Reporting Mode';
          window.applyScreenVisualState('state-workspace-hub', user);
        }
        }
      }
    } else {
      window.currentWorkspaceMode = null;
      window.hideAllStations();
      var modeSelOut = document.getElementById('workspace-mode-selector');
      var btnSwitchOut = document.getElementById('btn-switch-workspace-mode');
      var toolsOut = document.getElementById('tools-modules-section');
      var softwaresOut = document.getElementById('softwares-modules-section');
      if (modeSelOut) modeSelOut.style.display = 'none';
      if (btnSwitchOut) btnSwitchOut.style.display = 'none';
      if (toolsOut) toolsOut.style.display = 'none';
      if (softwaresOut) softwaresOut.style.display = 'none';
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
    if (typeof window.applyAccessPolicyUi === 'function') {
      window.applyAccessPolicyUi(window.currentAccessPolicy, user);
    }
  };

  window.showWorkspaceModeSelector = function () {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return;
    }
    var u = window.getScopedUser();
    window.currentWorkspaceMode = null;
    try { sessionStorage.removeItem('epts_workspace_mode'); } catch (e) {}
    window.hideAllStations();
    window.setPortalUI(true, u);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  window.openAdminNonAdminGate = function (user) {
    window.hideAllStations();
    window.setPortalUI(true, user);
    var gate = document.getElementById('admin-nonadmin-gate');
    var desc = document.getElementById('admin-nonadmin-desc');
    var link = document.getElementById('admin-nonadmin-portal-link');
    if (desc) {
      var who = user && user.gmail ? (escapeHtml(user.name || 'Officer') + ' (' + escapeHtml(user.gmail) + ')') : 'a standard officer account';
      desc.innerHTML =
        'Currently signed in as <strong>' + who + '</strong>, which does not have Administrator privileges. ' +
        'Sign in with an authorized Administrator Google account or return to the Officer Workspace Portal.';
    }
    if (link) {
      link.href = window.isProdCustomDomain() ? 'https://panchayatautomation.in/' : '/';
    }
    if (gate) gate.style.display = 'block';
  };

  window.selectWorkspaceMode = function (mode, options) {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return false;
    }
    var u = window.getScopedUser();
    var rawMode = String(mode || '').trim().toLowerCase();
    if (rawMode === 'admin') {
      if (!window.isAllowedAdminUIHost()) {
        if (typeof window.isProdCustomDomain === 'function' && window.isProdCustomDomain()) {
          window.location.href = 'https://admin.panchayatautomation.in/';
          return true;
        }
      }
      window.currentWorkspaceMode = 'admin';
      if (u && u.is_admin && typeof window.openAdminDashboardStation === 'function') {
        window.openAdminDashboardStation();
      } else {
        window.openAdminNonAdminGate(u);
      }
      return true;
    }
    var m = rawMode === 'automated' ? 'automated' : (rawMode === 'tools' ? 'tools' : (rawMode === 'softwares' || rawMode === 'software' ? 'softwares' : 'manual'));

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

    window.currentWorkspaceMode = m;
    try {
      sessionStorage.setItem('epts_workspace_mode', m);
      localStorage.setItem('epts_workspace_mode', m);
    } catch (e) {}
    window.hideAllStations();
    window.setPortalUI(true, u);
    if (!(options && options.skipScroll)) {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    try {
      if (window.history && typeof window.history.pushState === 'function' && !(options && options.fromInit)) {
        var currentPath = (window.location.pathname || '').toLowerCase();
        var isSoftwareSub = m === 'softwares' && (currentPath.indexOf('/softwares/') === 0 || currentPath.indexOf('/software/') === 0);
        if (!isSoftwareSub) {
          var path = m === 'automated' ? '/autoreports' : (m === 'tools' ? '/tools' : (m === 'softwares' ? '/softwares' : '/manualreports'));
          window.history.pushState(null, '', path);
        }
      }
    } catch (e) {}
    var isDirectClick = Boolean(options && options.isDirectClick);
    if (m === 'automated' && isDirectClick) {
      Promise.resolve(
        typeof window.initConsoleAfterPortalAuth === 'function'
          ? window.initConsoleAfterPortalAuth()
          : (window.isDeptAuthenticated === true)
      ).then(function (deptAuthed) {
        if (!deptAuthed && typeof window.openDepartmentLoginModal === 'function') {
          window.openDepartmentLoginModal();
        }
      }).catch(function () {
        if (typeof window.openDepartmentLoginModal === 'function') {
          window.openDepartmentLoginModal();
        }
      });
    }
    if (typeof window.updateRibbonActiveModule === 'function') {
      window.updateRibbonActiveModule(m);
    }
    return true;
  };

  window.showDashboard = function () {
    if (!window.isPortalAuthenticated) {
      window.setPortalUI(false, null);
      return;
    }
    var u = window.getScopedUser();
    if (window.isAdminRouteOrHost()) {
      window.selectWorkspaceMode('admin', { fromInit: true });
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
    if (window.isAdminRouteOrHost()) {
      window.selectWorkspaceMode('admin', { fromInit: true });
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
    var wasConsoleLogout = Boolean(
      sc === 'console' ||
      window.currentWorkspaceMode === 'automated' ||
      dedSection === 'automated' ||
      sessionStorage.getItem('epts_portal_auth') === 'true'
    );
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
    if (wasConsoleLogout) {
      try {
        if (window.DeptSessionManager && typeof window.DeptSessionManager.consoleFetch === 'function') {
          await window.DeptSessionManager.consoleFetch('/api/naresh/logout', { method: 'POST' });
        } else {
          await fetch('/api/naresh/logout', { method: 'POST' });
        }
      } catch (e) {}
    }
    try {
      if (window.DeptSessionManager && typeof window.DeptSessionManager.consoleFetch === 'function') {
        await window.DeptSessionManager.consoleFetch('/api/auth/portal-logout', { method: 'POST' });
      } else {
        await fetch('/api/auth/portal-logout', { method: 'POST' });
      }
    } catch (e) {}
    if (window.DeptSessionManager && typeof window.DeptSessionManager.clearEptsMetadata === 'function') {
      window.DeptSessionManager.clearEptsMetadata();
    }
    window.isDeptAuthenticated = false;
    window.clearScopeSessionStorage('portal');
    window.clearScopeSessionStorage('console');
    window.setPortalUI(false, null);
    if (wasConsoleLogout) {
      try { window.open('', '_self'); } catch (e) {}
      try { window.close(); } catch (e) {}
    }
    var dest = '/';
    if (dedSection) {
      dest = (window.isAdminHost() || window.isReportsHost() || window.isManualHost() || window.isToolsHost())
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

  var escHtml = window.escapeHtml || function (str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  window.cachedFeedbackList = [];

  window.isCurrentOfficerAdmin = function () {
    var u = (typeof window.getScopedUser === 'function') ? window.getScopedUser() : null;
    if (u && u.is_admin) return true;
    if (window.currentUser && window.currentUser.is_admin) return true;
    if (window.portalUser && window.portalUser.is_admin) return true;
    try {
      var raw = sessionStorage.getItem('epts_auth_user') || localStorage.getItem('epts_auth_user');
      if (raw) {
        var parsed = JSON.parse(raw);
        if (parsed && parsed.is_admin) return true;
      }
    } catch (e) {}
    return false;
  };

  window.switchFeedbackTab = function (tab) {
    var viewBoard = document.getElementById('fb-view-board');
    var viewSubmit = document.getElementById('fb-view-submit');
    var tabBoard = document.getElementById('fb-tab-board');
    var tabSubmit = document.getElementById('fb-tab-submit');
    var filterWrap = document.getElementById('fb-filter-wrapper');
    if (!viewBoard || !viewSubmit) return;

    if (tab === 'submit') {
      viewBoard.style.display = 'none';
      viewSubmit.style.display = 'block';
      if (filterWrap) filterWrap.style.display = 'none';
      if (tabSubmit) {
        tabSubmit.style.background = '#064e3b';
        tabSubmit.style.color = '#ffffff';
        tabSubmit.style.border = 'none';
      }
      if (tabBoard) {
        tabBoard.style.background = '#ffffff';
        tabBoard.style.color = '#334155';
        tabBoard.style.border = '1px solid #cbd5e1';
      }
    } else {
      viewBoard.style.display = 'block';
      viewSubmit.style.display = 'none';
      if (filterWrap) filterWrap.style.display = 'flex';
      if (tabBoard) {
        tabBoard.style.background = '#064e3b';
        tabBoard.style.color = '#ffffff';
        tabBoard.style.border = 'none';
      }
      if (tabSubmit) {
        tabSubmit.style.background = '#ffffff';
        tabSubmit.style.color = '#334155';
        tabSubmit.style.border = '1px solid #cbd5e1';
      }
    }
  };

  window.openFeedbackModal = function () {
    var modal = document.getElementById('feedback-modal');
    if (!modal) return;
    var user = window.getScopedUser() || {};
    var fbName = document.getElementById('fb-name');
    var fbDesig = document.getElementById('fb-desig');
    if (fbName && user.name && !fbName.value) fbName.value = user.name;
    if (fbDesig && user.designation && DESIGNATIONS.indexOf(user.designation) !== -1) {
      fbDesig.value = user.designation;
    }
    var alertEl = document.getElementById('feedback-alert');
    if (alertEl) alertEl.style.display = 'none';
    modal.style.display = 'flex';
    window.switchFeedbackTab('board');
    window.loadPublicFeedbackBoard();
  };

  window.closeFeedbackModal = function () {
    var modal = document.getElementById('feedback-modal');
    if (modal) modal.style.display = 'none';
  };

  window.loadPublicFeedbackBoard = async function () {
    var container = document.getElementById('fb-cards-container');
    var countEl = document.getElementById('fb-board-count');
    try {
      var res = await fetch('/api/feedback');
      var data = await res.json().catch(function () { return {}; });
      var list = Array.isArray(data.feedback) ? data.feedback : [];
      window.cachedFeedbackList = list;
      if (countEl) countEl.textContent = String(list.length);
      window.filterFeedbackCards();
    } catch (err) {
      if (container) {
        container.innerHTML = '<div style="text-align:center; padding:30px; color:#ef4444; font-weight:700;">Could not load community feedback: ' + escHtml(err.message) + '</div>';
      }
    }
  };

  window.filterFeedbackCards = function () {
    var filterEl = document.getElementById('fb-category-filter');
    var val = filterEl ? filterEl.value : 'ALL';
    var all = window.cachedFeedbackList || [];
    var filtered = all.filter(function (fb) {
      if (val === 'ALL') return true;
      if (val === 'REPLIED_ONLY') return Boolean(fb.admin_reply);
      return (fb.category || '').toLowerCase().indexOf(val.toLowerCase()) !== -1;
    });
    window.renderPublicFeedbackCards(filtered);
  };

  window.renderPublicFeedbackCards = function (items) {
    var container = document.getElementById('fb-cards-container');
    if (!container) return;
    if (!items || items.length === 0) {
      container.innerHTML = '<div style="text-align:center; padding:40px 16px; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:12px; color:#64748b;">' +
        '<div style="font-size:2.2rem; margin-bottom:8px;">💡</div>' +
        '<div style="font-weight:800; font-size:1rem; color:#1e293b;">No feedback or suggestions found</div>' +
        '<div style="font-size:0.84rem; margin-top:4px;">Be the first to share an idea, report a difficulty, or suggest a new feature!</div>' +
        '<button type="button" onclick="window.switchFeedbackTab(\'submit\')" style="margin-top:14px; padding:8px 18px; background:#064e3b; color:#ffffff; border:none; border-radius:8px; font-size:0.85rem; font-weight:700; cursor:pointer;">✍️ Submit Suggestion Now</button>' +
        '</div>';
      return;
    }

    var isAdmin = window.isCurrentOfficerAdmin();

    container.innerHTML = items.map(function (fb) {
      var fId = fb.feedback_id || fb.id || '';
      var cat = fb.category || 'General Feedback';
      var hasReply = Boolean(fb.admin_reply);
      var catIcon = '💡';
      if (cat.indexOf('Bug') !== -1) catIcon = '🐛';
      else if (cat.indexOf('Feature') !== -1) catIcon = '🚀';
      else if (cat.indexOf('Data') !== -1) catIcon = '📊';
      else if (cat.indexOf('Appreciation') !== -1) catIcon = '⭐';

      var dateStr = '—';
      try {
        if (fb.created_at) {
          var d = new Date(fb.created_at);
          if (!isNaN(d.getTime())) {
            dateStr = d.toLocaleString('en-IN', {
              year: 'numeric',
              month: 'short',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
            });
          }
        }
      } catch (e) {}

      var html = '<div class="fb-board-card" id="fb-card-' + escHtml(fId) + '">';
      html += '<div class="fb-card-header">';
      html += '<div class="fb-officer-line">';
      html += '<span class="fb-officer-name">' + escHtml(fb.name || 'Panchayat Officer') + '</span>';
      if (fb.designation) {
        html += '<span class="fb-desig-tag">' + escHtml(fb.designation) + '</span>';
      }
      html += '<span class="fb-category-tag">' + catIcon + ' ' + escHtml(cat) + '</span>';
      if (hasReply) {
        html += '<span style="background:#ecfdf5; color:#065f46; border:1px solid #a7f3d0; font-size:0.7rem; font-weight:800; padding:2px 8px; border-radius:10px;">🛡️ Replied</span>';
      } else {
        html += '<span style="background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-size:0.7rem; font-weight:800; padding:2px 8px; border-radius:10px;">⏳ Under Review</span>';
      }
      html += '</div>';
      html += '<div class="fb-date-tag">' + escHtml(dateStr) + '</div>';
      html += '</div>';

      html += '<div class="fb-message-body">' + escHtml(fb.message || '') + '</div>';

      if (hasReply) {
        var replyDateStr = '';
        try {
          if (fb.admin_replied_at) {
            var rd = new Date(fb.admin_replied_at);
            if (!isNaN(rd.getTime())) {
              replyDateStr = rd.toLocaleString('en-IN', {
                year: 'numeric',
                month: 'short',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
              });
            }
          }
        } catch (e) {}

        html += '<div class="fb-admin-reply-box">';
        html += '<div class="fb-admin-reply-header">';
        html += '<div class="fb-admin-reply-title"><span>🛡️</span> Official Admin Response · ' + escHtml(fb.admin_name || 'Administrator') + '</div>';
        if (replyDateStr) {
          html += '<div class="fb-admin-reply-time">' + escHtml(replyDateStr) + '</div>';
        }
        html += '</div>';
        html += '<div class="fb-admin-reply-text">' + escHtml(fb.admin_reply) + '</div>';
        html += '</div>';
      }

      if (isAdmin) {
        html += '<div style="margin-top:10px; display:flex; justify-content:flex-end;">';
        html += '<button type="button" onclick="window.toggleInlineAdminReply(\'' + escHtml(fId) + '\')" style="padding:4px 12px; font-size:0.76rem; font-weight:800; color:#064e3b; background:#ecfdf5; border:1px solid #6ee7b7; border-radius:6px; cursor:pointer;">';
        html += (hasReply ? '✏️ Edit Admin Reply' : '💬 Direct Admin Reply');
        html += '</button>';
        html += '</div>';

        html += '<div id="inline-reply-box-' + escHtml(fId) + '" class="fb-inline-reply-form" style="display:none;">';
        html += '<label style="display:block; font-size:0.76rem; font-weight:800; color:#064e3b; margin-bottom:4px;">Official Administrator Response (Visible to Everyone):</label>';
        html += '<textarea id="inline-reply-text-' + escHtml(fId) + '" rows="3" style="width:100%; box-sizing:border-box; padding:8px 10px; border:1px solid #cbd5e1; border-radius:6px; font-size:0.84rem; font-family:inherit; resize:vertical;" placeholder="Write reply to ' + escHtml(fb.name || 'officer') + '...">' + escHtml(fb.admin_reply || '') + '</textarea>';
        html += '<div style="display:flex; justify-content:flex-end; gap:8px; margin-top:8px;">';
        html += '<button type="button" onclick="window.toggleInlineAdminReply(\'' + escHtml(fId) + '\')" style="padding:6px 12px; font-size:0.76rem; background:#f1f5f9; border:1px solid #cbd5e1; border-radius:6px; cursor:pointer; font-weight:700;">Cancel</button>';
        html += '<button type="button" id="btn-inline-submit-' + escHtml(fId) + '" onclick="window.submitInlineAdminReply(\'' + escHtml(fId) + '\')" style="padding:6px 14px; font-size:0.78rem; background:#059669; color:#fff; border:none; border-radius:6px; cursor:pointer; font-weight:800;">Publish Reply</button>';
        html += '</div>';
        html += '</div>';
      }

      html += '</div>';
      return html;
    }).join('');
  };

  window.toggleInlineAdminReply = function (feedbackId) {
    var box = document.getElementById('inline-reply-box-' + feedbackId);
    if (!box) return;
    box.style.display = (box.style.display === 'none' || !box.style.display) ? 'block' : 'none';
  };

  window.submitInlineAdminReply = async function (feedbackId) {
    var txtEl = document.getElementById('inline-reply-text-' + feedbackId);
    var btn = document.getElementById('btn-inline-submit-' + feedbackId);
    var reply = txtEl ? txtEl.value.trim() : '';
    if (!reply) {
      window.showPortalNotice('Please enter an official reply message before publishing.', 'warning');
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Publishing...';
    }
    try {
      var res = await fetch('/api/feedback/' + encodeURIComponent(feedbackId) + '/reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply: reply }),
      });
      var data = await res.json().catch(function () { return {}; });
      if (res.ok && data && data.success) {
        window.loadPublicFeedbackBoard();
        if (typeof window.showPortalNotice === 'function') {
          window.showPortalNotice('Official admin reply published successfully!', 'success');
        }
      } else {
        window.showPortalNotice((data && data.message) || 'Failed to publish reply.', 'error');
      }
    } catch (err) {
      window.showPortalNotice('Error publishing reply: ' + err.message, 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Publish Reply';
      }
    }
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
          var msgArea = document.getElementById('fb-message');
          if (msgArea) msgArea.value = '';
          window.switchFeedbackTab('board');
          window.loadPublicFeedbackBoard();
        }, 900);
      } else {
        showFbAlert((data && data.message) || 'Failed to submit feedback.', false);
      }
    } catch (err) {
      showFbAlert('Error submitting feedback: ' + err.message, false);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>📤</span> Submit Feedback &amp; Suggestion';
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
    var cachedToken = typeof window.getScopedAuthToken === 'function' ? window.getScopedAuthToken(scope) : '';
    var cachedUser = typeof window.getScopedUser === 'function' ? window.getScopedUser(scope) : null;
    if (cachedToken && cachedUser) {
      isPortalAuth = true;
      portalUser = cachedUser;
      window.setPortalUI(true, cachedUser);
    }

    try {
      var statusUrl = '/api/auth/portal-status?_ts=' + Date.now();
      var reqHeaders = { 'Cache-Control': 'no-store' };
      if (cachedToken) {
        reqHeaders['Authorization'] = 'Bearer ' + cachedToken;
      }
      var pRes = (window.DeptSessionManager && typeof window.DeptSessionManager.consoleFetch === 'function')
        ? await window.DeptSessionManager.consoleFetch(statusUrl, { headers: reqHeaders, credentials: 'include', cache: 'no-store' })
        : await fetch(statusUrl, { headers: reqHeaders, credentials: 'include', cache: 'no-store' });
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

        if (pData.authenticated && pData.user) {
          isPortalAuth = true;
          portalUser = pData.user;
          window.isPortalAuthenticated = true;
          window.setScopedUser(portalUser, scope);
          if (pData.token) window.setScopedAuthToken(pData.token, scope);
          window.setPortalUI(true, portalUser);
        } else if (cachedToken && cachedUser) {
          isPortalAuth = true;
          portalUser = cachedUser;
          window.isPortalAuthenticated = true;
          window.setPortalUI(true, cachedUser);
        } else {
          isPortalAuth = false;
          portalUser = null;
          window.isPortalAuthenticated = false;
          window.setScopedUser(null, scope);
          window.setPortalUI(false, null);
        }

        if (window.FirebasePortalAuth && pData.firebase_config) {
          try {
            window.FirebasePortalAuth.init(pData.firebase_config, pData.auth_emulator_host);
            if (typeof window.FirebasePortalAuth.consumeRedirectSignIn === 'function') {
              var redirResult = await window.FirebasePortalAuth.consumeRedirectSignIn();
              if (redirResult && redirResult.idToken) {
                var fRes = await fetch('/api/auth/firebase-login', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  credentials: 'include',
                  body: JSON.stringify({ id_token: redirResult.idToken }),
                });
                if (fRes.ok) {
                  var fData = await fRes.json();
                  if (fData && fData.success && fData.user) {
                    window.handleFirebaseLoginSuccess(fData);
                  }
                }
              }
            }
          } catch (fbErr) {
            console.warn('Firebase Auth SDK initialization note:', fbErr);
          }
        }
      } else {
        if (cachedToken && cachedUser) {
          isPortalAuth = true;
          portalUser = cachedUser;
          window.isPortalAuthenticated = true;
          window.setPortalUI(true, cachedUser);
        } else {
          window.setPortalUI(isPortalAuth, portalUser);
        }
      }
    } catch (e) {
      console.warn('Portal auth status check note:', e);
      if (cachedToken && cachedUser) {
        isPortalAuth = true;
        portalUser = cachedUser;
        window.isPortalAuthenticated = true;
        window.setPortalUI(true, cachedUser);
      } else {
        window.setPortalUI(isPortalAuth, portalUser);
      }
    }

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
      if (urlParams.get('auth_required') === '1') {
        showLoginAlert('🔒 Authorization Required: Please sign in with Google or your registered email to access this module.', 'warning');
      }
      return;
    }

    await window.proceedAfterPortalAuth();

    if (portalUser && typeof window.checkAndShowFirstLoginProfilePrompt === 'function') {
      window.checkAndShowFirstLoginProfilePrompt(portalUser, false);
    }

    var dedSection = window.getDedicatedPageSection();
    if (dedSection && (!target || !(window.DeptSessionManager && urlParams.get('pending_module')))) {
      if (dedSection === 'admin' || dedSection === 'manual' || dedSection === 'tools' || dedSection === 'softwares') {
        window.selectWorkspaceMode(dedSection, { skipScroll: true, fromInit: true });
      } else if (dedSection === 'automated' && !urlParams.get('mode') && !target) {
        window.selectWorkspaceMode('automated', { skipScroll: true, fromInit: true });
      }
    }

    if (!target || (window.DeptSessionManager && urlParams.get('pending_module'))) return;

    if (target === 'multiday' || target === 'multi-day' || target === 'dsr_multiday') {
      window.location.href = '/reports/multi-day-dsr';
    } else if (target === 'dsr_excel' || target === 'manual-reports' || target === 'manual_reports') {
      window.location.href = '/reports/ps-attendance#reports';
    } else if (target === 'tax-dcb' || target === 'tax' || target === 'tax-station') {
      if (typeof window.openTaxDcbStation === 'function') await window.openTaxDcbStation();
    } else if (target === 'inspections') {
      if (typeof window.openGpInspectionsStation === 'function') await window.openGpInspectionsStation();
    } else if (target === 'auto-multi-dsr' || target === 'auto-multiday' || target === 'auto-multi') {
      if (typeof window.openAutoMultiDsrStation === 'function') await window.openAutoMultiDsrStation();
    } else if (target === 'state-format' || target === 'state_format' || target === 'dsr_state_format') {
      if (typeof window.openStateFormatRobot === 'function') await window.openStateFormatRobot();
    } else if (target === 'admin' && window.isAdminRouteOrHost() && portalUser && portalUser.is_admin) {
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
