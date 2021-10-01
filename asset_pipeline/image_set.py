from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from math import ceil, sqrt
from typing import Mapping, Tuple

import pygame


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


def surface_digest(srf: pygame.Surface) -> str:
    buf = srf.get_buffer()
    dig = sha256()
    dig.update(buf.raw)
    return dig.hexdigest()
