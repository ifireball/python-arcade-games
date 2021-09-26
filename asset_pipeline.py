from __future__ import annotations
"""asset_pipeline.py - Processing raw media files into game assets"""

from dataclasses import dataclass
from typing import Collection, Mapping


INPUT_DIR = "resource_making"
OUTPUT_DIR = "resources"
CONFIG_FILE = "asset_pipeline.toml"


@dataclass(frozen=True)
class Configuration:
    tilesets: Mapping[str, TilesetConfiguration]


@dataclass(frozen=True)
class TilesetConfiguration:
    name: str
    animations: Mapping[str, AnimationConfiguration]


@dataclass(frozen=True)
class AnimationConfiguration:
    source_file_patterns: Collection[str]
    duration: float


def main() -> None:
    ...


if __name__ == "__main__":
    main()
