from __future__ import annotations

from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import Optional, Sequence, Tuple, cast, overload
from xml.etree.ElementTree import Element

import pygame
from rich import print

from .configuration import AnimationConfiguration
from .slicer import Slicer


@dataclass(frozen=True)
class AnimationFrames(Sequence[pygame.Surface]):
    name: str
    duration: int
    frames: Tuple[pygame.Surface]

    @overload
    def __getitem__(self, i: int) -> pygame.Surface: ...

    @overload
    def __getitem__(self, s: slice) -> Sequence[pygame.Surface]: ...

    def __getitem__(self, i):
        return self.frames[i]

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def frame_duration(self) -> int:
        return self.duration // len(self)

    @classmethod
    def from_configuration(cls, name: str, animation_cfg: AnimationConfiguration, input_path: Path) -> AnimationFrames:
        frame_files = \
            list(chain.from_iterable(
                sorted(input_path.glob(pattern)) for pattern in animation_cfg.source_file_patterns
            ))
        print(f"Making animation: {name} from files: {[f.name for f in frame_files]}")
        frames = (cast(pygame.Surface, pygame.image.load(frame_file)) for frame_file in frame_files)
        if animation_cfg.slice_frames:
            slicer = Slicer.from_configuration(animation_cfg.slice_frames)
            frames = chain.from_iterable(map(slicer.slice_and_pick, frames))
        return AnimationFrames(
            name=name,
            duration=animation_cfg.duration,
            frames=tuple(frames),
        )


@dataclass(frozen=True)
class OptimizedAnimationInfo:
    name: str
    frames: Tuple[TileAnimationFrame] = field(default_factory=tuple)
    game_class: Optional[str] = None

    def with_appended_frame(self, tile_id: int, duration: int) -> OptimizedAnimationInfo:
        """Returns a new OptimizedAnimationInfo object with the given frame added. If the tile of the new frame is
        identical to the one that precedes it, the existing frame duration will be extended instead of adding a new
        frame"""
        if self.frames and (last_frame := self.frames[-1]).tile_id == tile_id:
            new_frames = \
                self.frames[:-1] + (TileAnimationFrame(tile_id=tile_id, duration=last_frame.duration + duration),)
        else:
            new_frames = self.frames + (TileAnimationFrame(tile_id=tile_id, duration=duration),)
        return OptimizedAnimationInfo(name=self.name, frames=new_frames, game_class=self.game_class)


@dataclass(frozen=True)
class TileAnimationFrame:
    tile_id: int
    duration: int

    def to_xml(self) -> Element:
        return Element('frame', tileid=str(self.tile_id), duration=str(self.duration))
