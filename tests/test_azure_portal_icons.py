import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

import azure_portal_icons as azure


def portal_bootstrap(config_hash: str = "bootstrap-hash") -> str:
    manifest_hashes = {
        category: [[f"{category}-hash", "alternate-hash"]]
        for category in azure.MANIFEST_GROUPS
    }
    return (
        "MsPortalImpl.redirect("
        + json.dumps(
            {
                "portalServerConfig": {
                    "portalQuery": {
                        "configHash": config_hash,
                        "pageVersion": "99.1.0.0",
                    },
                    "environment": {"extensionsManifestHash": manifest_hashes},
                }
            }
        )
        + ");"
    )


def require_config() -> str:
    return (
        "MsPortalImpl.setRequireConfig("
        + json.dumps(
            {
                "requireConfig": {
                    "dependencyTree": {
                        "Content/Dynamic/azure-core": {
                            "_generated/MsPortalImpl/Svg/Library/Cloud.svg": [],
                            "_generated/MsPortalImpl/Svg/Library/CloudFilled.svg": [],
                        },
                        "Content/Dynamic/other": {"Fx/Unrelated": []},
                    }
                }
            }
        )
        + ");"
    )


class AzurePortalIconsTests(unittest.TestCase):
    def test_discovers_bundle_from_bootstrap_without_evaluating_script(self) -> None:
        sources = {
            azure.PORTAL_BASE_URL: portal_bootstrap(),
            "https://portal.azure.com/Content/PortalRequireConfig/bootstrap-hash.js": require_config(),
        }

        source = azure.discover_portal_source(fetch_text=sources.__getitem__)

        self.assertEqual("99.1.0.0", source.page_version)
        self.assertEqual("bootstrap-hash", source.bootstrap_config_hash)
        self.assertEqual("bootstrap-hash", source.require_config_hash)
        self.assertEqual(
            ("https://portal.azure.com/Content/Dynamic/azure-core.js",),
            source.bundle_urls,
        )
        self.assertEqual(
            [
                "https://portal.azure.com/Content/ExtensionManifest/"
                f"{category}-hash.json"
                for category in azure.MANIFEST_GROUPS
            ],
            [manifest_source.url for manifest_source in source.manifest_sources],
        )

    def test_uses_matching_locked_require_config_when_bootstrap_hash_is_not_a_url(self) -> None:
        fallback_url = "https://portal.azure.com/Content/PortalRequireConfig/locked-hash.js"

        def fetch_text(url: str) -> str:
            if url == azure.PORTAL_BASE_URL:
                return portal_bootstrap()
            if url == fallback_url:
                return require_config()
            raise HTTPError(url, 404, "not found", hdrs=None, fp=None)

        source = azure.discover_portal_source(
            fetch_text=fetch_text, fallback_require_config_url=fallback_url
        )

        self.assertEqual("locked-hash", source.require_config_hash)
        self.assertEqual(fallback_url, source.require_config_url)

    def test_builds_descriptor_only_entries_and_deduplicates_svg(self) -> None:
        svg = '<svg viewBox="0 0 16 16"><path d="M0 0h16v16H0z"/></svg>'
        bundle = "\n".join(
            [
                'define("_generated/MsPortalImpl/Svg/Library/Cloud.svg", ["require", "exports"], function(t, e) { e.data = ' + json.dumps(svg) + '; });',
                'define("_generated/MsPortalImpl/Svg/Library/CloudFilled.svg", ["require", "exports"], function(t, e) { e.data = ' + json.dumps(svg) + '; });',
                'define("_generated/MsPortalImpl/Svg/Library/Polychromatic/Learn.svg", ["require", "exports"], function(t, e) { e.data = ' + json.dumps('<svg viewBox="0 0 16 16"><path d="M1 1h14v14H1z"/></svg>') + '; });',
            ]
        )
        source = azure.PortalSource(
            portal_base_url=azure.PORTAL_BASE_URL,
            page_version="99.1.0.0",
            bootstrap_config_hash="bootstrap-hash",
            require_config_hash="require-hash",
            require_config_url="https://portal.azure.com/Content/PortalRequireConfig/require-hash.js",
            bundle_urls=("https://portal.azure.com/Content/Dynamic/azure-core.js",),
            manifest_sources=(),
        )

        icons, unique_count = azure.build_azure_icons(
            source, fetch_text=lambda _url: bundle
        )
        payload = json.dumps(icons)
        cloud = next(icon for icon in icons if icon["name"] == "cloud")
        remote_source = cloud["variants"]["regular"]["remoteSource"]

        self.assertEqual(2, unique_count)
        self.assertNotIn("<svg", payload)
        self.assertEqual("portal-amd-svg-module", remote_source["format"])
        self.assertEqual(
            remote_source,
            cloud["variants"]["regular"]["sizes"]["16"]["remoteSource"],
        )
        canonical = azure.canonical_svg_text(svg)
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            remote_source["sha256"],
        )
        self.assertEqual(2, len(cloud["variants"]["regular"]["remoteSources"]))
        self.assertIn(
            "color", next(icon for icon in icons if icon["name"] == "learn")["variants"]
        )

    def test_preserves_authored_source_colors_only_when_svg_paints_need_it(self) -> None:
        fixtures = {
            "neutral": '<svg><path fill="#666" d="M0 0h1v1H0z"/></svg>',
            "chromatic": '<svg><path style="fill: #0078d4" d="M0 0h1v1H0z"/></svg>',
            "multiple": '<svg><path fill="#000" d="M0 0h1v1H0z"/><path stroke="#fff" d="M1 1h1v1H1z"/></svg>',
            "gradient": '<svg><defs><linearGradient id="a"><stop stop-color="#0078d4"/></linearGradient></defs><path fill="url(#a)" d="M0 0h1v1H0z"/></svg>',
            "pattern": '<svg><defs><pattern id="a" width="1" height="1"><path fill="#0078d4" d="M0 0h1v1H0z"/></pattern></defs><path style="fill: url(#a)" d="M0 0h1v1H0z"/></svg>',
            "hidden": '<svg><path style="display: none; fill: #0078d4" d="M0 0h1v1H0z"/></svg>',
            "hidden_display_important": '<svg><path style="display: none !important; fill: #0078d4" d="M0 0h1v1H0z"/></svg>',
            "hidden_visibility_important": '<svg><path style="visibility: hidden !IMPORTANT; fill: #0078d4" d="M0 0h1v1H0z"/></svg>',
            "hidden_duplicate": '<svg><path style="display: block; display: none; fill: #0078d4" d="M0 0h1v1H0z"/></svg>',
            "visible_duplicate_important": '<svg><path style="display: none; display: block !important; fill: #0078d4" d="M0 0h1v1H0z"/></svg>',
            "removed_style": '<svg><style>.icon { fill: #0078d4; }</style><path class="icon" d="M0 0h1v1H0z"/></svg>',
            "removed_use": '<svg><defs><path id="icon" fill="#0078d4" d="M0 0h1v1H0z"/></defs><use href="#icon" fill="#0078d4"/></svg>',
        }

        self.assertFalse(azure.preserve_source_colors(fixtures["neutral"]))
        self.assertTrue(azure.preserve_source_colors(fixtures["chromatic"]))
        self.assertTrue(azure.preserve_source_colors(fixtures["multiple"]))
        self.assertTrue(azure.preserve_source_colors(fixtures["gradient"]))
        self.assertTrue(azure.preserve_source_colors(fixtures["pattern"]))
        self.assertFalse(azure.preserve_source_colors(fixtures["hidden"]))
        self.assertFalse(azure.preserve_source_colors(fixtures["hidden_display_important"]))
        self.assertFalse(azure.preserve_source_colors(fixtures["hidden_visibility_important"]))
        self.assertFalse(azure.preserve_source_colors(fixtures["hidden_duplicate"]))
        self.assertTrue(azure.preserve_source_colors(fixtures["visible_duplicate_important"]))
        self.assertFalse(azure.preserve_source_colors(fixtures["removed_style"]))
        self.assertFalse(azure.preserve_source_colors(fixtures["removed_use"]))

        records = [
            {
                "name": name,
                "displayName": name.title(),
                "description": "Fixture.",
                "style": "regular",
                "tags": [],
                "descriptor": {
                    "url": "https://portal.azure.com/a",
                    "selector": f"/{name}",
                    "sha256": hashlib.sha256(
                        azure.canonical_svg_text(svg).encode("utf-8")
                    ).hexdigest(),
                },
                "preserveSourceColors": azure.preserve_source_colors(svg),
            }
            for name, svg in fixtures.items()
        ]
        icons, unique_count = azure._collapse_records(records)
        payload = json.dumps(icons)

        self.assertEqual(len(fixtures), unique_count)
        self.assertNotIn("<svg", payload)
        for name in (
            "neutral",
            "hidden",
            "hidden_display_important",
            "hidden_visibility_important",
            "hidden_duplicate",
            "removed_style",
            "removed_use",
        ):
            self.assertNotIn(
                "preserveSourceColors",
                next(icon for icon in icons if icon["name"] == name)["variants"]["regular"],
            )
        for name in ("chromatic", "multiple", "gradient", "pattern", "visible_duplicate_important"):
            self.assertTrue(
                next(icon for icon in icons if icon["name"] == name)["variants"]["regular"]["preserveSourceColors"]
            )

    def test_deduplication_propagates_source_color_preservation(self) -> None:
        descriptor = {"url": "https://portal.azure.com/a", "selector": "/a", "sha256": "a" * 64}
        records = [
            {"name": "first", "displayName": "First", "description": "First.", "style": "regular", "tags": [], "descriptor": descriptor, "preserveSourceColors": False},
            {"name": "second", "displayName": "Second", "description": "Second.", "style": "regular", "tags": [], "descriptor": {**descriptor, "selector": "/b"}, "preserveSourceColors": True},
        ]

        icons, unique_count = azure._collapse_records(records)

        self.assertEqual(1, unique_count)
        variant = icons[0]["variants"]["regular"]
        self.assertTrue(variant["preserveSourceColors"])
        self.assertEqual(2, len(variant["remoteSources"]))

    def test_manifest_icon_data_uses_json_pointer_and_deduplicates_aliases(self) -> None:
        first_svg = '<svg viewBox="0 0 16 16"><path d="M0 0h16v16H0z"/></svg>'
        second_svg = '<svg viewBox="0 0 16 16"><path d="M2 2h12v12H2z"/></svg>'
        source = azure.ManifestSource(
            category="assetTypes", url="https://portal.azure.com/Content/ExtensionManifest/test.json"
        )
        payload = {
            "manifest": {
                "DemoExtension": {
                    "assetTypes": [
                        {
                            "name": "Widgets",
                            "singularDisplayName": "Widget",
                            "keywords": ["sample", "resource"],
                            "icon": {"data": first_svg},
                            "resourceType": {
                                "resourceTypeName": "Microsoft.Demo/widgets",
                                "kinds": [
                                    {"name": "Shared", "icon": {"data": first_svg}}
                                ],
                            },
                        },
                        {
                            "name": "Widgets",
                            "singularDisplayName": "Widget",
                            "icon": {"data": second_svg},
                        },
                    ]
                }
            }
        }

        records = azure._manifest_icon_records(source, payload)
        icons, unique_count = azure._collapse_records(records)
        serialized = json.dumps(icons)
        shared = next(icon for icon in icons if icon["name"].endswith("shared"))
        descriptor = shared["variants"]["regular"]["remoteSource"]

        self.assertEqual(2, unique_count)
        self.assertNotIn("<svg", serialized)
        self.assertEqual("portal-json-pointer-svg", descriptor["format"])
        self.assertEqual(
            "/manifest/DemoExtension/assetTypes/0/resourceType/kinds/0/icon/data",
            descriptor["selector"],
        )
        self.assertEqual(
            "/manifest/DemoExtension/assetTypes/0/icon/data",
            records[0]["descriptor"]["selector"],
        )
        self.assertIn("resource", shared["metaphors"])
        self.assertIn(
            "azure_demo_extension_asset_types_microsoft_demo_widgets_widget",
            shared["aliases"],
        )
        self.assertEqual(len(icons), len({icon["name"] for icon in icons}))

    def test_same_count_content_drift_changes_source_and_index_digests(self) -> None:
        source = azure.PortalSource(
            portal_base_url=azure.PORTAL_BASE_URL,
            page_version="99.1.0.0",
            bootstrap_config_hash="bootstrap-hash",
            require_config_hash="require-hash",
            require_config_url="https://portal.azure.com/Content/PortalRequireConfig/require-hash.js",
            bundle_urls=("https://portal.azure.com/Content/Dynamic/azure-core.js",),
            manifest_sources=(),
        )

        def bundle(svg_path: str) -> str:
            return (
                'define("_generated/MsPortalImpl/Svg/Library/Cloud.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps(
                    f'<svg viewBox="0 0 16 16"><path d="{svg_path}"/></svg>'
                )
                + '; });'
            )

        first = azure.build_azure_catalog(source, fetch_text=lambda _url: bundle("M0 0"))
        second = azure.build_azure_catalog(source, fetch_text=lambda _url: bundle("M1 1"))

        self.assertEqual(len(first.icons), len(second.icons))
        self.assertNotEqual(first.source_digest, second.source_digest)
        self.assertNotEqual(first.index_digest, second.index_digest)

    def test_name_collisions_get_stable_distinct_families(self) -> None:
        records = [
            {
                "name": "duplicate",
                "displayName": "Duplicate",
                "description": "First.",
                "style": "regular",
                "tags": [],
                "descriptor": {"url": "https://portal.azure.com/a", "selector": "/a", "sha256": "a" * 64},
            },
            {
                "name": "duplicate",
                "displayName": "Duplicate",
                "description": "Second.",
                "style": "regular",
                "tags": [],
                "descriptor": {"url": "https://portal.azure.com/b", "selector": "/b", "sha256": "b" * 64},
            },
        ]

        icons, _unique_count = azure._collapse_records(records)

        self.assertEqual(["duplicate", "duplicate_regular_bbbbbbbb"], [icon["name"] for icon in icons])

    def test_count_gate_rejects_material_collapse(self) -> None:
        with self.assertRaisesRegex(azure.AzurePortalSchemaError, "minimum"):
            azure.enforce_count_gate(249, 250, None)
        with self.assertRaisesRegex(azure.AzurePortalSchemaError, "more than 25%"):
            azure.enforce_count_gate(74, 1, 100)

    def test_source_lock_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "nested" / "azure-lock.json"
            azure.write_source_lock(lock, {"indexedCount": 1})
            self.assertEqual({"indexedCount": 1}, json.loads(lock.read_text()))


if __name__ == "__main__":
    unittest.main()
