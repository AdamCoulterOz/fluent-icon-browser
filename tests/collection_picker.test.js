const assert = require("node:assert/strict");

const { getCollectionPickerOption } = require("../script.js");

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
    getCollectionPickerOption({ label: "Full collection name" }, "full"),
    { text: "Full collection name", title: "Full collection name" }
);

assert.deepEqual(
    getCollectionPickerOption({}, "fallback-key"),
    { text: "fallback-key", title: "fallback-key" }
);

console.log("collection_picker.test.js: ok");
