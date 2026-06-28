"""質問・チャットコマンド"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

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


@app.command("ask")
def ask(
    question: str = typer.Argument(help="質問内容"),
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    save: bool = typer.Option(False, "--save", "-s", help="回答をノートとして保存"),
) -> None:
    """ノートブックのソースに基づいて質問"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _ask():
        async with get_client() as client:
            result = await client.chat.ask(nb_id, question)
            if save:
                await client.chat.save_as_note(nb_id, result)
            return result

    result = run_async(_ask())
    console.print(Panel(Markdown(result.answer), title="回答", border_style="green"))

    if hasattr(result, "citations") and result.citations:
        console.print("\n[bold]引用元:[/]")
        for cite in result.citations:
            console.print(f"  - {cite}")

    if save:
        console.print("\n[dim]回答をノートとして保存しました[/]")


@app.command("ask-file")
def ask_from_file(
    file: Path = typer.Argument(help="質問を含むファイルのパス"),
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    output: Path | None = typer.Option(None, "--output", "-o", help="回答の出力先ファイル"),
) -> None:
    """ファイルから質問を読み込んで実行"""
    nb_id = _resolve_notebook_id(notebook_id)

    if not file.exists():
        console.print(f"[bold red]ファイルが見つかりません: {file}[/]")
        raise typer.Exit(code=1)

    question = file.read_text().strip()

    async def _ask():
        async with get_client() as client:
            return await client.chat.ask(nb_id, question)

    result = run_async(_ask())
    console.print(Panel(Markdown(result.answer), title="回答", border_style="green"))

    if output:
        output.write_text(result.answer)
        console.print(f"\n[dim]回答を {output} に保存しました[/]")


@app.command("batch")
def batch_query(
    file: Path = typer.Argument(help="質問リストファイル（1行1質問）"),
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    output_dir: Path = typer.Option("./answers", "--output", "-o", help="回答出力ディレクトリ"),
) -> None:
    """複数の質問を一括実行"""
    nb_id = _resolve_notebook_id(notebook_id)

    if not file.exists():
        console.print(f"[bold red]ファイルが見つかりません: {file}[/]")
        raise typer.Exit(code=1)

    questions = [
        line.strip()
        for line in file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not questions:
        console.print("[yellow]質問がありません[/]")
        raise typer.Exit()

    output_dir.mkdir(parents=True, exist_ok=True)

    async def _batch():
        async with get_client() as client:
            for i, q in enumerate(questions, 1):
                console.print(f"\n[bold blue]質問 {i}/{len(questions)}:[/] {q}")
                try:
                    result = await client.chat.ask(nb_id, q)
                    console.print(Panel(Markdown(result.answer), border_style="green"))
                    out_file = output_dir / f"answer_{i:03d}.md"
                    out_file.write_text(f"# {q}\n\n{result.answer}\n")
                except Exception as e:
                    console.print(f"  [red]エラー: {e}[/]")

    run_async(_batch())
    console.print(f"\n[bold green]完了:[/] 回答を {output_dir} に保存しました")
