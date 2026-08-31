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
