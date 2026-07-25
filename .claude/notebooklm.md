# NotebookLM スキル

このプロジェクトには NotebookLM MCP サーバーが設定されています（`.mcp.json`）。
セットアップ済みの場合、以下の MCP ツールが利用可能です。

## 主なツール

- **notebook_list** — ノートブック一覧取得
- **notebook_create** — ノートブック作成
- **notebook_query** — ノートブックへの質問
- **source_add** — ソース追加（URL / ファイル）
- **audio_create** — 音声オーバービュー生成
- **audio_download** — 音声ファイルのダウンロード

## セットアップが未完了の場合

```bash
bash setup-notebooklm.sh
```

を実行してから Claude Code を再起動してください。

## 直接 CLI で使う場合（`nlm` コマンド）

```bash
# ノートブック一覧
nlm notebook list

# ノートブック作成
nlm notebook create "河川災害復旧調査"

# ソース追加
nlm source add <notebook_id> --url "https://example.com/report.pdf"

# 質問
nlm notebook query <notebook_id> "重要変更協議の判断基準は？"

# 音声生成（日本語）
nlm audio create <notebook_id> --confirm --language ja
```
