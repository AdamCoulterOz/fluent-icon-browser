import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

import azure_portal_icons as azure


def portal_bootstrap(
    config_hash: str = "bootstrap-hash", page_version: str = "99.1.0.0"
) -> str:
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
                        "pageVersion": page_version,
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


def previous_source_lock_payload(
    page_version: str = "98.9.0.0", suffix: str = "previous"
) -> dict:
    return {
        "portalBaseUrl": azure.PORTAL_BASE_URL,
        "pageVersion": page_version,
        "bootstrapConfigHash": f"{suffix}-bootstrap",
        "requireConfigHash": f"{suffix}-require",
        "requireConfigUrl": (
            "https://portal.azure.com/Content/PortalRequireConfig/"
            f"{suffix}-require.js"
        ),
        "amdBundleUrls": [
            f"https://portal.azure.com/Content/Dynamic/{suffix}-bundle.js"
        ],
        "extensionManifestSources": [
            {
                "category": category,
                "url": (
                    "https://portal.azure.com/Content/ExtensionManifest/"
                    f"{suffix}-{category}.json"
                ),
            }
            for category in azure.MANIFEST_GROUPS
        ],
    }


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

    def test_uses_full_previous_snapshot_for_cross_version_require_config_404(self) -> None:
        payload = previous_source_lock_payload()
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "azure-lock.json"
            lock_path.write_text(json.dumps(payload), encoding="utf-8")
            previous_source = azure.previous_portal_source(lock_path)

        def fetch_text(url: str) -> str:
            if url == azure.PORTAL_BASE_URL:
                return portal_bootstrap(
                    config_hash="current-bootstrap", page_version="99.1.0.0"
                )
            raise HTTPError(url, 404, "not found", hdrs=None, fp=None)

        source = azure.discover_portal_source(
            fetch_text=fetch_text, fallback_source=previous_source
        )

        self.assertEqual(previous_source, source)
        self.assertEqual("98.9.0.0", source.page_version)
        self.assertTrue(all("previous-" in url for url in source.bundle_urls))
        self.assertTrue(
            all("previous-" in manifest.url for manifest in source.manifest_sources)
        )

    def test_rejects_malformed_previous_source_snapshot(self) -> None:
        malformed_payloads = []
        invalid_require_config_url = previous_source_lock_payload()
        invalid_require_config_url["requireConfigUrl"] = (
            "https://portal.azure.com@invalid.example/Content/PortalRequireConfig/"
            "previous-require.js"
        )
        malformed_payloads.append(invalid_require_config_url)

        duplicate_bundle_urls = previous_source_lock_payload()
        duplicate_bundle_urls["amdBundleUrls"] *= 2
        malformed_payloads.append(duplicate_bundle_urls)

        incomplete_manifest_categories = previous_source_lock_payload()
        incomplete_manifest_categories["extensionManifestSources"] = (
            incomplete_manifest_categories["extensionManifestSources"][:-1]
        )
        malformed_payloads.append(incomplete_manifest_categories)

        invalid_page_version = previous_source_lock_payload()
        invalid_page_version["pageVersion"] = "not-a-version"
        malformed_payloads.append(invalid_page_version)

        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "azure-lock.json"
            for payload in malformed_payloads:
                lock_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(payload=payload):
                    with self.assertRaises(azure.AzurePortalSchemaError):
                        azure.previous_portal_source(lock_path)

    def test_does_not_hide_non_transition_require_config_errors(self) -> None:
        fallback = azure.PortalSource(
            portal_base_url=azure.PORTAL_BASE_URL,
            page_version="98.9.0.0",
            bootstrap_config_hash="previous-bootstrap",
            require_config_hash="previous-require",
            require_config_url=(
                "https://portal.azure.com/Content/PortalRequireConfig/"
                "previous-require.js"
            ),
            bundle_urls=(
                "https://portal.azure.com/Content/Dynamic/previous-bundle.js",
            ),
            manifest_sources=tuple(
                azure.ManifestSource(
                    category=category,
                    url=(
                        "https://portal.azure.com/Content/ExtensionManifest/"
                        f"previous-{category}.json"
                    ),
                )
                for category in azure.MANIFEST_GROUPS
            ),
        )

        def fetch_500(url: str) -> str:
            if url == azure.PORTAL_BASE_URL:
                return portal_bootstrap()
            raise HTTPError(url, 500, "server error", hdrs=None, fp=None)

        def fetch_404(url: str) -> str:
            if url == azure.PORTAL_BASE_URL:
                return portal_bootstrap()
            raise HTTPError(url, 404, "not found", hdrs=None, fp=None)

        with self.assertRaises(HTTPError):
            azure.discover_portal_source(fetch_text=fetch_500, fallback_source=fallback)
        with self.assertRaises(HTTPError):
            azure.discover_portal_source(fetch_text=fetch_404)

    def test_builds_descriptor_only_entries_and_deduplicates_svg(self) -> None:
        svg = '<svg viewBox="0 0 16 16"><path d="M0 0h16v16H0z"/></svg>'
        bundle = "\n".join(
            [
                'define("_generated/Less/MsPortalImpl/Base/Base.Images.css", '
                '["module"], function(e) { return { css: ".msportalfx-svg-c01{fill:#fff}" }; });',
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

    def test_admits_only_renderable_vector_svg_content_for_core_and_manifests(self) -> None:
        valid_svg = (
            '<svg viewBox="0 0 16 16"><defs><symbol id="mark">'
            '<path d="M0 0h16v16H0z"/></symbol></defs><use href="#mark"/></svg>'
        )
        fixtures = {
            "ValidLocalUse": valid_svg,
            "Empty": '<svg viewBox="0 0 16 16"/>',
            "Hidden": '<svg viewBox="0 0 16 16"><g display="none"><path d="M0 0h16v16H0z"/></g></svg>',
            "Image": '<svg viewBox="0 0 16 16"><image href="data:image/png;base64,AA=="/></svg>',
            "ImageUse": (
                '<svg viewBox="0 0 16 16"><defs><image id="raster" '
                'href="data:image/png;base64,AA=="/></defs><use href="#raster"/></svg>'
            ),
        }
        bundle_modules = [
            'define("_generated/Less/MsPortalImpl/Base/Base.Images.css", '
            '["module"], function(e) { return { css: ".msportalfx-svg-c01{fill:#fff}" }; });'
        ]
        for name, svg in fixtures.items():
            bundle_modules.append(
                'define("_generated/MsPortalImpl/Svg/Library/'
                + name
                + '.svg", ["require", "exports"], function(t, e) { e.data = '
                + json.dumps(svg)
                + "; });"
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

        core_result = azure.build_azure_catalog(
            source, fetch_text=lambda _url: "\n".join(bundle_modules)
        )

        self.assertEqual(["valid_local_use"], [icon["name"] for icon in core_result.icons])

        manifest_source = azure.ManifestSource(
            category="assetTypes",
            url="https://portal.azure.com/Content/ExtensionManifest/test.json",
        )
        manifest_payload = {
            "manifest": {
                "DemoExtension": {
                    "assetTypes": [
                        {"name": name, "icon": {"data": svg}}
                        for name, svg in fixtures.items()
                    ]
                }
            }
        }

        manifest_records = azure._manifest_icon_records(manifest_source, manifest_payload)

        self.assertEqual(1, len(manifest_records))
        self.assertEqual(
            "/manifest/DemoExtension/assetTypes/0/icon/data",
            manifest_records[0]["descriptor"]["selector"],
        )

    def test_materializes_locked_base_images_palette_classes(self) -> None:
        css = (
            ".msportalfx-svg-c01{fill:#fff}.msportalfx-svg-c02{fill:#000}"
            ".msportalfx-svg-c03{fill:#a0a1a2}.msportalfx-svg-c19{fill:#0072c6}"
            ".msportalfx-svg-c05{fill:var(--fxs-svg-c05-fill,#3e3e3e)}"
            ".msportalfx-svg-c07{fill:var(--fxs-svg-c07-fill,#0f0f0f)}"
            ".msportalfx-svg-c22{fill:var(--fxs-svg-c22-fill,#e81123)}"
            ".msportalfx-svg-c77{fill:var(--arbitrary,red)}"
        )
        avatar_svg = (
            '<svg><path class="msportalfx-svg-c01"/>'
            '<path class="msportalfx-svg-c02"/>'
            '<path class="msportalfx-svg-c03"/></svg>'
        )
        bundle = "\n".join(
            [
                'define("_generated/Less/MsPortalImpl/Base/Base.Images.css", '
                '["module"], function(e) { return { css: '
                + json.dumps(css)
                + ", moduleId: e.id } });",
                'define("_generated/MsPortalImpl/Svg/Library/AvatarDefault.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps(avatar_svg)
                + "; });",
                'define("_generated/MsPortalImpl/Svg/Library/Chromatic.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps('<svg><path class="msportalfx-svg-c19"/></svg>')
                + "; });",
                'define("_generated/MsPortalImpl/Svg/Library/Neutral.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps('<svg><path class="msportalfx-svg-c03"/></svg>')
                + "; });",
                'define("_generated/MsPortalImpl/Svg/Library/Fallback.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps(
                    '<svg><path class="msportalfx-svg-c05"/>'
                    '<path class="msportalfx-svg-c07"/>'
                    '<path class="msportalfx-svg-c22"/></svg>'
                )
                + "; });",
                'define("_generated/MsPortalImpl/Svg/Library/Contextual.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps('<svg><path fill="currentColor"/></svg>')
                + "; });",
                'define("_generated/MsPortalImpl/Svg/Library/Unknown.svg", '
                '["require", "exports"], function(t, e) { e.data = '
                + json.dumps('<svg><path class="msportalfx-svg-c77"/></svg>')
                + "; });",
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

        result = azure.build_azure_catalog(source, fetch_text=lambda _url: bundle)
        variants = {
            icon["name"]: icon["variants"]["regular"] for icon in result.icons
        }

        self.assertEqual(
            {
                "msportalfx-svg-c01": "#FFFFFF",
                "msportalfx-svg-c02": "#000000",
                "msportalfx-svg-c03": "#A0A1A2",
            },
            variants["avatar_default"]["remoteSource"]["paintMap"],
        )
        self.assertEqual(
            {"msportalfx-svg-c19": "#0072C6"},
            variants["chromatic"]["remoteSource"]["paintMap"],
        )
        self.assertEqual(
            {"msportalfx-svg-c03": "#A0A1A2"},
            variants["neutral"]["remoteSource"]["paintMap"],
        )
        # The locked CSS fallback is materialized as an intrinsic literal fill.
        self.assertEqual(
            {
                "msportalfx-svg-c05": "#3E3E3E",
                "msportalfx-svg-c07": "#0F0F0F",
                "msportalfx-svg-c22": "#E81123",
            },
            variants["fallback"]["remoteSource"]["paintMap"],
        )
        self.assertTrue(variants["avatar_default"]["preserveSourceColors"])
        self.assertTrue(variants["chromatic"]["preserveSourceColors"])
        self.assertTrue(variants["neutral"]["preserveSourceColors"])
        self.assertTrue(variants["fallback"]["preserveSourceColors"])
        self.assertNotIn("paintMap", variants["contextual"]["remoteSource"])
        self.assertNotIn("preserveSourceColors", variants["contextual"])
        self.assertNotIn("paintMap", variants["unknown"]["remoteSource"])
        self.assertNotIn("preserveSourceColors", variants["unknown"])

        nonliteral_css_bundle = (
            'define("_generated/Less/MsPortalImpl/Base/Base.Images.css", '
            '["module"], function(e) { return { css: e.value, moduleId: e.id } });'
        )
        with self.assertRaisesRegex(azure.AzurePortalSchemaError, "non-literal css"):
            azure._base_images_palette_from_bundle(nonliteral_css_bundle)

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
                'define("_generated/Less/MsPortalImpl/Base/Base.Images.css", '
                '["module"], function(e) { return { css: ".msportalfx-svg-c01{fill:#fff}" }; });\n'
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
