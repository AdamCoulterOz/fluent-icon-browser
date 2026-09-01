const assert = require("node:assert/strict");

const {
    getDeepLinkFilterState,
    getIconMetaphors,
    getIconSearchParts,
    getIconSearchTerms,
    resolveIconEntry,
    resolveIconSetEntry,
} = require("../script.js");
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

const broadMatches = Array.from({ length: 973 }, (_, index) => ({
    name: `microsoft_service_${index}`,
    displayName: `Microsoft Service ${index}`,
}));
const lateTarget = {
    name: "microsoft",
    displayName: "Microsoft",
    aliases: ["microsoft_alias"],
};
broadMatches.splice(971, 0, lateTarget);

assert.deepEqual(getDeepLinkFilterState(broadMatches, "microsoft"), {
    resolved: lateTarget,
    query: "Microsoft",
    exactIcons: [lateTarget],
}, "a resolved deep link should mount only its canonical family");
assert.deepEqual(getDeepLinkFilterState(broadMatches, "microsoft_alias"), {
    resolved: lateTarget,
    query: "Microsoft",
    exactIcons: [lateTarget],
}, "a resolved alias should mount its canonical family");
assert.deepEqual(getDeepLinkFilterState(broadMatches, "unknown_icon"), {
    resolved: null,
    query: "unknown_icon",
    exactIcons: null,
}, "an unknown deep link should retain plain-search fallback behavior");
assert.ok(
    getIconSearchParts(vault).includes("vault_secrets_square_color"),
    "a folded alias should remain searchable through the canonical icon"
);

const displayMetadata = {
    name: "private_link_scope",
    metaphors: ["Azure Monitor", "k8s"],
    searchTerms: ["Microsoft.Insights/privateLinkScopes", "raw_transport_id"],
};
assert.deepEqual(getIconMetaphors(displayMetadata), ["Azure Monitor", "k8s"]);
assert.deepEqual(
    getIconSearchTerms(displayMetadata),
    ["Microsoft.Insights/privateLinkScopes", "raw_transport_id"]
);
assert.ok(
    getIconSearchParts(displayMetadata).includes("Microsoft.Insights/privateLinkScopes"),
    "hidden search terms should remain searchable"
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
