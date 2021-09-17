from __future__ import annotations

from pathlib import Path
from typing import Callable, Tuple

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


class Hero(pygame.sprite.Sprite):
    def __init__(self) -> None:
        super().__init__()

        self.image = load_image('hero.png').convert_alpha()
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
