"""Simple config persistence for the CLI."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path(os.getenv("UNBOUND_CONFIG_DIR", Path.home() / ".unbound"))
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_BASE_URL = "http://localhost:8000"


@dataclass
class CLIConfig:
    api_key: Optional[str]
    base_url: str = DEFAULT_BASE_URL

    def to_dict(self) -> dict:
        return {"api_key": self.api_key, "base_url": self.base_url}

    @classmethod
    def from_dict(cls, data: dict) -> "CLIConfig":
        return cls(
            api_key=data.get("api_key"),
            base_url=data.get("base_url", DEFAULT_BASE_URL),
        )


def load_config() -> CLIConfig:
    if not CONFIG_PATH.exists():
        return CLIConfig(api_key=None, base_url=DEFAULT_BASE_URL)

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return CLIConfig.from_dict(data)


def save_config(cfg: CLIConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2)


__all__ = ["CLIConfig", "load_config", "save_config", "CONFIG_PATH", "DEFAULT_BASE_URL"]
