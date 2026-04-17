#!/usr/bin/env python3
"""
generate_specs_report.py

02_official_specs/*.json を全て読み込み、集計レポートを生成する。
"""

import json
from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parent.parent / "02_official_specs"
REPORT_PATH = Path(__file__).resolve().parent.parent / "06_docs" / "specs_report.md"


def main():
    json_files = sorted(SPECS_DIR.glob("*.json"))
    json_files = [f for f in json_files if f.name != "schema.json"]

    total = len(json_files)
    has_colors = 0
    has_source = 0
    has_both = 0
    has_pantone = 0
    has_cmyk = 0
    has_rgb = 0
    no_colors = []
    no_source_list = []
    full_list = []

    for jf in json_files:
        with open(jf, encoding="utf-8-sig") as f:
            data = json.load(f)

        iso2 = data.get("iso_alpha2", jf.stem)
        name_en = data.get("name_en", "")
        colors = data.get("colors", [])
        source = data.get("specs_source", "")

        c_ok = len(colors) > 0
        s_ok = bool(source)

        if c_ok:
            has_colors += 1
        else:
            no_colors.append(f"{iso2} ({name_en})")

        if s_ok:
            has_source += 1
        else:
            no_source_list.append(f"{iso2} ({name_en})")

        if c_ok and s_ok:
            has_both += 1

        # Pantone / CMYK / RGB カバレッジ
        any_pantone = any(c.get("pantone") for c in colors)
        any_cmyk = any(c.get("cmyk") for c in colors)
        any_rgb = any(c.get("rgb") for c in colors)
        if any_pantone:
            has_pantone += 1
        if any_cmyk:
            has_cmyk += 1
        if any_rgb:
            has_rgb += 1

        mark = "◎" if c_ok and s_ok else ("○" if c_ok else "△")
        full_list.append((iso2, name_en, len(colors), s_ok, mark))

    # レポート生成
    lines = []
    lines.append("# Phase 2: 公式規定 照合レポート\n")
    lines.append(f"生成日時: 自動生成\n")
    lines.append(f"## 概要\n")
    lines.append(f"| 項目 | 件数 | 率 |")
    lines.append(f"|---|---|---|")
    lines.append(f"| 対象総数 | {total} | 100% |")
    lines.append(f"| カラーデータ取得済み | {has_colors} | {has_colors*100//total}% |")
    lines.append(f"| 公式法源特定済み | {has_source} | {has_source*100//total}% |")
    lines.append(f"| 両方取得済み（◎） | {has_both} | {has_both*100//total}% |")
    lines.append(f"| Pantone値あり | {has_pantone} | {has_pantone*100//total}% |")
    lines.append(f"| CMYK値あり | {has_cmyk} | {has_cmyk*100//total}% |")
    lines.append(f"| RGB値あり | {has_rgb} | {has_rgb*100//total}% |")
    lines.append("")

    lines.append(f"## 凡例\n")
    lines.append(f"- ◎ カラーデータ ＋ 公式法源あり")
    lines.append(f"- ○ カラーデータのみ（法源は今後手動で調査が必要）")
    lines.append(f"- △ カラーデータなし（要手動調査）\n")

    lines.append(f"## カラーデータ未取得（△） — {len(no_colors)}件\n")
    lines.append("手動でのデータ追加が最優先で必要です。\n")
    for item in no_colors:
        lines.append(f"- {item}")
    lines.append("")

    lines.append(f"## 全カ国一覧（ABC順）\n")
    lines.append("| # | ISO | 国名 | 色数 | 法源 | 評価 |")
    lines.append("|---|---|---|---|---|---|")
    for i, (iso2, name_en, n_colors, s_ok, mark) in enumerate(full_list, 1):
        s_text = "✓" if s_ok else "—"
        lines.append(f"| {i} | {iso2} | {name_en} | {n_colors} | {s_text} | {mark} |")
    lines.append("")

    # 書き出し
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"レポートを生成しました: {REPORT_PATH}")
    print(f"  ◎ {has_both} / ○ {has_colors - has_both} / △ {total - has_colors}")


if __name__ == "__main__":
    main()
