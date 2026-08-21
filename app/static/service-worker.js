const CACHE_NAME = "salahmate-v1";

const STATIC_ASSETS = [
    "/static/images/icon-192.png",
    "/static/images/icon-512.png"
];

// Install service worker
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );

    self.skipWaiting();
});

// Activate service worker
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((cacheName) => cacheName !== CACHE_NAME)
                    .map((cacheName) => caches.delete(cacheName))
            );
        })
    );

    self.clients.claim();
});

// Fetch requests
self.addEventListener("fetch", (event) => {
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});