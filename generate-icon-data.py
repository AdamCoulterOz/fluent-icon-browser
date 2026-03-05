#!/usr/bin/env python3
"""Generate icon-data.json from Fluent System + Fabric MDL2 upstream assets."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

SUPPORTED_VARIANTS = ("regular", "filled", "color")
PREFERRED_SIZES = (24, 20, 16, 28, 32, 48, 12)
SVG_PATTERN = re.compile(
    r"^ic_fluent_(?P<icon_name>.*?)_(?P<size>\d+)_(?P<variant>regular|filled|color|light)(?:_(?P<direction>ltr|rtl))?\.svg$",
    flags=re.IGNORECASE,
)
FABRIC_ICON_FILE_PATTERN = re.compile(r"^(?P<name>.+)Icon\.tsx$")
FABRIC_DEFAULT_SIZE_PATTERN = re.compile(r"(?P<size>\d+)$")
KNOWN_FABRIC_SIZES = {8, 10, 12, 16, 20, 24, 28, 32, 48, 64}
SVG_BLOCK_PATTERN = re.compile(r"<svg[\s\S]*?</svg>", flags=re.IGNORECASE)
DISPLAY_NAME_PATTERN = re.compile(r"displayName:\s*'([^']+)'")
FABRIC_VARIANT_SUFFIXES = {"solid": "filled", "fill": "filled", "filled": "filled"}
SEMANTIC_INVERSE_TOKENS = {
    "add": "remove",
    "back": "forward",
    "collapse": "expand",
    "decrease": "increase",
    "down": "up",
    "expand": "collapse",
    "forward": "back",
    "in": "out",
    "increase": "decrease",
    "left": "right",
    "next": "previous",
    "out": "in",
    "previous": "next",
    "remove": "add",
    "right": "left",
    "up": "down",
}
FABRIC_GROUP_OVERRIDES: Dict[str, Dict[str, object]] = {
    # Known semantic remaps where MDL2 naming does not directly express style family.
    "away_status": {"base": "clock", "style": "filled"},
    "accept_medium": {"base": "accept", "style": "filled"},
    "blocked_site_solid12": {"base": "blocked_site", "style": "filled"},
    "double_chevron_down12": {"base": "double_chevron_down", "style": "filled"},
    "double_chevron_left12": {"base": "double_chevron_left", "style": "filled"},
    "double_chevron_right12": {"base": "double_chevron_right", "style": "filled"},
    "double_chevron_up12": {"base": "double_chevron_up", "style": "filled"},
    "end_point": {"base": "flag", "style": "filled"},
    "end_point_solid": {"base": "flag", "style": "filled"},
    "parking_location": {"base": "parking", "style": "regular"},
    "parking_location_mirrored": {
        "base": "parking",
        "style": "regular",
        "mirrored": True,
    },
    "pin_solid12": {"base": "pin", "style": "filled"},
    # Known MDL2 color icon.
    "viva_engage": {"style": "color"},
    # Known mirrored + numeric cases.
    "arrow_down_right_mirrored8": {"base": "arrow_down_right8", "mirrored": True},
    # MDL2 quirk: ArrowUpRight8 is effectively the filled pair for ArrowUpRight.
    "arrow_up_right8": {"base": "arrow_up_right", "style": "filled"},
    "arrow_up_right_mirrored8": {
        "base": "arrow_up_right",
        "style": "filled",
        "mirrored": True,
    },
    "edit_solid_mirrored12": {"base": "edit", "style": "filled", "mirrored": True},
    "uneditable_solid_mirrored12": {
        "base": "uneditable",
        "style": "filled",
        "mirrored": True,
    },
}


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def camel_to_snake(name: str) -> str:
    with_word_boundaries = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    with_internal_caps = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", with_word_boundaries)
    return with_internal_caps.replace("-", "_").lower()


def humanize_camel(name: str) -> str:
    with_word_boundaries = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    with_internal_caps = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", with_word_boundaries)
    return with_internal_caps.strip()


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


def build_fabric_source_url(cdn_base: str, upstream_sha: str, file_name: str) -> str:
    encoded_file = quote(file_name, safe="")
    return (
        f"{cdn_base}@{upstream_sha}/packages/react-icons-mdl2/src/components/{encoded_file}"
    )


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


def load_fabric_metadata(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: failed to parse {path}: {exc}")
        return {}

    entries = payload.get("icons") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}

    by_id: Dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        icon_id = entry.get("id")
        if not isinstance(icon_id, str) or not icon_id:
            continue
        by_id[icon_id] = entry

    return by_id


def get_svg_files(icon_dir: Path) -> Iterable[Path]:
    svg_dir = icon_dir / "SVG"
    if svg_dir.exists():
        return svg_dir.glob("*.svg")
    return icon_dir.glob("*.svg")


def resolve_sha(provided_sha: Optional[str], sha_file_name: str) -> str:
    if provided_sha and provided_sha.strip():
        return provided_sha.strip()

    sha_file = Path(sha_file_name)
    if sha_file.exists():
        return sha_file.read_text(encoding="utf-8").strip()

    return "main"


def parse_int_attribute(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    cleaned = value.strip().lower().replace("px", "")
    try:
        parsed = float(cleaned)
    except ValueError:
        return None

    if parsed.is_integer() and parsed > 0:
        return int(parsed)

    return None


def parse_viewbox_size(value: Optional[str]) -> Optional[int]:
    if not value:
        return None

    parts = value.replace(",", " ").split()
    if len(parts) != 4:
        return None

    try:
        width = float(parts[2])
        height = float(parts[3])
    except ValueError:
        return None

    if width <= 0 or height <= 0 or not width.is_integer() or not height.is_integer():
        return None

    width_int = int(width)
    height_int = int(height)
    if width_int == height_int and width_int <= 64:
        return width_int

    return None


def infer_fabric_default_size(icon_name: str, svg_text: str) -> int:
    try:
        root = ET.fromstring(svg_text)
        width = parse_int_attribute(root.attrib.get("width"))
        height = parse_int_attribute(root.attrib.get("height"))
        if width and height and width == height:
            return width
        viewbox_size = parse_viewbox_size(root.attrib.get("viewBox"))
        if viewbox_size:
            return viewbox_size
    except ET.ParseError:
        pass

    size_match = FABRIC_DEFAULT_SIZE_PATTERN.search(icon_name)
    if size_match:
        size = int(size_match.group("size"))
        if size in KNOWN_FABRIC_SIZES:
            return size

    return 16


def extract_fabric_svg(tsx_text: str, source_path: Path) -> Optional[str]:
    match = SVG_BLOCK_PATTERN.search(tsx_text)
    if not match:
        print(f"Warning: no <svg> block in {source_path}")
        return None

    svg_text = match.group(0)
    svg_text = re.sub(r"\sclassName=\{classes\.svg\}", "", svg_text)
    svg_text = svg_text.replace("\r\n", "\n").strip()

    try:
        ET.fromstring(svg_text)
    except ET.ParseError as exc:
        print(f"Warning: invalid SVG in {source_path}: {exc}")
        return None

    return svg_text


def extract_display_name(tsx_text: str, fallback: str) -> str:
    match = DISPLAY_NAME_PATTERN.search(tsx_text)
    if not match:
        return fallback

    display_name = match.group(1)
    if display_name.endswith("Icon"):
        return display_name[:-4]
    return display_name


def parse_fabric_member_variant(raw_id: str) -> dict:
    override = dict(FABRIC_GROUP_OVERRIDES.get(raw_id, {}))
    base_from_override = override.get("base")
    style_from_override = override.get("style")
    mirrored_from_override = bool(override.get("mirrored", False))

    tokens = raw_id.split("_")
    base_tokens: List[str] = []
    inferred_style: Optional[str] = None
    mirrored = mirrored_from_override

    for token in tokens:
        normalized = token.lower()
        if normalized == "mirrored" or normalized.startswith("mirrored"):
            mirrored = True
            continue

        mapped_style = FABRIC_VARIANT_SUFFIXES.get(normalized)
        if mapped_style and inferred_style is None:
            inferred_style = mapped_style
            continue

        base_tokens.append(token)

    base_id = str(base_from_override) if base_from_override else "_".join(base_tokens)
    if not base_id:
        base_id = raw_id

    style = str(style_from_override) if style_from_override else inferred_style or "regular"
    if style not in SUPPORTED_VARIANTS:
        style = "regular"

    return {
        "baseId": base_id,
        "style": style,
        "mirrored": mirrored,
    }


def normalize_search_alias(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def humanize_snake(name: str) -> str:
    parts = [part for part in name.split("_") if part]
    return " ".join(part.capitalize() for part in parts)


def find_semantic_inverse_candidates(icon_name: str, known_names: set[str]) -> list[str]:
    tokens = icon_name.split("_")
    candidates: set[str] = set()

    for index, token in enumerate(tokens):
        inverse_token = SEMANTIC_INVERSE_TOKENS.get(token)
        if not inverse_token:
            continue

        candidate_tokens = list(tokens)
        candidate_tokens[index] = inverse_token
        candidate = "_".join(candidate_tokens)
        if candidate != icon_name and candidate in known_names:
            candidates.add(candidate)

    return sorted(candidates)


def build_normalized_fabric_families(icons: list[dict]) -> None:
    if not icons:
        return

    icons_by_name = {icon["name"]: icon for icon in icons}
    names = set(icons_by_name)

    for icon in icons:
        semantic_inverses = find_semantic_inverse_candidates(icon["name"], names)
        if semantic_inverses:
            icon["semanticInverses"] = semantic_inverses

    parent = {name: name for name in names}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            if left_root < right_root:
                parent[right_root] = left_root
            else:
                parent[left_root] = right_root

    for icon in icons:
        for inverse in icon.get("semanticInverses", []):
            union(icon["name"], inverse)

    families: Dict[str, list[str]] = {}
    for name in names:
        root = find(name)
        families.setdefault(root, []).append(name)

    for family_members in families.values():
        if len(family_members) < 2:
            continue

        canonical_name = min(family_members)
        canonical_icon = icons_by_name[canonical_name]
        other_members = sorted(
            member for member in family_members if member != canonical_name
        )
        canonical_icon["normalizedAliases"] = other_members

        existing_aliases = canonical_icon.get("aliases", [])
        merged_aliases = sorted(
            {
                *[str(alias) for alias in existing_aliases],
                *other_members,
            }
        )
        if merged_aliases:
            canonical_icon["aliases"] = merged_aliases

        for member_name in other_members:
            icon = icons_by_name[member_name]
            icon["normalizedTo"] = canonical_name


def generate_fluent_icons(
    icons_dir: Path,
    upstream_sha: str,
    cdn_base: str,
) -> list[dict]:
    if not icons_dir.exists():
        raise FileNotFoundError(f"Fluent icons directory not found: {icons_dir}")

    icons: list[dict] = []
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
    return icons


def generate_fabric_icons(
    components_dir: Path,
    upstream_sha: str,
    cdn_base: str,
    metadata_by_id: Dict[str, dict],
) -> list[dict]:
    if not components_dir.exists():
        raise FileNotFoundError(
            f"Fabric components directory not found: {components_dir}"
        )

    members: list[dict] = []
    for component_file in sorted(components_dir.glob("*.tsx")):
        match = FABRIC_ICON_FILE_PATTERN.match(component_file.name)
        if not match:
            continue

        icon_id = match.group("name")
        tsx_text = component_file.read_text(encoding="utf-8")
        svg_text = extract_fabric_svg(tsx_text, component_file)
        if not svg_text:
            continue

        default_size = infer_fabric_default_size(icon_id, svg_text)
        source_url = build_fabric_source_url(cdn_base, upstream_sha, component_file.name)
        display_name = extract_display_name(tsx_text, icon_id)
        normalized_id = camel_to_snake(icon_id)
        parsed_variant = parse_fabric_member_variant(normalized_id)
        metadata = metadata_by_id.get(normalized_id, {})
        description = metadata.get("description") if isinstance(metadata, dict) else ""
        metaphors = metadata.get("metaphors") if isinstance(metadata, dict) else []

        members.append(
            {
                "rawId": normalized_id,
                "displayName": humanize_camel(display_name),
                "baseId": parsed_variant["baseId"],
                "style": parsed_variant["style"],
                "mirrored": parsed_variant["mirrored"],
                "defaultSize": default_size,
                "svgText": svg_text,
                "sourceUrl": source_url,
                "description": description if isinstance(description, str) else "",
                "metaphors": normalize_metaphors(metaphors),
            }
        )

    grouped: Dict[str, list[dict]] = {}
    for member in members:
        grouped.setdefault(member["baseId"], []).append(member)

    icons: list[dict] = []
    for base_id in sorted(grouped):
        group_members = grouped[base_id]

        def member_priority(member: dict) -> tuple[int, int, int]:
            style_rank = {"regular": 0, "filled": 1, "color": 2}.get(member["style"], 3)
            mirrored_rank = 1 if member["mirrored"] else 0
            exact_rank = 0 if member["rawId"] == base_id else 1
            return (style_rank, mirrored_rank, exact_rank)

        primary = min(group_members, key=member_priority)

        base_metadata = metadata_by_id.get(base_id, {})
        base_name = base_metadata.get("name") if isinstance(base_metadata, dict) else None
        display_name = (
            str(base_name)
            if isinstance(base_name, str) and base_name.strip()
            else (
                primary["displayName"]
                if primary["rawId"] == base_id
                else humanize_snake(base_id)
            )
        )

        description = (
            str(base_metadata.get("description", "")).strip()
            if isinstance(base_metadata, dict)
            else ""
        ) or primary["description"]

        metaphors: list[str] = []
        if isinstance(base_metadata, dict):
            metaphors.extend(normalize_metaphors(base_metadata.get("metaphors")))
        for member in group_members:
            metaphors.extend(member["metaphors"])
            metaphors.append(normalize_search_alias(member["rawId"]))
            metaphors.append(member["rawId"])
            metaphors.append(member["displayName"].lower())

        deduped_metaphors: list[str] = []
        seen_metaphors = set()
        for metaphor in metaphors:
            normalized = metaphor.strip().lower()
            if not normalized or normalized in seen_metaphors:
                continue
            seen_metaphors.add(normalized)
            deduped_metaphors.append(normalized)

        aliases = sorted(
            {
                member["rawId"]
                for member in group_members
                if member["rawId"] != base_id
            }
        )

        variants: Dict[str, dict] = {}
        for style in SUPPORTED_VARIANTS:
            style_members = [member for member in group_members if member["style"] == style]
            if not style_members:
                continue

            sizes: Dict[str, dict] = {}
            for member in style_members:
                size_key = str(member["defaultSize"])
                size_entry = sizes.setdefault(size_key, {})
                if member["mirrored"]:
                    size_entry.setdefault("mirroredSvg", member["svgText"])
                    size_entry.setdefault("mirroredSourceUrl", member["sourceUrl"])
                else:
                    size_entry.setdefault("svg", member["svgText"])
                    size_entry.setdefault("sourceUrl", member["sourceUrl"])

            has_mirrored = False
            for size_entry in sizes.values():
                if "mirroredSvg" in size_entry:
                    has_mirrored = True
                if "svg" not in size_entry and "mirroredSvg" in size_entry:
                    size_entry["svg"] = size_entry["mirroredSvg"]
                    if "mirroredSourceUrl" in size_entry:
                        size_entry["sourceUrl"] = size_entry["mirroredSourceUrl"]

            numeric_sizes = sorted(int(size) for size in sizes)
            default_size = pick_default_size(numeric_sizes)
            default_entry = sizes.get(str(default_size), {})

            variant_payload: Dict[str, object] = {
                "defaultSize": default_size,
                "sizes": sizes,
            }
            if isinstance(default_entry.get("svg"), str):
                variant_payload["previewSvg"] = default_entry["svg"]
            if isinstance(default_entry.get("sourceUrl"), str):
                variant_payload["sourceUrl"] = default_entry["sourceUrl"]
            if has_mirrored:
                variant_payload["hasMirrored"] = True

            variants[style] = variant_payload

        if not variants:
            continue

        icon_payload = {
            "name": base_id,
            "displayName": display_name,
            "description": description,
            "metaphors": deduped_metaphors,
            "variants": variants,
        }
        if aliases:
            icon_payload["aliases"] = aliases

        icons.append(icon_payload)

    icons.sort(key=lambda icon: icon["name"])
    build_normalized_fabric_families(icons)
    return icons


def generate_icon_data(
    fluent_icons_dir: Path,
    fabric_components_dir: Path,
    fabric_metadata_path: Path,
    output_file: Path,
    fluent_upstream_sha: str,
    fabric_upstream_sha: str,
    fluent_cdn_base: str,
    fabric_cdn_base: str,
) -> tuple[int, int]:
    fabric_metadata = load_fabric_metadata(fabric_metadata_path)

    fluent_icons = generate_fluent_icons(
        icons_dir=fluent_icons_dir,
        upstream_sha=fluent_upstream_sha,
        cdn_base=fluent_cdn_base,
    )
    fabric_icons = generate_fabric_icons(
        components_dir=fabric_components_dir,
        upstream_sha=fabric_upstream_sha,
        cdn_base=fabric_cdn_base,
        metadata_by_id=fabric_metadata,
    )

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "defaultSet": "fluent",
        "icons": fluent_icons,
        "sets": {
            "fluent": {
                "label": "Fluent System Icons",
                "source": "microsoft/fluentui-system-icons",
                "upstreamSha": fluent_upstream_sha,
                "cdnBase": fluent_cdn_base,
                "icons": fluent_icons,
            },
            "fabric": {
                "label": "Fabric MDL2 Icons",
                "source": "microsoft/fluentui/packages/react-icons-mdl2",
                "upstreamSha": fabric_upstream_sha,
                "cdnBase": fabric_cdn_base,
                "icons": fabric_icons,
            },
        },
    }

    output_file.write_text(
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )

    print(
        "Generated "
        f"{len(fluent_icons)} fluent icons + {len(fabric_icons)} fabric icons "
        f"-> {output_file}"
    )
    return len(fluent_icons), len(fabric_icons)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate icon-data.json from Fluent System and Fabric MDL2 sources"
    )
    parser.add_argument(
        "--fluent-icons-dir",
        default="assets",
        help="Path to Fluent icons directory (default: assets)",
    )
    parser.add_argument(
        "--fabric-components-dir",
        default=".tmp/fluentui/packages/react-icons-mdl2/src/components",
        help="Path to Fabric MDL2 icon component directory",
    )
    parser.add_argument(
        "--fabric-metadata",
        default="fabric-mdl2-metadata.json",
        help="Path to Fabric MDL2 metadata JSON",
    )
    parser.add_argument(
        "--icons-dir",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--output",
        default="icon-data.json",
        help="Output JSON path (default: icon-data.json)",
    )
    parser.add_argument(
        "--fluent-upstream-sha",
        default="",
        help="Upstream fluentui-system-icons SHA (defaults to .upstream-sha or main)",
    )
    parser.add_argument(
        "--fabric-upstream-sha",
        default="",
        help="Upstream fluentui SHA for react-icons-mdl2 (defaults to .upstream-fabric-sha or main)",
    )
    parser.add_argument(
        "--upstream-sha",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fluent-cdn-base",
        default="https://cdn.jsdelivr.net/gh/microsoft/fluentui-system-icons",
        help="CDN base URL for Fluent source SVGs",
    )
    parser.add_argument(
        "--fabric-cdn-base",
        default="https://cdn.jsdelivr.net/gh/microsoft/fluentui",
        help="CDN base URL for Fabric source files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    fluent_icons_dir = args.fluent_icons_dir
    if args.icons_dir and args.fluent_icons_dir == "assets":
        fluent_icons_dir = args.icons_dir

    fluent_sha_override = args.fluent_upstream_sha or args.upstream_sha
    fluent_upstream_sha = resolve_sha(fluent_sha_override, ".upstream-sha")
    fabric_upstream_sha = resolve_sha(args.fabric_upstream_sha, ".upstream-fabric-sha")

    generate_icon_data(
        fluent_icons_dir=Path(fluent_icons_dir),
        fabric_components_dir=Path(args.fabric_components_dir),
        fabric_metadata_path=Path(args.fabric_metadata),
        output_file=Path(args.output),
        fluent_upstream_sha=fluent_upstream_sha,
        fabric_upstream_sha=fabric_upstream_sha,
        fluent_cdn_base=args.fluent_cdn_base.rstrip("/"),
        fabric_cdn_base=args.fabric_cdn_base.rstrip("/"),
    )


if __name__ == "__main__":
    main()
