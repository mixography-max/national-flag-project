import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project_fs

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
        
    # Illustrator は作業ツリーに直接書き込まない。保存先とログは本人専用の
    # 一時ディレクトリに置き、結果をリンクを辿らずに作業ツリーへ反映する。
    with project_fs.private_workdir() as work:
        jsx_path = work / f"{code}.jsx"
        work_ai = work / ai_file.name
        work_log = work / "error.log"
        jsx_content = f"""
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
try {{
    var doc = app.open(File("{svg_file}"));
    app.executeMenuCommand('doc-color-cmyk');
    
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    doc.saveAs(File("{work_ai}"), saveOpts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
}} catch(e) {{
    var log = new File("{work_log}");
    log.open("a");
    log.writeln("{code}: " + e.message);
    log.close();
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
"""
        project_fs.write_new(jsx_path, jsx_content.encode('utf-8'))
        cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
        subprocess.run(cmd)
        if work_log.exists():
            project_fs.append_text(PROJECT_ROOT / "error.log", work_log.read_text(encoding='utf-8', errors='replace'))
        if work_ai.exists():
            project_fs.install_file(work_ai, ai_file)
    print(f"Processed {code}")

