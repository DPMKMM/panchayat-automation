/**
 * Centralized Department Login Session & Navigation Manager
 * Shared across e-Panchayat Automation Console and Console subpages.
 * Stores UI navigation intents only (never stores passwords or OTPs).
 */
(function () {
  'use strict';

  var PENDING_ACTION_KEY = 'epts_pending_action';
  var PENDING_TTL_MS = 30 * 60 * 1000;
  var EPTS_META_KEYS = [
    'epts_portal_auth',
    'epts_dept_session',
    'epts_officer_id',
    'epts_user_level',
    'epts_mandal_name',
    'epts_district_name',
    'epts_office_name',
  ];

  var _inFlightVerify = null;

  function readCookie(name) {
    try {
      var prefix = name + '=';
      var parts = (document.cookie || '').split(';');
      for (var i = 0; i < parts.length; i++) {
        var s = parts[i].trim();
        if (s.indexOf(prefix) === 0) {
          return decodeURIComponent(s.slice(prefix.length));
        }
      }
    } catch (e) {}
    return '';
  }

  function isValidSid(val) {
    return typeof val === 'string' && /^[a-zA-Z0-9_\-]{8,64}$/.test(val.trim());
  }

  function persistSid(sid) {
    try { sessionStorage.setItem('epts_session_id', sid); } catch (e) {}
    try { localStorage.setItem('epts_session_id', sid); } catch (e) {}
    return sid;
  }

  function hasStoredSid() {
    try {
      if (isValidSid(sessionStorage.getItem('epts_session_id') || '')) return true;
      if (isValidSid(localStorage.getItem('epts_session_id') || '')) return true;
    } catch (e) {}
    return false;
  }

  function getSessionId() {
    var sid = '';
    try {
      var urlSid = new URLSearchParams(window.location.search || '').get('session_id') || '';
      if (isValidSid(urlSid)) sid = urlSid.trim();
    } catch (e) {}
    if (!isValidSid(sid)) {
      var fromCookie = readCookie('epts_session_id');
      if (isValidSid(fromCookie)) sid = fromCookie.trim();
    }
    if (!isValidSid(sid)) {
      try { sid = sessionStorage.getItem('epts_session_id') || ''; } catch (e) {}
    }
    if (!isValidSid(sid)) {
      try { sid = localStorage.getItem('epts_session_id') || ''; } catch (e) {}
    }
    if (!isValidSid(sid)) {
      sid =
        'sid_' +
        Date.now().toString(36) +
        '_' +
        Math.random().toString(36).substring(2, 10) +
        Math.random().toString(36).substring(2, 10);
    }
    return persistSid(sid.trim());
  }

  function adoptServerSessionId(serverSid) {
    if (!isValidSid(serverSid)) return getSessionId();
    var clean = serverSid.trim();
    var current = '';
    try {
      current = (sessionStorage.getItem('epts_session_id') || localStorage.getItem('epts_session_id') || '').trim();
    } catch (e) {}
    if (current && current !== clean) {
      clearEptsMetadata();
    }
    return persistSid(clean);
  }

  function isReportsHost() {
    try {
      var host = (window.location.hostname || '').toLowerCase();
      return (
        host.indexOf('reports.') === 0 ||
        host.indexOf('www.reports.') === 0 ||
        host.indexOf('autoreports.') === 0 ||
        host.indexOf('www.autoreports.') === 0
      );
    } catch (e) {
      return false;
    }
  }

  function isConsoleContext() {
    if (typeof window.isConsoleScope === 'function') {
      return Boolean(window.isConsoleScope());
    }
    try {
      if (isReportsHost()) {
        return true;
      }
      var sp = new URLSearchParams(window.location.search || '');
      var site = (sp.get('site') || '').trim().toLowerCase();
      return site === 'console' || site === 'reports';
    } catch (e) {
      return false;
    }
  }

  function buildScopedUrl(basePath, extraParams) {
    var url = new URL(basePath, window.location.origin);
    if (!isReportsHost() && isConsoleContext() && !url.searchParams.has('site')) {
      url.searchParams.set('site', 'console');
    }
    if (extraParams && typeof extraParams === 'object') {
      Object.keys(extraParams).forEach(function (k) {
        var val = extraParams[k];
        if (val !== undefined && val !== null && String(val).trim() !== '') {
          url.searchParams.set(k, String(val).trim());
        }
      });
    }
    return url.pathname + url.search + url.hash;
  }

  function getConsoleHomeUrl(extraParams) {
    return buildScopedUrl('/', extraParams);
  }

  function appendSessionParam(rawUrl) {
    if (!rawUrl) return rawUrl;
    try {
      var hashIdx = rawUrl.indexOf('#');
      var hashPart = hashIdx !== -1 ? rawUrl.slice(hashIdx) : '';
      var basePart = hashIdx !== -1 ? rawUrl.slice(0, hashIdx) : rawUrl;
      var url = new URL(basePart, window.location.origin);
      url.searchParams.set('session_id', getSessionId());
      if (!isReportsHost() && isConsoleContext() && !url.searchParams.has('site')) {
        url.searchParams.set('site', 'console');
      }
      return url.pathname + url.search + hashPart;
    } catch (e) {
      return rawUrl;
    }
  }

  function clearEptsMetadata() {
    EPTS_META_KEYS.forEach(function (k) {
      try { sessionStorage.removeItem(k); } catch (e) {}
      try { localStorage.removeItem(k); } catch (e) {}
    });
    try { sessionStorage.removeItem('epts_session_id'); } catch (e) {}
    try { localStorage.removeItem('epts_session_id'); } catch (e) {}
    if (typeof window !== 'undefined') {
      window.reportData = null;
      window.currentMandalName = '';
      window.currentUserLevel = 'district';
      ['results-section', 'auto-multi-dsr-station', 'auto-multi-results-section', 'inspections-results-card', 'balance-results-card', 'state-format-station', 'state-format-results'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
      });
    }
  }

  function syncEptsMetadata(data, fallbackUser) {
    if (!data || !data.authenticated) {
      clearEptsMetadata();
      return;
    }
    var officer = String(data.user_id || fallbackUser || 'Officer').trim();
    var uLevel = String(data.user_level || 'district').trim();
    var mName = (uLevel === 'mandal') ? String(data.mandal_name || '').trim() : '';
    var dName = String(data.district_name || '').trim();
    var oName = String(data.office_name || '').trim();
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
  }

  function sanitizeParams(params) {
    var clean = {};
    if (!params || typeof params !== 'object') return clean;
    Object.keys(params).forEach(function (k) {
      var lk = k.toLowerCase();
      if (lk.indexOf('pass') !== -1 || lk.indexOf('pwd') !== -1 || lk === 'otp') {
        return;
      }
      var v = params[k];
      if (v !== undefined && v !== null) {
        clean[k] = v;
      }
    });
    return clean;
  }

  function savePendingAction(action) {
    if (!action || !action.module) return null;
    var payload = {
      module: String(action.module).trim().toLowerCase(),
      returnUrl: action.returnUrl ? String(action.returnUrl) : '',
      autoGenerate: action.autoGenerate === true,
      reason: action.reason ? String(action.reason) : 'required',
      params: sanitizeParams(action.params),
      createdAt: Date.now(),
    };
    try {
      sessionStorage.setItem(PENDING_ACTION_KEY, JSON.stringify(payload));
    } catch (e) {}
    return payload;
  }

  function peekPendingAction() {
    try {
      var raw = sessionStorage.getItem(PENDING_ACTION_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || !parsed.module) return null;
      if (parsed.createdAt && Date.now() - parsed.createdAt > PENDING_TTL_MS) {
        clearPendingAction();
        return null;
      }
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function consumePendingAction() {
    var item = peekPendingAction();
    clearPendingAction();
    return item;
  }

  function clearPendingAction() {
    try { sessionStorage.removeItem(PENDING_ACTION_KEY); } catch (e) {}
  }

  function parsePendingFromUrl(searchStr) {
    try {
      var sp = new URLSearchParams(searchStr || window.location.search || '');
      var mod = (sp.get('pending_module') || '').trim().toLowerCase();
      if (!mod) return null;
      var params = {};
      ['fy', 'financial_year', 'month', 'year', 'report_type', 'excluded_modules', 'report_code', 'mandal', 'district', 'balance_date', 'auto_date', 'cutoff_time', 'sort_by', 'force_fresh'].forEach(function (k) {
        var v = sp.get(k);
        if (v !== null && v !== '') params[k] = v;
      });
      if (params.fy && !params.financial_year) params.financial_year = params.fy;
      return {
        module: mod,
        autoGenerate: sp.get('auto_generate') === '1',
        reason: (sp.get('reason') || 'required').trim().toLowerCase(),
        params: sanitizeParams(params),
      };
    } catch (e) {
      return null;
    }
  }

  async function consoleFetch(url, options) {
    var opts = options ? Object.assign({}, options) : {};
    var headers = new Headers(opts.headers || {});
    if (!headers.has('X-Session-ID')) headers.set('X-Session-ID', getSessionId());
    if (!headers.has('X-Platform-Scope')) {
      headers.set('X-Platform-Scope', isConsoleContext() ? 'console' : 'portal');
    }
    try {
      var consoleTok = sessionStorage.getItem('console_token') || '';
      if (consoleTok && !headers.has('X-Console-Token')) {
        headers.set('X-Console-Token', consoleTok);
      }
      var portalTok = sessionStorage.getItem('portal_token') || '';
      if (portalTok && !headers.has('X-Portal-Token')) {
        headers.set('X-Portal-Token', portalTok);
      }
    } catch (e) {}
    opts.headers = headers;
    if (!opts.credentials) opts.credentials = 'same-origin';
    return fetch(url, opts);
  }

  async function verifyStatus() {
    if (_inFlightVerify) {
      return _inFlightVerify;
    }
    _inFlightVerify = (async function () {
      var mySid = getSessionId();
      try {
        var res = await consoleFetch('/api/naresh/session-status?_ts=' + Date.now(), { cache: 'no-store' });
        var data = await res.json().catch(function () { return {}; });
        if (res.status === 401 || res.status === 403) {
          clearEptsMetadata();
          return {
            ok: false,
            httpStatus: res.status,
            stage1Required: true,
            authenticated: false,
            expired: false,
            status: 'stage1_required',
            user_id: '',
            data: data || {},
          };
        }
        if (!res.ok) {
          clearEptsMetadata();
          return {
            ok: false,
            httpStatus: res.status,
            stage1Required: false,
            authenticated: false,
            expired: false,
            status: 'idle',
            user_id: '',
            data: data || {},
          };
        }
        if (data && data.session_id && mySid && data.session_id !== mySid) {
          return {
            ok: false,
            httpStatus: res.status,
            stage1Required: false,
            authenticated: false,
            expired: false,
            status: 'mismatch',
            user_id: '',
            data: data,
          };
        }
        var isAuth = Boolean(data && data.authenticated);
        var isExpired = Boolean(data && (data.expired || data.status === 'expired'));
        if (isAuth) {
          syncEptsMetadata(data);
        } else {
          clearEptsMetadata();
        }
        return {
          ok: true,
          httpStatus: res.status,
          stage1Required: false,
          authenticated: isAuth,
          expired: isExpired,
          status: (data && data.status) || 'idle',
          user_id: (data && data.user_id) || '',
          data: data || {},
        };
      } catch (err) {
        return {
          ok: false,
          httpStatus: 0,
          stage1Required: false,
          authenticated: false,
          expired: false,
          status: 'error',
          user_id: '',
          data: { message: err && err.message ? err.message : 'Status check failed' },
        };
      } finally {
        _inFlightVerify = null;
      }
    })();
    return _inFlightVerify;
  }

  async function verifyStage1PortalStatus() {
    try {
      var res = await consoleFetch('/api/auth/portal-status?_ts=' + Date.now(), { cache: 'no-store' });
      if (res.status >= 500) return { authenticated: false, user: null, transientError: true };
      if (!res.ok) {
        clearEptsMetadata();
        return { authenticated: false, user: null };
      }
      var data = await res.json().catch(function () { return {}; });
      if (!data || !data.authenticated || !data.user) {
        clearEptsMetadata();
        return data || { authenticated: false, user: null };
      }
      var loggedUid = String(data.user.user_id || data.user.id || '').trim();
      var lastUid = '';
      try { lastUid = (sessionStorage.getItem('last_console_uid') || '').trim(); } catch (e) {}
      if (loggedUid && lastUid && loggedUid !== lastUid) {
        clearEptsMetadata();
      }
      try { if (loggedUid) sessionStorage.setItem('last_console_uid', loggedUid); } catch (e) {}
      if (data && data.epts_session_id) {
        adoptServerSessionId(data.epts_session_id);
      }
      return data || { authenticated: false, user: null };
    } catch (e) {
      return { authenticated: false, user: null, transientError: true };
    }
  }

  function redirectToConsoleDeptLogin(pendingAction) {
    var saved = savePendingAction(pendingAction || { module: 'dsr', autoGenerate: false });
    var extra = {
      dept_login: '1',
      pending_module: saved ? saved.module : 'dsr',
      auto_generate: (saved && saved.autoGenerate === true) ? '1' : '0',
      reason: saved && saved.reason ? saved.reason : 'required',
    };
    if (saved && saved.params) {
      Object.keys(saved.params).forEach(function (k) {
        var v = saved.params[k];
        if (v !== undefined && v !== null && String(v).trim() !== '' && k !== 'financial_year') {
          extra[k] = String(v).trim();
        }
      });
      if (saved.params.financial_year) extra.fy = String(saved.params.financial_year).trim();
    }
    window.location.href = getConsoleHomeUrl(extra);
  }

  window.DeptSessionManager = {
    getSessionId: getSessionId,
    adoptServerSessionId: adoptServerSessionId,
    isConsoleContext: isConsoleContext,
    isReportsHost: isReportsHost,
    buildScopedUrl: buildScopedUrl,
    getConsoleHomeUrl: getConsoleHomeUrl,
    appendSessionParam: appendSessionParam,
    clearEptsMetadata: clearEptsMetadata,
    syncEptsMetadata: syncEptsMetadata,
    savePendingAction: savePendingAction,
    peekPendingAction: peekPendingAction,
    consumePendingAction: consumePendingAction,
    clearPendingAction: clearPendingAction,
    parsePendingFromUrl: parsePendingFromUrl,
    consoleFetch: consoleFetch,
    verifyStatus: verifyStatus,
    verifyStage1PortalStatus: verifyStage1PortalStatus,
    redirectToConsoleDeptLogin: redirectToConsoleDeptLogin,
  };
})();
