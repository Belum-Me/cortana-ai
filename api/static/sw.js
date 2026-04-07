const CACHE = "cortana-v1";
const ASSETS = ["/", "/static/manifest.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener("fetch", e => {
  if (e.request.url.includes("/chat") || e.request.url.includes("/health")) return;
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
