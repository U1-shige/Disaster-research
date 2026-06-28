"""設定管理モジュール"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CONFIG_DIR = Path.home() / ".config" / "nlm-research"
CONFIG_FILE = CONFIG_DIR / "config.json"
DOWNLOAD_DIR = CONFIG_DIR / "downloads"


class Config(BaseModel):
    default_notebook_id: str | None = None
    default_language: str = Field(default="ja")
    download_dir: str = Field(default_factory=lambda: str(DOWNLOAD_DIR))
    profile: str = Field(default="default")

    @classmethod
    def load(cls) -> Config:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            return cls(**data)
        return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.model_dump(), indent=2, ensure_ascii=False))

    def get_download_path(self) -> Path:
        path = Path(self.download_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


def get_config() -> Config:
    return Config.load()


def update_config(**kwargs: Any) -> Config:
    config = Config.load()
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.save()
    return config
