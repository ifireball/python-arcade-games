from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Collection

from .configuration import Configuration
from .tiles import TileSet


@dataclass(frozen=True)
class AssetCollection:
    tilesets: Collection[TileSet]

    @classmethod
    def from_configuration(cls, cfg: Configuration, input_path: Path) -> AssetCollection:
        return AssetCollection(
            tilesets=[
                TileSet.from_configuration(name, tileset_cfg, input_path)
                for name, tileset_cfg in cfg.tilesets.items()
            ]
        )
