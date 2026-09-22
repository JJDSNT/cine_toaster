from __future__ import annotations

from pathlib import Path

from . import require


# Image generators insist on switching ceiling lights on. Asking an editor to
# "change only the light" moves furniture, so the fix is done on the pixels: the
# fixtures are found by brightness and taken down to the level of the ceiling
# around them, halo included. Nothing else in the frame changes.
#
# Only this operation lives here. Turning a whole room into a different lighting
# state is a look, not a repair, and a look belongs to the film that wants it.

TOP_BAND = 0.35
BRIGHT_THRESHOLD = 0.78
LUMINANCE = (0.30, 0.59, 0.11)


def dim_ceiling_lights(
    source: Path,
    destination: Path,
    *,
    band: float = TOP_BAND,
    threshold: float = BRIGHT_THRESHOLD,
    keep_warm: bool = True,
) -> int:
    """Switch off the ceiling fixtures a generator turned on.

    Only cold white light is taken down; amber sources are usually practicals or
    emergency lighting that should survive. Returns how many pixels were dimmed.
    """

    numpy = require("numpy")
    pil = require("PIL")
    from PIL import Image, ImageFilter  # noqa: PLC0415 - optional dependency

    del pil
    image = numpy.asarray(Image.open(source).convert("RGB")).astype(numpy.float32) / 255
    height, _width, _ = image.shape
    luma = image @ numpy.array(LUMINANCE)

    bright = luma > threshold
    if keep_warm:
        bright = bright & (image[..., 2] > image[..., 0] * 0.85)
    mask = bright.astype(numpy.float32)
    mask[int(height * band) :] = 0

    grown = (
        Image.fromarray((mask * 255).astype(numpy.uint8))
        .filter(ImageFilter.MaxFilter(9))
        .filter(ImageFilter.GaussianBlur(10))
    )
    mask = numpy.clip(numpy.asarray(grown).astype(numpy.float32) / 255 * 1.6, 0, 1)

    top = image[: int(height * band)]
    top_mask = mask[: int(height * band)]
    surrounding = numpy.median(top[top_mask < 0.05], axis=0)
    dimmed = image * 0.18 + surrounding * 0.6
    image = image * (1 - mask[..., None]) + dimmed * mask[..., None]

    halo = numpy.asarray(grown.filter(ImageFilter.GaussianBlur(60))).astype(numpy.float32) / 255
    image = image * (1 - 0.45 * numpy.clip(halo * 3, 0, 1)[..., None])

    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((numpy.clip(image, 0, 1) * 255).astype(numpy.uint8)).save(destination)
    return int((mask > 0.5).sum())


__all__ = ["dim_ceiling_lights"]
