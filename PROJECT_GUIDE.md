# 国旗プロジェクト — 統合手順書

> 全250カ国・地域の国旗仕様を検証・正規化し、Web/印刷の両メディアで展開するプロジェクトの統合ドキュメント。

---

## 🌐 公開URL

| 環境 | URL |
|------|-----|
| **本番** | [https://www.ninomiyashoten.co.jp/ninolabo/national-flag/](https://www.ninomiyashoten.co.jp/ninolabo/national-flag/) |
| **GitHub Pages** | [https://mixography-max.github.io/national-flag-project/](https://mixography-max.github.io/national-flag-project/) |
| **リポジトリ** | [https://github.com/mixography-max/national-flag-project](https://github.com/mixography-max/national-flag-project) |

---

## 📂 プロジェクト構成

```
国旗プロジェクト/
├── 00_master/              # マスターデータ（原本）
├── 01_svg_wikipedia/       # Wikipedia由来のSVG国旗（未検証）
├── 02_official_specs/      # 公式仕様JSON（250カ国）
├── 03_svg_verified/        # 検証済みSVG国旗（公式色適用済み）
├── 04_ai_cmyk/             # 印刷用AIファイル（CMYK/Japan Color 2011）
├── 05_web/                 # Webアトラス（公開用静的サイト）
│   ├── 01_svg_wikipedia/   #   シンボリックリンク
│   ├── 03_svg_verified/    #   シンボリックリンク
│   ├── css/                #   スタイルシート
│   ├── js/                 #   JavaScript（app, colors, quiz, guide, etc.）
│   ├── png_flags/          #   PNG国旗画像
│   │   ├── 1080/           #     高解像度（h=1080px）
│   │   └── 640/            #     標準解像度（h=640px）
│   ├── flags_data.json     #   国旗カラーデータ（250カ国）
│   ├── countries_data.json #   国名・首都データ
│   └── *.html              #   各ページ
├── 06_docs/                # ドキュメント・報告書
│   ├── roadmap.md          #   Phase 1-6 ロードマップ
│   ├── verification_notes.md # 検証ノート（約112KB）
│   └── ...
├── scripts/                # 自動化スクリプト（Python）
├── .agents/workflows/      # AIエージェント用ワークフロー
├── .github/workflows/      # GitHub Actions（Pages自動デプロイ）
└── id_rsa                  # 本番サーバー接続用SSH鍵（※gitignore済み）
```

---

## 🌍 ウェブサイトの構成と仕様

| ページ | ファイル | JS | 概要 |
|--------|---------|-----|------|
| 🏁 フラグアトラス | `index.html` | `app.js` | 250カ国の国旗一覧。地域フィルタ・検索・モーダル詳細表示。類似国旗比較機能 |
| 📖 国旗ガイド | `guide.html` | `guide.js` | 国旗の解説カード。カラー仕様・法的根拠を詳細表示 |
| 🌐 国名・首都名 | `countries.html` | `countries.js` | 外務省検証済みの国名・首都データ一覧表 |
| 💡 トリビア | `trivia.html` | `trivia.js` | 国旗にまつわる知識クイズ・雑学 |
| 🔄 国旗の変遷 | `changes.html` | `changes.js` | 最近の国旗変更の変遷記録 |
| 🎮 国旗クイズ | `quiz.html` | `quiz.js` | 4択クイズ。20問ランダム出題・100点満点 |
| 🎨 色の比較 | `colors.html` | `colors.js` | Pantone色系統別に国旗の色を分類・比較。ΔE色差計算付き |

### 共有データファイル

| ファイル | 内容 | 使用先 |
|---------|------|--------|
| `flags_data.json` | 全250カ国のカラー仕様（HEX, Pantone, CMYK, RGB） | app.js, colors.js, quiz.js |
| `countries_data.json` | 国名（日英）、首都、地域、外務省データ | countries.js, svg_to_png.py |

---

## 🔄 日常的な作業フロー

### 国旗SVGの色を修正した場合

1. `03_svg_verified/{CODE}.svg` を修正
2. `flags_data.json` のカラーデータを更新（該当国の `colors` 配列）
3. PNGを再生成：
   ```bash
   python3 scripts/svg_to_png.py
   ```
4. **全JSファイルの `SVG_VERSION` を更新**（→ [flag_file_naming ワークフロー §7](.agents/workflows/flag_file_naming.md)）
5. **全HTMLのキャッシュバスター `?v=YYYYMMDD` を更新**
6. コミット → push → 本番デプロイ（→ [deploy_production ワークフロー](.agents/workflows/deploy_production.md)）

### デプロイ手順

```bash
# 1. Git commit & push（GitHub Pages 自動デプロイ）
git add -A && git commit -m "fix: ..." && git push origin main

# 2. 本番サーバーへ rsync
chmod 600 id_rsa
rsync -avz --delete \
  -e "ssh -i id_rsa -o StrictHostKeyChecking=accept-new" \
  05_web/ \
  amimoto-user@a290.pilott.amimoto.io:/var/www/vhosts/ninomiyashoten.co.jp/ninolabo/national-flag/
```

> 詳細は [deploy_production.md](.agents/workflows/deploy_production.md) を参照。

---

## 📋 ワークフロー一覧

| ワークフロー | ファイル | 用途 |
|-------------|---------|------|
| **本番デプロイ** | [deploy_production.md](.agents/workflows/deploy_production.md) | SSH/rsyncによる本番サーバーへの同期手順と注意事項 |
| **ファイル命名規則** | [flag_file_naming.md](.agents/workflows/flag_file_naming.md) | SVG/PNG/AIの命名ルール、JS側パス構築、SVG_VERSION同期 |
| **Illustratorバッチ安全** | [illustrator_batch_safety.md](.agents/workflows/illustrator_batch_safety.md) | JSX自動制御によるAI一括変換時のメモリ安全対策 |
| **国旗仕様検証** | [verify_flag_specs.md](.agents/workflows/verify_flag_specs.md) | 250カ国のPantone/CMYK仕様と法定根拠の検証手順 |

---

## 🗺 プロジェクト・ロードマップ

> 詳細は [06_docs/roadmap.md](06_docs/roadmap.md) を参照。

| Phase | 内容 | 完了日 |
|-------|------|--------|
| **Phase 1** | カラー仕様の検証・正規化（250カ国） | 2026-04-10 ✅ |
| **Phase 2** | SVG生成・ビジュアル検証 | 2026-04-14 ✅ |
| **Phase 3** | 最終版SVGの整理（メタデータ・比率正規化） | 2026-04-14 ✅ |
| **Phase 4** | Webアトラス公開 | 2026-04-14 ✅ |
| **Phase 5** | 印刷用CMYK出力（AIファイル一括生成） | 2026-04-14 ✅ |
| **Phase 6** | 書籍レイアウト用素材（InDesignデータ結合） | 2026-04-14 ✅ |

### 継続メンテナンス項目
- 外務省の国名・首都名変更への追従
- 新しい国旗デザイン変更への対応（例: ブルネイ色修正 2026-05-21）
- ウェブサイト機能の追加・改善

---

## 🔧 主要スクリプト

| スクリプト | 用途 |
|-----------|------|
| `scripts/svg_to_png.py` | SVG → PNG変換（1080px/640px、国名ファイル名で出力） |
| `scripts/recolor_svg.py` | JSONカラー仕様に基づくSVG色置換 |
| `scripts/verify_svg_colors.py` | SVGとJSON間の色整合性チェック |
| `scripts/batch_ai_cmyk.py` | SVG → AI(CMYK)バッチ変換 |
| `scripts/generate_countries_json.py` | CSV/MOFA → countries_data.json 生成 |
| `scripts/build_web_data.py` | flags_data.json 構築 |
| `scripts/generate_master_csv.py` | InDesign用マスターCSV生成 |
| `scripts/download_wikipedia_svg.py` | Wikipedia SVG自動取得 |
| `scripts/normalize_svg.py` | SVGメタデータ・viewBox正規化 |

---

## ⚠ 運用上の注意事項

### ファイル命名の一貫性
- **SVG/AIはISOコードベース**（`JP.svg`, `JP.ai`）
- **PNGは国名ベース**（`Japan.png`）
- 詳細は [flag_file_naming.md](.agents/workflows/flag_file_naming.md) を参照

### キャッシュバスティング
- SVGを修正したら **全JSの `SVG_VERSION` と全HTMLのスクリプト参照バージョンを統一更新**
- 一箇所でも漏れるとページ間で不整合が発生する

### セキュリティ
- `id_rsa`（SSH秘密鍵）は `.gitignore` 登録済み — **絶対にコミットしないこと**
- 本番デプロイは `rsync --delete` を使用 — ローカルに存在しないファイルがサーバーから削除される点に注意

### ローカル確認
```bash
cd /Users/r-site/Documents/国旗プロジェクト
python3 -m http.server 8080
# → http://localhost:8080/05_web/index.html
```
