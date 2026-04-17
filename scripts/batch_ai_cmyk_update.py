#!/usr/bin/env python3
"""
batch_ai_cmyk_update.py – SVG変更を反映してAIファイルを再生成

03_svg_verified のSVGが 04_ai_cmyk のAIより新しいファイルのみ処理。
Adobe Illustratorをosascript経由で自動制御します。

使い方:
  python3 scripts/batch_ai_cmyk_update.py          # 変更分のみ
  python3 scripts/batch_ai_cmyk_update.py --all     # 全ファイル再生成
  python3 scripts/batch_ai_cmyk_update.py --codes AF QA CH  # 指定コードのみ
"""

import json
import os
import sys
import subprocess
import time
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
AI_OUT_DIR = PROJECT_ROOT / "04_ai_cmyk"

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

def generate_jsx(svg_path: Path, ai_path: Path, spec: dict):
    lines = []
    lines.append(f'try {{')
    lines.append(f'  var doc = app.open(File("{svg_path.absolute()}"));')
    
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
        
        if pantone and pantone not in ("White", "Black"):
            lines.append(f'  var spot_{i} = null;')
            lines.append(f'  try {{ spot_{i} = doc.spots.getByName("{pantone}"); }} catch(e) {{}}')
            lines.append(f'  if(!spot_{i}) {{')
            lines.append(f'      spot_{i} = doc.spots.add();')
            lines.append(f'      spot_{i}.name = "{pantone}";')
            lines.append(f'      spot_{i}.colorType = ColorModel.SPOT;')
            lines.append(f'      spot_{i}.color = cmyk_{i};')
            lines.append(f'  }}')
            lines.append(f'  var finalColor_{i} = new SpotColor();')
            lines.append(f'  finalColor_{i}.spot = spot_{i};')
            lines.append(f'  finalColor_{i}.tint = 100;')
        else:
            lines.append(f'  var finalColor_{i} = cmyk_{i};')
            
        lines.append(f'  colorMappings.push({{')
        lines.append(f'      targetR: {rgb[0]}, targetG: {rgb[1]}, targetB: {rgb[2]},')
        lines.append(f'      replColor: finalColor_{i}')
        lines.append(f'  }});')

    lines.append('''
  function processPaths(items) {
      for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item.typename == "PathItem") {
              if (item.filled && item.fillColor && item.fillColor.typename == "RGBColor") {
                  var r = item.fillColor.red;
                  var g = item.fillColor.green;
                  var b = item.fillColor.blue;
                  for (var c=0; c < colorMappings.length; c++) {
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
                  for (var c=0; c < colorMappings.length; c++) {
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
              processPaths(item.pageItems);
          } else if (item.typename == "CompoundPathItem") {
              processPaths(item.pathItems);
          }
      }
  }
  processPaths(doc.pageItems);
''')
    
    lines.append("  app.executeMenuCommand('doc-color-cmyk');")
    lines.append(f'  var saveFile = new File("{ai_path.absolute()}");')
    lines.append(f'  var saveOpts = new IllustratorSaveOptions();')
    lines.append(f'  saveOpts.pdfCompatible = true;')
    lines.append(f'  doc.saveAs(saveFile, saveOpts);')
    lines.append(f'  doc.close(SaveOptions.DONOTSAVECHANGES);')
    lines.append(f'}} catch(err) {{')
    lines.append(f'  $.writeln(err.toString());')
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
        
    cmd = [
        'osascript', '-e',
        f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path.absolute()}"'
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if "Error" in res.stderr or res.returncode != 0:
        return f"ERROR: {res.stderr.strip()[:100]}"
    return "SUCCESS"


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
    
    # Parse arguments
    if "--all" in sys.argv:
        codes = [s.stem for s in sorted(SVG_DIR.glob("*.svg"))]
        print(f"Mode: ALL ({len(codes)} files)")
    elif "--codes" in sys.argv:
        idx = sys.argv.index("--codes")
        codes = sys.argv[idx+1:]
        print(f"Mode: SPECIFIC ({len(codes)} files: {', '.join(codes)})")
    else:
        codes = get_codes_needing_update()
        print(f"Mode: UPDATE ({len(codes)} files with newer SVGs)")
    
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
            print("✅")
        elif status.startswith("SKIP"):
            skip += 1
            print(f"⏭️ {status}")
        else:
            error += 1
            errors_list.append(f"{code}: {status}")
            print(f"❌ {status}")
        
        # Small delay between files to avoid overwhelming Illustrator
        if i < total:
            time.sleep(0.5)
    
    print("\n" + "=" * 50)
    print(f"Complete! ✅{success}  ❌{error}  ⏭️{skip}")
    if errors_list:
        print("\nErrors:")
        for e in errors_list:
            print(f"  {e}")
    print("=" * 50)


if __name__ == "__main__":
    main()
