const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const repositoryRoot = path.resolve(__dirname, "..");
const indexHtml = fs.readFileSync(path.join(repositoryRoot, "index.html"), "utf8");
const serviceWorker = fs.readFileSync(path.join(repositoryRoot, "service-worker.js"), "utf8");

function readConstant(name) {
    const match = serviceWorker.match(new RegExp(`const ${name} = "([^"]+)";`));
    assert.ok(match, `${name} should be declared`);
    return match[1];
}

function readAppShell() {
    const match = serviceWorker.match(/const APP_SHELL = (\[[\s\S]*?\n\]);/);
    assert.ok(match, "APP_SHELL should be declared as a static array");
    return JSON.parse(match[1]);
}

const currentFrontendAssets = [
    ...indexHtml.matchAll(/<(?:link|script)\b[^>]+(?:href|src)="((?:keel|style)\.css\?v=\d+|(?:remote-icon-source|script)\.js\?v=\d+)"/g),
].map((match) => match[1]);

assert.match(
    indexHtml,
    /<label class="sr-only" for="iconSetSelect">Icon collection<\/label>\s*<select id="iconSetSelect" aria-describedby="setSubtitle"><\/select>\s*<span class="keel-select__chev" aria-hidden="true">\s*<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1\.5" stroke-linecap="round" stroke-linejoin="round" focusable="false">/
);
assert.match(indexHtml, /class="icon-set-picker keel-select keel-select--sm"/);
assert.match(
    indexHtml,
    /<div class="icon-group-picker keel-select keel-select--sm" id="iconGroupPicker" hidden>\s*<label class="sr-only" for="iconGroupSelect">Icon group<\/label>\s*<select id="iconGroupSelect" aria-describedby="setSubtitle"><\/select>\s*<span class="keel-select__chev" aria-hidden="true">/
);

assert.deepEqual(
    currentFrontendAssets,
    ["keel.css?v=34", "style.css?v=38", "remote-icon-source.js?v=7", "script.js?v=23"]
);

const appShell = readAppShell();
assert.deepEqual(appShell, [
    "./",
    "index.html",
    "keel.css?v=34",
    "style.css?v=38",
    "remote-icon-source.js?v=7",
    "script.js?v=23",
    "icon-data.json",
    "icons/fluent-icons.svg?v=7",
    "icons/fluent-icons-192.png?v=7",
    "icons/fluent-icons-512.png?v=7"
]);
assert.deepEqual(
    appShell.filter((asset) =>
        /^(?:keel|style)\.css\?v=\d+$|^(?:remote-icon-source|script)\.js\?v=\d+$/.test(asset)
    ),
    currentFrontendAssets
);

assert.equal(readConstant("CACHE_NAME"), "fluent-icon-browser-v20");
assert.equal(readConstant("ICON_CACHE_NAME"), "fluent-icons-assets-v8");

console.log("app_shell.test.js: ok");
