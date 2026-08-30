#!/usr/bin/env python3
"""Index public Azure Portal icon sources without retaining SVG payloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urljoin, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PORTAL_BASE_URL = "https://portal.azure.com/"
LIBRARY_PREFIX = "_generated/MsPortalImpl/Svg/Library/"
MANIFEST_GROUPS = (
    "assetTypes",
    "assetTypesBrowse",
    "assetTypesMenu",
    "browseMenus",
    "portalServices",
)
AMD_DEFINE_PATTERN = re.compile(
    r"define\(\s*(?P<module>\"(?:\\.|[^\"])*\")\s*,\s*\[\s*\"require\"\s*,\s*\"exports\"\s*\]"
)
SVG_ASSIGNMENT_PATTERN = re.compile(
    r"(?:\bdata|\.data)\s*=\s*(?P<svg>\"(?:\\.|[^\"])*\")"
)
CAMEL_WORD_PATTERN = re.compile(r"([A-Z]+)([A-Z][a-z])|([a-z0-9])([A-Z])")


class AzurePortalSchemaError(RuntimeError):
    """The public Portal bootstrap no longer has the expected non-executed shape."""


@dataclass(frozen=True)
class PortalSource:
    portal_base_url: str
    page_version: str
    bootstrap_config_hash: str
    require_config_hash: str
    require_config_url: str
    bundle_urls: tuple[str, ...]
    manifest_sources: tuple["ManifestSource", ...]


@dataclass(frozen=True)
class ManifestSource:
    category: str
    url: str


@dataclass(frozen=True)
class AzureBuildResult:
    icons: list[dict]
    core_indexed_count: int
    core_unique_svg_count: int
    manifest_indexed_count: int
    manifest_unique_svg_count: int
    unique_svg_count: int
    source_digest: str
    index_digest: str


def _browser_request(url: str) -> Request:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "portal.azure.com":
        raise AzurePortalSchemaError(f"Unexpected Portal source URL: {url}")
    return Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131 Safari/537.36"
            ),
            "Referer": PORTAL_BASE_URL,
            "Accept": "text/html,application/json,text/javascript,*/*;q=0.8",
        },
    )


def fetch_portal_text(url: str) -> str:
    """Fetch one public Portal resource without cookies, credentials, or evaluation."""

    with urlopen(_browser_request(url), timeout=45) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="strict")


def extract_json_call(script: str, function_name: str) -> dict:
    """Extract a JSON object passed to a Portal bootstrap call without evaluating JS."""

    marker = f"{function_name}("
    start = script.find(marker)
    if start < 0:
        raise AzurePortalSchemaError(f"Missing {function_name} bootstrap call")
    start += len(marker)
    while start < len(script) and script[start].isspace():
        start += 1
    if start >= len(script) or script[start] != "{":
        raise AzurePortalSchemaError(f"{function_name} does not start with JSON")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(script)):
        character = script[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(script[start : index + 1])
                except json.JSONDecodeError as exc:
                    raise AzurePortalSchemaError(
                        f"{function_name} bootstrap payload is not JSON"
                    ) from exc
                if not isinstance(payload, dict):
                    raise AzurePortalSchemaError(f"{function_name} payload is not an object")
                return payload
    raise AzurePortalSchemaError(f"Unterminated {function_name} bootstrap payload")


def canonical_json_digest(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def discover_manifest_sources(bootstrap: dict, portal_base_url: str) -> tuple[ManifestSource, ...]:
    try:
        manifest_hashes = bootstrap["portalServerConfig"]["environment"][
            "extensionsManifestHash"
        ]
    except (KeyError, TypeError) as exc:
        raise AzurePortalSchemaError("Portal bootstrap has no extension manifest hashes") from exc
    if not isinstance(manifest_hashes, dict):
        raise AzurePortalSchemaError("Portal extension manifest hashes are invalid")

    sources: list[ManifestSource] = []
    for category in MANIFEST_GROUPS:
        candidates = manifest_hashes.get(category)
        if not isinstance(candidates, list) or not candidates:
            raise AzurePortalSchemaError(
                f"Portal bootstrap has no default manifest hash for {category}"
            )
        first_candidate = candidates[0]
        if not isinstance(first_candidate, list) or not first_candidate:
            raise AzurePortalSchemaError(
                f"Portal manifest hash entry is invalid for {category}"
            )
        manifest_hash = first_candidate[0]
        if not isinstance(manifest_hash, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", manifest_hash
        ):
            raise AzurePortalSchemaError(
                f"Portal manifest hash is invalid for {category}"
            )
        sources.append(
            ManifestSource(
                category=category,
                url=urljoin(
                    portal_base_url,
                    f"Content/ExtensionManifest/{manifest_hash}.json",
                ),
            )
        )
    return tuple(sources)


def discover_portal_source(
    fetch_text: Callable[[str], str] = fetch_portal_text,
    portal_base_url: str = PORTAL_BASE_URL,
    fallback_require_config_url: Optional[str] = None,
) -> PortalSource:
    """Discover immutable core bundles and default extension manifests from Portal."""

    if portal_base_url != PORTAL_BASE_URL:
        raise AzurePortalSchemaError("Only the public Azure Portal host is supported")
    bootstrap = extract_json_call(
        fetch_text(portal_base_url), "MsPortalImpl.redirect"
    )
    try:
        portal_query = bootstrap["portalServerConfig"]["portalQuery"]
        config_hash = portal_query["configHash"]
        page_version = portal_query["pageVersion"]
    except (KeyError, TypeError) as exc:
        raise AzurePortalSchemaError("Portal bootstrap has no config hash/version") from exc
    if not isinstance(config_hash, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", config_hash):
        raise AzurePortalSchemaError("Portal config hash is invalid")
    if not isinstance(page_version, str) or not page_version:
        raise AzurePortalSchemaError("Portal page version is invalid")

    discovered_require_config_url = urljoin(
        portal_base_url, f"Content/PortalRequireConfig/{config_hash}.js"
    )
    require_config_url = discovered_require_config_url
    try:
        require_config_text = fetch_text(require_config_url)
    except HTTPError as exc:
        should_fallback = exc.code in {403, 404} and fallback_require_config_url is not None
        exc.close()
        if not should_fallback:
            raise
        parsed_fallback = urlparse(fallback_require_config_url)
        if (
            parsed_fallback.scheme != "https"
            or parsed_fallback.netloc != "portal.azure.com"
            or not re.fullmatch(
                r"/Content/PortalRequireConfig/[A-Za-z0-9_-]+\.js",
                parsed_fallback.path,
            )
        ):
            raise AzurePortalSchemaError("Previous source lock has an invalid RequireConfig URL")
        require_config_url = fallback_require_config_url
        require_config_text = fetch_text(require_config_url)
    require_payload = extract_json_call(require_config_text, "MsPortalImpl.setRequireConfig")
    try:
        dependency_tree = require_payload["requireConfig"]["dependencyTree"]
    except (KeyError, TypeError) as exc:
        raise AzurePortalSchemaError("Require config has no dependency tree") from exc
    if not isinstance(dependency_tree, dict):
        raise AzurePortalSchemaError("Require config dependency tree is invalid")

    bundles: list[str] = []
    for bundle_path, modules in sorted(dependency_tree.items()):
        if not isinstance(bundle_path, str) or not isinstance(modules, dict):
            continue
        if any(
            isinstance(module, str) and module.startswith(LIBRARY_PREFIX)
            for module in modules
        ):
            bundles.append(urljoin(portal_base_url, f"{bundle_path}.js"))
    if not bundles:
        raise AzurePortalSchemaError("Require config has no core library SVG modules")

    return PortalSource(
        portal_base_url=portal_base_url,
        page_version=page_version,
        bootstrap_config_hash=config_hash,
        require_config_hash=Path(urlparse(require_config_url).path).stem,
        require_config_url=require_config_url,
        bundle_urls=tuple(bundles),
        manifest_sources=discover_manifest_sources(bootstrap, portal_base_url),
    )


def _decode_js_string(value: str) -> str:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AzurePortalSchemaError("AMD SVG payload is not a JSON-compatible string") from exc
    if not isinstance(decoded, str):
        raise AzurePortalSchemaError("AMD SVG payload is not text")
    return decoded


def _matching_parenthesis(text: str, opening_index: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening_index, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    raise AzurePortalSchemaError("Unterminated AMD define call")


def canonical_svg_text(svg_text: str) -> str:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise AzurePortalSchemaError("AMD module has invalid SVG text") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise AzurePortalSchemaError("AMD module payload is not an SVG root")
    return ET.canonicalize(svg_text, with_comments=False, strip_text=True)


def parse_amd_svg_modules(bundle_text: str) -> list[tuple[str, str]]:
    """Return named public SVG AMD modules and canonical SVG text from one bundle."""

    modules: list[tuple[str, str]] = []
    for match in AMD_DEFINE_PATTERN.finditer(bundle_text):
        module_name = _decode_js_string(match.group("module"))
        if not module_name.startswith(LIBRARY_PREFIX) or not module_name.endswith(".svg"):
            continue
        call_end = _matching_parenthesis(bundle_text, bundle_text.find("(", match.start()))
        call_text = bundle_text[match.start() : call_end + 1]
        svg_match = SVG_ASSIGNMENT_PATTERN.search(call_text)
        if not svg_match:
            raise AzurePortalSchemaError(f"SVG AMD module has no data payload: {module_name}")
        modules.append((module_name, canonical_svg_text(_decode_js_string(svg_match.group("svg")))))
    return modules


def _snake_case(value: str) -> str:
    normalized = CAMEL_WORD_PATTERN.sub(
        lambda match: f"{match.group(1) or match.group(3)}_{match.group(2) or match.group(4)}",
        value,
    ).replace("-", "_")
    return re.sub(r"[^A-Za-z0-9_]+", "_", normalized).strip("_").lower()


def _display_name(value: str) -> str:
    return _snake_case(value).replace("_", " ").title()


def _module_metadata(module_name: str) -> tuple[str, str, list[str]]:
    relative = module_name[len(LIBRARY_PREFIX) : -len(".svg")]
    path_parts = relative.split("/")
    raw_name = path_parts[-1]
    category = path_parts[:-1]
    style = "color" if "Polychromatic" in category else "regular"
    if raw_name.endswith("Filled"):
        raw_name = raw_name[: -len("Filled")]
        style = "filled"
    tags = [_snake_case(part).replace("_", " ") for part in category]
    return _snake_case(raw_name), style, tags


def _source_descriptor(url: str, module_name: str, canonical_svg: str) -> dict:
    return {
        "url": url,
        "format": "portal-amd-svg-module",
        "selector": module_name,
        "sha256": hashlib.sha256(canonical_svg.encode("utf-8")).hexdigest(),
    }


def _json_pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _text_values(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]


def _meaningful_text(value: object) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _manifest_entry_label(entry: dict) -> str:
    for field in (
        "singularDisplayName",
        "displayName",
        "label",
        "display",
        "ariaLabel",
        "name",
        "id",
        "bladeName",
    ):
        label = _meaningful_text(entry.get(field))
        if label:
            return label
    resource_type = entry.get("resourceType")
    if isinstance(resource_type, dict):
        for field in ("resourceTypeName", "displayName", "name"):
            label = _meaningful_text(resource_type.get(field))
            if label:
                return label
    return "icon"


def _manifest_context_name(entry: dict, fallback: str) -> str:
    resource_type = entry.get("resourceType")
    if isinstance(resource_type, dict):
        for field in ("resourceTypeName", "name", "displayName"):
            value = _meaningful_text(resource_type.get(field))
            if value:
                return value
    for field in ("name", "id", "bladeName", "displayName", "label"):
        value = _meaningful_text(entry.get(field))
        if value:
            return value
    return fallback


def _manifest_category_tags(category: str) -> list[str]:
    return {
        "assetTypes": ["resource", "asset type"],
        "assetTypesBrowse": ["command", "browse"],
        "assetTypesMenu": ["menu", "command"],
        "browseMenus": ["browse", "menu"],
        "portalServices": ["service", "portal"],
    }.get(category, [category])


def _manifest_record(
    source: ManifestSource,
    pointer: list[str],
    extension_name: str,
    context_name: str,
    entry: dict,
    svg_text: str,
) -> dict:
    canonical_svg = canonical_svg_text(svg_text)
    label = _manifest_entry_label(entry)
    name_parts = ["azure", extension_name, source.category, context_name, label]
    name = "_".join(
        part for part in (_snake_case(part) for part in name_parts) if part
    )
    tags = {
        "azure",
        "portal",
        "extension manifest",
        *_manifest_category_tags(source.category),
        *_text_values(extension_name),
        *_text_values(context_name),
        *_text_values(label),
    }
    for field in ("keywords", "description", "toolTip", "tooltip", "ariaLabel"):
        value = entry.get(field)
        if isinstance(value, list):
            for item in value:
                tags.update(_text_values(item))
        else:
            tags.update(_text_values(value))
    description = next(
        (
            text
            for text in (
                _meaningful_text(entry.get("description")),
                _meaningful_text(entry.get("toolTip")),
                _meaningful_text(entry.get("tooltip")),
            )
            if text
        ),
        f"Azure Portal {source.category} icon: {label}.",
    )
    descriptor = {
        "url": source.url,
        "format": "portal-json-pointer-svg",
        "selector": "/" + "/".join(_json_pointer_token(part) for part in pointer),
        "sha256": hashlib.sha256(canonical_svg.encode("utf-8")).hexdigest(),
    }
    return {
        "name": name,
        "displayName": label,
        "description": description,
        "style": "regular",
        "tags": sorted(tags),
        "descriptor": descriptor,
    }


def _manifest_icon_records(
    source: ManifestSource, manifest_payload: object
) -> list[dict]:
    if not isinstance(manifest_payload, dict) or not isinstance(
        manifest_payload.get("manifest"), dict
    ):
        raise AzurePortalSchemaError(
            f"Extension manifest is missing its manifest object: {source.url}"
        )

    records: list[dict] = []

    def visit(
        value: object,
        pointer: list[str],
        extension_name: str,
        context_name: str,
    ) -> None:
        if isinstance(value, dict):
            icon = value.get("icon")
            if isinstance(icon, dict) and isinstance(icon.get("data"), str):
                records.append(
                    _manifest_record(
                        source,
                        pointer + ["icon", "data"],
                        extension_name,
                        context_name,
                        value,
                        icon["data"],
                    )
                )
            for key, child in value.items():
                if key == "icon":
                    continue
                visit(child, pointer + [key], extension_name, context_name)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                child_context = context_name
                if isinstance(child, dict):
                    item_context = _manifest_context_name(
                        child, f"{context_name}_{index}"
                    )
                    child_context = (
                        item_context
                        if context_name == extension_name
                        else f"{context_name}_{item_context}"
                    )
                visit(child, pointer + [str(index)], extension_name, child_context)

    manifest = manifest_payload["manifest"]
    for extension_name, extension_value in sorted(manifest.items()):
        if not isinstance(extension_name, str) or not isinstance(extension_value, dict):
            raise AzurePortalSchemaError(
                f"Extension manifest has an invalid extension entry: {source.url}"
            )
        category_value = extension_value.get(source.category)
        if category_value is not None:
            visit(
                category_value,
                ["manifest", extension_name, source.category],
                extension_name,
                extension_name,
            )
    if not records:
        raise AzurePortalSchemaError(
            f"Extension manifest has no icon.data SVG fields for {source.category}"
        )
    return records


def _collapse_records(records: list[dict]) -> tuple[list[dict], int]:
    """Deduplicate canonical SVGs and guarantee one generated family per name."""

    by_hash: dict[str, list[dict]] = {}
    for record in records:
        by_hash.setdefault(record["descriptor"]["sha256"], []).append(record)

    style_rank = {"regular": 0, "filled": 1, "color": 2}
    collapsed: list[dict] = []
    for duplicate_records in by_hash.values():
        ordered = sorted(
            duplicate_records,
            key=lambda record: (
                record["name"],
                style_rank[record["style"]],
                record["descriptor"]["url"],
                record["descriptor"]["selector"],
            ),
        )
        primary = ordered[0]
        collapsed.append(
            {
                "name": primary["name"],
                "displayName": primary["displayName"],
                "description": primary["description"],
                "style": primary["style"],
                "tags": sorted({tag for record in ordered for tag in record["tags"]}),
                "aliases": sorted(
                    {
                        record["name"]
                        for record in ordered[1:]
                        if record["name"] != primary["name"]
                    }
                ),
                "remoteSource": primary["descriptor"],
                "remoteSources": [record["descriptor"] for record in ordered],
            }
        )

    families: dict[str, dict] = {}
    for member in sorted(
        collapsed,
        key=lambda member: (
            member["name"],
            style_rank[member["style"]],
            member["remoteSource"]["sha256"],
        ),
    ):
        family_name = member["name"]
        family = families.get(family_name)
        if family is not None and member["style"] in family["variants"]:
            suffix = f"_{member['style']}_{member['remoteSource']['sha256'][:8]}"
            family_name = f"{member['name']}{suffix}"
            sequence = 2
            while family_name in families:
                family_name = f"{member['name']}{suffix}_{sequence}"
                sequence += 1
            member = dict(member)
            member["aliases"] = sorted(set(member["aliases"]) | {member["name"]})
            family = None
        if family is None:
            family = {
                "name": family_name,
                "displayName": member["displayName"],
                "description": member["description"],
                "tags": set(),
                "aliases": set(),
                "variants": {},
            }
            families[family_name] = family
        family["tags"].update(member["tags"])
        family["aliases"].update(member["aliases"])
        variant = {
            "defaultSize": 16,
            "remoteSource": member["remoteSource"],
            "sizes": {"16": {"remoteSource": member["remoteSource"]}},
        }
        if len(member["remoteSources"]) > 1:
            variant["remoteSources"] = member["remoteSources"]
        family["variants"][member["style"]] = variant

    icons: list[dict] = []
    for name, family in sorted(families.items()):
        icon = {
            "name": name,
            "displayName": family["displayName"],
            "description": family["description"],
            "metaphors": sorted(family["tags"]),
            "variants": {
                style: family["variants"][style]
                for style in sorted(family["variants"], key=style_rank.__getitem__)
            },
        }
        aliases = sorted(alias for alias in family["aliases"] if alias != name)
        if aliases:
            icon["aliases"] = aliases
        icons.append(icon)
    return icons, len(by_hash)


def _core_records(
    source: PortalSource,
    fetch_text: Callable[[str], str] = fetch_portal_text,
) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    source_digests: list[dict] = []
    for bundle_url in source.bundle_urls:
        bundle_text = fetch_text(bundle_url)
        source_digests.append(
            {
                "url": bundle_url,
                "sha256": hashlib.sha256(bundle_text.encode("utf-8")).hexdigest(),
            }
        )
        for module_name, canonical_svg in parse_amd_svg_modules(bundle_text):
            name, style, tags = _module_metadata(module_name)
            records.append(
                {
                    "name": name,
                    "displayName": _display_name(name),
                    "description": f"Azure Portal core icon: {_display_name(name)}.",
                    "style": style,
                    "tags": ["azure", "portal", "core", *tags],
                    "descriptor": _source_descriptor(bundle_url, module_name, canonical_svg),
                }
            )
    if not records:
        raise AzurePortalSchemaError("Portal bundles contained no named core SVG modules")
    return records, source_digests


def build_azure_catalog(
    source: PortalSource,
    fetch_text: Callable[[str], str] = fetch_portal_text,
) -> AzureBuildResult:
    """Build core and extension-manifest entries without retaining SVG source text."""

    core_records, core_source_digests = _core_records(source, fetch_text)
    manifest_records: list[dict] = []
    manifest_source_digests: list[dict] = []
    for manifest_source in source.manifest_sources:
        manifest_text = fetch_text(manifest_source.url)
        try:
            manifest_payload = json.loads(manifest_text)
        except json.JSONDecodeError as exc:
            raise AzurePortalSchemaError(
                f"Extension manifest is not JSON: {manifest_source.url}"
            ) from exc
        manifest_source_digests.append(
            {
                "category": manifest_source.category,
                "url": manifest_source.url,
                "sha256": canonical_json_digest(manifest_payload),
            }
        )
        manifest_records.extend(_manifest_icon_records(manifest_source, manifest_payload))

    icons, unique_svg_count = _collapse_records(core_records + manifest_records)
    _, core_unique_svg_count = _collapse_records(core_records)
    manifest_icons, manifest_unique_svg_count = _collapse_records(manifest_records)
    return AzureBuildResult(
        icons=icons,
        core_indexed_count=len(_collapse_records(core_records)[0]),
        core_unique_svg_count=core_unique_svg_count,
        manifest_indexed_count=len(manifest_icons),
        manifest_unique_svg_count=manifest_unique_svg_count,
        unique_svg_count=unique_svg_count,
        source_digest=canonical_json_digest(
            {"amdBundles": core_source_digests, "extensionManifests": manifest_source_digests}
        ),
        index_digest=canonical_json_digest(icons),
    )


def build_azure_icons(
    source: PortalSource,
    fetch_text: Callable[[str], str] = fetch_portal_text,
) -> tuple[list[dict], int]:
    """Compatibility wrapper returning the generated Azure index and SVG count."""

    result = build_azure_catalog(source, fetch_text)
    return result.icons, result.unique_svg_count


def source_lock_payload(source: PortalSource, result: AzureBuildResult) -> dict:
    return {
        "portalBaseUrl": source.portal_base_url,
        "pageVersion": source.page_version,
        "bootstrapConfigHash": source.bootstrap_config_hash,
        "requireConfigHash": source.require_config_hash,
        "requireConfigUrl": source.require_config_url,
        "amdBundleUrls": list(source.bundle_urls),
        "extensionManifestSources": [
            {"category": manifest_source.category, "url": manifest_source.url}
            for manifest_source in source.manifest_sources
        ],
        "coreIndexedCount": result.core_indexed_count,
        "coreUniqueSvgCount": result.core_unique_svg_count,
        "manifestIndexedCount": result.manifest_indexed_count,
        "manifestUniqueSvgCount": result.manifest_unique_svg_count,
        "indexedCount": len(result.icons),
        "uniqueSvgCount": result.unique_svg_count,
        "sourceDigest": result.source_digest,
        "indexDigest": result.index_digest,
    }


def write_source_lock(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def previous_count(path: Optional[Path], field: str = "indexedCount") -> Optional[int]:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get(field)
    except (OSError, ValueError, TypeError) as exc:
        raise AzurePortalSchemaError(f"Invalid previous Azure source lock: {path}") from exc
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        raise AzurePortalSchemaError(f"Invalid {field} count in {path}")
    return value


def previous_require_config_url(path: Optional[Path], page_version: str) -> Optional[str]:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        locked_page_version = payload["pageVersion"]
        require_config_url = payload["requireConfigUrl"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AzurePortalSchemaError(f"Invalid previous Azure source lock: {path}") from exc
    if locked_page_version != page_version:
        return None
    return require_config_url if isinstance(require_config_url, str) else None


def enforce_count_gate(
    indexed_count: int,
    minimum_count: int,
    previous_count: Optional[int],
) -> None:
    if indexed_count < minimum_count:
        raise AzurePortalSchemaError(
            f"Azure Portal indexed count collapsed to {indexed_count}; minimum is {minimum_count}"
        )
    if previous_count is not None and indexed_count * 100 < previous_count * 75:
        raise AzurePortalSchemaError(
            "Azure Portal indexed count collapsed from "
            f"{previous_count} to {indexed_count} (more than 25%)"
        )


def generate_azure_icons(
    source_lock_path: Path,
    previous_source_lock_path: Optional[Path] = None,
    core_minimum_count: int = 250,
    manifest_minimum_count: int = 100,
    fetch_text: Callable[[str], str] = fetch_portal_text,
) -> list[dict]:
    bootstrap = extract_json_call(fetch_text(PORTAL_BASE_URL), "MsPortalImpl.redirect")
    try:
        page_version = bootstrap["portalServerConfig"]["portalQuery"]["pageVersion"]
    except (KeyError, TypeError) as exc:
        raise AzurePortalSchemaError("Portal bootstrap has no page version") from exc
    source = discover_portal_source(
        fetch_text=fetch_text,
        fallback_require_config_url=previous_require_config_url(
            previous_source_lock_path, page_version
        ),
    )
    result = build_azure_catalog(source, fetch_text=fetch_text)
    enforce_count_gate(
        result.core_indexed_count,
        core_minimum_count,
        previous_count(previous_source_lock_path, "coreIndexedCount")
        or previous_count(previous_source_lock_path),
    )
    enforce_count_gate(
        result.manifest_indexed_count,
        manifest_minimum_count,
        previous_count(previous_source_lock_path, "manifestIndexedCount"),
    )
    write_source_lock(source_lock_path, source_lock_payload(source, result))
    return result.icons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", required=True, help="Generated source lock path")
    parser.add_argument("--previous-source-lock", default="", help="Prior committed source lock")
    parser.add_argument(
        "--seed-require-config-url",
        default="",
        help="One-time verified public RequireConfig URL used only when no prior lock exists",
    )
    parser.add_argument("--minimum-count", type=int, default=250)
    parser.add_argument("--manifest-minimum-count", type=int, default=100)
    args = parser.parse_args()
    previous_lock = Path(args.previous_source_lock) if args.previous_source_lock else None
    if args.seed_require_config_url:
        source = discover_portal_source(
            fallback_require_config_url=args.seed_require_config_url
        )
        result = build_azure_catalog(source)
        enforce_count_gate(
            result.core_indexed_count,
            args.minimum_count,
            previous_count(previous_lock, "coreIndexedCount")
            or previous_count(previous_lock),
        )
        enforce_count_gate(
            result.manifest_indexed_count,
            args.manifest_minimum_count,
            previous_count(previous_lock, "manifestIndexedCount"),
        )
        write_source_lock(
            Path(args.source_lock), source_lock_payload(source, result)
        )
        icons = result.icons
    else:
        icons = generate_azure_icons(
            source_lock_path=Path(args.source_lock),
            previous_source_lock_path=previous_lock,
            core_minimum_count=args.minimum_count,
            manifest_minimum_count=args.manifest_minimum_count,
        )
    print(f"Indexed {len(icons)} Azure Portal icons -> {args.source_lock}")


if __name__ == "__main__":
    main()
