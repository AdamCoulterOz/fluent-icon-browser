#!/usr/bin/env python3
"""Generate 10x10 visual sampling grids for Fabric MDL2 icons."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Run this script from the .venv-vision environment."
    ) from exc


CARD_WIDTH = 280
CARD_HEIGHT = 240
GRID_COLUMNS = 10
GRID_ROWS = 10
CARD_GAP = 20
GRID_PADDING = 20
ICON_MAX_SIZE = 70
ICON_TOP_OFFSET = 40
LABEL_TOP_OFFSET = 138
LABEL_SIDE_PADDING = 14
CARD_BG = (244, 244, 244)
CANVAS_BG = (236, 236, 236)
CARD_BORDER = (201, 201, 201)
TEXT_COLOR = (42, 42, 42)


def load_payload(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def pick_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = []
    if bold:
        font_candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
                "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
            ]
        )
    else:
        font_candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttf",
                "/System/Library/Fonts/Supplemental/Verdana.ttf",
            ]
        )

    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue

    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return [text]

    lines: List[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)

    if len(lines) <= 2:
        return lines

    first = lines[0]
    second = " ".join(lines[1:])
    while draw.textbbox((0, 0), second + "…", font=font)[2] > max_width and len(second) > 1:
        second = second[:-1]

    return [first, second.rstrip() + "…"]


def render_svg_to_png(svg_text: str, output_png: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        svg_path = Path(tmp_dir) / "icon.svg"
        svg_path.write_text(svg_text, encoding="utf-8")

        subprocess.run(
            [
                "magick",
                str(svg_path),
                "-background",
                "none",
                "-alpha",
                "set",
                "-colorspace",
                "sRGB",
                "-resize",
                f"{ICON_MAX_SIZE}x{ICON_MAX_SIZE}",
                str(output_png),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def card_position(index_in_batch: int) -> Tuple[int, int]:
    row = index_in_batch // GRID_COLUMNS
    col = index_in_batch % GRID_COLUMNS

    x = GRID_PADDING + col * (CARD_WIDTH + CARD_GAP)
    y = GRID_PADDING + row * (CARD_HEIGHT + CARD_GAP)
    return x, y


def make_batch_canvas() -> Image.Image:
    width = GRID_PADDING * 2 + GRID_COLUMNS * CARD_WIDTH + (GRID_COLUMNS - 1) * CARD_GAP
    height = GRID_PADDING * 2 + GRID_ROWS * CARD_HEIGHT + (GRID_ROWS - 1) * CARD_GAP
    return Image.new("RGB", (width, height), CANVAS_BG)


def generate_batches(
    icons: List[Dict],
    output_dir: Path,
    batch_size: int,
) -> Dict:
    ensure_dir(output_dir)

    icon_cache_dir = output_dir / "_icon_cache"
    ensure_dir(icon_cache_dir)

    name_font = pick_font(18, bold=True)
    manifest: Dict[str, List[Dict[str, str]]] = {}

    total_batches = math.ceil(len(icons) / batch_size)

    for batch_index in range(total_batches):
        start = batch_index * batch_size
        end = min(start + batch_size, len(icons))
        batch_icons = icons[start:end]

        canvas = make_batch_canvas()
        draw = ImageDraw.Draw(canvas)

        key = f"batch-{batch_index + 1:04d}"
        manifest[key] = []

        for i, icon in enumerate(batch_icons):
            card_x, card_y = card_position(i)
            card_box = [
                card_x,
                card_y,
                card_x + CARD_WIDTH,
                card_y + CARD_HEIGHT,
            ]

            draw.rounded_rectangle(
                card_box,
                radius=14,
                fill=CARD_BG,
                outline=CARD_BORDER,
                width=2,
            )

            icon_id = icon["name"]
            display_name = icon.get("displayName") or icon_id.replace("_", " ").title()
            svg_text = icon["variants"]["regular"].get("previewSvg")
            if not isinstance(svg_text, str) or not svg_text:
                continue

            icon_png = icon_cache_dir / f"{icon_id}.png"
            if not icon_png.exists():
                render_svg_to_png(svg_text, icon_png)

            icon_img = Image.open(icon_png).convert("RGBA")
            icon_px = card_x + (CARD_WIDTH - icon_img.width) // 2
            icon_py = card_y + ICON_TOP_OFFSET
            canvas.paste(icon_img, (icon_px, icon_py), mask=icon_img)

            lines = wrap_text(draw, display_name, name_font, CARD_WIDTH - LABEL_SIDE_PADDING * 2)
            line_height = draw.textbbox((0, 0), "Ag", font=name_font)[3] + 2
            text_block_height = line_height * len(lines)
            text_start_y = card_y + LABEL_TOP_OFFSET + max(0, (58 - text_block_height) // 2)

            for line_index, line in enumerate(lines):
                text_width = draw.textbbox((0, 0), line, font=name_font)[2]
                text_x = card_x + (CARD_WIDTH - text_width) // 2
                text_y = text_start_y + line_index * line_height
                draw.text((text_x, text_y), line, font=name_font, fill=TEXT_COLOR)

            manifest[key].append(
                {
                    "id": icon_id,
                    "name": display_name,
                }
            )

        output_file = output_dir / f"{key}.png"
        canvas.save(output_file, format="PNG")

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Fabric MDL2 visual sampling grids")
    parser.add_argument(
        "--icon-data",
        default="icon-data.json",
        help="Path to icon-data.json",
    )
    parser.add_argument(
        "--output-dir",
        default="samples/fabric-grids",
        help="Directory to write grid PNGs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Icons per grid sheet",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of icons to include (0 = all)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = load_payload(Path(args.icon_data))
    icons = payload.get("sets", {}).get("fabric", {}).get("icons", [])

    if not isinstance(icons, list) or not icons:
        raise SystemExit("No Fabric icons found in icon-data payload.")

    if args.limit and args.limit > 0:
        icons = icons[: args.limit]

    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)

    manifest = generate_batches(icons=icons, output_dir=output_dir, batch_size=args.batch_size)

    manifest_payload = {
        "generatedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "iconCount": len(icons),
        "batchSize": args.batch_size,
        "batches": manifest,
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        f"{json.dumps(manifest_payload, indent=2, ensure_ascii=False)}\n", encoding="utf-8"
    )

    print(
        f"Generated {len(manifest)} batch sheets for {len(icons)} icons -> {output_dir}"
    )


if __name__ == "__main__":
    main()
