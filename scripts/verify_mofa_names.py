#!/usr/bin/env python3
"""
外務省サイトから全国の正式名称・首都・更新日を直接取得し、
JSONファイルに保存するスクリプト（Playwright headed モード使用）
"""
import json, re, time, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(__file__).resolve().parent.parent / "06_docs"
JSON_PATH = OUT_DIR / "mofa_verified.json"

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

# ── JS: ページ内テキストから構造化データを抽出 ──
EXTRACT_JS = """
() => {
    const text = document.body.innerText;
    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

    let formalLine = '';
    let updateDate = '';
    let capitalLine = '';
    let capitalNext = '';

    for (let i = 0; i < Math.min(lines.length, 100); i++) {
        const line = lines[i];

        // 正式名称の行: 「○○（English Name）」パターン
        if (!formalLine) {
            // 全角括弧で英語名を含む行
            if (/（[A-Z]/.test(line) && /）/.test(line) && !/基礎データ/.test(line) && !/外務省/.test(line)) {
                formalLine = line;
            }
        }

        // 更新日
        if (!updateDate) {
            const m = line.match(/令和\\d+年\\d+月\\d*日?/);
            if (m) updateDate = m[0];
        }

        // 首都
        if (!capitalLine && /首都/.test(line)) {
            capitalLine = line;
            if (i + 1 < lines.length) capitalNext = lines[i + 1];
        }
    }

    return JSON.stringify({
        title: document.title,
        formalLine: formalLine,
        capitalLine: capitalLine,
        capitalNext: capitalNext,
        updateDate: updateDate,
        first20: lines.slice(0, 20)
    });
}
"""


def extract_from_page(page, slug, region):
    """1ページからデータを抽出"""
    url = f"https://www.mofa.go.jp/mofaj/area/{slug}/data.html"
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if not resp or resp.status != 200:
            # index.html にフォールバック
            url2 = f"https://www.mofa.go.jp/mofaj/area/{slug}/index.html"
            resp2 = page.goto(url2, wait_until="domcontentloaded", timeout=15000)
            if not resp2 or resp2.status != 200:
                return {"slug": slug, "region": region, "error": f"HTTP {resp.status if resp else '?'}"}
            url = url2

        raw = page.evaluate(EXTRACT_JS)
        d = json.loads(raw)

        # 正式名称をパース
        formal_line = d.get("formalLine", "")
        formal_ja = ""
        formal_en = ""
        if formal_line:
            m = re.match(r'^(.+?)（(.+?)）(.*)$', formal_line)
            if m:
                formal_ja = m.group(1).strip()
                formal_en = m.group(2).strip()
                # 残りの部分（追加の括弧等）があれば結合
                rest = m.group(3).strip()
                if rest:
                    formal_ja = formal_ja + "（" + formal_en + "）" + rest
                    # 再度パース
                    formal_ja = formal_line.split("（")[0].strip()
                    # 全体を保持
                    inner = re.findall(r'（(.+?)）', formal_line)
                    if inner:
                        formal_en = inner[0]
            else:
                formal_ja = formal_line

        # 首都をパース
        cap_line = d.get("capitalLine", "")
        cap_next = d.get("capitalNext", "")
        cap_text = re.sub(r'^\d*\s*首都\s*', '', cap_line).strip()
        if not cap_text:
            cap_text = cap_next

        capital = ""
        capital_note = ""
        if cap_text:
            # 括弧内を分離
            m2 = re.match(r'^([^（(]+)(?:[（(](.+?)[）)])?(.*)$', cap_text)
            if m2:
                capital = m2.group(1).strip()
                note_part = m2.group(2) or ""
                rest2 = m2.group(3) or ""
                # 人口情報はスキップ、注記のみ抽出
                if note_part and not re.match(r'[\d約]', note_part) and not note_part.startswith('人口'):
                    capital_note = note_part.strip()
                # rest に追加の注記がある場合
                if rest2:
                    extra_notes = re.findall(r'[（(](.+?)[）)]', rest2)
                    for en in extra_notes:
                        if not re.match(r'[\d約]', en) and not en.startswith('人口'):
                            capital_note = (capital_note + "；" + en).strip("；")
            else:
                capital = cap_text

        return {
            "slug": slug,
            "region": region,
            "url": url,
            "formal_line_raw": formal_line,
            "formal_name_ja": formal_ja,
            "formal_name_en": formal_en,
            "capital_line_raw": cap_text,
            "capital": capital,
            "capital_note": capital_note,
            "update_date": d.get("updateDate", ""),
            "page_title": d.get("title", ""),
            "first20": d.get("first20", []),
        }
    except Exception as e:
        return {"slug": slug, "region": region, "error": str(e)}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 既存データを読み込む（中断再開用）
    existing = {}
    if JSON_PATH.exists():
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            for item in json.load(f):
                if "error" not in item:
                    existing[item["slug"]] = item

    results = list(existing.values())
    done_slugs = set(existing.keys())

    total = sum(len(v) for v in REGIONS.values())
    count = 0
    new_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )

        for region, slugs in REGIONS.items():
            for slug in slugs:
                count += 1
                if slug in done_slugs:
                    print(f"  [{count}/{total}] {slug} … スキップ")
                    continue

                print(f"  [{count}/{total}] {region}/{slug} …", end=" ", flush=True)
                entry = extract_from_page(page, slug, region)

                if "error" in entry:
                    print(f"❌ {entry['error']}")
                else:
                    print(f"✅ {entry['formal_name_ja']} | {entry['capital']}")
                    new_count += 1

                results.append(entry)
                done_slugs.add(slug)

                # 10件ごとに中間保存
                if new_count % 10 == 0 and new_count > 0:
                    with open(JSON_PATH, "w", encoding="utf-8") as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)

                time.sleep(0.3)

        browser.close()

    # 最終保存
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 保存完了: {JSON_PATH}  ({len(results)}件, 新規{new_count}件)")


if __name__ == "__main__":
    main()
