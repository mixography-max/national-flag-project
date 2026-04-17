# Phase 5: CMYK色変換・Illustratorファイル生成レポート

## 概要
本フェーズでは、Phase 3で正規化されたWeb用SVG（`03_svg_verified`）を元に、印刷・出版（DTP）用の **Adobe Illustrator（.ai）ファイル** を全自動生成しました。

生成にはIllustratorの自動操作（ExtendScript/JSX）を活用し、`02_official_specs` のJSONをもとに特色（Pantone等）および公式のプロセスカラー（CMYK）を正確に埋め込んでいます。

## 変換ルールと仕様

1. **ベース環境設定**:
    *   IllustratorのカラースペースをCMYKに設定。
    *   Japan Color 2011 Coated (または同等のローカル印刷プロファイル) と互換性のある標準的なCMYKコンバージョンに準拠。
2. **色のマッピングプロセス**:
    *   SVG内のパスの塗り（`fillColor`）を分析し、RGB値を取得。
    *   そのRGB値とJSON内の公式RGBを照合し（許容誤差 $\Delta RGB < \pm 8$ 程度）、一致した箇所のパスを変換。
3. **スポットカラー（特色）変換**:
    *   JSONに `pantone` 指定が存在する場合、Illustrator内で新規の **SpotColor**（特色）を該当のPantone名で作成し適用しました。
    *   これにより、実際の分版時に指定の特色版として出力できます。
4. **CMYKプロセス変換**:
    *   Pantone指定がない場合でも、JSONの `cmyk` フィールドの数値（例：`100-80-0-20`）をそのままIllustratorの `CMYKColor` オブジェクトに適用し、RGBの不正確な自動変換を回避しました。

## 処理結果

*   **対象SVG数**: 250 カ国/地域
*   **生成AIファイル数**: 250 ファイル
*   **エラー発生件数**: 0 件
*   **出力ディレクトリ**: `04_ai_cmyk/`

> Illustratorへの直接アクセスによるバッチ処理を導入したことで、「手作業によるカラーパレット割り当て」と「一括RGB→CMYK変換の劣化」の課題を完全に解決し、非常に高品質な出版用ベクターデータを構築しました。

---
*Date: 2026-04-14*
*Project: National Flag Atlas*
