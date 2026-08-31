import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import aws_icons


SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path fill="#ff9900" d="M0 0h32v32H0z"/></svg>'


def write_archive(path: Path, *, include_invalid_layout: bool = False) -> None:
    entries = {
        "Architecture-Service-Icons_20260731/Arch_Compute/16/Arch_Amazon-EC2_16.svg": SVG,
        "Architecture-Service-Icons_20260731/Arch_Compute/32/Arch_Amazon-EC2_32.svg": SVG,
        "Resource-Icons_20260731/Res_Storage/Res_Amazon-S3-Bucket_48.svg": SVG,
        "Resource-Icons_20260731/Res_General-Icons/Res_48_Dark/Res_AWS-Management-Console_48_Dark.svg": SVG,
        "Resource-Icons_20260731/Res_General-Icons/Res_48_Light/Res_AWS-Management-Console_48_Light.svg": SVG,
        "Category-Icons_20260731/Arch-Category_16/Arch-Category_Compute_16.svg": SVG,
        "Category-Icons_20260731/Arch-Category_32/Arch-Category_Compute_32.svg": SVG,
        "Architecture-Group-Icons_20260731/AWS-Cloud_32.svg": SVG,
        "Architecture-Group-Icons_20260731/AWS-Cloud_32_Dark.svg": SVG,
        "__MACOSX/Architecture-Group-Icons_20260731/._AWS-Cloud_32.svg": SVG,
        "Architecture-Service-Icons_20260731/.DS_Store": "metadata",
        "Architecture-Service-Icons_20260731/Arch_Compute/32/Arch_Amazon-EC2_32.png": "not a vector",
    }
    if include_invalid_layout:
        entries["unexpected/vector.svg"] = SVG
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry, content in entries.items():
            archive.writestr(entry, content)


class AwsIconTests(unittest.TestCase):
    def fixture_minimums(self):
        return patch.multiple(
            aws_icons,
            MINIMUM_ASSET_COUNT=1,
            MINIMUM_KIND_COUNTS={"Service": 1, "Resource": 1, "Category": 1, "Group": 1},
        )

    def test_writes_lock_and_generates_descriptor_only_families(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.fixture_minimums():
            root = Path(directory)
            archive_path = root / "architecture-icons.zip"
            lock_path = root / "aws-lock.json"
            write_archive(archive_path)

            lock = aws_icons.write_source_lock(
                archive_path,
                lock_path,
                "https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_20260731.example.zip",
            )
            icons = aws_icons.generate_icons(archive_path, lock_path)
            by_name = {icon["name"]: icon for icon in icons}

            self.assertEqual(9, lock["indexedAssetCount"])
            self.assertEqual(7, lock["indexedFamilyCount"])
            self.assertEqual(
                {"Service": 2, "Resource": 3, "Category": 2, "Group": 2},
                lock["kindCounts"],
            )
            self.assertEqual("20260731", lock["release"])
            self.assertEqual("Service / Compute", by_name["service_compute_amazon_ec2"]["category"])
            self.assertEqual(
                ["16", "32"],
                list(by_name["service_compute_amazon_ec2"]["variants"]["color"]["sizes"]),
            )
            self.assertEqual(
                ["color"],
                list(by_name["resource_general_icons_aws_management_console_dark"]["variants"]),
            )
            self.assertIn("resource_general_icons_aws_management_console_light", by_name)
            self.assertIn("group_aws_cloud", by_name)
            self.assertIn("group_aws_cloud_dark", by_name)
            category = by_name["category_compute"]
            self.assertEqual(["16", "32"], list(category["variants"]["color"]["sizes"]))

            descriptor = category["variants"]["color"]["sizes"]["32"]["remoteSource"]
            self.assertEqual("zip-svg-entry", descriptor["format"])
            self.assertEqual(lock["archiveSha256"], descriptor["archiveSha256"])
            self.assertEqual(
                next(entry["sha256"] for entry in lock["entries"] if entry["path"] == descriptor["entry"]),
                descriptor["entrySha256"],
            )
            for icon in icons:
                self.assertEqual(["color"], list(icon["variants"]))
                variant = next(iter(icon["variants"].values()))
                self.assertTrue(variant["preserveSourceColors"])
                self.assertFalse(variant["sourceCapabilities"]["currentColor"])
                self.assertFalse(variant["sourceCapabilities"]["boundingBox"])
            self.assertNotIn("<svg", json.dumps({"lock": lock, "icons": icons}))

    def test_rejects_archive_or_candidate_kind_count_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.fixture_minimums():
            root = Path(directory)
            archive_path = root / "architecture-icons.zip"
            lock_path = root / "aws-lock.json"
            candidate_path = root / "candidate.json"
            write_archive(archive_path)
            archive_url = "https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_20260731.example.zip"
            aws_icons.write_source_lock(archive_path, lock_path, archive_url)
            aws_icons.write_source_lock(archive_path, candidate_path, archive_url)

            changed_archive = root / "changed.zip"
            write_archive(changed_archive)
            with zipfile.ZipFile(changed_archive, "a") as archive:
                archive.writestr(
                    "Architecture-Group-Icons_20260731/Region_32.svg",
                    SVG.replace("#ff9900", "#232f3e"),
                )
            with self.assertRaisesRegex(ValueError, "does not match"):
                aws_icons.generate_icons(changed_archive, lock_path)

            candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
            candidate["kindCounts"]["Resource"] = 0
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Resource count collapsed"):
                aws_icons.validate_candidate_lock(candidate_path, lock_path)

    def test_rejects_unexpected_vector_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.fixture_minimums():
            archive_path = Path(directory) / "architecture-icons.zip"
            write_archive(archive_path, include_invalid_layout=True)
            with self.assertRaisesRegex(ValueError, "unexpected SVG root"):
                aws_icons.inspect_archive(archive_path)

    def test_discovers_only_the_architecture_icon_package_from_aws_page(self) -> None:
        archive_url = (
            "https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/"
            "architecture-icon-release/Icon-package_20260731.example.zip"
        )
        page = f'<a href="{archive_url}">Icon package</a><a href="{archive_url}">Again</a>'
        self.assertEqual(archive_url, aws_icons.discover_archive_url(lambda _url: page))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            aws_icons.discover_archive_url(lambda _url: "<a href='https://example.test/icons.zip'>x</a>")


if __name__ == "__main__":
    unittest.main()
