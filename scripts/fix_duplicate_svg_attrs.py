import os
import re

svg_dir = "03_svg_verified"

for filename in os.listdir(svg_dir):
    if not filename.endswith(".svg"):
        continue
    filepath = os.path.join(svg_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the <svg ...> tag
    svg_tag_match = re.search(r'<svg[^>]+>', content)
    if not svg_tag_match:
        continue
    
    svg_tag = svg_tag_match.group(0)
    
    cleaned_tag = re.sub(r'\s+width=(["\']).*?\1', '', svg_tag)
    cleaned_tag = re.sub(r'\s+height=(["\']).*?\1', '', cleaned_tag)
    
    # Add back width="900" height="600" just before the >
    if cleaned_tag.endswith("/>"):
        cleaned_tag = cleaned_tag[:-2] + ' width="900" height="600"/>'
    elif cleaned_tag.endswith(">"):
        cleaned_tag = cleaned_tag[:-1] + ' width="900" height="600">'
        
    if svg_tag != cleaned_tag:
        new_content = content.replace(svg_tag, cleaned_tag, 1)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed duplicate attributes in {filename}")

