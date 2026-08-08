const CACHE_NAME = "fluent-icons-v1";
const ICON_CACHE_NAME = "fluent-icons-assets-v1";
const ICON_CACHE_CONCURRENCY = 60;
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

self.addEventListener("message", (event) => {
    if (event.data?.type !== "cache-icons" || !Array.isArray(event.data.urls)) {
        return;
    }

    event.waitUntil(cacheIconAssets(event.data.urls, event.ports[0]));
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
    }
    return response;
}

async function cacheIconAssets(urls, statusPort) {
    const cache = await caches.open(ICON_CACHE_NAME);
    const uniqueUrls = [...new Set(urls)];
    const total = uniqueUrls.length;
    let nextIndex = 0;
    let completed = 0;
    let failed = 0;

    const reportProgress = (complete = false) => {
        if (complete || completed % 25 === 0) {
            statusPort?.postMessage({
                type: complete ? "icon-cache-complete" : "icon-cache-progress",
                completed,
                total,
                failed
            });
        }
    };

    const worker = async () => {
        while (nextIndex < total) {
            const url = uniqueUrls[nextIndex];
            nextIndex += 1;

            try {
                const request = new Request(url);
                if (!await cache.match(request)) {
                    const response = await fetch(request);
                    if (!response.ok && response.type !== "opaque") {
                        throw new Error(`Failed to fetch ${url}`);
                    }
                    await cache.put(request, response);
                }
            } catch (error) {
                failed += 1;
            } finally {
                completed += 1;
                reportProgress();
            }
        }
    };

    await Promise.all(Array.from({ length: Math.min(ICON_CACHE_CONCURRENCY, total) }, worker));
    reportProgress(true);
}