"""The VFX catalog's effects as fragments of a SPEC-0012 graph (C6, CT-0077).

Until C6 each effect was an FFmpeg filter chain of its own (`vfx._chain`), a
second way of blurring, keying, mixing and moving pictures beside the graph.
Here each is a few primitives, built from the item's parameters, and a shot's
effects are chained in one graph that the compositing renderers draw -- GL when
it holds every op, the reference otherwise.

Parameters keep the meaning they had (`strength` 0 to 1, `start` and `length`
in seconds, positions as fractions of the frame); the looks were matched by eye
to the FFmpeg ones, in linear light, so they are close rather than identical.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from ..errors import ValidationError

#: What a fragment builder gets: the graph being built, the picture it treats, the effect's parameters and the
#: shot's length; it returns the node whose picture is the treated one.
Builder = Callable[["Fragment", str, dict[str, Any], float], str]


def _number(params: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except (TypeError, ValueError) as error:
        raise ValidationError(f"The effect parameter {key} must be a number") from error


def _linear(hex_colour: str, fallback: str = "#FF8A3C") -> list[float]:
    text = str(hex_colour or fallback).lstrip("#")
    text = text if len(text) == 6 else fallback.lstrip("#")
    encoded = [int(text[index:index + 2], 16) / 255.0 for index in (0, 2, 4)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in encoded]


class Fragment:
    """Nodes added under one prefix, so several effects chain in one graph without clashing."""

    def __init__(self, nodes: dict[str, Any], prefix: str, fps: float) -> None:
        self.nodes, self.prefix, self.fps = nodes, prefix, fps

    def add(self, name: str, node: dict[str, Any]) -> str:
        key = f"{self.prefix}-{name}"
        self.nodes[key] = node
        return key

    def keys(self, name: str, keys: list[Any]) -> dict[str, str]:
        """Keys as a parameter's curve: `{curve: node}`."""

        return {"curve": self.curve(name, keys)}

    def curve(self, name: str, keys: list[Any]) -> str:
        """Keys as a node, for a port that takes a curve (merge.mix's `by`)."""

        return self.add(name, {"op": "curve.keys", "keys": keys})

    def sampled(self, name: str, function: Callable[[float], Any], length: float) -> dict[str, str]:
        """A curve through a function sampled at every frame: a wobble, a flicker."""

        frames = max(2, int(math.ceil(length * self.fps)) + 1)
        return self.keys(name, [[round(index / self.fps, 6), function(index / self.fps)] for index in range(frames)])

    def solid(self, name: str, colour: list[float]) -> str:
        return self.add(name, {"op": "generate.solid", "colour": colour})


def _mirror(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    return f.add("mirrored", {"op": "warp.transform", "in": src, "scale": [-1.0, 1.0]})


def _crop(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # A detail of the frame (x, y, width, height as fractions), enlarged to fill it.
    x, y = _number(params, "x", 0.0), _number(params, "y", 0.0)
    w, h = max(_number(params, "width", 0.5), 1e-3), max(_number(params, "height", 0.5), 1e-3)
    centre = [x + w / 2, y + h / 2]
    return f.add("cropped", {"op": "warp.transform", "in": src, "scale": [1 / w, 1 / h], "pivot": centre,
                             "translate": [0.5 - centre[0], 0.5 - centre[1]]})


def _fade_out(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    fade = min(_number(params, "length", 1.0), length)
    return f.add("faded", {"op": "merge.mix", "a": src, "b": f.solid("black", [0.0, 0.0, 0.0, 1.0]),
                           "by": f.curve("fade", [[max(0.0, length - fade), 0.0], [length, 1.0]])})


def _grain(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # As video shows grain: in the display encoding, as FFmpeg's noise was (±40 levels at full strength).
    return f.add("grain", {"op": "filter.noise", "in": src, "amount": 0.9 * _number(params, "strength", 0.5),
                           "size": 1.0, "seed": 7, "space": "display"})


def _vignette_of(f: Fragment, src: str, strength: float, name: str = "vignette") -> str:
    edge = max(0.0, 1.0 - 0.85 * strength)
    shade = f.add(f"{name}-shade", {"op": "generate.gradient", "kind": "radial",
                                    "colours": [[1.0, 1.0, 1.0, 1.0], [edge, edge, edge, 1.0]]})
    return f.add(name, {"op": "merge.blend", "a": src, "b": shade, "mode": "multiply"})


def _vignette(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    return _vignette_of(f, src, _number(params, "strength", 0.5))


def _light_leak(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # A warm glow drifting across the frame, added as light.
    colour = _linear(params.get("color"))
    strength = _number(params, "strength", 0.5)
    # A round glow that has faded out well inside the frame, so moving it never shows an edge.
    distance = f.add("distance", {"op": "generate.gradient", "kind": "circle"})
    falloff = f.add("falloff", {"op": "matte.from_signal", "low": 0.0, "high": 0.55, "invert": True, "gamma": 1.6,
                                "signal": f.add("reach", {"op": "signal.luminance", "picture": distance})})
    glow = f.add("glow", {"op": "merge.over", "front": f.solid("colour", colour + [1.0]),
                          "back": f.solid("clear", [0.0, 0.0, 0.0, 0.0]), "matte": falloff})
    drift = f.keys("drift", [[0.0, [-0.3, 0.0]], [max(length, 0.1), [0.3, 0.0]]])
    moving = f.add("drifting", {"op": "warp.transform", "in": glow, "translate": drift})
    return f.add("leak", {"op": "merge.blend", "a": src, "b": moving, "mode": "screen", "mix": min(1.0, strength)})


def _split_channels(f: Fragment, src: str, shift: float, name: str) -> str:
    """Red one way, blue the other, green in place: the colour fringe of a cheap lens or a bad signal."""

    red = f.add(f"{name}-r", {"op": "warp.transform", "in": src, "translate": [-shift, 0.0]})
    blue = f.add(f"{name}-b", {"op": "warp.transform", "in": src, "translate": [shift, 0.0]})
    channels = {channel: f.add(f"{name}-{channel}", {"op": "signal.channel", "picture": picture, "channel": channel})
                for channel, picture in (("red", red), ("green", src), ("blue", blue), ("alpha", src))}
    return f.add(name, {"op": "merge.channels", **channels})


def _aberration(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    return _split_channels(f, src, _number(params, "strength", 0.5) * 8 / 1280, "aberration")


def _glitch(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # Bursts of a split, noisy copy, several times a second.
    strength, rate = _number(params, "strength", 0.5), min(max(_number(params, "rate", 0.15), 0.0), 1.0)
    split = _split_channels(f, src, strength * 24 / 1280, "split")
    noisy = f.add("noisy", {"op": "filter.noise", "in": split, "amount": 0.68 * strength, "seed": 11,
                            "space": "display"})
    keys: list[Any] = []
    for tick in range(int(length * 12) + 2):
        keys += [{"t": tick / 12, "value": 0.0, "ease": "hold"}, {"t": (tick + 1 - rate) / 12, "value": 1.0, "ease": "hold"}]
    return f.add("glitch", {"op": "merge.mix", "a": src, "b": noisy, "by": f.curve("bursts", keys)})


def _shake(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    amount = _number(params, "strength", 0.5) * 20 / 1280
    wobble = f.sampled("wobble", lambda t: [round(amount * math.sin(t * 37) * math.sin(t * 13), 6),
                                            round(amount * math.sin(t * 29) * math.cos(t * 17), 6)], length)
    return f.add("shaken", {"op": "warp.transform", "in": src, "translate": wobble,
                            "scale": [1 + 2 * amount, 1 + 2 * amount]})


def _flash(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    at, width = _number(params, "start", 0.0), max(_number(params, "length", 0.4), 1e-3)
    peak = min(1.0, _number(params, "strength", 0.5))
    return f.add("flash", {"op": "merge.mix", "a": src, "b": f.solid("white", [1.0, 1.0, 1.0, 1.0]),
                           "by": f.curve("burst", [[at - width, 0.0], [at, peak], [at + width, 0.0]])})


def _defocus(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # Out of focus, coming into focus over `length`: radius in pixels at 720 lines.
    radius = 2 * (4 + 16 * _number(params, "strength", 0.5))
    pull = f.keys("pull", [{"t": 0.0, "value": radius, "ease": "out"}, [max(_number(params, "length", 1.2), 1e-3), 0.0]])
    return f.add("defocused", {"op": "filter.blur", "in": src, "radius": pull})


def _flicker(f: Fragment, name: str, rate: float, depth: float, length: float) -> dict[str, str]:
    return f.sampled(name, lambda t: round(1.0 + depth * math.sin(t * rate), 6), length)


def _old_film(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    strength = _number(params, "strength", 0.5)
    sepia = f.add("sepia", {"op": "colour.grade", "in": src, "saturation": 0.0, "gain": [1.45, 1.05, 0.5]})
    grain = f.add("grain", {"op": "filter.noise", "in": sepia, "amount": 0.68 * strength, "seed": 3,
                            "space": "display"})
    vignette = _vignette_of(f, grain, 0.75, "vignette")
    return f.add("flicker", {"op": "colour.grade", "in": vignette, "gain": _flicker(f, "beat", 23, 0.06, length)})


def _hologram(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # Cyan light, scanlines, a colour fringe and an unsteady brightness: a projection, not a person.
    strength = _number(params, "strength", 0.5)
    tint = f.add("tint", {"op": "colour.grade", "in": src, "saturation": 0.25, "gain": [0.35, 0.95, 1.35]})
    dark = max(0.0, 1.0 - (0.35 + 0.4 * strength))
    lines = f.add("lines", {"op": "generate.gradient", "kind": "linear", "angle": 90.0, "repeat": 240.0,
                            "colours": [[1.0, 1.0, 1.0, 1.0], [dark, dark, dark, 1.0]]})
    scanned = f.add("scanned", {"op": "merge.blend", "a": tint, "b": lines, "mode": "multiply"})
    fringed = _split_channels(f, scanned, strength * 4 / 1280, "fringe")
    soft = f.add("soft", {"op": "filter.blur", "in": fringed, "radius": 1.2})
    return f.add("unsteady", {"op": "colour.grade", "in": soft, "gain": _flicker(f, "beat", 31, 0.08, length)})


def _fog(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # Soft banks of mist drifting across, added as light.
    drift = _number(params, "drift", 0.5)
    mist = f.add("mist", {"op": "generate.noise", "kind": "perlin", "scale": 9.0, "seed": 5})
    thin = f.add("thin", {"op": "colour.grade", "in": mist, "gain": 0.55})
    moving = f.add("moving", {"op": "warp.transform", "in": thin, "scale": [1.4, 1.4],
                              "translate": f.keys("drift", [[0.0, [-0.08 * drift, 0.0]],
                                                            [max(length, 0.1), [0.08 * drift, 0.02 * drift]]])})
    soft = f.add("soft", {"op": "filter.blur", "in": moving, "radius": 40.0})
    return f.add("fogged", {"op": "merge.blend", "a": src, "b": soft, "mode": "screen",
                            "mix": min(1.0, 0.8 * _number(params, "strength", 0.5))})


#: The effect kinds the graph draws, by the `effect` name items give in `[render]`.
BUILDERS: dict[str, Builder] = {
    "mirror": _mirror, "crop": _crop, "fade-out": _fade_out, "grain": _grain, "vignette": _vignette,
    "light-leak": _light_leak, "aberration": _aberration, "glitch": _glitch, "shake": _shake, "flash": _flash,
    "defocus": _defocus, "old-film": _old_film, "hologram": _hologram, "fog": _fog,
}


def graph_for(effects: list[dict[str, Any]], length: float, fps: float) -> dict[str, Any]:
    """A shot's effects, in order, as one graph from the port `picture` to its output."""

    nodes: dict[str, Any] = {}
    current = "picture"
    for index, effect in enumerate(effects, 1):
        builder = BUILDERS.get(effect["effect"])
        if builder is None:
            raise ValidationError(f"The effect {effect['effect']!r} is not drawn by the graph",
                                  effects=sorted(BUILDERS))
        current = builder(Fragment(nodes, f"E{index}", fps), current, effect.get("params") or {}, length)
    if current == "picture":
        nodes["out"] = {"op": "merge.over", "front": "picture", "back": "picture"}
        current = "out"
    return {"ports": {"picture": "picture"}, "nodes": nodes, "output": current}


def primitives_of(effect_kind: str, params: dict[str, Any] | None = None) -> list[str]:
    """The primitives an effect is made of, as its item declares them (C6's "every item says")."""

    graph = graph_for([{"effect": effect_kind, "params": params or {}}], 2.0, 24)
    return sorted({node["op"] for node in graph["nodes"].values()})
