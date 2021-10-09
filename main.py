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
import pymunk
import pymunk.pygame_util
import pymunk.autogeometry
import pyscroll.data
import pytmx

from game.controls import Controls


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

    @classmethod
    def from_vector(cls, vx: float, vy: float, tolerance: float = 10.0) -> Direction:
        if vx < -tolerance:
            direction = Direction.WEST
        elif vx > tolerance:
            direction = Direction.EAST
        elif vy < -tolerance:
            direction = Direction.NORTH
        elif vy > tolerance:
            direction = Direction.SOUTH
        else:
            direction = Direction.IDLE
        return direction


@dataclass(frozen=True)
class AnimationFrame:
    image: pygame.Surface
    duration: int


@dataclass(frozen=True)
class Animation:
    frames: Tuple[AnimationFrame]

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
    def load_from_tmx_by_name(cls, tmx_data: pytmx.TiledMap, name: str):
        animations = {}
        for direction in Direction:
            direction_name = f"{name}.{direction.name.lower()}"
            try:
                animations[direction] = Animation.load_from_tmx_by_name(tmx_data, direction_name)
            except KeyError:
                if direction == Direction.IDLE:
                    animations[direction] = Animation.load_from_tmx_by_name(tmx_data, name)
                else:
                    pass
        return cls(MappingProxyType(defaultdict(lambda: animations[Direction.IDLE], animations)))


class MapObject(metaclass=ABCMeta):
    __known_classes: MutableMapping[str, Type[MapObject]] = dict()

    def __init_subclass__(cls: Type[MapObject], **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            MapObject.__known_classes[cls.__name__] = cls

    @classmethod
    @abstractmethod
    def create_from_map_object(cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame) -> None:
        obj_type = obj.type or obj.properties.get("type") or group.properties.get("default_type")
        if not obj_type:
            return
        MapObject.__known_classes[obj_type].create_from_map_object(group, obj, game)


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
        self._velocity = [0.0, 0.0]
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

    @property
    def velocity(self) -> Tuple[float, float]:
        return self._velocity[0], self._velocity[1]

    @velocity.setter
    def velocity(self, value: Sequence[float]) -> None:
        self._velocity = [value[0], value[1]]

    def update(self, dt: int, game: QuestGame) -> None:
        self.update_position(dt)
        self.update_image(dt)

    def update_image(self, dt) -> None:
        new_direction = self.calculate_animation_direction()
        if self.direction == new_direction:
            self.animation_player.update(dt)
        else:
            self.direction = new_direction
            self.animation_player.animation = self.animation.frames[self.direction]
        self.image = self.animation_player.current_frame

    def calculate_animation_direction(self) -> Direction:
        return Direction.from_vector(*self.velocity)

    def update_position(self, dt) -> None:
        self._old_position = self._position[:]
        self._position[0] += self.velocity[0] * dt / 1000.0
        self._position[1] += self.velocity[1] * dt / 1000.0
        self.rect.topleft = self._position
        self.feet.midbottom = self.rect.midbottom

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
    def create_from_map_object(cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame) -> None:
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


class Hero(OnGroundEntity, MapObject):
    @classmethod
    def create_from_map_object(cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame) -> None:
        if game.hero:
            raise ValueError("More then one Hero starting point found on map")
        game.hero = game.make_animated_entity(Hero, "hero")
        game.hero.topleft = (obj.x, obj.y)

    def __init__(self, animation: CharacterAnimation, game: QuestGame) -> None:
        super().__init__(animation, game)
        self.pymunk_body = pymunk.Body()
        pymunk_shape = pymunk.Circle(self.pymunk_body, 10.0)
        pymunk_shape.mass = 1.0
        pymunk_shape.friction = 0.5
        pymunk_shape.color = pygame.Color("pink")
        pymunk_shape.elasticity = 0.1
        game.pymunk_space.add(
            self.pymunk_body,
            pymunk_shape,
        )

    @property
    def topleft(self) -> Tuple[float, float]:
        return tuple(self.rect.topleft)

    @topleft.setter
    def topleft(self, value: Sequence[float]):
        self.rect.topleft = value[0], value[1]
        self.position = self.rect.midbottom[0], self.rect.midbottom[1] - 10.0

    @property
    def position(self) -> Tuple[float, float]:
        return self.pymunk_body.position

    @position.setter
    def position(self, value: Sequence[float]) -> None:
        self.pymunk_body.position = value
        # self.pymunk_control_body.position = self.pymunk_body.position
        print(f"hero.pymunk_body at: {self.pymunk_body.position} v={self.pymunk_body.velocity} ({self.pymunk_body})")

    @property
    def velocity(self) -> Tuple[float, float]:
        return self.pymunk_body.velocity

    @velocity.setter
    def velocity(self, value: Sequence[float]) -> None:
        self.pymunk_body.velocity = value[0], value[1]

    def update_position(self, dt) -> None:
        self.rect.midbottom = self.position[0], self.position[1] + 10.0
        self.feet.midbottom = self.rect.midbottom

    def move_back(self) -> None:
        pass

    def apply_controls(self, controls: Controls) -> None:
        if controls.speedup_pressed:
            max_velocity = 500.0
        else:
            max_velocity = 250.0
        current_velocity = self.pymunk_body.velocity
        if current_velocity.length > max_velocity:
            self.pymunk_body.force = current_velocity * -10.0
            return
        if controls.up_pressed:
            if controls.left_pressed:
                angle = 135.0
            elif controls.right_pressed:
                angle = 225.0
            else:
                angle = 180.0
        elif controls.down_pressed:
            if controls.left_pressed:
                angle = 45.0
            elif controls.right_pressed:
                angle = -45.0
            else:
                angle = 0.0
        elif controls.left_pressed:
            angle = 90.0
        elif controls.right_pressed:
            angle = -90.0
        else:
            self.pymunk_body.force = current_velocity * -10.0
            return
        control_force = pymunk.Vec2d(0.0, 500.0).rotated_degrees(angle)
        self.pymunk_body.force = control_force


class CollectibleBalloons(OnGroundEntity, TouchableEntity, SpawnableEntity):
    @classmethod
    def spawn(cls, location: Tuple[int, int], game: QuestGame) -> SpawnableEntity:
        balloons = game.make_animated_entity(cls, "collectibles.balloons-on-ground")
        balloons.position = location
        return balloons

    def on_hero_touch(self, hero: Hero, game: QuestGame) -> None:
        self.kill()
        animations = [
            "collectibles.balloons-red-fly", "collectibles.balloons-green-fly", "collectibles.balloons-blue-fly"
        ]
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
    def create_from_map_object(cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame) -> None:
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


class HudElement(Entity, MapObject):
    def __init__(self, rect: pygame.Rect, image: pygame.Surface, game: QuestGame):
        super().__init__(game)
        self.rect = rect
        self.image = image
        game.add_hud_element(self)

    @classmethod
    def create_from_map_object(cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame) -> None:
        cls(pygame.Rect(obj.x, obj.y, obj.width, obj.height), obj.image, game)

    def update(self, dt: int, game: QuestGame) -> None:
        pass


class Wall(Entity, MapObject):
    def update(self, dt: int, game: QuestGame) -> None:
        pass

    @classmethod
    def create_pymunk_shapes(
        cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame
    ) -> Sequence[pymunk.Shape]:
        source_points = obj.points if hasattr(obj, "points") else obj.as_points
        if not pymunk.autogeometry.is_closed(source_points):
            source_points = source_points + source_points[:1]
        point_sets = pymunk.autogeometry.convex_decomposition(source_points, 5.0)
        shapes = []
        for point_set in point_sets:
            shape = pymunk.Poly(body=game.pymunk_space.static_body, vertices=point_set)
            shape.elasticity = 0.0
            shape.friction = 0.5
            shade = randrange(96, 224)
            shape.color = pygame.Color(shade, shade, shade, 127)
            game.pymunk_space.add(shape)
            shapes.append(shape)
        return shapes

    @classmethod
    def create_from_map_object(cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame) -> None:
        cls.create_pymunk_shapes(group, obj, game)


class PolyWall(Wall):
    @classmethod
    def create_pymunk_shapes(
        cls, group: pytmx.TiledObjectGroup, obj: pytmx.TiledObject, game: QuestGame
    ) -> Sequence[pymunk.Shape]:
        shapes = super().create_pymunk_shapes(group, obj, game)
        for shape in shapes:
            shape.elasticity = 7.5
        return shapes


AnimatedEntityType = TypeVar("AnimatedEntityType", bound=AnimatedEntity)


class QuestGame:
    def __init__(self, screen: Screen) -> None:
        self.running: bool = False
        self.screen = screen
        self.controls = Controls()

        self.tmx_data = tmx_data = load_map("fields.tmx")
        map_data = pyscroll.data.TiledMapData(tmx_data)

        self.map_layer = pyscroll.BufferedRenderer(map_data, screen.surface.get_size(), clamp_camera=True)
        self.layered_draw_group = pyscroll.PyscrollGroup(map_layer=self.map_layer)
        self.touchable = pygame.sprite.Group()
        self.world_escaping = pygame.sprite.Group()
        self.invisible = pygame.sprite.Group()
        self.hero = None
        self.hud_elements = pygame.sprite.Group()

        self.pymunk_space = pymunk.Space()
        self.pymunk_draw_options = pymunk.pygame_util.DrawOptions(self.screen.surface)
        self.debug_draw = False

        self.world_rect = self.map_layer.map_rect
        self.sprite_layer_number = \
            next((idx for idx, layer in enumerate(tmx_data.layers) if layer.name == MAP_SPRITES_LAYER), 0)
        self.topmost_layer_number = max(layer.id for layer in tmx_data.layers) - 1

        for group in tmx_data.objectgroups:
            for obj in group:
                MapObject.create_from_map_object(group, obj, self)


    def add_hud_element(self, elm: HudElement):
        self.hud_elements.add(elm)
        self.invisible.remove(elm)

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
        self.layered_draw_group.center((self.hero.rect.center[0], self.hero.rect.center[1] + 32))
        self.layered_draw_group.draw(surface)
        if self.debug_draw:
            view_vec = pymunk.Vec2d(*self.map_layer.view_rect.topleft) * -1
            transform = pymunk.Transform.translation(*view_vec)
            self.pymunk_draw_options.transform = transform
            self.pymunk_space.debug_draw(self.pymunk_draw_options)
        self.hud_elements.draw(surface)

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if self.controls.handle_events(event):
                pass
            elif event.type == pygame.QUIT:
                self.running = False
                break
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    break
                elif event.key == pygame.K_d:
                    self.debug_draw = not self.debug_draw
                    self.debug_dump()
            self.screen.handle_events(event, resize_callback=self.map_layer.set_size)

        self.hero.apply_controls(self.controls)

    def debug_dump(self):
        print(f"viewport at: {self.map_layer.view_rect}")
        print(f"Hero at: {self.hero.position}")
        print(f"g={self.pymunk_space.gravity}")
        print([f"{b} at {b.position} v={b.velocity}" for b in self.pymunk_space.bodies])
        print([f"{s} at {s.center_of_gravity}" for s in self.pymunk_space.shapes])

    @property
    def visible_rect(self) -> pygame.Rect:
        return self.layered_draw_group.view

    def update(self, dt: int) -> None:
        self.invisible.update(dt, self)
        self.layered_draw_group.update(dt, self)
        self.pymunk_space.step(1.0 / 60.0)
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
    def __init__(self, width: int = 768) -> None:
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
