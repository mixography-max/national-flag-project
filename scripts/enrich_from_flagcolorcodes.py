#!/usr/bin/env python3
"""
enrich_from_flagcolorcodes.py

flagcolorcodes.com のページから各国の国旗カラー仕様を取得し、
02_official_specs/<ISO>.json を更新する。

取得項目: 色名, HEX, RGB, CMYK, Pantone(PMS), RAL
処理順: name_en の ABC 順
"""

import csv
import json
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from html.parser import HTMLParser

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "00_master" / "countries_master.csv"
SPECS_DIR = BASE_DIR / "02_official_specs"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0.0.0 Safari/537.36")

# name_en → flagcolorcodes.com の URL slug マッピング
# 多くは国名を小文字+ハイフンにすれば良いが、例外が多数ある
SLUG_OVERRIDES = {
    "Antigua and Barbuda": "antigua-and-barbuda",
    "Bosnia and Herzegovina": "bosnia-and-herzegovina",
    "Brunei": "brunei",
    "Cabo Verde": "cape-verde",
    "Central African Republic": "central-african-republic",
    "Congo": "republic-of-the-congo",
    "Côte d'Ivoire": "ivory-coast",
    "Czechia": "czech-republic",
    "DR Congo": "democratic-republic-of-the-congo",
    "Eswatini": "eswatini",
    "Gambia": "gambia",
    "Guinea-Bissau": "guinea-bissau",
    "Holy See": "vatican-city",
    "Iran": "iran",
    "Laos": "laos",
    "Moldova": "moldova",
    "Myanmar": "myanmar",
    "North Korea": "north-korea",
    "North Macedonia": "north-macedonia",
    "Palestine": "palestine",
    "Papua New Guinea": "papua-new-guinea",
    "Russia": "russia",
    "Saint Kitts and Nevis": "saint-kitts-and-nevis",
    "Saint Lucia": "saint-lucia",
    "Saint Vincent and the Grenadines": "saint-vincent-and-the-grenadines",
    "São Tomé and Príncipe": "sao-tome-and-principe",
    "Saudi Arabia": "saudi-arabia",
    "Sierra Leone": "sierra-leone",
    "Solomon Islands": "solomon-islands",
    "South Africa": "south-africa",
    "South Korea": "south-korea",
    "South Sudan": "south-sudan",
    "Sri Lanka": "sri-lanka",
    "Syria": "syria",
    "Timor-Leste": "east-timor",
    "Trinidad and Tobago": "trinidad-and-tobago",
    "Türkiye": "turkey",
    "United Arab Emirates": "uae",
    "United Kingdom": "uk",
    "United States": "usa",
    "Viet Nam": "vietnam",
}


def country_to_slug(name_en: str) -> str:
    """国名をflagcolorcodes.comのURLスラグに変換"""
    if name_en in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name_en]
    # 基本変換: 小文字化、スペース→ハイフン、特殊文字除去
    slug = name_en.lower()
    slug = re.sub(r'[àáâãä]', 'a', slug)
    slug = re.sub(r'[èéêë]', 'e', slug)
    slug = re.sub(r'[ìíîï]', 'i', slug)
    slug = re.sub(r'[òóôõö]', 'o', slug)
    slug = re.sub(r'[ùúûü]', 'u', slug)
    slug = re.sub(r'[ñ]', 'n', slug)
    slug = re.sub(r'[ç]', 'c', slug)
    slug = re.sub(r"[''`]", "", slug)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    return slug


class FlagColorParser(HTMLParser):
    """flagcolorcodes.com の HTML から色情報を抽出するパーサー"""

    def __init__(self):
        super().__init__()
        self.colors = []
        self.current_color_name = ""
        self.in_color_heading = False
        self.in_table = False
        self.in_td = False
        self.current_row_label = ""
        self.current_row_value = ""
        self.td_count = 0
        self.current_color_data = {}
        self.capture_text = False
        self.text_buffer = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "h3":
            self.in_color_heading = True
            self.text_buffer = ""
        if tag == "table":
            self.in_table = True
        if tag == "td":
            self.in_td = True
            self.td_count += 1
            self.text_buffer = ""

    def handle_endtag(self, tag):
        if tag == "h3" and self.in_color_heading:
            self.in_color_heading = False
            # "Red Color Codes" → "Red"
            m = re.match(r'(.+?)\s+Color\s+Codes', self.text_buffer.strip(), re.IGNORECASE)
            if m:
                # 新しい色のセクション開始
                if self.current_color_data and self.current_color_name:
                    self.current_color_data["color_name"] = self.current_color_name
                    self.colors.append(self.current_color_data)
                self.current_color_name = m.group(1).strip()
                self.current_color_data = {
                    "color_name": "", "hex": "", "rgb": "",
                    "cmyk": "", "pantone": ""
                }
        if tag == "td" and self.in_td:
            self.in_td = False
            val = self.text_buffer.strip()
            if self.td_count % 2 == 1:
                self.current_row_label = val.lower()
            else:
                self.current_row_value = val
                # ラベルに基づいてデータ格納
                if "hex" in self.current_row_label:
                    if not val.startswith("#"):
                        val = f"#{val}"
                    self.current_color_data["hex"] = val.upper() if val != "#" else ""
                elif "rgb" in self.current_row_label:
                    self.current_color_data["rgb"] = val
                elif "cmyk" in self.current_row_label:
                    self.current_color_data["cmyk"] = val
                elif "pantone" in self.current_row_label or "pms" in self.current_row_label:
                    self.current_color_data["pantone"] = val
        if tag == "table":
            self.in_table = False
            self.td_count = 0

    def handle_data(self, data):
        if self.in_color_heading or self.in_td:
            self.text_buffer += data

    def finalize(self):
        if self.current_color_data and self.current_color_name:
            self.current_color_data["color_name"] = self.current_color_name
            self.colors.append(self.current_color_data)
        return self.colors


def fetch_flag_colors(slug: str) -> list:
    """flagcolorcodes.com から色データを取得"""
    url = f"https://www.flagcolorcodes.com/{slug}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            parser = FlagColorParser()
            parser.feed(html)
            return parser.finalize()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        print(f"    ⚠ HTTP {e.code} for {slug}")
        return []
    except Exception as e:
        print(f"    ⚠ Error: {e}")
        return []


def fetch_wikipedia_source(wiki_filename: str, name_en: str) -> str:
    """Wikipedia API から公式法源を検索"""
    page_title = wiki_filename.replace(".svg", "").replace("_", " ")
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
                    wikitext = revs[0].get("slots", {}).get("main", {}).get("content", "")
                    return extract_source_from_wikitext(wikitext)
    except Exception:
        pass
    return ""


def extract_source_from_wikitext(wikitext: str) -> str:
    """Wikitextから公式法源の言及を抽出"""
    sources = []
    patterns = [
        r'(?:Law|Act|Decree|Constitution|Loi|Ley|Gesetz|Lei|Zakon)\s+(?:No\.?\s*)?[\w\d./\-]+(?:\s+of\s+\d{4})?',
        r'(?:BS|DIN|ISO|NCS|RAL|GOST|JIS|KS|AFNOR|NFX)\s*[\d:\-\.]+\w*',
        r'Executive\s+Order\s+\d+',
        r'Federal\s+Standard\s+\d+\w*',
    ]
    section_pat = re.compile(
        r'==+\s*(?:Design|Specifications?|Colou?rs?|Construction|Description)\s*==+(.*?)(?===|\Z)',
        re.DOTALL | re.IGNORECASE
    )
    for sec in section_pat.finditer(wikitext):
        text = sec.group(1)
        # wikiマークアップを簡易除去
        text = re.sub(r'\[\[([^|\]]*\|)?([^\]]*)\]\]', r'\2', text)
        text = re.sub(r'\{\{[^}]*\}\}', '', text)
        text = re.sub(r"'''?", '', text)
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                found = m.group(0).strip()
                if found and found not in sources and len(found) > 3:
                    sources.append(found)
    return "; ".join(sources[:3]) if sources else ""


def process_country(iso2, name_en, name_ja, ratio, wiki_filename, status):
    """1カ国分の処理"""
    out_path = SPECS_DIR / f"{iso2}.json"

    # 既存データを読み込んでenriched v2済みか確認
    if out_path.exists():
        with open(out_path, encoding="utf-8-sig") as f:
            existing = json.load(f)
        if existing.get("notes", "").startswith("Enriched v2"):
            print(f"  ✓ スキップ（照合済み）")
            return

    # 領土/海外地域でフランス国旗を使う場合はフランスのデータを参照
    if wiki_filename == "Flag_of_France.svg" and iso2 != "FR":
        slug = "france"
    else:
        slug = country_to_slug(name_en)

    # flagcolorcodes.com から色データ取得
    colors = fetch_flag_colors(slug)
    time.sleep(0.8)

    # Wikipedia から公式法源取得
    specs_source = fetch_wikipedia_source(wiki_filename, name_en)
    time.sleep(0.8)

    # 結果組み立て
    notes_parts = ["Enriched v2."]
    if colors:
        notes_parts.append(f"{len(colors)} color(s) from flagcolorcodes.com.")
    else:
        notes_parts.append("Color data not found on flagcolorcodes.com.")
    if specs_source:
        notes_parts.append(f"Legal refs: {specs_source}")
    else:
        notes_parts.append("No official source identified yet.")

    spec = {
        "iso_alpha2": iso2,
        "name_en": name_en,
        "name_ja": name_ja,
        "status": status,
        "ratio": ratio,
        "specs_source": specs_source,
        "colors": colors if colors else [],
        "notes": " ".join(notes_parts)
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    mark = "◎" if colors and specs_source else ("○" if colors else "△")
    print(f"  {mark} {len(colors)} colors, source={'Yes' if specs_source else 'No'}")


def main():
    if not CSV_PATH.is_file():
        print(f"❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    # ABC順（name_en）でソート
    rows.sort(key=lambda r: r.get("name_en", "").lower())

    print(f"=== Phase 2 v2: 公式照合（flagcolorcodes.com + Wikipedia法源） ===")
    print(f"対象: {len(rows)} カ国/地域 (ABC順)\n")

    for i, row in enumerate(rows, 1):
        iso2 = row.get("iso_alpha2", "")
        name_en = row.get("name_en", "")
        name_ja = row.get("name_ja", "")
        ratio = row.get("ratio", "")
        wiki_fn = row.get("wiki_flag_filename", "")
        status = row.get("status", "")

        print(f"[{i:3d}/{len(rows)}] {name_en} ({iso2})")
        process_country(iso2, name_en, name_ja, ratio, wiki_fn, status)

    print("\n=== 完了 ===")


if __name__ == "__main__":
    main()
