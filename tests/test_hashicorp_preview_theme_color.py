import json
import tempfile
import unittest
from pathlib import Path

import flight_icons


def write_svg(path: Path, markup: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markup, encoding="utf-8")


class HashiCorpPreviewThemeColorTests(unittest.TestCase):
    def test_black_paint_classifier_accepts_black_and_near_black_only(self) -> None:
        self.assertTrue(
            flight_icons.is_monochrome_black_svg(
                b'<svg><path fill="#000000" stroke="#000001"/></svg>'
            )
        )
        self.assertTrue(
            flight_icons.is_monochrome_black_svg(
                b'<svg><path style="fill: rgb(0, 0, 0); stroke: none"/></svg>'
            )
        )
        self.assertFalse(
            flight_icons.is_monochrome_black_svg(
                b'<svg><path fill="#7b42bc"/></svg>'
            )
        )
        self.assertFalse(
            flight_icons.is_monochrome_black_svg(
                b'<svg><path fill="#000000" stroke="#00a1df"/></svg>'
            )
        )

    def test_product_color_variant_marks_only_black_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package_dir = Path(directory)
            (package_dir / "package.json").write_text(
                '{"version":"5.1.0"}', encoding="utf-8"
            )
            (package_dir / "LICENSE.md").write_text(
                "Mozilla Public License Version 2.0\n", encoding="utf-8"
            )
            assets = [
                {
                    "fileName": "black-24",
                    "iconName": "black",
                    "category": "Products",
                    "size": "24",
                },
                {
                    "fileName": "black-color-16",
                    "iconName": "black-color",
                    "category": "Products",
                    "size": "16",
                },
                {
                    "fileName": "black-color-24",
                    "iconName": "black-color",
                    "category": "Products",
                    "size": "24",
                },
                {
                    "fileName": "purple-24",
                    "iconName": "purple",
                    "category": "Products",
                    "size": "24",
                },
                {
                    "fileName": "purple-color-24",
                    "iconName": "purple-color",
                    "category": "Products",
                    "size": "24",
                },
                {
                    "fileName": "multi-24",
                    "iconName": "multi",
                    "category": "Products",
                    "size": "24",
                },
                {
                    "fileName": "multi-color-24",
                    "iconName": "multi-color",
                    "category": "Products",
                    "size": "24",
                },
            ]
            (package_dir / "catalog.json").write_text(
                json.dumps({"assets": assets}), encoding="utf-8"
            )
            write_svg(package_dir / "svg-original/black-24.svg", '<svg><path/></svg>')
            write_svg(
                package_dir / "svg-original/black-color-16.svg",
                '<svg fill="#000001"><path/></svg>',
            )
            black_color_svg = '<svg><path fill="#000"/></svg>'
            black_color_path = package_dir / "svg-original/black-color-24.svg"
            write_svg(black_color_path, black_color_svg)
            write_svg(package_dir / "svg-original/purple-24.svg", '<svg><path/></svg>')
            write_svg(
                package_dir / "svg-original/purple-color-24.svg",
                '<svg><path fill="#7b42bc"/></svg>',
            )
            write_svg(package_dir / "svg-original/multi-24.svg", '<svg><path/></svg>')
            write_svg(
                package_dir / "svg-original/multi-color-24.svg",
                '<svg><path fill="#000" stroke="#00a1df"/></svg>',
            )

            lock_path = package_dir / "hashicorp-products-lock.json"
            commit = "b" * 40
            flight_icons.write_product_source_lock(package_dir, lock_path, commit)
            icons = {
                icon["name"]: icon
                for icon in flight_icons.generate_product_icons(package_dir, commit, lock_path)
            }

            self.assertTrue(icons["black"]["variants"]["color"]["previewThemeColor"])
            self.assertNotIn("previewThemeColor", icons["purple"]["variants"]["color"])
            self.assertNotIn("previewThemeColor", icons["multi"]["variants"]["color"])
            self.assertNotIn("previewThemeColor", icons["black"]["variants"]["regular"])
            self.assertEqual(black_color_svg, black_color_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
