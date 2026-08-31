const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const {
    getCollectionPickerOption,
    isThemeColorPaint,
    previewThemeColorClass,
    sourceAllowsTransform,
} = require("../script.js");

assert.deepEqual(
    getCollectionPickerOption(
        {
            shortLabel: "Flight",
            label: "HashiCorp Flight Icons",
            source: "HashiCorp Flight Icons",
        },
        "flight"
    ),
    { text: "Flight", title: "HashiCorp Flight Icons" }
);

assert.deepEqual(
    getCollectionPickerOption(
        { shortLabel: "Salesforce", label: "Salesforce SLDS Icons" },
        "salesforce"
    ),
    { text: "Salesforce", title: "Salesforce SLDS Icons" }
);

assert.equal(
    sourceAllowsTransform(
        { sourceCapabilities: { currentColor: false, boundingBox: false } },
        "currentColor"
    ),
    false
);
assert.equal(sourceAllowsTransform({}, "boundingBox"), true);

assert.equal(previewThemeColorClass({ previewThemeColor: true }), "preview-theme-color");
assert.equal(previewThemeColorClass({ previewThemeColor: false }), "");
assert.equal(previewThemeColorClass({}), "");
assert.equal(isThemeColorPaint("#fff"), true);
assert.equal(isThemeColorPaint("rgb(0, 0, 0)"), true);
assert.equal(isThemeColorPaint("#0176d3"), false);

const styleSheet = fs.readFileSync(path.join(__dirname, "..", "style.css"), "utf8");
const browserScript = fs.readFileSync(path.join(__dirname, "..", "script.js"), "utf8");
assert.doesNotMatch(styleSheet, /preview-surface-contrast/);
assert.match(styleSheet, /\.icon-view\.preview-theme-color\s*\{\s*color: #000;\s*\}/);
assert.match(styleSheet, /\.icon-view\.preview-theme-color img\s*\{\s*filter: brightness\(0\);\s*\}/);
assert.match(styleSheet, /@media \(prefers-color-scheme: dark\)[\s\S]*?\.icon-view\.preview-theme-color\s*\{\s*color: #fff;\s*\}/);
assert.match(styleSheet, /@media \(prefers-color-scheme: dark\)[\s\S]*?\.icon-view\.preview-theme-color img\s*\{\s*filter: brightness\(0\) invert\(1\);\s*\}/);
assert.match(styleSheet, /\.icon-view\.has-color-variant\.preview-theme-color img\s*\{\s*filter: brightness\(0\) invert\(1\) !important;\s*\}/);
assert.doesNotMatch(styleSheet, /preview-theme-color[^}]*background:/);
assert.doesNotMatch(browserScript.slice(browserScript.indexOf("async function copyToClipboard")), /applyPreviewThemeColor/);

assert.deepEqual(
    getCollectionPickerOption({ label: "Full collection name" }, "full"),
    { text: "Full collection name", title: "Full collection name" }
);

assert.deepEqual(
    getCollectionPickerOption({}, "fallback-key"),
    { text: "fallback-key", title: "fallback-key" }
);

console.log("collection_picker.test.js: ok");
