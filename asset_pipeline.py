from __future__ import annotations

from abc import ABCMeta, abstractmethod
from hashlib import sha256
from itertools import chain
from math import ceil, sqrt
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

import pygame
import toml

"""asset_pipeline.py - Processing raw media files into game assets"""

from dataclasses import dataclass, field
from typing import Collection, Mapping, Tuple

INPUT_DIR = "resource_making/raw"
OUTPUT_DIR = "resources"
CONFIG_FILE = "asset_pipeline.toml"

TILE_ANIMATION_NAME_PROPERTY = "animation_name"


@dataclass(frozen=True)
class Configuration:
    tilesets: Mapping[str, TilesetConfiguration]

    @classmethod
    def from_toml(cls, file_path: Path) -> Configuration:
        return cls.from_mapping(toml.load(file_path))

    @classmethod
    def from_mapping(cls, data: Mapping) -> Configuration:
        return Configuration(
            tilesets={
                key: TilesetConfiguration.from_mapping(value)
                for key, value in data.items()
                if isinstance(value, Mapping) and value.get('type', 'tileset') == 'tileset'
            }
        )


@dataclass(frozen=True)
class TilesetConfiguration:
    animations: Mapping[str, AnimationConfiguration]

    @classmethod
    def from_mapping(cls, data: Mapping) -> TilesetConfiguration:
        animations = data.get('animations', {})
        if not isinstance(animations, Mapping):
            raise ValueError("`animations` key in a tileset entry does not contain a mapping")
        return TilesetConfiguration(
            animations={
                key: AnimationConfiguration.from_mapping(value)
                for key, value in animations.items()
                if isinstance(value, Mapping)
            }
        )


@dataclass(frozen=True)
class AnimationConfiguration:
    source_file_patterns: Collection[str]
    duration: int

    @classmethod
    def from_mapping(cls, data: Mapping):
        source_file_patterns = data['from']
        if (
                isinstance(source_file_patterns, str)
                or not isinstance(source_file_patterns, Collection)
                or any(not isinstance(pattern, str) for pattern in source_file_patterns)
        ):
            raise ValueError(f"Animation `from` key given as {type(source_file_patterns)}, should be a list of strings")
        duration = data['duration']
        if not isinstance(duration, int):
            raise ValueError("Animation duration must be specified as an integer value")
        return AnimationConfiguration(source_file_patterns, duration)


@dataclass(frozen=True)
class AssetCollection:
    tilesets: Collection[TileSet]

    @classmethod
    def from_configuration(cls, cfg: Configuration, input_path: Path) -> AssetCollection:
        return AssetCollection(
            tilesets=[
                TileSet.from_configuration(name, tileset_cfg, input_path)
                for name, tileset_cfg in cfg.tilesets.items()
            ]
        )


@dataclass(frozen=True)
class OptimizedAnimationInfo:
    name: str
    frames: Tuple[TileAnimationFrame] = field(default_factory=tuple)

    def with_appended_frame(self, tile_id: int, duration: int) -> OptimizedAnimationInfo:
        """Returns a new OptimizedAnimationInfo object with the given frame added. If the tile of the new frame is
        identical to the one that precedes it, the existing frame duration will be extended instead of adding a new
        frame"""
        if self.frames and (last_frame := self.frames[-1]).tile_id == tile_id:
            new_frames = \
                self.frames[:-1] + (TileAnimationFrame(tile_id=tile_id, duration=last_frame.duration + duration),)
        else:
            new_frames = self.frames + (TileAnimationFrame(tile_id=tile_id, duration=duration),)
        return OptimizedAnimationInfo(name=self.name, frames=new_frames)


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
        image_set = ImageSet()
        animations, image_set = cls.load_and_optimize_animations(cfg.animations, image_set, input_path)
        tiles, image_set = cls.generate_animation_tiles(animations, image_set)
        return TileSet(
            name=name,
            tile_width=image_set.images[0].get_width(),
            tile_height=image_set.images[0].get_height(),
            tile_count=len(image_set.images),
            image=image_set.as_tiled_image(),
            tiles_with_extra_info=tiles,
        )

    @classmethod
    def load_and_optimize_animations(
        cls, animation_cfg: Mapping[str, AnimationConfiguration], image_set: ImageSet, input_path: Path
    ) -> Tuple[Tuple[OptimizedAnimationInfo, ...], ImageSet]:
        optimized_animations = []
        for name, animation_cfg in animation_cfg.items():
            animation, image_set = cls.load_and_optimize_animation(name, animation_cfg, image_set, input_path)
            optimized_animations.append(animation)
        return tuple(optimized_animations), image_set

    @classmethod
    def generate_animation_tiles(
        cls, animations: Collection[OptimizedAnimationInfo], image_set: ImageSet
    ) -> Tuple[Tuple[AnimatedTile, ...], ImageSet]:
        used_tile_ids = set()
        tiles = []
        for animation in animations:
            try:
                tile_id = next(frame.tile_id for frame in animation.frames if frame.tile_id not in used_tile_ids)
            except StopIteration:
                image_set, tile_id = image_set.with_image_added(image_set.images[animation.frames[0].tile_id])
            tile = AnimatedTile(
                id=tile_id,
                properties={
                     TILE_ANIMATION_NAME_PROPERTY: PropertyStringValue(animation.name)
                },
                frames=animation.frames,
            )
            tiles.append(tile)
        return tuple(tiles), image_set

    @classmethod
    def load_and_optimize_animation(
        cls, name: str, animation_cfg: AnimationConfiguration, image_set: ImageSet, input_path: Path
    ) -> Tuple[OptimizedAnimationInfo, ImageSet]:
        animation = OptimizedAnimationInfo(name)
        frame_files = \
            list(chain.from_iterable(
                sorted(input_path.glob(pattern)) for pattern in animation_cfg.source_file_patterns
            ))
        print(f"Making animation: {name} from files: {[f.name for f in frame_files]}")
        frame_duration: int = animation_cfg.duration // len(frame_files)
        for frame_file in frame_files:
            image = pygame.image.load(frame_file)
            image_set, tile_id = image_set.with_image(image)
            animation = animation.with_appended_frame(tile_id, frame_duration)
        return animation, image_set

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
class ImageSet:
    images: Tuple[pygame.Surface, ...] = field(default_factory=tuple)
    image_digests: Mapping[str, int] = field(default_factory=dict)

    def with_image(self, image: pygame.Surface) -> Tuple[ImageSet, int]:
        """Returns an image set that includes the given image. And the id of the image within the set.

        The image is scaled to match the size of all other images in the set, without maintaining aspect ratio. If its
        already found in the set, the same set may be returned.
        """
        image = self.fit_image_to_set(image)
        image_digest = surface_digest(image)
        try:
            return self, self.image_digests[image_digest]
        except KeyError:
            return self._new_set_with_image(image, image_digest)

    def with_image_added(self, image: pygame.Surface) -> Tuple[ImageSet, int]:
        """Returns an image set that includes the given image. And the id of the image within the set.

        The image is scaled to match the size of all other images in the set, without maintaining aspect ratio.
        This function always generates a new set with the image appended , even if the image was already included in
        the set
        """
        image = self.fit_image_to_set(image)
        image_digest = surface_digest(image)
        return self._new_set_with_image(image, image_digest)

    def _new_set_with_image(self, image: pygame.Surface, image_digest: str) -> Tuple[ImageSet, int]:
        return ImageSet(
            images=self.images + (image,),
            image_digests={image_digest: len(self.images)} | self.image_digests
        ), len(self.images)

    def fit_image_to_set(self, image: pygame.Surface) -> pygame.Surface:
        if self.images:
            first_image: pygame.Surface = self.images[0]
            if image.get_size() != first_image.get_size():
                image = pygame.transform.scale(image, first_image.get_size())
        return image

    def as_tiled_image(self) -> pygame.Surface:
        """Returns an image with all the set's images tiled in it"""
        n_tiles = len(self.images)
        tile_width, tile_height = self.images[0].get_size()
        width = int(ceil(sqrt(n_tiles)))
        height = int(ceil(n_tiles / width))
        surface = pygame.Surface(size=(width * tile_width, height * tile_height), depth=32, flags=pygame.SRCALPHA)
        for img_idx, img in enumerate(self.images):
            x, y = img_idx % width, img_idx // width
            surface.blit(img, (x * tile_width, y * tile_height))
        return surface


@dataclass(frozen=True)
class Tile(metaclass=ABCMeta):
    id: int
    properties: Mapping[str, PropertyValue]

    @abstractmethod
    def to_xml(self) -> Element:
        elm = Element('tile', id=str(self.id))
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
        animation = SubElement(elm, "animation")
        animation.extend(frame.to_xml() for frame in self.frames)
        return elm


@dataclass(frozen=True)
class TileAnimationFrame:
    tile_id: int
    duration: int

    def to_xml(self) -> Element:
        return Element('frame', tileid=str(self.tile_id), duration=str(self.duration))


def surface_digest(srf: pygame.Surface) -> str:
    buf = srf.get_buffer()
    dig = sha256()
    dig.update(buf.raw)
    return dig.hexdigest()


def main() -> None:
    script_path = Path(__file__).parent
    configuration_path = script_path / CONFIG_FILE
    configuration = Configuration.from_toml(configuration_path)
    print(configuration)

    assets = AssetCollection.from_configuration(configuration, script_path / INPUT_DIR)
    print(assets)

    for tileset in assets.tilesets:
        tileset.save_to(script_path / OUTPUT_DIR)


if __name__ == "__main__":
    main()
