"""Create and validate deterministic, static GCP Console SVG icon archives.

This module deliberately treats Console JavaScript as untrusted text.  It scans
only complete JavaScript string/template literals, rejects interpolated template
literals, and never executes a module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from gcp_console_archive_notice import REFERENTIAL_FAIR_USE_NOTICE_BYTES


SOURCE = "Google Cloud Console"
ARCHIVE_FORMAT = "gcp-console-svg-archive-v1"
ROUTE_MAP_URL = "https://console.cloud.google.com/p/routemapdata"
XSSI_PREFIX = b")]}'\n"
NOTICE_NAME = "REFERENTIAL-FAIR-USE.md"
MANIFEST_NAME = "manifest.json"
LOCK_NAME = "source-lock.json"
ICON_PREFIX = "icons/"
ICON_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ROUTE_EXTENSION_PATTERN = re.compile(
    r"^routes/features(?:/[^/]+)*/extensions/(?P<extension>[A-Za-z0-9._-]+)$"
)
MODULE_KEY_PATTERN = re.compile(
    r"^k=boq-cloud-client\.(?P<module>[A-Za-z0-9]+(?:MicroUi|StandaloneUi))\.en_US(?:\.[A-Za-z0-9._-]+)?$"
)
URL_PATTERN = re.compile(r"https://[^\s\"'<>]+")
DRAWABLE_SVG_ELEMENTS = frozenset({
    "circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text",
})
NON_RENDERING_SVG_CONTAINERS = frozenset({
    "clippath", "defs", "marker", "mask", "pattern", "symbol",
})
LOCAL_FRAGMENT_REFERENCE_PATTERN = re.compile(r"^#[-\w:.]+$")


@dataclass(frozen=True)
class Module:
    identifier: str
    extension: str
    module: str
    url: str
    sha256: str


@dataclass(frozen=True)
class ExtractedIcon:
    data_icon_name: str | None
    svg: bytes
    module: Module
    template_index: int


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _safe_member_name(name: str) -> PurePosixPath:
    if not name or name.startswith(("/", "\\")) or "\\" in name:
        raise ValueError(f"Unsafe archive member path: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive member path: {name}")
    return path


def _module_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.gstatic.com":
        raise ValueError(f"Module URL is not an official HTTPS www.gstatic.com URL: {url}")
    if parsed.query or parsed.fragment:
        raise ValueError(f"Module URL must not contain a query or fragment: {url}")
    prefix = "/_/mss/boq-cloud-client/_/js/"
    if not parsed.path.startswith(prefix):
        raise ValueError(f"Module URL is not a boq-cloud-client JavaScript path: {url}")
    match = next(
        (candidate for segment in parsed.path.split("/") if (candidate := MODULE_KEY_PATTERN.fullmatch(segment))),
        None,
    )
    if match is None:
        raise ValueError(f"Module URL has no Console MicroUi or StandaloneUi k= segment: {url}")
    return match.group("module")


def _is_console_javascript_path(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.startswith("/_/mss/boq-cloud-client/_/js/")


def _canonical_module_url(url: str) -> str:
    """Drop routemap tracking parameters before validating or pinning a module URL."""

    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl()


def _stable_id(extension: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9]+", "-", extension).strip("-").lower()
    if not identifier or not ICON_NAME_PATTERN.fullmatch(identifier):
        raise ValueError(f"GCP Console route extension has no safe stable id: {extension}")
    return identifier


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    return []


def _route_extension_values(value: object) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("GCP Console routemap has a non-string route key")
            match = ROUTE_EXTENSION_PATTERN.fullmatch(key)
            if match:
                if not isinstance(child, str):
                    raise ValueError(f"GCP Console route extension {key} is not JSON-encoded")
                result.append((match.group("extension"), child))
            result.extend(_route_extension_values(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_route_extension_values(child))
    return result


def discover_modules(route_map_bytes: bytes) -> list[dict[str, str]]:
    """Discover public Console modules from the official XSSI-protected routemap only."""

    if not isinstance(route_map_bytes, bytes) or not route_map_bytes.startswith(XSSI_PREFIX):
        raise ValueError("GCP Console routemap response is missing the expected XSSI prefix")
    payload = route_map_bytes.removeprefix(XSSI_PREFIX)
    if payload.startswith(XSSI_PREFIX):
        raise ValueError("GCP Console routemap response has a duplicated XSSI prefix")
    try:
        route_map = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("GCP Console routemap response is not JSON") from exc
    if not isinstance(route_map, (dict, list)):
        raise ValueError("GCP Console routemap response has an unexpected JSON root")

    discovered: list[dict[str, str]] = []
    extensions: set[str] = set()
    module_names: set[str] = set()
    identifiers: set[str] = set()
    for extension, encoded_value in _route_extension_values(route_map):
        try:
            value = json.loads(encoded_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"GCP Console route extension {extension} is not valid JSON") from exc
        urls = [
            url
            for string in _strings(value)
            for url in URL_PATTERN.findall(string)
            if _is_console_javascript_path(url)
        ]
        if len(urls) != 1:
            raise ValueError(f"GCP Console route extension {extension} must contain exactly one module URL")
        url = _canonical_module_url(urls[0])
        module = _module_from_url(url)
        identifier = _stable_id(extension)
        if extension in extensions or module in module_names or identifier in identifiers:
            raise ValueError("GCP Console routemap has duplicate extension, module, or stable id candidates")
        extensions.add(extension)
        module_names.add(module)
        identifiers.add(identifier)
        discovered.append({"id": identifier, "extension": extension, "module": module, "url": url})
    if not discovered:
        raise ValueError("GCP Console routemap has no route feature extension modules")
    return sorted(discovered, key=lambda entry: (entry["id"], entry["module"], entry["url"]))


def pin_modules(
    discovered_modules: Sequence[Mapping[str, object]], fetch_bytes: Callable[[str], bytes]
) -> dict[str, object]:
    """Digest-pin discovered public module bytes without evaluating JavaScript."""

    modules = _read_discovered_modules(discovered_modules)
    pinned_modules: list[dict[str, str]] = []
    for module in modules:
        payload = fetch_bytes(module.url)
        if not isinstance(payload, bytes):
            raise ValueError(f"GCP Console module fetch for {module.identifier} did not return bytes")
        pinned_modules.append(
            {
                "id": module.identifier,
                "extension": module.extension,
                "module": module.module,
                "url": module.url,
                "sha256": _sha256(payload),
            }
        )
    return {"format": ARCHIVE_FORMAT, "routeMapUrl": ROUTE_MAP_URL, "source": SOURCE, "modules": pinned_modules}


def _read_discovered_modules(discovered_modules: Sequence[Mapping[str, object]]) -> list[Module]:
    if not isinstance(discovered_modules, Sequence) or isinstance(discovered_modules, (str, bytes)) or not discovered_modules:
        raise ValueError("GCP Console discovered modules must be a non-empty sequence")
    result: list[Module] = []
    identifiers: set[str] = set()
    extensions: set[str] = set()
    module_names: set[str] = set()
    urls: set[str] = set()
    for raw in discovered_modules:
        if not isinstance(raw, Mapping):
            raise ValueError("GCP Console discovery has an invalid module")
        identifier, extension, module_name, url = (raw.get(field) for field in ("id", "extension", "module", "url"))
        if not all(isinstance(value, str) for value in (identifier, extension, module_name, url)):
            raise ValueError("GCP Console discovery has incomplete module fields")
        if identifier != _stable_id(extension) or not ICON_NAME_PATTERN.fullmatch(identifier):
            raise ValueError("GCP Console discovery has an unsafe stable id")
        if _module_from_url(url) != module_name:
            raise ValueError("GCP Console discovery module does not match its URL")
        if identifier in identifiers or extension in extensions or module_name in module_names or url in urls:
            raise ValueError("GCP Console discovery has duplicate extension, module, id, or URL")
        identifiers.add(identifier)
        extensions.add(extension)
        module_names.add(module_name)
        urls.add(url)
        result.append(Module(identifier, extension, module_name, url, ""))
    return sorted(result, key=lambda module: module.identifier)


def read_module_registry(registry: Mapping[str, object]) -> list[Module]:
    """Validate a supplied registry; fetching its modules is intentionally out of scope."""

    if (
        registry.get("format") != ARCHIVE_FORMAT
        or registry.get("source") != SOURCE
        or registry.get("routeMapUrl") != ROUTE_MAP_URL
    ):
        raise ValueError("GCP Console module registry is not a pinned routemap registry")
    modules = registry.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("GCP Console module registry must contain a non-empty modules list")
    result: list[Module] = []
    identifiers: set[str] = set()
    extensions: set[str] = set()
    module_names: set[str] = set()
    urls: set[str] = set()
    for raw in modules:
        if not isinstance(raw, Mapping):
            raise ValueError("GCP Console module registry has an invalid module")
        identifier = raw.get("id")
        extension = raw.get("extension")
        module_name = raw.get("module")
        url = raw.get("url")
        digest = raw.get("sha256")
        if not isinstance(identifier, str) or not isinstance(extension, str) or not isinstance(module_name, str):
            raise ValueError("GCP Console module registry has incomplete module identity")
        if identifier != _stable_id(extension) or not ICON_NAME_PATTERN.fullmatch(identifier):
            raise ValueError("GCP Console module registry has an unsafe module id")
        if not isinstance(url, str):
            raise ValueError("GCP Console module registry has no module URL")
        if _module_from_url(url) != module_name:
            raise ValueError("GCP Console module registry module does not match its URL")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError("GCP Console module registry has no valid module sha256")
        if identifier in identifiers or extension in extensions or module_name in module_names or url in urls:
            raise ValueError("GCP Console module registry has duplicate extension, module, id, or URL")
        identifiers.add(identifier)
        extensions.add(extension)
        module_names.add(module_name)
        urls.add(url)
        result.append(Module(identifier, extension, module_name, url, digest))
    return sorted(result, key=lambda module: module.identifier)


def _decode_js_escape(source: str, position: int) -> tuple[str, int]:
    if position >= len(source):
        raise ValueError("JavaScript literal ends with an escape")
    character = source[position]
    simple = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    if character in simple:
        return simple[character], position + 1
    if character == "x":
        digits = source[position + 1:position + 3]
        if len(digits) != 2 or not re.fullmatch(r"[0-9a-fA-F]{2}", digits):
            raise ValueError("JavaScript literal has an invalid hex escape")
        return chr(int(digits, 16)), position + 3
    if character == "u":
        digits = source[position + 1:position + 5]
        if len(digits) != 4 or not re.fullmatch(r"[0-9a-fA-F]{4}", digits):
            raise ValueError("JavaScript literal has an invalid unicode escape")
        return chr(int(digits, 16)), position + 5
    return character, position + 1


def _skip_javascript_regular_expression(source: str, index: int) -> int | None:
    """Return the position after a complete regex literal at ``index``."""

    previous = index - 1
    while previous >= 0 and source[previous].isspace():
        previous -= 1
    if previous >= 0 and source[previous] not in "([{,:;=!?&|+-*%^~<>":
        return None

    cursor = index + 1
    in_character_class = False
    while cursor < len(source):
        character = source[cursor]
        if character in "\r\n":
            return None
        if character == "\\":
            cursor += 2
            continue
        if character == "[":
            in_character_class = True
        elif character == "]":
            in_character_class = False
        elif character == "/" and not in_character_class:
            cursor += 1
            while cursor < len(source) and source[cursor].isalpha():
                cursor += 1
            return cursor
        cursor += 1
    return None


def _javascript_literals(source: str) -> list[tuple[str, bool]]:
    """Return decoded string literals and whether each was an interpolated template."""

    literals: list[tuple[str, bool]] = []
    index = 0
    while index < len(source):
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            index = len(source) if newline == -1 else newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end == -1:
                raise ValueError("JavaScript module has an unterminated block comment")
            index = end + 2
            continue
        if source[index] == "/":
            regex_end = _skip_javascript_regular_expression(source, index)
            if regex_end is not None:
                index = regex_end
                continue
        quote = source[index]
        if quote not in "'\"`":
            index += 1
            continue
        index += 1
        characters: list[str] = []
        interpolated = False
        while index < len(source):
            character = source[index]
            if character == quote:
                index += 1
                literals.append(("".join(characters), interpolated))
                break
            if quote == "`" and character == "$" and index + 1 < len(source) and source[index + 1] == "{":
                interpolated = True
            if character == "\\":
                decoded, index = _decode_js_escape(source, index + 1)
                characters.append(decoded)
                continue
            characters.append(character)
            index += 1
        else:
            raise ValueError("JavaScript module has an unterminated string literal")
    return literals


def _icon_entry_segment(data_icon_name: str | None, template_index: int) -> str:
    """Return a bounded, collision-safe filesystem segment for one template."""

    if data_icon_name is not None and not isinstance(data_icon_name, str):
        raise ValueError("GCP Console SVG data-icon-name is not a string")
    if not isinstance(template_index, int) or isinstance(template_index, bool) or template_index < 0:
        raise ValueError("GCP Console SVG template index is invalid")
    identity = b"\x00" if data_icon_name is None else b"\x01" + data_icon_name.encode("utf-8")
    return f"template-{_sha256(identity)}-{template_index}"


def _validate_svg_template(
    value: str, module: Module, template_index: int = 0
) -> ExtractedIcon:
    if "${" in value:
        raise ValueError(f"GCP Console module {module.identifier} has an interpolated SVG template")
    try:
        root = ET.fromstring(value)
    except ET.ParseError as exc:
        raise ValueError(f"GCP Console module {module.identifier} has malformed SVG template") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValueError(f"GCP Console module {module.identifier} template is not SVG")
    return ExtractedIcon(
        data_icon_name=root.get("data-icon-name"),
        svg=value.encode("utf-8"),
        module=module,
        template_index=template_index,
    )


def svg_has_renderable_content(svg_text: str) -> bool:
    """Return whether browser sanitization leaves a visibly drawable SVG element.

    This deliberately models only unambiguous blankness: active/external
    elements are removed by the browser sanitizer, definitions do not render on
    their own, and fully hidden or unpainted primitives cannot produce a card
    preview. It is not a geometry renderer.
    """

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValueError("GCP Console SVG is malformed") from exc
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        raise ValueError("GCP Console SVG is not an SVG root")

    def style_values(element: ET.Element) -> dict[str, str]:
        values = {
            key.rsplit("}", 1)[-1].lower(): value.strip()
            for key, value in element.attrib.items()
        }
        for declaration in values.get("style", "").split(";"):
            key, separator, value = declaration.partition(":")
            if separator:
                values[key.strip().lower()] = value.strip()
        return values

    def hidden_or_transparent(values: dict[str, str]) -> bool:
        if values.get("display", "").lower() == "none" or values.get("visibility", "").lower() in {"hidden", "collapse"}:
            return True
        try:
            if "opacity" in values and float(values["opacity"]) <= 0:
                return True
        except ValueError:
            pass
        return False

    def has_paint(values: dict[str, str]) -> bool:
        fill = values.get("fill", "black").replace(" ", "").lower()
        stroke = values.get("stroke", "none").replace(" ", "").lower()
        transparent = {"none", "transparent", "rgba(0,0,0,0)"}
        try:
            fill_visible = fill not in transparent and float(values.get("fill-opacity", "1")) > 0
        except ValueError:
            fill_visible = fill not in transparent
        try:
            stroke_visible = stroke not in transparent and float(values.get("stroke-opacity", "1")) > 0
        except ValueError:
            stroke_visible = stroke not in transparent
        return fill_visible or stroke_visible

    elements_by_id = {
        element.get("id"): element
        for element in root.iter()
        if isinstance(element.get("id"), str)
    }

    def visit(
        element: ET.Element,
        inherited: dict[str, str],
        in_definition: bool,
        referenced_ids: frozenset[str] = frozenset(),
    ) -> bool:
        name = element.tag.rsplit("}", 1)[-1].lower()
        values = {**inherited, **style_values(element)}
        is_definition = in_definition or name in NON_RENDERING_SVG_CONTAINERS
        if name == "use":
            reference = values.get("href") or values.get("xlink:href")
            if isinstance(reference, str) and LOCAL_FRAGMENT_REFERENCE_PATTERN.fullmatch(reference):
                reference_id = reference[1:]
                target = elements_by_id.get(reference_id)
                if target is not None and reference_id not in referenced_ids:
                    return visit(target, values, False, referenced_ids | {reference_id})
        if name in DRAWABLE_SVG_ELEMENTS and not is_definition:
            if not hidden_or_transparent(values) and has_paint(values):
                if name != "path" or values.get("d", "").strip():
                    return True
        return any(visit(child, values, is_definition, referenced_ids) for child in element)

    return visit(root, {}, False)


def extract_literal_svg_templates(module: Module, javascript: bytes) -> list[ExtractedIcon]:
    """Extract complete literal ``<svg data-icon-name=...>`` templates without evaluation."""

    try:
        source = javascript.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"GCP Console module {module.identifier} is not UTF-8 JavaScript") from exc
    if _sha256(javascript) != module.sha256:
        raise ValueError(f"GCP Console module {module.identifier} does not match its registry digest")

    icons: list[ExtractedIcon] = []
    template_index = 0
    for literal, interpolated in _javascript_literals(source):
        candidate = literal.strip()
        if not candidate.startswith("<svg"):
            continue
        if interpolated:
            raise ValueError(f"GCP Console module {module.identifier} has an interpolated SVG template")
        icons.append(_validate_svg_template(candidate, module, template_index))
        template_index += 1
    return icons


def _lock_for_modules(modules: list[Module]) -> dict[str, object]:
    entries = [
        {
            "extension": module.extension,
            "id": module.identifier,
            "module": module.module,
            "sha256": module.sha256,
            "url": module.url,
        }
        for module in modules
    ]
    content_digest = _sha256(_canonical_json(entries))
    return {
        "contentSha256": content_digest,
        "format": ARCHIVE_FORMAT,
        "modules": entries,
        "routeMapUrl": ROUTE_MAP_URL,
        "source": SOURCE,
    }


def build_source_tree(registry: Mapping[str, object], module_fixtures: Mapping[str, bytes]) -> dict[str, bytes]:
    """Build a deterministic source tree from digest-pinned modules.

    Fixtures are keyed by the registry module id.  Callers performing a future
    network fetch must verify bytes through this function, not execute modules.
    """

    modules = read_module_registry(registry)
    expected_ids = {module.identifier for module in modules}
    if set(module_fixtures) != expected_ids:
        raise ValueError("GCP Console module fixtures must exactly match the module registry")
    icons: list[ExtractedIcon] = []
    for module in modules:
        payload = module_fixtures[module.identifier]
        if not isinstance(payload, bytes):
            raise ValueError(f"GCP Console module fixture {module.identifier} is not bytes")
        icons.extend(extract_literal_svg_templates(module, payload))

    paths: set[str] = set()
    icon_entries: list[dict[str, str]] = []
    files: dict[str, bytes] = {NOTICE_NAME: REFERENTIAL_FAIR_USE_NOTICE_BYTES}
    for icon in sorted(icons, key=lambda candidate: (candidate.module.identifier, candidate.template_index)):
        entry_name = _icon_entry_segment(icon.data_icon_name, icon.template_index)
        path = f"{ICON_PREFIX}{icon.module.identifier}/{entry_name}.svg"
        _safe_member_name(path)
        if path in paths:
            raise ValueError(f"GCP Console modules have duplicate icon entry: {path}")
        paths.add(path)
        files[path] = icon.svg
        icon_entries.append(
            {
                "extension": icon.module.extension,
                "module": icon.module.module,
                "moduleId": icon.module.identifier,
                "dataIconName": icon.data_icon_name,
                "name": entry_name,
                "path": path,
                "sha256": _sha256(icon.svg),
                "templateIndex": icon.template_index,
            }
        )

    lock = _lock_for_modules(modules)
    lock_bytes = _canonical_json(lock)
    manifest = {
        "format": ARCHIVE_FORMAT,
        "iconCount": len(icon_entries),
        "icons": icon_entries,
        "notice": {"path": NOTICE_NAME, "sha256": _sha256(REFERENTIAL_FAIR_USE_NOTICE_BYTES)},
        "sourceLock": {"path": LOCK_NAME, "sha256": _sha256(lock_bytes)},
        "source": SOURCE,
    }
    files[LOCK_NAME] = lock_bytes
    files[MANIFEST_NAME] = _canonical_json(manifest)
    _validate_source_files(files)
    return files


def write_source_tree(root: Path, files: Mapping[str, bytes]) -> dict[str, object]:
    """Materialize a previously validated source tree into an empty directory."""

    manifest = _validate_source_files(files)
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"GCP Console source tree destination is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for name in sorted(files):
        destination = root.joinpath(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(files[name])
    return manifest


def _read_source_tree(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise ValueError(f"GCP Console source tree is not a directory: {root}")
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"GCP Console source tree contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"GCP Console source tree contains a non-file: {path}")
        name = path.relative_to(root).as_posix()
        _safe_member_name(name)
        files[name] = path.read_bytes()
    return files


def validate_source_tree(root: Path) -> dict[str, object]:
    """Validate source-tree layout, icon bytes, manifest, lock, and exact notice."""

    return _validate_source_files(_read_source_tree(root))


def _deterministic_zip(files: Mapping[str, bytes]) -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            _safe_member_name(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def _validate_source_files(files: Mapping[str, bytes]) -> dict[str, object]:
    names = sorted(files)
    if files.get(NOTICE_NAME) != REFERENTIAL_FAIR_USE_NOTICE_BYTES:
        raise ValueError("GCP Console source tree has a missing or altered referential fair-use notice")
    if any(not isinstance(data, bytes) for data in files.values()):
        raise ValueError("GCP Console source tree contains non-byte content")
    if any(not name.endswith(".svg") and name not in {NOTICE_NAME, MANIFEST_NAME, LOCK_NAME} for name in names):
        raise ValueError("GCP Console source tree contains a non-SVG asset")
    try:
        manifest = json.loads(files[MANIFEST_NAME])
        lock = json.loads(files[LOCK_NAME])
    except (KeyError, json.JSONDecodeError) as exc:
        raise ValueError("GCP Console source tree has invalid manifest or source lock") from exc
    if (
        not isinstance(manifest, dict)
        or not isinstance(lock, dict)
        or manifest.get("format") != ARCHIVE_FORMAT
        or lock.get("format") != ARCHIVE_FORMAT
        or files[MANIFEST_NAME] != _canonical_json(manifest)
        or files[LOCK_NAME] != _canonical_json(lock)
    ):
        raise ValueError("GCP Console source tree has an unexpected manifest or source lock")
    modules = lock.get("modules")
    if not isinstance(modules, list) or lock.get("contentSha256") != _sha256(_canonical_json(modules)):
        raise ValueError("GCP Console source tree source lock integrity check failed")
    locked_modules = read_module_registry(
        {
            "format": lock.get("format"),
            "modules": modules,
            "routeMapUrl": lock.get("routeMapUrl"),
            "source": lock.get("source"),
        }
    )
    if lock.get("source") != SOURCE or lock.get("routeMapUrl") != ROUTE_MAP_URL:
        raise ValueError("GCP Console source tree source lock has an unexpected source")
    locked_modules_by_id = {module.identifier: module for module in locked_modules}
    icons = manifest.get("icons")
    notice = manifest.get("notice")
    source_lock = manifest.get("sourceLock")
    if (
        not isinstance(icons, list)
        or manifest.get("iconCount") != len(icons)
        or manifest.get("source") != SOURCE
        or not isinstance(notice, dict)
        or notice.get("path") != NOTICE_NAME
        or notice.get("sha256") != _sha256(REFERENTIAL_FAIR_USE_NOTICE_BYTES)
        or not isinstance(source_lock, dict)
        or source_lock.get("path") != LOCK_NAME
        or source_lock.get("sha256") != _sha256(files[LOCK_NAME])
    ):
        raise ValueError("GCP Console source tree manifest icon count is invalid")
    expected_icon_paths: set[str] = set()
    expected_template_indices: dict[str, set[int]] = {}
    for entry in icons:
        if not isinstance(entry, dict) or set(entry) != {
            "dataIconName", "extension", "module", "moduleId", "name", "path", "sha256", "templateIndex"
        }:
            raise ValueError("GCP Console source tree manifest has an invalid icon")
        path = entry.get("path")
        data_icon_name = entry.get("dataIconName")
        template_index = entry.get("templateIndex")
        entry_name = entry.get("name")
        if (
            data_icon_name is not None and not isinstance(data_icon_name, str)
        ) or not isinstance(entry_name, str):
            raise ValueError("GCP Console source tree manifest has an invalid icon")
        try:
            expected_entry_name = _icon_entry_segment(data_icon_name, template_index)
        except ValueError as exc:
            raise ValueError("GCP Console source tree manifest has an invalid icon") from exc
        if entry_name != expected_entry_name:
            raise ValueError("GCP Console source tree manifest has an invalid icon entry name")
        if not isinstance(path, str) or not path.startswith(ICON_PREFIX) or not path.endswith(".svg") or path in expected_icon_paths:
            raise ValueError("GCP Console source tree manifest has unsafe or duplicate icon paths")
        path_parts = PurePosixPath(path).parts
        if (
            len(path_parts) != 3
            or path_parts[0] != "icons"
            or path_parts[2][:-4] != entry_name
            or path_parts[1] != entry.get("moduleId")
            or entry.get("moduleId") not in locked_modules_by_id
        ):
            raise ValueError("GCP Console source tree manifest has an icon outside the source lock")
        module_indices = expected_template_indices.setdefault(entry["moduleId"], set())
        if template_index in module_indices:
            raise ValueError("GCP Console source tree manifest has duplicate template indexes")
        module_indices.add(template_index)
        locked_module = locked_modules_by_id[entry["moduleId"]]
        if entry.get("extension") != locked_module.extension or entry.get("module") != locked_module.module:
            raise ValueError("GCP Console source tree manifest has an icon outside the source lock")
        expected_icon_paths.add(path)
        data = files.get(path)
        if data is None or entry.get("sha256") != _sha256(data):
            raise ValueError("GCP Console source tree icon does not match its manifest digest")
        parsed_icon = _validate_svg_template(data.decode("utf-8"), locked_module, template_index)
        if parsed_icon.data_icon_name != data_icon_name:
            raise ValueError("GCP Console source tree SVG data-icon-name does not match its manifest")
    actual_icon_paths = {name for name in names if name.startswith(ICON_PREFIX)}
    if actual_icon_paths != expected_icon_paths or set(names) != {NOTICE_NAME, MANIFEST_NAME, LOCK_NAME, *expected_icon_paths}:
        raise ValueError("GCP Console source tree members do not match its manifest")
    return manifest


def build_archive_from_source_tree(root: Path) -> bytes:
    """Package a validated source tree for same-origin Pages deployment only."""

    files = _read_source_tree(root)
    _validate_source_files(files)
    return _deterministic_zip(files)


def validate_archive(archive_bytes: bytes) -> dict[str, object]:
    """Validate an archive staged from the deterministic source tree."""

    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            infos = archive.infolist()
            names: list[str] = []
            files: dict[str, bytes] = {}
            for info in infos:
                path = _safe_member_name(info.filename)
                if info.is_dir() or info.filename in names:
                    raise ValueError(f"GCP Console archive has invalid member: {info.filename}")
                if info.filename != path.as_posix() or info.date_time != (1980, 1, 1, 0, 0, 0) or info.external_attr != (0o100644 << 16):
                    raise ValueError(f"GCP Console archive member is not deterministic: {info.filename}")
                names.append(info.filename)
                files[info.filename] = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise ValueError("GCP Console archive is not a ZIP file") from exc
    if names != sorted(names):
        raise ValueError("GCP Console archive members are not ordered")
    return _validate_source_files(files)


def build_archive(registry: Mapping[str, object], module_fixtures: Mapping[str, bytes]) -> bytes:
    """Build an in-memory deploy archive from modules; never persist it in the repo."""

    return _deterministic_zip(build_source_tree(registry, module_fixtures))


def build_source_tree_from_route_map(
    route_map_bytes: bytes,
    fetch_bytes: Callable[[str], bytes],
    *,
    workers: int = 8,
) -> dict[str, bytes]:
    """Discover, pin, and build one source generation using an injected fetcher.

    Module responses are kept only in memory, so callers do not need to retain
    Console JavaScript on disk.
    """

    if not isinstance(workers, int) or workers < 1 or workers > 32:
        raise ValueError("GCP Console worker count must be between 1 and 32")
    discovered = discover_modules(route_map_bytes)
    payloads_by_url: dict[str, bytes] = {}

    def fetch_module(url: str) -> bytes:
        payload = fetch_bytes(url)
        if not isinstance(payload, bytes):
            raise ValueError(f"GCP Console module fetch for {url} did not return bytes")
        return payload

    with ThreadPoolExecutor(max_workers=min(workers, len(discovered))) as executor:
        fetched = list(executor.map(lambda entry: (entry["url"], fetch_module(entry["url"])), discovered))
    payloads_by_url.update(fetched)
    registry = pin_modules(discovered, payloads_by_url.__getitem__)
    return build_source_tree(
        registry,
        {entry["id"]: payloads_by_url[entry["url"]] for entry in discovered},
    )


def fetch_public_bytes(url: str) -> bytes:
    """Fetch a fixed public source without cookies, credentials, or execution."""

    request = Request(url, headers={"User-Agent": "fluent-icon-browser-source-archive/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--source-tree", help="Empty candidate source-tree directory to populate")
    operation.add_argument("--package-source-tree", help="Validated source-tree directory to package for Pages")
    parser.add_argument("--archive", help="Deploy-time static GCP Console ZIP path")
    parser.add_argument("--workers", type=int, default=8, help="Bounded concurrent module fetches (1-32)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.source_tree:
        source_tree = build_source_tree_from_route_map(
            fetch_public_bytes(ROUTE_MAP_URL), fetch_public_bytes, workers=args.workers
        )
        write_source_tree(Path(args.source_tree), source_tree)
        return
    if not args.archive:
        raise ValueError("--archive is required with --package-source-tree")
    archive_path = Path(args.archive)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(build_archive_from_source_tree(Path(args.package_source_tree)))


if __name__ == "__main__":
    main()
