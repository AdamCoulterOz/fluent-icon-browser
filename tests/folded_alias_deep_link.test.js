const assert = require("node:assert/strict");

const { getIconSearchParts, resolveIconEntry, resolveIconSetEntry } = require("../script.js");
const iconData = require("../icon-data.json");

const vault = {
    name: "vault_secrets_square",
    displayName: "Vault Secrets Square",
    aliases: ["vault_secrets_square_color"],
};
const directName = { name: "vault_secrets_square_color", displayName: "Direct match" };

assert.equal(
    resolveIconEntry([vault], "vault_secrets_square_color"),
    vault,
    "a folded alias should resolve to its canonical icon"
);
assert.equal(
    resolveIconEntry([vault, directName], "vault_secrets_square_color"),
    directName,
    "a direct icon name should take precedence over an alias"
);
assert.equal(resolveIconEntry([vault], "missing_icon"), null);
assert.ok(
    getIconSearchParts(vault).includes("vault_secrets_square_color"),
    "a folded alias should remain searchable through the canonical icon"
);

assert.deepEqual(
    resolveIconSetEntry(iconData.sets, "vault_secrets_square_color"),
    {
        key: "hashicorp",
        icon: iconData.sets.hashicorp.icons.find(
            (icon) => icon.name === "vault_secrets_square"
        ),
    },
    "the generated HashiCorp alias should resolve to its canonical family"
);

const iconSets = {
    fluent: { icons: [directName] },
    hashicorp: { icons: [vault] },
};
assert.deepEqual(resolveIconSetEntry(iconSets, "vault_secrets_square_color"), {
    key: "fluent",
    icon: directName,
});
assert.deepEqual(resolveIconSetEntry({ hashicorp: iconSets.hashicorp }, "vault_secrets_square_color"), {
    key: "hashicorp",
    icon: vault,
});
assert.equal(resolveIconSetEntry(iconSets, "missing_icon"), null);

console.log("folded_alias_deep_link.test.js: ok");
