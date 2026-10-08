/**
 * Service Worker de StrikeHub: hace instalable la app (requisito para
 * `beforeinstallprompt`) y da un respaldo sin conexión.
 *
 * Estrategia:
 * - App shell (HTML/CSS/JS/logo/iconos): cache-first, precacheado al instalar.
 * - /api/*: network-first (los marcadores nunca deben salir rancios);
 *   si no hay red, se sirve lo último guardado.
 * - Navegación sin red: cae a index.html cacheado.
 *
 * Al desplegar con cambios en dist/*, sube CACHE_VERSION (mismo número
 * que el ?v= de index.html) para que los clientes tomen lo nuevo.
 */
const CACHE_VERSION = '20261016';
const CACHE = `strikehub-v${CACHE_VERSION}`;

const SHELL = [
  './',
  'index.html',
  'manifest.json',
  'dist/app.bundle.min.js',
  'dist/styles.min.css',
  'assets/logos/strikehub-logo.svg',
  'assets/icons/icon-192.png',
  'assets/icons/icon-512.png',
  'assets/icons/favicon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.pathname.includes('/api/')) {
    // API: red primero, caché como respaldo sin conexión.
    event.respondWith(
      fetch(request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return res;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Estáticos: caché primero.
  event.respondWith(
    caches.match(request).then((hit) => {
      if (hit) return hit;
      return fetch(request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return res;
      }).catch(() => {
        if (request.mode === 'navigate') return caches.match('index.html');
        throw new Error('offline');
      });
    })
  );
});
