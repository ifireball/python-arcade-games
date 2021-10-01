from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple
from xml.etree.ElementTree import Element


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
