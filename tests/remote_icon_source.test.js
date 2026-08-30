const assert = require("node:assert/strict");
const crypto = require("node:crypto").webcrypto;

const {
    RemoteIconSourceResolver,
    decodeJsonPointer,
    extractAmdSvgModule,
    extractJsonPointerSvg,
} = require("../remote-icon-source.js");

async function sha256Hex(text) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Buffer.from(digest).toString("hex");
}

async function run() {
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
