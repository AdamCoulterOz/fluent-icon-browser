#!/usr/bin/env python3
"""Generate icon-data.json from Fluent System + Fabric MDL2 upstream assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
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
SET_ALIASES = {"fabric": "segoe"}


class CollectionDescriptor:
    """Private generator description for one coherent icon collection."""

    __slots__ = (
        "key",
        "label",
        "short_label",
        "source",
        "sources",
        "upstream_sha",
        "cdn_base",
        "build_icons",
    )

    def __init__(
        self,
        *,
        key: str,
        label: str,
        short_label: str,
        source: str,
        sources: tuple[dict, ...],
        upstream_sha: str,
        cdn_base: str,
        build_icons: Callable[[], list[dict]],
    ) -> None:
        self.key = key
        self.label = label
        self.short_label = short_label
        self.source = source
        self.sources = sources
        self.upstream_sha = upstream_sha
        self.cdn_base = cdn_base
        self.build_icons = build_icons


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
    if "raw.githubusercontent.com/" in cdn_base:
        return f"{cdn_base}/{upstream_sha}/assets/{encoded_folder}/SVG/{encoded_file}"
    return f"{cdn_base}@{upstream_sha}/assets/{encoded_folder}/SVG/{encoded_file}"


def build_fabric_source_url(
    cdn_base: str,
    upstream_sha: str,
    package_name: str,
    file_name: str,
) -> str:
    encoded_file = quote(file_name, safe="")
    return (
        f"{cdn_base}@{upstream_sha}/packages/{package_name}/src/components/{encoded_file}"
    )


def source_record(
    *,
    label: str,
    reference: str,
    url: str,
    revision: str,
    license_name: str = "",
    license_url: str = "",
    digest: str = "",
) -> dict:
    """Return the stable, human-facing provenance shape for a source."""

    return {
        "label": label,
        "name": label,
        "reference": reference,
        "url": url,
        "revision": revision,
        "license": license_name,
        "licenseUrl": license_url,
        "digest": digest,
    }


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


def gcp_snake_case(value: str) -> str:
    """Return a stable readable identifier for a validated GCP archive field."""

    return re.sub(
        r"_+",
        "_",
        re.sub(r"[^a-z0-9]+", "_", camel_to_snake(value).lower()),
    ).strip("_")


def humanize_gcp_extension(extension: str) -> str:
    return humanize_snake(gcp_snake_case(extension))


GCP_RESOURCE_ICON_NAMES_BY_EXTENSION = {
    "app_design_center": frozenset(
        {
            "standardClusterIcon",
            "cloudNatIcon",
            "deviceTemplateIcon",
            "firebaseIcon",
            "firewallIcon",
            "instanceGroupIcon",
            "instanceTemplateIcon",
            "privateServiceConnectIcon",
            "secretManagerIcon",
            "serviceAccountsIcon",
            "vpcIcon",
        }
    ),
    "dbmanageability": frozenset(
        {
            "dataCanvasIcon",
            "dataPreparationIcon",
            "tablePartitionedIcon",
            "tableShardedIcon",
            "tableViewIcon",
            "folderDataIcon",
            "teamDriveIcon",
            "datasetsIcon",
            "flumeWorkerIcon",
            "tableIcon",
            "folderIcon",
            "computeEngineIcon",
            "domainIcon",
            "alloydbIcon",
            "bigqueryIcon",
            "bigtableIcon",
            "cloudSqlIcon",
            "databasesIcon",
            "firestoreIcon",
            "memorystoreIcon",
            "oracleIcon",
            "spannerIcon",
        }
    ),
    "networking": frozenset(
        {
            "interconnectIcon",
            "routerIcon",
            "apisIcon",
            "cloudNatIcon",
            "connectIcon",
            "endpointsIcon",
            "instanceIcon",
            "instanceGroupIcon",
            "istioWorkloadIcon",
            "k8sClusterIcon",
            "k8sNamespaceIcon",
            "k8sNodeIcon",
            "k8sNodePoolIcon",
            "k8sPodIcon",
            "loadBalancerIcon",
            "netvizGcpRegionIcon",
            "netvizGcpRegionnetIcon",
            "netvizGcpSubnetIcon",
            "netvizPublicIcon",
            "networkPeeringIcon",
            "replicaFailoverIcon",
            "servicesIcon",
        }
    ),
}


def is_gcp_resource_icon(entry: dict) -> bool:
    """Identify source-named service and resource artwork in known mixed modules."""

    data_icon_name = entry["dataIconName"]
    if not isinstance(data_icon_name, str):
        return False
    if (
        entry["extension"] == "app_design_center"
        and data_icon_name.endswith("SectionIcon")
    ):
        return True
    return data_icon_name in GCP_RESOURCE_ICON_NAMES_BY_EXTENSION.get(
        entry["extension"], frozenset()
    )


def gcp_family_name(entry: dict) -> str:
    """Return the legacy per-module GCP family id for alias compatibility."""

    data_icon_name = entry["dataIconName"]
    readable_identity = (
        gcp_snake_case(data_icon_name) if data_icon_name is not None else "template"
    ) or "icon"
    return "_".join(
        (
            "gcp",
            gcp_snake_case(entry["extension"]),
            gcp_snake_case(entry["module"]),
            readable_identity,
            gcp_snake_case(entry["name"]),
        )
    )


def gcp_resource_family_name(data_icon_name: str) -> str:
    return f"gcp_resource_icons_{gcp_snake_case(data_icon_name) or 'icon'}"


def gcp_entry_sort_key(entry: dict) -> tuple[str, str, int, str]:
    """Choose a reproducible representative independent of manifest ordering."""

    data_icon_name = entry["dataIconName"]
    return (
        gcp_snake_case(data_icon_name) if data_icon_name is not None else "template",
        entry["moduleId"],
        entry["templateIndex"],
        entry["name"],
    )


def generate_gcp_console_icons(
    directory: Path,
) -> tuple[dict, list[dict], str]:
    """Emit same-origin ZIP descriptors from a validated GCP source directory."""

    from azure_portal_icons import preserve_source_colors
    from gcp_console_icons import (
        LOCK_NAME,
        build_archive_from_source_tree,
        svg_has_renderable_content,
        validate_source_tree,
    )

    manifest = validate_source_tree(directory)
    archive_bytes = build_archive_from_source_tree(directory)
    try:
        source_lock = json.loads((directory / LOCK_NAME).read_bytes())
    except json.JSONDecodeError as exc:
        raise ValueError("GCP Console source lock is not JSON") from exc
    if not isinstance(source_lock, dict):
        raise ValueError("GCP Console source lock is not an object")

    modules = source_lock.get("modules")
    if not isinstance(modules, list):
        raise ValueError("GCP Console source lock has no modules")
    modules_by_id = {
        module.get("id"): module
        for module in modules
        if isinstance(module, dict) and isinstance(module.get("id"), str)
    }
    if len(modules_by_id) != len(modules):
        raise ValueError("GCP Console source lock has duplicate or invalid module ids")

    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    renderable_entries: list[dict] = []
    for entry in manifest["icons"]:
        svg_text = (directory / entry["path"]).read_text(encoding="utf-8")
        if svg_has_renderable_content(svg_text):
            renderable_entries.append(entry)

    resource_entries_by_name: dict[str, list[dict]] = {}
    grouped_entries: list[tuple[str, list[dict]]] = []
    other_entries_by_digest: dict[str, list[dict]] = {}
    for entry in renderable_entries:
        if is_gcp_resource_icon(entry):
            resource_entries_by_name.setdefault(entry["dataIconName"], []).append(entry)
        else:
            other_entries_by_digest.setdefault(entry["sha256"], []).append(entry)

    for data_icon_name, entries in sorted(resource_entries_by_name.items()):
        entries_by_style: dict[str, set[str]] = {}
        for entry in entries:
            svg_text = (directory / entry["path"]).read_text(encoding="utf-8")
            style = "color" if preserve_source_colors(svg_text) else "regular"
            entries_by_style.setdefault(style, set()).add(entry["sha256"])
        has_same_style_collision = any(
            len(digests) > 1 for digests in entries_by_style.values()
        )
        if has_same_style_collision:
            entries_by_digest: dict[str, list[dict]] = {}
            for entry in entries:
                entries_by_digest.setdefault(entry["sha256"], []).append(entry)
            for digest, digest_entries in sorted(entries_by_digest.items()):
                grouped_entries.append(
                    (
                        f"{gcp_resource_family_name(data_icon_name)}_{digest}",
                        sorted(digest_entries, key=gcp_entry_sort_key),
                    )
                )
        else:
            grouped_entries.append(
                (
                    gcp_resource_family_name(data_icon_name),
                    sorted(entries, key=gcp_entry_sort_key),
                )
            )

    for digest, digest_entries in sorted(other_entries_by_digest.items()):
        entries = sorted(digest_entries, key=gcp_entry_sort_key)
        if len({entry["moduleId"] for entry in entries}) > 1:
            grouped_entries.append((digest, entries))
    icons: list[dict] = []
    seen_family_names: set[str] = set()
    for group_id, entries in grouped_entries:
        entry = entries[0]
        module_id = entry["moduleId"]
        module_record = modules_by_id.get(module_id)
        if module_record is None or not isinstance(module_record.get("url"), str):
            raise ValueError("GCP Console source tree icon has no matching locked module URL")
        data_icon_name = entry["dataIconName"]
        display_name = data_icon_name if data_icon_name is not None else entry["name"]
        readable_identity = (
            gcp_snake_case(data_icon_name) if data_icon_name is not None else "template"
        ) or "icon"
        is_resource_icon = is_gcp_resource_icon(entry)
        is_common_ui = (
            not is_resource_icon
            and len({candidate["moduleId"] for candidate in entries}) > 1
        )
        family_name = (
            group_id
            if is_resource_icon
            else f"gcp_common_ui_{readable_identity}_{group_id}"
            if is_common_ui
            else gcp_family_name(entry)
        )
        if not family_name or family_name in seen_family_names:
            raise ValueError("GCP Console source tree has colliding generated family ids")
        seen_family_names.add(family_name)

        variants: dict[str, dict] = {}
        for candidate in entries:
            candidate_module = modules_by_id.get(candidate["moduleId"])
            if candidate_module is None or not isinstance(candidate_module.get("url"), str):
                raise ValueError(
                    "GCP Console source tree icon has no matching locked module URL"
                )
            svg_text = (directory / candidate["path"]).read_text(encoding="utf-8")
            style = "color" if preserve_source_colors(svg_text) else "regular"
            if style in variants:
                continue
            descriptor = {
                "format": "same-origin-zip-svg-entry",
                "url": "gcp-console-icons.zip",
                "entry": candidate["path"],
                "archiveSha256": archive_sha256,
                "entrySha256": candidate["sha256"],
            }
            default_size = (
                parse_viewbox_size(ET.fromstring(svg_text).attrib.get("viewBox"))
                or 24
            )
            variant = {
                "defaultSize": default_size,
                "sourceUrl": candidate_module["url"],
                "remoteSource": descriptor,
                "sizes": {str(default_size): {"remoteSource": descriptor}},
            }
            if style == "color":
                variant["preserveSourceColors"] = True
                variant["sourceCapabilities"] = {"currentColor": False, "boundingBox": False}
            variants[style] = variant
        variants = {
            style: variants[style]
            for style in SUPPORTED_VARIANTS
            if style in variants
        }
        if is_common_ui or is_resource_icon:
            search_metadata = [
                value
                for candidate in entries
                for value in (
                    candidate["dataIconName"] or candidate["name"],
                    candidate["name"],
                    candidate["extension"],
                    candidate["module"],
                    candidate["moduleId"],
                    gcp_family_name(candidate),
                )
            ]
            aliases = list(dict.fromkeys([display_name, *search_metadata]))
        else:
            search_metadata = [
                display_name,
                entry["name"],
                entry["extension"],
                entry["module"],
                entry["moduleId"],
            ]
            aliases = [display_name]
            if entry["name"] != display_name:
                aliases.append(entry["name"])
        metaphors = list(dict.fromkeys(search_metadata))
        icons.append(
            {
                "name": family_name,
                "displayName": display_name,
                "description": "",
                "metaphors": metaphors,
                "aliases": aliases,
                "category": (
                    "Resource Icons"
                    if is_resource_icon
                    else "Common UI"
                    if is_common_ui
                    else humanize_gcp_extension(entry["extension"])
                ),
                "variants": variants,
            }
        )

    icons.sort(key=lambda icon: icon["name"])
    return source_lock, icons, archive_sha256


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
    branded_components_dir: Optional[Path] = None,
) -> list[dict]:
    if not components_dir.exists():
        raise FileNotFoundError(
            f"Fabric components directory not found: {components_dir}"
        )
    if branded_components_dir is not None and not branded_components_dir.exists():
        raise FileNotFoundError(
            "Branded Fabric components directory not found: "
            f"{branded_components_dir}"
        )

    members: list[dict] = []
    component_sources = []
    if branded_components_dir is not None:
        component_sources.append(
            (
                branded_components_dir,
                "react-icons-mdl2-branded",
                ["branded"],
            )
        )
    component_sources.append((components_dir, "react-icons-mdl2", []))

    for source_dir, package_name, source_tags in component_sources:
        for component_file in sorted(source_dir.glob("*.tsx")):
            match = FABRIC_ICON_FILE_PATTERN.match(component_file.name)
            if not match:
                continue

            icon_id = match.group("name")
            tsx_text = component_file.read_text(encoding="utf-8")
            svg_text = extract_fabric_svg(tsx_text, component_file)
            if not svg_text:
                continue

            default_size = infer_fabric_default_size(icon_id, svg_text)
            source_url = build_fabric_source_url(
                cdn_base,
                upstream_sha,
                package_name,
                component_file.name,
            )
            display_name = extract_display_name(tsx_text, icon_id)
            normalized_id = camel_to_snake(icon_id)
            parsed_variant = parse_fabric_member_variant(normalized_id)
            metadata = metadata_by_id.get(normalized_id, {})
            description = (
                metadata.get("description") if isinstance(metadata, dict) else ""
            )
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
                    "sourceTags": source_tags,
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
            metaphors.extend(member["sourceTags"])
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


def assemble_collections(
    descriptors: Iterable[CollectionDescriptor],
) -> Dict[str, dict]:
    """Build the generated collection map without exposing source adapters to the UI."""

    collections: Dict[str, dict] = {}
    for descriptor in descriptors:
        if not descriptor.key:
            raise ValueError("Collection keys must not be empty")
        if descriptor.key in collections:
            raise ValueError(f"Duplicate collection key: {descriptor.key}")

        collection = {
            "label": descriptor.label,
            "shortLabel": descriptor.short_label,
            "source": descriptor.source,
        }
        collection["sources"] = list(descriptor.sources)
        collection.update(
            {
                "upstreamSha": descriptor.upstream_sha,
                "cdnBase": descriptor.cdn_base,
                "icons": descriptor.build_icons(),
            }
        )
        collections[descriptor.key] = collection

    return collections


def generate_icon_data(
    fluent_icons_dir: Path,
    fabric_components_dir: Path,
    fabric_branded_components_dir: Optional[Path],
    fabric_metadata_path: Path,
    output_file: Path,
    fluent_upstream_sha: str,
    fabric_upstream_sha: str,
    fluent_cdn_base: str,
    fabric_cdn_base: str,
    azure_source_lock_path: Optional[Path] = None,
    azure_previous_source_lock_path: Optional[Path] = None,
    azure_minimum_count: int = 250,
    azure_manifest_minimum_count: int = 100,
    flight_icons_dir: Optional[Path] = None,
    flight_source_lock_path: Optional[Path] = None,
    flight_upstream_sha: str = "",
    hashicorp_products_source_lock_path: Optional[Path] = None,
    salesforce_archive_path: Optional[Path] = None,
    salesforce_source_lock_path: Optional[Path] = None,
    aws_archive_path: Optional[Path] = None,
    aws_source_lock_path: Optional[Path] = None,
    redhat_icons_dir: Optional[Path] = None,
    redhat_source_lock_path: Optional[Path] = None,
    redhat_upstream_sha: str = "",
    gcp_console_directory: Optional[Path] = None,
) -> tuple[int, int]:
    fabric_metadata = load_fabric_metadata(fabric_metadata_path)

    descriptors: list[CollectionDescriptor] = [
        CollectionDescriptor(
            key="fluent",
            label="Fluent System Icons",
            short_label="Fluent",
            source="microsoft/fluentui-system-icons",
            sources=(
                source_record(
                    label="Fluent System Icons",
                    reference="microsoft/fluentui-system-icons",
                    url="https://github.com/microsoft/fluentui-system-icons",
                    revision=fluent_upstream_sha,
                    license_name="MIT",
                    license_url="https://github.com/microsoft/fluentui-system-icons/blob/main/LICENSE",
                ),
            ),
            upstream_sha=fluent_upstream_sha,
            cdn_base=fluent_cdn_base,
            build_icons=lambda: generate_fluent_icons(
                icons_dir=fluent_icons_dir,
                upstream_sha=fluent_upstream_sha,
                cdn_base=fluent_cdn_base,
            ),
        ),
        CollectionDescriptor(
            key="segoe",
            label="Segoe",
            short_label="Segoe",
            source="microsoft/fluentui/packages/react-icons-mdl2",
            sources=(
                source_record(
                    label="Segoe MDL2 Icons",
                    reference="microsoft/fluentui/packages/react-icons-mdl2",
                    url="https://github.com/microsoft/fluentui/tree/main/packages/react-icons-mdl2",
                    revision=fabric_upstream_sha,
                    license_name="MIT",
                    license_url="https://github.com/microsoft/fluentui/blob/master/LICENSE",
                ),
                *(
                    (
                        source_record(
                            label="Segoe MDL2 Branded Icons",
                            reference="microsoft/fluentui/packages/react-icons-mdl2-branded",
                            url="https://github.com/microsoft/fluentui/tree/main/packages/react-icons-mdl2-branded",
                            revision=fabric_upstream_sha,
                            license_name="Microsoft Fabric Assets License",
                            license_url="https://aka.ms/fluentui-assets-license",
                        ),
                    )
                    if fabric_branded_components_dir is not None
                    else ()
                ),
            ),
            upstream_sha=fabric_upstream_sha,
            cdn_base=fabric_cdn_base,
            build_icons=lambda: generate_fabric_icons(
                components_dir=fabric_components_dir,
                upstream_sha=fabric_upstream_sha,
                cdn_base=fabric_cdn_base,
                metadata_by_id=fabric_metadata,
                branded_components_dir=fabric_branded_components_dir,
            ),
        ),
    ]
    if azure_source_lock_path is not None:
        from azure_portal_icons import generate_azure_icons

        descriptors.append(
            CollectionDescriptor(
                key="azure",
                label="Azure Portal Icons",
                short_label="Azure",
                source=(
                    "Microsoft Azure Portal public core SVG modules and default "
                    "extension manifests (bounded public subset)"
                ),
                sources=(
                    source_record(
                        label="Microsoft Azure Portal",
                        reference="portal.azure.com public icon sources",
                        url="https://portal.azure.com/",
                        revision="portal-bootstrap",
                    ),
                ),
                upstream_sha="portal-bootstrap",
                cdn_base="https://portal.azure.com",
                build_icons=lambda: generate_azure_icons(
                    source_lock_path=azure_source_lock_path,
                    previous_source_lock_path=azure_previous_source_lock_path,
                    core_minimum_count=azure_minimum_count,
                    manifest_minimum_count=azure_manifest_minimum_count,
                ),
            )
        )
    if flight_icons_dir is not None or flight_source_lock_path is not None:
        if flight_icons_dir is None or flight_source_lock_path is None or not flight_upstream_sha:
            raise ValueError("Flight icons require directory, source lock, and upstream SHA")
        from flight_icons import LICENSE as FLIGHT_LICENSE
        from flight_icons import LICENSE_URL as FLIGHT_LICENSE_URL
        from flight_icons import REPOSITORY_URL as FLIGHT_REPOSITORY_URL
        from flight_icons import SOURCE as FLIGHT_SOURCE
        from flight_icons import generate_icons as generate_flight_icons
        from source_lock import read_lock

        flight_lock = read_lock(flight_source_lock_path, FLIGHT_SOURCE, flight_upstream_sha)
        descriptors.append(
            CollectionDescriptor(
                key="flight",
                label="HashiCorp Flight Icons",
                short_label="Flight",
                source="HashiCorp Flight Icons",
                sources=(
                    source_record(
                        label="HashiCorp Flight Icons",
                        reference=FLIGHT_SOURCE,
                        url=FLIGHT_REPOSITORY_URL,
                        revision=flight_upstream_sha,
                        license_name=FLIGHT_LICENSE,
                        license_url=FLIGHT_LICENSE_URL,
                        digest=flight_lock["contentSha256"],
                    ),
                ),
                upstream_sha=flight_upstream_sha,
                cdn_base="https://raw.githubusercontent.com/hashicorp/design-system",
                build_icons=lambda: generate_flight_icons(
                    flight_icons_dir, flight_upstream_sha, flight_source_lock_path
                ),
            )
        )
    if hashicorp_products_source_lock_path is not None:
        if flight_icons_dir is None or not flight_upstream_sha:
            raise ValueError(
                "HashiCorp Products require the Flight directory and upstream SHA"
            )
        from flight_icons import LICENSE as HASHICORP_LICENSE
        from flight_icons import LICENSE_URL as HASHICORP_LICENSE_URL
        from flight_icons import PRODUCT_SOURCE as HASHICORP_PRODUCTS_SOURCE
        from flight_icons import REPOSITORY_URL as HASHICORP_REPOSITORY_URL
        from flight_icons import generate_product_icons
        from source_lock import read_lock

        hashicorp_products_lock = read_lock(
            hashicorp_products_source_lock_path,
            HASHICORP_PRODUCTS_SOURCE,
            flight_upstream_sha,
        )
        descriptors.append(
            CollectionDescriptor(
                key="hashicorp",
                label="HashiCorp Products",
                short_label="HashiCorp",
                source="HashiCorp product icons",
                sources=(
                    source_record(
                        label="HashiCorp Flight Products",
                        reference=HASHICORP_PRODUCTS_SOURCE,
                        url=HASHICORP_REPOSITORY_URL,
                        revision=flight_upstream_sha,
                        license_name=HASHICORP_LICENSE,
                        license_url=HASHICORP_LICENSE_URL,
                        digest=hashicorp_products_lock["contentSha256"],
                    ),
                ),
                upstream_sha=flight_upstream_sha,
                cdn_base="https://raw.githubusercontent.com/hashicorp/design-system",
                build_icons=lambda: generate_product_icons(
                    flight_icons_dir,
                    flight_upstream_sha,
                    hashicorp_products_source_lock_path,
                ),
            )
        )
    if salesforce_archive_path is not None or salesforce_source_lock_path is not None:
        if salesforce_archive_path is None or salesforce_source_lock_path is None:
            raise ValueError("Salesforce icons require archive and source lock")
        from salesforce_icons import LICENSE as SALESFORCE_LICENSE
        from salesforce_icons import LICENSE_URL as SALESFORCE_LICENSE_URL
        from salesforce_icons import REGISTRY_URL as SALESFORCE_REGISTRY_URL
        from salesforce_icons import SOURCE as SALESFORCE_SOURCE
        from salesforce_icons import archive_url as salesforce_archive_url
        from salesforce_icons import generate_icons as generate_salesforce_icons
        from source_lock import read_archive_lock

        salesforce_lock_data = json.loads(
            salesforce_source_lock_path.read_text(encoding="utf-8")
        )
        salesforce_version = salesforce_lock_data.get("packageVersion")
        if not isinstance(salesforce_version, str) or not salesforce_version:
            raise ValueError("Salesforce source lock has no package version")
        salesforce_lock = read_archive_lock(
            salesforce_source_lock_path,
            SALESFORCE_SOURCE,
            salesforce_archive_url(salesforce_version),
            salesforce_version,
        )
        descriptors.append(
            CollectionDescriptor(
                key="salesforce",
                label="Salesforce SLDS Icons",
                short_label="Salesforce",
                source="Salesforce Lightning Design System icons",
                sources=(
                    source_record(
                        label="Salesforce SLDS Icons",
                        reference=SALESFORCE_SOURCE,
                        url=SALESFORCE_REGISTRY_URL,
                        revision=salesforce_version,
                        license_name=SALESFORCE_LICENSE,
                        license_url=SALESFORCE_LICENSE_URL,
                        digest=salesforce_lock["archiveSha256"],
                    ),
                ),
                upstream_sha=salesforce_version,
                cdn_base=SALESFORCE_REGISTRY_URL,
                build_icons=lambda: generate_salesforce_icons(
                    salesforce_archive_path, salesforce_source_lock_path
                ),
            )
        )
    if aws_archive_path is not None or aws_source_lock_path is not None:
        if aws_archive_path is None or aws_source_lock_path is None:
            raise ValueError("AWS icons require archive and source lock")
        from aws_icons import ARCHITECTURE_ICONS_PAGE_URL
        from aws_icons import SOURCE as AWS_SOURCE
        from aws_icons import TERMS_URL as AWS_TERMS_URL
        from aws_icons import generate_icons as generate_aws_icons
        from aws_icons import read_source_lock as read_aws_source_lock

        aws_lock = read_aws_source_lock(aws_source_lock_path)
        descriptors.append(
            CollectionDescriptor(
                key="aws",
                label="AWS Architecture Icons",
                short_label="AWS",
                source="AWS Architecture Icons official archive",
                sources=(
                    source_record(
                        label="AWS Architecture Icons",
                        reference=AWS_SOURCE,
                        url=ARCHITECTURE_ICONS_PAGE_URL,
                        revision=aws_lock["release"],
                        license_name="AWS Site Terms",
                        license_url=AWS_TERMS_URL,
                        digest=aws_lock["archiveSha256"],
                    ),
                ),
                upstream_sha=aws_lock["archiveSha256"],
                cdn_base=aws_lock["archiveUrl"],
                build_icons=lambda: generate_aws_icons(
                    aws_archive_path, aws_source_lock_path
                ),
            )
        )
    if redhat_icons_dir is not None or redhat_source_lock_path is not None:
        if redhat_icons_dir is None or redhat_source_lock_path is None or not redhat_upstream_sha:
            raise ValueError("Red Hat icons require directory, source lock, and upstream SHA")
        from redhat_icons import LICENSE as REDHAT_LICENSE
        from redhat_icons import LICENSE_URL as REDHAT_LICENSE_URL
        from redhat_icons import REPOSITORY_URL as REDHAT_REPOSITORY_URL
        from redhat_icons import SOURCE as REDHAT_SOURCE
        from redhat_icons import generate_icons as generate_redhat_icons
        from source_lock import read_lock

        redhat_lock = read_lock(redhat_source_lock_path, REDHAT_SOURCE, redhat_upstream_sha)
        descriptors.append(
            CollectionDescriptor(
                key="redhat",
                label="Red Hat Icons",
                short_label="Red Hat",
                source="Red Hat Icons",
                sources=(
                    source_record(
                        label="Red Hat Icons",
                        reference=REDHAT_SOURCE,
                        url=REDHAT_REPOSITORY_URL,
                        revision=redhat_upstream_sha,
                        license_name=REDHAT_LICENSE,
                        license_url=REDHAT_LICENSE_URL,
                        digest=redhat_lock["contentSha256"],
                    ),
                ),
                upstream_sha=redhat_upstream_sha,
                cdn_base="https://raw.githubusercontent.com/RedHat-UX/red-hat-icons",
                build_icons=lambda: generate_redhat_icons(
                    redhat_icons_dir, redhat_upstream_sha, redhat_source_lock_path
                ),
            )
        )
    if gcp_console_directory is not None:
        gcp_source_lock, gcp_icons, gcp_archive_sha256 = generate_gcp_console_icons(
            gcp_console_directory
        )
        descriptors.append(
            CollectionDescriptor(
                key="gcp",
                label="Google Cloud Console Icons",
                short_label="Google Cloud",
                source=(
                    "Static same-origin archive generated from public Google Cloud "
                    "Console route-map and module sources; contains the archive notice"
                ),
                sources=(
                    source_record(
                        label="Google Cloud Console Icons",
                        reference="Google Cloud Console public route-map/module sources",
                        url="https://console.cloud.google.com/",
                        revision=gcp_source_lock["contentSha256"],
                        digest=gcp_archive_sha256,
                    ),
                ),
                upstream_sha=gcp_source_lock["contentSha256"],
                cdn_base="gcp-console-icons.zip",
                build_icons=lambda: gcp_icons,
            )
        )
    collections = assemble_collections(descriptors)
    fluent_icons = collections["fluent"]["icons"]
    segoe_icons = collections["segoe"]["icons"]
    azure_icons = collections.get("azure", {}).get("icons", [])
    flight_icons = collections.get("flight", {}).get("icons", [])
    hashicorp_products = collections.get("hashicorp", {}).get("icons", [])
    salesforce_icons = collections.get("salesforce", {}).get("icons", [])
    aws_icons = collections.get("aws", {}).get("icons", [])
    redhat_icons = collections.get("redhat", {}).get("icons", [])
    gcp_icons = collections.get("gcp", {}).get("icons", [])

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "defaultSet": "fluent",
        "icons": fluent_icons,
        "setAliases": SET_ALIASES,
        "sets": collections,
    }

    output_file.write_text(
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )

    print(
        "Generated "
        f"{len(fluent_icons)} fluent icons + {len(segoe_icons)} Segoe icons "
        f"+ {len(azure_icons)} Azure Portal icons "
        f"+ {len(flight_icons)} HashiCorp Flight icons "
        f"+ {len(hashicorp_products)} HashiCorp product icons "
        f"+ {len(salesforce_icons)} Salesforce SLDS icons "
        f"+ {len(aws_icons)} AWS Architecture icons "
        f"+ {len(redhat_icons)} Red Hat icons "
        f"+ {len(gcp_icons)} Google Cloud Console icons "
        f"-> {output_file}"
    )
    return len(fluent_icons), len(segoe_icons)


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
        "--flight-icons-dir",
        default="",
        help="Path to HashiCorp Flight package directory",
    )
    parser.add_argument(
        "--flight-source-lock",
        default="",
        help="Digest-bound HashiCorp Flight source lock",
    )
    parser.add_argument(
        "--flight-upstream-sha",
        default="",
        help="HashiCorp design-system commit SHA",
    )
    parser.add_argument(
        "--hashicorp-products-source-lock",
        default="",
        help="Digest-bound HashiCorp product-icons source lock",
    )
    parser.add_argument(
        "--salesforce-archive",
        default="",
        help="Official @salesforce-ux/icons package archive",
    )
    parser.add_argument(
        "--salesforce-source-lock",
        default="",
        help="Digest-bound Salesforce package archive source lock",
    )
    parser.add_argument(
        "--aws-archive",
        default="",
        help="Official AWS Architecture Icons ZIP archive",
    )
    parser.add_argument(
        "--aws-source-lock",
        default="",
        help="Digest-bound AWS Architecture Icons archive source lock",
    )
    parser.add_argument(
        "--gcp-console-directory",
        default="",
        help="Versioned GCP Console SVG source directory for the Pages ZIP payload",
    )
    parser.add_argument(
        "--redhat-icons-dir",
        default="",
        help="Path to Red Hat icons repository directory",
    )
    parser.add_argument(
        "--redhat-source-lock",
        default="",
        help="Digest-bound Red Hat icons source lock",
    )
    parser.add_argument(
        "--redhat-upstream-sha",
        default="",
        help="Red Hat icons commit SHA",
    )
    parser.add_argument(
        "--fabric-components-dir",
        default=".tmp/fluentui/packages/react-icons-mdl2/src/components",
        help="Path to Fabric MDL2 icon component directory",
    )
    parser.add_argument(
        "--fabric-branded-components-dir",
        default="",
        help="Optional path to branded Fabric MDL2 icon component directory",
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
        default="https://raw.githubusercontent.com/microsoft/fluentui-system-icons",
        help="Asset base URL for Fluent source SVGs",
    )
    parser.add_argument(
        "--fabric-cdn-base",
        default="https://cdn.jsdelivr.net/gh/microsoft/fluentui",
        help="CDN base URL for Fabric source files",
    )
    parser.add_argument(
        "--azure-source-lock",
        default="",
        help="Output path for the Azure Portal source lock; enables the Azure collection",
    )
    parser.add_argument(
        "--azure-previous-source-lock",
        default="",
        help="Prior committed Azure Portal source lock for drift detection",
    )
    parser.add_argument(
        "--azure-minimum-count",
        type=int,
        default=250,
        help="Minimum Azure Portal core icon count before failing generation",
    )
    parser.add_argument(
        "--azure-manifest-minimum-count",
        type=int,
        default=100,
        help="Minimum Azure Portal extension-manifest icon count before failing generation",
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
    fabric_branded_components_dir = (
        Path(args.fabric_branded_components_dir)
        if args.fabric_branded_components_dir
        else None
    )

    generate_icon_data(
        fluent_icons_dir=Path(fluent_icons_dir),
        fabric_components_dir=Path(args.fabric_components_dir),
        fabric_branded_components_dir=fabric_branded_components_dir,
        fabric_metadata_path=Path(args.fabric_metadata),
        output_file=Path(args.output),
        fluent_upstream_sha=fluent_upstream_sha,
        fabric_upstream_sha=fabric_upstream_sha,
        fluent_cdn_base=args.fluent_cdn_base.rstrip("/"),
        fabric_cdn_base=args.fabric_cdn_base.rstrip("/"),
        azure_source_lock_path=Path(args.azure_source_lock)
        if args.azure_source_lock
        else None,
        azure_previous_source_lock_path=Path(args.azure_previous_source_lock)
        if args.azure_previous_source_lock
        else None,
        azure_minimum_count=args.azure_minimum_count,
        azure_manifest_minimum_count=args.azure_manifest_minimum_count,
        flight_icons_dir=Path(args.flight_icons_dir) if args.flight_icons_dir else None,
        flight_source_lock_path=Path(args.flight_source_lock)
        if args.flight_source_lock
        else None,
        flight_upstream_sha=args.flight_upstream_sha.strip(),
        hashicorp_products_source_lock_path=Path(args.hashicorp_products_source_lock)
        if args.hashicorp_products_source_lock
        else None,
        salesforce_archive_path=Path(args.salesforce_archive)
        if args.salesforce_archive
        else None,
        salesforce_source_lock_path=Path(args.salesforce_source_lock)
        if args.salesforce_source_lock
        else None,
        aws_archive_path=Path(args.aws_archive) if args.aws_archive else None,
        aws_source_lock_path=Path(args.aws_source_lock)
        if args.aws_source_lock
        else None,
        redhat_icons_dir=Path(args.redhat_icons_dir) if args.redhat_icons_dir else None,
        redhat_source_lock_path=Path(args.redhat_source_lock)
        if args.redhat_source_lock
        else None,
        redhat_upstream_sha=args.redhat_upstream_sha.strip(),
        gcp_console_directory=Path(args.gcp_console_directory)
        if args.gcp_console_directory
        else None,
    )


if __name__ == "__main__":
    main()
