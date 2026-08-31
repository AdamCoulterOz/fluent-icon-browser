import importlib.util
import hashlib
import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import gcp_console_icons


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_gcp_catalog_icon_data", REPO_ROOT / "generate-icon-data.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load generate-icon-data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


icon_data = load_generator()


def module_url(module: str) -> str:
    return (
        "https://www.gstatic.com/_/mss/boq-cloud-client/_/js/"
        f"k=boq-cloud-client.{module}.en_US.eJ12PFaV9JU.es6.O/"
        "d=1/rs=AJ563L-weu0Pyzvwhm3bZLczzTwmMJgZxw/m=b"
    )


def build_archive() -> bytes:
    route_map = {
        "routes/features/home/extensions/databases_home": json.dumps(
            {"moduleUrl": module_url("DatabasesHomeMicroUi")}
        ),
        "routes/features/home/extensions/storage_home": json.dumps(
            {"moduleUrl": module_url("StorageHomeStandaloneUi")}
        ),
    }
    discovered = gcp_console_icons.discover_modules(
        gcp_console_icons.XSSI_PREFIX
        + json.dumps({"routeDetails": route_map}).encode("utf-8")
    )
    payloads = {
        module_url("DatabasesHomeMicroUi"): (
            b"const one = '<svg data-icon-name=\"database\" viewBox=\"0 0 20 20\">"
            b"<path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
            b"const two = '<svg data-icon-name=\"../../outside\" viewBox=\"0 0 20 20\">"
            b"<path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
            b"const three = '<svg data-icon-name=\"duplicate\" viewBox=\"0 0 20 20\">"
            b"<path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
            b"const four = '<svg data-icon-name=\"duplicate\" viewBox=\"0 0 20 20\">"
            b"<path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
            b"const five = '<svg viewBox=\"0 0 20 20\">"
            b"<path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
            b"const six = '<svg viewBox=\"0 0 20 20\">"
            b"<path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
        ),
        module_url("StorageHomeStandaloneUi"): (
            b"const icon = '<svg data-icon-name=\"cloud-service\" viewBox=\"0 0 24 24\">"
            b"<path fill=\"#4285f4\" d=\"M0 0h24v24H0z\"/></svg>';"
        ),
    }
    registry = gcp_console_icons.pin_modules(discovered, payloads.__getitem__)
    return gcp_console_icons.build_archive(
        registry,
        {record["id"]: payloads[record["url"]] for record in discovered},
    )


def write_directory(directory: Path, archive: bytes) -> None:
    directory.mkdir(exist_ok=True)
    with zipfile.ZipFile(BytesIO(archive)) as source:
        for info in source.infolist():
            target = directory / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(info))


def manifest_from_archive(archive: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(archive)) as source:
        return json.loads(source.read(gcp_console_icons.MANIFEST_NAME))


class GcpCatalogIntegrationTests(unittest.TestCase):
    def generate_payload(self, root: Path, archive: bytes) -> dict:
        directory = root / "gcp-console-icons"
        output_path = root / "icon-data.json"
        write_directory(directory, archive)
        with (
            patch.object(icon_data, "generate_fluent_icons", return_value=[]),
            patch.object(icon_data, "generate_fabric_icons", return_value=[]),
        ):
            icon_data.generate_icon_data(
                fluent_icons_dir=root / "fluent",
                fabric_components_dir=root / "segoe",
                fabric_branded_components_dir=None,
                fabric_metadata_path=root / "metadata.json",
                output_file=output_path,
                fluent_upstream_sha="fluent-sha",
                fabric_upstream_sha="segoe-sha",
                fluent_cdn_base="https://example.test/fluent",
                fabric_cdn_base="https://example.test/segoe",
                gcp_console_directory=directory,
            )
        return json.loads(output_path.read_text(encoding="utf-8"))

    def test_builds_stable_collision_safe_gcp_descriptors(self) -> None:
        archive = build_archive()
        manifest = manifest_from_archive(archive)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.generate_payload(root, archive)
            second = self.generate_payload(root, archive)

        self.assertEqual({"fabric": "segoe"}, first["setAliases"])
        self.assertEqual(["fluent", "segoe", "gcp"], list(first["sets"]))
        gcp = first["sets"]["gcp"]
        self.assertEqual("Google Cloud Console Icons", gcp["label"])
        self.assertEqual("Google Cloud", gcp["shortLabel"])
        self.assertIn("same-origin archive", gcp["source"])
        self.assertEqual("", gcp["sources"][0]["license"])
        self.assertEqual("", gcp["sources"][0]["licenseUrl"])

        icons = {icon["name"]: icon for icon in gcp["icons"]}
        self.assertEqual(
            set(icons),
            {icon["name"] for icon in second["sets"]["gcp"]["icons"]},
        )
        self.assertEqual(7, len(icons))

        def icon_for_entry(entry: dict) -> dict:
            return next(
                icon
                for icon in icons.values()
                if next(iter(icon["variants"].values()))["remoteSource"]["entry"]
                == entry["path"]
            )

        database_entry = next(
            entry for entry in manifest["icons"] if entry["dataIconName"] == "database"
        )
        unsafe_entry = next(
            entry
            for entry in manifest["icons"]
            if entry["dataIconName"] == "../../outside"
        )
        duplicate_entries = [
            entry for entry in manifest["icons"] if entry["dataIconName"] == "duplicate"
        ]
        null_entries = [
            entry for entry in manifest["icons"] if entry["dataIconName"] is None
        ]
        color_entry = next(
            entry
            for entry in manifest["icons"]
            if entry["dataIconName"] == "cloud-service"
        )

        regular = icon_for_entry(database_entry)
        unsafe = icon_for_entry(unsafe_entry)
        duplicates = [icon_for_entry(entry) for entry in duplicate_entries]
        nulls = [icon_for_entry(entry) for entry in null_entries]
        color = icon_for_entry(color_entry)
        self.assertEqual("Databases Home", regular["category"])
        self.assertEqual("Storage Home", color["category"])
        self.assertEqual(["regular"], list(regular["variants"]))
        self.assertEqual(["color"], list(color["variants"]))
        self.assertTrue(color["variants"]["color"]["preserveSourceColors"])
        self.assertEqual("database", regular["displayName"])
        self.assertEqual(["database", database_entry["name"]], regular["aliases"])
        self.assertIn("database", regular["metaphors"])
        self.assertIn(database_entry["name"], regular["metaphors"])
        self.assertEqual("../../outside", unsafe["displayName"])
        self.assertIn("../../outside", unsafe["metaphors"])
        self.assertIn(icon_data.gcp_snake_case(unsafe_entry["name"]), unsafe["name"])
        self.assertEqual(2, len({icon["name"] for icon in duplicates}))
        self.assertTrue(all(icon["displayName"] == "duplicate" for icon in duplicates))
        self.assertTrue(
            all(
                entry["name"] in icon["metaphors"]
                for entry, icon in zip(duplicate_entries, duplicates)
            )
        )
        self.assertEqual(2, len({icon["name"] for icon in nulls}))
        self.assertEqual(
            [entry["name"] for entry in null_entries],
            [icon["displayName"] for icon in nulls],
        )
        self.assertTrue(all("template" in icon["name"] for icon in nulls))

        descriptor = color["variants"]["color"]["remoteSource"]
        self.assertEqual(
            {
                "format": "same-origin-zip-svg-entry",
                "url": "gcp-console-icons.zip",
                "entry": color_entry["path"],
                "archiveSha256": descriptor["archiveSha256"],
                "entrySha256": descriptor["entrySha256"],
            },
            descriptor,
        )
        self.assertEqual(hashlib.sha256(archive).hexdigest(), descriptor["archiveSha256"])
        self.assertEqual(
            descriptor,
            color["variants"]["color"]["sizes"]["24"]["remoteSource"],
        )
        self.assertEqual(
            module_url("StorageHomeStandaloneUi"),
            color["variants"]["color"]["sourceUrl"],
        )
        self.assertEqual(["cloud-service", color_entry["name"]], color["aliases"])

    def test_rejects_malformed_directory_metadata_and_svg(self) -> None:
        archive = build_archive()
        manifest = manifest_from_archive(archive)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_directory = root / "gcp-console-icons"
            write_directory(source_directory, archive)
            lock_path = source_directory / gcp_console_icons.LOCK_NAME
            lock_path.write_bytes(lock_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "unexpected manifest or source lock"):
                icon_data.generate_gcp_console_icons(source_directory)

            write_directory(root / "missing-metadata", archive)
            (root / "missing-metadata" / gcp_console_icons.LOCK_NAME).unlink()
            with self.assertRaisesRegex(ValueError, "invalid manifest or source lock"):
                icon_data.generate_gcp_console_icons(root / "missing-metadata")

            write_directory(root / "changed-svg", archive)
            color_entry = next(
                entry
                for entry in manifest["icons"]
                if entry["dataIconName"] == "cloud-service"
            )
            changed_svg = root / "changed-svg" / color_entry["path"]
            changed_svg.write_bytes(changed_svg.read_bytes().replace(b"#4285f4", b"#ffffff"))
            with self.assertRaisesRegex(ValueError, "does not match its manifest digest"):
                icon_data.generate_gcp_console_icons(root / "changed-svg")

    def test_groups_cross_module_digest_matches_as_common_ui_with_legacy_aliases(self) -> None:
        route_map = {
            "routes/features/home/extensions/alpha": json.dumps(
                {"moduleUrl": module_url("AlphaMicroUi")}
            ),
            "routes/features/home/extensions/beta": json.dumps(
                {"moduleUrl": module_url("BetaStandaloneUi")}
            ),
        }
        discovered = gcp_console_icons.discover_modules(
            gcp_console_icons.XSSI_PREFIX
            + json.dumps({"routeDetails": route_map}).encode("utf-8")
        )
        shared_svg = b'<svg data-icon-name="closeIcon" viewBox="0 0 20 20"><path d="M0 0h20v20H0z"/></svg>'
        payloads = {
            module_url("AlphaMicroUi"): (
                b"const shared = '" + shared_svg + b"';"
                b"const sameName = '<svg data-icon-name=\"sameName\"><path d=\"M1 1\"/></svg>';"
            ),
            module_url("BetaStandaloneUi"): (
                b"const shared = '" + shared_svg + b"';"
                b"const sameName = '<svg data-icon-name=\"sameName\"><path d=\"M2 2\"/></svg>';"
            ),
        }
        registry = gcp_console_icons.pin_modules(discovered, payloads.__getitem__)
        archive = gcp_console_icons.build_archive(
            registry,
            {record["id"]: payloads[record["url"]] for record in discovered},
        )
        manifest = manifest_from_archive(archive)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self.generate_payload(root, archive)

        icons = payload["sets"]["gcp"]["icons"]
        self.assertEqual(3, len(icons))
        common = next(icon for icon in icons if icon["category"] == "Common UI")
        self.assertEqual("closeIcon", common["displayName"])
        self.assertTrue(common["name"].startswith("gcp_common_ui_close_icon_"))
        shared_entries = [entry for entry in manifest["icons"] if entry["dataIconName"] == "closeIcon"]
        self.assertEqual(2, len(shared_entries))
        self.assertEqual(
            {icon_data.gcp_family_name(entry) for entry in shared_entries},
            set(common["aliases"]) & {icon_data.gcp_family_name(entry) for entry in shared_entries},
        )
        self.assertEqual(
            2,
            len([icon for icon in icons if icon["displayName"] == "sameName"]),
        )

    def test_excludes_source_authored_blank_templates_but_keeps_source_tree_complete(self) -> None:
        route_map = {
            "routes/features/home/extensions/alpha": json.dumps(
                {"moduleUrl": module_url("AlphaMicroUi")}
            ),
        }
        discovered = gcp_console_icons.discover_modules(
            gcp_console_icons.XSSI_PREFIX
            + json.dumps({"routeDetails": route_map}).encode("utf-8")
        )
        payload = (
            b"const blank = '<svg data-icon-name=\"blank\"></svg>';"
            b"const visible = '<svg data-icon-name=\"visible\"><path d=\"M0 0h20v20H0z\"/></svg>';"
        )
        registry = gcp_console_icons.pin_modules(discovered, lambda _url: payload)
        archive = gcp_console_icons.build_archive(registry, {"alpha": payload})
        manifest = manifest_from_archive(archive)
        self.assertEqual(2, manifest["iconCount"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generated = self.generate_payload(root, archive)

        icons = generated["sets"]["gcp"]["icons"]
        self.assertEqual(["visible"], [icon["displayName"] for icon in icons])


if __name__ == "__main__":
    unittest.main()
