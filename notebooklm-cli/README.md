# NotebookLM CLI（nlm-research）

災害復旧事業調査向け NotebookLM CLI ツール。
[notebooklm-py](https://github.com/teng-lin/notebooklm-py) をベースに、調査業務に特化したコマンド体系を提供します。

## セットアップ

### 前提条件

- Python 3.10 以上
- Google アカウント（NotebookLM へのアクセス権）

### インストール

```bash
# uv を使用（推奨）
cd notebooklm-cli
uv pip install -e ".[dev]"

# pip を使用
pip install -e ".[dev]"
```

### 認証

```bash
# Google アカウントでログイン（ブラウザが開きます）
nlm-research auth login

# 認証状態を確認
nlm-research auth status
```

## コマンド一覧

### 認証（auth）

| コマンド | 説明 |
|---------|------|
| `nlm-research auth login` | Google 認証 |
| `nlm-research auth status` | 認証状態の確認 |
| `nlm-research auth refresh` | トークン更新 |
| `nlm-research auth switch <profile>` | プロファイル切替 |

### ノートブック（notebook）

| コマンド | 説明 |
|---------|------|
| `nlm-research notebook list` | 一覧表示 |
| `nlm-research notebook create "名前"` | 新規作成 |
| `nlm-research notebook delete <id>` | 削除 |
| `nlm-research notebook use <id>` | デフォルト設定 |

### ソース管理（source）

| コマンド | 説明 |
|---------|------|
| `nlm-research source add <URL/ファイル>` | ソース追加 |
| `nlm-research source list` | 一覧表示 |
| `nlm-research source remove <id>` | 削除 |
| `nlm-research source add-batch <file>` | URL一括追加 |

### 質問（query）

| コマンド | 説明 |
|---------|------|
| `nlm-research query ask "質問"` | ソースに基づいて質問 |
| `nlm-research query ask-file <file>` | ファイルから質問 |
| `nlm-research query batch <file>` | 複数質問の一括実行 |

### コンテンツ生成（generate）

| コマンド | 説明 |
|---------|------|
| `nlm-research generate audio` | 音声ポッドキャスト生成 |
| `nlm-research generate summary` | 要約レポート生成 |
| `nlm-research generate quiz` | クイズ生成 |
| `nlm-research generate slide-deck` | スライド生成 |
| `nlm-research generate mind-map` | マインドマップ生成 |

### 設定（config）

| コマンド | 説明 |
|---------|------|
| `nlm-research config show` | 設定表示 |
| `nlm-research config set <key> <value>` | 設定変更 |
| `nlm-research config reset` | 初期化 |

## 使用例

```bash
# ノートブックを作成してデフォルトに設定
nlm-research notebook create "河川災害復旧調査" --default

# ソースを追加
nlm-research source add "https://example.com/report.pdf"
nlm-research source add ./査定設計書.pdf

# URLリストから一括追加
nlm-research source add-batch urls.txt

# 質問
nlm-research query ask "重要変更協議の判断基準は何ですか？"

# 回答をノートとして保存
nlm-research query ask "工法変更の手続きフローを説明してください" --save

# 音声オーバービューを日本語で生成
nlm-research generate audio --lang ja --output ./podcast.mp3

# 要約レポートを生成してファイルに保存
nlm-research generate summary --output ./summary.md
```

## 設定ファイル

設定は `~/.config/nlm-research/config.json` に保存されます。

| キー | 説明 | デフォルト |
|-----|------|----------|
| `language` | デフォルト言語 | `ja` |
| `download_dir` | ダウンロード先 | `~/.config/nlm-research/downloads` |
| `profile` | 認証プロファイル | `default` |
| `notebook` | デフォルトノートブック ID | なし |

## 注意事項

- 本ツールは Google NotebookLM の非公式 API を使用しています
- API の仕様変更により動作しなくなる可能性があります
- 認証クッキーは数週間で期限切れとなるため、定期的な再認証が必要です
