#!/usr/bin/env python3
"""
外務省ウェブサイトから国・地域の基礎データを収集するスクリプト
（ブラウザ経由で取得したHTMLファイルを解析する用）

使い方:
1. ブラウザで各国のdata.htmlを保存
2. このスクリプトで解析

このファイルは、ブラウザ経由で取得したデータの一覧を管理するために使用
"""

# 全地域の国スラッグ一覧（非国家エンティティを除外済み）
REGIONS = {
    "アジア": [
        "india", "indonesia", "cambodia", "singapore", "srilanka",
        "thailand", "korea", "china", "nepal", "pakistan",
        "bangladesh", "easttimor", "philippines", "bhutan", "brunei",
        "vietnam", "malaysia", "myanmar", "maldives", "mongolia",
        "laos", "n_korea", "taiwan",
    ],
    "大洋州": [
        "australia", "kiribati", "cook", "samoa", "solomon",
        "tuvalu", "tonga", "nauru", "niue", "nz",
        "vanuatu", "png", "palau", "fiji", "marshall", "micronesia",
    ],
    "北米": [
        "usa", "canada",
    ],
    "中南米": [
        "argentine", "antigua", "uruguay", "ecuador", "elsalvador",
        "guyana", "cuba", "guatemala", "grenada", "costarica",
        "colombia", "jamaica", "suriname", "svg", "scn",
        "s_lucia", "chile", "c_dominica", "dominican_r", "trinidad",
        "nicaragua", "haiti", "panama", "bahama", "paraguay",
        "barbados", "brazil", "venezuela", "belize", "peru",
        "bolivia", "honduras", "mexico",
    ],
    "欧州": [
        "iceland", "ireland", "azerbaijan", "albania", "armenia",
        "andorra", "italy", "ukraine", "uzbekistan", "uk",
        "estonia", "austria", "netherlands", "kazakhstan", "macedonia",
        "cyprus", "greece", "kyrgyz", "croatia", "kosovo",
        "sanmarino_r", "georgia", "switzerland", "sweden", "spain",
        "slovak", "slovenia", "serbia", "tajikistan", "czech",
        "denmark", "germany", "turkmenistan", "norway", "vatican",
        "hungary", "finland", "france", "bulgaria", "belarus",
        "belgium", "poland", "bosnia_h", "portugal", "malta",
        "monaco", "moldova", "montenegro", "latvia", "liechtenstein",
        "lithuania", "romania", "luxembourg", "russia",
    ],
    "中東": [
        "afghanistan", "uae", "yemen", "israel", "iraq",
        "iran", "oman", "qatar", "kuwait", "saudi",
        "syria", "turkey", "bahrain", "jordan", "lebanon", "plo",
    ],
    "アフリカ": [
        "algeria", "angola", "uganda", "egypt", "eswatini",
        "ethiopia", "eritrea", "ghana", "capeverde", "gabon",
        "cameroon", "gambia", "guinea", "guinea_b", "kenya",
        "cote_d", "comoros", "congokyo", "congomin", "stp",
        "zambia", "s_leone", "djibouti", "zimbabwe", "sudan",
        "seychelles", "eq_guinea", "senegal", "somali", "tanzania",
        "chad", "car", "tunisia", "togo", "nigeria",
        "namibia", "niger", "burkina", "brundi", "benin",
        "botswana", "madagascar", "malawi", "mali", "s_africa",
        "s_sudan", "mozambique", "mauritius", "mauritania", "morocco",
        "libya", "liberia", "rwanda", "lesotho",
    ],
}

def get_all_slugs():
    """全スラッグをフラットなリストで返す"""
    all_slugs = []
    for region, slugs in REGIONS.items():
        for slug in slugs:
            all_slugs.append((region, slug))
    return all_slugs

def get_data_url(slug):
    """スラッグからdata.htmlのURLを生成"""
    return f"https://www.mofa.go.jp/mofaj/area/{slug}/data.html"

if __name__ == "__main__":
    all_countries = get_all_slugs()
    print(f"合計: {len(all_countries)} カ国・地域")
    for region, slug in all_countries:
        print(f"  {region}: {slug} -> {get_data_url(slug)}")
