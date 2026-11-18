/**
 * Panchayat Automation — Progressive Web App (PWA) & Mobile UX Engine
 * Handles app installation prompts (Desktop, Android, iOS Safari), Service Worker registration,
 * and mobile responsiveness enhancements.
 */
(function () {
  'use strict';

  var deferredPrompt = null;
  var isInstalled = false;

  // Check if app is already running in standalone PWA mode
  function checkStandaloneMode() {
    return Boolean(
      window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true ||
      document.referrer.includes('android-app://')
    );
  }

  // Detect iOS Safari
  function isIosSafari() {
    var ua = window.navigator.userAgent;
    var isIos = /iPad|iPhone|iPod/.test(ua) || (window.navigator.platform === 'MacIntel' && window.navigator.maxTouchPoints > 1);
    var isWebview = Boolean(window.navigator.standalone || /CriOS|FxiOS|EdgiOS/.test(ua));
    return isIos && !isWebview;
  }

  // Register Service Worker
  function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function () {
        navigator.serviceWorker.register('/sw.js', { scope: '/' })
          .then(function (reg) {
            console.log('[PWA] Service Worker registered with scope:', reg.scope);
          })
          .catch(function (err) {
            console.warn('[PWA] Service Worker registration failed:', err);
          });
      });
    }
  }

  // Update UI when installable or installed
  function updateInstallUI() {
    var ribbonBtn = document.getElementById('ribbon-btn-install');
    var drawerSection = document.getElementById('mobile-drawer-install-section');
    var drawerBtn = document.getElementById('mobile-drawer-install-btn');
    var drawerBadge = document.getElementById('mobile-install-badge-text');
    var floatingBanner = document.getElementById('pwa-floating-banner');

    if (isInstalled) {
      if (ribbonBtn) {
        ribbonBtn.style.display = 'inline-flex';
        ribbonBtn.innerHTML = '<span>✅</span> <span>Installed</span>';
        ribbonBtn.classList.add('installed');
        ribbonBtn.title = 'Panchayat Automation is installed on this device';
      }
      if (drawerBadge) {
        drawerBadge.textContent = 'INSTALLED';
        drawerBadge.style.background = '#059669';
        drawerBadge.style.color = '#ffffff';
      }
      if (floatingBanner) {
        floatingBanner.style.display = 'none';
      }
      return;
    }

    // If installable or iOS
    if (deferredPrompt || isIosSafari()) {
      if (ribbonBtn) ribbonBtn.style.display = 'inline-flex';
      if (drawerSection) drawerSection.style.display = 'block';

      // Check if floating banner was dismissed in the last 7 days
      var dismissedTime = localStorage.getItem('pwa_banner_dismissed_time');
      var now = Date.now();
      var oneWeek = 7 * 24 * 60 * 60 * 1000;
      var isDismissedRecent = dismissedTime && (now - Number(dismissedTime) < oneWeek);

      // Only show floating banner on mobile screens if not dismissed recently
      if (floatingBanner && !isDismissedRecent && window.innerWidth <= 860) {
        // Small delay so page loads cleanly before banner slides up
        setTimeout(function () {
          floatingBanner.style.display = 'flex';
          floatingBanner.classList.add('pwa-banner-visible');
        }, 2200);
      }
    } else {
      // In other desktop browsers without prompt, keep button visible so user can click for browser menu instructions
      if (ribbonBtn) ribbonBtn.style.display = 'inline-flex';
      if (drawerSection) drawerSection.style.display = 'block';
    }
  }

  // Trigger PWA Installation
  window.triggerPwaInstall = function () {
    if (isInstalled) {
      if (window.showPortalNotice) {
        window.showPortalNotice('Panchayat Automation is already installed on your device!', 'info');
      } else {
        alert('Panchayat Automation is already installed on your device!');
      }
      return;
    }

    if (deferredPrompt) {
      // Native Chrome/Edge/Android install prompt
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function (choiceResult) {
        if (choiceResult.outcome === 'accepted') {
          console.log('[PWA] User accepted the installation prompt');
          isInstalled = true;
          updateInstallUI();
          if (window.showPortalNotice) {
            window.showPortalNotice('Installing Panchayat Automation to your device...', 'success');
          }
        } else {
          console.log('[PWA] User dismissed the installation prompt');
        }
        deferredPrompt = null;
      });
      return;
    }

    if (isIosSafari()) {
      // Show iOS step-by-step guidance modal
      window.openIosInstallModal();
      return;
    }

    // Fallback for browsers that don't support beforeinstallprompt
    var msg = 'To install Panchayat Automation: tap your browser menu (⋮ or ⋯) and select "Install app" or "Add to Home Screen".';
    if (window.showPortalNotice) {
      window.showPortalNotice(msg, 'info', 8000);
    } else {
      alert(msg);
    }
  };

  // Floating Banner Dismiss
  window.dismissPwaBanner = function () {
    var banner = document.getElementById('pwa-floating-banner');
    if (banner) {
      banner.style.display = 'none';
      banner.classList.remove('pwa-banner-visible');
    }
    localStorage.setItem('pwa_banner_dismissed_time', String(Date.now()));
  };

  // iOS Safari Modal Controls
  window.openIosInstallModal = function () {
    var modal = document.getElementById('pwa-ios-modal');
    if (modal) {
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  };

  window.closeIosInstallModal = function () {
    var modal = document.getElementById('pwa-ios-modal');
    if (modal) {
      modal.style.display = 'none';
      document.body.style.overflow = '';
    }
  };

  // Initialize PWA Listeners
  function initPwa() {
    isInstalled = checkStandaloneMode();
    registerServiceWorker();

    // Listen for beforeinstallprompt
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferredPrompt = e;
      console.log('[PWA] beforeinstallprompt captured');
      updateInstallUI();
    });

    // Listen for appinstalled
    window.addEventListener('appinstalled', function () {
      console.log('[PWA] Panchayat Automation was successfully installed!');
      isInstalled = true;
      deferredPrompt = null;
      updateInstallUI();
      window.dismissPwaBanner();
      if (window.showPortalNotice) {
        window.showPortalNotice('✓ Panchayat Automation installed successfully!', 'success');
      }
    });

    // Initial check
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', updateInstallUI);
    } else {
      updateInstallUI();
    }
  }

  // Mobile Responsiveness Enhancements (Tables, Viewport, Touch)
  function initMobileEnhancements() {
    // 1. Table Touch Scroll Hints
    function checkTableOverflows() {
      var tableWraps = document.querySelectorAll('.table-responsive, .md-table-wrap, .table-wrap, .dataTables_wrapper');
      tableWraps.forEach(function (wrap) {
        if (wrap.scrollWidth > wrap.clientWidth + 15) {
          wrap.classList.add('has-horizontal-overflow');
        } else {
          wrap.classList.remove('has-horizontal-overflow');
        }
      });
    }

    window.addEventListener('resize', checkTableOverflows);
    setTimeout(checkTableOverflows, 1000);

    // 2. Touch Active Feedback for mobile elements
    document.addEventListener('touchstart', function () {}, { passive: true });
  }

  // Start PWA and Mobile UX
  initPwa();
  initMobileEnhancements();
})();
