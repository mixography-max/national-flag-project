import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_open import write_text_no_follow  # noqa: E402

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
        
    jsx_path = PROJECT_ROOT / f"temp_{code}.jsx"
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
    result = "ERROR:" + e.message;
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
result;
"""
    write_text_no_follow(jsx_path, jsx_content)
    cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
    res = subprocess.run(cmd, capture_output=True, text=True)
    output = res.stdout.strip()
    if output.startswith("ERROR:"):
        write_text_no_follow(PROJECT_ROOT / "error.log", f"{code}: {output[len('ERROR:'):]}\n", append=True)
    jsx_path.unlink()
    print(f"Processed {code}")
