import os
import re
import subprocess

svg_dir = "03_svg_verified"
namespaces = ' xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:cc="http://creativecommons.org/ns#" '

errors = []
for filename in os.listdir(svg_dir):
    if not filename.endswith(".svg"):
        continue
    filepath = os.path.join(svg_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix unescaped ampersands (mainly in <desc> or <title>)
    content = content.replace(" & ", " &amp; ")

    # Inject namespaces into the <svg> opening tag safely
    svg_tag_match = re.search(r'<svg([^>]+)>', content)
    if svg_tag_match:
        old_tag = svg_tag_match.group(0)
        inner = svg_tag_match.group(1)
        
        # Don't add if already there
        if "sodipodi-0.dtd" not in inner:
            # We just insert them right after <svg
            new_tag = f'<svg{namespaces}{inner}>'
            content = content.replace(old_tag, new_tag, 1)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    # Check validity using xmllint
    res = subprocess.run(['xmllint', '--noout', filepath], capture_output=True)
    if res.returncode != 0:
        errors.append(filename)

if errors:
    print("Files still invalid:", errors)
else:
    print("All SVGs are valid XML!")
