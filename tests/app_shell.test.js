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

assert.deepEqual(
    currentFrontendAssets,
    ["keel.css?v=33", "style.css?v=34", "remote-icon-source.js?v=3", "script.js?v=17"]
);

const appShell = readAppShell();
const appShellFrontendAssets = appShell.filter((asset) =>
    /^(?:keel|style)\.css\?v=\d+$|^(?:remote-icon-source|script)\.js\?v=\d+$/.test(asset)
);
assert.deepEqual(appShellFrontendAssets, currentFrontendAssets);

assert.equal(readConstant("CACHE_NAME"), "fluent-icons-v9");
assert.equal(readConstant("ICON_CACHE_NAME"), "fluent-icons-assets-v6");

console.log("app_shell.test.js: ok");
