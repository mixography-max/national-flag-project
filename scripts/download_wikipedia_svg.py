#!/usr/bin/env python3
"""
download_wikipedia_svg.py

このスクリプトは `00_master/countries_master.csv` を読み込み、各行の `wiki_flag_filename`
（例: Flag_of_Japan.svg）から Wikipedia Commons の SVG ファイルをダウンロードし、
`01_svg_wikipedia/<ISO_ALPHA2>.svg` に保存します。

- 既に同名ファイルが存在する場合はスキップします（上書きは行いません）。
- `01_svg_wikipedia` ディレクトリが存在しない場合は自動的に作成します。
- ダウンロード失敗（HTTP エラー等）はログに記録し、処理は続行します。
"""

import csv
import os
import sys
from pathlib import Path
import logging
import urllib.request
import urllib.error
import time

# 設定
BASE_DIR = Path(__file__).resolve().parent.parent  # プロジェクトルート
CSV_PATH = BASE_DIR / "00_master" / "countries_master.csv"
OUTPUT_DIR = BASE_DIR / "01_svg_wikipedia"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def ensure_output_dir():
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logging.info(f"出力ディレクトリを作成/確認: {OUTPUT_DIR}")
    except Exception as e:
        logging.error(f"ディレクトリ作成に失敗: {e}")
        sys.exit(1)


def download_svg(iso_alpha2: str, filename: str):
    # Wikipedia Commons のファイルパス URL を使用
    url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}"
    dest_path = OUTPUT_DIR / f"{iso_alpha2}.svg"
    if dest_path.exists():
        logging.info(f"既に存在するためスキップ: {dest_path.name}")
        return
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                dest_path.write_bytes(resp.read())
                logging.info(f"ダウンロード成功: {dest_path.name}")
                time.sleep(1.0)
            else:
                logging.warning(f"HTTP {resp.status} で失敗: {filename}")
                time.sleep(1.0)
    except urllib.error.HTTPError as e:
        logging.warning(f"HTTP {e.code} で失敗: {filename}")
        time.sleep(1.0)
    except Exception as e:
        logging.error(f"例外発生 ({filename}): {e}")
        time.sleep(1.0)


def main():
    ensure_output_dir()
    if not CSV_PATH.is_file():
        logging.error(f"CSV が見つかりません: {CSV_PATH}")
        sys.exit(1)
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iso_alpha2 = row.get("iso_alpha2") or row.get("iso_alpha2")
            wiki_filename = row.get("wiki_flag_filename")
            if not iso_alpha2 or not wiki_filename:
                logging.warning("必要なカラムが欠けています: %s", row)
                continue
            download_svg(iso_alpha2, wiki_filename)

if __name__ == "__main__":
    main()
