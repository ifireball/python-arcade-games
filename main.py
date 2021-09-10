from typing import Optional

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

LAYER_NAME_PLATFORMS = "Platforms"
LAYER_NAME_COINS = "Coins"
LAYER_NAME_FOREGROUND = "Foreground"
LAYER_NAME_BACKGROUND = "Background"
LAYER_NAME_DONT_TOUCH = "Don't Touch"

AMOUNT_OF_LEVELS = 2


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
        self.player_sprite: Optional[arcade.Sprite] = None
        self.physics_engine: Optional[arcade.PhysicsEnginePlatformer] = None

        self.camera: Optional[arcade.Camera] = None
        self.gui_camera: Optional[arcade.Camera] = None

        self.collect_coin_sound = arcade.load_sound(":resources:sounds/coin1.wav")
        self.jump_sound = arcade.load_sound(":resources:sounds/jump1.wav")
        self.game_over = arcade.load_sound(":resources:sounds/gameover1.wav")

        self.score: int = 0
        self.level: int = 1

    def setup(self):
        """Setup the game"""
        self.camera = arcade.Camera(self.width, self.height)
        self.gui_camera = arcade.Camera(self.width, self.height)

        map_name = f":resources:tiled_maps/map2_level_{self.level}.json"
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

        self.scene.add_sprite_list_before("Player", LAYER_NAME_FOREGROUND)
        image_source = ":resources:images/animated_characters/female_adventurer/femaleAdventurer_idle.png"
        self.player_sprite = arcade.Sprite(image_source, CHARACTER_SCALING)
        self.player_sprite.center_x = PLAYER_START_X
        self.player_sprite.center_y = PLAYER_START_Y
        self.scene.add_sprite("Player", self.player_sprite)

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite, self.scene.get_sprite_list(LAYER_NAME_PLATFORMS), GRAVITY
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
        if key == arcade.key.UP or key == arcade.key.W or key == arcade.key.SPACE:
            if self.physics_engine.can_jump():
                self.player_sprite.change_y = PLAYER_JUMP_SPEED
                arcade.play_sound(self.jump_sound)
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.player_sprite.change_x = -PLAYER_MOVEMENT_SPEED
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.player_sprite.change_x = PLAYER_MOVEMENT_SPEED

    def on_key_release(self, key: int, modifiers: int):
        if key == arcade.key.UP or key == arcade.key.W:
            self.player_sprite.change_y = 0
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.player_sprite.change_y = 0
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.player_sprite.change_x = 0
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.player_sprite.change_x = 0

    def center_camera_to_player(self):
        screen_x = self.player_sprite.center_x - self.camera.viewport_width // 2
        screen_x = min(max(screen_x, 0), self.end_of_map - self.camera.viewport_width)
        screen_y = max(self.player_sprite.center_y - self.camera.viewport_width // 2, 0)
        self.camera.move_to((screen_x, screen_y))


    def player_die(self):
        self.player_sprite.change_x = 0
        self.player_sprite.change_y = 0
        self.player_sprite.center_x = PLAYER_START_X
        self.player_sprite.center_y = PLAYER_START_Y
        arcade.play_sound(self.game_over)

    def next_level(self):
        self.level = self.level % AMOUNT_OF_LEVELS + 1
        self.setup()

    def on_update(self, delta_time: float):
        self.physics_engine.update()

        coin_hit_list = \
            arcade.check_for_collision_with_list(self.player_sprite, self.scene.get_sprite_list(LAYER_NAME_COINS))
        for coin in coin_hit_list:
            coin.remove_from_sprite_lists()
            self.score += 1
            arcade.play_sound(self.collect_coin_sound)

        if self.player_sprite.center_y < -100:
            self.player_die()
        if arcade.check_for_collision_with_list(self.player_sprite, self.scene.get_sprite_list(LAYER_NAME_DONT_TOUCH)):
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
