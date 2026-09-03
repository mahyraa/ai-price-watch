"""Loads config/sources.yaml and exposes it as plain Python objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "sources.yaml"
DATA_DIR = ROOT / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SITE_DIR = ROOT / "docs"   # GitHub Pages serves /docs


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    url: str
    expect_min: int = 1


@dataclass(frozen=True)
class Config:
    sources: list[Source]
    extract_model: str
    summarize_model: str
    major_price_move: float

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        raw = yaml.safe_load(path.read_text())
        sources = [Source(**s) for s in raw["sources"]]
        models = raw.get("models", {})
        thresholds = raw.get("thresholds", {})
        return cls(
            sources=sources,
            extract_model=models.get("extract", "claude-haiku-4-5-20251001"),
            summarize_model=models.get("summarize", "claude-sonnet-5"),
            major_price_move=float(thresholds.get("major_price_move", 0.05)),
        )
