#!/usr/bin/env python3
"""
Generate an Excel file for distribution containing flag color rules, specs, and notes.
"""
import json
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DATA_JSON = PROJECT_ROOT / "05_web" / "flags_data.json"
OUT_EXCEL = PROJECT_ROOT / "06_docs" / "Flag_Color_Rules_and_Specs.xlsx"

def format_colors(colors):
    if not colors:
        return ""
    
    color_lines = []
    for c in colors:
        cname = c.get('color_name', '')
        hex_val = c.get('hex', '')
        pantone = c.get('pantone', '')
        cmyk = c.get('cmyk', '')
        
        details = []
        if hex_val: details.append(f"HEX: {hex_val}")
        if pantone: details.append(f"Pantone: {pantone}")
        if cmyk: details.append(f"CMYK: {cmyk}")
        
        detail_str = ", ".join(details)
        if detail_str:
            color_lines.append(f"{cname} ({detail_str})")
        else:
            color_lines.append(cname)
            
    return "\n".join(color_lines)

def main():
    if not WEB_DATA_JSON.exists():
        print(f"Error: {WEB_DATA_JSON} not found.")
        return
        
    with open(WEB_DATA_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    rows = []
    for entry in data:
        # Strip HTML from specs_source if present
        source = entry.get('specs_source', '')
        if '<a href=' in source:
            import re
            # Extract URL or just strip tags, here we just strip HTML tags nicely
            # Actually, process_links in build_web_data.py converted URLs to <a href="...">URL</a>
            # We can strip the tags to get the plain text or URL back
            source = re.sub(r'<[^>]+>', '', source)
            
        rows.append({
            'ISO Code': entry.get('code', ''),
            '国名 (和文)': entry.get('name_ja', ''),
            '国名 (英文)': entry.get('name_en', ''),
            '縦横比率': entry.get('ratio', ''),
            '指定カラー': format_colors(entry.get('colors', [])),
            '法的根拠・出典': source,
            '備考・構造規定': entry.get('notes', ''),
            'ステータス': entry.get('status', '')
        })
        
    df = pd.DataFrame(rows)
    
    # Save to Excel
    OUT_EXCEL.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_EXCEL, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Flag Specs')
        
        # Auto-adjust column widths for better readability (simple approach)
        worksheet = writer.sheets['Flag Specs']
        for idx, col in enumerate(df.columns, 1):
            worksheet.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = 20
        
        # Make the '指定カラー' and '備考・構造規定' columns wider and wrap text
        from openpyxl.styles import Alignment
        wrap_alignment = Alignment(wrap_text=True, vertical='top')
        top_alignment = Alignment(vertical='top')
        
        for row in worksheet.iter_rows(min_row=2): # skip header
            for cell in row:
                if cell.column_letter in ['E', 'F', 'G']: # カラー, 出典, 備考
                    cell.alignment = wrap_alignment
                else:
                    cell.alignment = top_alignment
                    
        worksheet.column_dimensions['B'].width = 15
        worksheet.column_dimensions['C'].width = 25
        worksheet.column_dimensions['E'].width = 40 # カラー
        worksheet.column_dimensions['F'].width = 40 # 出典
        worksheet.column_dimensions['G'].width = 50 # 備考

    print(f"✅ Excelファイルの出力が完了しました: {OUT_EXCEL}")

if __name__ == "__main__":
    # We need to import openpyxl to use its utils
    import openpyxl.utils
    main()
