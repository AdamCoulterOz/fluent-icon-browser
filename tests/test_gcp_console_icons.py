import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

import gcp_console_icons
from gcp_console_archive_notice import REFERENTIAL_FAIR_USE_NOTICE_BYTES


def module_url(module: str) -> str:
    return (
        "https://www.gstatic.com/_/mss/boq-cloud-client/_/js/"
        f"k=boq-cloud-client.{module}.en_US.eJ12PFaV9JU.es6.O/"
        "d=1/rs=AJ563L-weu0Pyzvwhm3bZLczzTwmMJgZxw/m=b"
    )


def route_map_bytes(records: dict[str, object]) -> bytes:
    return gcp_console_icons.XSSI_PREFIX + json.dumps({"routeDetails": records}).encode("utf-8")


def route_record(extension: str, module: str) -> tuple[str, str]:
    return (
        f"routes/features/home/extensions/{extension}",
        json.dumps(
            {
                "moduleUrl": module_url(module),
                "stylesheet": "https://www.gstatic.com/_/ss/boq-cloud-client/abc.css",
            }
        ),
    )


def discovered_two_modules() -> list[dict[str, str]]:
    return gcp_console_icons.discover_modules(route_map_bytes(dict([
        route_record("databases_home", "DatabasesHomeMicroUi"),
        route_record("storage_home", "StorageHomeStandaloneUi"),
    ])))


class GcpConsoleIconTests(unittest.TestCase):
    def test_discovers_public_routemap_modules_with_required_xssi_prefix(self) -> None:
        discovered = discovered_two_modules()
        self.assertEqual([
            {
                "id": "databases-home",
                "extension": "databases_home",
                "module": "DatabasesHomeMicroUi",
                "url": module_url("DatabasesHomeMicroUi"),
            },
            {
                "id": "storage-home",
                "extension": "storage_home",
                "module": "StorageHomeStandaloneUi",
                "url": module_url("StorageHomeStandaloneUi"),
            },
        ], discovered)
        with self.assertRaisesRegex(ValueError, "XSSI prefix"):
            gcp_console_icons.discover_modules(route_map_bytes({})[len(gcp_console_icons.XSSI_PREFIX):])
        with self.assertRaisesRegex(ValueError, "duplicated XSSI"):
            gcp_console_icons.discover_modules(gcp_console_icons.XSSI_PREFIX + route_map_bytes({}))

    def test_canonicalizes_routemap_query_and_fragment_before_pinning(self) -> None:
        tracked_url = f"{module_url('MacroLoungeMicroUi')}?wli=route-map#ignored"
        discovered = gcp_console_icons.discover_modules(route_map_bytes({
            "routes/features/home/extensions/macro_lounge": json.dumps({"moduleUrl": tracked_url}),
        }))
        self.assertEqual(module_url("MacroLoungeMicroUi"), discovered[0]["url"])
        self.assertNotIn("?", discovered[0]["url"])
        self.assertNotIn("#", discovered[0]["url"])

    def test_rejects_routemap_host_path_ambiguity_and_duplicate_candidates(self) -> None:
        cases = [
            ({"routes/features/home/extensions/bad_host": json.dumps({"url": module_url("BadHostMicroUi").replace("www.gstatic.com", "evil.example")})}, "www.gstatic.com"),
            ({"routes/features/home/extensions/bad_path": json.dumps({"url": "https://www.gstatic.com/_/mss/boq-cloud-client/_/js/not-a-console-module.js"})}, "k= segment"),
            ({"routes/features/home/extensions/ambiguous": json.dumps({"one": module_url("OneMicroUi"), "two": module_url("TwoMicroUi")})}, "exactly one"),
        ]
        for records, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                gcp_console_icons.discover_modules(route_map_bytes(records))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            gcp_console_icons.discover_modules(route_map_bytes(dict([
                route_record("one", "SharedMicroUi"),
                route_record("two", "SharedMicroUi"),
            ])))

    def test_pins_modules_without_evaluating_or_requiring_icons(self) -> None:
        discovered = discovered_two_modules()
        payloads = {
            module_url("DatabasesHomeMicroUi"): b"const icon = '<svg data-icon-name=\"database\"></svg>';",
            module_url("StorageHomeStandaloneUi"): b"throw new Error('would execute if evaluated');",
        }
        registry = gcp_console_icons.pin_modules(discovered, payloads.__getitem__)
        fixtures = {entry["id"]: payloads[entry["url"]] for entry in discovered}
        archive = gcp_console_icons.build_archive(registry, fixtures)
        self.assertEqual(1, gcp_console_icons.validate_archive(archive)["iconCount"])
        self.assertEqual(gcp_console_icons.ROUTE_MAP_URL, registry["routeMapUrl"])

    def test_builds_route_map_source_tree_and_deterministic_deploy_archive_with_injected_fetcher(self) -> None:
        route_map = route_map_bytes(dict([
            route_record("databases_home", "DatabasesHomeMicroUi"),
            route_record("storage_home", "StorageHomeStandaloneUi"),
        ]))
        payloads = {
            gcp_console_icons.ROUTE_MAP_URL: route_map,
            module_url("DatabasesHomeMicroUi"): b"const icon = '<svg data-icon-name=\"database\"></svg>';",
            module_url("StorageHomeStandaloneUi"): b"const icon = '<svg data-icon-name=\"storage\"></svg>';",
        }
        fetched_urls: list[str] = []

        def fetcher(url: str) -> bytes:
            fetched_urls.append(url)
            return payloads[url]

        source_tree = gcp_console_icons.build_source_tree_from_route_map(
            route_map, fetcher, workers=2
        )
        self.assertCountEqual(payloads.keys() - {gcp_console_icons.ROUTE_MAP_URL}, fetched_urls)
        self.assertEqual(2, json.loads(source_tree["manifest.json"])["iconCount"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gcp-console-icons"
            self.assertEqual(2, gcp_console_icons.write_source_tree(root, source_tree)["iconCount"])
            self.assertEqual(2, gcp_console_icons.validate_source_tree(root)["iconCount"])
            self.assertEqual(source_tree["source-lock.json"], (root / "source-lock.json").read_bytes())

            first_archive = gcp_console_icons.build_archive_from_source_tree(root)
            second_archive = gcp_console_icons.build_archive_from_source_tree(root)
            self.assertEqual(first_archive, second_archive)
            self.assertEqual(2, gcp_console_icons.validate_archive(first_archive)["iconCount"])
            with zipfile.ZipFile(BytesIO(first_archive)) as zip_file:
                self.assertEqual(source_tree["source-lock.json"], zip_file.read("source-lock.json"))

            manifest = json.loads((root / "manifest.json").read_bytes())
            manifest["icons"][0]["sha256"] = "0" * 64
            (root / "manifest.json").write_bytes(gcp_console_icons._canonical_json(manifest))
            with self.assertRaisesRegex(ValueError, "manifest digest"):
                gcp_console_icons.validate_source_tree(root)
        with self.assertRaisesRegex(ValueError, "worker count"):
            gcp_console_icons.build_source_tree_from_route_map(route_map, fetcher, workers=0)

    def test_builds_deterministic_collision_safe_svg_only_archive(self) -> None:
        discovered = discovered_two_modules()
        payloads = {
            module_url("DatabasesHomeMicroUi"): b"const icon = '<svg data-icon-name=\"shared\"></svg>';",
            module_url("StorageHomeStandaloneUi"): b"const icon = '<svg data-icon-name=\"shared\"></svg>';",
        }
        registry = gcp_console_icons.pin_modules(discovered, payloads.__getitem__)
        fixtures = {entry["id"]: payloads[entry["url"]] for entry in discovered}
        archive = gcp_console_icons.build_archive(registry, fixtures)
        self.assertEqual(archive, gcp_console_icons.build_archive(registry, fixtures))
        self.assertEqual(2, gcp_console_icons.validate_archive(archive)["iconCount"])
        with zipfile.ZipFile(BytesIO(archive)) as zip_file:
            databases_entry = gcp_console_icons._icon_entry_segment("shared", 0)
            storage_entry = gcp_console_icons._icon_entry_segment("shared", 0)
            self.assertEqual([
                "REFERENTIAL-FAIR-USE.md",
                f"icons/databases-home/{databases_entry}.svg",
                f"icons/storage-home/{storage_entry}.svg",
                "manifest.json",
                "source-lock.json",
            ], zip_file.namelist())
            self.assertEqual(REFERENTIAL_FAIR_USE_NOTICE_BYTES, zip_file.read("REFERENTIAL-FAIR-USE.md"))
            self.assertTrue(all(name.endswith(".svg") or name in {"REFERENTIAL-FAIR-USE.md", "manifest.json", "source-lock.json"} for name in zip_file.namelist()))
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) and info.external_attr == (0o100644 << 16) for info in zip_file.infolist()))

    def test_preserves_unsafe_or_absent_icon_names_with_safe_entry_segments(self) -> None:
        discovered = gcp_console_icons.discover_modules(route_map_bytes(dict([
            route_record("databases_home", "DatabasesHomeMicroUi"),
        ])))
        javascript = (
            b"const one = '<svg data-icon-name=\"../../outside\"></svg>';"
            b"const two = '<svg></svg>';"
            b"const three = '<svg></svg>';"
        )
        registry = gcp_console_icons.pin_modules(discovered, lambda _url: javascript)
        source_tree = gcp_console_icons.build_source_tree(registry, {"databases-home": javascript})
        manifest = json.loads(source_tree["manifest.json"])

        self.assertEqual(["../../outside", None, None], [entry["dataIconName"] for entry in manifest["icons"]])
        self.assertEqual([0, 1, 2], [entry["templateIndex"] for entry in manifest["icons"]])
        self.assertTrue(all(entry["path"].startswith("icons/databases-home/template-") for entry in manifest["icons"]))
        self.assertEqual(3, gcp_console_icons.validate_archive(gcp_console_icons._deterministic_zip(source_tree))["iconCount"])

        manifest["icons"][0]["dataIconName"] = "tampered"
        source_tree["manifest.json"] = gcp_console_icons._canonical_json(manifest)
        with self.assertRaisesRegex(ValueError, "entry name"):
            gcp_console_icons._validate_source_files(source_tree)

    def test_rejects_interpolation_digest_drift_and_tampered_integrity(self) -> None:
        discovered = gcp_console_icons.discover_modules(route_map_bytes(dict([
            route_record("databases_home", "DatabasesHomeMicroUi"),
        ])))
        interpolated = b"const icon = `<svg data-icon-name=\"database-${kind}\"></svg>`;"
        registry = gcp_console_icons.pin_modules(discovered, lambda _url: interpolated)
        with self.assertRaisesRegex(ValueError, "interpolated SVG"):
            gcp_console_icons.build_archive(registry, {"databases-home": interpolated})

        malformed = b"const icon = '<svg data-icon-name=\"database\">';"
        malformed_registry = gcp_console_icons.pin_modules(discovered, lambda _url: malformed)
        with self.assertRaisesRegex(ValueError, "malformed SVG"):
            gcp_console_icons.build_archive(malformed_registry, {"databases-home": malformed})

        valid = b"const icon = '<svg data-icon-name=\"database\"></svg>';"
        registry = gcp_console_icons.pin_modules(discovered, lambda _url: valid)
        with self.assertRaisesRegex(ValueError, "does not match its registry digest"):
            gcp_console_icons.build_archive(registry, {"databases-home": valid + b" "})

        archive = gcp_console_icons.build_archive(registry, {"databases-home": valid})
        with zipfile.ZipFile(BytesIO(archive)) as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        members["REFERENTIAL-FAIR-USE.md"] = b"altered\n"
        with self.assertRaisesRegex(ValueError, "notice"):
            gcp_console_icons.validate_archive(gcp_console_icons._deterministic_zip(members))

        with zipfile.ZipFile(BytesIO(archive)) as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        manifest = json.loads(members["manifest.json"])
        manifest["icons"][0]["sha256"] = "0" * 64
        members["manifest.json"] = gcp_console_icons._canonical_json(manifest)
        with self.assertRaisesRegex(ValueError, "manifest digest"):
            gcp_console_icons.validate_archive(gcp_console_icons._deterministic_zip(members))

        with zipfile.ZipFile(BytesIO(archive)) as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        manifest = json.loads(members["manifest.json"])
        manifest["sourceLock"]["sha256"] = "0" * 64
        members["manifest.json"] = gcp_console_icons._canonical_json(manifest)
        with self.assertRaisesRegex(ValueError, "manifest icon count"):
            gcp_console_icons.validate_archive(gcp_console_icons._deterministic_zip(members))

        with zipfile.ZipFile(BytesIO(archive)) as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        lock = json.loads(members["source-lock.json"])
        lock["modules"][0]["sha256"] = "0" * 64
        members["source-lock.json"] = gcp_console_icons._canonical_json(lock)
        with self.assertRaisesRegex(ValueError, "source lock integrity"):
            gcp_console_icons.validate_archive(gcp_console_icons._deterministic_zip(members))

        with self.assertRaisesRegex(ValueError, "Unsafe archive member path"):
            gcp_console_icons._deterministic_zip({"../unsafe.svg": b"<svg/>"})
        with zipfile.ZipFile(BytesIO(archive)) as source:
            members = {info.filename: source.read(info) for info in source.infolist()}
        members["icons/bitmap.png"] = b"not an SVG"
        with self.assertRaisesRegex(ValueError, "non-SVG asset"):
            gcp_console_icons.validate_archive(gcp_console_icons._deterministic_zip(members))

    def test_scans_svg_literals_after_micro_ui_regular_expressions(self) -> None:
        javascript = (
            b'const routePattern = /["\'`]/;'
            b'const icon = \'<svg data-icon-name="database"></svg>\';'
        )
        discovered = gcp_console_icons.discover_modules(route_map_bytes(dict([
            route_record("databases_home", "DatabasesHomeMicroUi"),
        ])))
        registry = gcp_console_icons.pin_modules(discovered, lambda _url: javascript)

        archive = gcp_console_icons.build_archive(registry, {"databases-home": javascript})

        self.assertEqual(1, gcp_console_icons.validate_archive(archive)["iconCount"])


if __name__ == "__main__":
    unittest.main()
