const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const serviceWorker = fs.readFileSync(path.join(__dirname, "..", "service-worker.js"), "utf8");
const listeners = new Map();
const cacheOpens = [];
const fetchCalls = [];

const response = {
    ok: true,
    type: "basic",
    clone() {
        return this;
    },
    headers: {
        get() {
            return "image/svg+xml";
        },
    },
};

const context = {
    URL,
    Promise,
    console,
    caches: {
        async open(name) {
            cacheOpens.push(name);
            return {
                async match() {
                    return undefined;
                },
                async put() {},
            };
        },
        async keys() {
            return [];
        },
        async delete() {},
    },
    fetch: async (request) => {
        fetchCalls.push(request);
        return response;
    },
    self: {
        location: { origin: "https://icons.example.test" },
        addEventListener(type, listener) {
            listeners.set(type, listener);
        },
        skipWaiting() {},
        clients: { claim() {} },
    },
};

vm.runInNewContext(serviceWorker, context, { filename: "service-worker.js" });

async function dispatchFetch(request) {
    let responsePromise;
    listeners.get("fetch")({
        request,
        respondWith(value) {
            assert.equal(responsePromise, undefined, "fetch route should respond once");
            responsePromise = Promise.resolve(value);
        },
    });
    if (responsePromise) {
        await responsePromise;
    }
    return responsePromise;
}

async function run() {
    const remoteResolverRequest = {
        method: "GET",
        url: "https://portal.azure.com/Content/Dynamic/C1EB1JWhknQ2.js",
        mode: "cors",
        credentials: "omit",
        destination: "",
    };
    assert.equal(await dispatchFetch(remoteResolverRequest), undefined);
    assert.deepEqual(cacheOpens, []);
    assert.deepEqual(fetchCalls, []);

    const remoteArchiveRequest = {
        ...remoteResolverRequest,
        url: "https://registry.npmjs.org/@salesforce-ux/icons/-/icons-10.17.0.tgz",
    };
    assert.equal(await dispatchFetch(remoteArchiveRequest), undefined);
    assert.deepEqual(cacheOpens, []);
    assert.deepEqual(fetchCalls, []);

    await dispatchFetch({
        ...remoteResolverRequest,
        url: "https://icons.example.test/gcp-console-icons.zip",
    });
    assert.deepEqual(cacheOpens, ["fluent-icon-browser-v23"]);
    assert.equal(fetchCalls.length, 1);

    cacheOpens.length = 0;
    fetchCalls.length = 0;
    await dispatchFetch({
        method: "GET",
        url: "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/Add/SVG/ic_fluent_add_24_regular.svg",
        mode: "no-cors",
        credentials: "same-origin",
        destination: "image",
    });
    assert.deepEqual(cacheOpens, ["fluent-icons-assets-v8"]);
    assert.equal(fetchCalls.length, 1);

    console.log("service_worker_fetch.test.js: ok");
}

run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
