#!/usr/bin/env python3
"""
normalize_svg.py – Phase 3: 最終版SVGの整理

03_svg_verified のSVGに対して以下を実施:
1. メタデータ埋め込み (title, desc, metadata)
2. 比率の正規化 (viewBox を公式比率に統一)
3. 不要要素の除去 (DOCTYPE, XML comments, editor metadata)
4. 統一XMLヘッダー付与

入力: 03_svg_verified/*.svg + 02_official_specs/*.json + 00_master/countries_master.csv
出力: 03_svg_verified/*.svg (上書き) + 06_docs/normalize_log.csv
"""

import json
import os
import re
import csv
import math
from pathlib import Path
from typing import Optional, Dict, Tuple
from fractions import Fraction

# ── Configuration ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR      = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR     = PROJECT_ROOT / "02_official_specs"
MASTER_CSV   = PROJECT_ROOT / "00_master" / "countries_master.csv"
LOG_PATH     = PROJECT_ROOT / "06_docs" / "normalize_log.csv"

# Metadata constants
PROJECT_AUTHOR = "国旗仕様検証プロジェクト (Flag Specification Verification Project)"
LICENSE_TEXT = "Colors verified from official government/vexillological sources. SVG geometry from Wikimedia Commons (various authors, mostly public domain)."

# Base height for viewBox normalization
BASE_HEIGHT = 600


# ── Ratio parsing ────────────────────────────────────────────────

def parse_ratio(ratio_str: str) -> Optional[Tuple[float, float]]:
    """
    Parse aspect ratio string to (height, width) tuple.
    Returns None for unparseable ratios.
    Ratio format is height:width (e.g., "2:3" means height=2, width=3).
    """
    if not ratio_str or ratio_str.strip() == "":
        return None

    ratio_str = ratio_str.strip()

    # Special cases
    if ratio_str == "special":
        # Nepal - non-rectangular, keep as-is
        return None
    if ratio_str == "golden ratio":
        # Togo: height:width = 1:φ ≈ 1:1.618
        return (1.0, 1.618033988749895)

    # Standard "H:W" format
    m = re.match(r'^(\d+):(\d+)$', ratio_str)
    if m:
        h = int(m.group(1))
        w = int(m.group(2))
        return (float(h), float(w))

    return None


def compute_dimensions(ratio: Optional[Tuple[float, float]], base_h: int = BASE_HEIGHT) -> Tuple[int, int]:
    """Compute (width, height) from ratio, with height = base_h."""
    if ratio is None:
        return (base_h * 3 // 2, base_h)  # default 2:3
    h_ratio, w_ratio = ratio
    width = round(base_h * w_ratio / h_ratio)
    return (width, base_h)


# ── SVG processing ───────────────────────────────────────────────

def clean_svg(svg_text: str) -> str:
    """Remove unwanted elements from SVG."""
    # Remove XML declaration (we'll add our own)
    svg_text = re.sub(r'<\?xml[^?]*\?>\s*', '', svg_text)

    # Remove DOCTYPE declarations
    svg_text = re.sub(r'<!DOCTYPE[^>]*>\s*', '', svg_text)

    # Remove HTML/XML comments (but preserve conditional comments)
    svg_text = re.sub(r'<!--[\s\S]*?-->\s*', '', svg_text)

    # Remove existing <title> elements
    svg_text = re.sub(r'<title[^>]*>[\s\S]*?</title>\s*', '', svg_text)

    # Remove existing <desc> elements
    svg_text = re.sub(r'<desc[^>]*>[\s\S]*?</desc>\s*', '', svg_text)

    # Remove existing <metadata> elements
    svg_text = re.sub(r'<metadata[^>]*>[\s\S]*?</metadata>\s*', '', svg_text)

    # Remove Inkscape/Sodipodi/Adobe specific attributes on the root <svg>
    svg_text = re.sub(r'\s+(?:inkscape|sodipodi|xmlns:inkscape|xmlns:sodipodi|xmlns:dc|xmlns:cc|xmlns:rdf)[^\s=]*="[^"]*"', '', svg_text)

    # Remove empty lines
    svg_text = re.sub(r'\n\s*\n+', '\n', svg_text)

    return svg_text.strip()


def get_svg_tag_match(svg_text: str):
    """Find the opening <svg> tag."""
    return re.search(r'(<svg\b[^>]*>)', svg_text, re.DOTALL)


def update_viewbox(svg_text: str, width: int, height: int) -> str:
    """
    Update the <svg> tag's width, height, and viewBox attributes.
    Preserves the internal viewBox coordinate system if it exists,
    but updates width/height to match the target ratio.
    """
    svg_match = get_svg_tag_match(svg_text)
    if not svg_match:
        return svg_text

    svg_tag = svg_match.group(1)
    new_tag = svg_tag

    # Extract current viewBox if exists
    vb_match = re.search(r'viewBox\s*=\s*"([^"]*)"', new_tag)

    if vb_match:
        # Has viewBox — update width/height attributes but keep viewBox
        # (viewBox defines the internal coordinate system)
        new_tag = re.sub(r'\bwidth\s*=\s*"[^"]*"', f'width="{width}"', new_tag)
        new_tag = re.sub(r'\bheight\s*=\s*"[^"]*"', f'height="{height}"', new_tag)
        if 'width=' not in new_tag:
            new_tag = new_tag.replace('<svg ', f'<svg width="{width}" ')
        if 'height=' not in new_tag:
            new_tag = new_tag.replace(f'width="{width}"', f'width="{width}" height="{height}"')
    else:
        # No viewBox — create one from current width/height, then update
        w_match = re.search(r'\bwidth\s*=\s*"(\d+(?:\.\d+)?)"', new_tag)
        h_match = re.search(r'\bheight\s*=\s*"(\d+(?:\.\d+)?)"', new_tag)

        if w_match and h_match:
            old_w = w_match.group(1)
            old_h = h_match.group(1)
            # Add viewBox with old dimensions (preserves internal coordinates)
            new_tag = new_tag.replace('<svg ', f'<svg viewBox="0 0 {old_w} {old_h}" ')
            # Update width/height to new ratio
            new_tag = re.sub(r'\bwidth\s*=\s*"[^"]*"', f'width="{width}"', new_tag)
            new_tag = re.sub(r'\bheight\s*=\s*"[^"]*"', f'height="{height}"', new_tag)
        else:
            # No dimensions at all — set viewBox and dimensions
            new_tag = new_tag.replace('<svg ', f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" ')

    return svg_text.replace(svg_tag, new_tag, 1)


def inject_metadata(svg_text: str, spec: dict, master_row: dict) -> str:
    """Insert <title>, <desc>, and <metadata> right after the opening <svg> tag."""
    code = spec.get("iso_alpha2", "")
    name_en = spec.get("name_en", "")
    name_ja = spec.get("name_ja", "")
    ratio = spec.get("ratio", master_row.get("ratio", ""))
    source = spec.get("specs_source", "")

    title_text = f"Flag of {name_en}" + (f" ({name_ja})" if name_ja else "")
    desc_text = f"ISO 3166-1: {code} | Ratio: {ratio}" + (f" | {source}" if source else "")

    metadata_block = f"""
  <title>{title_text}</title>
  <desc>{desc_text}</desc>
  <metadata>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:dc="http://purl.org/dc/elements/1.1/">
      <rdf:Description>
        <dc:title>{title_text}</dc:title>
        <dc:creator>{PROJECT_AUTHOR}</dc:creator>
        <dc:rights>{LICENSE_TEXT}</dc:rights>
        <dc:format>image/svg+xml</dc:format>
        <dc:identifier>{code}</dc:identifier>
      </rdf:Description>
    </rdf:RDF>
  </metadata>"""

    # Insert after opening <svg> tag
    svg_match = get_svg_tag_match(svg_text)
    if svg_match:
        insert_pos = svg_match.end()
        svg_text = svg_text[:insert_pos] + metadata_block + svg_text[insert_pos:]

    return svg_text


def add_xml_header(svg_text: str) -> str:
    """Add standard XML declaration."""
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_text


# ── Main ─────────────────────────────────────────────────────────

def process_all():
    """Process all SVGs."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load master CSV
    master = {}
    with open(MASTER_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            master[row['iso_alpha2']] = row

    log_rows = []
    stats = {
        "processed": 0,
        "skipped": 0,
        "ratio_updated": 0,
        "metadata_added": 0,
        "cleaned": 0,
    }

    for svg_path in sorted(SVG_DIR.glob("*.svg")):
        code = svg_path.stem
        spec_path = SPEC_DIR / f"{code}.json"

        if not spec_path.exists():
            stats["skipped"] += 1
            log_rows.append([code, "SKIP", "No spec file", "", ""])
            continue

        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)

        m_row = master.get(code, {})
        ratio_str = spec.get("ratio", m_row.get("ratio", ""))

        # Read SVG
        with open(svg_path, encoding="utf-8") as f:
            original = f.read()

        svg_text = original

        # Step 1: Clean
        svg_text = clean_svg(svg_text)
        was_cleaned = svg_text != original.strip()

        # Step 2: Normalize viewBox / dimensions
        ratio = parse_ratio(ratio_str)
        if ratio is not None:
            width, height = compute_dimensions(ratio)
            svg_text = update_viewbox(svg_text, width, height)
            stats["ratio_updated"] += 1
            ratio_note = f"{ratio_str} → {width}x{height}"
        else:
            # Nepal or unknown — keep original dimensions
            ratio_note = f"{ratio_str} (kept original)"

        # Step 3: Inject metadata
        svg_text = inject_metadata(svg_text, spec, m_row)
        stats["metadata_added"] += 1

        # Step 4: Add XML header
        svg_text = add_xml_header(svg_text)

        # Write back
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_text)

        if was_cleaned:
            stats["cleaned"] += 1

        stats["processed"] += 1
        log_rows.append([
            code,
            "OK",
            ratio_note,
            spec.get("name_en", ""),
            f"cleaned={was_cleaned}"
        ])

    # Write log
    with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iso_alpha2", "status", "ratio_info", "name_en", "notes"])
        writer.writerows(log_rows)

    # Print summary
    print("=" * 60)
    print("  SVG Normalization Summary")
    print("=" * 60)
    print(f"  Processed:        {stats['processed']}")
    print(f"  Skipped:          {stats['skipped']}")
    print(f"  Ratios updated:   {stats['ratio_updated']}")
    print(f"  Metadata added:   {stats['metadata_added']}")
    print(f"  Cleaned:          {stats['cleaned']}")
    print("=" * 60)
    print(f"  Log: {LOG_PATH}")


if __name__ == "__main__":
    process_all()
