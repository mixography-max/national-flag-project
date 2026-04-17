#!/usr/bin/env python3
"""
batch_ai_cmyk.py – Phase 5: 印刷用CMYK出力 (AIファイルのバッチ生成)

03_svg_verified の SVG を順番に Adobe Illustrator で開き、
02_official_specs の CMYK・Pantone 値を使って色を厳密に置換し、
CMYK カラースペースの .ai (PDF互換) として 04_ai_cmyk へ出力します。
"""

import json
import os
import subprocess
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
SPEC_DIR = PROJECT_ROOT / "02_official_specs"
AI_OUT_DIR = PROJECT_ROOT / "04_ai_cmyk"
LOG_DIR = AI_OUT_DIR / "logs"

def hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def parse_cmyk(cmyk_str: str):
    """Parse '100-80-0-20' or '100, 80, 0, 20' into a tuple (C, M, Y, K)"""
    if not cmyk_str or cmyk_str.strip() in ("", "N. A."):
        return (0, 0, 0, 0)
    
    # Try different splitters
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
    # Open SVG
    lines.append(f'  var doc = app.open(File("{svg_path.absolute()}"));')
    
    # Setup Colors
    colors = spec.get("colors_extracted", [])
    
    # We will build an array of match configurations in JSX
    lines.append(f'  var colorMappings = [];')
    
    for i, c in enumerate(colors):
        rgb = hex_to_rgb(c.get("hex", "#000000"))
        cmyk_vals = parse_cmyk(c.get("cmyk", ""))
        pantone = c.get("pantone", "").strip()
        
        # Determine replacing color creation
        lines.append(f'  var cmyk_{i} = new CMYKColor();')
        lines.append(f'  cmyk_{i}.cyan = {cmyk_vals[0]};')
        lines.append(f'  cmyk_{i}.magenta = {cmyk_vals[1]};')
        lines.append(f'  cmyk_{i}.yellow = {cmyk_vals[2]};')
        lines.append(f'  cmyk_{i}.black = {cmyk_vals[3]};')
        
        if pantone and pantone not in ("White", "Black"):
            # Avoid duplicate spot names if we iterate, but it's per document so it's fresh
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

    # Recursive path processor
    lines.append('''
  function processPaths(items) {
      for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item.typename == "PathItem") {
              if (item.filled && item.fillColor && item.fillColor.typename == "RGBColor") {
                  var r = item.fillColor.red;
                  var g = item.fillColor.green;
                  var b = item.fillColor.blue;
                  // Find closest match within tolerance (e.g. 5)
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
              // Also check stroke
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
                          item.strokeOverprint = false; // ensure standard print behaviors
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
    
    # Convert active doc to CMYK after paths are matched
    # It ensures the resulting file is saved as CMYK format
    lines.append("  app.executeMenuCommand('doc-color-cmyk');")
    
    # Save
    lines.append(f'  var saveFile = new File("{ai_path.absolute()}");')
    lines.append(f'  var saveOpts = new IllustratorSaveOptions();')
    lines.append(f'  saveOpts.pdfCompatible = true;')
    lines.append(f'  doc.saveAs(saveFile, saveOpts);')
    lines.append(f'  doc.close(SaveOptions.DONOTSAVECHANGES);')
    lines.append(f'}} catch(err) {{')
    lines.append(f'  $.writeln(err.toString());')
    lines.append(f'}}')

    return "\n".join(lines)


def process_country(code: str, test_mode=False):
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
        
    cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path.absolute()}"']
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if "Error" in res.stderr or res.returncode != 0:
        print(f"[{code}] ERR: {res.stderr.strip()}")
        return "ERROR"
    else:
        return "SUCCESS"

def main():
    AI_OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Starting full batch conversion for all Verified SVGs...")
    
    # Get all SVGs
    svg_files = sorted(SVG_DIR.glob("*.svg"))
    total = len(svg_files)
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    for i, svg in enumerate(svg_files, 1):
        code = svg.stem
        print(f"[{i}/{total}] Processing {code}...")
        
        status = process_country(code)
        
        if status == "SUCCESS":
            success_count += 1
        elif status == "ERROR":
            error_count += 1
        else:
            skip_count += 1
            
    print("=" * 40)
    print("Batch Run Complete!")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print(f"Skipped: {skip_count}")
    print("=" * 40)

if __name__ == "__main__":
    main()
