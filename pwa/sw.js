// Device Portal service worker: cache the app shell only.
// Device API calls are never cached.
const CACHE = 'device-portal-v1';
const SHELL = ['index.html', 'app.js', 'manifest.webmanifest'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(() => {}));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/status') || url.pathname.startsWith('/command') ||
      url.pathname.startsWith('/audit') || url.pathname.startsWith('/pair') ||
      url.pathname.startsWith('/approve') || url.pathname.startsWith('/kill')) return;
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
