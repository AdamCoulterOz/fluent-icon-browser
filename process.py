#!/usr/bin/env python3
"""
Build a consolidated icon folder from Fluent UI System Icons assets.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from svgpathtools import parse_path

def normalise_svg(input_file: Path, output_file: Path, inherit_color: bool = False) -> None:
    # Parse the SVG file
    tree = ET.parse(input_file)
    root = tree.getroot()
    
    # Remove namespace prefixes for easier processing
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}')[1]
    
    # Calculate bounding box of all elements
    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
    
    def update_bbox(x, y):
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)
    
    # Process different SVG elements to find bounding box
    for elem in root.iter():
        if elem.tag in ['rect', 'circle', 'ellipse', 'line']:
            if elem.tag == 'rect':
                x = float(elem.get('x', 0))
                y = float(elem.get('y', 0))
                width = float(elem.get('width', 0))
                height = float(elem.get('height', 0))
                update_bbox(x, y)
                update_bbox(x + width, y + height)
            elif elem.tag == 'circle':
                cx = float(elem.get('cx', 0))
                cy = float(elem.get('cy', 0))
                r = float(elem.get('r', 0))
                update_bbox(cx - r, cy - r)
                update_bbox(cx + r, cy + r)
            elif elem.tag == 'ellipse':
                cx = float(elem.get('cx', 0))
                cy = float(elem.get('cy', 0))
                rx = float(elem.get('rx', 0))
                ry = float(elem.get('ry', 0))
                update_bbox(cx - rx, cy - ry)
                update_bbox(cx + rx, cy + ry)
            elif elem.tag == 'line':
                x1 = float(elem.get('x1', 0))
                y1 = float(elem.get('y1', 0))
                x2 = float(elem.get('x2', 0))
                y2 = float(elem.get('y2', 0))
                update_bbox(x1, y1)
                update_bbox(x2, y2)
        
        elif elem.tag == 'path':
            d = elem.get('d', '')
            if d:
                try:
                    path = parse_path(d)
                    bbox = path.bbox()
                    # bbox returns (xmin, xmax, ymin, ymax)
                    update_bbox(bbox[0], bbox[2])  # xmin, ymin
                    update_bbox(bbox[1], bbox[3])  # xmax, ymax
                except Exception:
                    pass
    
    # If no elements found, use default values
    if min_x == float('inf'):
        min_x = min_y = 0
        max_x = max_y = 100
    
    # Calculate current dimensions
    current_width = max_x - min_x
    current_height = max_y - min_y
    
    # Calculate scale factor to fit in 100x100 while maintaining aspect ratio
    scale_x = 100 / current_width if current_width > 0 else 1
    scale_y = 100 / current_height if current_height > 0 else 1
    scale = min(scale_x, scale_y)
    
    # Calculate new dimensions after scaling
    new_width = current_width * scale
    new_height = current_height * scale
    
    # Calculate translation to center in 100x100 viewbox
    translate_x = (100 - new_width) / 2 - min_x * scale
    translate_y = (100 - new_height) / 2 - min_y * scale
    
    # Create transformation string
    transform = f"translate({translate_x:.6f}, {translate_y:.6f}) scale({scale:.6f})"
    
    # Apply transformation to root or create a group
    if root.get('transform'):
        root.set('transform', f"{transform} {root.get('transform')}")
    else:
        # Create a group to contain all elements with the transformation
        group = ET.Element('g')
        group.set('transform', transform)
        
        # Move all children to the group
        for child in list(root):
            root.remove(child)
            group.append(child)
        
        root.append(group)
    
    # Set the viewBox to 100x100
    root.set('viewBox', '0 0 100 100')
    root.set('width', '100')
    root.set('height', '100')
    
    # Ensure SVG namespace
    root.set('xmlns', 'http://www.w3.org/2000/svg')

    if inherit_color:
        # replace fill with "currentColor" for inheriting color
        # only where fill is set and isnt "none"
        for elem in root.iter():
            if 'fill' in elem.attrib and elem.get('fill') != 'none':
                elem.set('fill', 'currentColor')
    
    # Write the normalized SVG
    tree.write(output_file, encoding='utf-8', xml_declaration=True)

def extract_svg(icon_type: str, icon_dir: Path, target_dir: Path) -> None:
    pattern = f"ic_fluent_*_{icon_type}.svg"
    # Locate the SVG folder and the first matching SVG file
    svg_folder = icon_dir / 'SVG'
    svg_files = sorted(svg_folder.glob(pattern))
    if not svg_files:
        return
    svg_file = svg_files[0]

    if not (m := re.match(r"^ic_fluent_(.*?)_\d+_.*\.svg$", svg_file.name)):
        raise ValueError(f"Invalid icon filename: {svg_file.name}")
    new_icon_name = f"{m.group(1)}_{icon_type}.svg"
    # Write out the new SVG
    out_svg_path = target_dir / new_icon_name
    inherit_color = icon_type != "color"  # Inherit color for non-color variants
    normalise_svg(svg_file, out_svg_path, inherit_color=inherit_color)

def consolidate_icons(input_dir: Path, output_dir: Path) -> None:
    """
    Iterate through asset icon folders, normalize icon variants to a 100x100 viewBox,
    and output alongside cleaned metadata.
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    for icon_dir in input_dir.iterdir():
        if not icon_dir.is_dir():
            continue

        target_dir = output_dir / icon_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)

        extract_svg("regular", icon_dir, target_dir)
        extract_svg("filled", icon_dir, target_dir)
        extract_svg("color", icon_dir, target_dir)

        # Process metadata.json
        meta_in = icon_dir / 'metadata.json'
        if meta_in.exists():
            data = json.loads(meta_in.read_text(encoding="utf-8"))
            data.pop("size", None)  # Remove size if present
            with open(target_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build consolidated icon assets from microsoft/fluentui-system-icons"
    )
    parser.add_argument(
        "--input-dir",
        default="assets",
        help="Path to upstream assets directory (default: assets)",
    )
    parser.add_argument(
        "--output-dir",
        default="consolidated",
        help="Output path for consolidated icons (default: consolidated)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    consolidate_icons(Path(args.input_dir), Path(args.output_dir))
    print(f"Consolidation complete. Output in '{args.output_dir}/' directory.")
