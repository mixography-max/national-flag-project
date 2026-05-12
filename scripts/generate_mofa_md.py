#!/usr/bin/env python3
"""収集済みデータから外務省 国・地域一覧 Markdown を生成する"""
import json, time
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "06_docs"
JSON_PATH = OUT_DIR / "mofa_countries.json"
MD_PATH   = OUT_DIR / "mofa_countries.md"

# ── 収集済みデータ（TSV形式）──
# slug \t 正式名称（和文） \t 正式名称（英語） \t 首都 \t 備考 \t 更新日
RAW = r"""
#アジア
india	インド（ヒンディー語：バーラト）	India (Hindi: Bharat)	ニューデリー		令和6年8月1日
indonesia	インドネシア共和国	Republic of Indonesia	ジャカルタ		令和6年10月8日
cambodia	カンボジア王国	Kingdom of Cambodia	プノンペン		令和6年11月14日
singapore	シンガポール共和国	Republic of Singapore	シンガポール	都市国家	令和6年6月3日
srilanka	スリランカ民主社会主義共和国	Democratic Socialist Republic of Sri Lanka	スリ・ジャヤワルダナプラ・コッテ		令和6年11月22日
thailand	タイ王国	Kingdom of Thailand	バンコク		令和6年10月30日
korea	大韓民国	Republic of Korea	ソウル		令和6年12月19日
china	中華人民共和国	People's Republic of China	北京		令和6年9月10日
nepal	ネパール連邦民主共和国	Federal Democratic Republic of Nepal	カトマンズ		令和6年6月3日
pakistan	パキスタン・イスラム共和国	Islamic Republic of Pakistan	イスラマバード		令和6年6月11日
bangladesh	バングラデシュ人民共和国	People's Republic of Bangladesh	ダッカ		令和6年11月14日
easttimor	東ティモール民主共和国	The Democratic Republic of Timor-Leste	ディリ		令和6年6月3日
philippines	フィリピン共和国	Republic of the Philippines	マニラ		令和6年9月30日
bhutan	ブータン王国	Kingdom of Bhutan	ティンプー		令和6年6月3日
brunei	ブルネイ・ダルサラーム国	Brunei Darussalam	バンダルスリブガワン		令和6年6月3日
vietnam	ベトナム社会主義共和国	Socialist Republic of Viet Nam	ハノイ		令和6年11月14日
malaysia	マレーシア	Malaysia	クアラルンプール		令和6年6月3日
myanmar	ミャンマー連邦共和国	Republic of the Union of Myanmar	ネーピードー		令和6年8月27日
maldives	モルディブ共和国	Republic of Maldives	マレ		令和6年6月3日
mongolia	モンゴル国	Mongolia	ウランバートル		令和6年10月8日
laos	ラオス人民民主共和国	Lao People's Democratic Republic	ビエンチャン		令和6年6月3日
n_korea	朝鮮民主主義人民共和国	Democratic People's Republic of Korea	平壌		令和6年6月3日
taiwan	台湾		台北	日本国との間に外交関係なし	
#大洋州
australia	オーストラリア連邦	Commonwealth of Australia	キャンベラ		令和6年11月20日
kiribati	キリバス共和国	Republic of Kiribati	タラワ		令和6年6月3日
cook	クック諸島	Cook Islands	アバルア		令和6年6月3日
samoa	サモア独立国	Independent State of Samoa	アピア		令和6年6月3日
solomon	ソロモン諸島	Solomon Islands	ホニアラ		令和6年6月3日
tuvalu	ツバル	Tuvalu	フナフティ		令和6年6月3日
tonga	トンガ王国	Kingdom of Tonga	ヌクアロファ		令和6年6月3日
nauru	ナウル共和国	Republic of Nauru	ヤレン		令和6年6月3日
niue	ニウエ	Niue	アロフィ		令和6年6月3日
nz	ニュージーランド	New Zealand	ウェリントン		令和6年6月3日
vanuatu	バヌアツ共和国	Republic of Vanuatu	ポートビラ		令和6年6月3日
png	パプアニューギニア独立国	Independent State of Papua New Guinea	ポートモレスビー		令和6年6月3日
palau	パラオ共和国	Republic of Palau	マルキョク		令和6年6月3日
fiji	フィジー共和国	Republic of Fiji	スバ		令和6年6月3日
marshall	マーシャル諸島共和国	Republic of the Marshall Islands	マジュロ		令和6年6月3日
micronesia	ミクロネシア連邦	Federated States of Micronesia	パリキール		令和6年6月3日
#北米
usa	アメリカ合衆国	United States of America	ワシントンD.C.		令和7年2月3日
canada	カナダ	Canada	オタワ		令和6年11月11日
#中南米
argentine	アルゼンチン共和国	Argentine Republic	ブエノスアイレス		令和6年6月3日
antigua	アンティグア・バーブーダ	Antigua and Barbuda	セントジョンズ		令和6年6月3日
uruguay	ウルグアイ東方共和国	Oriental Republic of Uruguay	モンテビデオ		令和6年6月3日
ecuador	エクアドル共和国	Republic of Ecuador	キト		令和6年6月3日
elsalvador	エルサルバドル共和国	Republic of El Salvador	サンサルバドル		令和6年6月3日
guyana	ガイアナ共同共和国	Co-operative Republic of Guyana	ジョージタウン		令和6年6月3日
cuba	キューバ共和国	Republic of Cuba	ハバナ		令和6年6月3日
guatemala	グアテマラ共和国	Republic of Guatemala	グアテマラシティ		令和6年6月3日
grenada	グレナダ	Grenada	セントジョージズ		令和6年6月3日
costarica	コスタリカ共和国	Republic of Costa Rica	サンホセ		令和6年6月3日
colombia	コロンビア共和国	Republic of Colombia	ボゴタ		令和6年6月3日
jamaica	ジャマイカ	Jamaica	キングストン		令和6年6月3日
suriname	スリナム共和国	Republic of Suriname	パラマリボ		令和6年6月3日
svg	セントビンセント及びグレナディーン諸島	Saint Vincent and the Grenadines	キングスタウン		令和6年6月3日
scn	セントクリストファー・ネービス	Federation of Saint Christopher and Nevis	バセテール		令和6年6月3日
s_lucia	セントルシア	Saint Lucia	カストリーズ		令和6年6月3日
chile	チリ共和国	Republic of Chile	サンティアゴ		令和6年6月3日
c_dominica	ドミニカ国	Commonwealth of Dominica	ロゾー		令和6年6月3日
dominican_r	ドミニカ共和国	Dominican Republic	サントドミンゴ		令和6年6月3日
trinidad	トリニダード・トバゴ共和国	Republic of Trinidad and Tobago	ポートオブスペイン		令和6年6月3日
nicaragua	ニカラグア共和国	Republic of Nicaragua	マナグア		令和6年8月1日
haiti	ハイチ共和国	Republic of Haiti	ポルトープランス		令和6年6月3日
panama	パナマ共和国	Republic of Panama	パナマシティ		令和6年6月3日
bahama	バハマ国	Commonwealth of The Bahamas	ナッソー		令和6年6月3日
paraguay	パラグアイ共和国	Republic of Paraguay	アスンシオン		令和6年6月3日
barbados	バルバドス	Barbados	ブリッジタウン		令和6年6月3日
brazil	ブラジル連邦共和国	Federative Republic of Brazil	ブラジリア		令和6年6月3日
venezuela	ベネズエラ・ボリバル共和国	Bolivarian Republic of Venezuela	カラカス		令和6年6月3日
belize	ベリーズ	Belize	ベルモパン		令和6年6月3日
peru	ペルー共和国	Republic of Peru	リマ		令和6年6月3日
bolivia	ボリビア多民族国	Plurinational State of Bolivia	ラパス	憲法上の首都はスクレ	令和6年8月1日
honduras	ホンジュラス共和国	Republic of Honduras	テグシガルパ		令和6年6月3日
mexico	メキシコ合衆国	United Mexican States	メキシコシティ		令和6年11月5日
#欧州
iceland	アイスランド共和国	Republic of Iceland	レイキャビク		令和6年6月3日
ireland	アイルランド	Ireland	ダブリン		令和6年6月3日
azerbaijan	アゼルバイジャン共和国	Republic of Azerbaijan	バクー		令和6年11月12日
albania	アルバニア共和国	Republic of Albania	ティラナ		令和6年6月3日
armenia	アルメニア共和国	Republic of Armenia	エレバン		令和6年6月3日
andorra	アンドラ公国	Principality of Andorra	アンドラ・ラ・ベリャ		令和6年6月3日
italy	イタリア共和国	Italian Republic	ローマ		令和6年10月28日
ukraine	ウクライナ	Ukraine	キーウ		令和7年3月4日
uzbekistan	ウズベキスタン共和国	Republic of Uzbekistan	タシケント		令和6年11月14日
uk	グレートブリテン及び北アイルランド連合王国（英国）	United Kingdom of Great Britain and Northern Ireland	ロンドン		令和7年1月16日
estonia	エストニア共和国	Republic of Estonia	タリン		令和6年6月3日
austria	オーストリア共和国	Republic of Austria	ウィーン		令和6年6月3日
netherlands	オランダ王国	Kingdom of the Netherlands	アムステルダム	憲法上の首都。政府所在地はハーグ	令和6年6月17日
kazakhstan	カザフスタン共和国	Republic of Kazakhstan	アスタナ		令和6年7月5日
macedonia	北マケドニア共和国	Republic of North Macedonia	スコピエ		令和6年6月3日
cyprus	キプロス共和国	Republic of Cyprus	ニコシア		令和6年6月3日
greece	ギリシャ共和国	Hellenic Republic	アテネ		令和6年6月3日
kyrgyz	キルギス共和国	Kyrgyz Republic	ビシュケク		令和6年6月3日
croatia	クロアチア共和国	Republic of Croatia	ザグレブ		令和6年6月3日
kosovo	コソボ共和国	Republic of Kosovo	プリシュティナ		令和6年6月3日
sanmarino_r	サンマリノ共和国	Republic of San Marino	サンマリノ		令和6年6月3日
georgia	ジョージア	Georgia	トビリシ		令和6年6月3日
switzerland	スイス連邦	Swiss Confederation	ベルン		令和6年9月12日
sweden	スウェーデン王国	Kingdom of Sweden	ストックホルム		令和6年6月3日
spain	スペイン王国	Kingdom of Spain	マドリード		令和6年6月3日
slovak	スロバキア共和国	Slovak Republic	ブラチスラバ		令和6年6月3日
slovenia	スロベニア共和国	Republic of Slovenia	リュブリャナ		令和6年6月3日
serbia	セルビア共和国	Republic of Serbia	ベオグラード		令和6年6月3日
tajikistan	タジキスタン共和国	Republic of Tajikistan	ドゥシャンベ		令和6年6月3日
czech	チェコ共和国	Czech Republic	プラハ		令和6年6月3日
denmark	デンマーク王国	Kingdom of Denmark	コペンハーゲン		令和6年6月3日
germany	ドイツ連邦共和国	Federal Republic of Germany	ベルリン		令和6年10月21日
turkmenistan	トルクメニスタン	Turkmenistan	アシガバット		令和6年6月3日
norway	ノルウェー王国	Kingdom of Norway	オスロ		令和6年6月3日
vatican	バチカン市国	Vatican City State	バチカン		令和6年6月3日
hungary	ハンガリー	Hungary	ブダペスト		令和6年6月3日
finland	フィンランド共和国	Republic of Finland	ヘルシンキ		令和6年6月3日
france	フランス共和国	French Republic	パリ		令和6年9月18日
bulgaria	ブルガリア共和国	Republic of Bulgaria	ソフィア		令和6年6月3日
belarus	ベラルーシ共和国	Republic of Belarus	ミンスク		令和6年6月3日
belgium	ベルギー王国	Kingdom of Belgium	ブリュッセル		令和6年6月3日
poland	ポーランド共和国	Republic of Poland	ワルシャワ		令和6年6月3日
bosnia_h	ボスニア・ヘルツェゴビナ	Bosnia and Herzegovina	サラエボ		令和6年6月3日
portugal	ポルトガル共和国	Portuguese Republic	リスボン		令和6年6月3日
malta	マルタ共和国	Republic of Malta	バレッタ		令和6年6月3日
monaco	モナコ公国	Principality of Monaco	モナコ		令和6年6月3日
moldova	モルドバ共和国	Republic of Moldova	キシナウ		令和6年6月3日
montenegro	モンテネグロ	Montenegro	ポドゴリツァ		令和6年6月3日
latvia	ラトビア共和国	Republic of Latvia	リガ		令和6年6月3日
liechtenstein	リヒテンシュタイン公国	Principality of Liechtenstein	ファドゥーツ		令和6年6月3日
lithuania	リトアニア共和国	Republic of Lithuania	ビリニュス		令和6年6月3日
romania	ルーマニア	Romania	ブカレスト		令和6年6月3日
luxembourg	ルクセンブルク大公国	Grand Duchy of Luxembourg	ルクセンブルク		令和6年6月3日
russia	ロシア連邦	Russian Federation	モスクワ		令和6年6月3日
#中東
afghanistan	アフガニスタン・イスラム共和国	Islamic Republic of Afghanistan	カブール		令和6年6月3日
uae	アラブ首長国連邦	United Arab Emirates	アブダビ		令和6年9月24日
yemen	イエメン共和国	Republic of Yemen	サヌア		令和6年6月3日
israel	イスラエル国	State of Israel	エルサレム	日本は東エルサレムの地位について国際法上未確定との立場	令和6年12月26日
iraq	イラク共和国	Republic of Iraq	バグダッド		令和6年6月3日
iran	イラン・イスラム共和国	Islamic Republic of Iran	テヘラン		令和6年6月3日
oman	オマーン国	Sultanate of Oman	マスカット		令和6年6月3日
qatar	カタール国	State of Qatar	ドーハ		令和6年11月5日
kuwait	クウェート国	State of Kuwait	クウェート		令和6年6月3日
saudi	サウジアラビア王国	Kingdom of Saudi Arabia	リヤド		令和6年6月3日
syria	シリア・アラブ共和国	Syrian Arab Republic	ダマスカス		令和7年2月12日
turkey	トルコ共和国	Republic of Türkiye	アンカラ		令和6年6月6日
bahrain	バーレーン王国	Kingdom of Bahrain	マナーマ		令和6年6月3日
jordan	ヨルダン・ハシェミット王国	Hashemite Kingdom of Jordan	アンマン		令和6年6月3日
lebanon	レバノン共和国	Lebanese Republic	ベイルート		令和6年11月5日
plo	パレスチナ	Palestine	ラマッラ	（西岸地区）	令和6年11月26日
#アフリカ
algeria	アルジェリア民主人民共和国	People's Democratic Republic of Algeria	アルジェ		令和6年6月3日
angola	アンゴラ共和国	Republic of Angola	ルアンダ		令和6年6月3日
uganda	ウガンダ共和国	Republic of Uganda	カンパラ		令和6年6月3日
egypt	エジプト・アラブ共和国	Arab Republic of Egypt	カイロ		令和6年6月6日
eswatini	エスワティニ王国	Kingdom of Eswatini	ムババネ	行政上の首都。立法上の首都はロバンバ	令和6年6月3日
ethiopia	エチオピア連邦民主共和国	Federal Democratic Republic of Ethiopia	アディスアベバ		令和6年6月3日
eritrea	エリトリア国	State of Eritrea	アスマラ		令和6年6月3日
ghana	ガーナ共和国	Republic of Ghana	アクラ		令和6年6月3日
capeverde	カーボベルデ共和国	Republic of Cabo Verde	プライア		令和6年6月3日
gabon	ガボン共和国	Gabonese Republic	リーブルビル		令和6年6月3日
cameroon	カメルーン共和国	Republic of Cameroon	ヤウンデ		令和6年6月3日
gambia	ガンビア共和国	Republic of The Gambia	バンジュール		令和6年6月3日
guinea	ギニア共和国	Republic of Guinea	コナクリ		令和6年6月3日
guinea_b	ギニアビサウ共和国	Republic of Guinea-Bissau	ビサウ		令和6年6月3日
kenya	ケニア共和国	Republic of Kenya	ナイロビ		令和6年11月14日
cote_d	コートジボワール共和国	Republic of Côte d'Ivoire	ヤムスクロ	政治上の実質的首都はアビジャン	令和6年6月3日
comoros	コモロ連合	Union of the Comoros	モロニ		令和6年6月3日
congokyo	コンゴ共和国	Republic of the Congo	ブラザビル		令和6年6月3日
congomin	コンゴ民主共和国	Democratic Republic of the Congo	キンシャサ		令和6年6月3日
stp	サントメ・プリンシペ民主共和国	Democratic Republic of São Tomé and Príncipe	サントメ		令和6年6月3日
zambia	ザンビア共和国	Republic of Zambia	ルサカ		令和6年6月3日
s_leone	シエラレオネ共和国	Republic of Sierra Leone	フリータウン		令和6年6月3日
djibouti	ジブチ共和国	Republic of Djibouti	ジブチ		令和6年6月3日
zimbabwe	ジンバブエ共和国	Republic of Zimbabwe	ハラレ		令和6年6月3日
sudan	スーダン共和国	Republic of the Sudan	ハルツーム		令和6年6月3日
seychelles	セーシェル共和国	Republic of Seychelles	ビクトリア		令和6年6月3日
eq_guinea	赤道ギニア共和国	Republic of Equatorial Guinea	マラボ		令和6年6月3日
senegal	セネガル共和国	Republic of Senegal	ダカール		令和6年6月3日
somali	ソマリア連邦共和国	Federal Republic of Somalia	モガディシュ		令和6年6月3日
tanzania	タンザニア連合共和国	United Republic of Tanzania	ドドマ		令和6年11月14日
chad	チャド共和国	Republic of Chad	ンジャメナ		令和6年6月3日
car	中央アフリカ共和国	Central African Republic	バンギ		令和6年6月3日
tunisia	チュニジア共和国	Republic of Tunisia	チュニス		令和6年6月3日
togo	トーゴ共和国	Togolese Republic	ロメ		令和6年6月3日
nigeria	ナイジェリア連邦共和国	Federal Republic of Nigeria	アブジャ		令和6年6月3日
namibia	ナミビア共和国	Republic of Namibia	ウィントフック		令和6年6月3日
niger	ニジェール共和国	Republic of Niger	ニアメ		令和6年6月3日
burkina	ブルキナファソ	Burkina Faso	ワガドゥグー		令和6年6月3日
brundi	ブルンジ共和国	Republic of Burundi	ギテガ		令和6年6月3日
benin	ベナン共和国	Republic of Benin	ポルトノボ	事実上の首都はコトヌー	令和6年6月3日
botswana	ボツワナ共和国	Republic of Botswana	ハボローネ		令和6年6月3日
madagascar	マダガスカル共和国	Republic of Madagascar	アンタナナリボ		令和6年6月3日
malawi	マラウイ共和国	Republic of Malawi	リロングウェ		令和6年6月3日
mali	マリ共和国	Republic of Mali	バマコ		令和6年6月3日
s_africa	南アフリカ共和国	Republic of South Africa	プレトリア	行政府所在地。立法府所在地はケープタウン、司法府所在地はブルームフォンテーン	令和6年6月3日
s_sudan	南スーダン共和国	Republic of South Sudan	ジュバ		令和6年6月3日
mozambique	モザンビーク共和国	Republic of Mozambique	マプト		令和6年6月3日
mauritius	モーリシャス共和国	Republic of Mauritius	ポートルイス		令和6年6月3日
mauritania	モーリタニア・イスラム共和国	Islamic Republic of Mauritania	ヌアクショット		令和6年6月3日
morocco	モロッコ王国	Kingdom of Morocco	ラバト		令和6年6月3日
libya	リビア	Libya	トリポリ		令和6年6月3日
liberia	リベリア共和国	Republic of Liberia	モンロビア		令和6年6月3日
rwanda	ルワンダ共和国	Republic of Rwanda	キガリ		令和6年6月3日
lesotho	レソト王国	Kingdom of Lesotho	マセル		令和6年6月3日
"""

def parse_raw():
    entries = []
    region = ""
    for line in RAW.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            region = line[1:]
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        entries.append({
            "slug": parts[0],
            "region": region,
            "formal_name_ja": parts[1],
            "formal_name_en": parts[2],
            "capital": parts[3],
            "capital_note": parts[4] if len(parts) > 4 else "",
            "update_date": parts[5] if len(parts) > 5 else "",
            "url": f"https://www.mofa.go.jp/mofaj/area/{parts[0]}/data.html",
        })
    return entries

def save_json(entries):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON: {JSON_PATH} ({len(entries)}件)")

def save_md(entries):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# 外務省「国・地域」基礎データ一覧")
    lines.append("")
    lines.append("> **出典**: [外務省「国・地域」](https://www.mofa.go.jp/mofaj/area/index.html)  ")
    lines.append(f"> **収集日**: 2026-05-12")
    lines.append("")
    lines.append(f"全 **{len(entries)}** カ国・地域")
    lines.append("")

    current_region = None
    idx = 0
    for entry in entries:
        region = entry["region"]
        if region != current_region:
            current_region = region
            n = sum(1 for e in entries if e["region"] == region)
            if idx > 0:
                lines.append("")
            lines.append(f"## {region}（{n}カ国・地域）")
            lines.append("")
            lines.append("| # | 正式名称（和文） | 正式名称（英語） | 首都 | 備考 | 最終更新日 |")
            lines.append("|--:|:--|:--|:--|:--|:--|")
            idx = 0

        idx += 1
        ja = entry["formal_name_ja"]
        en = entry["formal_name_en"]
        cap = entry["capital"]
        note = entry["capital_note"]
        date = entry["update_date"]
        lines.append(f"| {idx} | {ja} | {en} | {cap} | {note} | {date} |")

    lines.append("")
    lines.append("---")
    lines.append("*このファイルは `scripts/generate_mofa_md.py` により自動生成されました。*")

    md_text = "\n".join(lines)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"✅ Markdown: {MD_PATH}")

if __name__ == "__main__":
    entries = parse_raw()
    save_json(entries)
    save_md(entries)
