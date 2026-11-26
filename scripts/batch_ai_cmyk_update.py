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
import tempfile
import time
import unicodedata
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
AI_OUT_DIR = PROJECT_ROOT / "04_ai_cmyk"
PROGRESS_LOG = AI_OUT_DIR / "logs" / "progress.txt"
JSX_ERROR_LOG = PROJECT_ROOT / "jsx_error.log"

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
    with tempfile.TemporaryDirectory(prefix="flag_jsx_") as tmp_dir:
        jsx_path = Path(tmp_dir) / "temp_closeall.jsx"
        with open(jsx_path, "xb") as f:
            f.write(b'\xef\xbb\xbf')
            f.write(jsx.encode('utf-8'))
        cmd = [
            'osascript', '-e',
            f'tell application "Adobe Illustrator" to do javascript file POSIX file "{nfc(str(jsx_path))}"'
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
    
    # Wait for activeDocument to be initialized after open
    lines.append('''
  var initReady = false;
  for (var w = 0; w < 50; w++) {
      try {
          if (app.activeDocument != null) {
              initReady = true;
              break;
          }
      } catch(e) {}
      $.sleep(100);
  }
  if (!initReady) {
      throw new Error("Active document initialization timed out after open");
  }
''')
    
    # Use "colors" key (not "colors_extracted")
    colors = spec.get("colors", spec.get("colors_extracted", []))
    
    lines.append(f'  var colorMappings = [];')
    
    for i, c in enumerate(colors):
        rgb = hex_to_rgb(c.get("hex", "#000000"))
        cmyk_vals = parse_cmyk(c.get("cmyk", ""))
        pantone = c.get("pantone", "").strip()
        
        lines.append(f'  var cmyk_{i} = new CMYKColor();')
        lines.append(f'  cmyk_{i}.cyan = {cmyk_vals[0]};')
        lines.append(f'  cmyk_{i}.magenta = {cmyk_vals[1]};')
        lines.append(f'  cmyk_{i}.yellow = {cmyk_vals[2]};')
        lines.append(f'  cmyk_{i}.black = {cmyk_vals[3]};')
        
        # Register Swatch as SPOT first (in RGB mode) to avoid MRAP errors
        if pantone and pantone not in ("White", "Black"):
            lines.append(f'  var spot_{i} = null;')
            lines.append(f'  try {{ spot_{i} = doc.spots.getByName("{pantone}"); }} catch(e) {{}}')
            lines.append(f'  if (!spot_{i}) {{')
            lines.append(f'      spot_{i} = doc.spots.add();')
            lines.append(f'      spot_{i}.name = "{pantone}";')
            lines.append(f'      spot_{i}.colorType = ColorModel.SPOT;')
            lines.append(f'      spot_{i}.color = cmyk_{i};')
            lines.append(f'  }}')
            lines.append(f'  var spotColor_{i} = new SpotColor();')
            lines.append(f'  spotColor_{i}.spot = spot_{i};')
            lines.append(f'  spotColor_{i}.tint = 100;')
            lines.append(f'  var replColor_{i} = spotColor_{i};')
        else:
            lines.append(f'  var replColor_{i} = cmyk_{i};')
            
        lines.append(f'  colorMappings.push({{')
        lines.append(f'      targetR: {rgb[0]}, targetG: {rgb[1]}, targetB: {rgb[2]},')
        lines.append(f'      pantone: "{pantone}",')
        lines.append(f'      replColor: replColor_{i}')
        lines.append(f'  }});')

    lines.append('''
  function markPaths(items) {
      for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item.typename == "PathItem") {
              var tags = [];
              if (item.filled && item.fillColor && item.fillColor.typename == "RGBColor") {
                  var r = item.fillColor.red;
                  var g = item.fillColor.green;
                  var b = item.fillColor.blue;
                  for (var c = 0; c < colorMappings.length; c++) {
                      var mapping = colorMappings[c];
                      if (Math.abs(r - mapping.targetR) <= 8 && 
                          Math.abs(g - mapping.targetG) <= 8 && 
                          Math.abs(b - mapping.targetB) <= 8) {
                          tags.push("fill:" + c);
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
                          tags.push("stroke:" + c);
                          break;
                      }
                  }
              }
              if (tags.length > 0) {
                  item.note = tags.join("|");
              }
          } else if (item.typename == "GroupItem") {
              markPaths(item.pageItems);
          } else if (item.typename == "CompoundPathItem") {
              markPaths(item.pathItems);
          }
      }
  }

  function applyColors(items) {
      for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item.typename == "PathItem") {
              if (item.note) {
                  var parts = item.note.split("|");
                  for (var p = 0; p < parts.length; p++) {
                      var tag = parts[p].split(":");
                      if (tag.length == 2) {
                          var type = tag[0];
                          var idx = parseInt(tag[1]);
                          var color = colorMappings[idx].replColor;
                          if (type == "fill") {
                              item.filled = true;
                              item.fillColor = color;
                          } else if (type == "stroke") {
                              item.stroked = true;
                              item.strokeColor = color;
                              item.strokeOverprint = false;
                          }
                      }
                  }
                  item.note = "";
              }
          } else if (item.typename == "GroupItem") {
              applyColors(item.pageItems);
          } else if (item.typename == "CompoundPathItem") {
              applyColors(item.pathItems);
          }
      }
  }

  // 1. Tag paths based on RGB
  markPaths(doc.pageItems);
  
  // 2. Apply colors to paths (still in RGB mode)
  applyColors(doc.pageItems);
  
  // 3. Switch document to CMYK mode
  app.activeDocument = doc;
  app.executeMenuCommand('doc-color-cmyk');
  
  // 4. Wait for CMYK conversion to complete using app.documents[0]
  var docReady = false;
  var lastErr = "none";
  for (var w = 0; w < 100; w++) {
      $.sleep(100);
      try {
          if (app.documents.length > 0) {
              var targetDoc = app.documents[0];
              if (targetDoc.documentColorSpace == DocumentColorSpace.CMYK) {
                  doc = targetDoc;
                  docReady = true;
                  break;
              } else {
                  lastErr = "space is still " + targetDoc.documentColorSpace;
              }
          } else {
              lastErr = "documents.length is 0";
          }
      } catch(e) {
          lastErr = "exception: " + e.toString() + " line:" + e.line;
      }
  }
  if (!docReady) {
      throw new Error("CMYK conversion timeout. Last status: " + lastErr);
  }
  
  // 5. Change Spot Swatches to PROCESS color model
  for (var c = 0; c < colorMappings.length; c++) {
      var mapping = colorMappings[c];
      var pName = mapping.pantone;
      if (pName && pName !== "" && pName !== "White" && pName !== "Black") {
          try {
              var targetSpot = doc.spots.getByName(pName);
              targetSpot.colorType = ColorModel.PROCESS;
          } catch(e) {}
      }
  }
''')

    lines.append(f'  var saveFile = new File("{ai_abs}");')
    lines.append(f'  var saveOpts = new IllustratorSaveOptions();')
    lines.append(f'  saveOpts.pdfCompatible = true;')
    lines.append(f'  doc.saveAs(saveFile, saveOpts);')
    lines.append(f'  doc.close(SaveOptions.DONOTSAVECHANGES);')
    lines.append(f'  "SAVED_OK";')
    lines.append(f'}} catch(err) {{')
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
    
    # 一時ディレクトリはASCIIのみのパスなので osascript にそのまま渡せる
    with tempfile.TemporaryDirectory(prefix="flag_jsx_") as tmp_dir:
        jsx_path = Path(tmp_dir) / "temp_run.jsx"
        with open(jsx_path, "x", encoding="utf-8") as f:
            f.write(jsx_content)
        
        cmd = [
            'osascript',
            '-e', 'tell application "Adobe Illustrator" to activate',
            '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"'
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
        with open_nofollow(JSX_ERROR_LOG, os.O_TRUNC) as f:
            f.write(f"{stdout}\n")
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
    with open_nofollow(PROGRESS_LOG, os.O_APPEND) as f:
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
        open_nofollow(PROGRESS_LOG, os.O_TRUNC).close()
    
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
