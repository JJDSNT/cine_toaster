from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


LUT_SIZE = 33
LUMINANCE = (0.2126, 0.7152, 0.0722)


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    text = value.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Not a six-digit hex colour: {value!r}")
    return tuple(int(text[index : index + 2], 16) / 255 for index in (0, 2, 4))  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Palette:
    """A look, expressed as a ramp from shadow to highlight.

    The ramp is the production's; this module only knows how to turn one into a
    lookup table. Which looks a film has, and what they mean, stays in the film.
    """

    ramp: tuple[str, ...]
    strength: float = 0.5
    saturation: float = 1.0
    blacks: float = 0.0

    def colours(self) -> list[tuple[float, float, float]]:
        if len(self.ramp) < 2:
            raise ValueError("A palette ramp needs at least two colours")
        pairs = [(sum(c * w for c, w in zip(hex_to_rgb(item), LUMINANCE)), hex_to_rgb(item)) for item in self.ramp]
        pairs.sort(key=lambda pair: pair[0])
        return [colour for _luma, colour in pairs]

    def luminances(self) -> list[float]:
        values = [sum(c * w for c, w in zip(hex_to_rgb(item), LUMINANCE)) for item in self.ramp]
        return sorted(values)


def _sample_ramp(palette: Palette, luma: float) -> tuple[float, float, float]:
    """The palette colour that a given brightness maps to.

    The ramp is stretched to cover black to white, so the darkest colour anchors
    at 0 and the lightest at 1 rather than leaving the extremes ungraded.
    """

    colours = palette.colours()
    stops = palette.luminances()
    low, high = stops[0], stops[-1]
    span = (high - low) or 1.0
    position = (luma - low) / span
    position = min(1.0, max(0.0, position))

    scaled = position * (len(colours) - 1)
    index = min(len(colours) - 2, int(scaled))
    blend = scaled - index
    first, second = colours[index], colours[index + 1]
    return tuple(a + (b - a) * blend for a, b in zip(first, second))  # type: ignore[return-value]


def build_lut(palette: Palette, size: int = LUT_SIZE) -> str:
    """Generate a .cube lookup table that pulls an image toward a palette.

    A pixel's own brightness picks a colour on the ramp, and that colour is
    mixed with the original by `strength`. The clip keeps what the model got
    right; only the colour is steered.
    """

    if size < 2:
        raise ValueError("A lookup table needs at least two steps per axis")

    lines = [f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
    step = 1.0 / (size - 1)
    for blue_index in range(size):
        for green_index in range(size):
            for red_index in range(size):
                red, green, blue = red_index * step, green_index * step, blue_index * step
                luma = red * LUMINANCE[0] + green * LUMINANCE[1] + blue * LUMINANCE[2]

                # Desaturate toward the pixel's own brightness first, so the
                # palette is not fighting colour the model invented.
                desaturated = [
                    luma + (channel - luma) * palette.saturation for channel in (red, green, blue)
                ]
                target = _sample_ramp(palette, luma)
                mixed = [
                    value + (colour - value) * palette.strength
                    for value, colour in zip(desaturated, target)
                ]
                if palette.blacks:
                    # Positive closes the blacks, negative lifts them.
                    mixed = [max(0.0, value - palette.blacks * (1 - value)) for value in mixed]
                lines.append(" ".join(f"{min(1.0, max(0.0, value)):.6f}" for value in mixed))
    return "\n".join(lines) + "\n"


def write_lut(palette: Palette, destination: Path, size: int = LUT_SIZE) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_lut(palette, size), encoding="utf-8")
    return destination


def ffmpeg_filter(lut_path: Path) -> str:
    """The filter string that applies this table in an ffmpeg graph."""

    return f"lut3d=file={lut_path}"


__all__ = ["LUT_SIZE", "Palette", "build_lut", "ffmpeg_filter", "hex_to_rgb", "write_lut"]
