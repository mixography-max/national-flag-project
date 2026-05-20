#!/usr/bin/env python3
"""
CSVの国旗データとMOFA検証済みデータを結合し、
国名一覧ページ用のJSONを生成する。
"""
import csv, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CSV_PATH = BASE / "06_docs" / "indesign_data_merge.csv"
MOFA_JSON = BASE / "06_docs" / "mofa_verified.json"
OUT_JSON = BASE / "05_web" / "countries_data.json"

# MOFA slug → ISO2 マッピング（手動）
SLUG_TO_ISO = {
    "india":"IN","indonesia":"ID","cambodia":"KH","singapore":"SG","srilanka":"LK",
    "thailand":"TH","korea":"KR","china":"CN","nepal":"NP","pakistan":"PK",
    "bangladesh":"BD","easttimor":"TL","philippines":"PH","bhutan":"BT","brunei":"BN",
    "vietnam":"VN","malaysia":"MY","myanmar":"MM","maldives":"MV","mongolia":"MN",
    "laos":"LA","n_korea":"KP","taiwan":"TW",
    "australia":"AU","kiribati":"KI","cook":"CK","samoa":"WS","solomon":"SB",
    "tuvalu":"TV","tonga":"TO","nauru":"NR","niue":"NU","nz":"NZ",
    "vanuatu":"VU","png":"PG","palau":"PW","fiji":"FJ","marshall":"MH","micronesia":"FM",
    "usa":"US","canada":"CA",
    "argentine":"AR","antigua":"AG","uruguay":"UY","ecuador":"EC","elsalvador":"SV",
    "guyana":"GY","cuba":"CU","guatemala":"GT","grenada":"GD","costarica":"CR",
    "colombia":"CO","jamaica":"JM","suriname":"SR","svg":"VC","scn":"KN",
    "s_lucia":"LC","chile":"CL","c_dominica":"DM","dominican_r":"DO","trinidad":"TT",
    "nicaragua":"NI","haiti":"HT","panama":"PA","bahama":"BS","paraguay":"PY",
    "barbados":"BB","brazil":"BR","venezuela":"VE","belize":"BZ","peru":"PE",
    "bolivia":"BO","honduras":"HN","mexico":"MX",
    "iceland":"IS","ireland":"IE","azerbaijan":"AZ","albania":"AL","armenia":"AM",
    "andorra":"AD","italy":"IT","ukraine":"UA","uzbekistan":"UZ","uk":"GB",
    "estonia":"EE","austria":"AT","netherlands":"NL","kazakhstan":"KZ","macedonia":"MK",
    "cyprus":"CY","greece":"GR","kyrgyz":"KG","croatia":"HR","kosovo":"XK",
    "sanmarino_r":"SM","georgia":"GE","switzerland":"CH","sweden":"SE","spain":"ES",
    "slovak":"SK","slovenia":"SI","serbia":"RS","tajikistan":"TJ","czech":"CZ",
    "denmark":"DK","germany":"DE","turkmenistan":"TM","norway":"NO","vatican":"VA",
    "hungary":"HU","finland":"FI","france":"FR","bulgaria":"BG","belarus":"BY",
    "belgium":"BE","poland":"PL","bosnia_h":"BA","portugal":"PT","malta":"MT",
    "monaco":"MC","moldova":"MD","montenegro":"ME","latvia":"LV","liechtenstein":"LI",
    "lithuania":"LT","romania":"RO","luxembourg":"LU","russia":"RU",
    "afghanistan":"AF","uae":"AE","yemen":"YE","israel":"IL","iraq":"IQ",
    "iran":"IR","oman":"OM","qatar":"QA","kuwait":"KW","saudi":"SA",
    "syria":"SY","turkey":"TR","bahrain":"BH","jordan":"JO","lebanon":"LB","plo":"PS",
    "algeria":"DZ","angola":"AO","uganda":"UG","egypt":"EG","eswatini":"SZ",
    "ethiopia":"ET","eritrea":"ER","ghana":"GH","capeverde":"CV","gabon":"GA",
    "cameroon":"CM","gambia":"GM","guinea":"GN","guinea_b":"GW","kenya":"KE",
    "cote_d":"CI","comoros":"KM","congokyo":"CG","congomin":"CD","stp":"ST",
    "zambia":"ZM","s_leone":"SL","djibouti":"DJ","zimbabwe":"ZW","sudan":"SD",
    "seychelles":"SC","eq_guinea":"GQ","senegal":"SN","somali":"SO","tanzania":"TZ",
    "chad":"TD","car":"CF","tunisia":"TN","togo":"TG","nigeria":"NG",
    "namibia":"NA","niger":"NE","burkina":"BF","brundi":"BI","benin":"BJ",
    "botswana":"BW","madagascar":"MG","malawi":"MW","mali":"ML","s_africa":"ZA",
    "s_sudan":"SS","mozambique":"MZ","mauritius":"MU","mauritania":"MR","morocco":"MA",
    "libya":"LY","liberia":"LR","rwanda":"RW","lesotho":"LS",
}

# 外務省地域 → 英語
REGION_MAP = {
    "アジア": "Asia",
    "大洋州": "Oceania",
    "北米": "Americas",
    "中南米": "Americas",
    "欧州": "Europe",
    "中東": "Asia",
    "アフリカ": "Africa",
}


def main():
    # CSVを読み込み
    csv_data = {}
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Code"]
            csv_data[code] = {
                "code": code,
                "name_ja": row.get("Name_JA", ""),
                "name_en": row.get("Name_EN", ""),
                "region": row.get("Region", ""),
                "status": row.get("Status", ""),
            }

    # MOFA検証済みデータを読み込み
    mofa_entries = []
    with open(MOFA_JSON, "r", encoding="utf-8") as f:
        mofa_entries = json.load(f)

    # 手動修正を適用
    import sys
    sys.path.append(str(BASE / "scripts"))
    try:
        from fix_and_rebuild_md import apply_overrides
        apply_overrides(mofa_entries)
    except ImportError:
        print("Warning: Could not import apply_overrides from fix_and_rebuild_md.py")

    mofa_data = {}
    for entry in mofa_entries:
        if "error" in entry:
            continue
        slug = entry.get("slug", "")
        iso = SLUG_TO_ISO.get(slug)
        if iso:
            mofa_data[iso] = entry

    # 結合
    result = []
    for code, csv_entry in csv_data.items():
        mofa = mofa_data.get(code, {})
        formal_ja = mofa.get("formal_name_ja", "")
        formal_en = mofa.get("formal_name_en", "")
        capital = mofa.get("capital", "")
        capital_note = mofa.get("capital_note", "")
        mofa_region = mofa.get("region", "")
        update_date = mofa.get("update_date", "")

        # capital_note クリーンアップ（英語名のみや統計情報は除外）
        if capital_note and re.match(r'^[A-Za-z\s\'\-\.\,\(\)éè]+$', capital_note):
            capital_note = ""

        result.append({
            "code": code,
            "name_ja": csv_entry["name_ja"],     # CSV由来の略称
            "name_en": csv_entry["name_en"],
            "formal_ja": formal_ja,               # 外務省正式名称
            "formal_en": formal_en,
            "capital": capital,
            "capital_note": capital_note,
            "region": csv_entry["region"],
            "mofa_region": mofa_region,
            "status": csv_entry["status"],
            "update_date": update_date,
            "has_mofa": bool(formal_ja),
        })

    # code 順にソート
    result.sort(key=lambda x: x["code"])

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    mofa_count = sum(1 for r in result if r["has_mofa"])
    print(f"✅ 生成完了: {OUT_JSON}")
    print(f"   全{len(result)}件（MOFA情報あり: {mofa_count}件）")


if __name__ == "__main__":
    main()
