from __future__ import annotations

from collections import deque
from colorsys import rgb_to_hls
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import NamedTuple, Optional

import arcade

from debug_utils import get_key_name

VIEWPORT_WIDTH = 1000
VIEWPORT_HEIGHT = 650
SCREEN_TITLE = "Platformer"

GAME_SCALE = 1.5
CHARACTER_SCALING = 1.0 * GAME_SCALE
TILE_SCALING = 0.5 * GAME_SCALE
COIN_SCALING = 0.5 * GAME_SCALE
TILE_PIXEL_SIZE = 128
GRID_PIXEL_SIZE = TILE_PIXEL_SIZE * TILE_SCALING

PLAYER_START_X = 64 * GAME_SCALE
PLAYER_START_Y = 255 * GAME_SCALE
PLAYER_MOVEMENT_SPEED = 5 * GAME_SCALE
PLAYER_JUMP_SPEED = 20 * GAME_SCALE
GRAVITY = 1.0 * GAME_SCALE

INSTRUCTION_BAR_SIZE = GRID_PIXEL_SIZE

LAYER_NAME_MOVING_PLATFORMS = "Moving Platforms"
LAYER_NAME_PLATFORMS = "Platforms"
LAYER_NAME_COINS = "Coins"
LAYER_NAME_FOREGROUND = "Foreground"
LAYER_NAME_BACKGROUND = "Background"
LAYER_NAME_DONT_TOUCH = "Don't Touch"
LAYER_NAME_LADDERS = "Ladders"
LAYER_NAME_PLAYER = "Player"
MOVING_PLATFORM_PROPERTIES = (
    'change_x', 'change_y', 'boundary_top', 'boundary_left', 'boundary_right', 'boundary_bottom'
)

LEVEL_MAPS = (
    ":resources:tiled_maps/map2_level_1.json",
    ":resources:tiled_maps/map2_level_2.json",
    ":resources:tiled_maps/map_with_ladders.json",
)
AMOUNT_OF_LEVELS = len(LEVEL_MAPS)

KEYS_UP = {arcade.key.UP, arcade.key.S, arcade.key.SPACE}
KEYS_DOWN = {arcade.key.DOWN, arcade.key.G}
KEYS_LEFT = {arcade.key.LEFT, arcade.key.K}
KEYS_RIGHT = {arcade.key.RIGHT, arcade.key.APOSTROPHE}

KEYS_NEXT_LEVEL = {arcade.key.N}
KEYS_FULL_SCREEN = {arcade.key.F, arcade.key.F11}
KEYS_DEBUG_DISPLAY = {arcade.key.P}


class Direction(IntEnum):
    RIGHT=0
    LEFT=1


class PlayerMode(IntEnum):
    IDLE = auto()
    WALKING = auto()
    JUMPING = auto()
    FALLING = auto()
    CLIMBING = auto()


class TexturePair(NamedTuple):
    right_facing: arcade.Texture
    left_facing: arcade.Texture

    @classmethod
    def load(cls, filename: str) -> TexturePair:
        return TexturePair(
            right_facing=arcade.load_texture(filename),
            left_facing=arcade.load_texture(filename, flipped_horizontally=True),
        )


class PlayerCharacter(arcade.Sprite):
    def __init__(self):
        super(PlayerCharacter, self).__init__(scale=CHARACTER_SCALING)

        main_path = ":resources:images/animated_characters/female_adventurer/femaleAdventurer"
        self.mode_textures = {
            PlayerMode.IDLE: [TexturePair.load(f"{main_path}_idle.png")],
            PlayerMode.JUMPING: [TexturePair.load(f"{main_path}_jump.png")],
            PlayerMode.FALLING: [TexturePair.load(f"{main_path}_fall.png")],
            PlayerMode.WALKING: [TexturePair.load(f"{main_path}_walk{i}.png") for i in range(0, 8)],
            PlayerMode.CLIMBING: [TexturePair.load(f"{main_path}_climb{i}.png") for i in range(0, 2)],
        }

        self.character_face_direction: Direction = Direction.RIGHT
        self.cur_texture_frame = 0
        self.player_mode: PlayerMode = PlayerMode.IDLE
        self.reset_frames = False
        self.progress_frames = False
        self.update_texture()

        self.is_on_ladder = False

    def update_texture(self):
        current_texture_set = self.mode_textures[self.player_mode]
        if self.reset_frames:
            self.cur_texture_frame = 0
            self.reset_frames = False
        elif self.progress_frames:
            self.cur_texture_frame = (self.cur_texture_frame + 1) % len(current_texture_set)
            self.progress_frames = False
        self.texture = current_texture_set[self.cur_texture_frame][self.character_face_direction]

    def update_player_direction(self):
        old_direction = self.character_face_direction
        if self.change_x < 0:
            self.character_face_direction = Direction.LEFT
        elif self.change_x > 0:
            self.character_face_direction = Direction.RIGHT
        self.reset_frames = self.reset_frames or (old_direction != self.character_face_direction)

    def update_player_mode(self):
        old_mode = self.player_mode
        if self.is_on_ladder and abs(self.change_y) > 1:
            self.player_mode = PlayerMode.CLIMBING
            self.progress_frames = True
        elif self.is_on_ladder and old_mode == PlayerMode.CLIMBING:
            self.player_mode = PlayerMode.CLIMBING
        elif self.change_y > 0:
            self.player_mode = PlayerMode.JUMPING
        elif self.change_y < -10:
            self.player_mode = PlayerMode.FALLING
        elif self.change_y < 0 and (old_mode == PlayerMode.JUMPING or old_mode == PlayerMode.FALLING):
            self.player_mode = PlayerMode.FALLING
        elif self.change_y == 0 and old_mode == PlayerMode.JUMPING:
            self.player_mode = PlayerMode.FALLING
        elif self.change_x == 0:
            self.player_mode = PlayerMode.IDLE
        else:
            self.player_mode = PlayerMode.WALKING
            self.progress_frames = True
        self.reset_frames = self.reset_frames or (old_mode != self.player_mode)

    def update_animation(self, delta_time: float = 1 / 60):
        self.update_player_direction()
        self.update_player_mode()
        self.update_texture()


@dataclass
class GameSettings:
    debug_display: bool = False


class MyGame(arcade.Window):
    """
    Main application class
    """

    def __init__(self):
        super().__init__(VIEWPORT_WIDTH, VIEWPORT_HEIGHT, SCREEN_TITLE, resizable=True)

        self.text_color: arcade.Color = arcade.csscolor.WHITE

        self.tile_map: Optional[arcade.TileMap] = None
        self.end_of_map: int = 0
        self.scene: Optional[arcade.Scene] = None
        self.player_sprite: Optional[PlayerCharacter] = None
        self.physics_engine: Optional[arcade.PhysicsEnginePlatformer] = None

        self.camera: Optional[arcade.Camera] = None
        self.gui_camera: Optional[arcade.Camera] = None

        self.collect_coin_sound = arcade.load_sound(":resources:sounds/coin1.wav")
        self.jump_sound = arcade.load_sound(":resources:sounds/jump1.wav")
        self.game_over = arcade.load_sound(":resources:sounds/gameover1.wav")

        self.score: int = 0
        self.level: int = 0

        self.game_settings = GameSettings()
        self.debug_key_buf: Optional[deque] = None

        self.instruction_bar = arcade.SpriteList(use_spatial_hash=True)
        sprites_loc = ":resources:onscreen_controls/shaded_light/"
        for idx, (direction, color) in enumerate(zip(
                ("up", "down", "left", "right"),
                (arcade.csscolor.BLUE, arcade.csscolor.YELLOW, arcade.csscolor.RED, arcade.csscolor.GREEN),
        )):
            button = arcade.Sprite(f"{sprites_loc}{direction}.png")
            button.color = color
            self.instruction_bar.append(button)
        self.position_instructions()

    def position_instructions(self):
        for idx, button in enumerate(self.instruction_bar):
            button.center_x = self.width * (idx+1) / 5
            button.center_y = INSTRUCTION_BAR_SIZE / 2

    def setup(self):
        """Setup the game"""
        self.camera = arcade.Camera(self.width, self.height)
        self.gui_camera = arcade.Camera(self.width, self.height)

        map_name = LEVEL_MAPS[self.level]
        layer_options = {
            LAYER_NAME_PLATFORMS: {"use_spatial_hash": True},
            LAYER_NAME_COINS: {"use_spatial_hash": True},
            LAYER_NAME_DONT_TOUCH: {"use_spatial_hash": True},
        }
        self.tile_map = arcade.TileMap(map_name, TILE_SCALING, layer_options)
        self.scene = arcade.Scene.from_tilemap(self.tile_map)

        if self.tile_map.tiled_map.background_color:
            self.background_color = self.tile_map.tiled_map.background_color
        else:
            self.background_color = arcade.csscolor.CORNFLOWER_BLUE
        arcade.set_background_color(self.background_color)
        if rgb_to_hls(*arcade.get_three_float_color(self.background_color))[1] > 0.5:
            self.text_color = arcade.csscolor.BLACK
        else:
            self.text_color = arcade.csscolor.WHITE
        self.end_of_map = self.tile_map.tiled_map.map_size.width * GRID_PIXEL_SIZE

        if LAYER_NAME_FOREGROUND in self.scene.name_mapping:
            self.scene.add_sprite_list_before(LAYER_NAME_PLAYER, LAYER_NAME_FOREGROUND)
        self.player_sprite = PlayerCharacter()
        self.player_sprite.center_x = PLAYER_START_X
        self.player_sprite.center_y = PLAYER_START_Y
        self.scene.add_sprite(LAYER_NAME_PLAYER, self.player_sprite)

        # if LAYER_NAME_MOVING_PLATFORMS in self.scene.
        for platform in self.scene.name_mapping.get(LAYER_NAME_MOVING_PLATFORMS, []):
            for prop_name in MOVING_PLATFORM_PROPERTIES:
                if prop_name in platform.properties:
                    platform.properties[prop_name] = int(platform.properties[prop_name]) * GAME_SCALE
                if (attr_value := getattr(platform, prop_name)) is not None:
                    setattr(platform, prop_name, attr_value * GAME_SCALE)
        platforms = [
            self.scene.get_sprite_list(key)
            for key in (LAYER_NAME_PLATFORMS, LAYER_NAME_MOVING_PLATFORMS)
            if key in self.scene.name_mapping
        ]
        ladders = [
            self.scene.get_sprite_list(key)
            for key in (LAYER_NAME_LADDERS,)
            if key in self.scene.name_mapping
        ]
        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite, platforms, gravity_constant=GRAVITY, ladders=ladders
        )

        self.score = 0

    def on_resize(self, width: float, height: float):
        super().on_resize(width, height)

        self.gui_camera.resize(width, height)
        self.camera.resize(width, height)
        self.position_instructions()

    def on_draw(self):
        """Render the screen"""
        arcade.start_render()

        self.camera.use()
        self.scene.draw()

        self.gui_camera.use()
        hud_text = f"Score: {self.score}"
        arcade.draw_text(
            hud_text, 20, self.gui_camera.viewport_height - 20, self.text_color, 18,
            anchor_y="top"
        )

        self.instruction_bar.draw()

        if self.game_settings.debug_display:
            hud_text_lines = [f"POS: ({self.player_sprite.center_x}, {self.player_sprite.bottom})"]
            if not self.debug_key_buf:
                self.debug_key_buf = deque(maxlen=4)
            hud_text_lines.append("Recent pressed key codes:")
            hud_text_lines += [f"  {key} ({get_key_name(key)})" for key in self.debug_key_buf]
            hud_text = "\n".join(hud_text_lines)
            arcade.draw_text(
                hud_text, self.gui_camera.viewport_width - 20, self.gui_camera.viewport_height - 20, self.text_color,
                12,
                width=300, anchor_x="right", anchor_y="top", multiline=True,
            )


    def on_key_press(self, key: int, modifiers: int):
        if key in KEYS_UP:
            if self.physics_engine.is_on_ladder():
                self.player_sprite.change_y = PLAYER_MOVEMENT_SPEED
            elif self.physics_engine.can_jump():
                self.player_sprite.change_y = PLAYER_JUMP_SPEED
                arcade.play_sound(self.jump_sound)
        elif key in KEYS_DOWN:
            if self.physics_engine.is_on_ladder():
                self.player_sprite.change_y = -PLAYER_MOVEMENT_SPEED
        elif key in KEYS_LEFT:
            self.player_sprite.change_x = -PLAYER_MOVEMENT_SPEED
        elif key in KEYS_RIGHT:
            self.player_sprite.change_x = PLAYER_MOVEMENT_SPEED

    def on_key_release(self, key: int, modifiers: int):
        if self.game_settings.debug_display:
            if not self.debug_key_buf:
                self.debug_key_buf = deque(maxlen=4)
            self.debug_key_buf.append(key)
        else:
            self.debug_key_buf = None

        if key in KEYS_UP | KEYS_DOWN:
            if self.physics_engine.is_on_ladder():
                self.player_sprite.change_y = 0
        elif key in KEYS_LEFT | KEYS_RIGHT:
            self.player_sprite.change_x = 0
        elif key in KEYS_NEXT_LEVEL:
            self.next_level()
        elif key in KEYS_DEBUG_DISPLAY:
            self.game_settings.debug_display = not self.game_settings.debug_display
        elif key in KEYS_FULL_SCREEN:
            self.set_fullscreen(not self.fullscreen)

    def center_camera_to_player(self):
        screen_x = self.player_sprite.center_x - self.camera.viewport_width // 2
        screen_x = arcade.clamp(screen_x, 0, self.end_of_map - self.camera.viewport_width)
        screen_y = max(
            self.player_sprite.center_y - self.camera.viewport_height // 2 - INSTRUCTION_BAR_SIZE,
            -INSTRUCTION_BAR_SIZE
        )
        self.camera.move_to((screen_x, screen_y))


    def player_die(self):
        self.player_sprite.change_x = 0
        self.player_sprite.change_y = 0
        self.player_sprite.center_x = PLAYER_START_X
        self.player_sprite.center_y = PLAYER_START_Y
        arcade.play_sound(self.game_over)

    def next_level(self):
        self.level = (self.level + 1) % AMOUNT_OF_LEVELS
        self.setup()

    def on_update(self, delta_time: float):
        self.physics_engine.update()
        self.player_sprite.is_on_ladder = self.physics_engine.is_on_ladder()

        self.scene.update_animation(delta_time, [LAYER_NAME_BACKGROUND, LAYER_NAME_COINS, LAYER_NAME_PLAYER])

        coin_hit_list = \
            arcade.check_for_collision_with_list(self.player_sprite, self.scene.get_sprite_list(LAYER_NAME_COINS))
        for coin in coin_hit_list:
            coin.remove_from_sprite_lists()
            self.score += int(coin.properties.get("Points", 1))
            arcade.play_sound(self.collect_coin_sound)

        if self.player_sprite.center_y < -100:
            self.player_die()
        if (
                LAYER_NAME_DONT_TOUCH in self.scene.name_mapping
                and self.player_sprite.collides_with_list(self.scene.get_sprite_list(LAYER_NAME_DONT_TOUCH))
        ):
            self.player_die()

        self.player_sprite.left = max(self.player_sprite.left, 0)
        self.player_sprite.right = min(self.player_sprite.right, self.end_of_map)

        if self.player_sprite.right >= self.end_of_map:
            self.next_level()

        self.center_camera_to_player()


def main():
    window = MyGame()
    window.setup()
    arcade.run()


if __name__ == '__main__':
    main()
