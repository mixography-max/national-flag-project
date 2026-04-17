#!/usr/bin/env python3
"""
ISO 3166-1 全249エントリ + UN M49地域分類のマスターCSV生成スクリプト
各エントリにWikipedia国旗SVGファイル名を付与する
"""
import csv
import os

# ISO 3166-1 全249エントリ
# Format: (alpha2, alpha3, numeric, name_en, name_ja, un_m49_region, un_m49_subregion, status, ratio, wiki_flag_filename)
# status: "UN Member", "UN Observer", "Territory", "Disputed", "Special"
# ratio: 公式アスペクト比 (height:width)

COUNTRIES = [
    # ========== アジア / Asia ==========
    # --- 東アジア / Eastern Asia ---
    ("CN", "CHN", "156", "China", "中国", "Asia", "Eastern Asia", "UN Member", "2:3", "Flag_of_the_People's_Republic_of_China.svg"),
    ("HK", "HKG", "344", "Hong Kong", "香港", "Asia", "Eastern Asia", "Territory", "2:3", "Flag_of_Hong_Kong.svg"),
    ("MO", "MAC", "446", "Macao", "マカオ", "Asia", "Eastern Asia", "Territory", "2:3", "Flag_of_Macau.svg"),
    ("JP", "JPN", "392", "Japan", "日本", "Asia", "Eastern Asia", "UN Member", "2:3", "Flag_of_Japan.svg"),
    ("KP", "PRK", "408", "North Korea", "北朝鮮", "Asia", "Eastern Asia", "UN Member", "1:2", "Flag_of_North_Korea.svg"),
    ("KR", "KOR", "410", "South Korea", "韓国", "Asia", "Eastern Asia", "UN Member", "2:3", "Flag_of_South_Korea.svg"),
    ("MN", "MNG", "496", "Mongolia", "モンゴル", "Asia", "Eastern Asia", "UN Member", "1:2", "Flag_of_Mongolia.svg"),
    ("TW", "TWN", "158", "Taiwan", "台湾", "Asia", "Eastern Asia", "Special", "2:3", "Flag_of_the_Republic_of_China.svg"),

    # --- 東南アジア / South-Eastern Asia ---
    ("BN", "BRN", "096", "Brunei", "ブルネイ", "Asia", "South-Eastern Asia", "UN Member", "1:2", "Flag_of_Brunei.svg"),
    ("KH", "KHM", "116", "Cambodia", "カンボジア", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Cambodia.svg"),
    ("ID", "IDN", "360", "Indonesia", "インドネシア", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Indonesia.svg"),
    ("LA", "LAO", "418", "Laos", "ラオス", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Laos.svg"),
    ("MY", "MYS", "458", "Malaysia", "マレーシア", "Asia", "South-Eastern Asia", "UN Member", "1:2", "Flag_of_Malaysia.svg"),
    ("MM", "MMR", "104", "Myanmar", "ミャンマー", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Myanmar.svg"),
    ("PH", "PHL", "608", "Philippines", "フィリピン", "Asia", "South-Eastern Asia", "UN Member", "1:2", "Flag_of_the_Philippines.svg"),
    ("SG", "SGP", "702", "Singapore", "シンガポール", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Singapore.svg"),
    ("TH", "THA", "764", "Thailand", "タイ", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Thailand.svg"),
    ("TL", "TLS", "626", "Timor-Leste", "東ティモール", "Asia", "South-Eastern Asia", "UN Member", "1:2", "Flag_of_East_Timor.svg"),
    ("VN", "VNM", "704", "Viet Nam", "ベトナム", "Asia", "South-Eastern Asia", "UN Member", "2:3", "Flag_of_Vietnam.svg"),

    # --- 南アジア / Southern Asia ---
    ("AF", "AFG", "004", "Afghanistan", "アフガニスタン", "Asia", "Southern Asia", "UN Member", "2:3", "Flag_of_Afghanistan.svg"),
    ("BD", "BGD", "050", "Bangladesh", "バングラデシュ", "Asia", "Southern Asia", "UN Member", "3:5", "Flag_of_Bangladesh.svg"),
    ("BT", "BTN", "064", "Bhutan", "ブータン", "Asia", "Southern Asia", "UN Member", "2:3", "Flag_of_Bhutan.svg"),
    ("IN", "IND", "356", "India", "インド", "Asia", "Southern Asia", "UN Member", "2:3", "Flag_of_India.svg"),
    ("IR", "IRN", "364", "Iran", "イラン", "Asia", "Southern Asia", "UN Member", "4:7", "Flag_of_Iran.svg"),
    ("MV", "MDV", "462", "Maldives", "モルディブ", "Asia", "Southern Asia", "UN Member", "2:3", "Flag_of_Maldives.svg"),
    ("NP", "NPL", "524", "Nepal", "ネパール", "Asia", "Southern Asia", "UN Member", "special", "Flag_of_Nepal.svg"),
    ("PK", "PAK", "586", "Pakistan", "パキスタン", "Asia", "Southern Asia", "UN Member", "2:3", "Flag_of_Pakistan.svg"),
    ("LK", "LKA", "144", "Sri Lanka", "スリランカ", "Asia", "Southern Asia", "UN Member", "1:2", "Flag_of_Sri_Lanka.svg"),

    # --- 中央アジア / Central Asia ---
    ("KZ", "KAZ", "398", "Kazakhstan", "カザフスタン", "Asia", "Central Asia", "UN Member", "1:2", "Flag_of_Kazakhstan.svg"),
    ("KG", "KGZ", "417", "Kyrgyzstan", "キルギス", "Asia", "Central Asia", "UN Member", "3:5", "Flag_of_Kyrgyzstan.svg"),
    ("TJ", "TJK", "762", "Tajikistan", "タジキスタン", "Asia", "Central Asia", "UN Member", "1:2", "Flag_of_Tajikistan.svg"),
    ("TM", "TKM", "795", "Turkmenistan", "トルクメニスタン", "Asia", "Central Asia", "UN Member", "2:3", "Flag_of_Turkmenistan.svg"),
    ("UZ", "UZB", "860", "Uzbekistan", "ウズベキスタン", "Asia", "Central Asia", "UN Member", "1:2", "Flag_of_Uzbekistan.svg"),

    # --- 西アジア / Western Asia ---
    ("AM", "ARM", "051", "Armenia", "アルメニア", "Asia", "Western Asia", "UN Member", "1:2", "Flag_of_Armenia.svg"),
    ("AZ", "AZE", "031", "Azerbaijan", "アゼルバイジャン", "Asia", "Western Asia", "UN Member", "1:2", "Flag_of_Azerbaijan.svg"),
    ("BH", "BHR", "048", "Bahrain", "バーレーン", "Asia", "Western Asia", "UN Member", "3:5", "Flag_of_Bahrain.svg"),
    ("CY", "CYP", "196", "Cyprus", "キプロス", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Cyprus.svg"),
    ("GE", "GEO", "268", "Georgia", "ジョージア", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Georgia.svg"),
    ("IQ", "IRQ", "368", "Iraq", "イラク", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Iraq.svg"),
    ("IL", "ISR", "376", "Israel", "イスラエル", "Asia", "Western Asia", "UN Member", "8:11", "Flag_of_Israel.svg"),
    ("JO", "JOR", "400", "Jordan", "ヨルダン", "Asia", "Western Asia", "UN Member", "1:2", "Flag_of_Jordan.svg"),
    ("KW", "KWT", "414", "Kuwait", "クウェート", "Asia", "Western Asia", "UN Member", "1:2", "Flag_of_Kuwait.svg"),
    ("LB", "LBN", "422", "Lebanon", "レバノン", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Lebanon.svg"),
    ("OM", "OMN", "512", "Oman", "オマーン", "Asia", "Western Asia", "UN Member", "1:2", "Flag_of_Oman.svg"),
    ("PS", "PSE", "275", "Palestine", "パレスチナ", "Asia", "Western Asia", "UN Observer", "1:2", "Flag_of_Palestine.svg"),
    ("QA", "QAT", "634", "Qatar", "カタール", "Asia", "Western Asia", "UN Member", "11:28", "Flag_of_Qatar.svg"),
    ("SA", "SAU", "682", "Saudi Arabia", "サウジアラビア", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Saudi_Arabia.svg"),
    ("SY", "SYR", "760", "Syria", "シリア", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Syria.svg"),
    ("TR", "TUR", "792", "Türkiye", "トルコ", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Turkey.svg"),
    ("AE", "ARE", "784", "United Arab Emirates", "アラブ首長国連邦", "Asia", "Western Asia", "UN Member", "1:2", "Flag_of_the_United_Arab_Emirates.svg"),
    ("YE", "YEM", "887", "Yemen", "イエメン", "Asia", "Western Asia", "UN Member", "2:3", "Flag_of_Yemen.svg"),

    # ========== ヨーロッパ / Europe ==========
    # --- 西ヨーロッパ / Western Europe ---
    ("AT", "AUT", "040", "Austria", "オーストリア", "Europe", "Western Europe", "UN Member", "2:3", "Flag_of_Austria.svg"),
    ("BE", "BEL", "056", "Belgium", "ベルギー", "Europe", "Western Europe", "UN Member", "13:15", "Flag_of_Belgium.svg"),
    ("FR", "FRA", "250", "France", "フランス", "Europe", "Western Europe", "UN Member", "2:3", "Flag_of_France.svg"),
    ("DE", "DEU", "276", "Germany", "ドイツ", "Europe", "Western Europe", "UN Member", "3:5", "Flag_of_Germany.svg"),
    ("LI", "LIE", "438", "Liechtenstein", "リヒテンシュタイン", "Europe", "Western Europe", "UN Member", "3:5", "Flag_of_Liechtenstein.svg"),
    ("LU", "LUX", "442", "Luxembourg", "ルクセンブルク", "Europe", "Western Europe", "UN Member", "3:5", "Flag_of_Luxembourg.svg"),
    ("MC", "MCO", "492", "Monaco", "モナコ", "Europe", "Western Europe", "UN Member", "4:5", "Flag_of_Monaco.svg"),
    ("NL", "NLD", "528", "Netherlands", "オランダ", "Europe", "Western Europe", "UN Member", "2:3", "Flag_of_the_Netherlands.svg"),
    ("CH", "CHE", "756", "Switzerland", "スイス", "Europe", "Western Europe", "UN Member", "1:1", "Flag_of_Switzerland.svg"),

    # --- 北ヨーロッパ / Northern Europe ---
    ("AX", "ALA", "248", "Åland Islands", "オーランド諸島", "Europe", "Northern Europe", "Territory", "17:26", "Flag_of_Åland.svg"),
    ("DK", "DNK", "208", "Denmark", "デンマーク", "Europe", "Northern Europe", "UN Member", "28:37", "Flag_of_Denmark.svg"),
    ("EE", "EST", "233", "Estonia", "エストニア", "Europe", "Northern Europe", "UN Member", "7:11", "Flag_of_Estonia.svg"),
    ("FO", "FRO", "234", "Faroe Islands", "フェロー諸島", "Europe", "Northern Europe", "Territory", "8:11", "Flag_of_the_Faroe_Islands.svg"),
    ("FI", "FIN", "246", "Finland", "フィンランド", "Europe", "Northern Europe", "UN Member", "11:18", "Flag_of_Finland.svg"),
    ("GG", "GGY", "831", "Guernsey", "ガーンジー", "Europe", "Northern Europe", "Territory", "2:3", "Flag_of_Guernsey.svg"),
    ("IS", "ISL", "352", "Iceland", "アイスランド", "Europe", "Northern Europe", "UN Member", "18:25", "Flag_of_Iceland.svg"),
    ("IE", "IRL", "372", "Ireland", "アイルランド", "Europe", "Northern Europe", "UN Member", "1:2", "Flag_of_Ireland.svg"),
    ("IM", "IMN", "833", "Isle of Man", "マン島", "Europe", "Northern Europe", "Territory", "1:2", "Flag_of_the_Isle_of_Man.svg"),
    ("JE", "JEY", "832", "Jersey", "ジャージー", "Europe", "Northern Europe", "Territory", "3:5", "Flag_of_Jersey.svg"),
    ("LV", "LVA", "428", "Latvia", "ラトビア", "Europe", "Northern Europe", "UN Member", "1:2", "Flag_of_Latvia.svg"),
    ("LT", "LTU", "440", "Lithuania", "リトアニア", "Europe", "Northern Europe", "UN Member", "3:5", "Flag_of_Lithuania.svg"),
    ("NO", "NOR", "578", "Norway", "ノルウェー", "Europe", "Northern Europe", "UN Member", "8:11", "Flag_of_Norway.svg"),
    ("SJ", "SJM", "744", "Svalbard and Jan Mayen", "スヴァールバル諸島およびヤンマイエン島", "Europe", "Northern Europe", "Territory", "8:11", "Flag_of_Norway.svg"),
    ("SE", "SWE", "752", "Sweden", "スウェーデン", "Europe", "Northern Europe", "UN Member", "5:8", "Flag_of_Sweden.svg"),
    ("GB", "GBR", "826", "United Kingdom", "イギリス", "Europe", "Northern Europe", "UN Member", "1:2", "Flag_of_the_United_Kingdom.svg"),

    # --- 南ヨーロッパ / Southern Europe ---
    ("AL", "ALB", "008", "Albania", "アルバニア", "Europe", "Southern Europe", "UN Member", "5:7", "Flag_of_Albania.svg"),
    ("AD", "AND", "020", "Andorra", "アンドラ", "Europe", "Southern Europe", "UN Member", "7:10", "Flag_of_Andorra.svg"),
    ("BA", "BIH", "070", "Bosnia and Herzegovina", "ボスニア・ヘルツェゴビナ", "Europe", "Southern Europe", "UN Member", "1:2", "Flag_of_Bosnia_and_Herzegovina.svg"),
    ("HR", "HRV", "191", "Croatia", "クロアチア", "Europe", "Southern Europe", "UN Member", "1:2", "Flag_of_Croatia.svg"),
    ("GI", "GIB", "292", "Gibraltar", "ジブラルタル", "Europe", "Southern Europe", "Territory", "1:2", "Flag_of_Gibraltar.svg"),
    ("GR", "GRC", "300", "Greece", "ギリシャ", "Europe", "Southern Europe", "UN Member", "2:3", "Flag_of_Greece.svg"),
    ("VA", "VAT", "336", "Holy See", "バチカン市国", "Europe", "Southern Europe", "UN Observer", "1:1", "Flag_of_the_Vatican_City.svg"),
    ("IT", "ITA", "380", "Italy", "イタリア", "Europe", "Southern Europe", "UN Member", "2:3", "Flag_of_Italy.svg"),
    ("XK", "XKX", "383", "Kosovo", "コソボ", "Europe", "Southern Europe", "Disputed", "5:7", "Flag_of_Kosovo.svg"),
    ("MT", "MLT", "470", "Malta", "マルタ", "Europe", "Southern Europe", "UN Member", "2:3", "Flag_of_Malta.svg"),
    ("ME", "MNE", "499", "Montenegro", "モンテネグロ", "Europe", "Southern Europe", "UN Member", "1:2", "Flag_of_Montenegro.svg"),
    ("MK", "MKD", "807", "North Macedonia", "北マケドニア", "Europe", "Southern Europe", "UN Member", "1:2", "Flag_of_North_Macedonia.svg"),
    ("PT", "PRT", "620", "Portugal", "ポルトガル", "Europe", "Southern Europe", "UN Member", "2:3", "Flag_of_Portugal.svg"),
    ("RS", "SRB", "688", "Serbia", "セルビア", "Europe", "Southern Europe", "UN Member", "2:3", "Flag_of_Serbia.svg"),
    ("SI", "SVN", "705", "Slovenia", "スロベニア", "Europe", "Southern Europe", "UN Member", "1:2", "Flag_of_Slovenia.svg"),
    ("ES", "ESP", "724", "Spain", "スペイン", "Europe", "Southern Europe", "UN Member", "2:3", "Flag_of_Spain.svg"),
    ("SM", "SMR", "674", "San Marino", "サンマリノ", "Europe", "Southern Europe", "UN Member", "3:4", "Flag_of_San_Marino.svg"),

    # --- 東ヨーロッパ / Eastern Europe ---
    ("BY", "BLR", "112", "Belarus", "ベラルーシ", "Europe", "Eastern Europe", "UN Member", "1:2", "Flag_of_Belarus.svg"),
    ("BG", "BGR", "100", "Bulgaria", "ブルガリア", "Europe", "Eastern Europe", "UN Member", "3:5", "Flag_of_Bulgaria.svg"),
    ("CZ", "CZE", "203", "Czechia", "チェコ", "Europe", "Eastern Europe", "UN Member", "2:3", "Flag_of_the_Czech_Republic.svg"),
    ("HU", "HUN", "348", "Hungary", "ハンガリー", "Europe", "Eastern Europe", "UN Member", "1:2", "Flag_of_Hungary.svg"),
    ("MD", "MDA", "498", "Moldova", "モルドバ", "Europe", "Eastern Europe", "UN Member", "1:2", "Flag_of_Moldova.svg"),
    ("PL", "POL", "616", "Poland", "ポーランド", "Europe", "Eastern Europe", "UN Member", "5:8", "Flag_of_Poland.svg"),
    ("RO", "ROU", "642", "Romania", "ルーマニア", "Europe", "Eastern Europe", "UN Member", "2:3", "Flag_of_Romania.svg"),
    ("RU", "RUS", "643", "Russia", "ロシア", "Europe", "Eastern Europe", "UN Member", "2:3", "Flag_of_Russia.svg"),
    ("SK", "SVK", "703", "Slovakia", "スロバキア", "Europe", "Eastern Europe", "UN Member", "2:3", "Flag_of_Slovakia.svg"),
    ("UA", "UKR", "804", "Ukraine", "ウクライナ", "Europe", "Eastern Europe", "UN Member", "2:3", "Flag_of_Ukraine.svg"),

    # ========== アフリカ / Africa ==========
    # --- 北アフリカ / Northern Africa ---
    ("DZ", "DZA", "012", "Algeria", "アルジェリア", "Africa", "Northern Africa", "UN Member", "2:3", "Flag_of_Algeria.svg"),
    ("EG", "EGY", "818", "Egypt", "エジプト", "Africa", "Northern Africa", "UN Member", "2:3", "Flag_of_Egypt.svg"),
    ("LY", "LBY", "434", "Libya", "リビア", "Africa", "Northern Africa", "UN Member", "1:2", "Flag_of_Libya.svg"),
    ("MA", "MAR", "504", "Morocco", "モロッコ", "Africa", "Northern Africa", "UN Member", "2:3", "Flag_of_Morocco.svg"),
    ("SD", "SDN", "729", "Sudan", "スーダン", "Africa", "Northern Africa", "UN Member", "1:2", "Flag_of_Sudan.svg"),
    ("TN", "TUN", "788", "Tunisia", "チュニジア", "Africa", "Northern Africa", "UN Member", "2:3", "Flag_of_Tunisia.svg"),
    ("EH", "ESH", "732", "Western Sahara", "西サハラ", "Africa", "Northern Africa", "Territory", "1:2", "Flag_of_the_Sahrawi_Arab_Democratic_Republic.svg"),

    # --- 西アフリカ / Western Africa ---
    ("BJ", "BEN", "204", "Benin", "ベナン", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Benin.svg"),
    ("BF", "BFA", "854", "Burkina Faso", "ブルキナファソ", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Burkina_Faso.svg"),
    ("CV", "CPV", "132", "Cabo Verde", "カーボベルデ", "Africa", "Western Africa", "UN Member", "10:17", "Flag_of_Cape_Verde.svg"),
    ("CI", "CIV", "384", "Côte d'Ivoire", "コートジボワール", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Côte_d'Ivoire.svg"),
    ("GM", "GMB", "270", "Gambia", "ガンビア", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_The_Gambia.svg"),
    ("GH", "GHA", "288", "Ghana", "ガーナ", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Ghana.svg"),
    ("GN", "GIN", "324", "Guinea", "ギニア", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Guinea.svg"),
    ("GW", "GNB", "624", "Guinea-Bissau", "ギニアビサウ", "Africa", "Western Africa", "UN Member", "1:2", "Flag_of_Guinea-Bissau.svg"),
    ("LR", "LBR", "430", "Liberia", "リベリア", "Africa", "Western Africa", "UN Member", "10:19", "Flag_of_Liberia.svg"),
    ("ML", "MLI", "466", "Mali", "マリ", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Mali.svg"),
    ("MR", "MRT", "478", "Mauritania", "モーリタニア", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Mauritania.svg"),
    ("NE", "NER", "562", "Niger", "ニジェール", "Africa", "Western Africa", "UN Member", "6:7", "Flag_of_Niger.svg"),
    ("NG", "NGA", "566", "Nigeria", "ナイジェリア", "Africa", "Western Africa", "UN Member", "1:2", "Flag_of_Nigeria.svg"),
    ("SN", "SEN", "686", "Senegal", "セネガル", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Senegal.svg"),
    ("SL", "SLE", "694", "Sierra Leone", "シエラレオネ", "Africa", "Western Africa", "UN Member", "2:3", "Flag_of_Sierra_Leone.svg"),
    ("SH", "SHN", "654", "Saint Helena, Ascension and Tristan da Cunha", "セントヘレナ・アセンションおよびトリスタンダクーニャ", "Africa", "Western Africa", "Territory", "1:2", "Flag_of_Saint_Helena.svg"),
    ("TG", "TGO", "768", "Togo", "トーゴ", "Africa", "Western Africa", "UN Member", "golden ratio", "Flag_of_Togo.svg"),

    # --- 東アフリカ / Eastern Africa ---
    ("IO", "IOT", "086", "British Indian Ocean Territory", "イギリス領インド洋地域", "Africa", "Eastern Africa", "Territory", "1:2", "Flag_of_the_British_Indian_Ocean_Territory.svg"),
    ("BI", "BDI", "108", "Burundi", "ブルンジ", "Africa", "Eastern Africa", "UN Member", "3:5", "Flag_of_Burundi.svg"),
    ("KM", "COM", "174", "Comoros", "コモロ", "Africa", "Eastern Africa", "UN Member", "3:5", "Flag_of_the_Comoros.svg"),
    ("DJ", "DJI", "262", "Djibouti", "ジブチ", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Djibouti.svg"),
    ("ER", "ERI", "232", "Eritrea", "エリトリア", "Africa", "Eastern Africa", "UN Member", "1:2", "Flag_of_Eritrea.svg"),
    ("ET", "ETH", "231", "Ethiopia", "エチオピア", "Africa", "Eastern Africa", "UN Member", "1:2", "Flag_of_Ethiopia.svg"),
    ("TF", "ATF", "260", "French Southern Territories", "フランス領南方・南極地域", "Africa", "Eastern Africa", "Territory", "2:3", "Flag_of_the_French_Southern_and_Antarctic_Lands.svg"),
    ("KE", "KEN", "404", "Kenya", "ケニア", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Kenya.svg"),
    ("MG", "MDG", "450", "Madagascar", "マダガスカル", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Madagascar.svg"),
    ("MW", "MWI", "454", "Malawi", "マラウイ", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Malawi.svg"),
    ("MU", "MUS", "480", "Mauritius", "モーリシャス", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Mauritius.svg"),
    ("YT", "MYT", "175", "Mayotte", "マヨット", "Africa", "Eastern Africa", "Territory", "2:3", "Flag_of_France.svg"),
    ("MZ", "MOZ", "508", "Mozambique", "モザンビーク", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Mozambique.svg"),
    ("RE", "REU", "638", "Réunion", "レユニオン", "Africa", "Eastern Africa", "Territory", "2:3", "Flag_of_France.svg"),
    ("RW", "RWA", "646", "Rwanda", "ルワンダ", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Rwanda.svg"),
    ("SC", "SYC", "690", "Seychelles", "セーシェル", "Africa", "Eastern Africa", "UN Member", "1:2", "Flag_of_Seychelles.svg"),
    ("SO", "SOM", "706", "Somalia", "ソマリア", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Somalia.svg"),
    ("SS", "SSD", "728", "South Sudan", "南スーダン", "Africa", "Eastern Africa", "UN Member", "1:2", "Flag_of_South_Sudan.svg"),
    ("UG", "UGA", "800", "Uganda", "ウガンダ", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Uganda.svg"),
    ("TZ", "TZA", "834", "Tanzania", "タンザニア", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Tanzania.svg"),
    ("ZM", "ZMB", "894", "Zambia", "ザンビア", "Africa", "Eastern Africa", "UN Member", "2:3", "Flag_of_Zambia.svg"),
    ("ZW", "ZWE", "716", "Zimbabwe", "ジンバブエ", "Africa", "Eastern Africa", "UN Member", "1:2", "Flag_of_Zimbabwe.svg"),

    # --- 中部アフリカ / Middle Africa ---
    ("AO", "AGO", "024", "Angola", "アンゴラ", "Africa", "Middle Africa", "UN Member", "2:3", "Flag_of_Angola.svg"),
    ("CM", "CMR", "120", "Cameroon", "カメルーン", "Africa", "Middle Africa", "UN Member", "2:3", "Flag_of_Cameroon.svg"),
    ("CF", "CAF", "140", "Central African Republic", "中央アフリカ共和国", "Africa", "Middle Africa", "UN Member", "2:3", "Flag_of_the_Central_African_Republic.svg"),
    ("TD", "TCD", "148", "Chad", "チャド", "Africa", "Middle Africa", "UN Member", "2:3", "Flag_of_Chad.svg"),
    ("CG", "COG", "178", "Congo", "コンゴ共和国", "Africa", "Middle Africa", "UN Member", "2:3", "Flag_of_the_Republic_of_the_Congo.svg"),
    ("CD", "COD", "180", "DR Congo", "コンゴ民主共和国", "Africa", "Middle Africa", "UN Member", "3:4", "Flag_of_the_Democratic_Republic_of_the_Congo.svg"),
    ("GQ", "GNQ", "226", "Equatorial Guinea", "赤道ギニア", "Africa", "Middle Africa", "UN Member", "2:3", "Flag_of_Equatorial_Guinea.svg"),
    ("GA", "GAB", "266", "Gabon", "ガボン", "Africa", "Middle Africa", "UN Member", "3:4", "Flag_of_Gabon.svg"),
    ("ST", "STP", "678", "São Tomé and Príncipe", "サントメ・プリンシペ", "Africa", "Middle Africa", "UN Member", "1:2", "Flag_of_São_Tomé_and_Príncipe.svg"),

    # --- 南部アフリカ / Southern Africa ---
    ("BW", "BWA", "072", "Botswana", "ボツワナ", "Africa", "Southern Africa", "UN Member", "2:3", "Flag_of_Botswana.svg"),
    ("SZ", "SWZ", "748", "Eswatini", "エスワティニ", "Africa", "Southern Africa", "UN Member", "2:3", "Flag_of_Eswatini.svg"),
    ("LS", "LSO", "426", "Lesotho", "レソト", "Africa", "Southern Africa", "UN Member", "2:3", "Flag_of_Lesotho.svg"),
    ("NA", "NAM", "516", "Namibia", "ナミビア", "Africa", "Southern Africa", "UN Member", "2:3", "Flag_of_Namibia.svg"),
    ("ZA", "ZAF", "710", "South Africa", "南アフリカ", "Africa", "Southern Africa", "UN Member", "2:3", "Flag_of_South_Africa.svg"),

    # ========== アメリカ / Americas ==========
    # --- 北アメリカ / Northern America ---
    ("BM", "BMU", "060", "Bermuda", "バミューダ", "Americas", "Northern America", "Territory", "1:2", "Flag_of_Bermuda.svg"),
    ("CA", "CAN", "124", "Canada", "カナダ", "Americas", "Northern America", "UN Member", "1:2", "Flag_of_Canada.svg"),
    ("GL", "GRL", "304", "Greenland", "グリーンランド", "Americas", "Northern America", "Territory", "2:3", "Flag_of_Greenland.svg"),
    ("PM", "SPM", "666", "Saint Pierre and Miquelon", "サンピエール島・ミクロン島", "Americas", "Northern America", "Territory", "2:3", "Flag_of_Saint-Pierre_and_Miquelon.svg"),
    ("US", "USA", "840", "United States", "アメリカ合衆国", "Americas", "Northern America", "UN Member", "10:19", "Flag_of_the_United_States.svg"),

    # --- カリブ海 / Caribbean ---
    ("AI", "AIA", "660", "Anguilla", "アンギラ", "Americas", "Caribbean", "Territory", "1:2", "Flag_of_Anguilla.svg"),
    ("AG", "ATG", "028", "Antigua and Barbuda", "アンティグア・バーブーダ", "Americas", "Caribbean", "UN Member", "2:3", "Flag_of_Antigua_and_Barbuda.svg"),
    ("AW", "ABW", "533", "Aruba", "アルバ", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_Aruba.svg"),
    ("BS", "BHS", "044", "Bahamas", "バハマ", "Americas", "Caribbean", "UN Member", "1:2", "Flag_of_the_Bahamas.svg"),
    ("BB", "BRB", "052", "Barbados", "バルバドス", "Americas", "Caribbean", "UN Member", "2:3", "Flag_of_Barbados.svg"),
    ("BQ", "BES", "535", "Bonaire, Sint Eustatius and Saba", "ボネール、シント・ユースタティウスおよびサバ", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_Bonaire.svg"),
    ("VG", "VGB", "092", "British Virgin Islands", "イギリス領ヴァージン諸島", "Americas", "Caribbean", "Territory", "1:2", "Flag_of_the_British_Virgin_Islands.svg"),
    ("KY", "CYM", "136", "Cayman Islands", "ケイマン諸島", "Americas", "Caribbean", "Territory", "1:2", "Flag_of_the_Cayman_Islands.svg"),
    ("CU", "CUB", "192", "Cuba", "キューバ", "Americas", "Caribbean", "UN Member", "1:2", "Flag_of_Cuba.svg"),
    ("CW", "CUW", "531", "Curaçao", "キュラソー", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_Curaçao.svg"),
    ("DM", "DMA", "212", "Dominica", "ドミニカ国", "Americas", "Caribbean", "UN Member", "1:2", "Flag_of_Dominica.svg"),
    ("DO", "DOM", "214", "Dominican Republic", "ドミニカ共和国", "Americas", "Caribbean", "UN Member", "2:3", "Flag_of_the_Dominican_Republic.svg"),
    ("GD", "GRD", "308", "Grenada", "グレナダ", "Americas", "Caribbean", "UN Member", "3:5", "Flag_of_Grenada.svg"),
    ("GP", "GLP", "312", "Guadeloupe", "グアドループ", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_France.svg"),
    ("HT", "HTI", "332", "Haiti", "ハイチ", "Americas", "Caribbean", "UN Member", "3:5", "Flag_of_Haiti.svg"),
    ("JM", "JAM", "388", "Jamaica", "ジャマイカ", "Americas", "Caribbean", "UN Member", "1:2", "Flag_of_Jamaica.svg"),
    ("MQ", "MTQ", "474", "Martinique", "マルティニーク", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_France.svg"),
    ("MS", "MSR", "500", "Montserrat", "モントセラト", "Americas", "Caribbean", "Territory", "1:2", "Flag_of_Montserrat.svg"),
    ("PR", "PRI", "630", "Puerto Rico", "プエルトリコ", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_Puerto_Rico.svg"),
    ("BL", "BLM", "652", "Saint Barthélemy", "サン・バルテルミー", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_France.svg"),
    ("KN", "KNA", "659", "Saint Kitts and Nevis", "セントクリストファー・ネイビス", "Americas", "Caribbean", "UN Member", "2:3", "Flag_of_Saint_Kitts_and_Nevis.svg"),
    ("LC", "LCA", "662", "Saint Lucia", "セントルシア", "Americas", "Caribbean", "UN Member", "1:2", "Flag_of_Saint_Lucia.svg"),
    ("MF", "MAF", "663", "Saint Martin (French part)", "サン・マルタン", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_France.svg"),
    ("VC", "VCT", "670", "Saint Vincent and the Grenadines", "セントビンセントおよびグレナディーン諸島", "Americas", "Caribbean", "UN Member", "2:3", "Flag_of_Saint_Vincent_and_the_Grenadines.svg"),
    ("SX", "SXM", "534", "Sint Maarten (Dutch part)", "シント・マールテン", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_Sint_Maarten.svg"),
    ("TT", "TTO", "780", "Trinidad and Tobago", "トリニダード・トバゴ", "Americas", "Caribbean", "UN Member", "3:5", "Flag_of_Trinidad_and_Tobago.svg"),
    ("TC", "TCA", "796", "Turks and Caicos Islands", "タークス・カイコス諸島", "Americas", "Caribbean", "Territory", "1:2", "Flag_of_the_Turks_and_Caicos_Islands.svg"),
    ("VI", "VIR", "850", "United States Virgin Islands", "アメリカ領ヴァージン諸島", "Americas", "Caribbean", "Territory", "2:3", "Flag_of_the_United_States_Virgin_Islands.svg"),

    # --- 中央アメリカ / Central America ---
    ("BZ", "BLZ", "084", "Belize", "ベリーズ", "Americas", "Central America", "UN Member", "3:5", "Flag_of_Belize.svg"),
    ("CR", "CRI", "188", "Costa Rica", "コスタリカ", "Americas", "Central America", "UN Member", "3:5", "Flag_of_Costa_Rica.svg"),
    ("SV", "SLV", "222", "El Salvador", "エルサルバドル", "Americas", "Central America", "UN Member", "189:335", "Flag_of_El_Salvador.svg"),
    ("GT", "GTM", "320", "Guatemala", "グアテマラ", "Americas", "Central America", "UN Member", "5:8", "Flag_of_Guatemala.svg"),
    ("HN", "HND", "340", "Honduras", "ホンジュラス", "Americas", "Central America", "UN Member", "1:2", "Flag_of_Honduras.svg"),
    ("MX", "MEX", "484", "Mexico", "メキシコ", "Americas", "Central America", "UN Member", "4:7", "Flag_of_Mexico.svg"),
    ("NI", "NIC", "558", "Nicaragua", "ニカラグア", "Americas", "Central America", "UN Member", "3:5", "Flag_of_Nicaragua.svg"),
    ("PA", "PAN", "591", "Panama", "パナマ", "Americas", "Central America", "UN Member", "2:3", "Flag_of_Panama.svg"),

    # --- 南アメリカ / South America ---
    ("AR", "ARG", "032", "Argentina", "アルゼンチン", "Americas", "South America", "UN Member", "5:8", "Flag_of_Argentina.svg"),
    ("BO", "BOL", "068", "Bolivia", "ボリビア", "Americas", "South America", "UN Member", "15:22", "Flag_of_Bolivia.svg"),
    ("BR", "BRA", "076", "Brazil", "ブラジル", "Americas", "South America", "UN Member", "7:10", "Flag_of_Brazil.svg"),
    ("CL", "CHL", "152", "Chile", "チリ", "Americas", "South America", "UN Member", "2:3", "Flag_of_Chile.svg"),
    ("CO", "COL", "170", "Colombia", "コロンビア", "Americas", "South America", "UN Member", "2:3", "Flag_of_Colombia.svg"),
    ("EC", "ECU", "218", "Ecuador", "エクアドル", "Americas", "South America", "UN Member", "2:3", "Flag_of_Ecuador.svg"),
    ("FK", "FLK", "238", "Falkland Islands", "フォークランド諸島", "Americas", "South America", "Territory", "1:2", "Flag_of_the_Falkland_Islands.svg"),
    ("GF", "GUF", "254", "French Guiana", "フランス領ギアナ", "Americas", "South America", "Territory", "2:3", "Flag_of_France.svg"),
    ("GY", "GUY", "328", "Guyana", "ガイアナ", "Americas", "South America", "UN Member", "3:5", "Flag_of_Guyana.svg"),
    ("PY", "PRY", "600", "Paraguay", "パラグアイ", "Americas", "South America", "UN Member", "3:5", "Flag_of_Paraguay.svg"),
    ("PE", "PER", "604", "Peru", "ペルー", "Americas", "South America", "UN Member", "2:3", "Flag_of_Peru.svg"),
    ("SR", "SUR", "740", "Suriname", "スリナム", "Americas", "South America", "UN Member", "2:3", "Flag_of_Suriname.svg"),
    ("UY", "URY", "858", "Uruguay", "ウルグアイ", "Americas", "South America", "UN Member", "2:3", "Flag_of_Uruguay.svg"),
    ("VE", "VEN", "862", "Venezuela", "ベネズエラ", "Americas", "South America", "UN Member", "2:3", "Flag_of_Venezuela.svg"),
    ("GS", "SGS", "239", "South Georgia and the South Sandwich Islands", "サウスジョージア・サウスサンドウィッチ諸島", "Americas", "South America", "Territory", "1:2", "Flag_of_South_Georgia_and_the_South_Sandwich_Islands.svg"),
    ("BV", "BVT", "074", "Bouvet Island", "ブーベ島", "Americas", "South America", "Territory", "8:11", "Flag_of_Norway.svg"),

    # ========== オセアニア / Oceania ==========
    # --- オーストラリアとニュージーランド / Australia and New Zealand ---
    ("AU", "AUS", "036", "Australia", "オーストラリア", "Oceania", "Australia and New Zealand", "UN Member", "1:2", "Flag_of_Australia.svg"),
    ("CX", "CXR", "162", "Christmas Island", "クリスマス島", "Oceania", "Australia and New Zealand", "Territory", "1:2", "Flag_of_Christmas_Island.svg"),
    ("CC", "CCK", "166", "Cocos (Keeling) Islands", "ココス（キーリング）諸島", "Oceania", "Australia and New Zealand", "Territory", "1:2", "Flag_of_the_Cocos_(Keeling)_Islands.svg"),
    ("HM", "HMD", "334", "Heard Island and McDonald Islands", "ハード島とマクドナルド諸島", "Oceania", "Australia and New Zealand", "Territory", "1:2", "Flag_of_Australia.svg"),
    ("NZ", "NZL", "554", "New Zealand", "ニュージーランド", "Oceania", "Australia and New Zealand", "UN Member", "1:2", "Flag_of_New_Zealand.svg"),
    ("NF", "NFK", "574", "Norfolk Island", "ノーフォーク島", "Oceania", "Australia and New Zealand", "Territory", "1:2", "Flag_of_Norfolk_Island.svg"),

    # --- メラネシア / Melanesia ---
    ("FJ", "FJI", "242", "Fiji", "フィジー", "Oceania", "Melanesia", "UN Member", "1:2", "Flag_of_Fiji.svg"),
    ("NC", "NCL", "540", "New Caledonia", "ニューカレドニア", "Oceania", "Melanesia", "Territory", "1:2", "Flag_of_New_Caledonia.svg"),
    ("PG", "PNG", "598", "Papua New Guinea", "パプアニューギニア", "Oceania", "Melanesia", "UN Member", "3:4", "Flag_of_Papua_New_Guinea.svg"),
    ("SB", "SLB", "090", "Solomon Islands", "ソロモン諸島", "Oceania", "Melanesia", "UN Member", "1:2", "Flag_of_the_Solomon_Islands.svg"),
    ("VU", "VUT", "548", "Vanuatu", "バヌアツ", "Oceania", "Melanesia", "UN Member", "3:5", "Flag_of_Vanuatu.svg"),

    # --- ミクロネシア / Micronesia ---
    ("GU", "GUM", "316", "Guam", "グアム", "Oceania", "Micronesia", "Territory", "22:41", "Flag_of_Guam.svg"),
    ("KI", "KIR", "296", "Kiribati", "キリバス", "Oceania", "Micronesia", "UN Member", "1:2", "Flag_of_Kiribati.svg"),
    ("MH", "MHL", "584", "Marshall Islands", "マーシャル諸島", "Oceania", "Micronesia", "UN Member", "10:19", "Flag_of_the_Marshall_Islands.svg"),
    ("FM", "FSM", "583", "Micronesia", "ミクロネシア連邦", "Oceania", "Micronesia", "UN Member", "10:19", "Flag_of_the_Federated_States_of_Micronesia.svg"),
    ("NR", "NRU", "520", "Nauru", "ナウル", "Oceania", "Micronesia", "UN Member", "1:2", "Flag_of_Nauru.svg"),
    ("MP", "MNP", "580", "Northern Mariana Islands", "北マリアナ諸島", "Oceania", "Micronesia", "Territory", "1:2", "Flag_of_the_Northern_Mariana_Islands.svg"),
    ("PW", "PLW", "585", "Palau", "パラオ", "Oceania", "Micronesia", "UN Member", "3:5", "Flag_of_Palau.svg"),
    ("UM", "UMI", "581", "United States Minor Outlying Islands", "合衆国領有小離島", "Oceania", "Micronesia", "Territory", "10:19", "Flag_of_the_United_States.svg"),

    # --- ポリネシア / Polynesia ---
    ("AS", "ASM", "016", "American Samoa", "アメリカ領サモア", "Oceania", "Polynesia", "Territory", "1:2", "Flag_of_American_Samoa.svg"),
    ("CK", "COK", "184", "Cook Islands", "クック諸島", "Oceania", "Polynesia", "Territory", "1:2", "Flag_of_the_Cook_Islands.svg"),
    ("PF", "PYF", "258", "French Polynesia", "フランス領ポリネシア", "Oceania", "Polynesia", "Territory", "2:3", "Flag_of_French_Polynesia.svg"),
    ("NU", "NIU", "570", "Niue", "ニウエ", "Oceania", "Polynesia", "Territory", "1:2", "Flag_of_Niue.svg"),
    ("PN", "PCN", "612", "Pitcairn Islands", "ピトケアン諸島", "Oceania", "Polynesia", "Territory", "1:2", "Flag_of_the_Pitcairn_Islands.svg"),
    ("WS", "WSM", "882", "Samoa", "サモア", "Oceania", "Polynesia", "UN Member", "1:2", "Flag_of_Samoa.svg"),
    ("TK", "TKL", "772", "Tokelau", "トケラウ", "Oceania", "Polynesia", "Territory", "1:2", "Flag_of_Tokelau.svg"),
    ("TO", "TON", "776", "Tonga", "トンガ", "Oceania", "Polynesia", "UN Member", "1:2", "Flag_of_Tonga.svg"),
    ("TV", "TUV", "798", "Tuvalu", "ツバル", "Oceania", "Polynesia", "UN Member", "1:2", "Flag_of_Tuvalu.svg"),
    ("WF", "WLF", "876", "Wallis and Futuna", "ウォリス・フツナ", "Oceania", "Polynesia", "Territory", "2:3", "Flag_of_Wallis_and_Futuna.svg"),

    # ========== その他 / Other ==========
    ("AQ", "ATA", "010", "Antarctica", "南極", "Other", "Antarctica", "Special", "2:3", "Flag_of_Antarctica.svg"),
]

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, "00_master", "countries_master.csv")

    headers = [
        "iso_alpha2",
        "iso_alpha3",
        "iso_numeric",
        "name_en",
        "name_ja",
        "un_m49_region",
        "un_m49_subregion",
        "status",
        "ratio",
        "wiki_flag_filename"
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for country in COUNTRIES:
            writer.writerow(country)

    print(f"✅ Generated {output_path}")
    print(f"   Total entries: {len(COUNTRIES)}")

    # Count by status
    status_counts = {}
    for c in COUNTRIES:
        s = c[7]
        status_counts[s] = status_counts.get(s, 0) + 1
    for s, count in sorted(status_counts.items()):
        print(f"   - {s}: {count}")

    # Count by region
    print("\n   By region:")
    region_counts = {}
    for c in COUNTRIES:
        r = c[5]
        region_counts[r] = region_counts.get(r, 0) + 1
    for r, count in sorted(region_counts.items()):
        print(f"   - {r}: {count}")

if __name__ == "__main__":
    main()
