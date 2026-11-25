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

import errno
import os
import re
import stat
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
PROGRESS_LOG = PROJECT_ROOT / "04_ai_cmyk" / "logs" / "spot_to_process_done.txt"
JSX_PATH = PROJECT_ROOT / "temp_convert_spot.jsx"

SAFE_CODE = re.compile(r"[A-Za-z0-9_]{1,16}")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
_FILE_FLAGS = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def is_safe_code(code: str) -> bool:
    return SAFE_CODE.fullmatch(code) is not None


def _project_dir_fd(parts, create: bool) -> int:
    """PROJECT_ROOT 配下のディレクトリを、シンボリックリンクを辿らずに開く。"""
    fd = os.open(PROJECT_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
    except BaseException:
        os.close(fd)
        raise
    return fd


def open_project_file(path: Path, mode: str = "a", encoding: str = "utf-8"):
    """PROJECT_ROOT 配下のファイルを書き込み用に開く（mode は "w" か "a"）。

    パス上のシンボリックリンクは一切辿らない。ファイル名自体がリンク
    （シンボリックリンク／ハードリンク）の場合は、リンク先を開かずに
    名前だけを削除し、新しい通常ファイルを作成する。
    """
    *dirs, name = path.relative_to(PROJECT_ROOT).parts
    flags = os.O_WRONLY | os.O_CREAT | _FILE_FLAGS | (os.O_APPEND if mode == "a" else 0)
    dir_fd = _project_dir_fd(dirs, create=True)
    try:
        try:
            fd = os.open(name, flags, 0o644, dir_fd=dir_fd)
        except OSError as e:
            if e.errno != errno.ELOOP:
                raise
        else:
            st = os.fstat(fd)
            if stat.S_ISREG(st.st_mode) and st.st_nlink <= 1:
                if mode == "w":
                    os.ftruncate(fd, 0)
                return os.fdopen(fd, mode, encoding=encoding)
            os.close(fd)
        print(f"⚠️ {path} はリンクのため、通常ファイルに置き換えます", file=sys.stderr)
        os.unlink(name, dir_fd=dir_fd)
        fd = os.open(name, flags | os.O_EXCL, 0o644, dir_fd=dir_fd)
        return os.fdopen(fd, mode, encoding=encoding)
    finally:
        os.close(dir_fd)


def read_project_file(path: Path) -> str:
    """シンボリックリンクを辿らずに読む。存在しない・通常ファイルでない場合は空文字列。"""
    *dirs, name = path.relative_to(PROJECT_ROOT).parts
    try:
        dir_fd = _project_dir_fd(dirs, create=False)
        try:
            fd = os.open(name, os.O_RDONLY | _FILE_FLAGS, dir_fd=dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            return ""
        raise
    with os.fdopen(fd, encoding="utf-8") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            return ""
        return f.read()


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
    return set(read_project_file(PROGRESS_LOG).split())


def mark_done(code: str):
    """処理済みとしてログに追記"""
    if not is_safe_code(code):
        raise ValueError(f"unsafe country code: {code!r}")
    with open_project_file(PROGRESS_LOG, "a") as f:
        f.write(f"{code}\n")


def process_one(code: str, dry_run=False) -> str:
    """1ファイルを処理"""
    ai_path = AI_DIR / f"{code}.ai"
    if not ai_path.exists():
        return "SKIP_NOT_FOUND"
    
    if dry_run:
        return "DRY_RUN"
    
    # JSXを書き出す
    jsx_content = JSX_TEMPLATE.format(ai_path=str(ai_path.absolute()))
    with open_project_file(JSX_PATH, "w") as f:
        f.write(jsx_content)
    
    # Illustratorに実行させる
    cmd = [
        'osascript', '-e',
        f'tell application "Adobe Illustrator" to do javascript file POSIX file "{JSX_PATH.absolute()}"'
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
    
    unsafe = [c for c in codes if not is_safe_code(c)]
    if unsafe:
        print(f"⚠️ 不正なコードを除外: {unsafe!r}")
        codes = [c for c in codes if is_safe_code(c)]
    
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
    
    # 一時JSXファイルの掃除
    if JSX_PATH.exists() and not dry_run:
        JSX_PATH.unlink()


if __name__ == "__main__":
    main()
