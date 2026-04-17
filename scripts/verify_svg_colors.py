#!/usr/bin/env python3
"""
verify_svg_colors.py – 03_svg_verified の色を 02_official_specs と照合して検証

入力: 03_svg_verified/*.svg + 02_official_specs/*.json
出力: 06_docs/svg_color_verification.md
"""

import json
import re
import csv
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple

# ── Configuration ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR      = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR     = PROJECT_ROOT / "02_official_specs"
MASTER_CSV   = PROJECT_ROOT / "00_master" / "countries_master.csv"
REPORT_PATH  = PROJECT_ROOT / "06_docs" / "svg_color_verification.md"


def extract_svg_colors(svg_text: str) -> Set[str]:
    """Extract all hex color references from SVG text, including named colors and implicit black."""
    # CSS named colors → HEX
    CSS_NAMED_COLORS = {
        "black": "#000000", "white": "#FFFFFF", "red": "#FF0000",
        "green": "#008000", "blue": "#0000FF", "yellow": "#FFFF00",
        "orange": "#FFA500", "gray": "#808080", "grey": "#808080",
        "maroon": "#800000", "navy": "#000080", "olive": "#808000",
        "purple": "#800080", "teal": "#008080", "aqua": "#00FFFF",
        "fuchsia": "#FF00FF", "lime": "#00FF00", "silver": "#C0C0C0",
        "darkred": "#8B0000", "darkgreen": "#006400", "darkblue": "#00008B",
        "gold": "#FFD700", "crimson": "#DC143C", "indigo": "#4B0082",
    }

    colors = set()
    for m in re.finditer(r'#([0-9a-fA-F]{6})(?![0-9a-fA-F])', svg_text):
        colors.add("#" + m.group(1).upper())
    for m in re.finditer(r'#([0-9a-fA-F]{3})(?![0-9a-fA-F])', svg_text):
        h = m.group(1)
        expanded = h[0]*2 + h[1]*2 + h[2]*2
        colors.add("#" + expanded.upper())

    # Named colors in attributes/styles
    for m in re.finditer(
        r'(?:fill|stroke|stop-color|color)\s*[=:]\s*["\']?\s*([a-zA-Z]+)',
        svg_text
    ):
        name = m.group(1).lower()
        if name in CSS_NAMED_COLORS and name != "none":
            colors.add(CSS_NAMED_COLORS[name])

    # Detect implicit black: elements without fill attribute default to black per SVG spec
    shape_elements = re.findall(
        r'<(path|rect|polygon|circle|ellipse|polyline|line)\b([^>]*?)(?:/>|>)',
        svg_text
    )
    for tag, attrs in shape_elements:
        if 'fill' not in attrs.lower():
            colors.add("#000000")
            break  # one is enough to confirm black is used

    return colors


def load_master_csv() -> Dict[str, dict]:
    """Load master CSV for region data."""
    countries = {}
    with open(MASTER_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            countries[row['iso_alpha2']] = row
    return countries


def verify_all():
    """Verify all SVGs against specs."""
    master = load_master_csv()
    spec_files = sorted(SPEC_DIR.glob("*.json"))

    results = []
    total_match = 0
    total_mismatch = 0
    total_extra = 0
    total_missing_color = 0
    total_skipped = 0

    region_stats = {}

    for spec_path in spec_files:
        if spec_path.name == "schema.json":
            continue

        code = spec_path.stem
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)

        spec_colors = spec.get("colors", [])
        name_en = spec.get("name_en", code)
        name_ja = spec.get("name_ja", "")
        region = master.get(code, {}).get("un_m49_region", "Other")

        if not spec_colors:
            results.append({
                "code": code, "name_en": name_en, "name_ja": name_ja,
                "region": region, "status": "SKIP", "detail": "No color data",
                "spec_colors": [], "svg_colors": set(), "matched": set(),
                "extra": set(), "missing": set()
            })
            total_skipped += 1
            continue

        svg_path = SVG_DIR / f"{code}.svg"
        if not svg_path.exists():
            results.append({
                "code": code, "name_en": name_en, "name_ja": name_ja,
                "region": region, "status": "SKIP", "detail": "SVG not found",
                "spec_colors": [], "svg_colors": set(), "matched": set(),
                "extra": set(), "missing": set()
            })
            total_skipped += 1
            continue

        with open(svg_path, encoding="utf-8") as f:
            svg_text = f.read()

        svg_colors = extract_svg_colors(svg_text)
        spec_hex = set(c["hex"].upper() for c in spec_colors)

        matched = spec_hex & svg_colors
        missing = spec_hex - svg_colors
        extra = svg_colors - spec_hex

        if missing:
            status = "⚠️ MISMATCH"
            total_mismatch += 1
        else:
            status = "✅ PASS"
            total_match += 1

        total_extra += len(extra)
        total_missing_color += len(missing)

        results.append({
            "code": code, "name_en": name_en, "name_ja": name_ja,
            "region": region, "status": status, "detail": "",
            "spec_colors": spec_colors, "svg_colors": svg_colors,
            "matched": matched, "extra": extra, "missing": missing
        })

        # Region stats
        if region not in region_stats:
            region_stats[region] = {"pass": 0, "mismatch": 0, "skip": 0}
        if "PASS" in status:
            region_stats[region]["pass"] += 1
        elif "MISMATCH" in status:
            region_stats[region]["mismatch"] += 1
        else:
            region_stats[region]["skip"] += 1

    # ── Generate Markdown Report ─────────────────────────────────
    lines = []
    lines.append("# SVG Color Verification Report")
    lines.append("")
    lines.append(f"**Generated**: Phase 2 — SVG色整合性チェック")
    lines.append("")
    lines.append("## Summary\n")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| ✅ All spec colors present | **{total_match}** |")
    lines.append(f"| ⚠️ Missing spec colors | **{total_mismatch}** |")
    lines.append(f"| Skipped (no data/SVG) | {total_skipped} |")
    lines.append(f"| Total extra colors in SVGs | {total_extra} |")
    lines.append(f"| Total missing color instances | {total_missing_color} |")
    lines.append("")

    # Region breakdown
    lines.append("## By Region\n")
    lines.append("| Region | ✅ Pass | ⚠️ Mismatch | Skip |")
    lines.append("|--------|--------|------------|------|")
    for region in sorted(region_stats.keys()):
        s = region_stats[region]
        lines.append(f"| {region} | {s['pass']} | {s['mismatch']} | {s['skip']} |")
    lines.append("")

    # Mismatches detail
    mismatches = [r for r in results if "MISMATCH" in r["status"]]
    if mismatches:
        lines.append("## Mismatches Detail\n")
        lines.append("| Code | Country | Missing Colors | Extra Colors |")
        lines.append("|------|---------|---------------|-------------|")
        for r in mismatches:
            missing_str = ", ".join(sorted(r["missing"]))
            extra_str = ", ".join(sorted(r["extra"]))[:60]
            lines.append(f"| {r['code']} | {r['name_en']} | {missing_str} | {extra_str} |")
        lines.append("")

    # Pass list (compact)
    passes = [r for r in results if "PASS" in r["status"]]
    lines.append("## ✅ Passed Countries\n")
    lines.append(f"{len(passes)} countries have all spec colors present in their SVGs.\n")
    pass_codes = ", ".join(r["code"] for r in passes)
    lines.append(f"<details><summary>Show all {len(passes)} codes</summary>\n")
    lines.append(f"{pass_codes}")
    lines.append(f"\n</details>\n")

    # Write report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Report saved to: {REPORT_PATH}")
    print(f"  ✅ Pass: {total_match}")
    print(f"  ⚠️ Mismatch: {total_mismatch}")
    print(f"  Skipped: {total_skipped}")


if __name__ == "__main__":
    verify_all()
