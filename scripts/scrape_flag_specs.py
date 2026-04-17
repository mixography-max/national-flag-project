#!/usr/bin/env python3
import csv
import json
import os
import sys
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

# 設定
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "00_master" / "countries_master.csv"
OUTPUT_DIR = BASE_DIR / "02_official_specs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_wikipedia_wikitext(page_title: str) -> str:
    # URLエンコード
    safe_title = urllib.parse.quote(page_title)
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvslots=main&rvprop=content&titles={safe_title}&format=json"
    
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                if "missing" in page_info:
                    return ""
                revisions = page_info.get("revisions", [])
                if revisions:
                    slots = revisions[0].get("slots", {})
                    # Wikipedia API format
                    if "main" in slots:
                        return slots["main"].get("*", "")
                    elif "*" in revisions[0]:
                        return revisions[0]["*"]
    except Exception as e:
        print(f"Failed to fetch {page_title}: {e}")
    return ""

def extract_hex_colors(wikitext: str):
    """
    Wikitextから大まかに16進数カラーコードを抽出する簡易ロジック
    確実ではないがベースラインとして活用。
    """
    # {{Color box|#C8102E}} などのパターンや、html系の #FFFFFF などを探す
    matches = re.finditer(r'#([0-9a-fA-F]{6})\b', wikitext)
    found_colors = []
    seen = set()
    for m in matches:
        hex_code = m.group(1).upper()
        if hex_code not in seen:
            seen.add(hex_code)
            # 簡易的に色名を空で登録
            found_colors.append({
                "color_name": "",
                "hex": f"#{hex_code}",
                "rgb": "",
                "cmyk": "",
                "pantone": ""
            })
    return found_colors

def main():
    if not CSV_PATH.is_file():
        print(f"CSV not found: {CSV_PATH}")
        sys.exit(1)

    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iso2 = row.get("iso_alpha2", "")
            name_en = row.get("name_en", "")
            name_ja = row.get("name_ja", "")
            ratio = row.get("ratio", "")
            wiki_filename = row.get("wiki_flag_filename", "")
            
            if not iso2:
                continue
                
            out_path = OUTPUT_DIR / f"{iso2}.json"
            if out_path.exists():
                print(f"Skipping {iso2} (Already exists)")
                continue
                
            print(f"Processing {iso2} - {name_en}...")
            
            # wiki_filename (e.g. Flag_of_Japan.svg) からページ名を推測
            page_title = wiki_filename.replace(".svg", "")
            wikitext = get_wikipedia_wikitext(page_title)
            
            # 見つからなかった場合は "Flag of [Country]" で試す
            if not wikitext and "Flag_of_" not in page_title:
                wikitext = get_wikipedia_wikitext(f"Flag_of_{name_en.replace(' ', '_')}")
            
            extracted_colors = extract_hex_colors(wikitext) if wikitext else []
            
            # ratioの更新（Infoboxから取れることもあるが、一旦CSVのものを優先）
            # もしCSVがspecialやgolden ratioと表記していればそれを維持
            
            spec_data = {
                "iso_alpha2": iso2,
                "name_en": name_en,
                "name_ja": name_ja,
                "ratio": ratio,
                "specs_source": "",
                "colors_extracted": extracted_colors,
                "notes": "Generated baseline. Colors extracted via regex from Wikipedia." if extracted_colors else ""
            }
            
            with open(out_path, "w", encoding="utf-8-sig") as out_f:
                json.dump(spec_data, out_f, indent=2, ensure_ascii=False)
            
            time.sleep(1) # APIレートリミット回避

if __name__ == "__main__":
    main()
