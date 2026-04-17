import os
import re
import subprocess

svg_dir = "03_svg_verified"
namespaces = {
    "xmlns:xlink": "http://www.w3.org/1999/xlink",
    "xmlns:sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "xmlns:inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xmlns:dc": "http://purl.org/dc/elements/1.1/",
    "xmlns:cc": "http://creativecommons.org/ns#",
    "xmlns:ns1": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
}

errors = []
for filename in os.listdir(svg_dir):
    if not filename.endswith(".svg"):
        continue
    filepath = os.path.join(svg_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to find the FIRST <svg... > tag
    svg_tag_match = re.search(r'<svg([^>]+)>', content)
    if svg_tag_match:
        old_tag = svg_tag_match.group(0)
        inner = svg_tag_match.group(1)
        
        # Strip all existing namespaces from inner just to safely rebuild it (or just add what's missing)
        # Actually safer to just append what is missing
        missing_ns = ""
        for prefix, uri in namespaces.items():
            if prefix not in inner:
                missing_ns += f' {prefix}="{uri}"'
        
        new_tag = f'<svg{missing_ns}{inner}>'
        content = content.replace(old_tag, new_tag, 1)

    # Some files like ZW have `<sodipodi:namedview ... bordercolor="...`
    # Ensure they are valid xmlns
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    res = subprocess.run(['xmllint', '--noout', filepath], capture_output=True)
    if res.returncode != 0:
        print(f"Error in {filename}:", res.stderr.decode('utf-8'))
        errors.append(filename)

print("Files still invalid:", len(errors))
