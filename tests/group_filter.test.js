const assert = require("node:assert/strict");

const {
    getIconGroupFilterState,
    getIconGroupOptions,
    matchesIconGroup,
} = require("../script.js");

const categorizedIcons = [
    { name: "alpha", category: "Status" },
    { name: "beta", category: "User" },
    { name: "gamma", category: "Status" },
    { name: "blank", category: " " },
    { name: "missing" },
];

assert.deepEqual(getIconGroupOptions(categorizedIcons), [
    { value: "Status", text: "Status" },
    { value: "User", text: "User" },
]);
assert.deepEqual(getIconGroupOptions([
    { name: "resource", category: "Compute" },
    { name: "services", category: "Portal Services" },
    { name: "ui", category: "General UI" },
    { name: "browse", category: "Browse & Discover" },
    { name: "assets", category: "Portal Assets" },
    { name: "commands", category: "Portal Commands" },
    { name: "other", category: "Accessibility" },
]), [
    { value: "General UI", text: "General UI" },
    { value: "Portal Assets", text: "Portal Assets" },
    { value: "Portal Commands", text: "Portal Commands" },
    { value: "Browse & Discover", text: "Browse & Discover" },
    { value: "Portal Services", text: "Portal Services" },
    { value: "Accessibility", text: "Accessibility" },
    { value: "Compute", text: "Compute" },
]);
assert.deepEqual(getIconGroupFilterState(categorizedIcons, "User"), {
    options: [
        { value: "Status", text: "Status" },
        { value: "User", text: "User" },
    ],
    isVisible: true,
    selectedGroup: "User",
});
assert.equal(matchesIconGroup(categorizedIcons[1], "User"), true);
assert.equal(matchesIconGroup(categorizedIcons[0], "User"), false);
assert.equal(matchesIconGroup(categorizedIcons[0], ""), true);

assert.deepEqual(getIconGroupFilterState([{ name: "only", category: "Products" }], "Products"), {
    options: [{ value: "Products", text: "Products" }],
    isVisible: false,
    selectedGroup: "Products",
});
assert.deepEqual(getIconGroupFilterState([{ name: "none" }], "Status"), {
    options: [],
    isVisible: false,
    selectedGroup: "",
});

console.log("group_filter.test.js: ok");
