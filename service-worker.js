const CACHE_NAME = "fluent-icon-browser-v18";
const ICON_CACHE_NAME = "fluent-icons-assets-v8";
const ICON_CACHE_CONCURRENCY = 2;
const APP_SHELL = [
    "./",
    "index.html",
    "keel.css?v=34",
    "style.css?v=37",
    "remote-icon-source.js?v=7",
    "script.js?v=22",
    "icon-data.json",
    "icons/fluent-icons.svg?v=7",
    "icons/fluent-icons-192.png?v=7",
    "icons/fluent-icons-512.png?v=7"
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
    const isRemoteIconAsset =
        url.origin !== self.location.origin &&
        /\.(?:svg|js|json)$/i.test(url.pathname);

    if (isRemoteIconAsset) {
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
    const acceptsOpaqueResponse = request.mode === "no-cors";

    if (cachedResponse && (cachedResponse.type !== "opaque" || acceptsOpaqueResponse)) {
        return cachedResponse;
    }

    const response = await fetch(request);
    if (isCacheableRemoteIconResponse(request, response, acceptsOpaqueResponse)) {
        await cache.put(request, response.clone());
    }
    return response;
}

function isCacheableRemoteIconResponse(request, response, acceptsOpaqueResponse = false) {
    if (response.type === "opaque") {
        return acceptsOpaqueResponse;
    }
    if (!response.ok) {
        return false;
    }

    const pathname = new URL(request.url).pathname.toLowerCase();
    const contentType = response.headers?.get("content-type")?.toLowerCase() || "";
    if (!contentType || !/\.(?:js|json)$/.test(pathname)) {
        return true;
    }
    if (pathname.endsWith(".js")) {
        return /(?:application|text)\/(?:javascript|ecmascript)|application\/x-javascript/.test(contentType);
    }
    return /(?:application|text)\/json|application\/[a-z0-9.+-]+\+json/.test(contentType);
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
                const request = new Request(url, { mode: "cors", credentials: "omit" });
                const cachedResponse = await cache.match(request);
                if (!cachedResponse || cachedResponse.type === "opaque") {
                    const response = await fetch(request);
                    if (!isCacheableRemoteIconResponse(request, response)) {
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
