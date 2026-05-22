#!/usr/bin/env python3
"""
検証済みSVG国旗から PNG を一括生成する。
rsvg-convert（librsvg）を使用。

ファイル名ルール:
  - 入力: 03_svg_verified/{CODE}.svg  (2文字略号)
  - 出力: png_flags/{SIZE}/{Name_EN}.png  (国名、スペース→アンダースコア)
  例: AD.svg → Andorra.png, US.svg → United_States.png

出力サイズ: 1080px, 640px（高さ固定、幅はアスペクト比に応じて自動）

使い方:
  python3 scripts/svg_to_png.py          # 全サイズ再生成
  python3 scripts/svg_to_png.py --size 1080  # 1080pxのみ
  python3 scripts/svg_to_png.py --size 640   # 640pxのみ
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SVG_DIR = BASE / "05_web" / "03_svg_verified"
PNG_BASE = BASE / "05_web" / "png_flags"
FLAGS_JSON = BASE / "05_web" / "flags_data.json"
COUNTRIES_JSON = BASE / "05_web" / "countries_data.json"

ALL_SIZES = {"1080": 1080, "640": 640}


def build_code_to_name():
    """flags_data.json + countries_data.json から code → name_en マッピングを構築"""
    mapping = {}

    # flags_data.json を優先
    if FLAGS_JSON.exists():
        with open(FLAGS_JSON, "r", encoding="utf-8") as f:
            for entry in json.load(f):
                code = entry.get("code", "")
                name_en = entry.get("name_en", "")
                if code and name_en:
                    mapping[code] = name_en

    # countries_data.json で補完
    if COUNTRIES_JSON.exists():
        with open(COUNTRIES_JSON, "r", encoding="utf-8") as f:
            for entry in json.load(f):
                code = entry.get("code", "")
                name_en = entry.get("name_en", "")
                if code and name_en and code not in mapping:
                    mapping[code] = name_en

    return mapping


def name_to_filename(name_en):
    """国名をファイル名に変換: スペース→アンダースコア"""
    return name_en.replace(" ", "_")


def check_rsvg():
    try:
        result = subprocess.run(
            ["rsvg-convert", "--version"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip().split(chr(10))[0]}")
            return True
    except FileNotFoundError:
        pass
    print("❌ rsvg-convert が見つかりません。brew install librsvg")
    return False


def convert_svg(svg_path, png_path, height):
    result = subprocess.run(
        ["rsvg-convert", "-h", str(height), str(svg_path), "-o", str(png_path)],
        capture_output=True, text=True
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="検証済みSVGからPNGを一括生成")
    parser.add_argument("--size", choices=["1080", "640"], help="生成するサイズ（省略時: 全サイズ）")
    args = parser.parse_args()

    if not check_rsvg():
        sys.exit(1)

    # マッピング構築
    code_to_name = build_code_to_name()
    print(f"📋 code→name_en マッピング: {len(code_to_name)}件")

    svgs = sorted(SVG_DIR.glob("*.svg"))
    print(f"📁 SVGファイル: {len(svgs)}件")

    sizes = {args.size: ALL_SIZES[args.size]} if args.size else ALL_SIZES

    for size_name, height in sizes.items():
        png_dir = PNG_BASE / size_name
        png_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📐 {size_name}px 生成開始（高さ={height}px）")

        success = 0
        errors = []
        unmapped = []

        for i, svg in enumerate(svgs, 1):
            code = svg.stem
            name_en = code_to_name.get(code)

            if not name_en:
                unmapped.append(code)
                continue

            filename = name_to_filename(name_en) + ".png"
            png_path = png_dir / filename

            if convert_svg(svg, png_path, height):
                success += 1
                if i % 50 == 0 or i == len(svgs):
                    print(f"  {i}/{len(svgs)} 完了…")
            else:
                errors.append(code)

        total_size = sum(f.stat().st_size for f in png_dir.glob("*.png"))
        print(f"\n✅ {size_name}px: {success}/{len(svgs)} 変換完了")
        print(f"   出力先: {png_dir}")
        print(f"   合計サイズ: {total_size / 1024 / 1024:.1f} MB")

        if unmapped:
            print(f"\n⚠ マッピングなし: {len(unmapped)}件: {', '.join(unmapped)}")
        if errors:
            print(f"\n❌ エラー: {len(errors)}件: {', '.join(errors)}")


if __name__ == "__main__":
    main()
