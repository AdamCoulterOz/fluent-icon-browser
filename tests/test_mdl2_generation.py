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


def write_fluent_icon(directory: Path, name: str) -> None:
    icon_dir = directory / name / "SVG"
    icon_dir.mkdir(parents=True)
    (icon_dir / f"ic_fluent_{name}_24_regular.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<path d="M0 0h24v24H0z" />'
        "</svg>",
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
                    sources=(
                        icon_data.source_record(
                            label="Fluent",
                            reference="example/fluent",
                            url="https://example.test/fluent",
                            revision="fluent-sha",
                        ),
                    ),
                    upstream_sha="fluent-sha",
                    cdn_base="https://cdn.example.test/fluent",
                    build_icons=lambda: [{"name": "access_time"}],
                ),
                icon_data.CollectionDescriptor(
                    key="segoe",
                    label="Segoe",
                    short_label="Segoe",
                    source="example/fabric",
                    sources=(
                        icon_data.source_record(
                            label="Fabric",
                            reference="example/fabric",
                            url="https://example.test/fabric",
                            revision="fabric-sha",
                        ),
                    ),
                    upstream_sha="fabric-sha",
                    cdn_base="https://cdn.example.test/fabric",
                    build_icons=lambda: [{"name": "accept"}],
                ),
                icon_data.CollectionDescriptor(
                    key="synthetic",
                    label="Synthetic Icons",
                    short_label="Synthetic",
                    source="example/synthetic",
                    sources=(
                        icon_data.source_record(
                            label="Synthetic",
                            reference="example/synthetic",
                            url="https://example.test/synthetic",
                            revision="synthetic-sha",
                        ),
                    ),
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
        self.assertEqual("example/synthetic", collections["synthetic"]["sources"][0]["reference"])
        self.assertEqual("Synthetic", collections["synthetic"]["sources"][0]["name"])

    def test_display_metadata_hygiene_preserves_hidden_search_terms(self) -> None:
        source_terms = [
            "branded",
            "k8s",
            "Azure Monitor",
            "raw_transport_id",
            "Microsoft.Insights/privateLinkScopes",
            "Microsoft.Insights",
            "template-d637b64eb57ae2872af4535105d96007ffce5f24643284cb798feffe324c2504-90",
            "This phrase is useful search context but too long to display",
            "and 24x7 support.",
            "including native vector search capabilities",
        ]
        collections = icon_data.assemble_collections(
            [
                icon_data.CollectionDescriptor(
                    key="synthetic",
                    label="Synthetic Icons",
                    short_label="Synthetic",
                    source="example/synthetic",
                    sources=(),
                    upstream_sha="synthetic-sha",
                    cdn_base="https://cdn.example.test/synthetic",
                    build_icons=lambda: [
                        {
                            "name": "test_icon",
                            "metaphors": source_terms,
                            "searchTerms": ["legacy_transport_name"],
                        }
                    ],
                )
            ]
        )
        icon = collections["synthetic"]["icons"][0]

        self.assertEqual(["branded", "k8s", "Azure Monitor"], icon["metaphors"])
        self.assertEqual(
            source_terms[3:] + ["legacy_transport_name"], icon["searchTerms"]
        )
        self.assertEqual(
            set(source_terms + ["legacy_transport_name"]),
            set(icon["metaphors"] + icon["searchTerms"]),
        )

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
                    fabric_branded_components_dir=Path(temp_dir) / "branded",
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
        source = payload["sets"]["fluent"]["sources"][0]
        self.assertEqual("microsoft/fluentui-system-icons", source["reference"])
        self.assertEqual("fluent-sha", source["revision"])
        ordinary_source, branded_source = payload["sets"]["segoe"]["sources"]
        self.assertEqual("MIT", ordinary_source["license"])
        self.assertEqual(
            "Microsoft Fabric Assets License", branded_source["license"]
        )
        self.assertEqual(
            "https://aka.ms/fluentui-assets-license",
            branded_source["licenseUrl"],
        )

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

    def test_fluent_categories_use_canonical_name_tokens_and_keep_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            icons_dir = Path(temp_dir) / "fluent"
            write_fluent_icon(icons_dir, "file_add")
            write_fluent_icon(icons_dir, "arrow_left")
            write_fluent_icon(icons_dir, "branch_request_closed")
            write_fluent_icon(icons_dir, "lock_closed")
            write_fluent_icon(icons_dir, "closed_caption")
            write_fluent_icon(icons_dir, "animal_paw_print")
            write_fluent_icon(icons_dir, "add_to_shopping_list")
            write_fluent_icon(icons_dir, "arrow_circle")
            write_fluent_icon(icons_dir, "add_circle")
            write_fluent_icon(icons_dir, "circle")
            write_fluent_icon(icons_dir, "unknown_widget")

            icons = icon_data.generate_fluent_icons(
                icons_dir=icons_dir,
                upstream_sha="fluent-sha",
                cdn_base="https://cdn.example.test/fluent",
            )

        icons_by_name = {icon["name"]: icon for icon in icons}
        self.assertEqual("Files & Documents", icons_by_name["file_add"]["category"])
        self.assertEqual("Actions & Navigation", icons_by_name["arrow_left"]["category"])
        self.assertEqual("General UI", icons_by_name["branch_request_closed"]["category"])
        self.assertEqual("Security & Privacy", icons_by_name["lock_closed"]["category"])
        self.assertEqual("Accessibility", icons_by_name["closed_caption"]["category"])
        self.assertEqual("Nature & Animals", icons_by_name["animal_paw_print"]["category"])
        self.assertEqual(
            "Commerce & Finance", icons_by_name["add_to_shopping_list"]["category"]
        )
        self.assertEqual(
            "Actions & Navigation", icons_by_name["arrow_circle"]["category"]
        )
        self.assertEqual(
            "Actions & Navigation", icons_by_name["add_circle"]["category"]
        )
        self.assertEqual("Shapes & Symbols", icons_by_name["circle"]["category"])
        self.assertEqual("General UI", icons_by_name["unknown_widget"]["category"])
        file_add = icons_by_name["file_add"]
        self.assertEqual("file_add", file_add["name"])
        self.assertEqual(["regular"], list(file_add["variants"]))
        self.assertEqual(24, file_add["variants"]["regular"]["defaultSize"])
        self.assertIn(
            "/file_add/SVG/ic_fluent_file_add_24_regular.svg",
            file_add["variants"]["regular"]["sizes"]["24"],
        )

    def test_segoe_categories_preserve_merged_source_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            ordinary_dir = temp_path / "ordinary"
            branded_dir = temp_path / "branded"
            ordinary_dir.mkdir()
            branded_dir.mkdir()
            for name in (
                "AccessLogo",
                "AzureInfo",
                "AzureInfoSolid",
                "ClassNotebookLogo",
                "Mail",
            ):
                write_component(ordinary_dir, name)
            for name in (
                "AzureInfo",
                "AzureLogo",
                "AmazonWebServicesLogo",
                "WordLogo",
                "VivaEngage",
                "GenericBrandedConcept",
            ):
                write_component(branded_dir, name)

            icons = icon_data.generate_fabric_icons(
                components_dir=ordinary_dir,
                branded_components_dir=branded_dir,
                upstream_sha="abc123",
                cdn_base="https://cdn.example.test/fluentui",
                metadata_by_id={
                    "generic_branded_concept": {"metaphors": ["raw_transport_id"]}
                },
            )
            assembled = icon_data.assemble_collections(
                [
                    icon_data.CollectionDescriptor(
                        key="segoe",
                        label="Segoe",
                        short_label="Segoe",
                        source="example/segoe",
                        sources=(),
                        upstream_sha="abc123",
                        cdn_base="https://cdn.example.test/fluentui",
                        build_icons=lambda: icons,
                    )
                ]
            )

        icons_by_name = {
            icon["name"]: icon
            for icon in assembled["segoe"]["icons"]
            if "normalizedTo" not in icon
        }
        self.assertEqual(
            "Microsoft Product Marks", icons_by_name["word_logo"]["category"]
        )
        self.assertEqual(
            "Microsoft Product Marks", icons_by_name["azure_logo"]["category"]
        )
        self.assertEqual(
            "Microsoft Product Marks", icons_by_name["access_logo"]["category"]
        )
        self.assertEqual(
            "Microsoft Product Marks",
            icons_by_name["class_notebook_logo"]["category"],
        )
        self.assertEqual(
            "Microsoft Product Marks", icons_by_name["viva_engage"]["category"]
        )
        self.assertEqual(
            "Microsoft Product UI", icons_by_name["azure_info"]["category"]
        )
        self.assertIn("filled", icons_by_name["azure_info"]["variants"])
        self.assertEqual(
            "Communication & Collaboration", icons_by_name["mail"]["category"]
        )
        self.assertEqual(
            "General UI", icons_by_name["generic_branded_concept"]["category"]
        )
        self.assertEqual(
            "General UI", icons_by_name["amazon_web_services_logo"]["category"]
        )
        self.assertIn("branded", icons_by_name["generic_branded_concept"]["metaphors"])
        self.assertIn("raw_transport_id", icons_by_name["generic_branded_concept"]["searchTerms"])
        self.assertNotIn("_identityNames", icons_by_name["azure_info"])
        self.assertNotIn("_hasBrandedMember", icons_by_name["azure_info"])

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
