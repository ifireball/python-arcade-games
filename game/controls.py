from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType
from typing import ClassVar, FrozenSet, Mapping

import pygame


class ControlTypes(IntEnum):
    UP = 0
    DOWN = 1
    LEFT = 2
    RIGHT = 3
    SPEEDUP = 4


@dataclass
class Controls:
    KEY_MAP: ClassVar[Mapping[ControlTypes, FrozenSet]] = {
        ControlTypes.UP: {pygame.K_UP, pygame.K_s},
        ControlTypes.DOWN: {pygame.K_DOWN, pygame.K_g},
        ControlTypes.LEFT: {pygame.K_LEFT, pygame.K_k},
        ControlTypes.RIGHT: {pygame.K_RIGHT, pygame.K_QUOTE},
        ControlTypes.SPEEDUP: {pygame.K_SPACE},
    }
    KEY_EVENTS: ClassVar[FrozenSet] = {pygame.KEYUP, pygame.KEYDOWN}

    _key_count_map: dict[ControlTypes, int] = field(default_factory=dict, init=False)
    _key_status_map: dict[ControlTypes, bool] = field(default_factory=dict, init=False)
    status: Mapping[ControlTypes, bool] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._key_count_map = dict.fromkeys(self.KEY_MAP, 0)
        self._key_status_map = dict.fromkeys(self.KEY_MAP, False)
        self.status = MappingProxyType(self._key_status_map)

    def handle_events(self, event: pygame.event.Event) -> bool:
        if event.type not in self.KEY_EVENTS:
            return False
        for control_type, key_set in self.KEY_MAP.items():
            if event.key in key_set:
                if event.type == pygame.KEYDOWN:
                    self._key_count_map[control_type] += 1
                elif event.type == pygame.KEYUP:
                    self._key_count_map[control_type] -= 1
                self._key_status_map[control_type] = (self._key_count_map[control_type] > 0)
                break
        else:
            return False
        return True

    @property
    def up_pressed(self) -> bool:
        return self._key_status_map[ControlTypes.UP]

    @property
    def down_pressed(self) -> bool:
        return self._key_status_map[ControlTypes.DOWN]

    @property
    def left_pressed(self) -> bool:
        return self._key_status_map[ControlTypes.LEFT]

    @property
    def right_pressed(self) -> bool:
        return self._key_status_map[ControlTypes.RIGHT]

    @property
    def speedup_pressed(self) -> bool:
        return self._key_status_map[ControlTypes.SPEEDUP]