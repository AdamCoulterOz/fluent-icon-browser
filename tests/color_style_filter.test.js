const assert = require("node:assert/strict");

const {
    getPreviewVariantForStyleMode,
    hasColorPreservingVariant,
} = require("../script.js");

const azureRegularColour = {
    variants: {
        regular: { preserveSourceColors: true },
        filled: {},
    },
};

assert.equal(hasColorPreservingVariant(azureRegularColour), true);
assert.equal(getPreviewVariantForStyleMode(azureRegularColour, "color"), "regular");

const explicitColorIsPreferred = {
    variants: {
        regular: { preserveSourceColors: true },
        filled: { preserveSourceColors: true },
        color: {},
    },
};

assert.equal(getPreviewVariantForStyleMode(explicitColorIsPreferred, "color"), "color");
assert.equal(getPreviewVariantForStyleMode(explicitColorIsPreferred, "regular"), "regular");
assert.equal(getPreviewVariantForStyleMode(explicitColorIsPreferred, "filled"), "filled");

const monochrome = {
    variants: {
        regular: {},
        filled: {},
    },
};

assert.equal(hasColorPreservingVariant(monochrome), false);
assert.equal(getPreviewVariantForStyleMode(monochrome, "color"), null);

console.log("color_style_filter.test.js: ok");
