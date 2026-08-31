"""Adapter for the source-owned Red Hat standard, UI, and micron icons."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from source_lock import digest_files, read_lock, write_lock


SOURCE = "RedHat-UX/red-hat-icons"
REPOSITORY_URL = "https://github.com/RedHat-UX/red-hat-icons"
LICENSE = "CC BY 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_FILE = Path("LICENSE_ICONS.md")
LICENSE_MARKER = "Creative Commons Attribution 4.0 International"
INCLUDED_CATEGORIES = ("standard", "ui", "microns")


def _source_paths(root: Path) -> list[Path]:
    return [
        path.relative_to(root)
        for category in INCLUDED_CATEGORIES
        for path in sorted((root / "src" / category).glob("*.svg"))
    ] + [Path("package.json"), LICENSE_FILE]


def _validate_license(root: Path) -> None:
    license_path = root / LICENSE_FILE
    try:
        license_text = license_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Red Hat icon license file is unavailable: {license_path}") from exc
    if LICENSE_MARKER not in license_text:
        raise ValueError(
            f"Red Hat icon license file is missing expected marker: {LICENSE_MARKER}"
        )


def write_source_lock(root: Path, output_path: Path, commit: str) -> dict:
    _validate_license(root)
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    version = package.get("version") if isinstance(package, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError("Red Hat package has no version")
    paths = _source_paths(root)
    family_names = {
        (
            category,
            path.stem[:-5] if path.stem.endswith("-fill") else path.stem,
        )
        for category in INCLUDED_CATEGORIES
        for path in (root / "src" / category).glob("*.svg")
    }
    payload = {
        "source": SOURCE,
        "repositoryUrl": REPOSITORY_URL,
        "commit": commit,
        "packageVersion": version,
        "contentSha256": digest_files(root, paths),
        "includedCategories": list(INCLUDED_CATEGORIES),
        "excludedCategories": ["social"],
        "indexedAssetCount": len(paths) - 2,
        "indexedFamilyCount": len(family_names),
    }
    write_lock(output_path, payload)
    return payload


def _raw_url(commit: str, relative_path: Path) -> str:
    return (
        "https://raw.githubusercontent.com/RedHat-UX/red-hat-icons/"
        f"{commit}/{relative_path.as_posix()}"
    )


def _size(svg_path: Path) -> int:
    root = ET.parse(svg_path).getroot()
    view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
    if len(view_box) != 4:
        raise ValueError(f"Red Hat SVG has no square viewBox: {svg_path}")
    width, height = float(view_box[2]), float(view_box[3])
    if width <= 0 or width != height or not width.is_integer():
        raise ValueError(f"Red Hat SVG has no square viewBox: {svg_path}")
    return int(width)


def generate_icons(root: Path, commit: str, source_lock_path: Path) -> list[dict]:
    _validate_license(root)
    lock = read_lock(source_lock_path, SOURCE, commit)
    source_paths = _source_paths(root)
    if digest_files(root, source_paths) != lock["contentSha256"]:
        raise ValueError("Red Hat source content does not match its source lock")

    members: dict[tuple[str, str], dict[str, dict]] = {}
    for category in INCLUDED_CATEGORIES:
        for svg_path in sorted((root / "src" / category).glob("*.svg")):
            file_name = svg_path.stem
            is_filled = file_name.endswith("-fill")
            base_name = file_name[:-5] if is_filled else file_name
            relative_path = svg_path.relative_to(root)
            members.setdefault((category, base_name), {})[
                "filled" if is_filled else "regular"
            ] = {
                "size": _size(svg_path),
                "url": _raw_url(commit, relative_path),
            }

    duplicate_names: dict[str, int] = {}
    for _category, base_name in members:
        duplicate_names[base_name] = duplicate_names.get(base_name, 0) + 1

    icons: list[dict] = []
    for (category, base_name), variants in sorted(members.items()):
        name = base_name if duplicate_names[base_name] == 1 else f"{category}-{base_name}"
        icon_variants: dict[str, dict] = {}
        for style, member in sorted(variants.items()):
            size = member["size"]
            icon_variants[style] = {
                "defaultSize": size,
                "previewUrl": member["url"],
                "sizes": {str(size): member["url"]},
            }
        icons.append(
            {
                "name": name.replace("-", "_"),
                "displayName": name.replace("-", " ").title(),
                "description": "",
                "category": category,
                "metaphors": [category, base_name.replace("-", " "), base_name],
                "variants": icon_variants,
            }
        )
    return icons
