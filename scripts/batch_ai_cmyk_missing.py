import json
import os
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
AI_DIR.mkdir(parents=True, exist_ok=True)

missing = ["CC", "GU", "HT", "KH", "KI", "MX", "SO", "SX", "TW", "VN", "XK", "ZW"]

for code in missing:
    svg_file = SVG_DIR / f"{code}.svg"
    ai_file = AI_DIR / f"{code}.ai"
    if not svg_file.exists():
        continue
        
    jsx_content = f"""
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var result = "OK";
try {{
    var doc = app.open(File("{svg_file}"));
    app.executeMenuCommand('doc-color-cmyk');
    
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    doc.saveAs(File("{ai_file}"), saveOpts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
}} catch(e) {{
    result = "ERROR: " + e.message;
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
result;
"""
    fd, jsx_path = tempfile.mkstemp(prefix=f"temp_{code}_", suffix=".jsx")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(jsx_content)
    cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        os.unlink(jsx_path)
    if "ERROR:" in res.stdout:
        print(f"{code}: {res.stdout.strip()}")
    print(f"Processed {code}")

