"""Digest-bound adapter for the official AWS Architecture Icons ZIP archive."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import urlparse
from urllib.request import urlopen

from source_lock import MINIMUM_COUNT_RATIO_PERCENT, write_lock


SOURCE = "AWS Architecture Icons"
ARCHITECTURE_ICONS_PAGE_URL = "https://aws.amazon.com/architecture/icons/"
TERMS_URL = "https://aws.amazon.com/terms/"
ARCHIVE_URL_PATTERN = re.compile(
    r"https://d1\.awsstatic\.com/[^\"'<>{}\s]+/architecture-icon-release/"
    r"Icon-package_[^\"'<>{}\s]+\.zip",
    re.IGNORECASE,
)
ROOT_PATTERNS = {
    "Service": re.compile(r"^Architecture-Service-Icons_(?P<release>\d{8})$"),
    "Resource": re.compile(r"^Resource-Icons_(?P<release>\d{8})$"),
    "Category": re.compile(r"^Category-Icons_(?P<release>\d{8})$"),
    "Group": re.compile(r"^Architecture-Group-Icons_(?P<release>\d{8})$"),
}
ROOT_KIND_BY_NAME = {pattern: kind for kind, pattern in ROOT_PATTERNS.items()}
ENTRY_NAME_PATTERN = re.compile(
    r"^(?P<name>.+)_(?P<size>16|32|48|64)(?:_(?P<theme>Dark|Light))?$",
    re.IGNORECASE,
)
SERVICE_CATEGORY_PATTERN = re.compile(r"^Arch_(?P<category>[A-Za-z0-9-]+)$")
RESOURCE_CATEGORY_PATTERN = re.compile(r"^Res_(?P<category>[A-Za-z0-9-]+)$")
CATEGORY_SIZE_DIRECTORY_PATTERN = re.compile(r"^Arch-Category_(?P<size>16|32|48|64)$")
RESOURCE_THEME_DIRECTORY_PATTERN = re.compile(
    r"^Res_(?P<size>16|32|48|64)_(?P<theme>Dark|Light)$", re.IGNORECASE
)
MINIMUM_ASSET_COUNT = 1500
MINIMUM_KIND_COUNTS = {"Service": 900, "Resource": 350, "Category": 80, "Group": 10}
PREFERRED_SIZES = (32, 48, 64, 16)


@dataclass(frozen=True)
class AwsArchiveEntry:
    path: str
    sha256: str
    kind: str
    source_category: str
    source_name: str
    size: int
    theme: str


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _slugify(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def _humanize(value: str) -> str:
    words = re.sub(r"[_-]+", " ", value).split()
    replacements = {"aws": "AWS", "iot": "IoT", "ec2": "EC2", "vpc": "VPC", "s3": "S3"}
    return " ".join(replacements.get(word.lower(), word) for word in words)


def _is_macos_metadata(path: PurePosixPath) -> bool:
    return "__MACOSX" in path.parts or path.name == ".DS_Store" or path.name.startswith("._")


def _safe_archive_path(name: str) -> PurePosixPath:
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise ValueError(f"AWS archive has unsafe entry path: {name}")
    path = PurePosixPath(name)
    if ".." in path.parts or path.is_absolute():
        raise ValueError(f"AWS archive has unsafe entry path: {name}")
    return path


def _kind_for_root(root: str) -> tuple[str, str]:
    matches = [
        (kind, match)
        for kind, pattern in ROOT_PATTERNS.items()
        if (match := pattern.fullmatch(root)) is not None
    ]
    if len(matches) != 1:
        raise ValueError(f"AWS archive has unexpected SVG root directory: {root}")
    kind, match = matches[0]
    return kind, match.group("release")


def _parse_entry_path(path: PurePosixPath) -> tuple[str, str, str, int, str]:
    kind, _release = _kind_for_root(path.parts[0])
    match = ENTRY_NAME_PATTERN.fullmatch(path.stem)
    if match is None:
        raise ValueError(f"AWS archive has an SVG without a supported size suffix: {path}")
    source_name = match.group("name")
    size = int(match.group("size"))
    theme = (match.group("theme") or "").title()

    if kind == "Service":
        if len(path.parts) != 4 or path.parts[2] != str(size) or theme:
            raise ValueError(f"AWS Service icon has unexpected layout: {path}")
        category_match = SERVICE_CATEGORY_PATTERN.fullmatch(path.parts[1])
        if category_match is None or not source_name.startswith("Arch_"):
            raise ValueError(f"AWS Service icon has unexpected taxonomy: {path}")
        return kind, category_match.group("category"), source_name.removeprefix("Arch_"), size, theme

    if kind == "Resource":
        category_match = RESOURCE_CATEGORY_PATTERN.fullmatch(path.parts[1]) if len(path.parts) >= 2 else None
        if category_match is None or not source_name.startswith("Res_"):
            raise ValueError(f"AWS Resource icon has unexpected taxonomy: {path}")
        if len(path.parts) == 3:
            if theme:
                raise ValueError(f"AWS Resource icon has themed filename outside themed directory: {path}")
        elif len(path.parts) == 4:
            theme_directory = RESOURCE_THEME_DIRECTORY_PATTERN.fullmatch(path.parts[2])
            if theme_directory is None or theme_directory.group("size") != str(size):
                raise ValueError(f"AWS Resource icon has unexpected themed layout: {path}")
            if theme_directory.group("theme").title() != theme:
                raise ValueError(f"AWS Resource icon theme does not match directory: {path}")
        else:
            raise ValueError(f"AWS Resource icon has unexpected layout: {path}")
        return kind, category_match.group("category"), source_name.removeprefix("Res_"), size, theme

    if kind == "Category":
        if len(path.parts) != 3 or theme or not source_name.startswith("Arch-Category_"):
            raise ValueError(f"AWS Category icon has unexpected layout: {path}")
        directory_match = CATEGORY_SIZE_DIRECTORY_PATTERN.fullmatch(path.parts[1])
        if directory_match is None or directory_match.group("size") != str(size):
            raise ValueError(f"AWS Category icon size does not match directory: {path}")
        return kind, "", source_name.removeprefix("Arch-Category_"), size, theme

    if len(path.parts) != 2:
        raise ValueError(f"AWS Group icon has unexpected layout: {path}")
    return kind, "", source_name, size, theme


def _validate_svg(data: bytes, path: PurePosixPath) -> None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"AWS archive SVG is not valid XML: {path}") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValueError(f"AWS archive entry is not an SVG document: {path}")


def inspect_archive(archive_path: Path) -> tuple[str, list[AwsArchiveEntry]]:
    """Read and validate the approved vector-only Architecture Icons archive."""

    release: str | None = None
    seen_paths: set[str] = set()
    entries: list[AwsArchiveEntry] = []
    kind_counts = defaultdict(int)
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            path = _safe_archive_path(info.filename)
            if info.filename in seen_paths:
                raise ValueError(f"AWS archive has duplicate entry path: {info.filename}")
            seen_paths.add(info.filename)
            if info.is_dir() or _is_macos_metadata(path):
                continue
            if path.suffix.lower() != ".svg":
                continue
            kind, entry_release = _kind_for_root(path.parts[0])
            if release is None:
                release = entry_release
            elif release != entry_release:
                raise ValueError("AWS archive mixes Architecture Icon release directories")
            data = archive.read(info)
            _validate_svg(data, path)
            kind, source_category, source_name, size, theme = _parse_entry_path(path)
            entries.append(
                AwsArchiveEntry(
                    path=path.as_posix(),
                    sha256=_sha256_bytes(data),
                    kind=kind,
                    source_category=source_category,
                    source_name=source_name,
                    size=size,
                    theme=theme,
                )
            )
            kind_counts[kind] += 1

    if release is None or not entries:
        raise ValueError("AWS archive has no approved vector SVG entries")
    if len(entries) < MINIMUM_ASSET_COUNT:
        raise ValueError(
            f"AWS archive indexed asset count {len(entries)} is below {MINIMUM_ASSET_COUNT}"
        )
    for kind, minimum in MINIMUM_KIND_COUNTS.items():
        if kind_counts[kind] < minimum:
            raise ValueError(
                f"AWS archive {kind} count {kind_counts[kind]} is below {minimum}"
            )
    return release, sorted(entries, key=lambda entry: entry.path)


def _content_digest(entries: list[AwsArchiveEntry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry.sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _family_count(entries: list[AwsArchiveEntry]) -> int:
    return len({_family_key(entry) for entry in entries})


def _family_key(entry: AwsArchiveEntry) -> tuple[str, str, str, str]:
    return entry.kind, entry.source_category, entry.source_name, entry.theme


def discover_archive_url(
    fetch_text: Callable[[str], str] | None = None,
) -> str:
    """Return the single current Architecture Icons ZIP advertised by AWS itself."""

    if fetch_text is None:
        def fetch_text(url: str) -> str:
            with urlopen(url, timeout=30) as response:
                return response.read().decode("utf-8")

    page = html.unescape(fetch_text(ARCHITECTURE_ICONS_PAGE_URL))
    candidates = sorted(set(ARCHIVE_URL_PATTERN.findall(page)))
    if len(candidates) != 1:
        raise ValueError(
            "AWS Architecture Icons page must advertise exactly one Icon-package ZIP"
        )
    archive_url = candidates[0]
    parsed = urlparse(archive_url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "d1.awsstatic.com"
        or not parsed.path.startswith(
            "/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_"
        )
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("AWS Architecture Icons page advertised an unexpected archive URL")
    return archive_url


def write_source_lock(archive_path: Path, output_path: Path, archive_url: str) -> dict:
    release, entries = inspect_archive(archive_path)
    kind_counts = {kind: sum(entry.kind == kind for entry in entries) for kind in ROOT_PATTERNS}
    payload = {
        "source": SOURCE,
        "architectureIconsPageUrl": ARCHITECTURE_ICONS_PAGE_URL,
        "termsUrl": TERMS_URL,
        "archiveUrl": archive_url,
        "release": release,
        "archiveSha256": _sha256_bytes(archive_path.read_bytes()),
        "contentSha256": _content_digest(entries),
        "includedKinds": list(ROOT_PATTERNS),
        "indexedAssetCount": len(entries),
        "indexedFamilyCount": _family_count(entries),
        "kindCounts": kind_counts,
        "entries": [
            {
                "path": entry.path,
                "sha256": entry.sha256,
                "kind": entry.kind,
                "sourceCategory": entry.source_category,
                "sourceName": entry.source_name,
                "size": entry.size,
                **({"theme": entry.theme} if entry.theme else {}),
            }
            for entry in entries
        ],
    }
    write_lock(output_path, payload)
    return payload


def read_source_lock(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read AWS source lock {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("source") != SOURCE:
        raise ValueError(f"Source lock {path} is not for {SOURCE}")
    if payload.get("architectureIconsPageUrl") != ARCHITECTURE_ICONS_PAGE_URL:
        raise ValueError(f"AWS source lock {path} has an unexpected source page")
    if payload.get("termsUrl") != TERMS_URL:
        raise ValueError(f"AWS source lock {path} has an unexpected terms URL")
    if not isinstance(payload.get("archiveUrl"), str):
        raise ValueError(f"AWS source lock {path} has no archive URL")
    for field in ("archiveSha256", "contentSha256"):
        value = payload.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError(f"AWS source lock {path} has no valid {field}")
    if payload.get("includedKinds") != list(ROOT_PATTERNS):
        raise ValueError(f"AWS source lock {path} changes the approved icon kinds")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"AWS source lock {path} has no indexed archive entries")
    return payload


def validate_candidate_lock(candidate_path: Path, previous_path: Path) -> dict:
    """Reject candidate scope or per-kind count collapses before promotion."""

    candidate = read_source_lock(candidate_path)
    previous = read_source_lock(previous_path)
    for field in ("indexedAssetCount", "indexedFamilyCount"):
        candidate_count = candidate.get(field)
        previous_count = previous.get(field)
        if not isinstance(candidate_count, int) or not isinstance(previous_count, int):
            raise ValueError(f"AWS source locks have invalid {field}")
        if candidate_count * 100 < previous_count * MINIMUM_COUNT_RATIO_PERCENT:
            raise ValueError(
                f"AWS candidate {field} collapsed from {previous_count} to {candidate_count}, "
                f"below {MINIMUM_COUNT_RATIO_PERCENT}% of prior"
            )
    for kind in ROOT_PATTERNS:
        candidate_count = candidate.get("kindCounts", {}).get(kind)
        previous_count = previous.get("kindCounts", {}).get(kind)
        if not isinstance(candidate_count, int) or not isinstance(previous_count, int):
            raise ValueError(f"AWS source locks have invalid {kind} count")
        if candidate_count * 100 < previous_count * MINIMUM_COUNT_RATIO_PERCENT:
            raise ValueError(
                f"AWS candidate {kind} count collapsed from {previous_count} to {candidate_count}, "
                f"below {MINIMUM_COUNT_RATIO_PERCENT}% of prior"
            )
    return candidate


def _entries_from_lock(lock: dict) -> list[AwsArchiveEntry]:
    entries: list[AwsArchiveEntry] = []
    for raw_entry in lock["entries"]:
        if not isinstance(raw_entry, dict):
            raise ValueError("AWS source lock has an invalid archive entry")
        try:
            entry = AwsArchiveEntry(
                path=str(raw_entry["path"]),
                sha256=str(raw_entry["sha256"]),
                kind=str(raw_entry["kind"]),
                source_category=str(raw_entry["sourceCategory"]),
                source_name=str(raw_entry["sourceName"]),
                size=int(raw_entry["size"]),
                theme=str(raw_entry.get("theme", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("AWS source lock has an invalid archive entry") from exc
        if entry.kind not in ROOT_PATTERNS or not re.fullmatch(r"[0-9a-f]{64}", entry.sha256):
            raise ValueError("AWS source lock has an invalid archive entry")
        entries.append(entry)
    return entries


def _validate_lock_entries(lock: dict, entries: list[AwsArchiveEntry]) -> None:
    if _content_digest(entries) != lock["contentSha256"]:
        raise ValueError("AWS archive entries do not match their source lock")
    locked = _entries_from_lock(lock)
    if entries != locked:
        raise ValueError("AWS archive entries do not match their source lock")


def _default_size(sizes: list[int]) -> int:
    for preferred in PREFERRED_SIZES:
        if preferred in sizes:
            return preferred
    return min(sizes)


def _icon_category(entry: AwsArchiveEntry) -> str:
    if entry.kind in {"Service", "Resource"}:
        return f"{entry.kind} / {_humanize(entry.source_category)}"
    return entry.kind


def _icon_name(entry: AwsArchiveEntry) -> str:
    parts = [entry.kind]
    if entry.source_category:
        parts.append(entry.source_category)
    parts.append(entry.source_name)
    if entry.theme:
        parts.append(entry.theme)
    return _slugify(" ".join(parts))


def generate_icons(archive_path: Path, source_lock_path: Path) -> list[dict]:
    """Emit descriptor-only AWS icon families from a verified source lock."""

    lock = read_source_lock(source_lock_path)
    if _sha256_bytes(archive_path.read_bytes()) != lock["archiveSha256"]:
        raise ValueError("AWS archive does not match its source lock")
    release, entries = inspect_archive(archive_path)
    if release != lock.get("release"):
        raise ValueError("AWS archive release does not match its source lock")
    _validate_lock_entries(lock, entries)

    grouped: dict[tuple[str, str, str, str], list[AwsArchiveEntry]] = defaultdict(list)
    for entry in entries:
        grouped[_family_key(entry)].append(entry)

    icons: list[dict] = []
    for family_entries in grouped.values():
        representative = family_entries[0]
        # AWS publishes authored colour artwork for every Architecture Icon,
        # including the non-Dark/Light source files.
        style = "color"
        sizes: dict[str, dict] = {}
        for entry in sorted(family_entries, key=lambda candidate: candidate.size):
            size_key = str(entry.size)
            if size_key in sizes:
                raise ValueError(f"AWS archive has duplicate family size: {entry.path}")
            sizes[size_key] = {
                "remoteSource": {
                    "url": lock["archiveUrl"],
                    "format": "zip-svg-entry",
                    "entry": entry.path,
                    "archiveSha256": lock["archiveSha256"],
                    "entrySha256": entry.sha256,
                }
            }
        available_sizes = [int(size) for size in sizes]
        default_size = _default_size(available_sizes)
        variant = {
            "defaultSize": default_size,
            "preserveSourceColors": True,
            "sourceCapabilities": {"currentColor": False, "boundingBox": False},
            "sizes": sizes,
        }
        display_name = _humanize(representative.source_name)
        if representative.theme:
            display_name = f"{display_name} {representative.theme}"
        icon = {
            "name": _icon_name(representative),
            "displayName": display_name,
            "description": f"AWS {representative.kind.lower()} architecture icon: {display_name}.",
            "category": _icon_category(representative),
            "metaphors": list(
                dict.fromkeys(
                    [
                        "aws",
                        representative.kind.lower(),
                        representative.source_category.lower(),
                        representative.source_name.lower(),
                        representative.source_name.replace("-", " ").replace("_", " ").lower(),
                        *( [representative.theme.lower()] if representative.theme else [] ),
                    ]
                )
            ),
            "variants": {style: variant},
        }
        icons.append(icon)
    icons.sort(key=lambda icon: icon["name"])
    if len({icon["name"] for icon in icons}) != len(icons):
        raise ValueError("AWS archive produced duplicate canonical icon names")
    return icons


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect AWS Architecture Icons archives")
    parser.add_argument("--discover-archive-url", action="store_true")
    parser.add_argument("--archive", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--archive-url", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.discover_archive_url:
        print(discover_archive_url())
        return
    if not args.archive or not args.output or not args.archive_url:
        raise SystemExit("--archive, --output, and --archive-url are required")
    write_source_lock(Path(args.archive), Path(args.output), args.archive_url)


if __name__ == "__main__":
    main()
