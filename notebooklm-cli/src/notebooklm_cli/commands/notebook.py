"""ノートブック操作コマンド"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ..client import get_client, run_async
from ..config import get_config, update_config

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("list")
def list_notebooks() -> None:
    """ノートブック一覧を表示"""

    async def _list():
        async with get_client() as client:
            notebooks = await client.notebooks.list()
            return notebooks

    notebooks = run_async(_list())
    config = get_config()

    table = Table(title="ノートブック一覧")
    table.add_column("ID", style="dim")
    table.add_column("名前", style="bold")
    table.add_column("デフォルト", justify="center")

    for nb in notebooks:
        is_default = "★" if nb.id == config.default_notebook_id else ""
        table.add_row(nb.id, nb.title, is_default)

    console.print(table)


@app.command()
def create(
    name: str = typer.Argument(help="ノートブック名"),
    set_default: bool = typer.Option(False, "--default", "-d", help="デフォルトとして設定"),
) -> None:
    """新規ノートブックを作成"""

    async def _create():
        async with get_client() as client:
            nb = await client.notebooks.create(name)
            return nb

    nb = run_async(_create())
    console.print(f"[bold green]作成完了:[/] {nb.title} (ID: {nb.id})")

    if set_default:
        update_config(default_notebook_id=nb.id)
        console.print(f"[dim]デフォルトノートブックに設定しました[/]")


@app.command()
def delete(
    notebook_id: str = typer.Argument(help="ノートブック ID"),
    force: bool = typer.Option(False, "--force", "-f", help="確認なしで削除"),
) -> None:
    """ノートブックを削除"""
    if not force:
        confirm = typer.confirm(f"ノートブック {notebook_id} を削除しますか？")
        if not confirm:
            raise typer.Abort()

    async def _delete():
        async with get_client() as client:
            await client.notebooks.delete(notebook_id)

    run_async(_delete())
    console.print(f"[bold green]削除完了:[/] {notebook_id}")

    config = get_config()
    if config.default_notebook_id == notebook_id:
        update_config(default_notebook_id=None)


@app.command("use")
def set_default(
    notebook_id: str = typer.Argument(help="デフォルトに設定するノートブック ID"),
) -> None:
    """デフォルトノートブックを設定"""
    update_config(default_notebook_id=notebook_id)
    console.print(f"[bold green]デフォルトノートブックを設定:[/] {notebook_id}")
