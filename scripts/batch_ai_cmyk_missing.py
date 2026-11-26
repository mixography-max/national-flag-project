import json
import os
import stat
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = PROJECT_ROOT / "03_svg_verified"
AI_DIR = PROJECT_ROOT / "04_ai_cmyk"
AI_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG = PROJECT_ROOT / "error.log"


def open_in_project(path: Path, flags: int, mode: str, **kwargs):
    """Open a file under PROJECT_ROOT without following symlinks.

    Git can check out symlinks even at ignored paths such as temp_*.jsx,
    so every directory below PROJECT_ROOT and the file itself are opened
    with O_NOFOLLOW relative to the previous descriptor.
    """
    parts = Path(os.path.abspath(path)).relative_to(PROJECT_ROOT).parts
    dir_fd = os.open(PROJECT_ROOT, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[:-1]:
            if flags & os.O_CREAT:
                try:
                    os.mkdir(part, dir_fd=dir_fd)
                except FileExistsError:
                    pass
            sub_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)
            os.close(dir_fd)
            dir_fd = sub_fd
        fd = os.open(parts[-1], flags | os.O_NOFOLLOW, 0o666, dir_fd=dir_fd)
    finally:
        os.close(dir_fd)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(f"Not a regular file: {path}")
    return os.fdopen(fd, mode, **kwargs)


missing = ["CC", "GU", "HT", "KH", "KI", "MX", "SO", "SX", "TW", "VN", "XK", "ZW"]

for code in missing:
    svg_file = SVG_DIR / f"{code}.svg"
    ai_file = AI_DIR / f"{code}.ai"
    if not svg_file.exists():
        continue
        
    jsx_path = PROJECT_ROOT / f"temp_{code}.jsx"
    jsx_content = f"""
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var result = "";
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
    with open_in_project(jsx_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, "w", encoding='utf-8') as f:
        f.write(jsx_content)
    cmd = ['osascript', '-e', f'tell application "Adobe Illustrator" to do javascript file POSIX file "{jsx_path}"']
    res = subprocess.run(cmd, capture_output=True, text=True)
    stdout = res.stdout.strip()
    if stdout.startswith("JSX_ERROR:"):
        with open_in_project(ERROR_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, "a", encoding='utf-8') as f:
            f.write(f"{code}: {stdout[len('JSX_ERROR:'):]}\n")
    jsx_path.unlink()
    print(f"Processed {code}")
