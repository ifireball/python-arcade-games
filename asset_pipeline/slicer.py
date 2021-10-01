from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable, Tuple

import pygame

from asset_pipeline.configuration import SlicerConfiguration


@dataclass(frozen=True)
class Slicer:
    slice_width: int
    slice_height: int
    spacing: int = 0
    margin: int = 0
    pick_slices: Tuple[int, int] = ()

    @property
    def _slice_step_x(self) -> int:
        return self.slice_width + self.spacing + self.margin * 2

    @property
    def _slice_step_y(self) -> int:
        return self.slice_height + self.spacing + self.margin * 2

    @classmethod
    def from_configuration(cls, slicer_cfg: SlicerConfiguration) -> Slicer:
        return Slicer(**asdict(slicer_cfg))

    def slice_and_pick(self, original: pygame.Surface) -> Iterable[pygame.Surface]:
        if self.pick_slices:
            return self._get_picked_slices(original)
        else:
            return self._get_all_slices(original)

    def _get_picked_slices(self, original: pygame.Surface) -> Iterable[pygame.Surface]:
        for x, y in self.pick_slices:
            slice_x = x * self._slice_step_x + self.margin
            slice_y = y * self._slice_step_y + self.margin
            yield original.subsurface(slice_x, slice_y, self.slice_width, self.slice_height)

    def _get_all_slices(self, original: pygame.Surface) -> Iterable[pygame.Surface]:
        for slice_y in range(self.margin, original.get_height(), self._slice_step_y):
            for slice_x in range(self.margin, original.get_width(), self._slice_step_x):
                yield original.subsurface(slice_x, slice_y, self.slice_width, self.slice_height)
