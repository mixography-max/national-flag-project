#!/usr/bin/env python3
"""
batch_ai_cmyk_update.py – SVG変更を反映してAIファイルを再生成

03_svg_verified のSVGが 04_ai_cmyk のAIより新しいファイルのみ処理。
Adobe Illustratorをosascript経由で自動制御します。

安全対策（illustrator_batch_safety ワークフロー準拠）:
- 1ファイルずつ開いて閉じる（doc.close 必須）
- 5件ごとに全ドキュメント強制クローズ + 5秒休止
- ファイル間に2秒の休止
- timeout=180でフリーズ対策
- 進捗ログで中断・再開対応
- macOS NFD→NFC正規化でパスの濁点問題回避

使い方:
  python3 scripts/batch_ai_cmyk_update.py          # 変更分のみ
  python3 scripts/batch_ai_cmyk_update.py --all     # 全ファイル再生成
  python3 scripts/batch_ai_cmyk_update.py --codes AF QA CH  # 指定コードのみ
  python3 scripts/batch_ai_cmyk_update.py --resume  # 前回の続きから
"""

import json
import os
import sys
import subprocess
import time
import unicodedata
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
AI_OUT_DIR = PROJECT_ROOT / "04_ai_cmyk"
PROGRESS_LOG = AI_OUT_DIR / "logs" / "progress.txt"

# ASCII-only symlink to avoid ExtendScript's non-ASCII path issues
# macOS + ExtendScript は日本語パスを正しく処理できないため、
# ASCII-onlyのシンボリックリンク経由でアクセスする
ASCII_ROOT = Path("/tmp/flag_project")


def nfc(path_str: str) -> str:
    """macOS NFD → NFC 正規化。
    macOS (APFS/HFS+) はファイルパスをNFD（分解形）で保持するため、
    「プ」が「フ」+「゚」に分解され、osascript/Illustrator に渡す際に
    エスケープやパース失敗の原因になる。NFC（合成形）に統一する。
    """
    return unicodedata.normalize("NFC", path_str)


def hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def parse_cmyk(cmyk_str: str):
    """Parse '100-80-0-20' or '100, 80, 0, 20' into (C, M, Y, K)"""
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
    """Illustrator の全ドキュメントを強制クローズする。メモリ解放用。"""
    jsx = """
try {
    while (app.documents.length > 0) {
        app.documents[0].close(SaveOptions.DONOTSAVECHANGES);
    }
} catch(e) {}
"""
    jsx_path = PROJECT_ROOT / "temp_closeall.jsx"
    with open(jsx_path, "wb") as f:
        f.write(b'\xef\xbb\xbf')
        f.write(jsx.encode('utf-8'))
    cmd = [
        'osascript', '-e',
        f'tell application "Adobe Illustrator" to do javascript file POSIX file "{nfc(str(jsx_path.absolute()))}"'
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        pass


def generate_jsx(svg_path: Path, ai_path: Path, spec: dict):
    # ASCII-only symlink 経由のパスを使用（ExtendScript非ASCII対策）
    svg_rel = svg_path.relative_to(PROJECT_ROOT)
    ai_rel = ai_path.relative_to(PROJECT_ROOT)
    svg_abs = str(ASCII_ROOT / svg_rel)
    ai_abs = str(ASCII_ROOT / ai_rel)

    lines = []
    lines.append(f'try {{')
    lines.append(f'  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;')
    lines.append(f'  var doc = app.open(new File("{svg_abs}"));')
    
    # Use "colors" key (not "colors_extracted")
    colors = spec.get("colors", spec.get("colors_extracted", []))
    
    lines.append(f'  var colorMappings = [];')
    
    for i, c in enumerate(colors):
        rgb = hex_to_rgb(c.get("hex", "#000000"))
        cmyk_vals = parse_cmyk(c.get("cmyk", ""))
        
        # Use pure CMYKColor (SpotColor causes MRAP errors on RGB documents)
        lines.append(f'  var cmyk_{i} = new CMYKColor();')
        lines.append(f'  cmyk_{i}.cyan = {cmyk_vals[0]};')
        lines.append(f'  cmyk_{i}.magenta = {cmyk_vals[1]};')
        lines.append(f'  cmyk_{i}.yellow = {cmyk_vals[2]};')
        lines.append(f'  cmyk_{i}.black = {cmyk_vals[3]};')
            
        lines.append(f'  colorMappings.push({{')
        lines.append(f'      targetR: {rgb[0]}, targetG: {rgb[1]}, targetB: {rgb[2]},')
        lines.append(f'      replColor: cmyk_{i}')
        lines.append(f'  }});')

    lines.append('''
  // Single-pass: match RGB colors and apply CMYK/Spot colors directly.
  // Note: executeMenuCommand('doc-color-cmyk') fails under osascript automation
  // ("there is no document" error). Instead, we apply CMYK colors directly
  // to the RGB document. Illustrator handles the conversion on saveAs.
  function applyColorsDirectly(items) {
      for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item.typename == "PathItem") {
              if (item.filled && item.fillColor && item.fillColor.typename == "RGBColor") {
                  var r = item.fillColor.red;
                  var g = item.fillColor.green;
                  var b = item.fillColor.blue;
                  for (var c = 0; c < colorMappings.length; c++) {
                      var mapping = colorMappings[c];
                      if (Math.abs(r - mapping.targetR) <= 8 && 
                          Math.abs(g - mapping.targetG) <= 8 && 
                          Math.abs(b - mapping.targetB) <= 8) {
                          item.fillColor = mapping.replColor;
                          break;
                      }
                  }
              }
              if (item.stroked && item.strokeColor && item.strokeColor.typename == "RGBColor") {
                  var r = item.strokeColor.red;
                  var g = item.strokeColor.green;
                  var b = item.strokeColor.blue;
                  for (var c = 0; c < colorMappings.length; c++) {
                      var mapping = colorMappings[c];
                      if (Math.abs(r - mapping.targetR) <= 8 && 
                          Math.abs(g - mapping.targetG) <= 8 && 
                          Math.abs(b - mapping.targetB) <= 8) {
                          item.strokeColor = mapping.replColor;
                          item.strokeOverprint = false;
                          break;
                      }
                  }
              }
          } else if (item.typename == "GroupItem") {
              applyColorsDirectly(item.pageItems);
          } else if (item.typename == "CompoundPathItem") {
              applyColorsDirectly(item.pathItems);
          }
      }
  }

  applyColorsDirectly(doc.pageItems);
''')

    log_abs = str(ASCII_ROOT / "jsx_error.log")
    lines.append(f'  var saveFile = new File("{ai_abs}");')
    lines.append(f'  var saveOpts = new IllustratorSaveOptions();')
    lines.append(f'  saveOpts.pdfCompatible = true;')
    lines.append(f'  doc.saveAs(saveFile, saveOpts);')
    lines.append(f'  doc.close(SaveOptions.DONOTSAVECHANGES);')
    lines.append(f'  "SAVED_OK";')
    lines.append(f'}} catch(err) {{')
    lines.append(f'  var logFile = new File("{log_abs}");')
    lines.append(f'  logFile.open("w");')
    lines.append(f'  logFile.writeln(err.toString());')
    lines.append(f'  logFile.close();')
    lines.append(f'  try {{ app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); }} catch(e2) {{}}')
    lines.append(f'  "JSX_ERROR:" + err.toString();')
    lines.append(f'}}')

    return "\n".join(lines)


def process_country(code: str):
    svg_path = SVG_DIR / f"{code}.svg"
    ai_path = AI_OUT_DIR / f"{code}.ai"
    spec_path = SPEC_DIR / f"{code}.json"
    
    if not svg_path.exists():
        return "SKIP_NO_SVG"
    if not spec_path.exists():
        return "SKIP_NO_SPEC"
        
    with open(spec_path, encoding='utf-8') as f:
        spec = json.load(f)
        
    jsx_content = generate_jsx(svg_path, ai_path, spec)
    
    jsx_path = PROJECT_ROOT / "temp_run.jsx"
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx_content)
    
    # osascript に渡すパスはASCII symlink経由
    jsx_ascii = str(ASCII_ROOT / "temp_run.jsx")
    cmd = [
        'osascript', '-e',
        f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_ascii}"'
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "ERROR_TIMEOUT"
    if "Error" in res.stderr or res.returncode != 0:
        return f"ERROR: {res.stderr.strip()[:100]}"
    # Check JSX return value
    stdout = res.stdout.strip()
    if "JSX_ERROR" in stdout:
        return f"ERROR_JSX: {stdout[:100]}"
    # Verify file was actually saved (timestamp check)
    if ai_path.exists():
        import time as _t
        age = _t.time() - ai_path.stat().st_mtime
        if age > 30:  # file older than 30 seconds = not updated
            return f"ERROR_NOT_SAVED: file not modified (age={age:.0f}s)"
    return "SUCCESS"


def mark_done(code: str):
    """進捗ログに完了コードを追記する。"""
    PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_LOG, "a") as f:
        f.write(f"{code}\n")


def get_done_codes() -> set:
    """進捗ログから完了済みコードを取得する。"""
    if not PROGRESS_LOG.exists():
        return set()
    return set(PROGRESS_LOG.read_text().strip().split("\n"))


def get_codes_needing_update():
    """Return codes where SVG is newer than AI or AI doesn't exist."""
    codes = []
    for svg in sorted(SVG_DIR.glob("*.svg")):
        code = svg.stem
        ai = AI_OUT_DIR / f"{code}.ai"
        if not ai.exists() or svg.stat().st_mtime > ai.stat().st_mtime:
            codes.append(code)
    return codes


def main():
    AI_OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # ASCII-only symlink を作成（ExtendScript が日本語パスを扱えないため）
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
    
    # --resume: skip already-done codes
    if resume:
        done = get_done_codes()
        before = len(codes)
        codes = [c for c in codes if c not in done]
        print(f"Resume: skipping {before - len(codes)} already-done, {len(codes)} remaining")
    else:
        # 新規実行時は進捗ログをリセット
        PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS_LOG.write_text("")
    
    if not codes:
        print("No files to process. All AI files are up to date!")
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
        
        # Delay and memory management per illustrator_batch_safety workflow
        if i < total:
            if i % 5 == 0:
                # 5件ごとに全ドキュメント強制クローズ + 長めの休止
                print(f"   🧹 5件完了 - 全ドキュメント強制クローズ + 5秒休止... ({i}/{total})")
                close_all_documents()
                time.sleep(5)
            else:
                time.sleep(2)
    
    # 最終クリーンアップ
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
