// Panchayat Automation Service Worker (PWA)
const CACHE_NAME = 'panchayat-pwa-v2';
const PRECACHE_ASSETS = [
  '/',
  '/static/css/common.css?v=17',
  '/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/favicon-32x32.png',
  '/favicon.ico'
];

// Install: Cache essential app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[PWA ServiceWorker] Precaching app shell assets');
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('[PWA ServiceWorker] Precache warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean up previous caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[PWA ServiceWorker] Removing old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Network-first for navigation/pages, Cache-first for static assets
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Bypass non-GET requests and dynamic API calls
  if (req.method !== 'GET' || url.pathname.startsWith('/api/') || url.pathname.includes('/download')) {
    return;
  }

  // Static assets: Cache-first with network fallback
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) {
          // Fetch updated version in background to keep cache fresh
          fetch(req).then((res) => {
            if (res && res.status === 200) {
              caches.open(CACHE_NAME).then((c) => c.put(req, res));
            }
          }).catch(() => {});
          return cached;
        }
        return fetch(req).then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(req, clone));
          }
          return res;
        });
      })
    );
    return;
  }

  // HTML Page Navigation: Network-first with cache fallback
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then((res) => {
        if (res && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(req, clone));
        }
        return res;
      }).catch(() => {
        return caches.match(req).then((cached) => {
          if (cached) return cached;
          return caches.match('/');
        });
      })
    );
  }
});
