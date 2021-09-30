from __future__ import annotations

import inspect
import random
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from random import randrange
from types import MappingProxyType
from typing import Any, Callable, Collection, Dict, Mapping, MutableMapping, Sequence, Tuple, Type, TypeVar

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
class AnimationFrame:
    image: pygame.Surface
    duration: int


@dataclass(frozen=True)
class Animation:
    frames: Tuple[AnimationFrame]

    @classmethod
    def load_from_sprite_sheet(
        cls, sprite_sheet: SpriteSheet, frames: Collection[Tuple[int, int], ...], duration: float
    ) -> Animation:
        frame_duration = int(duration * 1000.0 / len(frames))
        return cls(
            frames=tuple(AnimationFrame(sprite_sheet.get_frame_at(x, y), frame_duration) for x, y in frames),
        )

    @classmethod
    def load_from_tmx_tile(cls, tmx_data: pytmx.TiledMap, tile_id: int) -> Animation:
        tile_data: Mapping[str, Any] = tmx_data.tile_properties.get(tile_id, {})
        frames: Collection[pytmx.pytmx.AnimationFrame] = tile_data.get('frames', [
            pytmx.pytmx.AnimationFrame(tile_id, 0)
        ])
        return cls(frames=tuple(
            AnimationFrame(tmx_data.get_tile_image_by_gid(tile_frame_id), tile_frame_duration)
            for tile_frame_id, tile_frame_duration in frames
        ))

    @classmethod
    def load_from_tmx_by_name(cls, tmx_data: pytmx.TiledMap, name: str) -> Animation:
        try:
            tile_id = next(
                tid for tid, props in tmx_data.tile_properties.items() if props.get('animation_name') == name
            )
        except StopIteration as e:
            raise KeyError(f"Animation {name} not found in TMX data") from e
        return cls.load_from_tmx_tile(tmx_data, tile_id)



@dataclass()
class AnimationPlayer:
    animation: Animation

    _current_frame_idx: int = field(default=0, init=False)
    _current_frame_time: int = field(default=0, init=False)
    _current_frame_duration: int = field(init=False)
    _animation: Animation = field(init=False)

    @property
    def animation(self) -> Animation:
        return self._animation

    @animation.setter
    def animation(self, value: Animation) -> None:
        self._current_frame_idx = 0
        self._current_frame_time = 0
        self._animation = value
        self._current_frame_duration = self._animation.frames[self._current_frame_idx].duration

    @property
    def current_frame(self) -> pygame.Surface:
        return self.animation.frames[self._current_frame_idx].image

    def update(self, dt: int = 0) -> None:
        if self._current_frame_duration <= 0:
            return
        frames = self.animation.frames
        self._current_frame_time += dt
        while self._current_frame_time > self._current_frame_duration:
            self._current_frame_idx = (self._current_frame_idx + 1) % len(frames)
            self._current_frame_time -= self._current_frame_duration
            self._current_frame_duration = frames[self._current_frame_idx].duration


@dataclass(frozen=True)
class CharacterAnimation:
    frames: Mapping[Direction, Animation]

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
        final_frames = defaultdict(lambda: final_frames[Direction.IDLE], final_frames)
        return cls(MappingProxyType(final_frames))

    @classmethod
    def load_from_tmx_by_name(cls, tmx_data: pytmx.TiledMap, name: str):
        return cls(MappingProxyType(defaultdict(lambda: Animation.load_from_tmx_by_name(tmx_data, name))))


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


class MapObject(metaclass=ABCMeta):
    __known_classes: MutableMapping[str, Type[MapObject]] = dict()

    def __init_subclass__(cls: Type[MapObject], **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            MapObject.__known_classes[cls.__name__] = cls

    @classmethod
    @abstractmethod
    def create_from_map_object(cls, obj: pytmx.TiledObject, game: QuestGame) -> None:
        obj_type = obj.type or obj.properties.get("type")
        MapObject.__known_classes[obj_type].create_from_map_object(obj, game)


class Entity(pygame.sprite.Sprite, metaclass=ABCMeta):
    def __init__(self, game: QuestGame) -> None:
        super().__init__()
        game.set_invisible_entity(self)

    @abstractmethod
    def update(self, dt: int, game: QuestGame) -> None:
        pass


class AnimatedEntity(Entity):
    def __init__(self, animation: CharacterAnimation, game: QuestGame) -> None:
        super().__init__(game)

        self.animation = animation
        self.direction = Direction.IDLE
        self.animation_player = AnimationPlayer(self.animation.frames[self.direction])
        self.image = self.animation_player.current_frame
        self.velocity = [0.0, 0.0]
        self._position = [0.0, 0.0]
        self._old_position = [0.0, 0.0]
        self.rect = self.image.get_rect()
        self.feet = pygame.rect.Rect(0.0, 0.0, self.rect.width * 0.5, 8.0)

    @property
    def position(self) -> Tuple[float, float]:
        return self._position[0], self._position[1]

    @position.setter
    def position(self, value: Sequence[float]) -> None:
        self._position = [value[0], value[1]]

    @property
    def midbottom(self) -> Tuple[float, float]:
        return self.rect.midbottom

    @midbottom.setter
    def midbottom(self, value: Sequence[float]) -> None:
        self.rect.midbottom = value
        self.position = self.rect.topleft

    def update(self, dt: int, game: QuestGame) -> None:
        self._old_position = self._position[:]
        self._position[0] += self.velocity[0] * dt / 1000.0
        self._position[1] += self.velocity[1] * dt / 1000.0
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
            self.animation_player.update(dt)
        else:
            self.direction = new_direction
            self.animation_player.animation = self.animation.frames[self.direction]
        self.image = self.animation_player.current_frame

    def move_back(self) -> None:
        """Called after update() to cancel motion"""
        self._position = self._old_position
        self.rect.topleft = self._position
        self.feet.midbottom = self.rect.midbottom

    def on_hero_touch(self, hero: Hero, game: QuestGame) -> None:
        print(f"Player touched entity {self} at {self.rect.center}")

    def on_exit_world(self, game: QuestGame) -> None:
        self.kill()
        print(f"Entity: {self} had left this world")

    def really_touch(self, other: AnimatedEntity):
        return self.feet.colliderect(other.feet)


class SpawnableEntity(AnimatedEntity, MapObject, metaclass=ABCMeta):
    __known_classes: MutableMapping[str, Type[SpawnableEntity]] = dict()

    def __init_subclass__(cls: Type[SpawnableEntity], **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            SpawnableEntity.__known_classes[cls.__name__] = cls

    @classmethod
    @abstractmethod
    def spawn(cls, location: Tuple[int, int], game: QuestGame) -> SpawnableEntity:
        ...

    @classmethod
    def spawn_by_class(cls, obj_class: str, location: Tuple[int, int], game: QuestGame) -> SpawnableEntity:
        return SpawnableEntity.__known_classes[obj_class].spawn(location, game)

    @classmethod
    def create_from_map_object(cls, obj: pytmx.TiledObject, game: QuestGame) -> None:
        obj_type = obj.type or obj.properties.get("type")
        SpawnableEntity.spawn_by_class(obj_type, (obj.x, obj.y), game)


class OnGroundEntity(AnimatedEntity, metaclass=ABCMeta):
    def __init__(self, animation: CharacterAnimation, game: QuestGame) -> None:
        super().__init__(animation, game)
        game.place_entity_on_ground(self)


class TouchableEntity(AnimatedEntity, metaclass=ABCMeta):
    def __init__(self, animation: CharacterAnimation, game: QuestGame) -> None:
        super().__init__(animation, game)
        game.make_entity_touchable(self)

    @abstractmethod
    def on_hero_touch(self, hero: Hero, game: QuestGame) -> None:
        pass


class FlyingEntity(AnimatedEntity, metaclass=ABCMeta):
    def __init__(self, animation: CharacterAnimation, game: QuestGame) -> None:
        super().__init__(animation, game)
        game.place_entity_in_sky(self)


class EscapingEntity(AnimatedEntity, metaclass=ABCMeta):
    def __init__(self, animation: CharacterAnimation, game: QuestGame) -> None:
        super().__init__(animation, game)
        game.set_world_escaping_entity(self)


class Hero(OnGroundEntity, EscapingEntity):
    def __init__(self, game: QuestGame):
        super().__init__(load_hero_animation(), game)

    def on_exit_world(self, game: QuestGame) -> None:
        self.move_back()


class CollectibleBalloons(OnGroundEntity, TouchableEntity, SpawnableEntity):
    @classmethod
    def spawn(cls, location: Tuple[int, int], game: QuestGame) -> SpawnableEntity:
        balloons = game.make_animated_entity(cls, "balloons-on-ground")
        balloons.position = location
        return balloons

    def on_hero_touch(self, hero: Hero, game: QuestGame) -> None:
        self.kill()
        animations = ["balloons-red-fly", "balloons-green-fly", "balloons-blue-fly"]
        velocities = [[0, -60], [-16, -58], [16, -58]]
        for animation, velocity in zip(animations, velocities):
            flying_balloon = game.make_animated_entity(FlyingBalloon, animation)
            flying_balloon.position = self.position
            flying_balloon.velocity = velocity


class FlyingBalloon(FlyingEntity, EscapingEntity):
    pass


class Spawner(Entity, MapObject):
    def __init__(self, game: QuestGame):
        super().__init__(game)
        self.spawn_timeout_min = 5000
        self.spawn_timeout_max = 5001
        self.spawn_timer = 0
        self.spawn_timeout = randrange(self.spawn_timeout_min, self.spawn_timeout_max)
        self.spawned_classes = ("CollectibleBalloons",)
        self.spawn_max = 4
        self.spawned_objects = pygame.sprite.Group()

    MAP_CONFIGURABLE_INT_ATTRS = ("spawn_timeout_min", "spawn_timeout_max", "spawn_max")

    @classmethod
    def create_from_map_object(cls, obj: pytmx.TiledObject, game: QuestGame) -> None:
        instance = cls(game)
        instance.rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
        for attr in cls.MAP_CONFIGURABLE_INT_ATTRS:
            if attr in obj.properties:
                setattr(instance, attr, int(obj.properties[attr]))
        spawned_classes = obj.properties.get("spawned_classes", "").split()
        if spawned_classes:
            instance.spawned_classes = spawned_classes

    def update(self, dt: int, game: QuestGame) -> None:
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_timeout:
            self.do_spawn(game)
            self.spawn_timer = 0
            self.spawn_timeout = randrange(self.spawn_timeout_min, self.spawn_timeout_max)

    def do_spawn(self, game: QuestGame):
        if 0 < self.spawn_max <= len(self.spawned_objects):
            print(f"{self} at {self.rect}: reached spawn limit: {self.spawn_max}")
            return
        location = (randrange(self.rect.left, self.rect.right + 1), randrange(self.rect.top, self.rect.bottom + 1))
        obj_class = random.choice(self.spawned_classes)
        obj = SpawnableEntity.spawn_by_class(obj_class, location, game)
        obj.midbottom = location
        self.spawned_objects.add(obj)
        print(f"{self} at {self.rect}: spawned {obj} as {location}")


AnimatedEntityType = TypeVar("AnimatedEntityType", bound=AnimatedEntity)


class QuestGame:
    def __init__(self, screen: Screen) -> None:
        self.running: bool = False
        self.screen = screen

        self.tmx_data = tmx_data = load_map("grasslands.tmx")
        map_data = pyscroll.data.TiledMapData(tmx_data)

        self.map_layer = pyscroll.BufferedRenderer(map_data, screen.surface.get_size(), clamp_camera=True)
        self.layered_draw_group = pyscroll.PyscrollGroup(map_layer=self.map_layer)
        self.touchable = pygame.sprite.Group()
        self.world_escaping = pygame.sprite.Group()
        self.invisible = pygame.sprite.Group()

        self.walls = [
            pygame.Rect(wall.x, wall.y, wall.width, wall.height)
            for wall in tmx_data.layernames.get(MAP_WALLS_LAYER, [])
        ]
        self.world_rect = self.map_layer.map_rect
        self.sprite_layer_number = \
            next((idx for idx, layer in enumerate(tmx_data.layers) if layer.name == MAP_SPRITES_LAYER), 0)
        self.topmost_layer_number = max(layer.id for layer in tmx_data.layers) - 1

        for obj in tmx_data.objects:
            if not obj.type and "type" not in obj.properties:
                continue
            MapObject.create_from_map_object(obj, self)

        self.hero = Hero(self)
        self.hero.position = self.world_rect.center

    def make_animated_entity(self, ent_class: Type[AnimatedEntityType], animation_name: str) -> AnimatedEntityType:
        return ent_class(CharacterAnimation.load_from_tmx_by_name(self.tmx_data, animation_name), self)

    def make_entity_touchable(self, ent: AnimatedEntity) -> None:
        self.touchable.add(ent)

    def place_entity_on_ground(self, ent: AnimatedEntity) -> None:
        self.layered_draw_group.add(ent, layer=self.sprite_layer_number)
        self.invisible.remove(ent)

    def place_entity_in_sky(self, ent: AnimatedEntity) -> None:
        self.layered_draw_group.add(ent, layer=self.topmost_layer_number)
        self.invisible.remove(ent)

    def set_world_escaping_entity(self, ent: AnimatedEntity):
        self.world_escaping.add(ent)

    def set_invisible_entity(self, ent: Entity):
        self.layered_draw_group.remove(ent)
        self.invisible.add(ent)

    def draw(self, surface: pygame.Surface) -> None:
        self.layered_draw_group.center(self.hero.rect.center)
        self.layered_draw_group.draw(surface)

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

    @property
    def visible_rect(self) -> pygame.Rect:
        return self.layered_draw_group.view

    def update(self, dt: int) -> None:
        self.invisible.update(dt, self)
        self.layered_draw_group.update(dt, self)
        if self.hero.feet.collidelist(self.walls) >= 0:
            self.hero.move_back()
        # print(self.hero.feet, self.world_rect)
        for ent in self.world_escaping:
            assert isinstance(ent, AnimatedEntity)
            if not self.world_rect.contains(ent.feet):
                ent.on_exit_world(self)

        touched_objects = pygame.sprite.spritecollide(self.hero, self.touchable, False)
        for obj in touched_objects:
            assert isinstance(obj, AnimatedEntity)
            if not self.hero.really_touch(obj):
                continue
            obj.on_hero_touch(self.hero, self)


    def run(self) -> None:
        clock = pygame.time.Clock()
        fps = 60
        self.running = True

        try:
            while self.running:
                dt = clock.tick(fps)
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
