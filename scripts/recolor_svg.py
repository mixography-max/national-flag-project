#!/usr/bin/env python3
"""
recolor_svg.py – Wikipedia SVGの色を公式仕様のHEX値に置換する

入力: 01_svg_wikipedia/*.svg + 02_official_specs/*.json
出力: 03_svg_verified/*.svg + 06_docs/recolor_log.csv
"""

import json
import os
import re
import csv
import math
import colorsys
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple

# ── Configuration ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_IN_DIR   = PROJECT_ROOT / "01_svg_wikipedia"
SPEC_DIR     = PROJECT_ROOT / "02_official_specs"
SVG_OUT_DIR  = PROJECT_ROOT / "03_svg_verified"
LOG_PATH     = PROJECT_ROOT / "06_docs" / "recolor_log.csv"

# Color difference threshold: if ΔE > this, keep original color
DELTA_E_THRESHOLD = 30.0

# CSS named colors → HEX mapping (common ones found in SVGs)
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


# ── CIE Lab / CIEDE2000 helpers (no external deps) ──────────────

def _hex_to_rgb(h: str) -> tuple:
    """Parse #RRGGBB or #RGB to (R, G, B) in 0-255."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _srgb_to_linear(c: float) -> float:
    """sRGB gamma to linear."""
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb_to_lab(r: int, g: int, b: int) -> tuple:
    """Convert sRGB to CIE L*a*b* (D65)."""
    rl = _srgb_to_linear(r)
    gl = _srgb_to_linear(g)
    bl = _srgb_to_linear(b)

    # sRGB → XYZ (D65)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041

    # D65 reference
    xr, yr, zr = 0.95047, 1.00000, 1.08883
    x /= xr; y /= yr; z /= zr

    def f(t):
        return t ** (1/3) if t > 0.008856 else (903.3 * t + 16) / 116

    fx, fy, fz = f(x), f(y), f(z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return L, a, b_val


def ciede2000(lab1: tuple, lab2: tuple) -> float:
    """CIEDE2000 color difference."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    kL = kC = kH = 1.0

    # Step 1
    C1s = math.sqrt(a1**2 + b1**2)
    C2s = math.sqrt(a2**2 + b2**2)
    Cm = (C1s + C2s) / 2.0
    Cm7 = Cm**7
    G = 0.5 * (1 - math.sqrt(Cm7 / (Cm7 + 25**7)))
    a1p = a1 * (1 + G)
    a2p = a2 * (1 + G)
    C1p = math.sqrt(a1p**2 + b1**2)
    C2p = math.sqrt(a2p**2 + b2**2)

    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360

    # Step 2
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))

    # Step 3
    Lpm = (L1 + L2) / 2
    Cpm = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hpm = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hpm = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hpm = (h1p + h2p + 360) / 2
    else:
        hpm = (h1p + h2p - 360) / 2

    T = (1
         - 0.17 * math.cos(math.radians(hpm - 30))
         + 0.24 * math.cos(math.radians(2 * hpm))
         + 0.32 * math.cos(math.radians(3 * hpm + 6))
         - 0.20 * math.cos(math.radians(4 * hpm - 63)))

    SL = 1 + 0.015 * (Lpm - 50)**2 / math.sqrt(20 + (Lpm - 50)**2)
    SC = 1 + 0.045 * Cpm
    SH = 1 + 0.015 * Cpm * T

    Cpm7 = Cpm**7
    RT = (-2 * math.sqrt(Cpm7 / (Cpm7 + 25**7))
          * math.sin(math.radians(60 * math.exp(-((hpm - 275) / 25)**2))))

    dE = math.sqrt(
        (dLp / (kL * SL))**2
        + (dCp / (kC * SC))**2
        + (dHp / (kH * SH))**2
        + RT * (dCp / (kC * SC)) * (dHp / (kH * SH))
    )
    return dE


# ── Main logic ───────────────────────────────────────────────────

def load_spec(code: str) -> Optional[dict]:
    """Load official spec JSON for a country code."""
    path = SPEC_DIR / f"{code}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_svg_colors(svg_text: str) -> set:
    """Extract all hex color references from SVG text, including named colors."""
    colors = set()

    # Match #RRGGBB
    for m in re.finditer(r'#([0-9a-fA-F]{6})(?![0-9a-fA-F])', svg_text):
        colors.add("#" + m.group(1).upper())

    # Match #RGB (expand to #RRGGBB)
    for m in re.finditer(r'#([0-9a-fA-F]{3})(?![0-9a-fA-F])', svg_text):
        h = m.group(1)
        expanded = h[0]*2 + h[1]*2 + h[2]*2
        colors.add("#" + expanded.upper())

    # Match CSS named colors in fill/stroke/style attributes
    for m in re.finditer(
        r'(?:fill|stroke|stop-color|color)\s*[=:]\s*["\']?\s*([a-zA-Z]+)',
        svg_text
    ):
        name = m.group(1).lower()
        if name in CSS_NAMED_COLORS and name != "none":
            colors.add(CSS_NAMED_COLORS[name])

    return colors


def build_color_map(svg_colors: set, spec_colors: list) -> dict:
    """
    Map each SVG color to the closest spec color by CIEDE2000.
    Returns {svg_hex: spec_hex} or {svg_hex: None} if no close match.
    """
    spec_lab = {}
    for sc in spec_colors:
        hex_val = sc["hex"].upper()
        rgb = _hex_to_rgb(hex_val)
        spec_lab[hex_val] = _rgb_to_lab(*rgb)

    color_map = {}
    for svg_hex in svg_colors:
        svg_rgb = _hex_to_rgb(svg_hex)
        svg_lab = _rgb_to_lab(*svg_rgb)

        best_match = None
        best_de = float("inf")
        for spec_hex, s_lab in spec_lab.items():
            de = ciede2000(svg_lab, s_lab)
            if de < best_de:
                best_de = de
                best_match = spec_hex

        if best_de == 0:
            # Exact match  — no change needed
            color_map[svg_hex] = svg_hex
        elif best_de <= DELTA_E_THRESHOLD:
            color_map[svg_hex] = best_match
        else:
            # Too different — keep original (likely emblem/decoration color)
            color_map[svg_hex] = None

    return color_map


def recolor_svg(svg_text: str, color_map: dict) -> str:
    """
    Replace hex colors in SVG text according to color_map.
    Handles fill=, stroke=, stop-color=, style= attributes, CSS named colors.
    """
    def replace_hex6(match):
        original = "#" + match.group(1).upper()
        replacement = color_map.get(original)
        if replacement and replacement != original:
            return replacement
        return "#" + match.group(1)

    def replace_hex3(match):
        h = match.group(1)
        expanded = "#" + (h[0]*2 + h[1]*2 + h[2]*2).upper()
        replacement = color_map.get(expanded)
        if replacement and replacement != expanded:
            return replacement
        return "#" + h

    # Replace CSS named colors with mapped hex values
    def replace_named_color(match):
        prefix = match.group(1)
        name = match.group(2).lower()
        if name in CSS_NAMED_COLORS and name != "none":
            original_hex = CSS_NAMED_COLORS[name]
            replacement = color_map.get(original_hex)
            if replacement:
                return prefix + replacement
            return prefix + original_hex
        return match.group(0)

    result = svg_text

    # Replace named colors in attribute values (fill="red" etc.)
    result = re.sub(
        r'((?:fill|stroke|stop-color|color)\s*=\s*["\']?)([a-zA-Z]+)(?=["\';\s/>])',
        replace_named_color, result
    )

    # Replace named colors in style properties (fill:red etc.)
    result = re.sub(
        r'((?:fill|stroke|stop-color|color)\s*:\s*)([a-zA-Z]+)(?=[;"\'])',
        replace_named_color, result
    )

    # Replace 6-digit hex
    result = re.sub(r'#([0-9a-fA-F]{6})(?![0-9a-fA-F])', replace_hex6, result)
    # Replace 3-digit hex
    result = re.sub(r'#([0-9a-fA-F]{3})(?![0-9a-fA-F])', replace_hex3, result)

    return result


def process_all():
    """Process all countries."""
    SVG_OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    log_rows = []
    stats = {
        "processed": 0,
        "skipped_no_svg": 0,
        "skipped_no_colors": 0,
        "colors_replaced": 0,
        "colors_kept": 0,
        "colors_exact": 0,
        "warnings": [],
    }

    # Gather all spec files
    spec_files = sorted(SPEC_DIR.glob("*.json"))

    for spec_path in spec_files:
        if spec_path.name == "schema.json":
            continue

        code = spec_path.stem
        spec = load_spec(code)
        if not spec:
            continue

        spec_colors = spec.get("colors", [])
        if not spec_colors:
            stats["skipped_no_colors"] += 1
            log_rows.append([code, spec.get("name_en", ""), "SKIP", "", "", "No color data"])
            continue

        svg_path = SVG_IN_DIR / f"{code}.svg"
        if not svg_path.exists():
            stats["skipped_no_svg"] += 1
            log_rows.append([code, spec.get("name_en", ""), "SKIP", "", "", "SVG not found"])
            continue

        # Read SVG
        with open(svg_path, encoding="utf-8") as f:
            svg_text = f.read()

        # Extract colors and build mapping
        svg_colors = extract_svg_colors(svg_text)
        color_map = build_color_map(svg_colors, spec_colors)

        # Apply recoloring
        recolored = recolor_svg(svg_text, color_map)

        # Write output
        out_path = SVG_OUT_DIR / f"{code}.svg"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(recolored)

        # Log details
        for svg_hex, mapped in color_map.items():
            if mapped is None:
                status = "KEPT (ΔE > threshold)"
                stats["colors_kept"] += 1
                msg = f"ΔE too large, original kept"
            elif mapped == svg_hex:
                status = "EXACT"
                stats["colors_exact"] += 1
                msg = "Already correct"
            else:
                status = "REPLACED"
                stats["colors_replaced"] += 1
                msg = ""
            log_rows.append([code, spec.get("name_en",""), status, svg_hex, mapped or svg_hex, msg])

        stats["processed"] += 1

    # Write CSV log
    with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["iso_alpha2", "name_en", "status", "original_hex", "new_hex", "note"])
        writer.writerows(log_rows)

    # Print summary
    print("=" * 60)
    print("  SVG Recolor Summary")
    print("=" * 60)
    print(f"  Processed:         {stats['processed']}")
    print(f"  Skipped (no SVG):  {stats['skipped_no_svg']}")
    print(f"  Skipped (no color):{stats['skipped_no_colors']}")
    print(f"  Colors replaced:   {stats['colors_replaced']}")
    print(f"  Colors exact:      {stats['colors_exact']}")
    print(f"  Colors kept (ΔE>): {stats['colors_kept']}")
    print("=" * 60)
    print(f"  Log saved to: {LOG_PATH}")
    print(f"  Output SVGs:  {SVG_OUT_DIR}/")


if __name__ == "__main__":
    process_all()
