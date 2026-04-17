import os
import json
import re

notes_file = "06_docs/verification_notes.md"
spec_dir = "02_official_specs"

with open(notes_file, 'r', encoding='utf-8') as f:
    text = f.read()

ja_notes = {}
# Split the document by lines that look like: "1. **AD (Andorra)"
blocks = re.split(r'\n(?=\d+\.\s+\*\*[A-Z]{2}\s)', text)
for block in blocks:
    m = re.search(r'^\d+\.\s+\*\*([A-Z]{2})\s', block)
    if not m:
        m = re.search(r'\d+\.\s+\*\*([A-Z]{2})\s', block)
    
    if m:
        code = m.group(1)
        # Extract the 結果
        res_m = re.search(r'-\s*\*\*結果\*\*\s*:\s*(.*?)(?=\n\s*-|\n\s*\n|\Z)', block, re.DOTALL)
        if res_m:
            ja_notes[code] = res_m.group(1).strip()

print(f"Extracted {len(ja_notes)} Japanese notes.")

updated = 0
for filename in os.listdir(spec_dir):
    if not filename.endswith(".json") or filename == "schema.json":
        continue
    code = filename.split('.')[0]
    filepath = os.path.join(spec_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if code in ja_notes:
        data["notes"] = ja_notes[code]
    else:
        # Fallback translations for missing codes (mostly dependent territories that use their parent's flag)
        if code == "UM": data["notes"] = "アメリカ合衆国の領土であり、公式の国旗はアメリカ国旗（星条旗）を使用する。"
        elif code == "TF": data["notes"] = "フランスの海外領土であり、公式の国旗はフランス国旗（三色旗）を使用する。"
        elif code == "SJ": data["notes"] = "ノルウェーの領土であり、公式の国旗はノルウェー国旗を使用する。"
        elif code == "EH": data["notes"] = "西サハラ（サハラ・アラブ民主共和国）の国旗。パン・アラブ色を用いた標準近似値を使用。"
        # print("Could not find note for", code)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        updated += 1
        
print(f"Updated {updated} JSON files.")
