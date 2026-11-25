#!/usr/bin/env python3
"""
step1_convert_svg_to_cmyk_ai.py – SVGをCMYKのAI形式へ単純変換（第1パス）

03_svg_verified のSVGを開き、パスの note プロパティに元のRGB値をタグ付けした上で、
新規作成したCMYKドキュメントに複製してAIファイルとして保存します。
これにより、Illustrator内部の executeMenuCommand バグを完全に回避します。

安全対策（illustrator_batch_safety ワークフロー準拠）:
- 1ファイルずつ処理
- 5件ごとに全ドキュメント強制クローズ + 5秒休止
- ファイル間に2秒の休止
- timeout=180
- 進捗ログによる中断・再開対応
- macOS NFD→NFCパス正規化
"""

import errno
import json
import os
import re
import stat
import sys
import subprocess
import time
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
AI_OUT_DIR = PROJECT_ROOT / "04_ai_cmyk"
PROGRESS_LOG = AI_OUT_DIR / "logs" / "progress_step1.txt"
JSX_ERROR_LOG = AI_OUT_DIR / "logs" / "jsx_error_step1.log"

ASCII_ROOT = Path("/tmp/flag_project")

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


def nfc(path_str: str) -> str:
    return unicodedata.normalize("NFC", path_str)


def close_all_documents():
    jsx = """
try {
    while (app.documents.length > 0) {
        app.documents[0].close(SaveOptions.DONOTSAVECHANGES);
    }
} catch(e) {}
"""
    jsx_path = PROJECT_ROOT / "temp_closeall.jsx"
    with open_project_file(jsx_path, "w", encoding="utf-8-sig") as f:
        f.write(jsx)
    cmd = [
        'osascript', '-e',
        f'tell application "Adobe Illustrator" to do javascript file POSIX file "{nfc(str(jsx_path.absolute()))}"'
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        pass


def generate_jsx(svg_path: Path, ai_path: Path):
    svg_rel = svg_path.relative_to(PROJECT_ROOT)
    ai_rel = ai_path.relative_to(PROJECT_ROOT)
    
    svg_abs = f"/tmp/flag_project/{svg_rel}"
    ai_abs = f"/tmp/flag_project/{ai_rel}"
    
    jsx = f"""try {{
    app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
    var svgDoc = app.open(new File("{svg_abs}"));
    
    // Document initialization wait loop
    var initReady = false;
    for (var w = 0; w < 50; w++) {{
        try {{
            if (app.documents.length > 0) {{
                app.activeDocument = svgDoc;
                var testItems = svgDoc.pageItems;
                if (testItems && testItems.length >= 0) {{
                    initReady = true;
                    break;
                }}
            }}
        }} catch(e) {{}}
        $.sleep(100);
    }}
    if (!initReady) {{
        throw new Error("SVG document initialization timed out");
    }}
    
    // Tag helper functions
    function rgbToHex(rgbColor) {{
        var r = rgbColor.red.toString(16);
        var g = rgbColor.green.toString(16);
        var b = rgbColor.blue.toString(16);
        if (r.length < 2) r = "0" + r;
        if (g.length < 2) g = "0" + g;
        if (b.length < 2) b = "0" + b;
        return "#" + r + g + b;
    }}
    
    // Recursive tag function for all path types
    function tagItem(item) {{
        if (item.typename == "PathItem") {{
            var tags = [];
            if (item.filled && item.fillColor) {{
                if (item.fillColor.typename == "RGBColor") {{
                    tags.push("fill:" + rgbToHex(item.fillColor));
                }} else if (item.fillColor.typename == "GrayColor") {{
                    var val = Math.round(255 - (item.fillColor.gray * 2.55));
                    var hex = val.toString(16);
                    if (hex.length < 2) hex = "0" + hex;
                    tags.push("fill:#" + hex + hex + hex);
                }}
            }}
            if (item.stroked && item.strokeColor) {{
                if (item.strokeColor.typename == "RGBColor") {{
                    tags.push("stroke:" + rgbToHex(item.strokeColor));
                }} else if (item.strokeColor.typename == "GrayColor") {{
                    var val = Math.round(255 - (item.strokeColor.gray * 2.55));
                    var hex = val.toString(16);
                    if (hex.length < 2) hex = "0" + hex;
                    tags.push("stroke:#" + hex + hex + hex);
                }}
            }}
            if (tags.length > 0) {{
                item.note = tags.join(";");
            }}
        }} else if (item.typename == "CompoundPathItem") {{
            for (var j = 0; j < item.pathItems.length; j++) {{
                tagItem(item.pathItems[j]);
            }}
        }} else if (item.typename == "GroupItem") {{
            for (var j = 0; j < item.pageItems.length; j++) {{
                tagItem(item.pageItems[j]);
            }}
        }}
    }}
    
    // Tag all items in svgDoc (recursive)
    for (var i = 0; i < svgDoc.pageItems.length; i++) {{
        tagItem(svgDoc.pageItems[i]);
    }}
    
    // Create new CMYK document with same dimensions
    var cmykDoc = app.documents.add(DocumentColorSpace.CMYK, svgDoc.width, svgDoc.height);
    
    // Layer by layer duplication to preserve groups and compound paths hierarchy
    for (var l = 0; l < svgDoc.layers.length; l++) {{
        var svgLayer = svgDoc.layers[l];
        var cmykLayer;
        if (l == 0) {{
            cmykLayer = cmykDoc.activeLayer;
            cmykLayer.name = svgLayer.name;
        }} else {{
            cmykLayer = cmykDoc.layers.add();
            cmykLayer.name = svgLayer.name;
        }}
        for (var i = 0; i < svgLayer.pageItems.length; i++) {{
            svgLayer.pageItems[i].duplicate(cmykLayer, ElementPlacement.PLACEATEND);
        }}
    }}
    
    // Save new CMYK doc as AI
    var saveFile = new File("{ai_abs}");
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    cmykDoc.saveAs(saveFile, saveOpts);
    
    cmykDoc.close(SaveOptions.DONOTSAVECHANGES);
    svgDoc.close(SaveOptions.DONOTSAVECHANGES);
    "SAVED_OK";
}} catch(err) {{
    try {{ app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); }} catch(e2) {{}}
    "JSX_ERROR:" + err.toString();
}}"""
    return jsx


def process_country(code: str):
    svg_path = SVG_DIR / f"{code}.svg"
    ai_path = AI_OUT_DIR / f"{code}.ai"
    spec_path = SPEC_DIR / f"{code}.json"
    
    if not svg_path.exists():
        return "SKIP_NO_SVG"
    if not spec_path.exists():
        return "SKIP_NO_SPEC"
        
    jsx_content = generate_jsx(svg_path, ai_path)
    
    jsx_path = PROJECT_ROOT / "temp_run.jsx"
    with open_project_file(jsx_path, "w") as f:
        f.write(jsx_content)
    
    jsx_ascii = str(ASCII_ROOT / "temp_run.jsx")
    cmd = [
        'osascript',
        '-e', 'tell application "Adobe Illustrator" to activate',
        '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_ascii}"'
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "ERROR_TIMEOUT"
        
    if "Error" in res.stderr or res.returncode != 0:
        return f"ERROR: {res.stderr.strip()[:100]}"
        
    stdout = res.stdout.strip()
    if "JSX_ERROR" in stdout:
        with open_project_file(JSX_ERROR_LOG, "w") as f:
            f.write(stdout.split("JSX_ERROR:", 1)[-1] + "\n")
        return f"ERROR_JSX: {stdout[:100]}"
        
    if ai_path.exists():
        import time as _t
        age = _t.time() - ai_path.stat().st_mtime
        if age > 60:
            return f"ERROR_NOT_SAVED: file not modified (age={age:.0f}s)"
    else:
        return "ERROR_NOT_SAVED: output file missing"
        
    return "SUCCESS"


def mark_done(code: str):
    if not is_safe_code(code):
        raise ValueError(f"unsafe country code: {code!r}")
    with open_project_file(PROGRESS_LOG, "a") as f:
        f.write(f"{code}\n")


def get_done_codes() -> set:
    return set(read_project_file(PROGRESS_LOG).split())


def get_codes_needing_update():
    codes = []
    for svg in sorted(SVG_DIR.glob("*.svg")):
        code = svg.stem
        ai = AI_OUT_DIR / f"{code}.ai"
        if not ai.exists() or svg.stat().st_mtime > ai.stat().st_mtime:
            codes.append(code)
    return codes


def main():
    AI_OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # ASCII-only symlink setup
    if ASCII_ROOT.is_symlink() or ASCII_ROOT.exists():
        ASCII_ROOT.unlink()
    os.symlink(str(PROJECT_ROOT.absolute()), str(ASCII_ROOT))
    print(f"📁 ASCII symlink: {ASCII_ROOT} → {PROJECT_ROOT}")
    
    # Parse arguments
    resume = "--resume" in sys.argv
    
    if "--all" in sys.argv:
        codes = [s.stem for s in sorted(SVG_DIR.glob("*.svg"))]
        print(f"Mode: ALL ({len(codes)} files)")
    elif "--codes" in sys.argv:
        idx = sys.argv.index("--codes")
        codes = [a for a in sys.argv[idx+1:] if not a.startswith("--")]
        print(f"Mode: SPECIFIC ({len(codes)} files)")
    else:
        codes = get_codes_needing_update()
        print(f"Mode: UPDATE ({len(codes)} files with newer SVGs)")
        
    unsafe = [c for c in codes if not is_safe_code(c)]
    if unsafe:
        print(f"⚠️ 不正なコードを除外: {unsafe!r}")
        codes = [c for c in codes if is_safe_code(c)]
        
    if resume:
        done = get_done_codes()
        before = len(codes)
        codes = [c for c in codes if c not in done]
        print(f"Resume: skipping {before - len(codes)} already-done, {len(codes)} remaining")
    else:
        open_project_file(PROGRESS_LOG, "w").close()
        
    if not codes:
        print("No files to process.")
        return
        
    total = len(codes)
    success = error = skip = 0
    errors_list = []
    
    for i, code in enumerate(codes, 1):
        print(f"[{i}/{total}] {code}...", end=" ", flush=True)
        
        status = process_country(code)
        
        if status == "SUCCESS":
            success += 1
            mark_done(code)
            print("✅")
        elif status.startswith("SKIP"):
            skip += 1
            mark_done(code)
            print(f"⏭️ {status}")
        else:
            error += 1
            errors_list.append(f"{code}: {status}")
            print(f"❌ {status}")
            
        if i < total:
            if i % 5 == 0:
                print(f"   🧹 5件完了 - 全ドキュメント強制クローズ + 5秒休止... ({i}/{total})")
                close_all_documents()
                time.sleep(5)
            else:
                time.sleep(2)
                
    close_all_documents()
    
    print("\n" + "=" * 50)
    print(f"Complete! ✅{success}  ❌{error}  ⏭️{skip}")
    if errors_list:
        print("\nErrors:")
        for e in errors_list:
            print(f"  {e}")
    print("=" * 50)


if __name__ == "__main__":
    main()
