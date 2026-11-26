import json
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"

missing = ["CC", "GU", "HT", "MX", "SO", "SX", "XK", "ZW"]

for code in missing:
    svg_file = SVG_DIR / f"{code}.svg"
    ai_file = AI_DIR / f"{code}.ai"
        
    jsx_content = f"""
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
try {{
    var doc = app.open(File("{svg_file}"));
    app.executeMenuCommand('doc-color-cmyk');
    
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    doc.saveAs(File("{ai_file}"), saveOpts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
}} catch(e) {{
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
"""
    with tempfile.TemporaryDirectory(prefix="flag_jsx_") as tmp_dir:
        jsx_path = Path(tmp_dir) / f"temp_{code}.jsx"
        with open(jsx_path, "x", encoding='utf-8') as f:
            f.write(jsx_content)
        cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
        subprocess.run(cmd)
    
