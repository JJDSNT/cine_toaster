"""A shot's layers, as a filmmaker writes them, compiled into a SPEC-0012 graph (C4, CT-0075).

A layer is a picture placed over the ones below it: a source (a take of the
shot or a file), where it sits (move, size, turn in three axes with
perspective), what of it is seen (a keyer, a garbage shape, a matte in the
frame), how it meets what is below (a mode and an opacity), and a border and
a drop shadow. Any number can change over time, by keys or by the music's
beats (C3).

A layer may say its depth (C8 step 7, CT-0081): layers with a depth are ordered
among themselves by it (`merge.depth`: each one's depth carried into its
coverage, three depth states, the records' refusals kept), at the place of the
lowest of them; a layer without one keeps its place in the stack, over
everything below it. A layer's source may be a Blender render's record
(`render`), and what of it is seen may be cut by a segmentation (`cut`):

      - source: plates/street.mp4                 # the plate, its estimated depth per pixel
        depth: {signal: street-z, camera: shot-cam, estimated: true}
      - source: plates/street.mp4                 # the person, cut out, one depth for all of her
        cut: {signal: street-people, labels: [1]}
        depth: {signal: street-z, camera: shot-cam, estimated: true, object: true}
      - render: lamp                              # a Blender object, its own depth
        depth: {render: true, camera: shot-cam}

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
        key: {by: colour, colour: "#1fb34a", tolerance: 0.08, softness: 0.05}   # and its spill removed
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

LAYER_KEYS = ("source", "render", "start", "place", "key", "garbage", "cut", "matte", "border", "shadow", "mode",
              "opacity", "depth", "retime", "offset", "echo", "pin")
#: A layer's depth (C8 step 7, CT-0081): a signal record of its source, the render's own, or a constant -- each
#: from a named camera -- and what the merge may do with it.
DEPTH_KEYS = ("signal", "render", "camera", "object", "statistic", "estimated", "inversions", "unknown")
#: What a layer with a depth cannot have yet: its depth would have to move, shadow or blend with it.
NOT_WITH_DEPTH = ("place", "pin", "echo", "shadow", "border")
ECHO_KEYS = ("count", "spacing", "decay")
PIN_KEYS = ("track", "measure", "region", "of", "corners")
PLACE_KEYS = ("translate", "scale", "rotate", "pivot", "perspective")
#: How a layer meets what is below it: `over` by its alpha, the others by a blend of colours where the layer
#: is, leaving what is below unchanged where it is transparent (merge.blend, W3C Compositing; CT-0075).
MODES = ("over", "screen", "add", "multiply", "lighten", "darken", "difference", "overlay")
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
        #: Layers with a depth, waiting to be ordered among themselves: (picture, depth, its spec).
        self.group: list[tuple[str, str, dict[str, Any]]] = []

    def flush(self, below: str | None) -> str | None:
        """The layers with a depth merged by it, over what is below them (C8 step 7)."""

        if not self.group:
            return below
        policies = {spec.get("unknown") for _, _, spec in self.group if spec.get("unknown")}
        if len(policies) > 1:
            self.problems.append(f"layers merged by depth say different things of an unknown depth: "
                                 f"{', '.join(sorted(policies))}")
        index = len([name for name in self.nodes if name.startswith("depth-merge")]) + 1
        merged = self.add(f"depth-merge{index}", {
            "op": "merge.depth", "pictures": [picture for picture, _, _ in self.group],
            "depths": [depth for _, depth, _ in self.group], **({"unknown": next(iter(policies))} if policies else {})})
        self.group = []
        if below is None:
            return merged
        return self.add(f"depth-merge{index}-over", {"op": "merge.over", "front": merged, "back": below})

    def cut(self, n: str, spec: Any, where: str) -> str | None:
        """A segmentation of the source's own pixels, its labels kept: a matte (C8 step 7)."""

        if not isinstance(spec, dict) or not isinstance(spec.get("signal"), str) \
                or not isinstance(spec.get("labels"), list) or not spec["labels"] or set(spec) - {"signal", "labels"}:
            self.problems.append(f"{where} is {{signal: a segmentation's id, labels: [numbers]}}")
            return None
        source = self.nodes.get(n, {})
        labels = self.add(f"{n}-cut-labels", {"op": "signal.read", "signal": spec["signal"], "kind": "segmentation",
                                              **({"of": n} if source.get("op") == "generate.source" else {})})
        return self.add(f"{n}-cut", {"op": "matte.label", "signal": labels, "labels": spec["labels"]})

    def depth_of(self, n: str, current: str, spec: Any, where: str) -> str | None:
        """A layer's depth node: a signal record of its source (read at the instant the source shows), or the
        render's own; one depth for the whole object when asked."""

        if not isinstance(spec, dict) or set(spec) - set(DEPTH_KEYS):
            self.problems.append(f"{where}'s depth is {{signal: id | render: true, camera, object, estimated, "
                                 "inversions, unknown}}")
            return None
        if not spec.get("camera"):
            self.problems.append(f"{where}'s depth names its camera: depths are compared within one camera")
            return None
        source = self.nodes.get(n, {})
        if spec.get("render"):
            if source.get("op") != "generate.render":
                self.problems.append(f"{where}'s depth is its render's only when its source is a `render`")
                return None
            depth = f"{n}.depth"
        elif isinstance(spec.get("signal"), str):
            depth = self.add(f"{n}-depth", {
                "op": "signal.read", "signal": spec["signal"], "kind": "depth", "camera": spec["camera"],
                **({"of": n} if source.get("op") == "generate.source" else {}),
                **({"estimated": True} if spec.get("estimated") else {}),
                **({"inversions": spec["inversions"]} if spec.get("inversions") else {})})
        else:
            self.problems.append(f"{where}'s depth is a signal's (`signal: id`) or its render's (`render: true`)")
            return None
        if spec.get("object"):
            depth = self.add(f"{n}-object-depth", {
                "op": "signal.object_depth", "signal": depth, "matte": self.alpha(f"{n}-object", current),
                "camera": spec["camera"], **({"statistic": spec["statistic"]} if spec.get("statistic") else {})})
        return depth

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
        n = f"L{index + 1}"
        depth = layer.get("depth")
        if layer.get("render") is not None:
            if source is not None or not isinstance(layer["render"], str):
                self.problems.append(f"{where} has a `source` or a `render` (a render's record by its id), not both")
                return below
            camera = depth.get("camera") if isinstance(depth, dict) else None
            current = self.add(n, {"op": "generate.render", "render": layer["render"],
                                   **({"camera": camera} if camera else {})})
        elif not isinstance(source, str) or not source:
            self.problems.append(f"{where} says no `source` (a take of the shot, or a file) or `render`")
            return below
        else:
            reads = {"take": source} if "/" not in source and "." not in source else {"file": source}
            current = self.add(n, {"op": "generate.source", **reads,
                                   **({"start": float(layer["start"])} if layer.get("start") is not None else {})})
            current = self.timed(n, current, layer, where)

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
        if layer.get("cut") is not None:  # a segmentation of the source's own pixels (C8 step 7)
            cut = self.cut(n, layer["cut"], f"{where}'s cut")
            if cut and seen:
                seen = self.add(f"{n}-cut-kept", {"op": "matte.combine", "a": seen, "b": cut, "how": "intersect"})
            else:
                seen = seen or cut
        key = layer.get("key")
        if seen and isinstance(key, dict) and key.get("by") == "colour" and key.get("despill", True):
            # The screen taken out with the key (CT-0075): its share of each edge pixel subtracted, and its light
            # on the subject held back -- no green fringe on hair. `despill: false` multiplies by the matte only.
            current = self.add(f"{n}-seen", {"op": "colour.despill", "in": current, "matte": seen,
                                             "colour": self.nodes[f"{n}-key"]["colour"]})
        elif seen:
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
                current = self.add(f"{n}-placed", {"op": "warp.transform", "in": current,
                                                   **{k: v for k, v in params.items() if v is not None}})

        # Pinned by a track (C7, CT-0080): onto the plane, or moved with the point, another layer's source shows.
        if layer.get("pin") is not None:
            if layer.get("place") is not None:
                self.problems.append(f"{where} is pinned or placed, not both")
            else:
                current = self.pinned(n, current, layer["pin"], index, where)

        # Trails behind the layer as it moves (C7): its past frames laid under it, after the move, so the trail
        # follows where it went.
        if layer.get("echo") is not None:
            echo = layer["echo"]
            if not isinstance(echo, dict) or set(echo) - set(ECHO_KEYS):
                self.problems.append(f"{where}'s echo is {{count, spacing (frames), decay}}")
            else:
                current = self.add(f"{n}-echo", {"op": "time.echo", "in": current, **{k: echo[k] for k in echo}})

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

        if layer.get("depth") is not None:
            # Ordered among the layers with a depth by it, not by its place: kept for the merge (`flush`).
            for key in NOT_WITH_DEPTH:
                if layer.get(key) is not None:
                    self.problems.append(f"{where} has a depth and a {key}: its depth would have to follow it, "
                                         "which is not done yet")
            if layer.get("mode", "over") != "over":
                self.problems.append(f"{where} has a depth: it meets the others by it, over -- not {layer['mode']}")
            depth = self.depth_of(n, current, layer["depth"], where)
            if depth is None:
                return below
            if "opacity" in layer:
                mix = self.animated(f"{n}-opacity", layer["opacity"], f"{where}'s opacity")
                current = self.add(f"{n}-faded", {"op": "merge.over", "front": current, "back": self.clear(),
                                                  **({"mix": mix} if mix is not None else {})})
            self.group.append((current, depth, layer["depth"]))
            return below
        below = self.flush(below)

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

    def timed(self, n: str, current: str, layer: dict[str, Any], where: str) -> str:
        """The layer's source in time (C7, CT-0080): retimed (speed, freeze -- seconds, not beats: a layer is
        compiled before its shot is cut), and offset by some seconds; each a `time.remap` the sound and the
        tracks follow."""

        from .retime import compile_retime

        if layer.get("retime") is not None:
            spec = layer["retime"]
            speeds = spec.get("speed") if isinstance(spec, dict) else None
            on_beats = isinstance(speeds, list) and any(isinstance(key, dict) and "beat" in key for key in speeds)
            if isinstance(spec, dict) and (spec.get("reverse") or on_beats):
                self.problems.append(f"{where}'s retime: reverse and beats belong to a shot's retime (a layer "
                                     "does not know its shot's length or beats yet)")
            else:
                fragment, problems = compile_retime(spec, where=f"{where}'s retime", prefix=f"{n}-retime")
                self.problems.extend(problems)
                if fragment:
                    for name, node in fragment["nodes"].items():
                        self.nodes[name] = {**node, "in": current} if node["op"] == "time.remap" else node
                    current = fragment["output"]
        offset = layer.get("offset")
        if offset is not None:
            if isinstance(offset, bool) or not isinstance(offset, (int, float)):
                self.problems.append(f"{where}'s offset is seconds (positive: shown later)")
            else:
                # Shown `offset` seconds late: the source's instant is the layer's minus the offset (a slope-1 map).
                horizon = 3600.0
                late = self.add(f"{n}-offset-map", {"op": "curve.keys", "keys": [[0, -float(offset)],
                                                                                  [horizon, horizon - float(offset)]]})
                current = self.add(f"{n}-offset", {"op": "time.remap", "in": current, "map": {"curve": late}})
        return current

    def pinned(self, n: str, current: str, spec: Any, index: int, where: str) -> str:
        """The layer pinned by a track of another layer's source: read from a file, or measured here."""

        if not isinstance(spec, dict) or set(spec) - set(PIN_KEYS) or not (spec.get("track") or spec.get("measure")):
            self.problems.append(f"{where}'s pin is {{track: file | measure: point | plane, region, of: layer, "
                                 "corners}}")
            return current
        of = spec.get("of", 1)
        if not isinstance(of, int) or not 1 <= of <= index:
            self.problems.append(f"{where}'s pin follows a layer below it: `of` is 1 to {index}")
            return current
        source = f"L{of}"
        if spec.get("track"):
            given = str(spec["track"])
            # A production's track by its id (tracks/<id>), or a track file by its path.
            reads = {"file": given} if "/" in given or given.endswith(".json") else {"track": given}
            track = self.add(f"{n}-track", {"op": "track.read", **reads, "of": source})
        else:
            if spec["measure"] not in ("point", "plane"):
                self.problems.append(f"{where}'s pin measures a point or a plane, not {spec['measure']!r}")
                return current
            track = self.add(f"{n}-track", {"op": "track.measure", "in": source, "kind": spec["measure"],
                                            **({"region": spec["region"]} if spec.get("region") else {})})
        return self.add(f"{n}-pinned", {"op": "warp.corner_pin", "in": current, "track": track,
                                        **({"corners": spec["corners"]} if spec.get("corners") else {})})

    def key(self, name: str, picture: str, spec: Any, where: str) -> str | None:
        if not isinstance(spec, dict) or spec.get("by") not in ("luma", "luminance", "colour", "difference"):
            self.problems.append(f"{where} is {{by: luma | colour | difference, ...}}")
            return None
        node = {"op": "matte.key", "picture": picture,
                **{k: v for k, v in spec.items() if k not in ("reference", "despill")}}
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
    top = compiler.flush(top)
    if top is None:
        return None, compiler.problems or ["no layer has a source"]
    return {"ports": {}, "nodes": compiler.nodes, "output": top}, compiler.problems
