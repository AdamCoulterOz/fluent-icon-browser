import json
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

import flight_icons
import redhat_icons
import salesforce_icons
import source_lock


def write_svg(path: Path, size: int = 24) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}"><path d="M0 0"/></svg>',
        encoding="utf-8",
    )


def write_flight_license(package_dir: Path) -> None:
    (package_dir / "LICENSE.md").write_text(
        "Mozilla Public License Version 2.0\n", encoding="utf-8"
    )


def write_redhat_license(root: Path) -> None:
    (root / "LICENSE_ICONS.md").write_text(
        "Creative Commons Attribution 4.0 International\n", encoding="utf-8"
    )


def write_salesforce_archive(archive_path: Path, icons: list[tuple[str, str, str]]) -> None:
    def add_bytes(archive: tarfile.TarFile, name: str, value: bytes) -> None:
        member = tarfile.TarInfo(name)
        member.size = len(value)
        archive.addfile(member, io.BytesIO(value))

    with tarfile.open(archive_path, "w:gz") as archive:
        add_bytes(
            archive,
            "package/package.json",
            json.dumps(
                {
                    "name": "@salesforce-ux/icons",
                    "version": "10.17.0",
                    "license": "CC-BY-ND-4.0",
                }
            ).encode("utf-8"),
        )
        for category in salesforce_icons.APPROVED_CATEGORIES:
            metadata = {
                name: {"synonyms": [f"{name} synonym"]}
                for entry_category, name, _svg in icons
                if entry_category == category
            }
            add_bytes(
                archive,
                f"package/dist/{category}-icons-metadata.json",
                json.dumps(metadata).encode("utf-8"),
            )
        for category, name, svg in icons:
            add_bytes(
                archive,
                f"{salesforce_icons.PACKAGE_PREFIX}/{category}/{name}.svg",
                svg.encode("utf-8"),
            )


class SourceCollectionTests(unittest.TestCase):
    def test_salesforce_archive_lock_preserves_distinct_colour_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "icons.tgz"
            icon_entries = [
                ("standard", "account", '<svg viewBox="0 0 120 120"><path fill="#0176d3"/></svg>'),
                ("standard", "mulesoft", '<svg viewBox="0 0 120 120" fill="#fff"><path/></svg>'),
                ("action", "add_contact", '<svg viewBox="0 0 120 120"><path fill="#2e844a"/></svg>'),
                ("doctype", "pdf", '<svg viewBox="0 0 120 120"><path fill="#ea001e"/></svg>'),
                ("custom", "custom1", '<svg viewBox="0 0 120 120"><path fill="#9050e9"/></svg>'),
                ("utility", "mulesoft", '<svg viewBox="0 0 120 120"><path/></svg>'),
            ]
            write_salesforce_archive(archive_path, icon_entries)
            lock_path = root / "salesforce-lock.json"
            lock = salesforce_icons.write_source_lock(archive_path, lock_path)
            icons = salesforce_icons.generate_icons(archive_path, lock_path)
            by_name = {icon["name"]: icon for icon in icons}

            self.assertEqual("10.17.0", lock["packageVersion"])
            self.assertEqual(5, lock["indexedAssetCount"])
            self.assertEqual(["utility"], lock["excludedCategories"])
            self.assertIn("standard_mulesoft", by_name)
            self.assertIn("standard_account", by_name)
            self.assertNotIn("utility_mulesoft", by_name)
            self.assertEqual(["color"], list(by_name["standard_mulesoft"]["variants"]))
            descriptor = by_name["standard_mulesoft"]["variants"]["color"]["sizes"]["120"]["remoteSource"]
            self.assertEqual("npm-tgz-svg-entry", descriptor["format"])
            self.assertEqual(lock["archiveSha256"], descriptor["archiveSha256"])
            self.assertEqual("package/dist/salesforce-lightning-design-system-icons/standard/mulesoft.svg", descriptor["entry"])
            self.assertFalse(by_name["standard_mulesoft"]["variants"]["color"]["sourceCapabilities"]["currentColor"])
            self.assertFalse(by_name["standard_mulesoft"]["variants"]["color"]["sourceCapabilities"]["boundingBox"])
            self.assertEqual("contrast", by_name["standard_mulesoft"]["variants"]["color"]["previewSurface"])
            self.assertNotIn("previewSurface", by_name["standard_account"]["variants"]["color"])
            self.assertNotIn("<svg", json.dumps(icons))

    def test_salesforce_contrast_classification_requires_explicit_light_only_paint(self) -> None:
        self.assertTrue(
            salesforce_icons.requires_contrast_preview(
                b'<svg fill="#fff"><path d="M0 0"/></svg>'
            )
        )
        self.assertTrue(
            salesforce_icons.requires_contrast_preview(
                b'<svg><path style="fill: rgb(255, 255, 255)" d="M0 0"/></svg>'
            )
        )
        self.assertFalse(
            salesforce_icons.requires_contrast_preview(
                b'<svg><path fill="#0176d3" d="M0 0"/></svg>'
            )
        )
        self.assertFalse(
            salesforce_icons.requires_contrast_preview(b'<svg><path d="M0 0"/></svg>')
        )

    def test_salesforce_archive_lock_rejects_changed_archive_or_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_archive = root / "original.tgz"
            changed_archive = root / "changed.tgz"
            original_entries = [
                ("standard", "mulesoft", '<svg viewBox="0 0 120 120"><path fill="#00a1df"/></svg>'),
            ]
            write_salesforce_archive(original_archive, original_entries)
            lock_path = root / "salesforce-lock.json"
            salesforce_icons.write_source_lock(original_archive, lock_path)
            write_salesforce_archive(
                changed_archive,
                [("standard", "mulesoft", '<svg viewBox="0 0 120 120"><path fill="#ff0000"/></svg>')],
            )

            with self.assertRaisesRegex(ValueError, "does not match"):
                salesforce_icons.generate_icons(changed_archive, lock_path)

            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["entries"][0]["sha256"] = "0" * 64
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "entries do not match"):
                salesforce_icons.generate_icons(original_archive, lock_path)

    def test_flight_filters_product_and_service_assets_and_pins_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory)
            (package_dir / "package.json").write_text('{"version":"5.1.0"}', encoding="utf-8")
            write_flight_license(package_dir)
            (package_dir / "catalog.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {"fileName": "arrow-16", "iconName": "arrow", "category": "Arrows", "size": "16", "description": "next, forward"},
                            {"fileName": "arrow-24", "iconName": "arrow", "category": "Arrows", "size": "24", "description": "next, forward"},
                            {"fileName": "arrow-fill-16", "iconName": "arrow-fill", "category": "Arrows", "size": "16", "description": "next, forward, filled"},
                            {"fileName": "arrow-fill-24", "iconName": "arrow-fill", "category": "Arrows", "size": "24", "description": "next, forward, filled"},
                            {"fileName": "orphan-fill-24", "iconName": "orphan-fill", "category": "Arrows", "size": "24", "description": "filled"},
                            {"fileName": "vault-24", "iconName": "vault", "category": "Products", "size": "24"},
                            {"fileName": "cloud-24", "iconName": "cloud", "category": "Services", "size": "24"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            write_svg(package_dir / "svg-original" / "arrow-16.svg", 16)
            write_svg(package_dir / "svg-original" / "arrow-24.svg", 24)
            write_svg(package_dir / "svg-original" / "arrow-fill-16.svg", 16)
            write_svg(package_dir / "svg-original" / "arrow-fill-24.svg", 24)
            write_svg(package_dir / "svg-original" / "orphan-fill-24.svg", 24)
            lock_path = package_dir / "flight-lock.json"
            commit = "a" * 40
            lock = flight_icons.write_source_lock(package_dir, lock_path, commit)
            icons = flight_icons.generate_icons(package_dir, commit, lock_path)

            self.assertEqual(5, lock["indexedAssetCount"])
            self.assertEqual(2, lock["indexedFamilyCount"])
            self.assertEqual(1, lock["groupedFillPairCount"])
            self.assertEqual(["arrow", "orphan_fill"], [icon["name"] for icon in icons])
            arrow = next(icon for icon in icons if icon["name"] == "arrow")
            self.assertEqual("Arrows", arrow["category"])
            self.assertIn("next", arrow["metaphors"])
            self.assertEqual(24, arrow["variants"]["regular"]["defaultSize"])
            self.assertEqual(24, arrow["variants"]["filled"]["defaultSize"])
            self.assertIn("arrow_fill", arrow["aliases"])
            self.assertIn(commit, arrow["variants"]["regular"]["previewUrl"])
            orphan = next(icon for icon in icons if icon["name"] == "orphan_fill")
            self.assertEqual(["filled"], list(orphan["variants"]))
            self.assertNotIn("<svg", json.dumps(icons))

    def test_hashicorp_products_are_separate_from_flight_and_pin_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory)
            (package_dir / "package.json").write_text('{"version":"5.1.0"}', encoding="utf-8")
            write_flight_license(package_dir)
            (package_dir / "catalog.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {"fileName": "terraform-24", "iconName": "terraform", "category": "Products", "size": "24", "description": "infrastructure"},
                            {"fileName": "vault-24", "iconName": "vault", "category": "Products", "size": "24", "description": "secrets"},
                            {"fileName": "consul-24", "iconName": "consul", "category": "Products", "size": "24", "description": "service networking"},
                            {"fileName": "packer-24", "iconName": "packer", "category": "Products", "size": "24", "description": "machine images"},
                            {"fileName": "nomad-24", "iconName": "nomad", "category": "Products", "size": "24", "description": "orchestration"},
                            {"fileName": "cloud-24", "iconName": "cloud", "category": "Services", "size": "24"},
                            {"fileName": "arrow-24", "iconName": "arrow", "category": "Arrows", "size": "24"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            for name in ("terraform", "vault", "consul", "packer", "nomad"):
                write_svg(package_dir / "svg-original" / f"{name}-24.svg")
            lock_path = package_dir / "hashicorp-products-lock.json"
            commit = "b" * 40
            lock = flight_icons.write_product_source_lock(package_dir, lock_path, commit)
            icons = flight_icons.generate_product_icons(package_dir, commit, lock_path)

            self.assertEqual(["Products"], lock["includedCategories"])
            self.assertIn("Services", lock["excludedCategories"])
            self.assertEqual(5, lock["indexedAssetCount"])
            self.assertEqual(
                ["consul", "nomad", "packer", "terraform", "vault"],
                [icon["name"] for icon in icons],
            )
            self.assertEqual("Products", icons[0]["category"])
            self.assertIn(commit, icons[0]["variants"]["regular"]["previewUrl"])
            self.assertNotIn("<svg", json.dumps(icons))

    def test_redhat_pairs_fill_variants_and_excludes_social(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text('{"version":"2.3.1"}', encoding="utf-8")
            write_redhat_license(root)
            write_svg(root / "src/ui/folder.svg", 36)
            write_svg(root / "src/ui/folder-fill.svg", 36)
            write_svg(root / "src/standard/folder.svg", 36)
            write_svg(root / "src/microns/tiny.svg", 8)
            write_svg(root / "src/social/mastodon.svg", 36)
            lock_path = root / "redhat-lock.json"
            commit = "b" * 40
            lock = redhat_icons.write_source_lock(root, lock_path, commit)
            icons = redhat_icons.generate_icons(root, commit, lock_path)
            by_name = {icon["name"]: icon for icon in icons}

            self.assertEqual(4, lock["indexedAssetCount"])
            self.assertNotIn("mastodon", by_name)
            self.assertIn("ui_folder", by_name)
            self.assertIn("standard_folder", by_name)
            self.assertIn("filled", by_name["ui_folder"]["variants"])
            self.assertEqual("ui", by_name["ui_folder"]["category"])
            self.assertIn(commit, by_name["ui_folder"]["variants"]["filled"]["previewUrl"])
            self.assertNotIn("<svg", json.dumps(icons))

    def test_digest_bound_lock_rejects_changed_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text('{"version":"2.3.1"}', encoding="utf-8")
            write_redhat_license(root)
            icon_path = root / "src/standard/check.svg"
            write_svg(icon_path)
            lock_path = root / "redhat-lock.json"
            commit = "c" * 40
            redhat_icons.write_source_lock(root, lock_path, commit)
            icon_path.write_text('<svg viewBox="0 0 36 36"/>', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not match"):
                redhat_icons.generate_icons(root, commit, lock_path)

    def test_license_file_change_invalidates_source_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory)
            (package_dir / "package.json").write_text(
                '{"version":"5.1.0"}', encoding="utf-8"
            )
            write_flight_license(package_dir)
            (package_dir / "catalog.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "fileName": "arrow-24",
                                "iconName": "arrow",
                                "category": "Arrows",
                                "size": "24",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            write_svg(package_dir / "svg-original" / "arrow-24.svg")
            lock_path = package_dir / "flight-lock.json"
            commit = "d" * 40
            flight_icons.write_source_lock(package_dir, lock_path, commit)
            (package_dir / "LICENSE.md").write_text(
                "Mozilla Public License Version 2.0\nchanged rights text\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match"):
                flight_icons.generate_icons(package_dir, commit, lock_path)

    def test_missing_expected_license_marker_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "package.json").write_text(
                '{"version":"2.3.1"}', encoding="utf-8"
            )
            (root / "LICENSE_ICONS.md").write_text(
                "Unexpected license text\n", encoding="utf-8"
            )
            write_svg(root / "src/standard/check.svg")

            with self.assertRaisesRegex(ValueError, "missing expected marker"):
                redhat_icons.write_source_lock(root, root / "lock.json", "e" * 40)

    def test_unknown_flight_category_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory)
            (package_dir / "package.json").write_text(
                '{"version":"5.1.0"}', encoding="utf-8"
            )
            write_flight_license(package_dir)
            (package_dir / "catalog.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "fileName": "future-24",
                                "iconName": "future",
                                "category": "Future category",
                                "size": "24",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown categories"):
                flight_icons.write_source_lock(
                    package_dir, package_dir / "lock.json", "f" * 40
                )

    def test_candidate_lock_rejects_material_count_collapse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_path = root / "previous.json"
            candidate_path = root / "candidate.json"
            scope = {
                "includedCategories": ["Arrows"],
                "excludedCategories": ["Products", "Services"],
            }
            source_lock.write_lock(
                previous_path,
                {
                    "source": flight_icons.SOURCE,
                    **scope,
                    "indexedAssetCount": 100,
                    "indexedFamilyCount": 80,
                },
            )
            source_lock.write_lock(
                candidate_path,
                {
                    "source": flight_icons.SOURCE,
                    **scope,
                    "indexedAssetCount": 74,
                    "indexedFamilyCount": 80,
                },
            )

            with self.assertRaisesRegex(ValueError, "below 75% of prior"):
                source_lock.validate_candidate_lock(
                    candidate_path,
                    previous_path,
                    source=flight_icons.SOURCE,
                    count_fields=("indexedAssetCount", "indexedFamilyCount"),
                    scope_fields=("includedCategories", "excludedCategories"),
                )

    def test_candidate_lock_rejects_approved_scope_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_path = root / "previous.json"
            candidate_path = root / "candidate.json"
            base = {
                "source": redhat_icons.SOURCE,
                "includedCategories": ["standard", "ui", "microns"],
                "excludedCategories": ["social"],
                "indexedAssetCount": 100,
                "indexedFamilyCount": 90,
            }
            source_lock.write_lock(previous_path, base)
            source_lock.write_lock(
                candidate_path,
                {**base, "includedCategories": ["standard", "ui"]},
            )

            with self.assertRaisesRegex(ValueError, "approved scope"):
                source_lock.validate_candidate_lock(
                    candidate_path,
                    previous_path,
                    source=redhat_icons.SOURCE,
                    count_fields=("indexedAssetCount", "indexedFamilyCount"),
                    scope_fields=("includedCategories", "excludedCategories"),
                )

    def test_candidate_lock_requires_committed_prior_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_path = root / "candidate.json"
            source_lock.write_lock(
                candidate_path,
                {
                    "source": redhat_icons.SOURCE,
                    "includedCategories": ["standard", "ui", "microns"],
                    "excludedCategories": ["social"],
                    "indexedAssetCount": 100,
                    "indexedFamilyCount": 90,
                },
            )

            with self.assertRaisesRegex(ValueError, "Previous source lock is required"):
                source_lock.validate_candidate_lock(
                    candidate_path,
                    root / "missing.json",
                    source=redhat_icons.SOURCE,
                    count_fields=("indexedAssetCount", "indexedFamilyCount"),
                    scope_fields=("includedCategories", "excludedCategories"),
                )


if __name__ == "__main__":
    unittest.main()
