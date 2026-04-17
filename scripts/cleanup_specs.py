#!/usr/bin/env python3
"""
cleanup_specs.py

02_official_specs/*.json のデータをクリーンアップする。
- Pantone値のゴミ文字除去 (\t\t\t• 等)
- specs_source のノイズ除去（短すぎるフレーズ、不完全な抽出の除去）
- "N. A." を空文字に統一
- cmyk "N. A." を空文字に統一
"""

import json
import re
from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parent.parent / "02_official_specs"

def clean_pantone(val: str) -> str:
    if not val:
        return ""
    # ゴミ文字除去: タブ、•、余分な空白
    val = re.sub(r'[\t•·]+', '', val).strip()
    # "N. A." → 空
    if val.upper() in ("N. A.", "N/A", "NA", "N.A.", "-", "—"):
        return ""
    return val

def clean_cmyk(val: str) -> str:
    if not val:
        return ""
    val = val.strip()
    if val.upper() in ("N. A.", "N/A", "NA", "N.A.", "-", "—"):
        return ""
    return val

def clean_source(val: str) -> str:
    if not val:
        return ""
    # セミコロンで分割して、各パーツを評価
    parts = [p.strip() for p in val.split(";")]
    cleaned = []
    for part in parts:
        # 短すぎるもの、意味のないフレーズを除外
        if len(part) < 5:
            continue
        # "order is", "law has", "constitution of" など不完全なフレーズを除外
        noise_patterns = [
            r'^(order|law|act|article|section|decree|constitution|standard)\s+(is|of|has|the|a|an|in|on|to|for|was|were|be|are|by|at)$',
            r'^(order|law|act)\s+(is|has|was)\b',
            r'^constitution of$',
        ]
        skip = False
        for pat in noise_patterns:
            if re.match(pat, part, re.IGNORECASE):
                skip = True
                break
        if not skip:
            cleaned.append(part)
    return "; ".join(cleaned) if cleaned else ""

def process_file(path: Path):
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    
    changed = False
    
    # colors のクリーンアップ
    for color in data.get("colors", []):
        old_p = color.get("pantone", "")
        new_p = clean_pantone(old_p)
        if old_p != new_p:
            color["pantone"] = new_p
            changed = True
        
        old_c = color.get("cmyk", "")
        new_c = clean_cmyk(old_c)
        if old_c != new_c:
            color["cmyk"] = new_c
            changed = True
    
    # specs_source のクリーンアップ
    old_s = data.get("specs_source", "")
    new_s = clean_source(old_s)
    if old_s != new_s:
        data["specs_source"] = new_s
        changed = True
    
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    return False

def main():
    json_files = sorted(SPECS_DIR.glob("*.json"))
    json_files = [f for f in json_files if f.name != "schema.json"]
    
    fixed_count = 0
    for jf in json_files:
        if process_file(jf):
            fixed_count += 1
    
    print(f"クリーンアップ完了: {fixed_count}/{len(json_files)} ファイルを修正")

if __name__ == "__main__":
    main()
