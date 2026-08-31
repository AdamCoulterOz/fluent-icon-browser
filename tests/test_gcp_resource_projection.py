import importlib.util
import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

import gcp_console_icons


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_gcp_resource_projection", REPO_ROOT / "generate-icon-data.py"
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


def write_source_tree(directory: Path, archive: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(archive)) as source:
        for info in source.infolist():
            target = directory / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(info))
        return json.loads(source.read(gcp_console_icons.MANIFEST_NAME))


class GcpResourceProjectionTests(unittest.TestCase):
    def test_promotes_named_resources_and_folds_source_variants(self) -> None:
        modules = {
            "app_design_center": "AppDesignCenterMicroUi",
            "dbmanageability": "DbmanageabilityMicroUi",
            "networking": "NetworkingMicroUi",
            "alpha": "AlphaMicroUi",
        }
        route_map = {
            f"routes/features/home/extensions/{extension}": json.dumps(
                {"moduleUrl": module_url(module)}
            )
            for extension, module in modules.items()
        }
        discovered = gcp_console_icons.discover_modules(
            gcp_console_icons.XSSI_PREFIX
            + json.dumps({"routeDetails": route_map}).encode("utf-8")
        )
        close_svg = b'<svg data-icon-name="closeIcon"><path d="M0 0h20v20H0z"/></svg>'
        payloads = {
            module_url("AppDesignCenterMicroUi"): (
                b"const cloudNat = '<svg data-icon-name=\"cloudNatIcon\" viewBox=\"0 0 20 20\"><path fill=\"#000\" d=\"M0 0h20v20H0z\"/></svg>';"
                b"const instanceGroup = '<svg data-icon-name=\"instanceGroupIcon\"><path d=\"M10 10\"/></svg>';"
                b"const close = '" + close_svg + b"';"
                b"const status = '<svg data-icon-name=\"statusInfoIcon\"><path d=\"M1 1\"/></svg>';"
            ),
            module_url("DbmanageabilityMicroUi"): (
                b"const sql = '<svg data-icon-name=\"cloudSqlIcon\"><path d=\"M2 2\"/></svg>';"
                b"const filter = '<svg data-icon-name=\"filterIcon\"><path d=\"M3 3\"/></svg>';"
            ),
            module_url("NetworkingMicroUi"): (
                b"const cloudNat = '<svg data-icon-name=\"cloudNatIcon\" viewBox=\"0 0 24 24\"><path fill=\"#4285f4\" d=\"M0 0h24v24H0z\"/></svg>';"
                b"const instanceGroup = '<svg data-icon-name=\"instanceGroupIcon\"><path d=\"M11 11\"/></svg>';"
                b"const close = '" + close_svg + b"';"
                b"const router = '<svg data-icon-name=\"routerIcon\"><path d=\"M4 4\"/></svg>';"
            ),
            module_url("AlphaMicroUi"): (
                b"const visible = '<svg data-icon-name=\"visibleIcon\"><path d=\"M5 5\"/></svg>';"
            ),
        }
        registry = gcp_console_icons.pin_modules(discovered, payloads.__getitem__)
        archive = gcp_console_icons.build_archive(
            registry,
            {record["id"]: payloads[record["url"]] for record in discovered},
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory) / "gcp-console-icons"
            manifest = write_source_tree(directory, archive)
            _, icons, _ = icon_data.generate_gcp_console_icons(directory)

        by_name = {icon["name"]: icon for icon in icons}
        cloud_nat = by_name["gcp_resource_icons_cloud_nat_icon"]
        self.assertEqual("Resource Icons", cloud_nat["category"])
        self.assertEqual(["regular", "color"], list(cloud_nat["variants"]))
        self.assertTrue(cloud_nat["variants"]["color"]["preserveSourceColors"])
        cloud_nat_entries = [
            entry for entry in manifest["icons"] if entry["dataIconName"] == "cloudNatIcon"
        ]
        self.assertEqual(
            {icon_data.gcp_family_name(entry) for entry in cloud_nat_entries},
            set(cloud_nat["aliases"])
            & {icon_data.gcp_family_name(entry) for entry in cloud_nat_entries},
        )
        self.assertEqual("Resource Icons", by_name["gcp_resource_icons_cloud_sql_icon"]["category"])
        self.assertEqual("Resource Icons", by_name["gcp_resource_icons_router_icon"]["category"])
        self.assertFalse(any(icon["displayName"] == "visibleIcon" for icon in icons))
        instance_group_entries = [
            entry
            for entry in manifest["icons"]
            if entry["dataIconName"] == "instanceGroupIcon"
        ]
        instance_group_icons = [
            icon
            for icon in icons
            if icon["name"].startswith("gcp_resource_icons_instance_group_icon_")
        ]
        self.assertEqual(2, len(instance_group_icons))
        self.assertTrue(all(list(icon["variants"]) == ["regular"] for icon in instance_group_icons))
        self.assertEqual(
            {icon_data.gcp_family_name(entry) for entry in instance_group_entries},
            {
                alias
                for icon in instance_group_icons
                for alias in icon["aliases"]
                if alias.startswith("gcp_")
            },
        )
        self.assertEqual("Common UI", next(icon["category"] for icon in icons if icon["displayName"] == "closeIcon"))
        self.assertEqual(
            {"Resource Icons", "Common UI"},
            {icon["category"] for icon in icons},
        )


if __name__ == "__main__":
    unittest.main()
