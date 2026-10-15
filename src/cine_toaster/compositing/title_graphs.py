"""The title catalog's animations as fragments of a SPEC-0012 graph (C6 stage D, CT-0077).

Until C6 a title was FFmpeg's `drawtext` -- nine animations written as filter
expressions, and the neon sign as a whole FFmpeg graph of its own -- or a
Blender render laid by FFmpeg's overlay. Here each animation is `generate.text`
with curves on its reveal, place, size and colour, bars as solids through a
shape, the neon's halos as blurs added as light; a Blender title is a clip the
graph lays. The parameters keep their meaning: sizes and offsets in pixels at
720 lines, times in seconds from the start of the shot.

This is C6's convergence, not C6b's typography: what the titles did, drawn by
the one engine; richer lettering is C6b.
"""

from __future__ import annotations

import math
from typing import Any

from .effects import Fragment, _linear

FRAME_LINES = 720.0  # the title catalog's sizes are pixels at 720 lines


def _spaced(text: str) -> str:
    """Letters apart by a thin space, words by two em spaces: tracked-out capitals that do not run together."""

    return "  ".join(" ".join(word) for word in text.split(" "))


def _y(params: dict[str, Any], size: float) -> float:
    """The centre of a line by the item's position: centre, near the bottom, or near the top."""

    return {"centre": 0.5, "bottom": 1.0 - (46 + size / 2) / FRAME_LINES,
            "top": 0.16 + size / 2 / FRAME_LINES}[str(params.get("position") or "centre")]


def _alpha(params: dict[str, Any], length: float, *, fade_in: bool = True):
    """How much a title is seen at `t`: nothing before `enter_at`, rising over `fade_in`, held, falling over the
    last `fade_out` -- and when the fades do not fit in the shot, rising while it can, then falling, as the
    FFmpeg titles did."""

    enter = float(params.get("enter_at", 0.0))
    rise = max(0.001, float(params.get("fade_in", 1.0))) if fade_in else 0.001
    fall = max(0.001, float(params.get("fade_out", 1.0)))
    hold = max(enter + rise, length - fall)

    def seen(t: float) -> float:
        if t < enter:
            return 0.0
        if t < enter + rise:
            return (t - enter) / rise
        return 1.0 if t < hold else max(0.0, (length - t) / fall)

    return seen


def _coloured(f: Fragment, name: str, colour: list[float], seen, length: float) -> dict[str, str]:
    """A colour whose alpha follows `seen`, as a curve sampled at every frame."""

    return f.sampled(name, lambda t: [round(c, 6) for c in colour[:3]] + [round(seen(t), 6)], length)


def _text(f: Fragment, name: str, text: str, size: Any, colour: Any, position: Any, **more: Any) -> str:
    node = {"op": "generate.text", "text": text, "size": size, "colour": colour, "position": position, **more}
    return f.add(name, node)


def _over(f: Fragment, front: str, back: str, name: str, **more: Any) -> str:
    return f.add(name, {"op": "merge.over", "front": front, "back": back, **more})


def _fade(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    size, text = float(params["size"]), _maybe_spaced(params)
    colour, y = _linear(params.get("color"), "#E6E6E6"), _y(params, float(params["size"]))
    lines = _over(f, _text(f, "text", text, size, _coloured(f, "alpha", colour, _alpha(params, length), length),
                           [0.5, y]), src, "titled")
    if params.get("subtitle"):
        sub = _text(f, "subtitle", str(params["subtitle"]), size * 0.45,
                    _coloured(f, "sub-alpha", colour, _alpha(params, length), length),
                    [0.5, y + size * 1.1 / FRAME_LINES])
        lines = _over(f, sub, lines, "subtitled")
    return lines


def _maybe_spaced(params: dict[str, Any]) -> str:
    text = str(params.get("text") or "")
    return _spaced(text) if params.get("spaced") else text


def _stepped(params: dict[str, Any], count: int, typing: float) -> list[Any]:
    """A reveal showing the first unit at `enter_at` and the last after `typing` seconds."""

    enter = float(params.get("enter_at", 0.0))
    first = 1.0 / max(1, count)
    return [{"t": 0.0, "value": 0.0, "ease": "hold"}, [enter, first], [enter + max(typing, 1e-3), 1.0]]


def _typewriter(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    text, size = _maybe_spaced(params), float(params["size"])
    enter, fall = float(params.get("enter_at", 0.0)), float(params.get("fade_out", 1.0))
    span = max(0.2, length - enter - fall)
    typing = float(params.get("typing_seconds") or min(span * 0.6, 0.08 * len(text) + 0.4))
    reveal = f.keys("typing", _stepped(params, len(text), typing - typing / max(1, len(text))))
    colour = _coloured(f, "alpha", _linear(params.get("color"), "#E6E6E6"), _alpha(params, length, fade_in=False), length)
    return _over(f, _text(f, "text", text, size, colour, [0.5, _y(params, size)], reveal=reveal), src, "titled")


def _words(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    text, size = _maybe_spaced(params), float(params["size"])
    words = str(params.get("text") or "").split()
    enter, fall = float(params.get("enter_at", 0.0)), float(params.get("fade_out", 1.0))
    step = max(0.2, length - enter - fall) * 0.6 / max(1, len(words))
    reveal = f.keys("words", _stepped(params, len(words), step * (len(words) - 1)))
    colour = _coloured(f, "alpha", _linear(params.get("color"), "#E6E6E6"), _alpha(params, length, fade_in=False), length)
    # Spaced words are joined by two em spaces: a word is what lies between them.
    return _over(f, _text(f, "text", text, size, colour, [0.5, _y(params, size)], reveal=reveal,
                          reveal_by="word"), src, "titled")


def _slide(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    text, size = _maybe_spaced(params), float(params["size"])
    y, enter = _y(params, size), float(params.get("enter_at", 0.0))
    rise = f.keys("rise", [{"t": enter, "value": [0.5, y + 60 / FRAME_LINES]},
                           [enter + max(0.001, float(params.get("fade_in", 1.0))), [0.5, y]]])
    colour = _coloured(f, "alpha", _linear(params.get("color"), "#E6E6E6"), _alpha(params, length), length)
    return _over(f, _text(f, "text", text, size, colour, rise), src, "titled")


def _grow(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    text, size = _maybe_spaced(params), float(params["size"])
    enter, fall = float(params.get("enter_at", 0.0)), float(params.get("fade_out", 1.0))
    grow = f.keys("grow", [[enter, size * 0.6], [enter + max(0.2, length - enter - fall), size]])
    colour = _coloured(f, "alpha", _linear(params.get("color"), "#E6E6E6"), _alpha(params, length), length)
    return _over(f, _text(f, "text", text, grow, colour, [0.5, 0.5]), src, "titled")


def _roll(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # Credits: lines climbing from below the frame to above it.
    text = str(params.get("text") or "").replace("\\n", "\n")
    size, enter = float(params["size"]), float(params.get("enter_at", 0.0))
    lines = text.count("\n") + 1
    tall = lines * size * 1.6 / FRAME_LINES
    climb = f.keys("climb", [[enter, [0.5, 1.0 + tall / 2]], [max(length, enter + 0.5), [0.5, -tall / 2]]])
    return _over(f, _text(f, "text", text, size, _linear(params.get("color"), "#E6E6E6"), climb,
                          line_spacing=size * 0.6), src, "titled")


def _lower_third(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # A bar across the lower left, the name sliding in on it, its role below.
    size, enter = float(params["size"]), float(params.get("enter_at", 0.0))
    top = (FRAME_LINES - 150) / FRAME_LINES
    bar_shape = f.add("bar-shape", {"op": "matte.shape", "shape": "rectangle",
                                    "points": [[0.0, top], [0.42, top + 92 / FRAME_LINES]]})
    bar = f.add("bar", {"op": "merge.over", "back": f.solid("clear", [0.0, 0.0, 0.0, 0.0]),
                        "front": f.solid("bar-colour", _linear(params.get("bar_color"), "#101315") + [0.75]),
                        "matte": bar_shape})
    shown = _over(f, bar, src, "barred", mix=f.keys("bar-there", [{"t": 0.0, "value": 0.0, "ease": "hold"},
                                                                    [enter, 1.0]]))
    margin, rise = 40 / 1280, max(0.001, float(params.get("fade_in", 1.0)))

    def sliding(name: str, y: float) -> dict[str, str]:
        return f.keys(name, [{"t": enter, "value": [margin - 1.0, y]}, [enter + rise, [margin, y]]])

    name_y = top + (14 + size / 2) / FRAME_LINES
    named = _over(f, _text(f, "name", _maybe_spaced(params), size,
                           _coloured(f, "alpha", _linear(params.get("color"), "#E6E6E6"), _alpha(params, length), length),
                           sliding("slide", name_y), align="left"), shown, "named")
    if params.get("subtitle"):
        sub_size = size * 0.55
        sub = _text(f, "role", str(params["subtitle"]), sub_size,
                    _coloured(f, "role-alpha", _linear(params.get("subtitle_color"), "#9AA3A8"), _alpha(params, length),
                              length),
                    sliding("role-slide", top + (56 + sub_size / 2) / FRAME_LINES), align="left")
        named = _over(f, sub, named, "roled")
    return named


def _flicker(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    # The envelope, broken by a stutter: dimmed on about a quarter of the frames, the same frames every time.
    import numpy as np

    text, size = _maybe_spaced(params), float(params["size"])
    colour = _linear(params.get("color"), "#E6E6E6")
    seen = _alpha(params, length)
    stutter = np.random.default_rng(23).uniform(0, 1, int(math.ceil(length * f.fps)) + 2)

    def flickering(t: float) -> float:
        return seen(t) * (1.0 if stutter[min(int(t * f.fps), len(stutter) - 1)] > 0.25 else 0.55)

    return _over(f, _text(f, "text", text, size, _coloured(f, "stutter", colour, flickering, length),
                          [0.5, _y(params, size)]), src, "titled")


def _neon(f: Fragment, src: str, params: dict[str, Any], length: float) -> str:
    """A neon sign: tubes of light over the picture, lighting it, striking with a stutter.

    Each line (the title, and `line2` if given) is a tube -- a hollow stroke with a pale core inside when `tube`
    is on, solid letters otherwise -- over two halos and a wide spill of its colour, *added* to the picture so a
    wall behind is lit by it. All share one flicker: a tube striking, then a faint buzz.
    """

    enter, ignite = float(params.get("enter_at", 0.0)), max(0.05, float(params.get("ignite", 0.9)))
    fall, glow = max(0.001, float(params.get("fade_out", 0.6))), float(params.get("glow", 1.0))
    tube = bool(params.get("tube", False))

    def lit(t: float) -> float:
        if t < enter:
            return 0.0
        on = (1.0 if math.sin(t * 97) * math.sin(t * 61 + 1.3) > -0.2 else 0.0) if t < enter + ignite else (
            0.88 + 0.12 * (1.0 if math.sin(t * 53) * math.sin(t * 29 + 0.7) > 0.55 else 0.0))
        return round(on * min(1.0, max(0.0, (length - t) / fall)), 6)

    lines = [{"text": _maybe_spaced(params), "colour": params.get("color") or "#FF2E9A", "size": float(params["size"]),
              "y": params.get("y"), "font": params.get("font") or ""}]
    if params.get("line2"):
        lines.append({"text": str(params["line2"]), "colour": params.get("line2_color") or "#FF2E9A",
                      "size": float(params.get("line2_size") or params["size"]), "y": params.get("line2_y"),
                      "font": params.get("line2_font") or params.get("font") or ""})
    if len(lines) == 2:  # two lines stacked about the centre unless placed
        lines[0]["y"] = lines[0]["y"] if lines[0]["y"] is not None else 0.38
        lines[1]["y"] = lines[1]["y"] if lines[1]["y"] is not None else 0.66
    core = _linear(params.get("core_color"), "#FFF6FB")
    shining = f.sampled("lit", lit, length)
    current = src
    for index, line in enumerate(lines):
        size = line["size"]
        y = float(line["y"]) if line["y"] is not None else _y(params, size)
        stroke = max(2.0, size * 0.07)
        colour = _linear(line["colour"], "#FF2E9A")
        font = {"font": line["font"]} if line["font"] else {}
        shape = _text(f, f"tube{index}", line["text"], size, colour + [1.0], [0.5, y],
                      outline=stroke if tube else stroke / 2, hollow=tube, **font)
        for name, radius, gain in (("spill", 180, 1.1), ("far", 40, 1.2), ("near", 12, 1.4)):
            halo = f.add(f"{name}{index}", {"op": "filter.blur", "in": shape, "radius": radius * glow})
            bright = f.add(f"{name}{index}-lit", {"op": "colour.grade", "in": halo,
                                                   "gain": f.sampled(f"{name}{index}-gain",
                                                                     lambda t, g=gain: round(g * glow * lit(t), 6),
                                                                     length)})
            current = f.add(f"{name}{index}-added", {"op": "merge.blend", "a": current, "b": bright, "mode": "add"})
        inner = _text(f, f"core{index}", line["text"], size, core + [1.0], [0.5, y],
                      outline=max(1.0, stroke / 3) if tube else 0.0, hollow=tube, **font)
        letters = _over(f, inner, shape, f"letters{index}")
        current = _over(f, letters, current, f"sign{index}", mix=shining)
    return current


#: The title animations the graph draws, by the `effect` name items give in `[render]`.
BUILDERS = {
    "fade": _fade, "typewriter": _typewriter, "words": _words, "slide": _slide, "grow": _grow, "roll": _roll,
    "lower-third": _lower_third, "flicker": _flicker, "neon": _neon,
}


def graph_for(title: dict[str, Any], length: float, fps: float) -> dict[str, Any]:
    """A title over the port `picture`, as one graph. A Blender title's prepared clip is laid over it."""

    nodes: dict[str, Any] = {}
    f = Fragment(nodes, "T", fps)
    params = {**title["params"], **(title.get("prepared") or {})}
    if title.get("engine") == "blender":
        clip = f.add("letters", {"op": "generate.source", "file": params["_clip"], "alpha": "straight"})
        out = _over(f, clip, "picture", "titled")
    else:
        out = BUILDERS[title["effect"]](f, "picture", params, length)
    # A title's font is the production's, or the system's sans: carried by every text node.
    for node in nodes.values():
        if node["op"] == "generate.text" and params.get("font") and not node.get("font"):
            node["font"] = params["font"]
    return {"ports": {"picture": "picture"}, "nodes": nodes, "output": out}


def primitives_of(title: dict[str, Any]) -> list[str]:
    """The primitives a title is made of, as its item declares them."""

    prepared = {"_clip": "letters.mov"} if title.get("engine") == "blender" else {}
    graph = graph_for({**title, "prepared": prepared}, 3.0, 24)
    return sorted({node["op"] for node in graph["nodes"].values()})
