/**
 * Service Worker – El Caracol
 * Estrategia: Cache-First para assets estáticos, Network-First para datos.
 */

const CACHE_NAME = "el-caracol-v2";
const STATIC_ASSETS = [
  "/",
  "/static/logo_caracol.png",
  "/static/manifest.json",
];

// ── Instalación: pre-cachear assets estáticos ─────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// ── Activación: limpiar caches antiguas ───────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: Cache-First para estáticos, Network-First para el resto ────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Solo interceptar peticiones del mismo origen
  if (url.origin !== location.origin) return;

  // No interferir con endpoints internos de Streamlit ni requests no cacheables
  if (url.pathname.startsWith("/_stcore/") || request.method !== "GET") return;

  const isStaticAsset =
    request.destination === "image" ||
    request.destination === "style" ||
    request.destination === "script" ||
    url.pathname.startsWith("/static/");

  if (isStaticAsset) {
    // Cache-First
    event.respondWith(
      caches.match(request).then(
        (cached) => cached || fetch(request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return response;
        })
      )
    );
  } else {
    // Network-First con fallback a caché
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          return response;
        })
        .catch(() => caches.match(request))
    );
  }
});
