#!/usr/bin/env python3
"""
build_indesign_csv.py – Phase 6: 書籍レイアウト用素材（DTPワークフローの整理）

Adobe InDesign の「データ結合 (Data Merge)」機能で利用できる総括マスターCSVを出力します。
画像の相対パスのカラム名は `@` で開始する必要があります（@AI_Image, @SVG_Image）。
あわせて、レイアウト用のインデックスファイル（五十音・アルファベット順）なども出力します。
"""

import json
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
MASTER_CSV = PROJECT_ROOT / "00_master" / "countries_master.csv"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
DOCS_DIR = PROJECT_ROOT / "06_docs"

INDESIGN_OUT = DOCS_DIR / "indesign_data_merge.csv"
INDEX_OUT = DOCS_DIR / "layout_index.csv"

def clean_text(text):
    if not text:
        return ""
    return text.strip()

def build_csvs():
    master = {}
    with open(MASTER_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            master[row['iso_alpha2']] = row

    data_rows = []

    for spec_path in sorted(SPEC_DIR.glob("*.json")):
        if spec_path.name == "schema.json":
            continue
            
        code = spec_path.stem
        
        ai_path = AI_DIR / f"{code}.ai"
        svg_path = SVG_DIR / f"{code}.svg"
        
        if not svg_path.exists():
            print(f"Skipping {code}: SVG missing.")
            continue
            
        rel_ai = f"../04_ai_cmyk/{code}.ai" if ai_path.exists() else ""
        rel_svg = f"../03_svg_verified/{code}.svg"
        
        with open(spec_path, encoding='utf-8') as f:
            spec = json.load(f)
            
        m = master.get(code, {})
        
        colors = spec.get("colors", [])
        color_texts = []
        for c in colors:
            cname = c.get("color_name", "Color")
            pantone = c.get("pantone", "").strip()
            cmyk = c.get("cmyk", "").strip()
            if pantone and pantone not in ("N. A.", "White", "Black"):
                color_texts.append(f"{cname}: {pantone}")
            elif cmyk and cmyk not in ("N. A.", "White", "Black"):
                color_texts.append(f"{cname}: CMYK {cmyk}")
            else:
                hex_val = c.get("hex", "")
                if hex_val:
                    color_texts.append(f"{cname}: {hex_val}")
        
        colors_summary = " / ".join(color_texts)
        
        entry = {
            "Code": code,
            "Name_JA": spec.get("name_ja", m.get("name_ja", "")),
            "Name_EN": spec.get("name_en", m.get("name_en", "")),
            "Ratio": spec.get("ratio", m.get("ratio", "")),
            "Region": m.get("un_m49_region", "Other"),
            "Subregion": m.get("un_m49_subregion", ""),
            "Status": spec.get("status", m.get("status", "")),
            "Colors_Summary": colors_summary,
            "Notes": clean_text(spec.get("notes", "")),
            "@AI_Image": rel_ai,
            "@SVG_Image": rel_svg
        }
        data_rows.append(entry)

    with open(INDESIGN_OUT, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ["Code", "Name_JA", "Name_EN", "Ratio", "Region", "Subregion", "Status", "Colors_Summary", "Notes", "@AI_Image", "@SVG_Image"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_rows)
        print(f"Generated InDesign Data Merge CSV: {INDESIGN_OUT.name} ({len(data_rows)} items)")

    sorted_by_en = sorted(data_rows, key=lambda x: x["Name_EN"])
    with open(INDEX_OUT, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "Code", "Name_EN", "Name_JA", "Region", "Ratio"])
        for i, row in enumerate(sorted_by_en, 1):
            writer.writerow([i, row["Code"], row["Name_EN"], row["Name_JA"], row["Region"], row["Ratio"]])
        print(f"Generated Layout Index CSV: {INDEX_OUT.name}")

if __name__ == "__main__":
    build_csvs()
