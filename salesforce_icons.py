"""Archive-backed adapter for the official Salesforce SLDS icon package."""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

from source_lock import read_archive_lock, write_lock


SOURCE = "@salesforce-ux/icons"
REPOSITORY_URL = "https://github.com/salesforce-ux/icons"
REGISTRY_URL = "https://registry.npmjs.org/@salesforce-ux/icons"
LICENSE = "CC BY-ND 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nd/4.0/"
PACKAGE_PREFIX = "package/dist/salesforce-lightning-design-system-icons"
APPROVED_CATEGORIES = ("action", "custom", "doctype", "standard")
EXCLUDED_CATEGORIES = ("utility",)
LIGHT_PAINT_LUMINANCE = 0.88
STYLE_PAINT_PATTERN = re.compile(r"(?:^|;)\s*(fill|stroke|stop-color)\s*:\s*([^;]+)", re.IGNORECASE)
HEX_COLOR_PATTERN = re.compile(r"^#(?P<value>[0-9a-f]{3}|[0-9a-f]{6})$", re.IGNORECASE)
RGB_COLOR_PATTERN = re.compile(r"^rgb\(\s*(?P<red>\d+)\s*,\s*(?P<green>\d+)\s*,\s*(?P<blue>\d+)\s*\)$", re.IGNORECASE)
PAINT_ATTRIBUTES = ("fill", "stroke", "stop-color")


def archive_url(version: str) -> str:
    return f"https://registry.npmjs.org/@salesforce-ux/icons/-/icons-{version}.tgz"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_member_name(member: tarfile.TarInfo) -> str:
    name = member.name
    if name.startswith("/") or ".." in Path(name).parts:
        raise ValueError(f"Salesforce archive has unsafe entry path: {name}")
    return name


def _read_member(archive: tarfile.TarFile, name: str) -> bytes:
    try:
        member = archive.getmember(name)
    except KeyError as exc:
        raise ValueError(f"Salesforce archive is missing required entry: {name}") from exc
    if not member.isfile():
        raise ValueError(f"Salesforce archive entry is not a file: {name}")
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"Salesforce archive entry cannot be read: {name}")
    return handle.read()


def _package_metadata(archive: tarfile.TarFile) -> dict:
    try:
        metadata = json.loads(_read_member(archive, "package/package.json"))
    except json.JSONDecodeError as exc:
        raise ValueError("Salesforce archive package metadata is not valid JSON") from exc
    if not isinstance(metadata, dict):
        raise ValueError("Salesforce archive package metadata is not an object")
    return metadata


def _validate_package_metadata(metadata: dict, expected_version: str) -> None:
    if metadata.get("name") != SOURCE:
        raise ValueError("Salesforce archive package name does not match the approved source")
    if metadata.get("version") != expected_version:
        raise ValueError("Salesforce archive package version does not match the source lock")
    if metadata.get("license") != "CC-BY-ND-4.0":
        raise ValueError("Salesforce archive package license does not match CC BY-ND 4.0")


def _metadata_by_category(archive: tarfile.TarFile) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for category in APPROVED_CATEGORIES:
        raw = _read_member(archive, f"package/dist/{category}-icons-metadata.json")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Salesforce {category} metadata is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Salesforce {category} metadata is not an object")
        category_metadata: dict[str, list[str]] = {}
        for name, entry in payload.items():
            synonyms = entry.get("synonyms", []) if isinstance(entry, dict) else []
            if not isinstance(synonyms, list) or not all(isinstance(term, str) for term in synonyms):
                raise ValueError(f"Salesforce {category} metadata has invalid synonyms for {name}")
            category_metadata[name] = [term.strip().lower() for term in synonyms if term.strip()]
        result[category] = category_metadata
    return result


def _paint_luminance(value: str) -> float | None:
    normalized = value.strip().lower()
    if normalized in {"none", "transparent"}:
        return None
    if normalized == "white":
        return 1.0

    hex_match = HEX_COLOR_PATTERN.fullmatch(normalized)
    if hex_match:
        raw_value = hex_match.group("value")
        if len(raw_value) == 3:
            channels = [int(channel * 2, 16) for channel in raw_value]
        else:
            channels = [int(raw_value[index:index + 2], 16) for index in range(0, 6, 2)]
        red, green, blue = (channel / 255 for channel in channels)
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    rgb_match = RGB_COLOR_PATTERN.fullmatch(normalized)
    if rgb_match:
        channels = [int(rgb_match.group(channel)) for channel in ("red", "green", "blue")]
        if any(channel > 255 for channel in channels):
            return None
        red, green, blue = (channel / 255 for channel in channels)
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    return None


def requires_contrast_preview(svg: bytes) -> bool:
    """Identify authored artwork that would disappear on a white preview surface."""

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise ValueError("Salesforce SVG is not valid XML") from exc

    paints: list[str] = []
    for element in root.iter():
        for attribute in PAINT_ATTRIBUTES:
            value = element.get(attribute)
            if value is not None:
                paints.append(value)
        style = element.get("style")
        if style:
            paints.extend(match.group(2) for match in STYLE_PAINT_PATTERN.finditer(style))

    visible_paints = [paint for paint in paints if paint.strip().lower() not in {"none", "transparent"}]
    if not visible_paints:
        return False

    luminances = [_paint_luminance(paint) for paint in visible_paints]
    return all(luminance is not None and luminance >= LIGHT_PAINT_LUMINANCE for luminance in luminances)


def _approved_entries(archive: tarfile.TarFile) -> list[dict]:
    metadata_by_category = _metadata_by_category(archive)
    entries: list[dict] = []
    prefix = f"{PACKAGE_PREFIX}/"
    for member in archive.getmembers():
        name = _safe_member_name(member)
        if not member.isfile() or not name.startswith(prefix) or not name.endswith(".svg"):
            continue
        parts = Path(name).parts
        if len(parts) != 5:
            continue
        category = parts[-2]
        if category not in APPROVED_CATEGORIES:
            continue
        source_name = Path(parts[-1]).stem
        svg = _read_member(archive, name)
        preview_theme_color = requires_contrast_preview(svg)
        entries.append(
            {
                "path": name,
                "sha256": _sha256_bytes(svg),
                "category": category,
                "sourceName": source_name,
                "metaphors": metadata_by_category[category].get(source_name, []),
                "previewThemeColor": preview_theme_color,
            }
        )
    entries.sort(key=lambda entry: entry["path"])
    if not entries:
        raise ValueError("Salesforce archive has no approved SVG entries")
    if not any(entry["category"] == "standard" and entry["sourceName"] == "mulesoft" for entry in entries):
        raise ValueError("Salesforce archive is missing the approved standard mulesoft icon")
    return entries


def _content_digest(entries: list[dict]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def write_source_lock(archive_path: Path, output_path: Path) -> dict:
    with tarfile.open(archive_path, "r:gz") as archive:
        metadata = _package_metadata(archive)
        version = metadata.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError("Salesforce archive package has no version")
        _validate_package_metadata(metadata, version)
        entries = _approved_entries(archive)

    payload = {
        "source": SOURCE,
        "repositoryUrl": REPOSITORY_URL,
        "registryUrl": REGISTRY_URL,
        "archiveUrl": archive_url(version),
        "packageVersion": version,
        "archiveSha256": _sha256_bytes(archive_path.read_bytes()),
        "contentSha256": _content_digest(entries),
        "includedCategories": list(APPROVED_CATEGORIES),
        "excludedCategories": list(EXCLUDED_CATEGORIES),
        "indexedAssetCount": len(entries),
        "indexedFamilyCount": len(entries),
        "entries": entries,
    }
    write_lock(output_path, payload)
    return payload


def _validate_lock_entries(lock: dict, entries: list[dict]) -> None:
    locked_entries = lock.get("entries")
    actual_entries = [
        {key: entry[key] for key in ("path", "sha256", "category", "sourceName")}
        for entry in entries
    ]
    expected_entries = [
        {key: entry.get(key) for key in ("path", "sha256", "category", "sourceName")}
        for entry in locked_entries
        if isinstance(entry, dict)
    ]
    if actual_entries != expected_entries or _content_digest(entries) != lock["contentSha256"]:
        raise ValueError("Salesforce archive entries do not match their source lock")


def generate_icons(archive_path: Path, source_lock_path: Path) -> list[dict]:
    lock_data = json.loads(source_lock_path.read_text(encoding="utf-8"))
    version = lock_data.get("packageVersion") if isinstance(lock_data, dict) else None
    if not isinstance(version, str) or not version:
        raise ValueError("Salesforce source lock has no package version")
    lock = read_archive_lock(source_lock_path, SOURCE, archive_url(version), version)
    if _sha256_bytes(archive_path.read_bytes()) != lock["archiveSha256"]:
        raise ValueError("Salesforce archive does not match its source lock")

    with tarfile.open(archive_path, "r:gz") as archive:
        metadata = _package_metadata(archive)
        _validate_package_metadata(metadata, version)
        entries = _approved_entries(archive)
    _validate_lock_entries(lock, entries)

    icons: list[dict] = []
    for entry in entries:
        category = entry["category"]
        source_name = entry["sourceName"]
        canonical_name = f"{category}_{source_name}"
        metaphors = list(dict.fromkeys([
            "salesforce",
            category,
            source_name.replace("_", " "),
            source_name,
            *entry["metaphors"],
        ]))
        descriptor = {
            "url": lock["archiveUrl"],
            "format": "npm-tgz-svg-entry",
            "entry": entry["path"],
            "archiveSha256": lock["archiveSha256"],
            "entrySha256": entry["sha256"],
        }
        icons.append(
            {
                "name": canonical_name,
                "displayName": source_name.replace("_", " ").title(),
                "description": f"Salesforce SLDS {category} icon: {source_name.replace('_', ' ')}.",
                "category": category,
                "metaphors": metaphors,
                "variants": {
                    "color": {
                        "defaultSize": 120,
                        "preserveSourceColors": True,
                        **(
                            {"previewThemeColor": True}
                            if entry["previewThemeColor"]
                            else {}
                        ),
                        "sourceCapabilities": {
                            "currentColor": False,
                            "boundingBox": False,
                        },
                        "sizes": {
                            "120": {
                                "sourceUrl": lock["archiveUrl"],
                                "remoteSource": descriptor,
                            }
                        },
                    }
                },
            }
        )
    return icons
