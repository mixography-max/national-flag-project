#!/usr/bin/env python3
"""
enrich_flag_specs.py

既存の 02_official_specs/<ISO>.json を、Wikipediaの "Flag of [Country]" 記事から
より詳細な色仕様（色名、Pantone、CMYK、RGB、Hex）と公式出典を抽出して更新する。

処理順: name_en の ABC 順（全カ国均等に処理）
"""

import csv
import json
import os
import sys
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "00_master" / "countries_master.csv"
SPECS_DIR = BASE_DIR / "02_official_specs"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0.0.0 Safari/537.36")


def fetch_wikitext(page_title: str) -> str:
    """Wikipedia API から wikitext を取得"""
    safe = urllib.parse.quote(page_title.replace(" ", "_"))
    url = (f"https://en.wikipedia.org/w/api.php?"
           f"action=query&prop=revisions&rvslots=main&rvprop=content"
           f"&titles={safe}&format=json&formatversion=2")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            pages = data.get("query", {}).get("pages", [])
            if pages and "missing" not in pages[0]:
                revs = pages[0].get("revisions", [])
                if revs:
                    slots = revs[0].get("slots", {})
                    if "main" in slots:
                        return slots["main"].get("content", "")
    except Exception as e:
        print(f"  ⚠ Fetch error for '{page_title}': {e}")
    return ""


def strip_wikimarkup(s: str) -> str:
    """簡易的にWikiマークアップを除去"""
    s = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", s)  # [[link|text]] -> text
    s = re.sub(r"\{\{[^}]*\}\}", "", s)  # {{template}} 除去
    s = re.sub(r"'''?", "", s)  # bold/italic
    s = re.sub(r"<[^>]+>", "", s)  # HTML tags
    s = re.sub(r"&nbsp;", " ", s)
    return s.strip()


def parse_color_tables(wikitext: str) -> list:
    """
    Wikitextからカラー仕様テーブルを抽出する。
    典型パターン:
      {| class="wikitable"
      ! Color !! Pantone !! CMYK !! RGB !! Hex
      |-
      | White || ... || ... || ... || #FFFFFF
      |}
    """
    colors = []

    # wikitable ブロックを全て取得
    table_pattern = re.compile(
        r'\{\|[^\n]*wikitable[^\n]*\n(.*?)\|\}',
        re.DOTALL | re.IGNORECASE
    )

    for table_match in table_pattern.finditer(wikitext):
        table_content = table_match.group(1)

        # ヘッダー行を探す
        header_line = ""
        lines = table_content.split("\n")
        header_indices = {}

        for i, line in enumerate(lines):
            if line.startswith("!"):
                header_line = line
                # ヘッダーのカラムを解析
                cols = re.split(r'\s*!!\s*', header_line.lstrip("! "))
                cols = [strip_wikimarkup(c).strip().lower() for c in cols]
                for j, col in enumerate(cols):
                    if any(k in col for k in ["color", "colour", "name", "scheme"]):
                        header_indices["color_name"] = j
                    elif "pantone" in col:
                        header_indices["pantone"] = j
                    elif "cmyk" in col:
                        header_indices["cmyk"] = j
                    elif "rgb" in col:
                        header_indices["rgb"] = j
                    elif "hex" in col or "html" in col or "web" in col:
                        header_indices["hex"] = j
                break

        # カラー系のヘッダーが見つからなければこのテーブルはスキップ
        if not header_indices:
            continue
        # 少なくとも hex か pantone が含まれていればカラーテーブルと判断
        if "hex" not in header_indices and "pantone" not in header_indices:
            continue

        # データ行を解析
        row_data = []
        current_row = []
        for line in lines:
            line = line.strip()
            if line == "|-":
                if current_row:
                    row_data.append(current_row)
                current_row = []
            elif line.startswith("|") and not line.startswith("|+") and not line.startswith("|}"):
                # セルを分割
                cells = re.split(r'\s*\|\|\s*', line.lstrip("| "))
                current_row.extend(cells)
        if current_row:
            row_data.append(current_row)

        for row in row_data:
            if not row:
                continue
            entry = {
                "color_name": "",
                "hex": "",
                "rgb": "",
                "cmyk": "",
                "pantone": ""
            }
            for key, idx in header_indices.items():
                if idx < len(row):
                    val = strip_wikimarkup(row[idx]).strip()
                    # HEX値の正規化
                    if key == "hex":
                        m = re.search(r'#?([0-9a-fA-F]{6})', val)
                        if m:
                            val = f"#{m.group(1).upper()}"
                    entry[key] = val

            # 有効なエントリか判定（色名かHEXがあれば有効）
            if entry["color_name"] or entry["hex"]:
                colors.append(entry)

    return colors


def extract_official_source(wikitext: str) -> str:
    """WikitextからDesign/Specifications/Colours等のセクションを探し、公式法源を抽出"""
    sources = []

    # 法律・官報への言及パターン
    law_patterns = [
        r'(?:Law|Act|Decree|Constitution|Article|Section|Regulation|Standard|Order|Ordinance|Resolution|Loi|Ley|Gesetz|Lei)\s+(?:No\.?\s*)?[\w\d./\-]+(?:\s+of\s+\d{4})?',
        r'(?:BS|DIN|ISO|NCS|RAL|GOST|JIS|KS)\s*[\d:\-\.]+',
        r'(?:Federal|National|State|Government)\s+(?:Standard|Specification|Register)',
    ]

    # Design / Specifications / Colours / Colors セクションを探す
    section_pattern = re.compile(
        r'==+\s*(?:Design|Specifications?|Colou?rs?|Construction|Symbolism|Description)\s*==+(.*?)(?===|\Z)',
        re.DOTALL | re.IGNORECASE
    )

    for sec_match in section_pattern.finditer(wikitext):
        section_text = sec_match.group(1)
        for pat in law_patterns:
            for m in re.finditer(pat, section_text, re.IGNORECASE):
                found = strip_wikimarkup(m.group(0)).strip()
                if found and found not in sources and len(found) > 3:
                    sources.append(found)

    return "; ".join(sources[:5]) if sources else ""


def fallback_hex_extraction(wikitext: str) -> list:
    """テーブルパースに失敗した場合の最後の手段: Infobox系テンプレートやcolor boxからHEXを拾う"""
    colors = []
    seen = set()

    # {{Color box|#RRGGBB}} パターン
    for m in re.finditer(r'\{\{[Cc]olor\s*box\|#([0-9a-fA-F]{6})', wikitext):
        h = m.group(1).upper()
        if h not in seen:
            seen.add(h)
            colors.append({
                "color_name": "", "hex": f"#{h}",
                "rgb": "", "cmyk": "", "pantone": ""
            })

    # テーブル内の #RRGGBB（Infobox flag の colour1= 等）
    if not colors:
        for m in re.finditer(r'(?:colou?r\d?\s*=\s*|background[:\-]?\s*#)([0-9a-fA-F]{6})', wikitext, re.IGNORECASE):
            h = m.group(1).upper()
            if h not in seen:
                seen.add(h)
                colors.append({
                    "color_name": "", "hex": f"#{h}",
                    "rgb": "", "cmyk": "", "pantone": ""
                })

    return colors


def process_country(iso2, name_en, name_ja, ratio, wiki_filename):
    """1カ国分の処理"""
    out_path = SPECS_DIR / f"{iso2}.json"

    # 既存データを読み込み
    existing = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8-sig") as f:
            existing = json.load(f)

    # 既にenrichment済みならスキップ
    if existing.get("notes", "").startswith("Enriched"):
        print(f"  ✓ {iso2} ({name_en}) 既に照合済み — スキップ")
        return

    # Wikipedia ページタイトルの推定
    page_title = wiki_filename.replace(".svg", "").replace("_", " ")
    wikitext = fetch_wikitext(page_title)

    if not wikitext:
        # フォールバック: "Flag of [Country]"
        alt_title = f"Flag of {name_en}"
        wikitext = fetch_wikitext(alt_title)

    if not wikitext:
        print(f"  ✗ {iso2} ({name_en}) Wikipedia記事が取得できませんでした")
        spec = {
            "iso_alpha2": iso2,
            "name_en": name_en,
            "name_ja": name_ja,
            "ratio": ratio,
            "specs_source": "",
            "colors": [],
            "notes": "Enriched: Wikipedia article not found. Manual verification needed."
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        return

    # カラーテーブル解析
    colors = parse_color_tables(wikitext)

    # テーブルが見つからなかった場合のフォールバック
    if not colors:
        colors = fallback_hex_extraction(wikitext)

    # 公式出典の抽出
    source = extract_official_source(wikitext)

    # 結果の書き出し
    notes_parts = ["Enriched from Wikipedia."]
    if colors:
        notes_parts.append(f"{len(colors)} color(s) extracted from color table.")
    else:
        notes_parts.append("No structured color table found. Manual verification needed.")
    if source:
        notes_parts.append(f"Official source references found: {source}")

    spec = {
        "iso_alpha2": iso2,
        "name_en": name_en,
        "name_ja": name_ja,
        "ratio": ratio,
        "specs_source": source,
        "colors": colors,
        "notes": " ".join(notes_parts)
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    status = "◎" if colors and source else ("○" if colors else "△")
    print(f"  {status} {iso2} ({name_en}): {len(colors)} colors, source={'Yes' if source else 'No'}")


def main():
    if not CSV_PATH.is_file():
        print(f"❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    # CSV読み込み → name_en の ABC 順にソート
    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    rows.sort(key=lambda r: r.get("name_en", "").lower())

    print(f"=== Phase 2: 公式照合スクリプト ===")
    print(f"対象: {len(rows)} カ国/地域 (ABC順)")
    print()

    for i, row in enumerate(rows, 1):
        iso2 = row.get("iso_alpha2", "")
        name_en = row.get("name_en", "")
        name_ja = row.get("name_ja", "")
        ratio = row.get("ratio", "")
        wiki_fn = row.get("wiki_flag_filename", "")

        print(f"[{i:3d}/{len(rows)}] {name_en}")
        process_country(iso2, name_en, name_ja, ratio, wiki_fn)
        time.sleep(1.5)  # Wikipedia API レートリミット回避

    print()
    print("=== 完了 ===")


if __name__ == "__main__":
    main()
