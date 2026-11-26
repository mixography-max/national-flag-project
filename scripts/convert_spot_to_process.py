#!/usr/bin/env python3
"""
convert_spot_to_process.py – AIファイルのスポットカラーをプロセスカラーに変換

既存の04_ai_cmyk内のAIファイルを1つずつ開き、スウォッチの
カラータイプを「特色(Spot)」→「プロセスカラー(Process)」に変換して
上書き保存します。

★ メモリ安全設計:
  - 1ファイルずつ開く → 変換 → 保存 → 閉じる
  - 10ファイルごとに5秒の休止
  - 処理済みファイルをログに記録し、中断しても再開可能
  - --resume で前回の続きから再開

使い方:
  python3 scripts/convert_spot_to_process.py           # 全ファイル
  python3 scripts/convert_spot_to_process.py --resume   # 中断からの再開
  python3 scripts/convert_spot_to_process.py --codes JP US FR  # 指定のみ
  python3 scripts/convert_spot_to_process.py --dry-run  # 何をするか確認のみ
"""

import os
import sys
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
PROGRESS_LOG = PROJECT_ROOT / "04_ai_cmyk" / "logs" / "spot_to_process_done.txt"
# 旧バージョンが一時JSXを書き出していた場所。現在は書き込まず、残骸の削除のみ行う
JSX_PATH = PROJECT_ROOT / "temp_convert_spot.jsx"

# 1ファイル変換用のJSXテンプレート
# AI ファイルを開き、全Spotスウォッチの colorType を PROCESS に変え、
# 上書き保存して閉じる
JSX_TEMPLATE = r"""
try {{
    // Open the AI file
    var aiFile = new File("{ai_path}");
    var doc = app.open(aiFile);
    
    // Convert all spot colors to process colors
    var convertedCount = 0;
    for (var i = doc.spots.length - 1; i >= 0; i--) {{
        var spot = doc.spots[i];
        // Skip the built-in [Registration] spot
        if (spot.name === "[Registration]") continue;
        
        if (spot.colorType === ColorModel.SPOT) {{
            spot.colorType = ColorModel.PROCESS;
            convertedCount++;
        }}
    }}
    
    // Save in-place (overwrite)
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    doc.saveAs(aiFile, saveOpts);
    
    // CRITICAL: close the document to free memory
    doc.close(SaveOptions.DONOTSAVECHANGES);
    
    // Return result
    convertedCount.toString();
}} catch(err) {{
    // Try to close document even on error
    try {{ app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); }} catch(e2) {{}}
    "ERROR:" + err.toString();
}}
"""


def get_done_codes() -> set:
    """進捗ログから処理済みコード一覧を取得"""
    if not PROGRESS_LOG.exists():
        return set()
    return set(PROGRESS_LOG.read_text().strip().split("\n"))


def open_nofollow(path: Path, flags: int):
    """path を書き込み用に開く。path 自体や親ディレクトリがシンボリックリンクなら失敗する"""
    path.parent.mkdir(parents=True, exist_ok=True)
    dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | flags,
            0o644,
            dir_fd=dir_fd,
        )
    finally:
        os.close(dir_fd)
    return os.fdopen(fd, "w", encoding="utf-8")


def mark_done(code: str):
    """処理済みとしてログに追記"""
    with open_nofollow(PROGRESS_LOG, os.O_APPEND) as f:
        f.write(f"{code}\n")


def process_one(code: str, dry_run=False) -> str:
    """1ファイルを処理"""
    ai_path = AI_DIR / f"{code}.ai"
    if not ai_path.exists():
        return "SKIP_NOT_FOUND"
    
    if dry_run:
        return "DRY_RUN"
    
    jsx_content = JSX_TEMPLATE.format(ai_path=str(ai_path.absolute()))
    
    # JSXは本人だけが書き込める一時ディレクトリに新規作成する
    with tempfile.TemporaryDirectory(prefix="convert_spot_") as tmp_dir:
        jsx_path = Path(tmp_dir) / "temp_convert_spot.jsx"
        with open(jsx_path, "x", encoding="utf-8") as f:
            f.write(jsx_content)
        
        # Illustratorに実行させる
        cmd = [
            'osascript', '-e',
            f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"'
        ]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return "ERROR_TIMEOUT"
    
    output = res.stdout.strip()
    stderr = res.stderr.strip()
    
    if res.returncode != 0 or "ERROR:" in output:
        return f"ERROR: {output or stderr}"
    
    return f"OK (converted {output} spots)"


def main():
    # Parse arguments
    dry_run = "--dry-run" in sys.argv
    resume = "--resume" in sys.argv
    
    if "--codes" in sys.argv:
        idx = sys.argv.index("--codes")
        codes = sys.argv[idx + 1:]
    else:
        # 全AIファイルを対象
        codes = sorted(f.stem for f in AI_DIR.glob("*.ai"))
    
    if not codes:
        print("対象ファイルがありません。")
        return
    
    # --resume の場合、処理済みをスキップ
    if resume:
        done = get_done_codes()
        before = len(codes)
        codes = [c for c in codes if c not in done]
        print(f"📋 Resume mode: {before}ファイル中 {before - len(codes)}件は処理済み → 残り{len(codes)}件")
    else:
        # 新規実行時はログをリセット
        if PROGRESS_LOG.exists() and "--codes" not in sys.argv:
            PROGRESS_LOG.unlink()
    
    total = len(codes)
    if total == 0:
        print("✅ 全ファイル処理済みです！")
        return
    
    print(f"{'[DRY RUN] ' if dry_run else ''}SpotColor→ProcessColor 変換開始")
    print(f"対象: {total}ファイル")
    print(f"開始: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)
    
    success = error = skip = 0
    errors_list = []
    
    for i, code in enumerate(codes, 1):
        print(f"[{i}/{total}] {code}...", end=" ", flush=True)
        
        result = process_one(code, dry_run)
        
        if result.startswith("OK"):
            success += 1
            print(f"✅ {result}")
            if not dry_run:
                mark_done(code)
        elif result.startswith("SKIP"):
            skip += 1
            print(f"⏭️ {result}")
        elif result == "DRY_RUN":
            skip += 1
            print("🔍 (dry run)")
        else:
            error += 1
            errors_list.append(f"{code}: {result}")
            print(f"❌ {result}")
        
        # メモリ負荷対策: ファイル間の休止
        if not dry_run and i < total:
            if i % 10 == 0:
                # 10ファイルごとに長めの休止 (Illustratorのメモリ解放を待つ)
                print(f"   💤 10件完了 - 5秒休止中... ({i}/{total})")
                time.sleep(5)
            else:
                # 通常は2秒休止
                time.sleep(2)
    
    print("\n" + "=" * 50)
    print(f"完了! ✅{success}  ❌{error}  ⏭️{skip}")
    print(f"終了: {datetime.now().strftime('%H:%M:%S')}")
    if errors_list:
        print("\nエラー一覧:")
        for e in errors_list:
            print(f"  {e}")
    print("=" * 50)
    
    # 旧バージョンが残した一時JSXの掃除（リンクの場合もリンク先には触れない）
    if not dry_run:
        try:
            os.unlink(JSX_PATH)
        except OSError:
            pass


if __name__ == "__main__":
    main()
