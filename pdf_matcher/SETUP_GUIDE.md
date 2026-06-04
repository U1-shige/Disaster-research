# PDF突合システム セットアップガイド

## 全体構成

```
[Power Automate 手動ボタン]
  → OneDrive /二次調査/ 内の番号フォルダ(1〜570)を処理
  → 各フォルダ内の「設計変更」ファイルと証拠PDFを Copilot Studio で突合判定
  → 結果を Excel にまとめて OneDrive へ保存

[Python スクリプト（ローカル実行）]
  → Excel の「真」「要確認」行の PDF を DocuWorks (.xdw) に変換
```

---

## STEP 1: OneDrive に Excel 雛形を配置

1. Excel を新規作成し、Sheet1 に以下のヘッダー行を1行目に入力する

   | A | B | C | D | E | F |
   |---|---|---|---|---|---|
   | フォルダ番号 | 基準ファイル名 | 証拠ファイル名 | 判定 | スコア | 判定理由 |

2. ヘッダー行をテーブルに変換（挿入 → テーブル → 「先頭行をテーブルの見出しとして使用する」チェック）
3. テーブル名を `突合結果` に変更（テーブルデザインタブ）
4. ファイル名を `突合結果_template.xlsx` として OneDrive の `/二次調査/` フォルダに保存

---

## STEP 2: Copilot Studio でエージェントを作成

1. [Copilot Studio](https://copilotstudio.microsoft.com/) を開く
2. 「新しいコパイロットを作成」→ 名前: `PDF突合判定エージェント`
3. 「トピック」→「新しいトピック」→ 名前: `判定リクエスト`
4. トリガーフレーズ（使わないが必須）: `突合判定してください`
5. 「メッセージ」アクションを削除し、代わりに「生成 AI」→「GPT で応答を生成」を追加

   **プロンプト設定**:
   ```
   あなたは災害復旧工事の審査員です。
   以下の2つのテキストを比較し、「証拠文書テキスト」が「変更理由テキスト」を
   裏付けているかを判定してください。
   必ず以下のJSON形式のみで返答してください（説明文は不要）。
   {"judgment": "真"|"偽"|"要確認", "score": 0.0〜1.0, "reason": "根拠（1〜2文）"}

   判定基準:
   - 真 (score >= 0.7): 証拠文書が変更理由を明確に裏付けている
   - 偽 (score < 0.3): 内容が無関係または矛盾している
   - 要確認 (0.3 <= score < 0.7): 関連はあるが確証が不十分

   変更理由テキスト:
   {BaseText}

   証拠文書テキスト:
   {EvidenceText}
   ```

6. 入力変数を追加:
   - `BaseText`（テキスト型）
   - `EvidenceText`（テキスト型）
7. 「公開」→「公開」ボタンを押して発行する

---

## STEP 3: Power Automate フローを作成

1. [Power Automate](https://make.powerautomate.com/) を開く
2. 「新しいフローを作成」→「インスタントクラウドフロー」
3. フロー名: `PDF突合処理フロー`、トリガー: `手動でフローをトリガーします`

### フロー構成（順に追加）

#### ① 変数の初期化
- アクション: `変数を初期化する`
- 名前: `results`、種類: `配列`、値: `[]`

#### ② 基準フォルダ内のサブフォルダ一覧取得
- コネクタ: `OneDrive for Business`
- アクション: `フォルダー内のファイルのリスト`
- フォルダー: `/二次調査`

#### ③ Apply to each（番号フォルダをループ）
対象: `②の出力（value）`

**③-a. フォルダ内ファイル一覧取得**
- `OneDrive for Business` → `フォルダー内のファイルのリスト`
- フォルダー: `@{items('Apply_to_each')?['Path']}`

**③-b. 基準ファイルを特定（設計変更を含むファイル）**
- アクション: `配列のフィルター処理`
- 差出人: `③-aの出力（value）`
- 条件: `contains(item()?['Name'], '設計変更')`
- → 変数 `baseFileArray` に格納

**③-c. 基準ファイルが存在するか確認（条件分岐）**
- アクション: `条件`
- 条件: `length(variables('baseFileArray'))` が `0` より大きい

  **はいの場合（基準ファイルあり）**:

  **③-c-i. 基準ファイルのコンテンツ取得**
  - `OneDrive for Business` → `ファイル コンテンツの取得`
  - ファイル: `first(variables('baseFileArray'))?['Id']`

  **③-c-ii. 基準ファイルからテキスト抽出**
  - `AI Builder` → `ドキュメントからテキストを抽出する`
  - ドキュメント: `③-c-iのファイルコンテンツ`
  - → 変数 `baseText` に格納

  **③-c-iii. 証拠ファイルループ（Apply to each）**
  - 対象: `③-aの出力（value）` から 基準ファイルを除外したもの
    - フィルター条件: `not(contains(item()?['Name'], '設計変更'))`

    **③-c-iii-A. 証拠ファイルのコンテンツ取得**
    - `OneDrive for Business` → `ファイル コンテンツの取得`

    **③-c-iii-B. 証拠ファイルからテキスト抽出**
    - `AI Builder` → `ドキュメントからテキストを抽出する`
    - → 変数 `evidenceText` に格納

    **③-c-iii-C. Copilot Studio に判定依頼**
    - コネクタ: `Microsoft Copilot Studio`
    - エージェント: `PDF突合判定エージェント`
    - メッセージ: `判定リクエスト`
    - 入力変数:
      - `BaseText`: `variables('baseText')`
      - `EvidenceText`: `variables('evidenceText')`
    - → 変数 `judgmentJson` に格納

    **③-c-iii-D. JSON をパース**
    - アクション: `JSON の解析`
    - コンテンツ: `variables('judgmentJson')`
    - スキーマ:
      ```json
      {
        "type": "object",
        "properties": {
          "judgment": {"type": "string"},
          "score": {"type": "number"},
          "reason": {"type": "string"}
        }
      }
      ```

    **③-c-iii-E. results 配列に追記**
    - アクション: `配列変数に追加`
    - 名前: `results`
    - 値:
      ```json
      {
        "フォルダ番号": "@{items('Apply_to_each')?['Name']}",
        "基準ファイル名": "@{first(variables('baseFileArray'))?['Name']}",
        "証拠ファイル名": "@{items('Apply_to_each_2')?['Name']}",
        "判定": "@{body('JSON_の解析')?['judgment']}",
        "スコア": "@{body('JSON_の解析')?['score']}",
        "判定理由": "@{body('JSON_の解析')?['reason']}"
      }
      ```

  **いいえの場合（基準ファイルなし）**:
  - `配列変数に追加`: results に `{"フォルダ番号": "...", "判定": "基準ファイルなし"}` を追記

#### ④ Excel テーブルに全結果を書き込み（Apply to each）
対象: `variables('results')`

- コネクタ: `Excel Online (Business)`
- アクション: `表に行を追加する`
- 場所: `OneDrive for Business`
- ドキュメント ライブラリ: `OneDrive`
- ファイル: `/二次調査/突合結果_template.xlsx`
- テーブル: `突合結果`
- 各列に動的コンテンツをマッピング

#### ⑤ 保存済みファイルのパスを確認
フローが完了すると `/二次調査/突合結果_template.xlsx` が更新される。

---

## STEP 4: Python スクリプトのセットアップ（Windows ローカル）

### 前提条件
- Python 3.10 以上がインストール済み
- DocuWorks がインストール済み（XDWAPI.dll が存在すること）
- Poppler がインストール済み（pdf2image に必要）
  - ダウンロード: https://github.com/oschwartz10612/poppler-windows/releases
  - インストール後、`bin` フォルダを PATH に追加

### インストール

```cmd
cd pdf_matcher
pip install -r requirements.txt
```

### 実行手順

1. OneDrive から `突合結果_template.xlsx` をローカルにダウンロード
2. 証拠 PDF が入った番号フォルダ群（二次調査フォルダ）をローカルにダウンロード
3. 以下のコマンドを実行:

```cmd
python main_xdw.py ^
  --excel   C:\Downloads\突合結果_template.xlsx ^
  --pdf-dir C:\Downloads\二次調査 ^
  --pages   3,5 ^
  --output  C:\Downloads\xdw_out
```

4. `xdw_out\<フォルダ番号>\<ファイル名>.xdw` が生成される
5. DocuWorks で開いて確認

---

## よくある問題

| 症状 | 原因 | 対処 |
|---|---|---|
| `XDWAPI.dll が見つかりません` | DocuWorks 未インストール or パスが違う | `--xdwapi-dll` で正しいパスを指定 |
| `pdf2image エラー` | Poppler 未インストール | Poppler をインストールして PATH に追加 |
| AI Builder テキスト抽出が空 | スキャン PDF で解像度が低い | 元 PDF の品質を確認 |
| Copilot Studio が応答しない | エージェントが未公開 | STEP 2 の「公開」を実施 |
