#!/usr/bin/env python3
"""
mofa_verified.json（Playwright実取得）と mofa_countries.md の差分を比較し、
修正版 Markdown を生成する。
"""
import json, time
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "06_docs"
VERIFIED_JSON = OUT_DIR / "mofa_verified.json"
MD_PATH = OUT_DIR / "mofa_countries.md"

REGION_ORDER = ["アジア","大洋州","北米","中南米","欧州","中東","アフリカ"]

def load_verified():
    with open(VERIFIED_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_md(entries):
    """検証済みデータから Markdown を再生成"""
    # 地域順にソート
    entries.sort(key=lambda x: (
        REGION_ORDER.index(x["region"]) if x["region"] in REGION_ORDER else 99,
        x.get("slug", "")
    ))

    lines = []
    lines.append("# 外務省「国・地域」基礎データ一覧")
    lines.append("")
    lines.append("> **出典**: [外務省「国・地域」](https://www.mofa.go.jp/mofaj/area/index.html)  ")
    lines.append(f"> **収集日**: 2026-05-12（Playwright headed モードで実取得し検証済み）")
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

        # パイプ文字のエスケープ
        ja = ja.replace("|", "\\|")
        en = en.replace("|", "\\|")
        cap = cap.replace("|", "\\|")
        note = note.replace("|", "\\|")

        lines.append(f"| {idx} | {ja} | {en} | {cap} | {note} | {date} |")

    lines.append("")
    lines.append("---")
    lines.append("*このファイルは外務省ウェブサイトから Playwright で直接取得したデータに基づいて生成されました。*")
    lines.append(f"*生成スクリプト: `scripts/rebuild_md_from_verified.py`*")

    return "\n".join(lines)

def show_diffs(entries):
    """検証結果のサマリを表示"""
    print("=" * 70)
    print("検証結果サマリ")
    print("=" * 70)

    errors = [e for e in entries if "error" in e]
    if errors:
        print(f"\n❌ エラー: {len(errors)}件")
        for e in errors:
            print(f"  {e['slug']}: {e['error']}")

    # 首都が空のエントリ
    empty_capital = [e for e in entries if "error" not in e and not e.get("capital")]
    if empty_capital:
        print(f"\n⚠ 首都が空: {len(empty_capital)}件")
        for e in empty_capital:
            print(f"  {e['slug']}: capital_line_raw = {e.get('capital_line_raw','')}")

    # 正式名称が空のエントリ
    empty_name = [e for e in entries if "error" not in e and not e.get("formal_name_ja")]
    if empty_name:
        print(f"\n⚠ 正式名称（和文）が空: {len(empty_name)}件")
        for e in empty_name:
            print(f"  {e['slug']}: formal_line_raw = {e.get('formal_line_raw','')}, title = {e.get('page_title','')}")

    # 英語名が空
    empty_en = [e for e in entries if "error" not in e and not e.get("formal_name_en")]
    if empty_en:
        print(f"\n⚠ 正式名称（英語）が空: {len(empty_en)}件")
        for e in empty_en:
            print(f"  {e['slug']}: formal_line_raw = {e.get('formal_line_raw','')}")

    # raw データの一覧表示
    print(f"\n📋 全{len(entries)}件の取得データ:")
    for e in entries:
        if "error" in e:
            continue
        print(f"  {e['slug']:20s} | {e.get('formal_name_ja',''):30s} | {e.get('formal_name_en',''):40s} | {e.get('capital',''):15s} | {e.get('capital_note','')}")

if __name__ == "__main__":
    entries = load_verified()
    show_diffs(entries)
    md = generate_md(entries)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\n✅ Markdown再生成完了: {MD_PATH}")
