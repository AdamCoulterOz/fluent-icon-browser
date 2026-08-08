const CACHE_NAME = "fluent-icons-v1";
const ICON_CACHE_NAME = "fluent-icons-assets-v1";
const ICON_CACHE_LIMIT = 200;
const APP_SHELL = [
    "./",
    "index.html",
    "style.css",
    "script.js",
    "icon-data.json",
    "icons/fluent-icons-192.png",
    "icons/fluent-icons-512.png"
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => Promise.all(
            cacheNames
                .filter((cacheName) => cacheName !== CACHE_NAME && cacheName !== ICON_CACHE_NAME)
                .map((cacheName) => caches.delete(cacheName))
        ))
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }

    const url = new URL(event.request.url);
    const isRemoteSvg = url.origin !== self.location.origin && url.pathname.endsWith(".svg");

    if (isRemoteSvg) {
        event.respondWith(cacheIconAsset(event.request));
        return;
    }

    event.respondWith(cacheAppAsset(event.request));
});

async function cacheAppAsset(request) {
    const cache = await caches.open(CACHE_NAME);

    try {
        const response = await fetch(request);
        if (response.ok) {
            await cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        throw error;
    }
}

async function cacheIconAsset(request) {
    const cache = await caches.open(ICON_CACHE_NAME);
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }

    const response = await fetch(request);
    if (response.ok || response.type === "opaque") {
        await cache.put(request, response.clone());
        const keys = await cache.keys();
        if (keys.length > ICON_CACHE_LIMIT) {
            await cache.delete(keys[0]);
        }
    }
    return response;
}