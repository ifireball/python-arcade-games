from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Mapping, Optional, Tuple

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
class SlicerConfiguration:
    slice_width: int
    slice_height: int
    spacing: int = 0
    margin: int = 0
    pick_slices: Tuple[int, int] = ()

    @classmethod
    def from_mapping(cls, data: Mapping):
        mandatory_ints = {"slice_width", "slice_height"}
        other_ints = {"spacing", "margin"}
        clean_data = {}
        for int_attr in (mandatory_ints | other_ints) & set(data):
            if not isinstance(data[int_attr], int):
                raise ValueError(f"Slicer configuration attribute {int_attr} must be an integer value")
            clean_data[int_attr] = data[int_attr]
        missing = mandatory_ints - set(data)
        if missing:
            raise ValueError(f"Missing slicer mandatory configuration items: {missing}")
        pick_slices = data.get('pick_slices', ())
        if not (
            isinstance(pick_slices, Collection) and
            all(
                (
                    isinstance(slice_nfo, Collection) and
                    len(slice_nfo) == 2 and
                    all(isinstance(i, int) for i in slice_nfo)
                ) for slice_nfo in pick_slices
            )
        ):
            raise ValueError(f"Bad slice selection value, must be a list of number pairs")
        clean_data['pick_slices'] = pick_slices
        return SlicerConfiguration(**clean_data)


@dataclass(frozen=True)
class AnimationConfiguration:
    source_file_patterns: Collection[str]
    duration: int
    game_class: Optional[str] = None
    slice_frames: Optional[SlicerConfiguration] = None

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
        slice_frames = data.get("slice_frames", {})
        if not isinstance(slice_frames, Mapping):
            raise ValueError("Bad frame slicing configuration, must be given as a mapping)")
        return AnimationConfiguration(
            source_file_patterns=source_file_patterns,
            duration=duration,
            game_class=data.get('game_class'),
            slice_frames=SlicerConfiguration.from_mapping(slice_frames) if slice_frames else None
        )
