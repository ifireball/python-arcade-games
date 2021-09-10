from __future__ import annotations

from enum import IntEnum, auto
from typing import NamedTuple, Optional

import arcade

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 650
SCREEN_TITLE = "Platformer"

CHARACTER_SCALING = 1.0
TILE_SCALING = 0.5
COIN_SCALING = 0.5
TILE_PIXEL_SIZE = 128
GRID_PIXEL_SIZE = TILE_PIXEL_SIZE * TILE_SCALING

PLAYER_START_X = 64
PLAYER_START_Y = 255
PLAYER_MOVEMENT_SPEED = 5
PLAYER_JUMP_SPEED = 20
GRAVITY = 1.0

LAYER_NAME_MOVING_PLATFORMS = "Moving Platforms"
LAYER_NAME_PLATFORMS = "Platforms"
LAYER_NAME_COINS = "Coins"
LAYER_NAME_FOREGROUND = "Foreground"
LAYER_NAME_BACKGROUND = "Background"
LAYER_NAME_DONT_TOUCH = "Don't Touch"
LAYER_NAME_LADDERS = "Ladders"
LAYER_NAME_PLAYER = "Player"

LEVEL_MAPS = (
    # ":resources:tiled_maps/map2_level_1.json",
    # ":resources:tiled_maps/map2_level_2.json",
    ":resources:tiled_maps/map_with_ladders.json",
)
AMOUNT_OF_LEVELS = len(LEVEL_MAPS)

KEYS_UP = {arcade.key.UP, arcade.key.W, arcade.key.SPACE}
KEYS_DOWN = {arcade.key.DOWN, arcade.key.S}
KEYS_LEFT = {arcade.key.LEFT, arcade.key.A}
KEYS_RIGHT = {arcade.key.RIGHT, arcade.key.D}


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


class MyGame(arcade.Window):
    """
    Main application class
    """

    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

        arcade.set_background_color(arcade.csscolor.CORNFLOWER_BLUE)

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
            arcade.set_background_color(self.tile_map.tiled_map.background_color)
        self.end_of_map = self.tile_map.tiled_map.map_size.width * GRID_PIXEL_SIZE

        if LAYER_NAME_FOREGROUND in self.scene.name_mapping:
            self.scene.add_sprite_list_before(LAYER_NAME_PLAYER, LAYER_NAME_FOREGROUND)
        self.player_sprite = PlayerCharacter()
        self.player_sprite.center_x = PLAYER_START_X
        self.player_sprite.center_y = PLAYER_START_Y
        self.scene.add_sprite(LAYER_NAME_PLAYER, self.player_sprite)

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

    def on_draw(self):
        """Render the screen"""
        arcade.start_render()

        self.camera.use()
        self.scene.draw()

        self.gui_camera.use()
        score_text = f"Score: {self.score}"
        arcade.draw_text(
            score_text, 20, self.gui_camera.viewport_height - 20, arcade.csscolor.WHITE, 18,
            anchor_y="top"
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
        if key in KEYS_UP | KEYS_DOWN:
            if self.physics_engine.is_on_ladder():
                self.player_sprite.change_y = 0
        elif key in KEYS_LEFT | KEYS_RIGHT:
            self.player_sprite.change_x = 0

    def center_camera_to_player(self):
        screen_x = self.player_sprite.center_x - self.camera.viewport_width // 2
        screen_x = arcade.clamp(screen_x, 0, self.end_of_map - self.camera.viewport_width)
        screen_y = max(self.player_sprite.center_y - self.camera.viewport_height // 2, 0)
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
