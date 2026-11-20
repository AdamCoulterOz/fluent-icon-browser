import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_sync_projections", REPO_ROOT / "generate-icon-data.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load generate-icon-data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


icon_data = load_generator()


class SyncProjectionTests(unittest.TestCase):
    def test_non_gcp_projection_preserves_exact_gcp_set_and_picker_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_path = root / "base.json"
            output_path = root / "output.json"
            original_gcp = {"label": "Google Cloud", "icons": [{"name": "old"}]}
            base_path.write_text(
                json.dumps(
                    {
                        "generatedAt": "old",
                        "defaultSet": "fluent",
                        "icons": [],
                        "setAliases": {"fabric": "segoe"},
                        "sets": {
                            "fluent": {"old": "fluent"},
                            "gcp": original_gcp,
                            "segoe": {"old": "segoe"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "metadata.json").write_text("{}", encoding="utf-8")
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
                    fluent_upstream_sha="fluent",
                    fabric_upstream_sha="segoe",
                    fluent_cdn_base="https://example.test/fluent",
                    fabric_cdn_base="https://example.test/segoe",
                    preserve_gcp_from=base_path,
                )

            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(["fluent", "gcp", "segoe"], list(result["sets"]))
            self.assertEqual(original_gcp, result["sets"]["gcp"])

    def test_gcp_projection_preserves_non_gcp_sets_and_failure_keeps_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_path = root / "base.json"
            output_path = root / "output.json"
            non_gcp = {"label": "Fluent", "icons": [{"name": "keep"}]}
            base_path.write_text(
                json.dumps(
                    {
                        "generatedAt": "old",
                        "defaultSet": "fluent",
                        "icons": [{"name": "keep"}],
                        "setAliases": {"fabric": "segoe"},
                        "sets": {"fluent": non_gcp, "gcp": {"icons": []}},
                    }
                ),
                encoding="utf-8",
            )
            descriptor = icon_data.CollectionDescriptor(
                key="gcp",
                label="Google Cloud",
                short_label="Google Cloud",
                source="validated",
                sources=(),
                upstream_sha="new",
                cdn_base="gcp-console-icons.zip",
                build_icons=lambda: [{"name": "replacement"}],
            )
            with patch.object(icon_data, "gcp_collection_descriptor", return_value=descriptor):
                icon_data.generate_gcp_projection(base_path, root / "tree", output_path)
            result = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(non_gcp, result["sets"]["fluent"])
            self.assertEqual([{"name": "replacement"}], result["sets"]["gcp"]["icons"])

            output_path.write_text("last-good", encoding="utf-8")
            with patch.object(
                icon_data, "gcp_collection_descriptor", side_effect=ValueError("bad tree")
            ):
                with self.assertRaisesRegex(ValueError, "bad tree"):
                    icon_data.generate_gcp_projection(base_path, root / "tree", output_path)
            self.assertEqual("last-good", output_path.read_text(encoding="utf-8"))

    def test_committed_gcp_tree_archive_digest_matches_index(self) -> None:
        index = json.loads((REPO_ROOT / "icon-data.json").read_text(encoding="utf-8"))
        descriptor = icon_data.gcp_collection_descriptor(REPO_ROOT / "gcp-console-icons")
        generated = icon_data.assemble_collections((descriptor,))["gcp"]
        self.assertEqual(
            index["sets"]["gcp"]["sources"][0]["digest"],
            generated["sources"][0]["digest"],
        )


if __name__ == "__main__":
    unittest.main()
