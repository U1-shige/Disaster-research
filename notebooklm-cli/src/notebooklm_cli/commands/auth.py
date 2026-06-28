"""認証管理コマンド"""

from __future__ import annotations

import subprocess
import sys

import typer
from rich.console import Console

from ..config import get_config, update_config

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def login(
    profile: str = typer.Option("default", "--profile", "-p", help="プロファイル名"),
    browser: str = typer.Option("chrome", "--browser", "-b", help="使用するブラウザ"),
) -> None:
    """Google アカウントでログイン"""
    update_config(profile=profile)
    cmd = ["notebooklm", "login", "--browser", browser]
    if profile != "default":
        cmd.extend(["--profile", profile])
    console.print(f"[bold blue]ブラウザで Google 認証を開始します...[/]")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        console.print("[bold green]ログイン成功[/]")
    else:
        console.print("[bold red]ログインに失敗しました[/]")
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """認証状態を確認"""
    result = subprocess.run(
        ["notebooklm", "auth", "check", "--test", "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[bold green]認証済み[/]")
        config = get_config()
        console.print(f"  プロファイル: {config.profile}")
    else:
        console.print("[bold red]未認証 — `nlm-research auth login` を実行してください[/]")
        raise typer.Exit(code=1)


@app.command()
def refresh() -> None:
    """認証トークンを更新"""
    result = subprocess.run(
        ["notebooklm", "auth", "refresh", "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[bold green]トークンを更新しました[/]")
    else:
        console.print("[bold red]トークン更新に失敗しました。再ログインしてください[/]")
        raise typer.Exit(code=1)


@app.command("switch")
def switch_profile(
    profile: str = typer.Argument(help="切り替え先のプロファイル名"),
) -> None:
    """アクティブなプロファイルを切り替え"""
    update_config(profile=profile)
    console.print(f"[bold green]プロファイルを '{profile}' に切り替えました[/]")
