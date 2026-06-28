"""コンテンツ生成コマンド"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

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


@app.command()
def audio(
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    instructions: str = typer.Option("", "--instructions", "-i", help="生成の指示"),
    output: Path = typer.Option("./podcast.mp3", "--output", "-o", help="出力ファイルパス"),
    language: str | None = typer.Option(None, "--lang", "-l", help="言語コード（例: ja）"),
) -> None:
    """音声オーバービュー（ポッドキャスト）を生成"""
    nb_id = _resolve_notebook_id(notebook_id)
    config = get_config()
    lang = language or config.default_language

    async def _generate():
        async with get_client() as client:
            console.print("[bold blue]音声を生成中...[/]（数分かかる場合があります）")
            status = await client.artifacts.generate_audio(
                nb_id,
                instructions=instructions or None,
                language=lang,
            )
            await client.artifacts.wait_for_completion(nb_id, status.task_id)
            await client.artifacts.download_audio(nb_id, str(output))

    run_async(_generate())
    console.print(f"[bold green]音声生成完了:[/] {output}")


@app.command()
def summary(
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    output: Path | None = typer.Option(None, "--output", "-o", help="出力ファイルパス"),
) -> None:
    """ノートブックの要約レポートを生成"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _generate():
        async with get_client() as client:
            result = await client.chat.ask(
                nb_id,
                "このノートブックの全ソースの内容を包括的に要約してください。"
                "主要なポイント、重要な発見、結論を含めてください。",
            )
            return result

    result = run_async(_generate())
    console.print(result.answer)

    if output:
        output.write_text(result.answer)
        console.print(f"\n[dim]要約を {output} に保存しました[/]")


@app.command()
def quiz(
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    output: Path | None = typer.Option(None, "--output", "-o", help="出力ファイルパス"),
    format: str = typer.Option("markdown", "--format", "-f", help="出力形式（markdown/json）"),
) -> None:
    """クイズを生成"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _generate():
        async with get_client() as client:
            await client.artifacts.generate_quiz(nb_id)
            if output:
                await client.artifacts.download_quiz(nb_id, str(output), format=format)

    run_async(_generate())
    if output:
        console.print(f"[bold green]クイズ生成完了:[/] {output}")
    else:
        console.print("[bold green]クイズ生成完了[/]")


@app.command("slide-deck")
def slide_deck(
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    output: Path = typer.Option("./slides.pdf", "--output", "-o", help="出力ファイルパス"),
) -> None:
    """スライドデッキを生成"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _generate():
        async with get_client() as client:
            console.print("[bold blue]スライドを生成中...[/]")
            await client.artifacts.generate_slides(nb_id)
            await client.artifacts.download_slides(nb_id, str(output))

    run_async(_generate())
    console.print(f"[bold green]スライド生成完了:[/] {output}")


@app.command("mind-map")
def mind_map(
    notebook_id: str | None = typer.Option(None, "--notebook", "-n", help="ノートブック ID"),
    output: Path = typer.Option("./mindmap.json", "--output", "-o", help="出力ファイルパス"),
) -> None:
    """マインドマップを生成"""
    nb_id = _resolve_notebook_id(notebook_id)

    async def _generate():
        async with get_client() as client:
            console.print("[bold blue]マインドマップを生成中...[/]")
            await client.mind_maps.generate(nb_id)
            await client.mind_maps.download(nb_id, str(output))

    run_async(_generate())
    console.print(f"[bold green]マインドマップ生成完了:[/] {output}")
