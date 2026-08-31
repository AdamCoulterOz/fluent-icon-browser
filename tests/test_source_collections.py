import json
import tempfile
import unittest
from pathlib import Path

import flight_icons
import redhat_icons
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


class SourceCollectionTests(unittest.TestCase):
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
