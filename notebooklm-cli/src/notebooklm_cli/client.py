"""NotebookLM クライアント管理"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from notebooklm import NotebookLMClient

from .config import get_config


@asynccontextmanager
async def get_client() -> AsyncGenerator[NotebookLMClient, None]:
    config = get_config()
    async with NotebookLMClient.from_storage(profile=config.profile) as client:
        yield client


def run_async(coro):
    """非同期関数を同期的に実行するヘルパー"""
    return asyncio.run(coro)
