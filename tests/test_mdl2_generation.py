import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / file_name)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {file_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


icon_data = load_module("generate_icon_data", "generate-icon-data.py")
fabric_metadata = load_module(
    "generate_fabric_metadata",
    "generate-fabric-metadata.py",
)


def write_component(directory: Path, name: str) -> None:
    component_name = f"{name}Icon"
    (directory / f"{component_name}.tsx").write_text(
        "\n".join(
            [
                "import * as React from 'react';",
                f"const {component_name} = createSvgIcon({{",
                "  svg: ({ classes }) => (",
                '    <svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="0 0 2048 2048" className={classes.svg}>',
                '      <path d="M0 0h2048v2048H0z" />',
                "    </svg>",
                "  ),",
                f"  displayName: '{component_name}',",
                "});",
            ]
        ),
        encoding="utf-8",
    )


class Mdl2GenerationTests(unittest.TestCase):
    def test_collection_descriptors_support_an_additional_collection(self) -> None:
        collections = icon_data.assemble_collections(
            [
                icon_data.CollectionDescriptor(
                    key="fluent",
                    label="Fluent System Icons",
                    short_label="Fluent",
                    source="example/fluent",
                    sources=(),
                    upstream_sha="fluent-sha",
                    cdn_base="https://cdn.example.test/fluent",
                    build_icons=lambda: [{"name": "access_time"}],
                ),
                icon_data.CollectionDescriptor(
                    key="segoe",
                    label="Segoe",
                    short_label="Segoe",
                    source="example/fabric",
                    sources=("example/fabric",),
                    upstream_sha="fabric-sha",
                    cdn_base="https://cdn.example.test/fabric",
                    build_icons=lambda: [{"name": "accept"}],
                ),
                icon_data.CollectionDescriptor(
                    key="synthetic",
                    label="Synthetic Icons",
                    short_label="Synthetic",
                    source="example/synthetic",
                    sources=("example/synthetic",),
                    upstream_sha="synthetic-sha",
                    cdn_base="https://cdn.example.test/synthetic",
                    build_icons=lambda: [{"name": "test_icon"}],
                ),
            ]
        )

        self.assertEqual(["fluent", "segoe", "synthetic"], list(collections))
        self.assertEqual("Segoe", collections["segoe"]["label"])
        self.assertEqual("Segoe", collections["segoe"]["shortLabel"])
        self.assertEqual("Synthetic Icons", collections["synthetic"]["label"])
        self.assertEqual("Synthetic", collections["synthetic"]["shortLabel"])
        self.assertEqual([{"name": "test_icon"}], collections["synthetic"]["icons"])

    def test_generated_payload_uses_segoe_and_preserves_fabric_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "icon-data.json"
            with (
                patch.object(
                    icon_data,
                    "generate_fluent_icons",
                    return_value=[{"name": "access_time"}],
                ),
                patch.object(
                    icon_data,
                    "generate_fabric_icons",
                    return_value=[{"name": "accept"}],
                ),
            ):
                counts = icon_data.generate_icon_data(
                    fluent_icons_dir=Path(temp_dir) / "fluent",
                    fabric_components_dir=Path(temp_dir) / "mdl2",
                    fabric_branded_components_dir=None,
                    fabric_metadata_path=Path(temp_dir) / "metadata.json",
                    output_file=output_file,
                    fluent_upstream_sha="fluent-sha",
                    fabric_upstream_sha="mdl2-sha",
                    fluent_cdn_base="https://cdn.example.test/fluent",
                    fabric_cdn_base="https://cdn.example.test/mdl2",
                )

            payload = json.loads(output_file.read_text(encoding="utf-8"))

        self.assertEqual((1, 1), counts)
        self.assertEqual(["fluent", "segoe"], list(payload["sets"]))
        self.assertEqual({"fabric": "segoe"}, payload["setAliases"])
        self.assertEqual("Segoe", payload["sets"]["segoe"]["label"])
        self.assertEqual("Segoe", payload["sets"]["segoe"]["shortLabel"])

    def test_branded_components_are_included_and_tagged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ordinary_dir = temp_path / "ordinary"
            branded_dir = temp_path / "branded"
            ordinary_dir.mkdir()
            branded_dir.mkdir()
            write_component(ordinary_dir, "Mail")
            write_component(ordinary_dir, "VivaEngage")
            write_component(branded_dir, "VivaEngage")
            write_component(branded_dir, "WordLogo")

            icons = icon_data.generate_fabric_icons(
                components_dir=ordinary_dir,
                branded_components_dir=branded_dir,
                upstream_sha="abc123",
                cdn_base="https://cdn.example.test/fluentui",
                metadata_by_id={},
            )
            icons_by_name = {icon["name"]: icon for icon in icons}

            self.assertNotIn("branded", icons_by_name["mail"]["metaphors"])
            self.assertIn("branded", icons_by_name["word_logo"]["metaphors"])
            self.assertIn(
                "/packages/react-icons-mdl2-branded/src/components/WordLogoIcon.tsx",
                icons_by_name["word_logo"]["variants"]["regular"]["sourceUrl"],
            )
            self.assertIn("branded", icons_by_name["viva_engage"]["metaphors"])
            self.assertIn(
                "/packages/react-icons-mdl2-branded/src/components/VivaEngageIcon.tsx",
                icons_by_name["viva_engage"]["variants"]["color"]["sourceUrl"],
            )

    def test_metadata_deduplicates_sources_and_keeps_branded_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ordinary_dir = temp_path / "ordinary"
            branded_dir = temp_path / "branded"
            output_file = temp_path / "metadata.json"
            ordinary_dir.mkdir()
            branded_dir.mkdir()
            write_component(ordinary_dir, "Mail")
            write_component(ordinary_dir, "VivaEngage")
            write_component(branded_dir, "VivaEngage")
            write_component(branded_dir, "WordLogo")

            count = fabric_metadata.generate_metadata(
                ordinary_dir,
                output_file,
                branded_components_dir=branded_dir,
            )
            payload = json.loads(output_file.read_text(encoding="utf-8"))
            metadata_by_id = {
                entry["id"]: entry for entry in payload["icons"]
            }

            self.assertEqual(3, count)
            self.assertEqual(3, payload["count"])
            self.assertNotIn("branded", metadata_by_id["mail"]["metaphors"])
            self.assertIn("branded", metadata_by_id["viva_engage"]["metaphors"])
            self.assertIn("branded", metadata_by_id["word_logo"]["metaphors"])
            self.assertEqual(
                [
                    "microsoft/fluentui/packages/react-icons-mdl2",
                    "microsoft/fluentui/packages/react-icons-mdl2-branded",
                ],
                payload["sources"],
            )


if __name__ == "__main__":
    unittest.main()
