import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_files import (
    install_project_file, make_project_dirs, open_project_file,
    private_dir, write_private,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
make_project_dirs(AI_DIR)

missing = ["CC", "GU", "HT", "KH", "KI", "MX", "SO", "SX", "TW", "VN", "XK", "ZW"]

for code in missing:
    svg_file = SVG_DIR / f"{code}.svg"
    ai_file = AI_DIR / f"{code}.ai"
    if not svg_file.exists():
        continue

    with private_dir() as work:
        ai_out = work / "out.ai"
        log_out = work / "error.log"
        jsx_path = work / "script.jsx"
        jsx_content = f"""
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
try {{
    var doc = app.open(File("{svg_file}"));
    app.executeMenuCommand('doc-color-cmyk');
    
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    doc.saveAs(File("{ai_out}"), saveOpts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
}} catch(e) {{
    var log = new File("{log_out}");
    log.open("a");
    log.writeln("{code}: " + e.message);
    log.close();
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
"""
        write_private(jsx_path, jsx_content)
        cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
        subprocess.run(cmd)
        if log_out.exists():
            with open_project_file(PROJECT_ROOT / "error.log", "a") as f:
                f.write(log_out.read_text(encoding="utf-8"))
        if ai_out.exists():
            install_project_file(ai_out, ai_file)
    print(f"Processed {code}")

