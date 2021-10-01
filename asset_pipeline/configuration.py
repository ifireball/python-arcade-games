from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Mapping, Optional

import toml


@dataclass(frozen=True)
class Configuration:
    tilesets: Mapping[str, TilesetConfiguration]

    @classmethod
    def from_toml(cls, file_path: Path) -> Configuration:
        return cls.from_mapping(toml.load(file_path))

    @classmethod
    def from_mapping(cls, data: Mapping) -> Configuration:
        return Configuration(
            tilesets={
                key: TilesetConfiguration.from_mapping(value)
                for key, value in data.items()
                if isinstance(value, Mapping) and value.get('type', 'tileset') == 'tileset'
            }
        )


@dataclass(frozen=True)
class TilesetConfiguration:
    animations: Mapping[str, AnimationConfiguration]

    @classmethod
    def from_mapping(cls, data: Mapping) -> TilesetConfiguration:
        animations = data.get('animations', {})
        if not isinstance(animations, Mapping):
            raise ValueError("`animations` key in a tileset entry does not contain a mapping")
        return TilesetConfiguration(
            animations={
                key: AnimationConfiguration.from_mapping(value)
                for key, value in animations.items()
                if isinstance(value, Mapping)
            }
        )


@dataclass(frozen=True)
class AnimationConfiguration:
    source_file_patterns: Collection[str]
    duration: int
    game_class: Optional[str] = None

    @classmethod
    def from_mapping(cls, data: Mapping):
        source_file_patterns = data['from']
        if (
                isinstance(source_file_patterns, str)
                or not isinstance(source_file_patterns, Collection)
                or any(not isinstance(pattern, str) for pattern in source_file_patterns)
        ):
            raise ValueError(f"Animation `from` key given as {type(source_file_patterns)}, should be a list of strings")
        duration = data['duration']
        if not isinstance(duration, int):
            raise ValueError("Animation duration must be specified as an integer value")
        return AnimationConfiguration(source_file_patterns, duration, data.get('game_class'))
