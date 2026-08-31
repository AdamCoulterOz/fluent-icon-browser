const assert = require("node:assert/strict");

const {
    getCollectionPickerOption,
    previewSurfaceClass,
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

assert.equal(previewSurfaceClass({ previewSurface: "contrast" }), "preview-surface-contrast");
assert.equal(previewSurfaceClass({ previewSurface: "default" }), "");
assert.equal(previewSurfaceClass({}), "");

assert.deepEqual(
    getCollectionPickerOption({ label: "Full collection name" }, "full"),
    { text: "Full collection name", title: "Full collection name" }
);

assert.deepEqual(
    getCollectionPickerOption({}, "fallback-key"),
    { text: "fallback-key", title: "fallback-key" }
);

console.log("collection_picker.test.js: ok");
