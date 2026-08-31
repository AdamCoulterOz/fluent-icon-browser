const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
    getIconCacheUrls,
    getInitialIconCacheUrls,
} = require("../script.js");

const repositoryRoot = path.resolve(__dirname, "..");
const serviceWorker = fs.readFileSync(path.join(repositoryRoot, "service-worker.js"), "utf8");

const catalog = {
    icons: Array.from({ length: 100 }, (_, index) => ({
        asset: `https://assets.example.test/icons/${index}.svg`,
    })),
    duplicate: "https://assets.example.test/icons/0.svg",
    remoteSource: {
        url: "https://assets.example.test/descriptors/not-an-icon.svg",
    },
};

const urls = getIconCacheUrls(catalog);
assert.equal(urls.length, 100);
assert.equal(urls[0], "https://assets.example.test/icons/0.svg");
assert.equal(urls[99], "https://assets.example.test/icons/99.svg");
assert.deepEqual(getInitialIconCacheUrls(catalog), urls.slice(0, 96));

const concurrency = serviceWorker.match(/const ICON_CACHE_CONCURRENCY = (\d+);/);
assert.ok(concurrency, "service worker should declare icon-cache concurrency");
assert.equal(Number(concurrency[1]), 2);

console.log("icon_cache_warming.test.js: ok");
