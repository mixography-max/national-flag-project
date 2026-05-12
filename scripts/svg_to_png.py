#!/usr/bin/env python3
"""
検証済みSVG国旗から PNG を一括生成する。
rsvg-convert（librsvg）を使用。高さ1080px固定。

出力: 05_web/png_flags/1080/

使い方:
  python3 scripts/svg_to_png.py
"""
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SVG_DIR = BASE / "05_web" / "03_svg_verified"
PNG_DIR = BASE / "05_web" / "png_flags" / "1080"

TARGET_HEIGHT = 1080


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
    if not check_rsvg():
        sys.exit(1)

    svgs = sorted(SVG_DIR.glob("*.svg"))
    print(f"📁 SVGファイル: {len(svgs)}件")
    print(f"📐 出力サイズ: h={TARGET_HEIGHT}px（幅はアスペクト比に応じて自動）")

    PNG_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    errors = []

    for i, svg in enumerate(svgs, 1):
        code = svg.stem
        png_path = PNG_DIR / f"{code}.png"

        if convert_svg(svg, png_path, TARGET_HEIGHT):
            success += 1
            if i % 50 == 0 or i == len(svgs):
                print(f"  {i}/{len(svgs)} 完了…")
        else:
            errors.append(code)

    total_size = sum(f.stat().st_size for f in PNG_DIR.glob("*.png"))
    print(f"\n✅ {success}/{len(svgs)} 変換完了")
    print(f"   出力先: {PNG_DIR}")
    print(f"   合計サイズ: {total_size / 1024 / 1024:.1f} MB")

    if errors:
        print(f"\n⚠ エラー: {len(errors)}件: {', '.join(errors)}")


if __name__ == "__main__":
    main()
