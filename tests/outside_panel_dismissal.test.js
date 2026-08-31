const assert = require("node:assert/strict");

const { shouldDismissIconPanelFromPointerDown } = require("../script.js");

function createTarget(closestSelector = "") {
    return {
        closest(selector) {
            return selector === closestSelector ? {} : null;
        },
    };
}

const panel = { contains: () => false };
const panelSizeMenu = { contains: () => false };
const outsideTarget = {
    isPanelOpen: true,
    target: createTarget(),
    panel,
    panelSizeMenu,
};

assert.equal(shouldDismissIconPanelFromPointerDown(outsideTarget), true);
assert.equal(
    shouldDismissIconPanelFromPointerDown({
        ...outsideTarget,
        target: createTarget(".app-update-banner"),
    }),
    false
);
assert.equal(
    shouldDismissIconPanelFromPointerDown({
        ...outsideTarget,
        panel: { contains: () => true },
    }),
    false
);
assert.equal(
    shouldDismissIconPanelFromPointerDown({
        ...outsideTarget,
        panelSizeMenu: { contains: () => true },
    }),
    false
);
assert.equal(
    shouldDismissIconPanelFromPointerDown({
        ...outsideTarget,
        target: createTarget(".icon-card"),
    }),
    false
);
assert.equal(
    shouldDismissIconPanelFromPointerDown({
        ...outsideTarget,
        isPanelOpen: false,
    }),
    false
);

console.log("outside_panel_dismissal.test.js: ok");
