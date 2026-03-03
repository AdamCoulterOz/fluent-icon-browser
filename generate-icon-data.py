#!/usr/bin/env python3
"""Generate icon-data.json from icon folders."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, Optional

SUPPORTED_VARIANTS = ("regular", "filled", "color")
PREFERRED_SIZES = (24, 20, 16, 28, 32, 48)
SVG_PATTERN = re.compile(
    r".*(?:_(?P<size>\d+))?_(?P<variant>regular|filled|color|light)(?:_(?P<direction>ltr|rtl))?\.svg$",
    flags=re.IGNORECASE,
)


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Warning: failed to read {path}: {exc}")
        return None


def read_metadata(path: Path) -> Dict:
    if not path.exists():
        return {"description": "", "metaphor": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: failed to parse {path}: {exc}")
        return {"description": "", "metaphor": []}


def candidate_score(size: Optional[int], direction: Optional[str]) -> tuple[int, int, int]:
    if size is None:
        size_rank = -1
        normalized_size = 0
    elif size in PREFERRED_SIZES:
        size_rank = PREFERRED_SIZES.index(size)
        normalized_size = size
    else:
        size_rank = len(PREFERRED_SIZES) + size
        normalized_size = size

    direction_rank = {None: 0, "ltr": 1, "rtl": 2}.get(direction, 3)
    return (size_rank, direction_rank, normalized_size)


def pick_variants(svg_files: Iterable[Path]) -> Dict[str, str]:
    candidates: Dict[str, list[tuple[tuple[int, int, int], Path]]] = {
        variant: [] for variant in SUPPORTED_VARIANTS
    }

    for svg_file in svg_files:
        match = SVG_PATTERN.match(svg_file.name)
        if not match:
            continue

        variant = match.group("variant").lower()
        if variant not in candidates:
            continue

        size_group = match.group("size")
        size = int(size_group) if size_group else None
        direction = match.group("direction")
        candidates[variant].append((candidate_score(size, direction), svg_file))

    variants: Dict[str, str] = {}
    for variant, files in candidates.items():
        if not files:
            continue
        _score, svg_file = min(files, key=lambda entry: entry[0])
        content = read_text(svg_file)
        if content:
            variants[variant] = content

    return variants


def normalize_metaphors(raw_metaphors: object) -> list[str]:
    if isinstance(raw_metaphors, list):
        return [str(item) for item in raw_metaphors]
    if isinstance(raw_metaphors, str) and raw_metaphors.strip():
        return [raw_metaphors]
    return []


def get_svg_files(icon_dir: Path) -> Iterable[Path]:
    svg_dir = icon_dir / "SVG"
    if svg_dir.exists():
        return svg_dir.glob("*.svg")
    return icon_dir.glob("*.svg")


def generate_icon_data(icons_dir: Path, output_file: Path) -> int:
    if not icons_dir.exists():
        raise FileNotFoundError(f"Icons directory not found: {icons_dir}")

    icons = []
    icon_dirs = sorted(path for path in icons_dir.iterdir() if path.is_dir())

    for icon_dir in icon_dirs:
        variants = pick_variants(get_svg_files(icon_dir))
        if not variants:
            continue

        metadata = read_metadata(icon_dir / "metadata.json")
        description = metadata.get("description")

        icons.append(
            {
                "name": slugify(icon_dir.name),
                "displayName": icon_dir.name,
                "description": description if isinstance(description, str) else "",
                "metaphors": normalize_metaphors(metadata.get("metaphor")),
                "variants": variants,
            }
        )

    icons.sort(key=lambda icon: icon["name"])
    output_file.write_text(
        f"{json.dumps(icons, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )

    print(f"Generated {len(icons)} icons -> {output_file}")
    return len(icons)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate icon-data.json from icon folders"
    )
    parser.add_argument(
        "--icons-dir",
        default="consolidated",
        help="Path to icons directory (supports consolidated/* or assets/* layouts)",
    )
    parser.add_argument(
        "--output",
        default="icon-data.json",
        help="Output JSON path (default: icon-data.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_icon_data(Path(args.icons_dir), Path(args.output))


if __name__ == "__main__":
    main()
