const assert = require("node:assert/strict");
const crypto = require("node:crypto").webcrypto;

const {
    RemoteIconSourceResolver,
    decodeJsonPointer,
    extractAmdSvgModule,
    extractJsonPointerSvg,
    normalizeSafeStyleDeclarations,
    sanitizeSvg,
} = require("../remote-icon-source.js");

async function sha256Hex(text) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Buffer.from(digest).toString("hex");
}

function createFakeSvgElement(localName, attributes = {}) {
    const attributeValues = new Map(Object.entries(attributes));
    return {
        localName,
        get attributes() {
            return [...attributeValues].map(([name, value]) => ({ name, value }));
        },
        getAttribute(name) {
            return attributeValues.get(name);
        },
        removeAttribute(name) {
            attributeValues.delete(name);
        },
        setAttribute(name, value) {
            attributeValues.set(name, String(value));
        },
    };
}

function sanitizeWithFakeSvgDom(root) {
    const originalXmlSerializer = global.XMLSerializer;
    global.XMLSerializer = class {
        serializeToString() {
            return "<svg/>";
        }
    };
    try {
        return sanitizeSvg("<svg/>", {
            parseFromString() {
                return {
                    documentElement: root,
                    querySelector: () => null,
                };
            },
        });
    } finally {
        if (originalXmlSerializer === undefined) {
            delete global.XMLSerializer;
        } else {
            global.XMLSerializer = originalXmlSerializer;
        }
    }
}

async function run() {
    assert.deepEqual(
        normalizeSafeStyleDeclarations("fill: #0078d4 !important; stroke: #00188f; stroke-width: 1.5"),
        [["fill", "#0078d4"], ["stroke", "#00188f"], ["stroke-width", "1.5"]]
    );
    assert.deepEqual(
        normalizeSafeStyleDeclarations("fill: url(#azureGradient); stop-color: #00a4ef"),
        [["fill", "url(#azureGradient)"], ["stop-color", "#00a4ef"]]
    );
    assert.deepEqual(
        normalizeSafeStyleDeclarations("display: none; visibility: hidden; opacity: .35"),
        [["display", "none"], ["visibility", "hidden"], ["opacity", ".35"]]
    );
    assert.deepEqual(
        normalizeSafeStyleDeclarations("fill: #0078d4; filter: url(#blur); stroke: url(https://example.test/paint); color: #fff"),
        [["fill", "#0078d4"], ["color", "#fff"]]
    );
    assert.deepEqual(
        normalizeSafeStyleDeclarations("fill: url(data:image/svg+xml,unsafe); stroke: url(javascript:alert(1)); fill-opacity: .5"),
        [["fill-opacity", ".5"]]
    );
    assert.deepEqual(
        normalizeSafeStyleDeclarations("fill: red !important; fill: blue; stroke: black; stroke: white !important"),
        [["fill", "red"], ["stroke", "white"]]
    );

    const root = createFakeSvgElement("svg", {
        style: "display: none; visibility: hidden",
    });
    const styledPath = createFakeSvgElement("path", {
        style: "fill: #0078d4; stroke: url(#azureGradient); filter: url(#blur); stroke-width: 1.5",
    });
    const unsafePaintPath = createFakeSvgElement("path", {
        style: "fill: url(https://example.test/paint); stroke: url(data:image/svg+xml,unsafe); fill-opacity: .5",
    });
    const mixedUrlPath = createFakeSvgElement("path", {
        fill: "url(#azureGradient) url(https://example.test/paint)",
        stroke: "url(#azureGradient)",
    });
    root.querySelectorAll = () => [styledPath, unsafePaintPath, mixedUrlPath];
    sanitizeWithFakeSvgDom(root);
    assert.equal(root.getAttribute("style"), undefined);
    assert.equal(root.getAttribute("display"), "none");
    assert.equal(root.getAttribute("visibility"), "hidden");
    assert.equal(styledPath.getAttribute("style"), undefined);
    assert.equal(styledPath.getAttribute("fill"), "#0078d4");
    assert.equal(styledPath.getAttribute("stroke"), "url(#azureGradient)");
    assert.equal(styledPath.getAttribute("stroke-width"), "1.5");
    assert.equal(styledPath.getAttribute("filter"), undefined);
    assert.equal(unsafePaintPath.getAttribute("style"), undefined);
    assert.equal(unsafePaintPath.getAttribute("fill"), undefined);
    assert.equal(unsafePaintPath.getAttribute("stroke"), undefined);
    assert.equal(unsafePaintPath.getAttribute("fill-opacity"), ".5");
    assert.equal(mixedUrlPath.getAttribute("fill"), undefined);
    assert.equal(mixedUrlPath.getAttribute("stroke"), "url(#azureGradient)");

    const amdSource = [
        '// define("portal/icons/azure~logo", [], function () { return "<svg/>"; });',
        'define("portal/icons/azure~logo", [], function () {',
        '    return "\\u003csvg viewBox=\\\"0 0 24 24\\\"\\u003e\\u003cpath d=\\\"M0 0h24v24H0z\\\"/\\u003e\\u003c/svg\\u003e";',
        "});",
    ].join("\n");
    const expectedSvg = '<svg viewBox="0 0 24 24"><path d="M0 0h24v24H0z"/></svg>';

    assert.equal(
        extractAmdSvgModule(amdSource, "portal/icons/azure~logo"),
        expectedSvg
    );
    assert.throws(
        () => extractAmdSvgModule('define("portal/icons/azure", [], function () { return makeSvg(); });', "portal/icons/azure"),
        /exactly one static SVG string value/i
    );
    assert.equal(
        extractAmdSvgModule(
            'define("_generated/MsPortalImpl/Svg/Library/Cloud.svg", ["require", "exports"], function (require, exports) { exports.data = "<svg><path/></svg>"; });',
            "_generated/MsPortalImpl/Svg/Library/Cloud.svg"
        ),
        "<svg><path/></svg>"
    );
    assert.equal(
        extractAmdSvgModule(
            [
                'define("unrelated", [], function () { const confusingRegex = /[(]/; return "not an SVG"; });',
                'define("_generated/MsPortalImpl/Svg/Library/Target.svg", ["require", "exports"], function (require, exports) { exports.data = "<svg><path/></svg>"; });',
            ].join("\n"),
            "_generated/MsPortalImpl/Svg/Library/Target.svg"
        ),
        "<svg><path/></svg>"
    );
    assert.equal(
        extractAmdSvgModule(
            [
                'const decoy = \'define("_generated/MsPortalImpl/Svg/Library/Target.svg", [], function () { return "<svg/>"; });\';',
                'define("_generated/MsPortalImpl/Svg/Library/Target.svg", ["require", "exports"], function (require, exports) { exports.data = "<svg><path/></svg>"; });',
            ].join("\n"),
            "_generated/MsPortalImpl/Svg/Library/Target.svg"
        ),
        "<svg><path/></svg>"
    );

    const jsonSource = JSON.stringify({
        icons: {
            "azure/logo": {
                "~default": expectedSvg,
            },
        },
    });
    assert.deepEqual(decodeJsonPointer("/icons/azure~1logo/~0default"), ["icons", "azure/logo", "~default"]);
    assert.equal(
        extractJsonPointerSvg(jsonSource, "/icons/azure~1logo/~0default"),
        expectedSvg
    );
    assert.throws(() => decodeJsonPointer("/icons/~2bad"), /invalid escape/i);

    let fetchCount = 0;
    const resolver = new RemoteIconSourceResolver({
        crypto,
        sanitize: (svg) => svg,
        canonicalize: (svg) => svg,
        fetch: async (url) => {
            fetchCount += 1;
            assert.equal(url, "https://example.test/portal-bundle.js");
            return { ok: true, status: 200, text: async () => amdSource };
        },
    });
    const descriptor = {
        url: "https://example.test/portal-bundle.js",
        format: "portal-amd-svg-module",
        selector: "portal/icons/azure~logo",
        sha256: await sha256Hex(expectedSvg),
    };
    const secondDescriptor = {
        ...descriptor,
        selector: "portal/icons/missing",
    };

    assert.equal(await resolver.resolve(descriptor), expectedSvg);
    await assert.rejects(() => resolver.resolve(secondDescriptor), /was not found/i);
    assert.equal(fetchCount, 1);
    await assert.rejects(
        () => resolver.resolve({ ...descriptor, sha256: "0".repeat(64) }),
        /SHA-256 does not match/i
    );

    const alteredSvg = expectedSvg.replace("<path", "<script>ignore()</script><path");
    const alteredSource = `define("portal/icons/azure~logo", [], function () { return ${JSON.stringify(alteredSvg)}; });`;
    const sanitizerThatRemovesScript = (svg) => svg.replace(/<script[^>]*>[\s\S]*?<\/script>/i, "");
    assert.equal(sanitizerThatRemovesScript(alteredSvg), expectedSvg);
    const integrityResolver = new RemoteIconSourceResolver({
        crypto,
        canonicalize: (svg) => svg,
        sanitize: sanitizerThatRemovesScript,
        fetch: async () => ({ ok: true, status: 200, text: async () => alteredSource }),
    });
    await assert.rejects(
        () => integrityResolver.resolve(descriptor),
        /SHA-256 does not match/i
    );

    let htmlFetchCount = 0;
    const htmlThenSourceResolver = new RemoteIconSourceResolver({
        crypto,
        canonicalize: (svg) => svg,
        sanitize: (svg) => svg,
        fetch: async () => {
            htmlFetchCount += 1;
            if (htmlFetchCount === 1) {
                return {
                    ok: true,
                    status: 200,
                    headers: { get: () => "text/html; charset=utf-8" },
                    text: async () => "<html>request is blocked</html>",
                };
            }
            return { ok: true, status: 200, text: async () => amdSource };
        },
    });
    await assert.rejects(
        () => htmlThenSourceResolver.resolve(descriptor),
        /returned HTML/i
    );
    assert.equal(await htmlThenSourceResolver.resolve(descriptor), expectedSvg);
    assert.equal(htmlFetchCount, 2);

    const portalSvg = '<svg viewBox="0 0 16 16"><path d="M0 0h16v16H0z"/></svg>';
    const portalSource = `define("_generated/MsPortalImpl/Svg/Library/Cloud.svg", ["require", "exports"], function (require, exports) { exports.data = ${JSON.stringify(portalSvg)}; });`;
    const portalResolver = new RemoteIconSourceResolver({
        crypto,
        sanitize: (svg) => svg,
        canonicalize: (svg) => svg.replace("/>", "></path>"),
        fetch: async () => ({ ok: true, status: 200, text: async () => portalSource }),
    });
    assert.equal(
        await portalResolver.resolve({
            url: "https://example.test/portal-azure.js",
            format: "portal-amd-svg-module",
            selector: "_generated/MsPortalImpl/Svg/Library/Cloud.svg",
            sha256: await sha256Hex(portalSvg.replace("/>", "></path>")),
        }),
        portalSvg
    );

    let retryFetchCount = 0;
    const retryResolver = new RemoteIconSourceResolver({
        crypto,
        sanitize: (svg) => svg,
        canonicalize: (svg) => svg,
        fetch: async () => {
            retryFetchCount += 1;
            if (retryFetchCount === 1) {
                throw new Error("temporary network failure");
            }
            return { ok: true, status: 200, text: async () => amdSource };
        },
    });
    await assert.rejects(() => retryResolver.resolve(descriptor), /temporary network failure/i);
    assert.equal(await retryResolver.resolve(descriptor), expectedSvg);
    assert.equal(retryFetchCount, 2);
}

run().then(
    () => console.log("remote_icon_source.test.js: ok"),
    (error) => {
        console.error(error);
        process.exitCode = 1;
    }
);
