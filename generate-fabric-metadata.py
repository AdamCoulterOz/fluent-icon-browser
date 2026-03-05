#!/usr/bin/env python3
"""Generate and maintain metadata for Fabric MDL2 icons."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

FABRIC_ICON_FILE_PATTERN = re.compile(r"^(?P<name>.+)Icon\.tsx$")
DISPLAY_NAME_PATTERN = re.compile(r"displayName:\s*'([^']+)'")

STYLE_TOKENS = {
    "solid",
    "fill",
    "filled",
    "mirrored",
    "logo",
    "light",
    "medium",
    "color",
    "outline",
    "off",
    "on",
}

SIZE_TOKENS = {"8", "10", "12", "16", "20", "24", "28", "32", "48", "64"}

TOKEN_METAPHORS: Dict[str, List[str]] = {
    "accept": ["confirm", "approve", "done", "success", "yes", "tick", "checkmark"],
    "access": ["database", "microsoft access", "office", "data"],
    "accessibility": ["inclusive", "a11y", "assistive", "compliance"],
    "account": ["user", "profile", "identity", "person", "login"],
    "activity": ["timeline", "history", "events", "log"],
    "add": ["create", "new", "insert", "plus"],
    "address": ["location", "place", "contact", "postal"],
    "alert": ["warning", "attention", "notice", "caution"],
    "analytics": ["insights", "reporting", "metrics", "analysis"],
    "app": ["application", "software", "program"],
    "archive": ["store", "retain", "history", "old"],
    "arrow": ["direction", "navigate", "move"],
    "attach": ["attachment", "paperclip", "link", "file"],
    "audio": ["sound", "music", "voice"],
    "auto": ["automatic", "automation"],
    "back": ["previous", "return", "navigate"],
    "bar": ["chart", "graph", "analytics"],
    "book": ["documentation", "reference", "read"],
    "bookmark": ["save", "favorite", "mark"],
    "box": ["package", "container", "inventory"],
    "briefcase": ["work", "business", "office", "professional"],
    "browser": ["web", "internet", "window"],
    "bug": ["issue", "defect", "error", "debug"],
    "build": ["compile", "pipeline", "ci", "deploy"],
    "calendar": ["date", "schedule", "event", "planning"],
    "call": ["phone", "telephony", "contact"],
    "camera": ["photo", "video", "capture"],
    "cancel": ["close", "stop", "dismiss", "abort"],
    "card": ["id", "badge", "profile", "payment"],
    "caret": ["dropdown", "expand", "collapse"],
    "chat": ["message", "conversation", "communication"],
    "check": ["verify", "complete", "validated"],
    "checkbox": ["selection", "form", "choice"],
    "chevron": ["expand", "collapse", "navigate"],
    "circle": ["status", "indicator", "shape"],
    "city": ["office", "building", "location", "urban"],
    "clipboard": ["notes", "tasks", "copy", "record"],
    "clock": ["time", "schedule", "history"],
    "close": ["dismiss", "cancel", "exit", "x"],
    "cloud": ["online", "sync", "storage"],
    "code": ["development", "programming", "source"],
    "collapse": ["hide", "minimize", "fold"],
    "column": ["table", "grid", "layout"],
    "comment": ["feedback", "discussion", "annotation"],
    "contact": ["person", "directory", "address book"],
    "copy": ["duplicate", "clone"],
    "cut": ["trim", "remove", "scissors"],
    "dashboard": ["overview", "metrics", "home"],
    "data": ["database", "records", "information"],
    "database": ["storage", "data", "sql", "records"],
    "delete": ["remove", "trash", "erase"],
    "delivery": ["shipping", "logistics", "fulfillment"],
    "device": ["hardware", "computer", "mobile"],
    "document": ["file", "page", "paper"],
    "download": ["import", "save", "receive"],
    "edit": ["modify", "update", "pencil"],
    "email": ["mail", "inbox", "message"],
    "error": ["problem", "issue", "failure"],
    "event": ["calendar", "activity", "schedule"],
    "favorite": ["star", "like", "bookmark"],
    "file": ["document", "asset", "item"],
    "filter": ["refine", "search", "narrow"],
    "flag": ["marker", "important", "country"],
    "folder": ["directory", "files", "organize"],
    "forward": ["next", "send", "advance"],
    "gift": ["present", "reward"],
    "globe": ["world", "global", "internet"],
    "group": ["team", "collection", "multiple"],
    "help": ["support", "question", "info"],
    "history": ["recent", "log", "timeline"],
    "home": ["house", "main", "start"],
    "image": ["photo", "picture", "media"],
    "important": ["priority", "alert", "critical"],
    "inbox": ["mail", "messages", "incoming"],
    "info": ["information", "details", "about"],
    "key": ["security", "access", "credential"],
    "link": ["url", "connect", "chain"],
    "list": ["items", "tasks", "menu"],
    "location": ["place", "map", "address", "pin"],
    "lock": ["secure", "private", "protection"],
    "mail": ["email", "message", "inbox"],
    "manage": ["admin", "settings", "control"],
    "map": ["location", "address", "navigation"],
    "meeting": ["calendar", "schedule", "call"],
    "menu": ["navigation", "options"],
    "message": ["chat", "communication", "mail"],
    "microphone": ["audio", "voice", "record"],
    "more": ["additional", "extra", "overflow"],
    "move": ["drag", "relocate", "transfer"],
    "music": ["audio", "sound", "media"],
    "network": ["connectivity", "infrastructure", "internet"],
    "new": ["create", "add", "fresh"],
    "note": ["memo", "annotation", "text"],
    "office": ["work", "business", "company"],
    "open": ["launch", "expand", "view"],
    "package": ["bundle", "inventory", "delivery"],
    "page": ["document", "content", "paper"],
    "pause": ["stop", "hold", "media"],
    "people": ["users", "contacts", "team"],
    "person": ["user", "profile", "account"],
    "phone": ["call", "mobile", "contact"],
    "photo": ["image", "picture", "camera"],
    "pin": ["location", "bookmark", "fixed", "map pin"],
    "play": ["start", "media", "video"],
    "plus": ["add", "create", "new"],
    "print": ["paper", "output", "document"],
    "profile": ["user", "account", "identity"],
    "refresh": ["reload", "sync", "update"],
    "remove": ["delete", "subtract", "minus"],
    "reply": ["respond", "email", "message"],
    "report": ["document", "analytics", "summary"],
    "save": ["store", "persist", "download"],
    "search": ["find", "lookup", "query"],
    "security": ["protection", "safety", "auth"],
    "send": ["share", "submit", "forward"],
    "settings": ["configure", "preferences", "options"],
    "share": ["send", "collaborate", "link"],
    "shield": ["security", "protection", "safe"],
    "shop": ["store", "commerce", "purchase"],
    "sign": ["signature", "auth", "agreement"],
    "sort": ["order", "arrange", "filter"],
    "star": ["favorite", "rating", "highlight"],
    "status": ["state", "indicator", "health"],
    "sync": ["synchronize", "refresh", "update"],
    "table": ["grid", "rows", "columns", "data"],
    "tag": ["label", "category", "classification"],
    "task": ["todo", "work", "checklist"],
    "team": ["group", "collaboration", "people"],
    "time": ["clock", "schedule", "duration"],
    "timeline": ["history", "progress", "sequence"],
    "tool": ["utility", "settings", "configuration"],
    "train": ["transport", "vehicle", "travel"],
    "trash": ["delete", "remove", "bin"],
    "unlock": ["access", "open", "security"],
    "upload": ["send", "share", "submit"],
    "user": ["person", "account", "profile"],
    "video": ["media", "camera", "call"],
    "view": ["display", "visibility", "browse"],
    "warning": ["alert", "caution", "attention"],
    "wifi": ["network", "wireless", "internet"],
    "window": ["app", "screen", "browser"],
    "work": ["business", "task", "office"],
    "wrench": ["tool", "settings", "repair"],
    "xbox": ["gaming", "console", "controller"],
    "zoom": ["magnify", "scale", "view"],
}

PHRASE_METAPHORS: Dict[Tuple[str, ...], List[str]] = {
    ("access", "logo"): ["microsoft", "office", "database", "access"],
    ("account", "activity"): ["crm", "engagement", "record", "notes"],
    ("account", "browser"): ["web profile", "user portal", "account view"],
    ("account", "management"): ["identity admin", "user admin", "account settings"],
    ("map", "pin"): ["address", "location", "place", "marker", "gps"],
    ("city", "next"): ["office", "building", "business location"],
    ("city", "next", "2"): ["office", "building", "business location"],
    ("fixed", "asset", "management"): ["asset register", "inventory", "property"],
    ("tag", "group"): ["category", "taxonomy", "classification"],
}

EXACT_OVERRIDES: Dict[str, Dict[str, object]] = {
    "accept": {
        "description": "Checkmark or tick mark.",
        "metaphors": ["confirm", "approve", "done", "success", "tick", "checkmark"],
    },
    "accept_medium": {
        "description": "Bold or thicker checkmark / tick mark.",
        "metaphors": ["confirm", "approve", "done", "success", "tick", "checkmark"],
    },
    "access_logo": {
        "description": "Microsoft Office Access application icon.",
        "metaphors": ["microsoft", "office", "access", "database", "app logo"],
    },
    "accessibilty_checker": {
        "description": "Document with folded corner and an accessibility-check overlay (dashed circle with directional arrows).",
        "metaphors": ["accessibility", "a11y", "compliance", "audit", "document check"],
    },
    "account_activity": {
        "description": "Clipboard with a pencil, indicating account activity or notes.",
        "metaphors": ["account", "activity", "notes", "crm", "history"],
    },
    "account_browser": {
        "description": "Browser window containing a user/profile icon.",
        "metaphors": ["account", "profile", "web", "portal", "user view"],
    },
    "account_management": {
        "description": "Person/profile with a credential badge, representing account management.",
        "metaphors": ["account", "management", "identity", "admin", "user settings"],
    },
    "accounts": {
        "description": "At symbol (@).",
        "metaphors": ["account", "email", "mention", "at sign", "username"],
    },
    "city_next": {
        "description": "Stylized city skyline / office buildings.",
        "metaphors": ["office", "building", "city", "business location", "headquarters"],
    },
    "city_next2": {
        "description": "Stylized city skyline / office buildings (alternate variant).",
        "metaphors": ["office", "building", "city", "business location", "headquarters"],
    },
    "map_pin": {
        "description": "Map pin / location marker.",
        "metaphors": ["address", "location", "place", "marker", "gps", "map pin"],
    },
}


def camel_to_snake(name: str) -> str:
    with_word_boundaries = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    with_internal_caps = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", with_word_boundaries)
    return with_internal_caps.replace("-", "_").lower()


def humanize_camel(name: str) -> str:
    with_word_boundaries = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    with_internal_caps = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", with_word_boundaries)
    return with_internal_caps.strip()


def split_words(name: str) -> List[str]:
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", normalized)
    normalized = re.sub(r"(\d+)", r" \1 ", normalized)
    return [part for part in normalized.split() if part]


def extract_display_name(tsx_text: str, fallback: str) -> str:
    match = DISPLAY_NAME_PATTERN.search(tsx_text)
    if not match:
        return fallback

    display_name = match.group(1)
    if display_name.endswith("Icon"):
        return display_name[:-4]
    return display_name


def canonical_token(token: str) -> str:
    return token.strip().lower()


def build_description(display_name: str, words: List[str]) -> str:
    lowered = [canonical_token(word) for word in words]
    filtered = [
        word
        for word in lowered
        if word not in STYLE_TOKENS and word not in SIZE_TOKENS and not word.isdigit()
    ]

    if not filtered:
        filtered = lowered

    base_phrase = " ".join(filtered)
    if not base_phrase:
        base_phrase = display_name.lower()

    article = "an" if base_phrase[0] in "aeiou" else "a"

    if "logo" in lowered:
        description = f"Icon for {base_phrase} logo."
    elif "check" in lowered or "checkmark" in lowered:
        description = f"Icon depicting {article} {base_phrase} symbol."
    else:
        description = f"Icon depicting {base_phrase}."

    variants: List[str] = []
    if "solid" in lowered or "fill" in lowered or "filled" in lowered:
        variants.append("solid/filled style")
    if "mirrored" in lowered:
        variants.append("mirrored (RTL) variant")

    size_values = [word for word in lowered if word in SIZE_TOKENS]
    if size_values:
        variants.append(f"{size_values[0]}px variant")

    if variants:
        description = f"{description} {'; '.join(variants)}."

    return description[0].upper() + description[1:]


def build_metaphors(icon_id: str, words: List[str], description: str) -> List[str]:
    metaphors: List[str] = []

    lower_words = [canonical_token(word) for word in words]

    for token in lower_words:
        if token in STYLE_TOKENS or token in SIZE_TOKENS or token.isdigit():
            continue
        metaphors.append(token)
        metaphors.extend(TOKEN_METAPHORS.get(token, []))

    phrase_key = tuple(lower_words)
    metaphors.extend(PHRASE_METAPHORS.get(phrase_key, []))

    compact_words = [
        token
        for token in lower_words
        if token not in STYLE_TOKENS and token not in SIZE_TOKENS and not token.isdigit()
    ]
    if compact_words:
        metaphors.append(" ".join(compact_words))

    if "icon" not in metaphors:
        metaphors.append("icon")

    deduped: List[str] = []
    seen = set()
    for item in metaphors:
        normalized = item.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped[:24]


def load_existing_metadata(path: Path) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    entries = payload.get("icons") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}

    by_id: Dict[str, Dict[str, object]] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        icon_id = item.get("id")
        if not isinstance(icon_id, str) or not icon_id:
            continue
        by_id[icon_id] = item

    return by_id


def iter_fabric_icons(components_dir: Path) -> Iterable[Tuple[str, str]]:
    for component_file in sorted(components_dir.glob("*.tsx")):
        match = FABRIC_ICON_FILE_PATTERN.match(component_file.name)
        if not match:
            continue

        icon_name = match.group("name")
        tsx_text = component_file.read_text(encoding="utf-8")
        display_name = extract_display_name(tsx_text, icon_name)
        yield icon_name, display_name


def normalize_metaphors(raw: object) -> List[str]:
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
    elif isinstance(raw, str):
        values = [raw.strip()] if raw.strip() else []
    else:
        values = []

    deduped: List[str] = []
    seen = set()
    for value in values:
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(lowered)

    return deduped


def generate_metadata(components_dir: Path, output_file: Path) -> int:
    existing = load_existing_metadata(output_file)
    icons = []

    for icon_name, display_name in iter_fabric_icons(components_dir):
        icon_id = camel_to_snake(icon_name)
        words = split_words(display_name)

        if icon_id in EXACT_OVERRIDES:
            override = EXACT_OVERRIDES[icon_id]
            description = str(override.get("description", "")).strip()
            metaphors = normalize_metaphors(override.get("metaphors", []))
        else:
            existing_entry = existing.get(icon_id, {})
            existing_description = str(existing_entry.get("description", "")).strip()
            existing_metaphors = normalize_metaphors(existing_entry.get("metaphors", []))

            description = existing_description or build_description(display_name, words)
            metaphors = existing_metaphors or build_metaphors(icon_id, words, description)

        icons.append(
            {
                "id": icon_id,
                "name": humanize_camel(display_name),
                "description": description,
                "metaphors": metaphors,
            }
        )

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "microsoft/fluentui/packages/react-icons-mdl2",
        "count": len(icons),
        "icons": icons,
    }

    output_file.write_text(
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )

    print(f"Generated metadata for {len(icons)} Fabric icons -> {output_file}")
    return len(icons)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate metadata for Fabric MDL2 icons")
    parser.add_argument(
        "--components-dir",
        default=".tmp/fluent-fabric/packages/react-icons-mdl2/src/components",
        help="Path to Fabric MDL2 component directory",
    )
    parser.add_argument(
        "--output",
        default="fabric-mdl2-metadata.json",
        help="Output metadata JSON path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generate_metadata(Path(args.components_dir), Path(args.output))


if __name__ == "__main__":
    main()
