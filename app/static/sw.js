/* COSMIX offline shell — caches static assets only; API calls stay uncached. */
const CACHE_NAME = "cosmix-shell-v1";

const SHELL_ASSETS = [
  "/",
  "/styles.css",
  "/app.js",
  "/analyze.js",
  "/depth.js",
  "/pwa.js",
  "/manifest.json",
  "/icons/icon.svg",
  "/icons/icon-maskable.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/")) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        if (!response || response.status !== 200 || response.type !== "basic") {
          return response;
        }
        const clone = response.clone();
        const path = url.pathname;
        if (
          path.endsWith(".css") ||
          path.endsWith(".js") ||
          path.endsWith(".json") ||
          path.endsWith(".svg") ||
          path === "/" ||
          path.endsWith(".html")
        ) {
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone)).catch(() => {});
        }
        return response;
      });
    }),
  );
});
