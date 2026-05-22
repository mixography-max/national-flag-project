---
description: Adobe Illustratorのバッチ処理（JSX自動制御）を行う際のメモリ安全対策ガイドライン。AIファイルの一括変換・生成時に必ず参照すること。
---

# Illustrator バッチ処理 メモリ安全ワークフロー

> **背景**: 2026-05-19に250ファイルを一括処理した際、ファイルを閉じずに連続処理を行ったためIllustratorのメモリ使用量が膨張し、macOS全体がハングアウトした。以降、Illustratorのバッチ処理では以下のルールを**必ず**遵守する。

## 必須ルール

### Rule 1: 1ファイルずつ開いて閉じる
- JSXスクリプトでは、処理の最後に必ず `doc.close(SaveOptions.DONOTSAVECHANGES)` を呼ぶ。
- **エラーが発生した場合も** `catch` ブロック内で `doc.close()` を実行する。
- 複数ドキュメントを同時に開く処理は**絶対に禁止**。

```javascript
// ✅ 正しいパターン
try {
    var doc = app.open(File("/path/to/file.ai"));
    // ... 処理 ...
    doc.saveAs(saveFile, saveOpts);
    doc.close(SaveOptions.DONOTSAVECHANGES);  // ← 必須
} catch(err) {
    try { app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch(e2) {}
    // ↑ エラー時も必ず閉じる
}
```

### Rule 2: ファイル間に休止を入れる
- **通常**: 各ファイル処理後に `time.sleep(2)` (2秒) の休止を入れる。
- **10件ごと**: `time.sleep(5)` (5秒) の長めの休止を入れ、Illustratorのメモリ解放を促す。
- `--all` で250件一括実行する場合は特に重要。

```python
# ✅ Pythonバッチ側の休止パターン
for i, code in enumerate(codes, 1):
    result = process_one(code)
    if i < total:
        if i % 10 == 0:
            print(f"   💤 10件完了 - 5秒休止中... ({i}/{total})")
            time.sleep(5)
        else:
            time.sleep(2)
```

### Rule 3: タイムアウトを設定する
- `subprocess.run()` には必ず `timeout=180`（3分）を設定する。
- 特定のファイルでIllustratorがフリーズした場合にプロセス全体が止まることを防ぐ。

```python
# ✅ タイムアウト付きの実行
try:
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
except subprocess.TimeoutExpired:
    return "ERROR_TIMEOUT"
```

### Rule 4: 進捗ログで中断・再開に対応する
- 処理済みファイルのコードをテキストファイルに逐次記録する。
- `--resume` フラグで、前回の続きから再開できるようにする。
- これにより、万一ハングして強制終了しても、最初からやり直す必要がない。

```python
# ✅ 進捗ログのパターン
PROGRESS_LOG = PROJECT_ROOT / "04_ai_cmyk" / "logs" / "progress.txt"

def mark_done(code: str):
    with open(PROGRESS_LOG, "a") as f:
        f.write(f"{code}\n")

def get_done_codes() -> set:
    if not PROGRESS_LOG.exists():
        return set()
    return set(PROGRESS_LOG.read_text().strip().split("\n"))
```

### Rule 5: テスト実行を先に行う
- 全件処理の前に、必ず `--codes XX` で1〜2ファイルの動作確認を行う。
- `--dry-run` モードを用意し、何が処理されるかを事前確認可能にする。

## 禁止事項

| ❌ やってはいけないこと | ⭕ 正しい対応 |
|---|---|
| 250ファイルを一気に開いて処理する | 1ファイルずつ開く→処理→保存→閉じる |
| `doc.close()` を省略する | 正常時もエラー時も必ず閉じる |
| ファイル間に休止なしで連続実行する | 2秒/通常、5秒/5件ごとの休止を入れる |
| テストなしでいきなり全件実行する | まず1-2件でテスト、次に全件実行 |
| `timeout` なしで `subprocess.run()` を呼ぶ | `timeout=180` を必ず設定する |
| 進捗記録なしで長時間バッチを走らせる | 進捗ログに逐次記録、`--resume` 対応 |
| 5件以上連続で閉じずに放置する | 5件ごとに `close_all_documents()` で全強制クローズ |
| パスをNFD（macOS内部形式）のまま渡す | `unicodedata.normalize("NFC", path)` で正規化 |

---

### Rule 6: 5件ごとに全ドキュメント強制クローズ

Illustratorは `doc.close()` を呼んでもメモリを完全に解放しない場合がある。
**5件処理するごとに、全ドキュメントを強制クローズ**してメモリリークを防止する。

```python
# ✅ 5件ごとの強制クローズパターン
if i % 5 == 0:
    print(f"   🧹 全ドキュメント強制クローズ + 5秒休止")
    close_all_documents()  # JSX: while (app.documents.length > 0) { ... close ... }
    time.sleep(5)
```

> ⚠ **実際に発生した事故**: 2026-05-19に250ファイルを閉じずに連続処理し、macOS全体がハングアウトした。2026-05-22にも `doc.close()` 後にSVGウィンドウが残り続けメモリが膨張した。

---

### Rule 7: macOS NFD → NFC パス正規化（濁点問題）

macOS (APFS/HFS+) はファイルパスを**NFD（分解形）**で保持する。
例: 「プ」→「フ」+「゚」（U+30D5 + U+309A）に分解される。

この分解されたパスをosascript経由でAdobe Illustratorに渡すと、パス認識に失敗する。

**対策**: すべてのファイルパスを `unicodedata.normalize("NFC", path)` で**NFC（合成形）**に正規化してからJSX/osascriptに渡す。

```python
import unicodedata

def nfc(path_str: str) -> str:
    """macOS NFD → NFC 正規化"""
    return unicodedata.normalize("NFC", path_str)

# ✅ パスは必ずNFC正規化してから使う
svg_abs = nfc(str(svg_path.absolute()))
ai_abs = nfc(str(ai_path.absolute()))
jsx_abs = nfc(str(jsx_path.absolute()))
```

> ⚠ **実際に発生したエラー**: `国旗プロジェクト` の `プ` がNFDで分解され、osascriptで `syntax error: このidentifierの後にidentifierを書くことはできません` が発生した (2026-05-22, CC.ai)。

---

## CMYK AI 2段階変換パイプライン手順（個別・一括更新）

国旗データ（SVGや仕様書JSON）に修正が入った場合、以下の2段階の手順でAIファイルを再生成します。
このパイプラインは、Illustratorのメモリ破壊によるクラッシュやパス消失、RGBとCMYK間の四捨五入ブレを厳格に防ぎます。

### ステップ 1: SVG から CMYK AI への変換とRGBタグ埋め込み
SVGファイルを開き、各オブジェクトのRGB値をパスの `note` にタグ付けした上で、新規CMYKドキュメントに複製して中間AIファイルを出力します。

- **特定国のみ更新する場合 (例: セントルシア `LC`)**:
  ```bash
  python3 scripts/step1_convert_svg_to_cmyk_ai.py --codes LC
  ```
- **変更があったすべての国を更新する場合**:
  ```bash
  python3 scripts/step1_convert_svg_to_cmyk_ai.py
  ```
- **全カ国を一括更新する場合**:
  ```bash
  python3 scripts/step1_convert_svg_to_cmyk_ai.py --all
  ```
- **中間ファイルの保存先**: `04_ai_cmyk/<code>.ai`

### ステップ 2: Pantoneプロセススウォッチの登録と適用
中間AIファイルを開き、`02_official_specs/<code>.json` に定義された検証済みの整数CMYK値をもとに、カラータイプ「プロセス」のPantoneスウォッチを作成してパスに適用します。

- **特定国のみ適用する場合 (例: セントルシア `LC`)**:
  ```bash
  python3 scripts/step2_apply_pantone_swatches.py --codes LC
  ```
- **全カ国に適用する場合**:
  ```bash
  python3 scripts/step2_apply_pantone_swatches.py --all
  ```

---

## 既存スクリプトの対応状況

| スクリプト | 対応済み | 備考 |
|---|---|---|
| `scripts/step1_convert_svg_to_cmyk_ai.py` | ✅ | 2段階パイプライン（第1段階: CMYK複製 & RGBタグ埋め込み） |
| `scripts/step2_apply_pantone_swatches.py` | ✅ | 2段階パイプライン（第2段階: スウォッチ登録 & 適用） |
| `scripts/convert_spot_to_process.py` | ✅ | 古い一括スウォッチ変更スクリプト |
| `scripts/batch_ai_cmyk_update.py` | ✅ | 古い1段階変換スクリプト |

