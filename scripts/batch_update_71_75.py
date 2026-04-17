#!/usr/bin/env python3
"""Batch update flag spec JSON files for countries 71-75 (FJ, FK, FM, FO, FR)."""
import json
import os

BASE = "/Users/r-site/Library/CloudStorage/GoogleDrive-r-site@yamakawa.co.jp/マイドライブ/国旗プロジェクト/02_official_specs"

updates = {
    "FJ.json": {
        "specs_source": "De facto (Standard Vexillological Approximations)",
        "colors": [
            {"color_name": "Light Blue", "hex": "#68BBE3", "rgb": "104, 187, 227", "cmyk": "54, 0, 0, 0", "pantone": "2915 C"},
            {"color_name": "Dark Blue", "hex": "#002868", "rgb": "0, 40, 104", "cmyk": "100, 81, 0, 45", "pantone": "281 C"},
            {"color_name": "Red", "hex": "#CE1126", "rgb": "206, 17, 38", "cmyk": "0, 92, 82, 0", "pantone": "186 C"},
            {"color_name": "White", "hex": "#FFFFFF", "rgb": "255, 255, 255", "cmyk": "0, 0, 0, 0", "pantone": "White"},
            {"color_name": "Yellow", "hex": "#FCD116", "rgb": "252, 209, 22", "cmyk": "0, 6, 94, 0", "pantone": "109 C"},
            {"color_name": "Green", "hex": "#007A33", "rgb": "0, 122, 51", "cmyk": "93, 0, 100, 28", "pantone": "355 C"},
        ],
        "notes": "Officially verified. No government-mandated Pantone/CMYK specifications exist. The flag is based on the British Blue Ensign with the national coat of arms. Standard vexillological approximations (2915 C for the light blue field, 281 C for the Union Jack dark blue, 186 C for red) are cited as De facto."
    },
    "FK.json": {
        "specs_source": "De facto (Standard British Ensign Approximations)",
        "notes": "Officially verified. As a British Overseas Territory, the flag follows the British Blue Ensign convention. No specific territorial color statute exists. Standard British ensign colors (281 C for dark blue, 186 C for red) are applied as De facto."
    },
    "FM.json": {
        "specs_source": "De facto (Standard Vexillological Approximations)",
        "colors": [
            {"color_name": "Blue", "hex": "#6CACE4", "rgb": "108, 172, 228", "cmyk": "27, 13, 0, 9", "pantone": "277 C"},
            {"color_name": "White", "hex": "#FFFFFF", "rgb": "255, 255, 255", "cmyk": "0, 0, 0, 0", "pantone": "White"},
        ],
        "notes": "Officially verified. The law describes a blue field with four white stars but does not define exact color formulas. The blue is inspired by the UN flag blue. Pantone 277 C is the most common international reference, adopted as De facto."
    },
    "FO.json": {
        "specs_source": "De jure (Official Faroese Flag Regulations)",
        "notes": "Officially verified. The official Faroese flag (Merkið) colors are defined as Pantone 032 C (Red) and Pantone 300 C (Blue), as referenced by the Nordic Council (norden.org) and official Faroese government sources."
    },
    "FR.json": {
        "specs_source": "De jure (Album des Pavillons 2023)",
        "notes": "Officially verified. The French Navy's Album des Pavillons (2023 edition) specifies Pantone 2738 C (Blue) and Pantone 2347 C (Red) as the official flag colors. These represent the current standard replacing historical darker shades."
    },
}

for filename, update_data in updates.items():
    filepath = os.path.join(BASE, filename)
    if not os.path.exists(filepath):
        print(f"  SKIP: {filepath} not found")
        continue

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Update specs_source
    data["specs_source"] = update_data["specs_source"]

    # Update colors if provided
    if "colors" in update_data:
        data["colors"] = update_data["colors"]
    else:
        # Just format existing pantone values
        for color in data.get("colors", []):
            p = color.get("pantone", "")
            # Remove noise characters
            p = p.replace("!", "").replace("✓", "").replace("N. A.", "White").strip()
            # Add " C" suffix if it's a number-only pantone
            if p and p not in ("White", "Black", "Black C", "White C") and not p.endswith(" C") and not p.endswith(" U"):
                p = p + " C"
            # Ensure Black gets " C"
            if p == "Black":
                p = "Black C"
            if p == "":
                if color.get("color_name", "").lower() == "white":
                    p = "White"
            color["pantone"] = p

    # Update notes
    data["notes"] = update_data["notes"]

    # Write back
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"  OK: {filename} updated")

print("\nAll 5 files processed.")
