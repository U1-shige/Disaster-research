"""設定管理コマンド"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ..config import get_config, update_config

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("show")
def show() -> None:
    """現在の設定を表示"""
    config = get_config()

    table = Table(title="現在の設定")
    table.add_column("項目", style="bold")
    table.add_column("値")

    table.add_row("デフォルトノートブック", config.default_notebook_id or "(未設定)")
    table.add_row("言語", config.default_language)
    table.add_row("ダウンロードディレクトリ", config.download_dir)
    table.add_row("プロファイル", config.profile)

    console.print(table)


@app.command("set")
def set_value(
    key: str = typer.Argument(help="設定キー（language, download_dir, profile）"),
    value: str = typer.Argument(help="設定値"),
) -> None:
    """設定値を変更"""
    key_map = {
        "language": "default_language",
        "download_dir": "download_dir",
        "profile": "profile",
        "notebook": "default_notebook_id",
    }

    config_key = key_map.get(key)
    if not config_key:
        console.print(f"[bold red]不明な設定キー: {key}[/]")
        console.print(f"有効なキー: {', '.join(key_map.keys())}")
        raise typer.Exit(code=1)

    update_config(**{config_key: value})
    console.print(f"[bold green]{key} = {value}[/]")


@app.command("reset")
def reset(
    force: bool = typer.Option(False, "--force", "-f", help="確認なしでリセット"),
) -> None:
    """設定を初期値にリセット"""
    if not force:
        confirm = typer.confirm("設定を初期値にリセットしますか？")
        if not confirm:
            raise typer.Abort()

    from ..config import CONFIG_FILE

    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()

    console.print("[bold green]設定をリセットしました[/]")
