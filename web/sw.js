/* Skippy demo SW — caches only the static shell for installability.
 * Never caches /api/*, /config.js, /clips, /sprites — those stay live. */
const CACHE = 'skippy-demo-v1';
const SHELL = ['/', '/app.js', '/style.css', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/') || url.pathname === '/config.js' ||
      url.pathname.startsWith('/clips/') || url.pathname.startsWith('/sprites/')) return;
  if (!SHELL.includes(url.pathname)) return;
  e.respondWith(
    fetch(e.request).then(resp => { const c = resp.clone(); caches.open(CACHE).then(x => x.put(e.request, c)).catch(() => {}); return resp; })
      .catch(() => caches.match(e.request))
  );
});
