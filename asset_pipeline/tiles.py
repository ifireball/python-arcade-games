from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Collection, Mapping, Tuple
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

import pygame
from rich import print

from .animation import AnimationFrames, OptimizedAnimationInfo, TileAnimationFrame
from .configuration import AnimationConfiguration, TilesetConfiguration
from .image_set import ImageSet

TILE_ANIMATION_NAME_PROPERTY = "animation_name"


@dataclass(frozen=True)
class TileSet:
    name: str
    tile_width: int
    tile_height: int
    tile_count: int
    image: pygame.Surface
    tiles_with_extra_info: Collection[Tile]

    @classmethod
    def from_configuration(cls, name: str, cfg: TilesetConfiguration, input_path: Path) -> TileSet:
        images = ImageSet()
        animations, images = cls.load_and_optimize_animations(name, cfg.animations, images, input_path)
        tiles, images = cls.generate_animation_tiles(animations, images)
        return TileSet(
            name=name,
            tile_width=images.images[0].get_width(),
            tile_height=images.images[0].get_height(),
            tile_count=len(images.images),
            image=images.as_tiled_image(),
            tiles_with_extra_info=tiles,
        )

    @classmethod
    def load_and_optimize_animations(
        cls, tsname: str, animation_cfg: Mapping[str, AnimationConfiguration], images: ImageSet, input_path: Path
    ) -> Tuple[Tuple[OptimizedAnimationInfo, ...], ImageSet]:
        optimized_animations = []
        for name, animation_cfg in animation_cfg.items():
            anim, images = cls.load_and_optimize_animation(f"{tsname}.{name}", animation_cfg, images, input_path)
            optimized_animations.append(anim)
        return tuple(optimized_animations), images

    @classmethod
    def generate_animation_tiles(
        cls, animations: Collection[OptimizedAnimationInfo], images: ImageSet
    ) -> Tuple[Tuple[AnimatedTile, ...], ImageSet]:
        used_tile_ids = set()
        tiles = []
        for anim in animations:
            try:
                tile_id = next(frame.tile_id for frame in anim.frames if frame.tile_id not in used_tile_ids)
            except StopIteration:
                images, tile_id = images.with_image_added(images.images[anim.frames[0].tile_id])
            used_tile_ids.add(tile_id)
            tile = AnimatedTile(
                id=tile_id,
                properties={
                     TILE_ANIMATION_NAME_PROPERTY: PropertyStringValue(anim.name)
                },
                frames=anim.frames,
                type=anim.game_class or ""
            )
            tiles.append(tile)
        return tuple(tiles), images

    @classmethod
    def load_and_optimize_animation(
        cls, name: str, animation_cfg: AnimationConfiguration, images: ImageSet, input_path: Path
    ) -> Tuple[OptimizedAnimationInfo, ImageSet]:
        animation_frames = AnimationFrames.from_configuration(name, animation_cfg, input_path)
        optimized_animation = OptimizedAnimationInfo(name, game_class=animation_cfg.game_class)
        frame_duration: int = animation_frames.frame_duration
        for frame_image in animation_frames:
            images, tile_id = images.with_image(frame_image)
            optimized_animation = optimized_animation.with_appended_frame(tile_id, frame_duration)
        return optimized_animation, images

    def to_xml(self) -> Element:
        elm = Element(
            "tileset",
            name=self.name,
            tilewidth=str(self.tile_width),
            tileheight=str(self.tile_height),
            tilecount=str(self.tile_count),
        )
        SubElement(
            elm,
            "image",
            source=f"{self.name}.png",
            width=str(self.image.get_width()),
            height=str(self.image.get_height())
        )
        elm.extend(tile.to_xml() for tile in self.tiles_with_extra_info)
        return elm

    def save_to(self, save_path: Path) -> None:
        pygame.image.save(self.image, save_path / f"{self.name}.png")
        xml_doc = ElementTree(self.to_xml())
        indent(xml_doc)
        xml_doc.write(save_path / f"{self.name}.tsx")


@dataclass(frozen=True)
class Tile(metaclass=ABCMeta):
    id: int
    properties: Mapping[str, PropertyValue]
    type: str

    @abstractmethod
    def to_xml(self) -> Element:
        elm = Element('tile', id=str(self.id))
        if self.type:
            elm.attrib['type'] = self.type
        if self.properties:
            properties = SubElement(elm, 'properties')
            properties.extend(
                Element('property', name=name, type=value.get_type_name(), value=value.get_xml_value())
                for name, value in self.properties.items()
            )
        return elm


@dataclass(frozen=True)
class PropertyValue(metaclass=ABCMeta):
    @classmethod
    def get_type_name(cls) -> str:
        prefix = "Property"
        suffix = "Value"
        klass = cls.__name__
        if klass.startswith(prefix) and klass.endswith(suffix):
            return klass[len(prefix):-len(suffix)].lower()
        else:
            raise ValueError(f"Property value class names must begin with {prefix} and end with {suffix}")

    @abstractmethod
    def get_xml_value(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class PropertyStringValue(PropertyValue):
    value: str

    def get_xml_value(self) -> str:
        return self.value


@dataclass(frozen=True)
class AnimatedTile(Tile):
    frames: Tuple[TileAnimationFrame, ...]

    def to_xml(self) -> Element:
        elm = super().to_xml()
        animation_element = SubElement(elm, "animation")
        animation_element.extend(frame.to_xml() for frame in self.frames)
        return elm
