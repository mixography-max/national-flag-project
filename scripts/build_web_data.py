#!/usr/bin/env python3
"""
build_web_data.py – Phase 4: Webアトラス公開用データの構築

02_official_specs/*.json と 00_master/countries_master.csv からデータを抽出し、
05_web/flags_data.json を生成する。

- Extract: code, name_en, name_ja, ratio, region, subregion, status, colors
- New in Phase 4: notes, specs_source (with link autolinking), wiki_flag_filename
"""

import json
import csv
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
MASTER_CSV = PROJECT_ROOT / "00_master" / "countries_master.csv"
WEB_DATA_OUT = PROJECT_ROOT / "05_web" / "flags_data.json"

def process_links(text):
    """URL文字列をHTMLのaタグに変換する"""
    if not text:
        return ""
    # Simple URL to HTML link converter for specs_source
    url_pattern = re.compile(r'(https?://[^\s\)]+)')
    return url_pattern.sub(r'<a href="\1" target="_blank" rel="noopener noreferrer" class="source-link">\1</a>', text)

def build_data():
    master = {}
    with open(MASTER_CSV, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            master[row['iso_alpha2']] = row

    data = []
    
    # Enumerate all specified specs
    for spec_path in sorted(SPEC_DIR.glob("*.json")):
        if spec_path.name == "schema.json":
            continue
            
        code = spec_path.stem
        
        with open(spec_path, encoding='utf-8') as f:
            spec = json.load(f)
            
        m = master.get(code, {})
        
        entry = {
            "code": code,
            "name_en": spec.get("name_en", ""),
            "name_ja": spec.get("name_ja", ""),
            "ratio": spec.get("ratio", m.get("ratio", "")),
            "region": m.get("un_m49_region", "Other"),
            "subregion": m.get("un_m49_subregion", ""),
            "status": spec.get("status", m.get("status", "")),
            "colors": spec.get("colors", []),
            "specs_source": process_links(spec.get("specs_source", "")),
            "notes": spec.get("notes", ""),
            "wiki_flag_filename": m.get("wiki_flag_filename", "")
        }
        data.append(entry)
        
    WEB_DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(WEB_DATA_OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Generated web data for {len(data)} flags at {WEB_DATA_OUT}")

if __name__ == "__main__":
    build_data()
