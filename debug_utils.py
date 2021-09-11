from functools import lru_cache
from typing import Mapping

import arcade


@lru_cache
def _arcade_reverse_key_map() -> Mapping:
    reverse_key_map = {
        getattr(arcade.key, symbol): symbol
        for symbol in dir(arcade.key)
        if isinstance(getattr(arcade.key, symbol), int)
    }
    return reverse_key_map


def get_key_name(key_code: int) -> str:
    return _arcade_reverse_key_map().get(key_code, '[unknown]')
