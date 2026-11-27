import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_write import copy_into_project, private_dir, write_private_jsx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
AI_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG = PROJECT_ROOT / "error.log"

missing = ["CC", "GU", "HT", "KH", "KI", "MX", "SO", "SX", "TW", "VN", "XK", "ZW"]

for code in missing:
    svg_file = SVG_DIR / f"{code}.svg"
    ai_file = AI_DIR / f"{code}.ai"
    if not svg_file.exists():
        continue
        
    with private_dir() as tmp:
        tmp_log = tmp / "error.log"
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
    var log = new File("{tmp_log}");
    log.open("a");
    log.writeln("{code}: " + e.message);
    log.close();
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
"""
        jsx_path = write_private_jsx(tmp, jsx_content)
        cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
        try:
            subprocess.run(cmd)
        finally:
            copy_into_project(tmp_log, PROJECT_ROOT, ERROR_LOG, "a")
    print(f"Processed {code}")
