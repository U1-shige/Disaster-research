"""ソース管理コマンド"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..client import get_client, run_async
from ..config import get_config

app = typer.Typer(no_args_is_help=True)
console = Console()


def _resolve_notebook_id(notebook_id: str | None) -> str:
    if notebook_id:
        return notebook_id
    config = get_config()
    if config.default_notebook_id:
        return config.default_notebook_id
    console.print("[bold red]ノートブック ID を指定するか、デフォルトを設定してください[/]")
    raise typer.Exit(code=1)


@app.command("add")
def add_source(
    target: str = typer.Argument(help="URL またはファイルパス"),
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="処理完了を待つ"),
) -> None:
    """ソースを追加（URL、PDF、テキストファイルなど）"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _add():
        async with get_client() as client:
            if target.startswith(("http://", "https://")):
                result = await client.sources.add_url(nb_id, target, wait=wait)
            else:
                path = Path(target).expanduser().resolve()
                if not path.exists():
                    console.print(f"[bold red]ファイルが見つかりません: {path}[/]")
                    raise typer.Exit(code=1)
                result = await client.sources.add_file(nb_id, str(path), wait=wait)
            return result

    result = run_async(_add())
    console.print(f"[bold green]ソース追加完了:[/] {target}")


@app.command("list")
def list_sources(
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
) -> None:
    """ソース一覧を表示"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _list():
        async with get_client() as client:
            sources = await client.sources.list(nb_id)
            return sources

    sources = run_async(_list())

    table = Table(title="ソース一覧")
    table.add_column("ID", style="dim")
    table.add_column("タイトル", style="bold")
    table.add_column("種別")

    for src in sources:
        table.add_row(src.id, src.title, getattr(src, "type", "不明"))

    console.print(table)


@app.command("remove")
def remove_source(
    source_id: str = typer.Argument(help="ソース ID"),
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    force: bool = typer.Option(False, "--force", "-f", help="確認なしで削除"),
) -> None:
    """ソースを削除"""
    nb_id = _resolve_notebook_id(notebook_id)

    if not force:
        confirm = typer.confirm(f"ソース {source_id} を削除しますか？")
        if not confirm:
            raise typer.Abort()

    async def _remove():
        async with get_client() as client:
            await client.sources.delete(nb_id, source_id)

    run_async(_remove())
    console.print(f"[bold green]ソース削除完了:[/] {source_id}")


@app.command("add-batch")
def add_batch(
    file: Path = typer.Argument(help="URL リストファイル（1行1URL）"),
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
) -> None:
    """URLリストファイルから一括でソースを追加"""
    nb_id = _resolve_notebook_id(notebook_id)

    if not file.exists():
        console.print(f"[bold red]ファイルが見つかりません: {file}[/]")
        raise typer.Exit(code=1)

    urls = [line.strip() for line in file.read_text().splitlines() if line.strip() and not line.startswith("#")]

    if not urls:
        console.print("[yellow]追加するURLがありません[/]")
        raise typer.Exit()

    async def _add_batch():
        async with get_client() as client:
            results = []
            for url in urls:
                try:
                    result = await client.sources.add_url(nb_id, url, wait=True)
                    results.append((url, True))
                    console.print(f"  [green]✓[/] {url}")
                except Exception as e:
                    results.append((url, False))
                    console.print(f"  [red]✗[/] {url}: {e}")
            return results

    console.print(f"[bold blue]{len(urls)} 件の URL を追加中...[/]")
    results = run_async(_add_batch())
    success = sum(1 for _, ok in results if ok)
    console.print(f"\n[bold green]完了:[/] {success}/{len(urls)} 件追加成功")
