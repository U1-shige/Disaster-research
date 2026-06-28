"""NotebookLM CLI メインエントリーポイント"""

from __future__ import annotations

import typer
from rich.console import Console

from . import __version__
from .commands import auth, config_cmd, generate, notebook, query, source

app = typer.Typer(
    name="nlm-research",
    help="災害復旧事業調査向け NotebookLM CLI ツール",
    no_args_is_help=True,
)

console = Console()

app.add_typer(auth.app, name="auth", help="認証管理")
app.add_typer(notebook.app, name="notebook", help="ノートブック操作")
app.add_typer(source.app, name="source", help="ソース管理")
app.add_typer(query.app, name="query", help="質問・チャット")
app.add_typer(generate.app, name="generate", help="コンテンツ生成")
app.add_typer(config_cmd.app, name="config", help="設定管理")


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="バージョン表示"),
) -> None:
    if version:
        console.print(f"nlm-research v{__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
