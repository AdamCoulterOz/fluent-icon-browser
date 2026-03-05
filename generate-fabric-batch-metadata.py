#!/usr/bin/env python3
"""Generate metadata drafts for Fabric icon review batches.

Descriptions are intentionally literal (what is visually depicted).
Metaphors remain semantic usage tags.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


TOKEN_TAGS: Dict[str, List[str]] = {
    "accept": ["confirm", "approve", "done", "success", "tick"],
    "access": ["database", "office", "microsoft access"],
    "accessibilty": ["accessibility", "a11y", "compliance", "audit"],
    "account": ["user", "profile", "identity", "login"],
    "action": ["tasks", "actions", "operations"],
    "activity": ["feed", "timeline", "history"],
    "add": ["create", "new", "plus", "insert"],
    "bookmark": ["save", "favorite", "mark"],
    "event": ["calendar", "schedule", "meeting"],
    "favorite": ["star", "like"],
    "friend": ["contact", "person"],
    "group": ["team", "people", "collection"],
    "home": ["house", "start"],
    "link": ["url", "connect"],
    "notes": ["memo", "annotation", "text"],
    "meeting": ["video call", "calendar"],
    "phone": ["call", "telephony"],
    "reaction": ["emoji", "feedback"],
    "shopping": ["cart", "commerce"],
    "work": ["business", "office", "job"],
    "air": ["travel", "flight"],
    "airplane": ["flight", "travel", "transport"],
    "alarm": ["time", "clock", "reminder"],
    "album": ["media", "photos"],
    "alert": ["warning", "caution", "important"],
    "align": ["layout", "formatting", "editor"],
    "apps": ["applications", "app launcher"],
    "currency": ["money", "finance"],
    "alt": ["accessibility", "images", "screen reader"],
    "amazon": ["aws", "cloud"],
    "analytics": ["insights", "reporting", "metrics", "data"],
    "anchor": ["pin", "stability"],
    "lock": ["secure", "security", "protected"],
    "android": ["mobile", "os"],
    "annotation": ["comment", "markup", "review"],
    "apache": ["open source", "java build"],
    "archive": ["storage", "history", "retain"],
    "area": ["chart", "graph", "data viz"],
    "arrange": ["layers", "z-order", "layout"],
    "arrivals": ["travel", "airport"],
    "arrow": ["direction", "navigate", "move"],
    "articles": ["news", "docs", "content"],
    "ascending": ["sort", "order"],
    "aspect": ["resize", "dimensions"],
    "assessment": ["evaluation", "review"],
    "asset": ["library", "repository", "resources"],
    "assign": ["delegate", "ownership", "task"],
    "asterisk": ["wildcard", "note", "required"],
    "attach": ["attachment", "file", "paperclip"],
    "australian": ["sports", "football"],
    "auto": ["automatic", "automation"],
    "deploy": ["release", "delivery"],
    "enhance": ["image", "photo", "improve"],
    "fit": ["resize", "layout"],
    "height": ["size", "dimensions"],
    "racing": ["sports", "cars"],
    "automate": ["workflow", "flow", "process"],
}


LITERAL_OVERRIDES: Dict[str, str] = {
    "accept": "Checkmark / tick mark.",
    "accept_medium": "Heavier checkmark / tick mark.",
    "access_logo": "Microsoft Access logo tile over a database cylinder.",
    "accessibilty_checker": "Page/document with folded corner and a dashed circular arrow overlay.",
    "account_activity": "Clipboard with a pencil.",
    "account_browser": "Browser window with a person/profile symbol inside.",
    "account_management": "Person silhouette with a small credential/briefcase badge.",
    "accounts": "At sign (@) inside a circle.",
    "action_center": "Speech/message bubble outline.",
    "activate_orders": "Document/checklist page with a checkmark.",
    "activity_feed": "Two stacked chat/message bubbles.",
    "add": "Plus sign.",
    "add_bookmark": "Bookmark ribbon with a plus sign.",
    "add_event": "Calendar page with a plus sign.",
    "add_favorite": "Star with a plus sign.",
    "add_favorite_fill": "Filled star shape.",
    "add_friend": "Person icon with a plus sign.",
    "add_group": "Group of people with a plus sign.",
    "add_home": "House outline with a plus sign.",
    "add_in": "App/window tile with a plus sign.",
    "add_link": "Chain link with a plus sign.",
    "add_notes": "Horizontal text lines with a plus sign.",
    "add_online_meeting": "Globe symbol with a plus sign.",
    "add_phone": "Phone receiver with a plus sign.",
    "add_reaction": "Smiley face with a plus sign.",
    "add_space_after": "Horizontal lines with a downward arrow indicating added spacing after.",
    "add_space_before": "Horizontal lines with a downward arrow indicating added spacing before.",
    "add_to": "Circle with a plus sign.",
    "add_to_shopping_list": "Checklist/list page with a plus sign.",
    "add_work": "Briefcase with a plus sign.",
    "air_tickets": "Air ticket/pass icon.",
    "airplane": "Airplane outline.",
    "airplane_solid": "Filled airplane silhouette.",
    "alarm_clock": "Alarm clock with bells.",
    "album": "Rectangular album/media card.",
    "album_remove": "Rectangular album/media card with remove mark.",
    "alert_settings": "Alert/clock symbol with a small settings gear.",
    "alert_solid": "Filled circle with exclamation mark.",
    "align_center": "Centered horizontal lines.",
    "align_horizontal_center": "Horizontal alignment guides with centered reference marker.",
    "align_horizontal_left": "Horizontal alignment guides with left reference marker.",
    "align_horizontal_right": "Horizontal alignment guides with right reference marker.",
    "align_justify": "Even-width horizontal text lines (justify).",
    "align_left": "Left-aligned horizontal text lines.",
    "align_right": "Right-aligned horizontal text lines.",
    "align_vertical_bottom": "Vertical bars aligned to a bottom baseline.",
    "align_vertical_center": "Vertical bars centered around a middle axis.",
    "align_vertical_top": "Vertical bars aligned to a top baseline.",
    "all_apps": "Bulleted list with horizontal lines.",
    "all_apps_mirrored": "Mirrored bulleted list with horizontal lines.",
    "all_currency": "Currency symbols inside a circular motif.",
    "alt_text": "Image placeholder with text line beneath.",
    "amazon_web_services_logo": "AWS wordmark/logo.",
    "analytics_query": "Circular signal/radar-like analytics symbol.",
    "analytics_report": "Analytics page with pie/bar chart inset.",
    "analytics_view": "Rectangular chart panel with bars.",
    "anchor_lock": "Anchor symbol with a lock.",
    "android_logo": "Android robot logo.",
    "annotation": "Dotted frame with diagonal line and corner handles.",
    "apache_ivy_logo32": "Apache Ivy logo mark.",
    "apache_maven_logo": "Apache Maven “M” logo mark.",
    "archive": "Archive/storage box.",
    "archive_undo": "Archive/storage box with undo arrow.",
    "area_chart": "Area chart with rising region.",
    "arrange_bring_forward": "Two overlapping squares with forward-layer emphasis.",
    "arrange_bring_to_front": "Two overlapping squares with front-layer emphasis.",
    "arrange_by_from": "Document/list with a person badge (arrange-by source).",
    "arrange_send_backward": "Two overlapping squares with backward-layer emphasis.",
    "arrange_send_to_back": "Two overlapping squares with back-layer emphasis.",
    "arrivals": "Ship/arrivals transport symbol.",
    "arrow_down_right8": "Small arrow pointing down-right.",
    "arrow_down_right_mirrored8": "Small mirrored arrow pointing down-right.",
    "arrow_tall_down_left": "Long diagonal arrow pointing down-left.",
    "arrow_tall_down_right": "Long diagonal arrow pointing down-right.",
    "arrow_tall_up_left": "Long diagonal arrow pointing up-left.",
    "arrow_tall_up_right": "Long diagonal arrow pointing up-right.",
    "arrow_up_right": "Arrow pointing up-right.",
    "arrow_up_right8": "Small arrow pointing up-right.",
    "arrow_up_right_mirrored8": "Small mirrored arrow pointing up-right.",
    "articles": "Page/document with text lines.",
    "ascending": "Downward arrow beside stacked letters A and Z.",
    "aspect_ratio": "Dotted frame with centered rectangle (aspect-ratio guide).",
    "assessment_group": "Grouped chart/grid assessment symbol.",
    "assessment_group_template": "Assessment page with inset chart template.",
    "asset_library": "Folder/library with embedded asset tile.",
    "assign": "Clipboard with right-pointing arrow.",
    "assign_policy": "Clipboard with envelope/policy badge.",
    "asterisk": "Asterisk/starburst symbol.",
    "asterisk_solid": "Filled asterisk/starburst symbol.",
    "attach": "Paperclip.",
    "australian_rules": "Australian rules football ball.",
    "auto_deploy_settings": "Display/window with small gear and spark.",
    "auto_enhance_off": "Magic wand with sparkle and a strike/disabled indicator.",
    "auto_enhance_on": "Magic wand with sparkle (enabled).",
    "auto_fill_template": "Template field card with horizontal fill bars.",
    "auto_fit_contents": "Bounding guides with inward arrows (fit to contents).",
    "auto_fit_window": "Bounding guides with outward arrows (fit to window).",
    "auto_height": "Bidirectional vertical arrow with auto marker.",
    "auto_racing": "Steering wheel / racing wheel symbol.",
    "automate_flow": "Connected flow nodes with a lightning bolt connector.",
}

SEMANTIC_OVERRIDES: Dict[str, str] = {
    "accept": "Represents confirm/approve actions.",
    "accept_medium": "Represents confirm/approve actions.",
    "access_logo": "Represents Microsoft Access or database-related content.",
    "accessibilty_checker": "Represents accessibility checking or compliance review.",
    "account_activity": "Represents account history, notes, or activity logs.",
    "account_browser": "Represents viewing account/profile information in a web context.",
    "account_management": "Represents account administration and identity management.",
    "accounts": "Represents accounts, mentions, usernames, or email contexts.",
    "action_center": "Represents notifications, messages, or action hub.",
    "activate_orders": "Represents order activation or fulfillment start.",
    "activity_feed": "Represents an activity stream or feed.",
    "add": "Represents add/create/new actions.",
    "add_bookmark": "Represents saving/bookmarking an item.",
    "add_event": "Represents creating a calendar event.",
    "add_favorite": "Represents adding an item to favorites.",
    "add_favorite_fill": "Represents favorite/highlighted state.",
    "add_friend": "Represents adding a contact or friend.",
    "add_group": "Represents creating/adding a group.",
    "add_home": "Represents adding a home location or home shortcut.",
    "add_in": "Represents adding an add-in, extension, or app module.",
    "add_link": "Represents adding or attaching a link.",
    "add_notes": "Represents adding notes or comments.",
    "add_online_meeting": "Represents scheduling an online meeting.",
    "add_phone": "Represents adding a phone number/contact call endpoint.",
    "add_reaction": "Represents adding an emoji/reaction.",
    "add_space_after": "Represents increasing spacing after content.",
    "add_space_before": "Represents increasing spacing before content.",
    "add_to": "Represents adding to a list/collection.",
    "add_to_shopping_list": "Represents adding items to a shopping list/cart.",
    "add_work": "Represents adding work/business-related items.",
    "air_tickets": "Represents flight tickets or air travel bookings.",
    "airplane": "Represents flights, travel, or aviation.",
    "airplane_solid": "Represents flights, travel, or aviation.",
    "alarm_clock": "Represents alarms, reminders, or scheduled alerts.",
    "album": "Represents a media album or collection.",
    "album_remove": "Represents removing from an album/collection.",
    "alert_settings": "Represents notification or alert configuration.",
    "alert_solid": "Represents warning, error, or important alert state.",
    "align_center": "Represents center text/content alignment.",
    "align_horizontal_center": "Represents horizontal centering of objects.",
    "align_horizontal_left": "Represents left horizontal alignment.",
    "align_horizontal_right": "Represents right horizontal alignment.",
    "align_justify": "Represents justified text alignment.",
    "align_left": "Represents left text alignment.",
    "align_right": "Represents right text alignment.",
    "align_vertical_bottom": "Represents bottom vertical alignment.",
    "align_vertical_center": "Represents vertical centering.",
    "align_vertical_top": "Represents top vertical alignment.",
    "all_apps": "Represents app launcher or all-apps view.",
    "all_apps_mirrored": "Represents app launcher in RTL layouts.",
    "all_currency": "Represents currencies, payments, or finance.",
    "alt_text": "Represents alt-text metadata for images/accessibility.",
    "amazon_web_services_logo": "Represents AWS/cloud-related content.",
    "analytics_query": "Represents querying analytics data.",
    "analytics_report": "Represents analytics reports and reporting views.",
    "analytics_view": "Represents analytics dashboard/view.",
    "anchor_lock": "Represents pinned/anchored and secured state.",
    "android_logo": "Represents Android platform or mobile context.",
    "annotation": "Represents annotation, markup, or review tooling.",
    "apache_ivy_logo32": "Represents Apache Ivy ecosystem/tools.",
    "apache_maven_logo": "Represents Apache Maven ecosystem/tools.",
    "archive": "Represents archiving or long-term storage.",
    "archive_undo": "Represents restore/unarchive action.",
    "area_chart": "Represents area chart visualization.",
    "arrange_bring_forward": "Represents layer ordering: bring forward.",
    "arrange_bring_to_front": "Represents layer ordering: bring to front.",
    "arrange_by_from": "Represents sorting/arranging by a source field.",
    "arrange_send_backward": "Represents layer ordering: send backward.",
    "arrange_send_to_back": "Represents layer ordering: send to back.",
    "arrivals": "Represents arrivals in travel/transport contexts.",
    "arrow_down_right8": "Represents directional movement down-right.",
    "arrow_down_right_mirrored8": "Represents directional movement down-right in RTL contexts.",
    "arrow_tall_down_left": "Represents directional movement down-left.",
    "arrow_tall_down_right": "Represents directional movement down-right.",
    "arrow_tall_up_left": "Represents directional movement up-left.",
    "arrow_tall_up_right": "Represents directional movement up-right.",
    "arrow_up_right": "Represents directional movement up-right.",
    "arrow_up_right8": "Represents directional movement up-right.",
    "arrow_up_right_mirrored8": "Represents directional movement up-right in RTL contexts.",
    "articles": "Represents articles, documents, or written content.",
    "ascending": "Represents ascending sort order.",
    "aspect_ratio": "Represents aspect ratio and proportion constraints.",
    "assessment_group": "Represents grouped assessment/evaluation items.",
    "assessment_group_template": "Represents assessment templates.",
    "asset_library": "Represents an asset repository or media library.",
    "assign": "Represents assignment or delegation.",
    "assign_policy": "Represents assigning governance/security policy.",
    "asterisk": "Represents wildcard, required, or footnote marker.",
    "asterisk_solid": "Represents wildcard, required, or footnote marker.",
    "attach": "Represents file attachment.",
    "australian_rules": "Represents Australian rules football/sport.",
    "auto_deploy_settings": "Represents automated deployment configuration.",
    "auto_enhance_off": "Represents disabled auto-enhancement.",
    "auto_enhance_on": "Represents enabled auto-enhancement.",
    "auto_fill_template": "Represents auto-fill using templates.",
    "auto_fit_contents": "Represents fit-to-content behavior.",
    "auto_fit_window": "Represents fit-to-window behavior.",
    "auto_height": "Represents automatic height sizing.",
    "auto_racing": "Represents motor racing/automotive sport.",
    "automate_flow": "Represents automation workflow/process flow.",
}


def semantic_metaphors(icon_id: str) -> List[str]:
    parts = icon_id.split("_")
    tags: List[str] = []

    def normalized_part(part: str) -> str:
        stripped = part.strip().lower()
        if not stripped:
            return ""
        base = stripped.rstrip("0123456789")
        if base:
            return base
        return stripped

    for part in parts:
        normalized = normalized_part(part)
        if normalized:
            tags.append(normalized)
            tags.extend(TOKEN_TAGS.get(normalized, []))

    if icon_id in {"all_apps", "all_apps_mirrored"}:
        tags.extend(["launcher", "application menu"])
    if "mirrored" in parts:
        tags.extend(["rtl", "right-to-left"])
    if "solid" in parts or "fill" in parts:
        tags.extend(["filled", "solid style"])
    if "logo" in parts:
        tags.extend(["brand", "logo"])
    if icon_id.startswith("arrow_"):
        tags.append("directional")
    if icon_id.startswith("align_"):
        tags.append("text alignment")
    if icon_id.startswith("add_") or icon_id == "add":
        tags.append("add action")

    deduped: List[str] = []
    seen = set()
    for tag in tags:
        normalized = tag.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped[:18]


def literal_description(icon_id: str, display_name: str) -> str:
    if icon_id in LITERAL_OVERRIDES:
        return LITERAL_OVERRIDES[icon_id]

    # Conservative fallback: still literal framing.
    return f"Symbol/icon showing {display_name.lower()}."


def semantic_description(icon_id: str, display_name: str) -> str:
    if icon_id in SEMANTIC_OVERRIDES:
        return SEMANTIC_OVERRIDES[icon_id]

    lowered = display_name.lower()
    return f"Represents {lowered} usage."


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate literal-description batch metadata")
    parser.add_argument("--icon-data", default="icon-data.json")
    parser.add_argument("--batch-index", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--output-dir", default="samples/fabric-grids")
    args = parser.parse_args()

    payload = json.loads(Path(args.icon_data).read_text(encoding="utf-8"))
    icons = payload["sets"]["fabric"]["icons"]

    start = (args.batch_index - 1) * args.batch_size
    end = min(start + args.batch_size, len(icons))
    batch_icons = icons[start:end]

    result = {
        "batch": f"batch-{args.batch_index:04d}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(batch_icons),
        "icons": [],
    }

    for icon in batch_icons:
        icon_id = icon["name"]
        display_name = icon.get("displayName") or icon_id.replace("_", " ").title()
        result["icons"].append(
            {
                "id": icon_id,
                "name": display_name,
                "literalDescription": literal_description(icon_id, display_name),
                "semanticDescription": semantic_description(icon_id, display_name),
                "description": (
                    f"{literal_description(icon_id, display_name)} "
                    f"{semantic_description(icon_id, display_name)}"
                ).strip(),
                "metaphors": semantic_metaphors(icon_id),
            }
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"batch-{args.batch_index:04d}-metadata-draft.json"
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out_file)


if __name__ == "__main__":
    main()
