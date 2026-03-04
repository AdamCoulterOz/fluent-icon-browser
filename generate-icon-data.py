#!/usr/bin/env python3
"""Generate icon-data.json from Fluent UI assets using CDN URLs."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import quote

SUPPORTED_VARIANTS = ("regular", "filled", "color")
PREFERRED_SIZES = (24, 20, 16, 28, 32, 48, 12)
SVG_PATTERN = re.compile(
    r"^ic_fluent_(?P<icon_name>.*?)_(?P<size>\d+)_(?P<variant>regular|filled|color|light)(?:_(?P<direction>ltr|rtl))?\.svg$",
    flags=re.IGNORECASE,
)


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def read_metadata(path: Path) -> Dict:
    if not path.exists():
        return {"description": "", "metaphor": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: failed to parse {path}: {exc}")
        return {"description": "", "metaphor": []}


def candidate_score(size: int, direction: Optional[str]) -> tuple[int, int, int]:
    if size in PREFERRED_SIZES:
        size_rank = PREFERRED_SIZES.index(size)
    else:
        size_rank = len(PREFERRED_SIZES) + size

    direction_rank = {None: 0, "ltr": 1, "rtl": 2}.get(direction, 3)
    return (size_rank, direction_rank, size)


def build_cdn_url(
    cdn_base: str, upstream_sha: str, icon_folder_name: str, svg_file_name: str
) -> str:
    encoded_folder = quote(icon_folder_name, safe="")
    encoded_file = quote(svg_file_name, safe="")
    return f"{cdn_base}@{upstream_sha}/assets/{encoded_folder}/SVG/{encoded_file}"


def pick_default_size(available_sizes: list[int]) -> int:
    for preferred_size in PREFERRED_SIZES:
        if preferred_size in available_sizes:
            return preferred_size
    return min(available_sizes)


def pick_variants(
    icon_dir: Path,
    svg_files: Iterable[Path],
    upstream_sha: str,
    cdn_base: str,
) -> Dict[str, dict]:
    candidates: Dict[str, Dict[int, list[tuple[tuple[int, int, int], Path]]]] = {
        variant: {} for variant in SUPPORTED_VARIANTS
    }

    for svg_file in svg_files:
        match = SVG_PATTERN.match(svg_file.name)
        if not match:
            continue

        variant = match.group("variant").lower()
        if variant not in candidates:
            continue

        size = int(match.group("size"))
        direction = match.group("direction")
        candidates[variant].setdefault(size, []).append(
            (candidate_score(size, direction), svg_file)
        )

    variants: Dict[str, dict] = {}
    for variant, size_map in candidates.items():
        if not size_map:
            continue

        urls_by_size: dict[str, str] = {}
        numeric_sizes: list[int] = []

        for size in sorted(size_map):
            files = size_map[size]
            _score, svg_file = min(files, key=lambda entry: entry[0])
            url = build_cdn_url(cdn_base, upstream_sha, icon_dir.name, svg_file.name)
            urls_by_size[str(size)] = url
            numeric_sizes.append(size)

        numeric_sizes.sort()
        default_size = pick_default_size(numeric_sizes)
        variants[variant] = {
            "defaultSize": default_size,
            "previewUrl": urls_by_size[str(default_size)],
            "sizes": urls_by_size,
        }

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


def resolve_upstream_sha(provided_sha: Optional[str]) -> str:
    if provided_sha and provided_sha.strip():
        return provided_sha.strip()

    sha_file = Path(".upstream-sha")
    if sha_file.exists():
        return sha_file.read_text(encoding="utf-8").strip()

    return "main"


def generate_icon_data(
    icons_dir: Path,
    output_file: Path,
    upstream_sha: str,
    cdn_base: str,
) -> int:
    if not icons_dir.exists():
        raise FileNotFoundError(f"Icons directory not found: {icons_dir}")

    icons = []
    icon_dirs = sorted(path for path in icons_dir.iterdir() if path.is_dir())

    for icon_dir in icon_dirs:
        variants = pick_variants(
            icon_dir=icon_dir,
            svg_files=get_svg_files(icon_dir),
            upstream_sha=upstream_sha,
            cdn_base=cdn_base,
        )
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
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "upstreamSha": upstream_sha,
        "cdnBase": cdn_base,
        "icons": icons,
    }
    output_file.write_text(
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )

    print(f"Generated {len(icons)} icons -> {output_file}")
    return len(icons)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate icon-data.json from icon folders"
    )
    parser.add_argument(
        "--icons-dir",
        default="assets",
        help="Path to icons directory (default: assets)",
    )
    parser.add_argument(
        "--output",
        default="icon-data.json",
        help="Output JSON path (default: icon-data.json)",
    )
    parser.add_argument(
        "--upstream-sha",
        default="",
        help="Upstream fluentui-system-icons SHA (defaults to .upstream-sha or main)",
    )
    parser.add_argument(
        "--cdn-base",
        default="https://cdn.jsdelivr.net/gh/microsoft/fluentui-system-icons",
        help="CDN base URL for source SVGs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    upstream_sha = resolve_upstream_sha(args.upstream_sha)
    generate_icon_data(
        icons_dir=Path(args.icons_dir),
        output_file=Path(args.output),
        upstream_sha=upstream_sha,
        cdn_base=args.cdn_base.rstrip("/"),
    )


if __name__ == "__main__":
    main()
