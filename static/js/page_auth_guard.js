/**
 * page_auth_guard.js - Universal client-side auth guard for module pages.
 * Verifies active Firebase / SSO user session with the platform API.
 * If unauthenticated or expired, redirects to the login screen with return path.
 */
(function () {
  'use strict';

  async function verifySession() {
    try {
      var res = await fetch('/api/auth/portal-status', {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      if (res.ok) {
        var data = await res.json();
        if (data && data.authenticated && data.user) {
          // Officer is authenticated
          return;
        }
      }
    } catch (e) {
      // Network failure or offline mode - do not force redirect
      return;
    }
    // Unauthenticated: redirect to login with original target
    var target = window.location.pathname + window.location.search + window.location.hash;
    window.location.replace('/?auth_required=1&redirect=' + encodeURIComponent(target));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', verifySession);
  } else {
    verifySession();
  }
})();
