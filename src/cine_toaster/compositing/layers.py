"""A shot's layers, as a filmmaker writes them, compiled into a SPEC-0012 graph (C4, CT-0075).

A layer is a picture placed over the ones below it: a source (a take of the
shot or a file), where it sits (move, size, turn in three axes with
perspective), what of it is seen (a keyer, a garbage shape, a matte in the
frame), how it meets what is below (a mode and an opacity), and a border and
a drop shadow. Any number can change over time, by keys or by the music's
beats (C3).

The layers are a way of writing a composite, not a second way of drawing
one: they become nodes of the one graph, checked, cached and drawn by the
same renderers as any composite (ADR 0022, CT-0072).

    layers:                          # the first is at the back
      - source: CUT
      - source: plates/launch.mp4
        start: 1.0
        place:
          translate: {keys: [{t: 0, value: [0.6, -0.4], ease: out}, [1.2, [0.28, -0.25]]]}
          scale: 0.4
          rotate: [0, 20, 0]
          perspective: 35
        key: {by: colour, colour: "#1fb34a", tolerance: 0.08, softness: 0.05}
        garbage: {shape: rectangle, points: [[0.1, 0], [0.9, 1]]}
        matte: {shape: polygon, points: [[0.31, 0.2], [0.62, 0.2], [0.62, 0.71], [0.31, 0.71]]}
        border: {width: 4, colour: "#ffffff"}
        shadow: {offset: [0.01, 0.015], blur: 12, opacity: 0.6}
        mode: over
        opacity: {beats: {low: 0.8, high: 1.0, decay: 0.3}}

Units: positions and offsets are fractions of the frame; lengths (a border's
width, a shadow's blur) are pixels at 720 lines, scaled to the frame; colours
are as seen -- `#rrggbb`, or `[r, g, b]` from 0 to 1 in the display encoding.
"""

from __future__ import annotations

from typing import Any

LAYER_KEYS = ("source", "start", "place", "key", "garbage", "matte", "border", "shadow", "mode", "opacity", "depth")
PLACE_KEYS = ("translate", "scale", "rotate", "pivot", "perspective")
#: How a layer meets what is below it. `over` composites by its alpha; the others blend by the picture's values,
#: where a transparent part leaves what is below unchanged. (Multiply, darken and overlay would darken a
#: transparent part to black with merge.blend as it is; recorded in CT-0075.)
MODES = ("over", "screen", "add", "lighten", "difference")
SHAPES = ("rectangle", "ellipse", "polygon", "spline")


def _linear(value: Any) -> list[float] | None:
    """A colour as seen (hex, or display-encoded 0..1) as the graph works: linear, with alpha 1."""

    if isinstance(value, str) and value.startswith("#") and len(value) == 7:
        try:
            encoded = [int(value[index:index + 2], 16) / 255.0 for index in (1, 3, 5)]
        except ValueError:
            return None
    elif isinstance(value, (list, tuple)) and len(value) in (3, 4) and all(isinstance(c, (int, float)) for c in value):
        encoded = [float(c) for c in value[:3]]
    else:
        return None
    return [round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 6) for c in encoded] + [1.0]


class _Compiler:
    def __init__(self) -> None:
        self.nodes: dict[str, Any] = {}
        self.problems: list[str] = []

    def add(self, name: str, node: dict[str, Any]) -> str:
        self.nodes[name] = node
        return name

    def animated(self, name: str, value: Any, where: str) -> Any:
        """A parameter's value: as given, or a curve of keys or of the music's beats."""

        if isinstance(value, dict):
            if set(value) == {"keys"} and isinstance(value["keys"], list) and value["keys"]:
                return {"curve": self.add(name, {"op": "curve.keys", "keys": value["keys"]})}
            if set(value) == {"beats"} and isinstance(value["beats"], dict):
                return {"curve": self.add(name, {"op": "curve.beats", **value["beats"]})}
            self.problems.append(f"{where} is a value, {{keys: [...]}} or {{beats: {{...}}}}, not {value!r}")
            return None
        if isinstance(value, (int, float)) or (isinstance(value, list) and all(isinstance(v, (int, float)) for v in value)):
            return value
        self.problems.append(f"{where} is a number, a list of numbers, keys or beats, not {value!r}")
        return None

    def shape(self, name: str, spec: Any, where: str) -> str | None:
        if not isinstance(spec, dict) or spec.get("shape") not in SHAPES or not isinstance(spec.get("points"), list):
            self.problems.append(f"{where} is a shape: {{shape: {' | '.join(SHAPES)}, points: [[x, y], ...]}}")
            return None
        unknown = set(spec) - {"shape", "points", "feather"}
        if unknown:
            self.problems.append(f"{where} has no {', '.join(sorted(unknown))}")
        return self.add(name, {"op": "matte.shape", "shape": spec["shape"], "points": spec["points"],
                               **({"feather": spec["feather"]} if "feather" in spec else {})})

    def clear(self) -> str:
        if "clear" not in self.nodes:
            self.add("clear", {"op": "generate.solid", "colour": [0.0, 0.0, 0.0, 0.0]})
        return "clear"

    def masked(self, name: str, picture: str, matte: str) -> str:
        """The picture seen only where the matte is: its alpha multiplied by it."""

        return self.add(name, {"op": "merge.over", "front": picture, "back": self.clear(), "matte": matte})

    def alpha(self, name: str, picture: str) -> str:
        channel = self.add(f"{name}-a", {"op": "signal.channel", "picture": picture, "channel": "alpha"})
        return self.add(name, {"op": "matte.from_signal", "signal": channel})

    def filled(self, name: str, colour: list[float], matte: str) -> str:
        solid = self.add(f"{name}-colour", {"op": "generate.solid", "colour": colour})
        return self.masked(name, solid, matte)

    def layer(self, index: int, layer: Any, below: str | None) -> str | None:
        where = f"layer {index + 1}"
        if not isinstance(layer, dict):
            self.problems.append(f"{where} is a mapping with a `source`")
            return below
        unknown = [key for key in layer if key not in LAYER_KEYS]
        if unknown:
            self.problems.append(f"{where} has no {', '.join(unknown)} (a layer has {', '.join(LAYER_KEYS)})")
        source = layer.get("source")
        if not isinstance(source, str) or not source:
            self.problems.append(f"{where} says no `source` (a take of the shot, or a file)")
            return below
        n = f"L{index + 1}"
        reads = {"take": source} if "/" not in source and "." not in source else {"file": source}
        current = self.add(n, {"op": "generate.source", **reads,
                               **({"start": float(layer["start"])} if layer.get("start") is not None else {})})

        # What of the source is seen, in the source's own frame: a keyer, cut down by a garbage shape.
        seen = None
        if layer.get("key") is not None:
            seen = self.key(f"{n}-key", current, layer["key"], f"{where}'s key")
        if layer.get("garbage") is not None:
            garbage = self.shape(f"{n}-garbage", layer["garbage"], f"{where}'s garbage")
            if garbage and seen:
                seen = self.add(f"{n}-kept", {"op": "matte.combine", "a": seen, "b": garbage, "how": "intersect"})
            else:
                seen = seen or garbage
        if seen:
            current = self.masked(f"{n}-seen", current, seen)

        place = layer.get("place")
        if place is not None:
            if not isinstance(place, dict):
                self.problems.append(f"{where}'s place is a mapping of {', '.join(PLACE_KEYS)}")
            else:
                params = {}
                for key, value in place.items():
                    if key not in PLACE_KEYS:
                        self.problems.append(f"{where}'s place has no {key} ({', '.join(PLACE_KEYS)})")
                        continue
                    params[key] = self.animated(f"{n}-{key}", value, f"{where}'s {key}")
                if layer.get("depth") is not None:  # the record keeps room for 2.5D (ADR 0022 §8)
                    params["depth"] = layer["depth"]
                current = self.add(f"{n}-placed", {"op": "warp.transform", "in": current,
                                                   **{k: v for k, v in params.items() if v is not None}})

        # A border around what is seen, in the frame, after the move: a picture shrunk into a corner
        # gets its border around its new edge, the same width whatever its size.
        border = layer.get("border")
        if border is not None:
            colour = _linear(border.get("colour", "#ffffff")) if isinstance(border, dict) else None
            width = border.get("width") if isinstance(border, dict) else None
            if colour is None or not isinstance(width, (int, float)) or width <= 0:
                self.problems.append(f"{where}'s border is {{width: pixels at 720 lines, colour: '#rrggbb'}}")
            else:
                grown = self.add(f"{n}-grown", {"op": "filter.morphology", "in": self.alpha(f"{n}-alpha", current),
                                                "operation": "dilate", "radius": float(width)})
                band = self.filled(f"{n}-band", colour, grown)
                current = self.add(f"{n}-bordered", {"op": "merge.over", "front": current, "back": band})

        # A matte in the frame: where the layer shows (a window replaced by a landscape).
        if layer.get("matte") is not None:
            matte = self.shape(f"{n}-matte", layer["matte"], f"{where}'s matte")
            if matte:
                current = self.masked(f"{n}-framed", current, matte)

        if below is None:
            if any(layer.get(key) is not None for key in ("mode", "opacity", "shadow")):
                self.problems.append(f"{where} is at the back: it has nothing below it to merge with or shadow")
            return current

        shadow = layer.get("shadow")
        if shadow is not None:
            below = self.shadow(n, current, shadow, below, where)

        mode = layer.get("mode", "over")
        if mode not in MODES:
            self.problems.append(f"{where}'s mode is {mode!r}; it is one of {', '.join(MODES)}")
            mode = "over"
        mix = self.animated(f"{n}-opacity", layer["opacity"], f"{where}'s opacity") if "opacity" in layer else None
        mixing = {"mix": mix} if mix is not None else {}
        if mode == "over":
            return self.add(f"{n}-over", {"op": "merge.over", "front": current, "back": below, **mixing})
        return self.add(f"{n}-{mode}", {"op": "merge.blend", "a": below, "b": current, "mode": mode, **mixing})

    def key(self, name: str, picture: str, spec: Any, where: str) -> str | None:
        if not isinstance(spec, dict) or spec.get("by") not in ("luma", "luminance", "colour", "difference"):
            self.problems.append(f"{where} is {{by: luma | colour | difference, ...}}")
            return None
        node = {"op": "matte.key", "picture": picture, **{k: v for k, v in spec.items() if k != "reference"}}
        if spec["by"] == "colour":
            colour = _linear(spec.get("colour"))
            if colour is None:
                self.problems.append(f"{where}'s colour is '#rrggbb' or [r, g, b] as seen")
                return None
            node["colour"] = colour[:3]
        if spec["by"] == "difference":
            plate = spec.get("reference")
            if not isinstance(plate, str):
                self.problems.append(f"{where} by difference needs a `reference`: the clean plate's file")
                return None
            node["reference"] = self.add(f"{name}-plate", {"op": "generate.source", "file": plate})
        return self.add(name, node)

    def shadow(self, n: str, picture: str, spec: Any, below: str, where: str) -> str:
        if not isinstance(spec, dict):
            self.problems.append(f"{where}'s shadow is {{offset: [x, y], blur: pixels, opacity, colour}}")
            return below
        unknown = set(spec) - {"offset", "blur", "opacity", "colour"}
        if unknown:
            self.problems.append(f"{where}'s shadow has no {', '.join(sorted(unknown))}")
        colour = _linear(spec.get("colour", "#000000"))
        if colour is None:
            self.problems.append(f"{where}'s shadow colour is '#rrggbb' or [r, g, b] as seen")
            return below
        cast = self.alpha(f"{n}-cast", picture)
        if spec.get("blur"):
            cast = self.add(f"{n}-soft", {"op": "filter.blur", "in": cast, "radius": float(spec["blur"])})
        offset = spec.get("offset", [0.01, 0.015])
        cast = self.add(f"{n}-thrown", {"op": "warp.transform", "in": cast, "translate": offset})
        shade = self.filled(f"{n}-shade", colour, cast)
        opacity = self.animated(f"{n}-shadow-opacity", spec.get("opacity", 0.6), f"{where}'s shadow opacity")
        return self.add(f"{n}-shadowed", {"op": "merge.over", "front": shade, "back": below,
                                          **({"mix": opacity} if opacity is not None else {})})


def compile_layers(layers: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """(the graph, the problems): the layers as one SPEC-0012 graph with no ports, or why they cannot be."""

    if not isinstance(layers, list) or not layers:
        return None, ["`layers` is a list of layers, the first at the back"]
    compiler = _Compiler()
    top = None
    for index, layer in enumerate(layers):
        top = compiler.layer(index, layer, top)
    if top is None:
        return None, compiler.problems or ["no layer has a source"]
    return {"ports": {}, "nodes": compiler.nodes, "output": top}, compiler.problems
