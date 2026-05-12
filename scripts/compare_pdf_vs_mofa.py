#!/usr/bin/env python3
"""
2025年5月PDF（国名・首都名検討会議資料）と
2026年5月の外務省最新データ（mofa_verified.json）を比較し、
変更点を抽出する。
"""
import fitz
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "06_docs"
PDF_PATH = BASE / "国名・首都名_20250528.pdf"
VERIFIED_JSON = BASE / "mofa_verified.json"


def parse_pdf():
    """PDFから国データをパース"""
    doc = fitz.open(str(PDF_PATH))
    all_text = ""
    for page in doc:
        all_text += page.get_text()
    doc.close()

    lines = all_text.split("\n")
    entries = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        # Tコードの行を探す（3桁の数字）
        if re.match(r'^\d{3}$', line):
            code = line
            # 次の行は国名
            name_ja = lines[i + 1].strip() if i + 1 < len(lines) else ""
            # その次は英語名
            name_en = lines[i + 2].strip() if i + 2 < len(lines) else ""
            # その次は首都名
            capital_raw = lines[i + 3].strip() if i + 3 < len(lines) else ""
            # その次は更新日
            update_raw = lines[i + 4].strip() if i + 4 < len(lines) else ""

            # 首都名に更新日が混じっている場合の処理
            # 例: "アルジェ" が欧文表記行末に入ってしまっている場合
            if re.match(r'令和', capital_raw):
                # 首都が英語名行に含まれている可能性
                # name_en の末尾に首都名がある場合
                parts = name_en.rsplit(" ", 1)
                if len(parts) == 2:
                    name_en = parts[0]
                    capital_raw = parts[1]
                    update_raw = lines[i + 3].strip() if i + 3 < len(lines) else ""
                    i += 4
                else:
                    i += 4
                    continue
            else:
                i += 5

            # 首都名から注記を分離
            capital = capital_raw
            capital_note = ""
            m = re.match(r'^(.+?)（(.+?)）(.*)$', capital_raw)
            if m:
                capital = m.group(1).strip()
                note_text = m.group(2).strip()
                rest = m.group(3).strip()
                if note_text and not re.match(r'注', note_text):
                    capital_note = note_text
                if rest:
                    capital_note = (capital_note + " " + rest).strip()
            # 「令和」で始まる部分を除去（更新日の混入）
            capital = re.sub(r'令和.*$', '', capital).strip()

            # 更新日の抽出
            update_date = ""
            um = re.search(r'令和\d+年\d+月\d+日', update_raw)
            if um:
                update_date = um.group(0)
            elif re.search(r'令和\d+年\d+月\d+日', capital_raw):
                um2 = re.search(r'令和\d+年\d+月\d+日', capital_raw)
                update_date = um2.group(0)

            entries.append({
                "code": code,
                "name_ja": name_ja,
                "name_en": name_en,
                "capital": capital,
                "capital_note": capital_note,
                "update_date": update_date,
            })
        else:
            i += 1

    return entries


def load_verified():
    """最新の外務省データを読み込む"""
    with open(VERIFIED_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize(s):
    """比較用に文字列を正規化"""
    s = s.strip()
    s = s.replace("　", " ")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("‐", "-").replace("–", "-")
    s = re.sub(r'\s+', ' ', s)
    return s


def compare(pdf_entries, verified_entries):
    """PDF と最新データを比較して変更点を抽出"""
    # PDFの英語名で最新データとマッチング
    verified_by_en = {}
    verified_by_ja = {}
    for v in verified_entries:
        if "error" in v:
            continue
        en = normalize(v.get("formal_name_en", ""))
        ja = normalize(v.get("formal_name_ja", ""))
        if en:
            verified_by_en[en] = v
        if ja:
            verified_by_ja[ja] = v

    changes = []
    unmatched_pdf = []

    for p in pdf_entries:
        p_en = normalize(p["name_en"])
        p_ja = normalize(p["name_ja"])

        # マッチング（英語名 → 和名の順で試行）
        v = verified_by_en.get(p_en)
        if not v:
            v = verified_by_ja.get(p_ja)
        if not v:
            # 部分一致を試行
            for key, val in verified_by_en.items():
                if key in p_en or p_en in key:
                    v = val
                    break
            if not v:
                for key, val in verified_by_ja.items():
                    if key in p_ja or p_ja in key:
                        v = val
                        break

        if not v:
            unmatched_pdf.append(p)
            continue

        # 比較
        diffs = []

        # 国名（和文）の比較
        v_ja = normalize(v.get("formal_name_ja", ""))
        if p_ja != v_ja:
            diffs.append(("正式名称（和文）", p_ja, v_ja))

        # 国名（英語）の比較
        v_en = normalize(v.get("formal_name_en", ""))
        if p_en != v_en:
            diffs.append(("正式名称（英語）", p_en, v_en))

        # 首都の比較
        p_cap = normalize(p["capital"])
        v_cap = normalize(v.get("capital", ""))
        if p_cap != v_cap:
            diffs.append(("首都", p_cap, v_cap))

        if diffs:
            changes.append({
                "slug": v.get("slug", "?"),
                "pdf_name": p["name_ja"],
                "mofa_name": v.get("formal_name_ja", ""),
                "diffs": diffs,
            })

    return changes, unmatched_pdf


if __name__ == "__main__":
    print("📄 PDFを解析中...")
    pdf_entries = parse_pdf()
    print(f"  PDF: {len(pdf_entries)}件")

    print("📋 最新外務省データを読み込み中...")
    verified = load_verified()
    valid = [e for e in verified if "error" not in e]
    print(f"  最新: {len(valid)}件")

    print("\n🔍 比較中...")
    changes, unmatched = compare(pdf_entries, valid)

    if changes:
        print(f"\n{'='*70}")
        print(f"🔄 変更あり: {len(changes)}件")
        print(f"{'='*70}")
        for c in changes:
            print(f"\n■ {c['pdf_name']}（{c['slug']}）")
            for field, old, new in c["diffs"]:
                print(f"  {field}:")
                print(f"    PDF（2025年5月）: {old}")
                print(f"    外務省（最新）  : {new}")
    else:
        print("\n✅ 変更なし")

    if unmatched:
        print(f"\n⚠ PDFにあるが最新データとマッチしなかったエントリ: {len(unmatched)}件")
        for u in unmatched:
            print(f"  {u['name_ja']} ({u['name_en']}) - 首都: {u['capital']}")
