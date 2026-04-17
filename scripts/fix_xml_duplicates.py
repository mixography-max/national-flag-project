import os
import re

svg_dir = "03_svg_verified"
errors = []

for filename in os.listdir(svg_dir):
    if not filename.endswith(".svg"):
        continue
    filepath = os.path.join(svg_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the opening <svg ...> tag
    svg_tag_match = re.search(r'<svg([^>]+)>', content)
    if not svg_tag_match:
        continue
        
    old_tag = svg_tag_match.group(0)
    inner = svg_tag_match.group(1)
    
    # Extract all attributes using regex
    # attr_pattern matches name="value" or name='value'
    attrs = {}
    
    # find all attributes taking into account quotes and newlines
    matches = re.finditer(r'([a-zA-Z0-9_:-]+)\s*=\s*(["\'])(.*?)\2', inner, re.DOTALL)
    for m in matches:
        key = m.group(1)
        val = m.group(3)
        # We only keep the FIRST occurrence of an attribute!
        if key not in attrs:
            attrs[key] = val
            
    # Ensure mandatory xml namespaces
    if 'xmlns' not in attrs: attrs['xmlns'] = "http://www.w3.org/2000/svg"
    if 'xmlns:xlink' not in attrs: attrs['xmlns:xlink'] = "http://www.w3.org/1999/xlink"
    if 'xmlns:sodipodi' not in attrs: attrs['xmlns:sodipodi'] = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
    if 'xmlns:inkscape' not in attrs: attrs['xmlns:inkscape'] = "http://www.inkscape.org/namespaces/inkscape"
    
    # Also, remove ANY stray " xmlns:sodipodi" style strings if they were injected without '=' (which shouldn't happen, but just rebuild the string)
    
    new_inner = "\n   ".join([f'{k}="{v}"' for k, v in attrs.items()])
    new_tag = f'<svg\n   {new_inner}>'
    
    content = content.replace(old_tag, new_tag, 1)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("Done fixing attributes!")
