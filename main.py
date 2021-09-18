from __future__ import annotations

from dataclasses import Field, dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Callable, Collection, Dict, Tuple, Union

import pygame
import pyscroll.data
import pytmx

HERO_MOVE_SPEED = 200.0

MAP_SPRITES_LAYER = "sprites"
MAP_WALLS_LAYER = "walls"


def load_image(filename: str) -> pygame.Surface:
    filepath = Path(__file__).parent / 'resources' / filename
    return pygame.image.load(filepath)


def load_map(filename: str) -> pytmx.TiledMap:
    filepath = Path(__file__).parent / 'resources' / filename
    return pytmx.load_pygame(filepath)


class Direction(IntEnum):
    IDLE = 0
    NORTH = 1
    SOUTH = 2
    EAST = 3
    WEST = 4


@dataclass(frozen=True)
class SpriteSheet:
    sheet: pygame.Surface = field()
    width: int
    height: int
    _tile_cache: dict[tuple[int, int], pygame.Surface] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False
    )

    @classmethod
    def load(cls, filename: str, width: int, height: int, tile_width: int = 0, tile_height: int = 0):
        sheet_image = load_image(filename).convert_alpha()
        if tile_width > 0 and tile_height > 0:
            sheet_tile_rect = pygame.Rect(0, 0, sheet_image.get_width() / width, sheet_image.get_height() / height)
            needed_tile_rect = pygame.Rect(0, 0, tile_width, tile_height)
            adjusted_sheet_tile_rect = sheet_tile_rect.fit(needed_tile_rect)
            if adjusted_sheet_tile_rect.width < sheet_tile_rect.width:
                sheet_image = pygame.transform.smoothscale(
                    sheet_image,
                    (adjusted_sheet_tile_rect.width * width, adjusted_sheet_tile_rect.height * height)
                )
        return cls(sheet_image, width, height)

    def get_frame_at(self, x: int, y: int) -> pygame.Surface:
        try:
            return self._tile_cache[(x, y)]
        except KeyError:
            pass
        if x < 0 or y < 0:
            not_flipped = self.get_frame_at(abs(x), abs(y))
            frame = pygame.transform.flip(not_flipped, x < 0, y < 0)
        elif x == 0 or y == 0:
            raise AttributeError('Tile sheet frame coordinates must be between 1 and the sheet size')
        else:
            frame_width = self.sheet.get_width() // self.width
            frame_height = self.sheet.get_height() // self.height
            not_cropped = self.sheet.subsurface((x-1) * frame_width, (y-1) * frame_height, frame_width, frame_height)
            frame = not_cropped.copy()
        self._tile_cache[(x, y)] = frame
        return frame


@dataclass(frozen=True)
class Animation:
    frames: Tuple[pygame.Surface]
    duration: float

    @classmethod
    def load_from_sprite_sheet(cls, sprite_sheet: SpriteSheet, frames: Collection[Tuple[int, int], ...], duration: float):
        return cls(
            frames=tuple(sprite_sheet.get_frame_at(x, y) for x, y in frames),
            duration=duration
        )


@dataclass(frozen=True)
class CharacterAnimation:
    frames: Dict[Direction, Animation]

    @classmethod
    def load_from_sprite_sheet(
        cls,
        sprite_sheet: SpriteSheet,
        frames: Dict[Direction, Tuple[int, int] | Collection[Tuple[int, int] | float]],
    ):
        final_frames = {}
        for direction, frame_spec in frames.items():
            if len(frame_spec) == 2:
                if all(isinstance(v, int) for v in frame_spec):
                    frame_spec = [frame_spec]
                elif any(isinstance(v, Tuple) for v in frame_spec):
                    pass
                else:
                    raise AttributeError("Bad frame specification passed")
            spec_items = [v for v in frame_spec if isinstance(v, Tuple)]
            duration_items = [v for v in frame_spec if not isinstance(v, Tuple)]
            if len(duration_items) > 1:
                raise AttributeError("Bad frame specification: more then one duration value given")
            elif not duration_items:
                duration = 0.0
            else:
                duration = float(duration_items[0])
            final_frames[direction] = Animation.load_from_sprite_sheet(sprite_sheet, spec_items, duration)
        if Direction.IDLE not in final_frames:
            raise AttributeError("Character animation must at least include idle frames")
        return cls(final_frames)

    def get_frame(self, direction: Direction, motion_time: float = 0.0):
        animation = self.frames.get(direction, self.frames[Direction.IDLE])
        if animation.duration:
            num_frames = len(animation.frames)
            frame_num = int(num_frames * motion_time / animation.duration) % num_frames
        else:
            frame_num = 0
        return animation.frames[frame_num]


def load_hero_animation() -> CharacterAnimation:
    return CharacterAnimation.load_from_sprite_sheet(
        sprite_sheet=SpriteSheet.load("characters/character_femaleAdventurer_sheet.png", 9, 5, 48, 48),
        frames={
            Direction.IDLE: (1, 1),
            Direction.NORTH: [(7, 4), (7, 4), (-7, 4), (-7, 4), 0.4],
            Direction.SOUTH: [(4, 2), (5, 2), 0.4],
            Direction.EAST: [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5), (7, 5), (8, 5), 0.4],
            Direction.WEST: [(-1, 5), (-2, 5), (-3, 5), (-4, 5), (-5, 5), (-6, 5), (-7, 5), (-8, 5), 0.4],
        }
    )


class Hero(pygame.sprite.Sprite):
    def __init__(self) -> None:
        super().__init__()

        self.animation = load_hero_animation()
        self.direction = Direction.IDLE
        self.animation_timer = 0.0
        self.image = self.animation.get_frame(self.direction)
        self.velocity = [0.0, 0.0]
        self._position = [0.0, 0.0]
        self._old_position = [0.0, 0.0]
        self.rect = self.image.get_rect()
        self.feet = pygame.rect.Rect(0.0, 0.0, self.rect.width * 0.5, 8.0)

    @property
    def position(self) -> list[float]:
        return list(self._position)

    @position.setter
    def position(self, value: list[float]) -> None:
        self._position = list(value)

    def update(self, dt: float) -> None:
        self._old_position = self._position[:]
        self._position[0] += self.velocity[0] * dt
        self._position[1] += self.velocity[1] * dt
        self.rect.topleft = self._position
        self.feet.midbottom = self.rect.midbottom

        if self.velocity[0] < 0:
            new_direction = Direction.WEST
        elif self.velocity[0] > 0:
            new_direction = Direction.EAST
        elif self.velocity[1] < 0:
            new_direction = Direction.NORTH
        elif self.velocity[1] > 0:
            new_direction = Direction.SOUTH
        else:
            new_direction = Direction.IDLE

        if self.direction == new_direction:
            self.animation_timer += dt
        else:
            self.direction = new_direction
            self.animation_timer = 0
        self.image = self.animation.get_frame(self.direction, self.animation_timer)


    def move_back(self, dt: float) -> None:
        """Called after update() to cancel motion"""
        self._position = self._old_position
        self.rect.topleft = self._position
        self.feet.midbottom = self.rect.midbottom


class QuestGame:
    def __init__(self, screen: Screen) -> None:
        self.running: bool = False
        self.screen = screen

        tmx_data = load_map("grasslands.tmx")
        map_data = pyscroll.data.TiledMapData(tmx_data)

        self.walls = [
            pygame.Rect(wall.x, wall.y, wall.width, wall.height)
            for wall in tmx_data.layernames.get(MAP_WALLS_LAYER, [])
        ]
        self.world_rect = pygame.Rect(0, 0, tmx_data.width * tmx_data.tilewidth, tmx_data.height * tmx_data.tileheight)

        self.map_layer = pyscroll.BufferedRenderer(map_data, screen.surface.get_size(), clamp_camera=True)
        self.group = pyscroll.PyscrollGroup(map_layer=self.map_layer)

        self.hero = Hero()
        self.hero.position = self.map_layer.map_rect.center
        sprites_layer = tmx_data.layernames.get(MAP_SPRITES_LAYER)
        hero_layer = sprites_layer.id - 1 if sprites_layer else 0
        self.group.add(self.hero, layer=hero_layer)

    def draw(self, surface: pygame.Surface) -> None:
        self.group.center(self.hero.rect.center)
        self.group.draw(surface)

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                break
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    break
            self.screen.handle_events(event, resize_callback=self.map_layer.set_size)

        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_UP]:
            self.hero.velocity[1] = -HERO_MOVE_SPEED
        elif pressed[pygame.K_DOWN]:
            self.hero.velocity[1] = HERO_MOVE_SPEED
        else:
            self.hero.velocity[1] = 0
        if pressed[pygame.K_LEFT]:
            self.hero.velocity[0] = -HERO_MOVE_SPEED
        elif pressed[pygame.K_RIGHT]:
            self.hero.velocity[0] = HERO_MOVE_SPEED
        else:
            self.hero.velocity[0] = 0

    def update(self, dt: float = 0) -> None:
        self.group.update(dt)
        if self.hero.feet.collidelist(self.walls) >= 0:
            self.hero.move_back(dt)
        # print(self.hero.feet, self.world_rect)
        if not self.world_rect.contains(self.hero.feet):
            self.hero.move_back(dt)


    def run(self) -> None:
        clock = pygame.time.Clock()
        fps = 60
        self.running = True

        try:
            while self.running:
                dt = clock.tick(fps) / 1000.0
                self.handle_input()
                self.update(dt)
                self.draw(self.screen.surface)
                self.screen.flip()

        except KeyboardInterrupt:
            self.running = False
            pygame.exit()


class Screen:
    def __init__(self, width: int = 512) -> None:
        display_info = pygame.display.Info()
        self.width, self.height = width, width * display_info.current_h // display_info.current_w
        print(f"Set display size to {(self.width, self.height)}")
        self.surface = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE | pygame.SCALED)

    def handle_events(self, event: pygame.event.Event, resize_callback: Callable[[Tuple[int, int]], None] = None):
        if event.type == pygame.VIDEORESIZE:
            if resize_callback:
                resize_callback(self.surface.get_size())
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                pygame.display.toggle_fullscreen()

    @staticmethod
    def flip():
        pygame.display.flip()


def main() -> None:
    pygame.init()
    pygame.font.init()
    screen = Screen()
    pygame.display.set_caption("Quest")

    try:
        game = QuestGame(screen)
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


if __name__ == '__main__':
    main()
