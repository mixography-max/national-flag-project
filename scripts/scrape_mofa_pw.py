#!/usr/bin/env python3
"""
外務省ウェブサイトから国・地域の基礎データを Playwright で収集し、
JSON → Markdown テーブルに変換するスクリプト。

使い方:
  python3 scripts/scrape_mofa_pw.py          # 全工程実行
  python3 scripts/scrape_mofa_pw.py --md-only # JSON→MD変換のみ
"""

import json, re, time, sys, os
from pathlib import Path

# ── 定数 ──────────────────────────────────────────
BASE = "https://www.mofa.go.jp/mofaj/area"
OUT_DIR = Path(__file__).resolve().parent.parent / "06_docs"
JSON_PATH = OUT_DIR / "mofa_countries.json"
MD_PATH   = OUT_DIR / "mofa_countries.md"

REGIONS = {
    "アジア": [
        "india","indonesia","cambodia","singapore","srilanka",
        "thailand","korea","china","nepal","pakistan",
        "bangladesh","easttimor","philippines","bhutan","brunei",
        "vietnam","malaysia","myanmar","maldives","mongolia",
        "laos","n_korea","taiwan",
    ],
    "大洋州": [
        "australia","kiribati","cook","samoa","solomon",
        "tuvalu","tonga","nauru","niue","nz",
        "vanuatu","png","palau","fiji","marshall","micronesia",
    ],
    "北米": ["usa","canada"],
    "中南米": [
        "argentine","antigua","uruguay","ecuador","elsalvador",
        "guyana","cuba","guatemala","grenada","costarica",
        "colombia","jamaica","suriname","svg","scn",
        "s_lucia","chile","c_dominica","dominican_r","trinidad",
        "nicaragua","haiti","panama","bahama","paraguay",
        "barbados","brazil","venezuela","belize","peru",
        "bolivia","honduras","mexico",
    ],
    "欧州": [
        "iceland","ireland","azerbaijan","albania","armenia",
        "andorra","italy","ukraine","uzbekistan","uk",
        "estonia","austria","netherlands","kazakhstan","macedonia",
        "cyprus","greece","kyrgyz","croatia","kosovo",
        "sanmarino_r","georgia","switzerland","sweden","spain",
        "slovak","slovenia","serbia","tajikistan","czech",
        "denmark","germany","turkmenistan","norway","vatican",
        "hungary","finland","france","bulgaria","belarus",
        "belgium","poland","bosnia_h","portugal","malta",
        "monaco","moldova","montenegro","latvia","liechtenstein",
        "lithuania","romania","luxembourg","russia",
    ],
    "中東": [
        "afghanistan","uae","yemen","israel","iraq",
        "iran","oman","qatar","kuwait","saudi",
        "syria","turkey","bahrain","jordan","lebanon","plo",
    ],
    "アフリカ": [
        "algeria","angola","uganda","egypt","eswatini",
        "ethiopia","eritrea","ghana","capeverde","gabon",
        "cameroon","gambia","guinea","guinea_b","kenya",
        "cote_d","comoros","congokyo","congomin","stp",
        "zambia","s_leone","djibouti","zimbabwe","sudan",
        "seychelles","eq_guinea","senegal","somali","tanzania",
        "chad","car","tunisia","togo","nigeria",
        "namibia","niger","burkina","brundi","benin",
        "botswana","madagascar","malawi","mali","s_africa",
        "s_sudan","mozambique","mauritius","mauritania","morocco",
        "libya","liberia","rwanda","lesotho",
    ],
}

# ── JS: ページ上で実行してデータを抽出する ──────────
EXTRACT_JS = """
() => {
    const text = document.body.innerText;
    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
    const result = {lines_head: lines.slice(0, 60)};

    // 更新日: 「令和...」パターン
    const dateMatch = text.match(/令和\\d+年\\d+月\\d*日?/);
    result.update_date = dateMatch ? dateMatch[0] : '';

    // 正式名称行を探す: 「国名（英語名）」パターン（h2等の見出し直後）
    // data.html では「○○基礎データ」の後に正式名称が来る
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // 「1 主要産業」等の前に基礎情報がある
        if (/正式名称/.test(line) || /正式国名/.test(line)) {
            result.formal_line = line;
            // 次行も取得
            if (i + 1 < lines.length) result.formal_next = lines[i+1];
        }
        // 首都
        if (/^\\d*\\s*首都/.test(line) || line === '首都') {
            result.capital_line = line;
            if (i + 1 < lines.length) result.capital_next = lines[i+1];
            if (i + 2 < lines.length) result.capital_next2 = lines[i+2];
        }
    }

    // ページタイトルから国名を取得
    result.page_title = document.title;

    return JSON.stringify(result);
}
"""


def parse_entry(raw_json, slug, region):
    """JS抽出結果をパースして辞書に変換"""
    try:
        d = json.loads(raw_json)
    except Exception:
        return {"slug": slug, "region": region, "error": "JSON parse failed"}

    entry = {
        "slug": slug,
        "region": region,
        "url": f"{BASE}/{slug}/data.html",
        "update_date": d.get("update_date", ""),
    }

    lines = d.get("lines_head", [])

    # ── 正式名称（和文＋英語）──
    # パターン1: 「○○国（The ... of ...）」のような行
    formal_ja = ""
    formal_en = ""
    for line in lines:
        # 丸括弧内に英語名がある行を探す
        m = re.search(r'^(.+?)（((?:The |Republic |State |Kingdom |United |Federal |Plurinational |Co-operative |Democratic |Socialist |Islamic |Hashemite |Grand |Principality |Sultanate |Commonwealth |Independent ).+?)）', line)
        if not m:
            m = re.search(r'^(.+?)（([A-Z].+?)）', line)
        if m:
            formal_ja = m.group(1).strip()
            formal_en = m.group(2).strip()
            break

    # フォールバック: formal_line から取得
    if not formal_ja and d.get("formal_line"):
        fl = d["formal_line"]
        # 「正式名称　○○」のパターン
        m2 = re.sub(r'^正式名称\s*', '', fl).strip()
        if m2:
            formal_ja = m2

    entry["formal_name_ja"] = formal_ja
    entry["formal_name_en"] = formal_en

    # ── 首都 ──
    capital = ""
    capital_note = ""
    cap_line = d.get("capital_line", "")
    cap_next = d.get("capital_next", "")

    # 「3 首都　○○」のように同一行にある場合
    cap_text = re.sub(r'^\d*\s*首都\s*', '', cap_line).strip()
    if not cap_text:
        cap_text = cap_next

    if cap_text:
        # 括弧内の注記を分離
        # 例: 「ラパス（憲法上の首都はスクレ）」
        m3 = re.match(r'^([^（(]+?)(?:[（(](.+?)[）)])?$', cap_text)
        if m3:
            capital = m3.group(1).strip()
            if m3.group(2):
                note = m3.group(2).strip()
                # 人口情報は注記に含めない
                if not re.match(r'人口', note) and not re.match(r'\d', note):
                    capital_note = note
                elif '、' in note:
                    # 「人口...、注記」のパターン
                    parts = note.split('、')
                    for p in parts:
                        if not re.match(r'人口', p.strip()) and not re.match(r'\d', p.strip()):
                            capital_note = p.strip()
        else:
            capital = cap_text

    entry["capital"] = capital
    entry["capital_note"] = capital_note

    # ページタイトルからフォールバック国名
    title = d.get("page_title", "")
    if not formal_ja and title:
        entry["title_name"] = re.sub(r'[｜|].*$', '', title).replace("基礎データ", "").strip()

    return entry


def scrape_all():
    """Playwright で全国の data.html を巡回"""
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 既存データを読み込む（中断再開用）
    existing = {}
    if JSON_PATH.exists():
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            for item in json.load(f):
                existing[item["slug"]] = item

    results = list(existing.values())
    done_slugs = set(existing.keys())

    total = sum(len(v) for v in REGIONS.values())
    count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )

        for region, slugs in REGIONS.items():
            for slug in slugs:
                count += 1
                if slug in done_slugs:
                    print(f"  [{count}/{total}] {slug} … スキップ（取得済み）")
                    continue

                url = f"{BASE}/{slug}/data.html"
                print(f"  [{count}/{total}] {region} / {slug} …", end=" ", flush=True)

                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    if resp and resp.status == 200:
                        raw = page.evaluate(EXTRACT_JS)
                        entry = parse_entry(raw, slug, region)
                        results.append(entry)
                        done_slugs.add(slug)
                        print(f"OK  {entry.get('formal_name_ja','?')}")
                    else:
                        # data.html が無い場合は index.html を試す
                        url2 = f"{BASE}/{slug}/index.html"
                        resp2 = page.goto(url2, wait_until="domcontentloaded", timeout=20000)
                        if resp2 and resp2.status == 200:
                            raw = page.evaluate(EXTRACT_JS)
                            entry = parse_entry(raw, slug, region)
                            entry["url"] = url2
                            results.append(entry)
                            done_slugs.add(slug)
                            print(f"OK (index)  {entry.get('formal_name_ja','?')}")
                        else:
                            print(f"FAIL status={resp.status if resp else '?'}")
                            results.append({"slug": slug, "region": region, "error": f"HTTP {resp.status if resp else '?'}"})
                            done_slugs.add(slug)
                except Exception as e:
                    print(f"ERROR {e}")
                    results.append({"slug": slug, "region": region, "error": str(e)})
                    done_slugs.add(slug)

                # 中間保存（5件ごと）
                if count % 5 == 0:
                    with open(JSON_PATH, "w", encoding="utf-8") as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)

                time.sleep(0.5)  # サーバ負荷軽減

        browser.close()

    # 最終保存
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON保存完了: {JSON_PATH}  ({len(results)}件)")
    return results


def generate_md(results=None):
    """JSON から Markdown テーブルを生成"""
    if results is None:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            results = json.load(f)

    # 地域順にソート
    region_order = list(REGIONS.keys())
    results.sort(key=lambda x: (
        region_order.index(x["region"]) if x["region"] in region_order else 99,
        x.get("formal_name_ja", x.get("slug", ""))
    ))

    lines = []
    lines.append("# 外務省「国・地域」基礎データ一覧")
    lines.append("")
    lines.append(f"> 出典: [外務省「国・地域」]({BASE}/index.html)  ")
    lines.append(f"> 収集日: {time.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"全 **{len(results)}** カ国・地域")
    lines.append("")

    current_region = None
    for entry in results:
        region = entry.get("region", "不明")
        if region != current_region:
            current_region = region
            # 地域内の件数
            n = sum(1 for e in results if e.get("region") == region)
            lines.append(f"## {region}（{n}カ国・地域）")
            lines.append("")
            lines.append("| # | 正式名称（和文） | 正式名称（英語） | 首都 | 備考 | 最終更新日 |")
            lines.append("|--:|:--|:--|:--|:--|:--|")

        if "error" in entry:
            lines.append(f"| - | {entry['slug']} | - | - | ⚠ {entry['error']} | - |")
            continue

        idx = sum(1 for e in results
                  if e.get("region") == region
                  and e is not entry
                  and results.index(e) < results.index(entry)) + 1

        ja = entry.get("formal_name_ja") or entry.get("title_name") or entry["slug"]
        en = entry.get("formal_name_en", "")
        cap = entry.get("capital", "")
        note = entry.get("capital_note", "")
        date = entry.get("update_date", "")

        lines.append(f"| {idx} | {ja} | {en} | {cap} | {note} | {date} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*このファイルは `scripts/scrape_mofa_pw.py` により自動生成されました。*")

    md_text = "\n".join(lines)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"✅ Markdown保存完了: {MD_PATH}")


if __name__ == "__main__":
    if "--md-only" in sys.argv:
        generate_md()
    else:
        results = scrape_all()
        generate_md(results)
