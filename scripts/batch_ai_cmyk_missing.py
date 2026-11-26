import json
import os
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
ERROR_LOG = PROJECT_ROOT / "error.log"
AI_DIR.mkdir(parents=True, exist_ok=True)


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


missing = ["CC", "GU", "HT", "KH", "KI", "MX", "SO", "SX", "TW", "VN", "XK", "ZW"]

for code in missing:
    svg_file = SVG_DIR / f"{code}.svg"
    ai_file = AI_DIR / f"{code}.ai"
    if not svg_file.exists():
        continue
        
    jsx_content = f"""
var result = "";
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
try {{
    var doc = app.open(File("{svg_file}"));
    app.executeMenuCommand('doc-color-cmyk');
    
    var saveOpts = new IllustratorSaveOptions();
    saveOpts.pdfCompatible = true;
    doc.saveAs(File("{ai_file}"), saveOpts);
    doc.close(SaveOptions.DONOTSAVECHANGES);
}} catch(e) {{
    result = "JSX_ERROR:" + e.message;
}}
app.userInteractionLevel = UserInteractionLevel.DISPLAYALERTS;
result;
"""
    with tempfile.TemporaryDirectory(prefix="flag_jsx_") as tmp_dir:
        jsx_path = Path(tmp_dir) / f"temp_{code}.jsx"
        with open(jsx_path, "x", encoding='utf-8') as f:
            f.write(jsx_content)
        cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    output = res.stdout.strip()
    if output.startswith("JSX_ERROR:"):
        with open_nofollow(ERROR_LOG, os.O_APPEND) as log:
            log.write(f"{code}: {output[len('JSX_ERROR:'):]}\n")
    print(f"Processed {code}")
