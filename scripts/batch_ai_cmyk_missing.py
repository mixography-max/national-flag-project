import json
import subprocess
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
        
    jsx_path = PROJECT_ROOT / f"temp_{code}.jsx"
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
    var log = new File("{PROJECT_ROOT}/error.log");
    log.open("a");
    log.writeln("{code}: " + e.message);
    log.close();
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
"""
    jsx_path.write_text(jsx_content, encoding='utf-8')
    cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
    subprocess.run(cmd)
    jsx_path.unlink()
    print(f"Processed {code}")

