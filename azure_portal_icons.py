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
BASE_IMAGES_CSS_MODULE = "_generated/Less/MsPortalImpl/Base/Base.Images.css"
MANIFEST_GROUPS = (
    "assetTypes",
    "assetTypesBrowse",
    "assetTypesMenu",
    "browseMenus",
    "portalServices",
)
RESOURCE_TYPE_PATTERN = re.compile(
    r"^(?P<provider>[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z][A-Za-z0-9-]*)+)/"
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*$"
)
# Match provider namespaces, never individual resource types or icon identifiers.
# A trailing `*` intentionally matches a provider-name family such as
# `Microsoft.StorageMover` without depending on resource display text.
PROVIDER_CATEGORY_MATCHERS: tuple[tuple[str, str], ...] = (
    ("microsoft.compute", "Compute"),
    ("microsoft.classiccompute", "Compute"),
    ("microsoft.batch", "Compute"),
    ("microsoft.desktopvirtualization", "Compute"),
    ("microsoft.devcenter", "Compute"),
    ("microsoft.labservices", "Compute"),
    ("microsoft.hybridcompute", "Compute"),
    ("microsoft.azurestackhci", "Compute"),
    ("microsoft.connectedvmwarevsphere", "Compute"),
    ("microsoft.scvmm", "Compute"),
    ("microsoft.virtualmachineimages", "Compute"),
    ("microsoft.computeschedule", "Compute"),
    ("microsoft.standbypool", "Compute"),
    ("microsoft.baremetalinfrastructure", "Compute"),
    ("microsoft.azurelargeinstance", "Compute"),
    ("microsoft.avs", "Compute"),
    ("microsoft.containerservice", "Containers"),
    ("microsoft.containerinstance", "Containers"),
    ("microsoft.containerregistry", "Containers"),
    ("microsoft.containerstorage", "Storage"),
    ("microsoft.kubernetes", "Containers"),
    ("microsoft.kubernetesconfiguration", "Containers"),
    ("microsoft.redhatopenshift", "Containers"),
    ("microsoft.servicefabric", "Containers"),
    ("microsoft.app", "Containers"),
    ("microsoft.network", "Networking"),
    ("microsoft.managednetworkfabric", "Networking"),
    ("microsoft.networkcloud", "Networking"),
    ("microsoft.hybridnetwork", "Networking"),
    ("microsoft.hybridconnectivity", "Networking"),
    ("microsoft.networkfunction", "Networking"),
    ("microsoft.peering", "Networking"),
    ("microsoft.cdn", "Networking"),
    ("microsoft.relay", "Networking"),
    ("microsoft.servicenetworking", "Networking"),
    ("microsoft.devtunnels", "Networking"),
    ("microsoft.maps", "Networking"),
    ("microsoft.storage*", "Storage"),
    ("microsoft.classicstorage", "Storage"),
    ("microsoft.netapp", "Storage"),
    ("microsoft.databox", "Storage"),
    ("microsoft.databoxedge", "Storage"),
    ("microsoft.fileshares", "Storage"),
    ("microsoft.elasticsan", "Storage"),
    ("microsoft.connectedcache", "Storage"),
    ("microsoft.sql", "Databases"),
    ("microsoft.dbfor", "Databases"),
    ("microsoft.dbfor*", "Databases"),
    ("microsoft.documentdb", "Databases"),
    ("microsoft.cache", "Databases"),
    ("microsoft.cosmic", "Databases"),
    ("microsoft.kusto", "Analytics"),
    ("microsoft.horizondb", "Databases"),
    ("microsoft.oriondb", "Databases"),
    ("microsoft.hanaonazure", "Databases"),
    ("microsoft.azurearcdata", "Databases"),
    ("microsoft.databasewatcher", "Databases"),
    ("microsoft.cognitiveservices", "AI + Machine Learning"),
    ("microsoft.bing", "AI + Machine Learning"),
    ("microsoft.machinelearningservices", "AI + Machine Learning"),
    ("microsoft.search", "AI + Machine Learning"),
    ("microsoft.botservice", "AI + Machine Learning"),
    ("microsoft.healthdataaiservices", "AI + Machine Learning"),
    ("microsoft.copilot", "AI + Machine Learning"),
    ("microsoft.videoindexer", "AI + Machine Learning"),
    ("microsoft.synapse", "Analytics"),
    ("microsoft.datafactory", "Analytics"),
    ("microsoft.datalake*", "Analytics"),
    ("microsoft.datashare", "Analytics"),
    ("microsoft.databricks", "Analytics"),
    ("microsoft.analysisservices", "Analytics"),
    ("microsoft.streamanalytics", "Analytics"),
    ("microsoft.powerbidedicated", "Analytics"),
    ("microsoft.fabric", "Analytics"),
    ("microsoft.purview", "Analytics"),
    ("microsoft.hdinsight", "Analytics"),
    ("microsoft.eventgrid", "Integration"),
    ("microsoft.eventhub", "Integration"),
    ("microsoft.servicebus", "Integration"),
    ("microsoft.logic", "Integration"),
    ("microsoft.apimanagement", "Integration"),
    ("microsoft.signalrservice", "Integration"),
    ("microsoft.communication", "Integration"),
    ("microsoft.notificationhubs", "Integration"),
    ("microsoft.fluidrelay", "Integration"),
    ("microsoft.durabletask", "Integration"),
    ("microsoft.integrationspaces", "Integration"),
    ("microsoft.azuredatatransfer", "Integration"),
    ("microsoft.appconfiguration", "Integration"),
    ("microsoft.confluent", "Integration"),
    ("microsoft.apicenter", "Integration"),
    ("microsoft.keyvault", "Security"),
    ("microsoft.security*", "Security"),
    ("microsoft.authorization", "Security"),
    ("microsoft.attestation", "Security"),
    ("microsoft.confidentialledger", "Security"),
    ("microsoft.codesigning", "Security"),
    ("microsoft.easm", "Security"),
    ("microsoft.aadiam", "Identity"),
    ("microsoft.aad", "Identity"),
    ("microsoft.managedidentity", "Identity"),
    ("microsoft.azureactivedirectory", "Identity"),
    ("microsoft.insights", "Monitoring"),
    ("microsoft.operationalinsights", "Monitoring"),
    ("microsoft.monitor", "Monitoring"),
    ("microsoft.alertsmanagement", "Monitoring"),
    ("microsoft.operationsmanagement", "Monitoring"),
    ("microsoft.scom", "Monitoring"),
    ("microsoft.loadtestservice", "Monitoring"),
    ("microsoft.cloudhealth", "Monitoring"),
    ("microsoft.chaos", "Monitoring"),
    ("microsoft.datadog", "Monitoring"),
    ("microsoft.dashboard", "Monitoring"),
    ("microsoft.elastic", "Monitoring"),
    ("microsoft.devices", "IoT"),
    ("microsoft.deviceregistry", "IoT"),
    ("microsoft.iot*", "IoT"),
    ("microsoft.digitaltwins", "IoT"),
    ("microsoft.deviceupdate", "IoT"),
    ("microsoft.azuresphere", "IoT"),
    ("microsoft.resources", "Management"),
    ("microsoft.management", "Management"),
    ("microsoft.changesafety", "Management"),
    ("microsoft.dataprotection", "Management"),
    ("microsoft.machineconfiguration", "Management"),
    ("microsoft.recoveryservices", "Management"),
    ("microsoft.providerhub", "Management"),
    ("microsoft.deploymentmanager", "Management"),
    ("microsoft.extendedlocation", "Management"),
    ("microsoft.features", "Management"),
    ("microsoft.billing*", "Management"),
    ("microsoft.capacity", "Management"),
    ("microsoft.solutions", "Management"),
    ("microsoft.relationships", "Management"),
    ("microsoft.resourcegraph", "Management"),
    ("microsoft.portal", "Management"),
    ("microsoft.portal*", "Management"),
    ("microsoft.managedservices", "Management"),
    ("microsoft.azurefleet", "Management"),
    ("microsoft.maintenance", "Management"),
    ("microsoft.migrate", "Management"),
    ("microsoft.datamigration", "Databases"),
    ("microsoft.all", "Management"),
    ("microsoft.web", "Web"),
    ("microsoft.webiq", "Web"),
    ("microsoft.appplatform", "Web"),
    ("microsoft.devops", "DevOps"),
    ("microsoft.cloudtest", "DevOps"),
    ("microsoft.devopsinfrastructure", "DevOps"),
    ("microsoft.devhub", "DevOps"),
    ("microsoft.azureplaywrightservice", "DevOps"),
)
RESOURCE_CATEGORY_DOMAINS = frozenset(
    category for _provider, category in PROVIDER_CATEGORY_MATCHERS
)
RESOURCE_CATEGORY_VALUES = RESOURCE_CATEGORY_DOMAINS | {"Other Providers"}
SURFACE_CATEGORIES = {
    "core": "General UI",
    "assetTypes": "Portal Assets",
    "assetTypesBrowse": "Browse & Discover",
    "assetTypesMenu": "Portal Commands",
    "browseMenus": "Browse & Discover",
    "portalServices": "Portal Services",
}
CORE_NAME_CATEGORY_OVERRIDES = {
    "active_directory": "Identity",
    "advisor": "Management",
    "automation": "Management",
    "billing_hub": "Management",
    "cost_alerts": "Management",
    "cost_analysis": "Management",
    "cost_budgets": "Management",
    "resource_group": "Management",
    "resource_role": "Management",
    "api_management": "Integration",
    "biz_talk": "Integration",
    "event_grid": "Integration",
    "event_hub": "Integration",
    "service_bus": "Integration",
    "workflow": "Integration",
    "app_insights": "Monitoring",
    "insights": "Monitoring",
    "load_test": "Monitoring",
    "log_analytics": "Monitoring",
    "log_diagnostics": "Monitoring",
    "log_streaming": "Monitoring",
    "monitoring": "Monitoring",
    "operational_insights": "Monitoring",
    "workbooks": "Monitoring",
    "availability_set": "Compute",
    "cloud_service": "Compute",
    "functions": "Compute",
    "remote_app": "Compute",
    "virtual_machine": "Compute",
    "backup": "Storage",
    "blob_block": "Storage",
    "blob_page": "Storage",
    "storage": "Storage",
    "storage_azure_files": "Storage",
    "storage_container": "Storage",
    "storage_queue": "Storage",
    "stor_simple": "Storage",
    "cache": "Databases",
    "clear_db_database": "Databases",
    "database": "Databases",
    "production_ready_db": "Databases",
    "redis": "Databases",
    "sql_database": "Databases",
    "sql_database_server": "Databases",
    "cdn": "Networking",
    "express_route": "Networking",
    "ip_address": "Networking",
    "load_balancer": "Networking",
    "network_interface_card": "Networking",
    "traffic_manager": "Networking",
    "traffic_manager_disabled": "Networking",
    "traffic_manager_enabled": "Networking",
    "virtual_network": "Networking",
    "security_center": "Security",
    "stream_analytics": "Analytics",
    "server_farm": "Web",
    "web_environment": "Web",
    "web_hosting": "Web",
    "web_hosting_plan": "Web",
    "web_jobs": "Web",
    "web_slots": "Web",
    "web_test": "Web",
    "website": "Web",
    "website_power": "Web",
    "website_staging": "Web",
    "cloud_shell": "DevOps",
    "team_project": "DevOps",
    "tfsvc_repository": "DevOps",
}
NESTED_ASSET_TYPE_SURFACES = {
    "assetTypesBrowse": "assetTypesBrowse",
    "assetTypesMenu": "assetTypesMenu",
}
SURFACE_CATEGORY_PRIORITY = (
    "Portal Commands",
    "Browse & Discover",
    "Portal Services",
    "Portal Assets",
)
NON_SEMANTIC_AZURE_TAGS = {"azure", "core", "polychromatic", "portal"}
AMD_DEFINE_PATTERN = re.compile(
    r"define\(\s*(?P<module>\"(?:\\.|[^\"])*\")\s*,\s*\[\s*\"require\"\s*,\s*\"exports\"\s*\]"
)
AMD_NAMED_MODULE_PATTERN = re.compile(
    r'define\(\s*(?P<module>"(?:\\.|[^\"])*")\s*,'
)
SVG_ASSIGNMENT_PATTERN = re.compile(
    r"(?:\bdata|\.data)\s*=\s*(?P<svg>\"(?:\\.|[^\"])*\")"
)
BASE_IMAGES_RULE_PATTERN = re.compile(
    r"(?P<selectors>[^{}]+)\{(?P<declarations>[^{}]*)\}"
)
BASE_IMAGES_CLASS_PATTERN = re.compile(
    r"\s*\.(?P<name>msportalfx-svg-c\d{2})\s*"
)
BASE_IMAGES_FILL_PATTERN = re.compile(
    r"(?:^|;)\s*fill\s*:\s*(?P<value>[^;]+?)"
    r"\s*(?:!important)?\s*(?=;|$)",
    re.IGNORECASE,
)
BASE_IMAGES_VAR_FALLBACK_PATTERN = re.compile(
    r"var\(\s*--fxs-svg-(?P<class_name>c\d{2})-fill\s*,\s*"
    r"(?P<value>#[0-9a-f]{3}|#[0-9a-f]{6})\s*\)",
    re.IGNORECASE,
)
BASE_IMAGES_RETURN_CSS_PREFIX_PATTERN = re.compile(
    r"\breturn\s*\{\s*css\s*:\s*",
)
BASE_IMAGES_RETURN_OBJECT_SUFFIX_PATTERN = re.compile(
    r"\s*(?:,\s*moduleId\s*:\s*[A-Za-z_$][\w$]*\.id)?\s*}\s*;?\s*}\s*\)?\s*;?\s*$"
)
HEX_PAINT_PATTERN = re.compile(r"#[0-9a-f]{3}|#[0-9a-f]{6}", re.IGNORECASE)
CAMEL_WORD_PATTERN = re.compile(r"([A-Z]+)([A-Z][a-z])|([a-z0-9])([A-Z])")
STYLE_DECLARATION_PATTERN = re.compile(r"(?P<property>[-A-Za-z]+)\s*:\s*(?P<value>[^;]+)")
RGB_COLOR_PATTERN = re.compile(
    r"rgba?\(\s*(?P<red>\d+(?:\.\d+)?)\s*[ ,/]\s*"
    r"(?P<green>\d+(?:\.\d+)?)\s*[ ,/]\s*"
    r"(?P<blue>\d+(?:\.\d+)?)(?:\s*[/,]\s*[^)]*)?\s*\)",
    re.IGNORECASE,
)
HSL_COLOR_PATTERN = re.compile(
    r"hsla?\(\s*[^, ]+(?:\s*,\s*|\s+)(?P<saturation>\d+(?:\.\d+)?)%",
    re.IGNORECASE,
)
PAINT_PROPERTIES = {"fill", "stroke", "color", "stop-color", "flood-color", "lighting-color"}
NON_VISIBLE_ELEMENT_NAMES = {
    "defs",
    "clipPath",
    "mask",
    "marker",
    "linearGradient",
    "radialGradient",
    "pattern",
    "filter",
    "symbol",
    # Runtime sanitization removes stylesheet and external-instance content.
    "style",
    "use",
}
VECTOR_ELEMENT_NAMES = {
    "circle",
    "ellipse",
    "line",
    "path",
    "polygon",
    "polyline",
    "rect",
    "text",
    "tspan",
}
DEFINITION_ELEMENT_NAMES = {
    "clipPath",
    "defs",
    "filter",
    "linearGradient",
    "marker",
    "mask",
    "pattern",
    "radialGradient",
    "symbol",
}
REJECTED_SVG_ELEMENT_NAMES = {"foreignobject", "image"}


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
    fallback_source: Optional[PortalSource] = None,
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
        should_fallback = exc.code in {403, 404}
        exc.close()
        if not should_fallback:
            raise
        if fallback_source is not None:
            return _validated_portal_source(fallback_source)
        if fallback_require_config_url is None:
            raise
        parsed_fallback = urlparse(fallback_require_config_url)
        if (
            parsed_fallback.scheme != "https"
            or parsed_fallback.netloc != "portal.azure.com"
            or parsed_fallback.username is not None
            or parsed_fallback.password is not None
            or parsed_fallback.query
            or parsed_fallback.fragment
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


def _local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def _style_paints(style_text: str) -> list[str]:
    return [
        match.group("value").strip()
        for match in STYLE_DECLARATION_PATTERN.finditer(style_text)
        if match.group("property").lower() in PAINT_PROPERTIES
    ]


def _style_property(style_text: str, property_name: str) -> Optional[str]:
    selected: Optional[str] = None
    selected_important = False
    for match in STYLE_DECLARATION_PATTERN.finditer(style_text):
        if match.group("property").lower() == property_name:
            value = match.group("value").strip().lower()
            important = bool(re.search(r"\s*!important\s*$", value, flags=re.IGNORECASE))
            if selected is None or important or not selected_important:
                selected = value
                selected_important = important
    return selected


def _normalize_style_keyword(value: Optional[str]) -> str:
    return re.sub(r"\s*!important\s*$", "", value or "", flags=re.IGNORECASE).strip().lower()


def has_vector_svg_content(svg_text: str) -> bool:
    """Return whether an SVG has renderable vector artwork safe for indexing."""

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise AzurePortalSchemaError("AMD module has invalid SVG text") from exc
    if _local_name(root.tag) != "svg":
        raise AzurePortalSchemaError("AMD module payload is not an SVG root")

    elements_by_id = {
        element_id: element
        for element in root.iter()
        if (element_id := element.get("id"))
    }
    if any(
        _local_name(element.tag).lower() in REJECTED_SVG_ELEMENT_NAMES
        for element in root.iter()
    ):
        return False

    def is_hidden(element: ET.Element) -> bool:
        style_text = element.get("style", "")
        return (
            _normalize_style_keyword(
                element.get("display") or _style_property(style_text, "display")
            )
            == "none"
            or _normalize_style_keyword(
                element.get("visibility") or _style_property(style_text, "visibility")
            )
            == "hidden"
        )

    def renders_vector(
        element: ET.Element,
        resolving_reference: bool,
        visited_ids: set[str],
    ) -> bool:
        if is_hidden(element):
            return False
        element_name = _local_name(element.tag).lower()
        if element_name == "use":
            href = next(
                (
                    value.strip()
                    for name, value in element.attrib.items()
                    if _local_name(name) == "href" and value.strip().startswith("#")
                ),
                None,
            )
            if href is None:
                return False
            target_id = href[1:]
            if not target_id or target_id in visited_ids:
                return False
            target = elements_by_id.get(target_id)
            return target is not None and renders_vector(
                target, True, visited_ids | {target_id}
            )
        if element_name in DEFINITION_ELEMENT_NAMES and not resolving_reference:
            return False
        if element_name in VECTOR_ELEMENT_NAMES:
            return True
        return any(
            renders_vector(child, resolving_reference, visited_ids)
            for child in element
        )

    return renders_vector(root, False, set())


def _is_chromatic_paint(value: str) -> bool:
    paint = value.strip().lower()
    if paint in {"none", "currentcolor", "inherit", "initial", "unset", "context-fill", "context-stroke"}:
        return False
    if paint.startswith("url("):
        return True
    if paint.startswith("#"):
        hex_value = paint[1:]
        try:
            if len(hex_value) in {3, 4}:
                red, green, blue = (
                    int(component * 2, 16) for component in hex_value[:3]
                )
            elif len(hex_value) in {6, 8}:
                red, green, blue = (
                    int(hex_value[index : index + 2], 16) for index in (0, 2, 4)
                )
            else:
                return True
        except ValueError:
            return True
        return not (red == green == blue)
    rgb_match = RGB_COLOR_PATTERN.fullmatch(paint)
    if rgb_match:
        red, green, blue = (float(rgb_match.group(component)) for component in ("red", "green", "blue"))
        return not (red == green == blue)
    hsl_match = HSL_COLOR_PATTERN.match(paint)
    if hsl_match:
        return float(hsl_match.group("saturation")) != 0
    return paint not in {"black", "white", "gray", "grey", "transparent"}


def preserve_source_colors(svg_text: str) -> bool:
    """Return whether visible SVG artwork needs its authored paint values preserved."""

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise AzurePortalSchemaError("AMD module has invalid SVG text") from exc

    paints: set[str] = set()

    def visit(element: ET.Element, hidden: bool) -> bool:
        element_name = _local_name(element.tag)
        style_text = element.get("style", "")
        style_paints = _style_paints(style_text)
        display = _normalize_style_keyword(
            element.get("display") or _style_property(style_text, "display")
        )
        visibility = _normalize_style_keyword(
            element.get("visibility") or _style_property(style_text, "visibility")
        )
        hidden = (
            hidden
            or element_name in NON_VISIBLE_ELEMENT_NAMES
            or display == "none"
            or visibility == "hidden"
        )
        if not hidden:
            element_paints = [
                value
                for property_name, value in element.attrib.items()
                if _local_name(property_name).lower() in PAINT_PROPERTIES
            ] + style_paints
            for paint in element_paints:
                normalized = paint.strip().lower()
                if normalized.startswith("url(") or _is_chromatic_paint(normalized):
                    return True
                if normalized not in {"", "none", "currentcolor", "inherit", "initial", "unset", "context-fill", "context-stroke"}:
                    paints.add(normalized)
            if len(paints) > 1:
                return True
        return any(visit(child, hidden) for child in element)

    return visit(root, False)


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
        svg_text = _decode_js_string(svg_match.group("svg"))
        if has_vector_svg_content(svg_text):
            modules.append((module_name, canonical_svg_text(svg_text)))
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
    tags = [
        tag
        for tag in (_snake_case(part).replace("_", " ") for part in category)
        if tag.casefold() not in NON_SEMANTIC_AZURE_TAGS
    ]
    return _snake_case(raw_name), style, tags


def _source_descriptor(
    url: str, module_name: str, canonical_svg: str, palette: Optional[dict[str, str]] = None
) -> dict:
    descriptor = {
        "url": url,
        "format": "portal-amd-svg-module",
        "selector": module_name,
        "sha256": hashlib.sha256(canonical_svg.encode("utf-8")).hexdigest(),
    }
    paint_map = materialize_class_paints(canonical_svg, palette or {})
    if paint_map:
        descriptor["paintMap"] = paint_map
    return descriptor


def _normalize_hex_paint(value: str) -> Optional[str]:
    if not HEX_PAINT_PATTERN.fullmatch(value):
        return None
    hex_value = value[1:]
    if len(hex_value) == 3:
        hex_value = "".join(component * 2 for component in hex_value)
    return f"#{hex_value.upper()}"


def parse_base_images_palette(css_text: str) -> dict[str, str]:
    """Extract literal msportalfx-svg-cNN paints from the locked Portal palette."""

    palette: dict[str, str] = {}
    for rule in BASE_IMAGES_RULE_PATTERN.finditer(css_text):
        class_names = []
        for selector in rule.group("selectors").split(","):
            selector_match = BASE_IMAGES_CLASS_PATTERN.fullmatch(selector)
            if selector_match:
                class_names.append(selector_match.group("name"))
        if not class_names:
            continue
        fills = list(BASE_IMAGES_FILL_PATTERN.finditer(rule.group("declarations")))
        if not fills:
            continue
        fill_value = fills[-1].group("value")
        var_match = BASE_IMAGES_VAR_FALLBACK_PATTERN.fullmatch(fill_value)
        if var_match:
            # The locked CSS fallback is a literal authored paint, not a runtime variable.
            fill_value = var_match.group("value")
        paint = _normalize_hex_paint(fill_value)
        if paint is None:
            continue
        for class_name in class_names:
            if var_match and (
                var_match.group("class_name").lower()
                != class_name.removeprefix("msportalfx-svg-").lower()
            ):
                continue
            palette[class_name] = paint
    return palette


def _base_images_palette_from_bundle(bundle_text: str) -> dict[str, str]:
    """Read one static Base.Images return-object CSS module without evaluating it."""

    css_values: list[str] = []
    for match in AMD_NAMED_MODULE_PATTERN.finditer(bundle_text):
        if _decode_js_string(match.group("module")) != BASE_IMAGES_CSS_MODULE:
            continue
        call_end = _matching_parenthesis(bundle_text, bundle_text.find("(", match.start()))
        call_text = bundle_text[match.start() : call_end + 1]
        return_matches = list(BASE_IMAGES_RETURN_CSS_PREFIX_PATTERN.finditer(call_text))
        if len(return_matches) != 1:
            raise AzurePortalSchemaError("Base.Images CSS module has no static return-object css")
        try:
            css_text, consumed = json.JSONDecoder().raw_decode(
                call_text[return_matches[0].end() :]
            )
        except json.JSONDecodeError as exc:
            raise AzurePortalSchemaError(
                "Base.Images CSS module has a non-literal css value"
            ) from exc
        if not isinstance(css_text, str) or not BASE_IMAGES_RETURN_OBJECT_SUFFIX_PATTERN.fullmatch(
            call_text[return_matches[0].end() + consumed :]
        ):
            raise AzurePortalSchemaError("Base.Images CSS module has no static return-object css")
        css_values.append(css_text)

    if not css_values:
        return {}
    if len(css_values) != 1:
        raise AzurePortalSchemaError("Base.Images CSS module appears more than once")
    palette = parse_base_images_palette(css_values[0])
    if not palette:
        raise AzurePortalSchemaError("Base.Images CSS module has no literal palette paints")
    return palette


def materialize_class_paints(svg_text: str, palette: dict[str, str]) -> dict[str, str]:
    """Return only safe palette entries used by visible SVG class tokens."""

    if not palette:
        return {}
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise AzurePortalSchemaError("AMD module has invalid SVG text") from exc

    used: set[str] = set()

    def visit(element: ET.Element, hidden: bool) -> None:
        element_name = _local_name(element.tag)
        style_text = element.get("style", "")
        display = _normalize_style_keyword(
            element.get("display") or _style_property(style_text, "display")
        )
        visibility = _normalize_style_keyword(
            element.get("visibility") or _style_property(style_text, "visibility")
        )
        hidden = (
            hidden
            or element_name in NON_VISIBLE_ELEMENT_NAMES
            or display == "none"
            or visibility == "hidden"
        )
        if not hidden:
            used.update(
                class_name
                for class_name in element.get("class", "").split()
                if class_name in palette
            )
        for child in element:
            visit(child, hidden)

    visit(root, False)
    return {class_name: paint for class_name, paint in palette.items() if class_name in used}


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


def parse_resource_provider_namespace(resource_type_name: str) -> str:
    """Return the ARM provider namespace from a typed resource type name."""

    match = RESOURCE_TYPE_PATTERN.fullmatch(resource_type_name)
    if match is None:
        raise AzurePortalSchemaError(
            f"Unsupported ARM resource type name: {resource_type_name!r}"
        )
    return match.group("provider")


def provider_category(provider_namespace: str) -> str:
    """Map an ARM provider namespace to its deterministic browse-domain category."""

    normalized = provider_namespace.lower()
    for prefix, domain in PROVIDER_CATEGORY_MATCHERS:
        if prefix.endswith("*"):
            if normalized.startswith(prefix[:-1]):
                return _resource_category(domain)
        elif normalized == prefix or normalized.startswith(f"{prefix}."):
            return _resource_category(domain)
    return "Other Providers"


def _resource_category(domain: str) -> str:
    if domain not in RESOURCE_CATEGORY_DOMAINS:
        raise AzurePortalSchemaError(f"Unsupported Azure resource category: {domain}")
    return domain


def core_category(core_name: str) -> str:
    """Map an exact canonical core-module name to its reviewed Azure category."""

    domain = CORE_NAME_CATEGORY_OVERRIDES.get(core_name)
    if domain is None:
        return SURFACE_CATEGORIES["core"]
    return _resource_category(domain)


def _record_category_provenance(
    surface: str,
    provider_namespace: Optional[str] = None,
    core_name: Optional[str] = None,
) -> dict:
    if surface not in SURFACE_CATEGORIES:
        raise AzurePortalSchemaError(f"Unsupported Azure icon source surface: {surface}")
    if surface == "core":
        if provider_namespace is not None:
            raise AzurePortalSchemaError("Core Azure icons cannot have provider provenance")
        if core_name is None:
            return {"surface": surface, "category": SURFACE_CATEGORIES[surface]}
        return {
            "surface": surface,
            "coreName": core_name,
            "category": core_category(core_name),
        }
    if core_name is not None:
        raise AzurePortalSchemaError("Manifest Azure icons cannot have core provenance")
    if surface == "assetTypes" and provider_namespace is not None:
        return {
            "surface": surface,
            "providerNamespace": provider_namespace,
            "category": provider_category(provider_namespace),
        }
    return {"surface": surface, "category": SURFACE_CATEGORIES[surface]}


def _category_from_provenance(provenance: list[dict]) -> str:
    if not provenance:
        raise AzurePortalSchemaError("Azure icon record has no category provenance")
    categories: set[str] = set()
    for item in provenance:
        surface = item.get("surface")
        if not isinstance(surface, str) or surface not in SURFACE_CATEGORIES:
            raise AzurePortalSchemaError("Azure icon record has unsupported source surface")
        provider_namespace = item.get("providerNamespace")
        core_name = item.get("coreName")
        if surface == "core":
            if provider_namespace is not None:
                raise AzurePortalSchemaError("Azure icon record has invalid provider provenance")
            if core_name is None:
                expected_category = SURFACE_CATEGORIES[surface]
            elif isinstance(core_name, str):
                expected_category = core_category(core_name)
            else:
                raise AzurePortalSchemaError("Azure icon record has invalid core provenance")
        elif core_name is not None:
            raise AzurePortalSchemaError("Azure icon record has invalid core provenance")
        elif provider_namespace is not None:
            if surface != "assetTypes" or not isinstance(provider_namespace, str):
                raise AzurePortalSchemaError("Azure icon record has invalid provider provenance")
            expected_category = provider_category(provider_namespace)
        else:
            expected_category = SURFACE_CATEGORIES[surface]
        if item.get("category") != expected_category:
            raise AzurePortalSchemaError("Azure icon record has invalid category provenance")
        categories.add(expected_category)
    for category in SURFACE_CATEGORY_PRIORITY:
        if category in categories:
            return category
    resource_categories = sorted(
        category for category in categories if category in RESOURCE_CATEGORY_VALUES
    )
    if len(resource_categories) == 1:
        return resource_categories[0]
    if len(resource_categories) > 1:
        return "Shared"
    if "General UI" in categories:
        return "General UI"
    raise AzurePortalSchemaError("Azure icon record has unsupported source category")


def _manifest_record(
    source: ManifestSource,
    pointer: list[str],
    extension_name: str,
    context_name: str,
    entry: dict,
    svg_text: str,
    palette: Optional[dict[str, str]] = None,
    provider_namespace: Optional[str] = None,
    surface: Optional[str] = None,
) -> dict:
    canonical_svg = canonical_svg_text(svg_text)
    label = _manifest_entry_label(entry)
    name_parts = ["azure", extension_name, source.category, context_name, label]
    name = "_".join(
        part for part in (_snake_case(part) for part in name_parts) if part
    )
    # Source routing and copy remain searchable, but only authored keywords belong
    # in the visible metaphor-chip surface.
    tags: set[str] = set()
    search_terms = {
        *_text_values(extension_name),
        *_text_values(context_name),
        *_text_values(label),
    }
    for field in ("keywords",):
        value = entry.get(field)
        if isinstance(value, list):
            for item in value:
                tags.update(_text_values(item))
        else:
            tags.update(_text_values(value))
    tags = {
        tag for tag in tags if tag.casefold() not in NON_SEMANTIC_AZURE_TAGS
    }
    for field in ("description", "toolTip", "tooltip", "ariaLabel"):
        value = entry.get(field)
        if isinstance(value, list):
            for item in value:
                search_terms.update(_text_values(item))
        else:
            search_terms.update(_text_values(value))
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
    paint_map = materialize_class_paints(canonical_svg, palette or {})
    if paint_map:
        descriptor["paintMap"] = paint_map
    return {
        "name": name,
        "displayName": label,
        "description": description,
        "style": "regular",
        "tags": sorted(tags),
        "searchTerms": sorted(search_terms),
        "descriptor": descriptor,
        "preserveSourceColors": preserve_source_colors(canonical_svg) or bool(paint_map),
        "categoryProvenance": _record_category_provenance(
            surface or source.category, provider_namespace
        ),
    }


def _manifest_icon_records(
    source: ManifestSource,
    manifest_payload: object,
    palette: Optional[dict[str, str]] = None,
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
        provider_namespace: Optional[str] = None,
        surface: Optional[str] = None,
    ) -> None:
        current_surface = surface or source.category
        if isinstance(value, dict):
            current_provider_namespace = provider_namespace
            if current_surface == "assetTypes" and "resourceType" in value:
                resource_type = value["resourceType"]
                if not isinstance(resource_type, dict):
                    raise AzurePortalSchemaError(
                        "Typed assetTypes entry has an invalid resourceType object"
                    )
                resource_type_name = _meaningful_text(
                    resource_type.get("resourceTypeName")
                )
                if resource_type_name is None:
                    raise AzurePortalSchemaError(
                        "Typed assetTypes entry has no resourceType.resourceTypeName"
                    )
                current_provider_namespace = parse_resource_provider_namespace(
                    resource_type_name
                )
            icon = value.get("icon")
            if isinstance(icon, dict) and isinstance(icon.get("data"), str):
                if has_vector_svg_content(icon["data"]):
                    records.append(
                        _manifest_record(
                            source,
                            pointer + ["icon", "data"],
                            extension_name,
                            context_name,
                            value,
                            icon["data"],
                            palette,
                            current_provider_namespace,
                            current_surface,
                        )
                    )
            for key, child in value.items():
                if key == "icon":
                    continue
                child_surface = current_surface
                if source.category == "assetTypes":
                    child_surface = NESTED_ASSET_TYPE_SURFACES.get(
                        key, current_surface
                    )
                visit(
                    child,
                    pointer + [key],
                    extension_name,
                    context_name,
                    current_provider_namespace,
                    child_surface,
                )
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
                visit(
                    child,
                    pointer + [str(index)],
                    extension_name,
                    child_context,
                    provider_namespace,
                    current_surface,
                )

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
        descriptor = record.get("descriptor")
        if not isinstance(descriptor, dict) or descriptor.get("format") not in {
            "portal-amd-svg-module",
            "portal-json-pointer-svg",
        }:
            raise AzurePortalSchemaError("Azure icon record has unsupported source format")
        provenance = record.get("categoryProvenance")
        if not isinstance(provenance, dict):
            raise AzurePortalSchemaError("Azure icon record has no category provenance")
        _category_from_provenance([provenance])
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
                "searchTerms": sorted(
                    {
                        term
                        for record in ordered
                        for term in record.get("searchTerms", [])
                    }
                ),
                "aliases": sorted(
                    {
                        record["name"]
                        for record in ordered[1:]
                        if record["name"] != primary["name"]
                    }
                ),
                "remoteSource": primary["descriptor"],
                "remoteSources": [record["descriptor"] for record in ordered],
                "preserveSourceColors": any(
                    record.get("preserveSourceColors", False) for record in ordered
                ),
                "categoryProvenance": [
                    record["categoryProvenance"] for record in ordered
                ],
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
                "searchTerms": set(),
                "aliases": set(),
                "variants": {},
                "categoryProvenance": [],
            }
            families[family_name] = family
        family["tags"].update(member["tags"])
        family["searchTerms"].update(member.get("searchTerms", []))
        family["aliases"].update(member["aliases"])
        family["categoryProvenance"].extend(member["categoryProvenance"])
        variant = {
            "defaultSize": 16,
            "remoteSource": member["remoteSource"],
            "sizes": {"16": {"remoteSource": member["remoteSource"]}},
        }
        if len(member["remoteSources"]) > 1:
            variant["remoteSources"] = member["remoteSources"]
        if member["preserveSourceColors"]:
            variant["preserveSourceColors"] = True
        family["variants"][member["style"]] = variant

    icons: list[dict] = []
    for name, family in sorted(families.items()):
        icon = {
            "name": name,
            "displayName": family["displayName"],
            "description": family["description"],
            "metaphors": sorted(family["tags"]),
            "category": _category_from_provenance(family["categoryProvenance"]),
            "variants": {
                style: family["variants"][style]
                for style in sorted(family["variants"], key=style_rank.__getitem__)
            },
        }
        if family["searchTerms"]:
            icon["searchTerms"] = sorted(family["searchTerms"])
        aliases = sorted(alias for alias in family["aliases"] if alias != name)
        if aliases:
            icon["aliases"] = aliases
        icons.append(icon)
    return icons, len(by_hash)


def _core_records(
    source: PortalSource,
    fetch_text: Callable[[str], str] = fetch_portal_text,
) -> tuple[list[dict], list[dict], dict[str, str]]:
    records: list[dict] = []
    source_digests: list[dict] = []
    bundles: list[tuple[str, str]] = []
    for bundle_url in source.bundle_urls:
        bundle_text = fetch_text(bundle_url)
        bundles.append((bundle_url, bundle_text))
        source_digests.append(
            {
                "url": bundle_url,
                "sha256": hashlib.sha256(bundle_text.encode("utf-8")).hexdigest(),
            }
        )
    palette: dict[str, str] = {}
    palette_found = False
    for _bundle_url, bundle_text in bundles:
        candidate = _base_images_palette_from_bundle(bundle_text)
        if candidate:
            if palette_found:
                raise AzurePortalSchemaError("Base.Images CSS palette appears in multiple bundles")
            palette = candidate
            palette_found = True
    if not palette_found:
        raise AzurePortalSchemaError("Portal bundles have no Base.Images CSS palette")
    for bundle_url, bundle_text in bundles:
        for module_name, canonical_svg in parse_amd_svg_modules(bundle_text):
            name, style, tags = _module_metadata(module_name)
            descriptor = _source_descriptor(bundle_url, module_name, canonical_svg, palette)
            records.append(
                {
                    "name": name,
                    "displayName": _display_name(name),
                    "description": f"Azure Portal core icon: {_display_name(name)}.",
                    "style": style,
                    "tags": tags,
                    "descriptor": descriptor,
                    "preserveSourceColors": preserve_source_colors(canonical_svg)
                    or bool(descriptor.get("paintMap")),
                    "categoryProvenance": _record_category_provenance(
                        "core", core_name=name
                    ),
                }
            )
    if not records:
        raise AzurePortalSchemaError("Portal bundles contained no named core SVG modules")
    return records, source_digests, palette


def build_azure_catalog(
    source: PortalSource,
    fetch_text: Callable[[str], str] = fetch_portal_text,
) -> AzureBuildResult:
    """Build core and extension-manifest entries without retaining SVG source text."""

    core_records, core_source_digests, palette = _core_records(source, fetch_text)
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
        manifest_records.extend(
            _manifest_icon_records(manifest_source, manifest_payload, palette)
        )

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


def _validated_portal_source(source: PortalSource) -> PortalSource:
    if not isinstance(source.portal_base_url, str) or source.portal_base_url != PORTAL_BASE_URL:
        raise AzurePortalSchemaError("Previous source lock has an invalid Portal base URL")
    if not isinstance(source.page_version, str) or not re.fullmatch(
        r"\d+(?:\.\d+)+", source.page_version
    ):
        raise AzurePortalSchemaError("Previous source lock has an invalid page version")
    if not isinstance(source.bootstrap_config_hash, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+", source.bootstrap_config_hash
    ):
        raise AzurePortalSchemaError("Previous source lock has an invalid bootstrap config hash")
    if not isinstance(source.require_config_hash, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+", source.require_config_hash
    ):
        raise AzurePortalSchemaError("Previous source lock has an invalid RequireConfig hash")

    def valid_url(url: str, path_pattern: str) -> bool:
        if not isinstance(url, str):
            return False
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.netloc == "portal.azure.com"
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and re.fullmatch(path_pattern, parsed.path) is not None
        )

    require_config_pattern = r"/Content/PortalRequireConfig/(?P<hash>[A-Za-z0-9_-]+)\.js"
    if not valid_url(source.require_config_url, require_config_pattern):
        raise AzurePortalSchemaError("Previous source lock has an invalid RequireConfig URL")
    require_config_match = re.fullmatch(
        require_config_pattern, urlparse(source.require_config_url).path
    )
    if require_config_match is None or require_config_match["hash"] != source.require_config_hash:
        raise AzurePortalSchemaError("Previous source lock RequireConfig URL/hash mismatch")

    if not isinstance(source.bundle_urls, tuple) or not source.bundle_urls:
        raise AzurePortalSchemaError("Previous source lock has invalid AMD bundle URLs")
    for bundle_url in source.bundle_urls:
        if not isinstance(bundle_url, str) or not valid_url(
            bundle_url, r"/Content/Dynamic/[A-Za-z0-9_-]+\.js"
        ):
            raise AzurePortalSchemaError("Previous source lock has an invalid AMD bundle URL")
    if len(source.bundle_urls) != len(set(source.bundle_urls)):
        raise AzurePortalSchemaError("Previous source lock has invalid AMD bundle URLs")

    expected_categories = list(MANIFEST_GROUPS)
    if not isinstance(source.manifest_sources, tuple) or not all(
        isinstance(manifest_source, ManifestSource)
        for manifest_source in source.manifest_sources
    ):
        raise AzurePortalSchemaError("Previous source lock has invalid extension manifest categories")
    actual_categories = [manifest_source.category for manifest_source in source.manifest_sources]
    if actual_categories != expected_categories:
        raise AzurePortalSchemaError("Previous source lock has invalid extension manifest categories")
    for manifest_source in source.manifest_sources:
        if not isinstance(manifest_source.url, str) or not valid_url(
            manifest_source.url, r"/Content/ExtensionManifest/[A-Za-z0-9_-]+\.json"
        ):
            raise AzurePortalSchemaError("Previous source lock has an invalid extension manifest URL")
    return source


def previous_portal_source(path: Optional[Path]) -> Optional[PortalSource]:
    """Load a complete, validated prior Portal source snapshot for a 403/404 handoff."""

    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest_sources_payload = payload["extensionManifestSources"]
        if not isinstance(manifest_sources_payload, list):
            raise TypeError("extensionManifestSources is not a list")
        source = PortalSource(
            portal_base_url=payload["portalBaseUrl"],
            page_version=payload["pageVersion"],
            bootstrap_config_hash=payload["bootstrapConfigHash"],
            require_config_hash=payload["requireConfigHash"],
            require_config_url=payload["requireConfigUrl"],
            bundle_urls=tuple(payload["amdBundleUrls"]),
            manifest_sources=tuple(
                ManifestSource(category=item["category"], url=item["url"])
                for item in manifest_sources_payload
            ),
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AzurePortalSchemaError(f"Invalid previous Azure source lock: {path}") from exc
    return _validated_portal_source(source)


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
    source = discover_portal_source(
        fetch_text=fetch_text,
        fallback_source=previous_portal_source(previous_source_lock_path),
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
