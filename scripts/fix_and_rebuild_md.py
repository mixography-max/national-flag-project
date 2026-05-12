#!/usr/bin/env python3
"""
mofa_verified.json のパース問題を手動修正し、
全データの首都備考欄を整理して Markdown を再生成する。
"""
import json, re
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "06_docs"
VERIFIED_JSON = OUT_DIR / "mofa_verified.json"
MD_PATH = OUT_DIR / "mofa_countries.md"
REGION_ORDER = ["アジア","大洋州","北米","中南米","欧州","中東","アフリカ"]

# ── パース不備の手動修正テーブル ──
# 外務省 data.html の実際の記載に基づく
OVERRIDES = {
    # --- 正式名称の修正 ---
    "uk": {
        "formal_name_ja": "グレートブリテン及び北アイルランド連合王国（英国）",
        "formal_name_en": "United Kingdom of Great Britain and Northern Ireland",
    },

    # --- 首都の修正（パース誤りの手動修正） ---
    "singapore": {"capital": "シンガポール", "capital_note": "都市国家"},
    "easttimor":  {"capital": "ディリ", "capital_note": ""},
    "laos":       {"capital": "ビエンチャン", "capital_note": ""},
    "taiwan":     {"capital": "台北", "capital_note": ""},
    "vatican":    {"capital": "バチカン", "capital_note": "都市国家"},
    "monaco":     {"capital": "モナコ", "capital_note": "都市国家"},
    "plo":        {"capital": "", "capital_note": "外務省data.htmlに首都の記載なし"},
    "norway":     {"capital": "オスロ", "capital_note": ""},

    # --- 首都注記の整理（外務省サイト記載に基づく制度的注記のみ保持）---
    "eq_guinea":  {
        "capital": "シウダ・デ・ラ・パス",
        "capital_note": "2026年1月にマラボからの移転が宣言された。実質的首都機能は引き続きマラボ",
    },
    "tanzania":   {"capital_note": "法律上の首都。国会議事堂が置かれている"},
    "brundi":     {"capital_note": "経済の中心はブジュンブラ"},
    "netherlands":{"capital_note": "政治機能所在地はハーグ"},
    "bolivia":    {"capital_note": "憲法上の首都はスクレ"},
    "seychelles": {"capital_note": "マヘ島"},
    "cook":       {"capital_note": "ラロトンガ島"},
    "barbados":   {"capital_note": ""},
    "israel":     {"capital_note": "（注2）日本を含め多くの各国はテルアビブに大使館を置いている"},
}

# 備考から削除すべきパターン（首都に関する制度的注記以外）
NOTES_TO_CLEAR = {
    # 英語名のみ（地名の英語表記）
    "india", "bhutan", "argentine", "uzbekistan", "kyrgyz",
    "jordan", "eswatini", "ghana", "gabon", "cameroon",
    "gambia", "kenya", "cote_d", "comoros", "stp",
    "s_leone", "senegal", "chad", "togo", "nigeria",
    "niger", "burkina", "benin", "botswana", "madagascar",
    "mauritius", "liberia", "rwanda", "lesotho", "tajikistan",
    "turkmenistan",
    # 統計・人口・地理情報
    "australia", "spain", "sweden", "costarica", "zambia",
    "philippines", "n_korea",
}


def apply_overrides(entries):
    """手動修正を適用"""
    for entry in entries:
        slug = entry.get("slug", "")
        if slug in OVERRIDES:
            for k, v in OVERRIDES[slug].items():
                entry[k] = v

    # 備考クリーンアップ
    for entry in entries:
        slug = entry.get("slug", "")
        note = entry.get("capital_note", "")

        # 明示的にクリアすべきエントリ
        if slug in NOTES_TO_CLEAR:
            entry["capital_note"] = ""
            continue

        # 英語名のみの備考は削除
        if note and re.match(r'^[A-Za-z\s\'\-\.\,\(\)é]+$', note):
            entry["capital_note"] = ""

        # 「首都」の文字が残っている場合
        cap = entry.get("capital", "")
        if cap.startswith("首都"):
            entry["capital"] = cap.replace("首都", "").strip()

def generate_md(entries):
    """検証済みデータから Markdown を生成"""
    entries.sort(key=lambda x: (
        REGION_ORDER.index(x["region"]) if x["region"] in REGION_ORDER else 99,
        x.get("slug", "")
    ))

    lines = []
    lines.append("# 外務省「国・地域」基礎データ一覧")
    lines.append("")
    lines.append("> **出典**: [外務省「国・地域」](https://www.mofa.go.jp/mofaj/area/index.html)  ")
    lines.append("> **収集日**: 2026-05-12（Playwright headed モードで各国 data.html を実取得し検証済み）")
    lines.append("")
    valid = [e for e in entries if "error" not in e]
    lines.append(f"全 **{len(valid)}** カ国・地域")
    lines.append("")

    current_region = None
    idx = 0
    for entry in entries:
        if "error" in entry:
            continue

        region = entry["region"]
        if region != current_region:
            current_region = region
            n = sum(1 for e in entries if e.get("region") == region and "error" not in e)
            if idx > 0:
                lines.append("")
            lines.append(f"## {region}（{n}カ国・地域）")
            lines.append("")
            lines.append("| # | 正式名称（和文） | 正式名称（英語） | 首都 | 備考 | 最終更新日 |")
            lines.append("|--:|:--|:--|:--|:--|:--|")
            idx = 0

        idx += 1
        ja = entry.get("formal_name_ja", "")
        en = entry.get("formal_name_en", "")
        cap = entry.get("capital", "")
        note = entry.get("capital_note", "")
        date = entry.get("update_date", "")

        for field in [ja, en, cap, note]:
            field = field.replace("|", "\\|")

        lines.append(f"| {idx} | {ja} | {en} | {cap} | {note} | {date} |")

    lines.append("")
    lines.append("---")
    lines.append("*このファイルは外務省ウェブサイトから Playwright（headed モード）で直接取得したデータに基づいて生成されました。*  ")
    lines.append("*生成スクリプト: `scripts/fix_and_rebuild_md.py`*")

    return "\n".join(lines)

if __name__ == "__main__":
    with open(VERIFIED_JSON, "r", encoding="utf-8") as f:
        entries = json.load(f)

    print(f"読み込み: {len(entries)}件")
    apply_overrides(entries)

    # 修正後のサマリ
    problems = []
    for e in entries:
        if "error" in e:
            problems.append(f"  ❌ {e['slug']}: {e['error']}")
            continue
        if not e.get("formal_name_ja"):
            problems.append(f"  ⚠ {e['slug']}: 正式名称（和文）が空")
        if not e.get("formal_name_en"):
            problems.append(f"  ⚠ {e['slug']}: 正式名称（英語）が空")

    if problems:
        print("修正後の残存問題:")
        for p in problems:
            print(p)
    else:
        print("✅ 問題なし")

    md = generate_md(entries)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n✅ Markdown再生成完了: {MD_PATH}")
