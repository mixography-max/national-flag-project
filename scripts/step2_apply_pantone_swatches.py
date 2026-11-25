#!/usr/bin/env python3
"""
step2_apply_pantone_swatches.py – CMYK AIファイルにPantoneスウォッチを登録・適用（第2パス）

第1段階で生成された中間CMYK AIファイルを読み込み、
JSONスペックに基づいたPantoneスウォッチ（プロセスカラー指定）を作成して
タグ付けされたパスに適用し、パスの note をクリアします。

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
import stat
import sys
import subprocess
import time
import unicodedata
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
AI_OUT_DIR = PROJECT_ROOT / "04_ai_cmyk"
PROGRESS_LOG = AI_OUT_DIR / "logs" / "progress_step2.txt"
JSX_ERROR_LOG = AI_OUT_DIR / "logs" / "jsx_error_step2.log"

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


def hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def parse_cmyk(cmyk_str: str):
    if not cmyk_str or cmyk_str.strip() in ("", "N. A.", "N/A"):
        return (0, 0, 0, 0)
    parts = re.split(r'[-,\s]+', cmyk_str.strip())
    parts = [p for p in parts if p]
    if len(parts) == 4:
        try:
            return tuple(float(p) for p in parts)
        except ValueError:
            pass
    return (0, 0, 0, 0)


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


def generate_jsx(ai_path: Path, spec: dict):
    ai_rel = ai_path.relative_to(PROJECT_ROOT)
    ai_abs = f"/tmp/flag_project/{ai_rel}"
    
    color_specs = []
    for c in spec.get("colors", []):
        hex_str = c.get("hex", "#000000")
        rgb = hex_to_rgb(hex_str)
        pantone = c.get("pantone", "").strip()
        cmyk_vals = parse_cmyk(c.get("cmyk", ""))
        
        has_pantone = bool(pantone and pantone not in ("White", "", "N/A"))
        
        color_specs.append({
            "r": rgb[0],
            "g": rgb[1],
            "b": rgb[2],
            "pantone": pantone,
            "hasPantone": has_pantone,
            "c": cmyk_vals[0],
            "m": cmyk_vals[1],
            "y": cmyk_vals[2],
            "k": cmyk_vals[3]
        })
        
    color_specs_json = json.dumps(color_specs, indent=2)
    
    jsx = f"""try {{
    app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
    var doc = app.open(new File("{ai_abs}"));
    
    var initReady = false;
    for (var w = 0; w < 50; w++) {{
        try {{
            if (app.documents.length > 0) {{
                app.activeDocument = doc;
                var testItems = doc.pageItems;
                if (testItems && testItems.length >= 0) {{
                    initReady = true;
                    break;
                }}
            }}
        }} catch(e) {{}}
        $.sleep(100);
    }}
    if (!initReady) {{
        throw new Error("AI document initialization timed out");
    }}
    
    var colorSpecs = {color_specs_json};
    
    function hexToRgb(hex) {{
        hex = hex.replace("#", "");
        if (hex.length == 3) {{
            hex = hex[0]+hex[0] + hex[1]+hex[1] + hex[2]+hex[2];
        }}
        var num = parseInt(hex, 16);
        return {{
            r: (num >> 16) & 255,
            g: (num >> 8) & 255,
            b: num & 255
        }};
    }}
    
    function findMatchingColor(hexStr) {{
        var rgb = hexToRgb(hexStr);
        var minDistance = 999999;
        var bestMatch = null;
        for (var i = 0; i < colorSpecs.length; i++) {{
            var spec = colorSpecs[i];
            var dist = Math.abs(rgb.r - spec.r) + Math.abs(rgb.g - spec.g) + Math.abs(rgb.b - spec.b);
            if (dist < minDistance) {{
                minDistance = dist;
                bestMatch = spec;
            }}
        }}
        if (minDistance <= 24) {{
            return bestMatch;
        }}
        return null;
    }}
    
    var spotColorMappings = {{}};
    for (var i = 0; i < colorSpecs.length; i++) {{
        var spec = colorSpecs[i];
        if (spec.hasPantone) {{
            var spot = null;
            try {{
                spot = doc.spots.getByName(spec.pantone);
            }} catch(e) {{}}
            if (!spot) {{
                spot = doc.spots.add();
                spot.name = spec.pantone;
            }}
            spot.colorType = ColorModel.PROCESS;
            
            var cmyk = new CMYKColor();
            cmyk.cyan = spec.c;
            cmyk.magenta = spec.m;
            cmyk.yellow = spec.y;
            cmyk.black = spec.k;
            spot.color = cmyk;
            
            var sc = new SpotColor();
            sc.spot = spot;
            sc.tint = 100;
            spotColorMappings[spec.pantone] = sc;
        }}
    }}
    
    function createCMYK(spec) {{
        var cmyk = new CMYKColor();
        cmyk.cyan = spec.c;
        cmyk.magenta = spec.m;
        cmyk.yellow = spec.y;
        cmyk.black = spec.k;
        return cmyk;
    }}
    
    function applyColors(items) {{
        for (var i = 0; i < items.length; i++) {{
            var item = items[i];
            if (item.typename == "PathItem") {{
                if (item.note && item.note != "") {{
                    var parts = item.note.split(";");
                    for (var p = 0; p < parts.length; p++) {{
                        var tag = parts[p].split(":");
                        if (tag.length == 2) {{
                            var type = tag[0];
                            var hexVal = tag[1];
                            var spec = findMatchingColor(hexVal);
                            if (spec) {{
                                var colorVal;
                                if (spec.hasPantone) {{
                                    colorVal = spotColorMappings[spec.pantone];
                                }} else {{
                                    colorVal = createCMYK(spec);
                                }}
                                if (type == "fill") {{
                                    item.filled = true;
                                    item.fillColor = colorVal;
                                }} else if (type == "stroke") {{
                                    item.stroked = true;
                                    item.strokeColor = colorVal;
                                }}
                            }}
                        }}
                    }}
                    item.note = "";
                }}
            }} else if (item.typename == "GroupItem") {{
                applyColors(item.pageItems);
            }} else if (item.typename == "CompoundPathItem") {{
                applyColors(item.pathItems);
            }}
        }}
    }}
    
    applyColors(doc.pageItems);
    
    doc.save();
    doc.close(SaveOptions.DONOTSAVECHANGES);
    "SUCCESS";
}} catch(err) {{
    try {{ app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); }} catch(e2) {{}}
    "JSX_ERROR:" + err.toString();
}}"""
    return jsx


def process_country(code: str):
    ai_path = AI_OUT_DIR / f"{code}.ai"
    spec_path = SPEC_DIR / f"{code}.json"
    
    if not ai_path.exists():
        return "SKIP_NO_AI"
    if not spec_path.exists():
        return "SKIP_NO_SPEC"
        
    with open(spec_path, encoding='utf-8') as f:
        spec = json.load(f)
        
    jsx_content = generate_jsx(ai_path, spec)
    
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


def main():
    # Setup ASCII symlink
    if ASCII_ROOT.is_symlink() or ASCII_ROOT.exists():
        ASCII_ROOT.unlink()
    os.symlink(str(PROJECT_ROOT.absolute()), str(ASCII_ROOT))
    print(f"📁 ASCII symlink: {ASCII_ROOT} → {PROJECT_ROOT}")
    
    resume = "--resume" in sys.argv
    
    if "--all" in sys.argv:
        codes = [s.stem for s in sorted(SPEC_DIR.glob("*.json"))]
        print(f"Mode: ALL ({len(codes)} files)")
    elif "--codes" in sys.argv:
        idx = sys.argv.index("--codes")
        codes = [a for a in sys.argv[idx+1:] if not a.startswith("--")]
        print(f"Mode: SPECIFIC ({len(codes)} files)")
    else:
        # Default to all spec files
        codes = [s.stem for s in sorted(SPEC_DIR.glob("*.json"))]
        print(f"Mode: DEFAULT ({len(codes)} files)")
        
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
