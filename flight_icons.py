"""Adapter for the source-owned HashiCorp Flight icon collection."""

from __future__ import annotations

import json
from pathlib import Path

from source_lock import digest_files, read_lock, write_lock


SOURCE = "hashicorp/design-system/packages/flight-icons"
PRODUCT_SOURCE = "hashicorp/design-system/packages/flight-icons (Products)"
REPOSITORY_URL = "https://github.com/hashicorp/design-system"
LICENSE = "MPL-2.0"
LICENSE_URL = "https://www.mozilla.org/MPL/2.0/"
LICENSE_FILE = Path("LICENSE.md")
LICENSE_MARKER = "Mozilla Public License Version 2.0"
PACKAGE_PATH = Path("packages/flight-icons")
APPROVED_CATEGORIES = {
    "Animated",
    "Arrows",
    "Business",
    "Communication",
    "Data",
    "Date and time",
    "Development",
    "Files",
    "Interface",
    "Location",
    "Media",
    "Operations",
    "Security",
    "Status",
    "Support",
    "Symbols",
    "User",
}
EXCLUDED_CATEGORIES = {"Products", "Services"}
PRODUCT_CATEGORIES = {"Products"}
PRODUCT_EXCLUDED_CATEGORIES = APPROVED_CATEGORIES | {"Services"}


def _catalog(package_dir: Path) -> list[dict]:
    payload = json.loads((package_dir / "catalog.json").read_text(encoding="utf-8"))
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        raise ValueError("Flight catalog has no assets list")
    return [asset for asset in assets if isinstance(asset, dict)]


def _included_assets(
    package_dir: Path,
    included_categories: set[str] = APPROVED_CATEGORIES,
    excluded_categories: set[str] = EXCLUDED_CATEGORIES,
    collection_name: str = "Flight",
) -> list[dict]:
    assets = _catalog(package_dir)
    categories = set()
    for asset in assets:
        category = asset.get("category")
        if not isinstance(category, str) or not category:
            raise ValueError("Flight catalog asset has no valid category")
        categories.add(category)

    unknown_categories = categories - included_categories - excluded_categories
    if unknown_categories:
        names = ", ".join(sorted(unknown_categories))
        raise ValueError(f"{collection_name} catalog has unknown categories: {names}")

    included = []
    for asset in assets:
        if asset["category"] not in included_categories:
            continue
        if not isinstance(asset.get("fileName"), str) or not isinstance(
            asset.get("iconName"), str
        ):
            raise ValueError(f"{collection_name} approved asset has invalid source identity")
        included.append(asset)
    return included


def _source_paths(
    package_dir: Path,
    included_categories: set[str] = APPROVED_CATEGORIES,
    excluded_categories: set[str] = EXCLUDED_CATEGORIES,
    collection_name: str = "Flight",
) -> list[Path]:
    paths = [Path("catalog.json"), Path("package.json"), LICENSE_FILE]
    for asset in _included_assets(
        package_dir, included_categories, excluded_categories, collection_name
    ):
        paths.append(Path("svg-original") / f"{asset['fileName']}.svg")
    return paths


def _validate_license(package_dir: Path) -> None:
    license_path = package_dir / LICENSE_FILE
    try:
        license_text = license_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Flight license file is unavailable: {license_path}") from exc
    if LICENSE_MARKER not in license_text:
        raise ValueError(
            f"Flight license file is missing expected marker: {LICENSE_MARKER}"
        )


def _group_assets(assets: list[dict]) -> dict[str, dict]:
    known_names = {
        (str(asset["category"]), str(asset["iconName"])) for asset in assets
    }
    grouped: dict[str, dict] = {}
    for asset in assets:
        category = str(asset["category"])
        source_name = str(asset["iconName"])
        style = "regular"
        family_name = source_name
        if source_name.endswith("-fill"):
            style = "filled"
            base_name = source_name[:-5]
            if (category, base_name) in known_names:
                family_name = base_name

        family = grouped.setdefault(
            family_name,
            {"category": category, "members": {"regular": [], "filled": []}},
        )
        if family["category"] != category:
            raise ValueError(f"Flight family spans categories: {family_name}")
        family["members"][style].append(asset)
    return grouped


def _write_source_lock(
    package_dir: Path,
    output_path: Path,
    commit: str,
    *,
    source: str,
    included_categories: set[str],
    excluded_categories: set[str],
    collection_name: str,
) -> dict:
    _validate_license(package_dir)
    package = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    version = package.get("version") if isinstance(package, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError("Flight package has no version")
    assets = _included_assets(
        package_dir, included_categories, excluded_categories, collection_name
    )
    families = _group_assets(assets)
    payload = {
        "source": source,
        "repositoryUrl": REPOSITORY_URL,
        "packagePath": PACKAGE_PATH.as_posix(),
        "commit": commit,
        "packageVersion": version,
        "contentSha256": digest_files(
            package_dir,
            _source_paths(
                package_dir, included_categories, excluded_categories, collection_name
            ),
        ),
        "includedCategories": sorted(included_categories),
        "excludedCategories": sorted(excluded_categories),
        "indexedAssetCount": len(assets),
        "indexedFamilyCount": len(families),
        "groupedFillPairCount": sum(
            bool(family["members"]["regular"] and family["members"]["filled"])
            for family in families.values()
        ),
    }
    write_lock(output_path, payload)
    return payload


def write_source_lock(package_dir: Path, output_path: Path, commit: str) -> dict:
    return _write_source_lock(
        package_dir,
        output_path,
        commit,
        source=SOURCE,
        included_categories=APPROVED_CATEGORIES,
        excluded_categories=EXCLUDED_CATEGORIES,
        collection_name="Flight",
    )


def write_product_source_lock(package_dir: Path, output_path: Path, commit: str) -> dict:
    return _write_source_lock(
        package_dir,
        output_path,
        commit,
        source=PRODUCT_SOURCE,
        included_categories=PRODUCT_CATEGORIES,
        excluded_categories=PRODUCT_EXCLUDED_CATEGORIES,
        collection_name="HashiCorp Products",
    )


def _raw_url(commit: str, relative_path: Path) -> str:
    return (
        "https://raw.githubusercontent.com/hashicorp/design-system/"
        f"{commit}/{PACKAGE_PATH.as_posix()}/{relative_path.as_posix()}"
    )


def _generate_icons(
    package_dir: Path,
    commit: str,
    source_lock_path: Path,
    *,
    source: str,
    included_categories: set[str],
    excluded_categories: set[str],
    collection_name: str,
) -> list[dict]:
    _validate_license(package_dir)
    lock = read_lock(source_lock_path, source, commit)
    actual_digest = digest_files(
        package_dir,
        _source_paths(
            package_dir, included_categories, excluded_categories, collection_name
        ),
    )
    if actual_digest != lock["contentSha256"]:
        raise ValueError(f"{collection_name} source content does not match its source lock")

    grouped = _group_assets(
        _included_assets(
            package_dir, included_categories, excluded_categories, collection_name
        )
    )

    icons: list[dict] = []
    for icon_name in sorted(grouped):
        family = grouped[icon_name]
        members = family["members"]
        entries = members["regular"] + members["filled"]
        category = family["category"]
        description = next(
            (
                entry["description"].strip()
                for entry in entries
                if isinstance(entry.get("description"), str) and entry["description"].strip()
            ),
            "",
        )
        metaphors = []
        aliases = []
        for entry in entries:
            entry_description = entry.get("description")
            if isinstance(entry_description, str):
                metaphors.extend(
                    term.strip().lower()
                    for term in entry_description.split(",")
                    if term.strip()
                )
            source_name = str(entry["iconName"])
            metaphors.extend([source_name.replace("-", " "), source_name])
            if source_name != icon_name:
                aliases.append(source_name.replace("-", "_"))
        metaphors.extend([category.lower(), icon_name.replace("-", " "), icon_name])

        variants: dict[str, dict] = {}
        for style in ("regular", "filled"):
            style_entries = members[style]
            if not style_entries:
                continue
            sizes: dict[str, str] = {}
            for entry in sorted(
                style_entries,
                key=lambda item: int(str(item.get("size", "0")) or 0),
            ):
                size = int(str(entry["size"]))
                relative_path = Path("svg-original") / f"{entry['fileName']}.svg"
                sizes[str(size)] = _raw_url(commit, relative_path)
            default_size = 24 if "24" in sizes else min(int(size) for size in sizes)
            variants[style] = {
                "defaultSize": default_size,
                "previewUrl": sizes[str(default_size)],
                "sizes": sizes,
            }

        icon = {
            "name": icon_name.replace("-", "_"),
            "displayName": icon_name.replace("-", " ").title(),
            "description": description,
            "category": category,
            "metaphors": list(dict.fromkeys(metaphors)),
            "variants": variants,
        }
        if aliases:
            icon["aliases"] = sorted(set(aliases))
        icons.append(icon)
    return icons


def generate_icons(package_dir: Path, commit: str, source_lock_path: Path) -> list[dict]:
    return _generate_icons(
        package_dir,
        commit,
        source_lock_path,
        source=SOURCE,
        included_categories=APPROVED_CATEGORIES,
        excluded_categories=EXCLUDED_CATEGORIES,
        collection_name="Flight",
    )


def generate_product_icons(
    package_dir: Path, commit: str, source_lock_path: Path
) -> list[dict]:
    return _generate_icons(
        package_dir,
        commit,
        source_lock_path,
        source=PRODUCT_SOURCE,
        included_categories=PRODUCT_CATEGORIES,
        excluded_categories=PRODUCT_EXCLUDED_CATEGORIES,
        collection_name="HashiCorp Products",
    )
