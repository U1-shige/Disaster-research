#!/usr/bin/env bash
# NotebookLM CLI セットアップスクリプト
# 使用方法: bash setup-notebooklm.sh

set -e

echo "=== NotebookLM CLI セットアップ ==="

# 1. uv の存在確認
if ! command -v uv &>/dev/null; then
    echo ">>> uv をインストール中..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 2. notebooklm-mcp-cli をインストール
echo ">>> notebooklm-mcp-cli をインストール中..."
uv tool install notebooklm-mcp-cli

# 3. PATH に uv tool bin を追加（未追加の場合）
UV_BIN="$(uv tool dir)/../bin"
if [[ ":$PATH:" != *":$UV_BIN:"* ]]; then
    export PATH="$UV_BIN:$PATH"
    echo "export PATH=\"$UV_BIN:\$PATH\"" >> ~/.bashrc
    echo "export PATH=\"$UV_BIN:\$PATH\"" >> ~/.zshrc 2>/dev/null || true
fi

# 4. Google ログイン（ブラウザが開きます）
echo ""
echo ">>> Google アカウントでログインします（ブラウザが開きます）..."
nlm login

# 5. Claude Code への MCP 設定を自動追加
echo ""
echo ">>> Claude Code に NotebookLM MCP を設定中..."
nlm setup add claude-code

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "使い始め方:"
echo "  nlm notebook list                          # ノートブック一覧"
echo "  nlm notebook create '河川災害復旧調査'      # ノートブック作成"
echo "  nlm source add <notebook> --url <URL>      # ソース追加"
echo "  nlm notebook query <notebook> '質問内容'   # 質問"
echo "  nlm audio create <notebook> --confirm      # 音声生成"
echo ""
echo "Claude Code を再起動すると NotebookLM MCP が有効になります。"
