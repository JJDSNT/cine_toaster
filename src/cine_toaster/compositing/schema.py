"""The operations of SPEC-0012 as data, and a validator for graphs written with them.

A graph is what a shot's `composite` or a join's recipe holds:

    nodes:
      order:  {op: signal.luma, picture: texture}
      shape:  {op: matte.from_signal, signal: order}
      reveal: {op: matte.threshold, matte: shape, progress: progress, softness: 0.05}
      out:    {op: merge.over, front: to, back: from, matte: reveal}
    output: out
    ports: {from: picture, to: picture, progress: curve, texture: picture}

A node names its op, connects its input ports to other nodes (`node`, or
`node.output` for an op with several outputs) or to the graph's `ports`, and
sets parameters. A numeric parameter may instead name a curve: `{curve: node}`.

`validate` returns the problems, each a (code, message) pair, using the codes
of SPEC-0012 §9. It checks types, kinds, parameters, references and cycles;
it renders nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TYPES = ("picture", "matte", "signal", "sound", "track", "curve", "meta")
#: The only conversions an edge may make (SPEC-0012 §1).
CONVERSIONS = {("picture", "matte"), ("matte", "picture")}

SIGNAL_KINDS = ("luminance", "luma", "alpha", "red", "green", "blue", "hue", "saturation", "depth", "depth_relative",
                "vectors", "normals", "segmentation")
#: `=in` means the output has the type (and kind) of the first input.
SAME = "=in"


@dataclass(frozen=True)
class Port:
    types: tuple[str, ...]
    required: bool = True
    kinds: tuple[str, ...] = ()  # for a signal: the kinds accepted
    many: bool = False  # a list of values


@dataclass(frozen=True)
class Op:
    inputs: dict[str, Port] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=lambda: {"out": "picture"})
    params: dict[str, str] = field(default_factory=dict)  # name -> kind: number, vector, text, file, bool, int, enum:a|b
    #: The signal kind the output carries, a fixed one, or a parameter that names it.
    kind: str = ""
    deterministic: bool = True


def P(*types: str, required: bool = True, kinds: tuple[str, ...] = (), many: bool = False) -> Port:
    return Port(types, required, kinds, many)


PIC, MAT, SIG, CRV, TRK = ("picture",), ("matte",), ("signal",), ("curve",), ("track",)
EITHER = ("picture", "matte")

OPS: dict[str, Op] = {
    # -- signal
    "signal.luminance": Op({"picture": P(*PIC)}, {"out": "signal"}, {"weights": "vector", "transform": "text"},
                           kind="luminance"),
    "signal.luma": Op({"picture": P(*PIC)}, {"out": "signal"}, {"transfer": "text", "weights": "vector"}, kind="luma"),
    "signal.channel": Op({"picture": P(*PIC)}, {"out": "signal"},
                         {"channel": "enum:red|green|blue|alpha|hue|saturation"}, kind="@channel"),
    "signal.read": Op({}, {"out": "signal"}, {"file": "file", "kind": "enum:" + "|".join(SIGNAL_KINDS),
                                              "range": "vector", "camera": "text"}, kind="@kind"),
    "signal.estimate": Op({"picture": P(*PIC)}, {"out": "signal"},
                          {"kind": "enum:depth_relative|vectors|normals|segmentation", "model": "text", "seed": "int"},
                          kind="@kind", deterministic=False),
    # Monocular depth has an unknown scale and shift; aligned to a metric reference it can be compared (§1).
    "signal.align_depth": Op({"signal": P(*SIG, kinds=("depth_relative",)),
                              "reference": P(*SIG, required=False, kinds=("depth",)),
                              "region": P(*MAT, required=False)},
                             {"out": "signal"}, {"method": "enum:scale_shift|manual", "scale": "number",
                                                 "shift": "number", "inverse": "bool", "camera": "text"}, kind="depth"),
    # -- matte
    "matte.from_signal": Op({"signal": P(*SIG)}, {"out": "matte"},
                            {"low": "number", "high": "number", "invert": "bool", "gamma": "number"}),
    "matte.key": Op({"picture": P(*PIC), "reference": P(*PIC, required=False)}, {"out": "matte"},
                    {"by": "enum:luminance|luma|colour|difference", "low": "number", "high": "number",
                     "colour": "vector", "tolerance": "number", "softness": "number", "invert": "bool"}),
    "matte.label": Op({"signal": P(*SIG, kinds=("segmentation",))}, {"out": "matte"}, {"labels": "vector"}),
    "matte.shape": Op({}, {"out": "matte"}, {"shape": "enum:rectangle|ellipse|polygon|spline", "points": "vector",
                                             "size": "number", "angle": "number", "feather": "number"}),
    "matte.threshold": Op({"matte": P(*MAT), "progress": P(*CRV)}, {"out": "matte"}, {"softness": "number"}),
    "matte.combine": Op({"a": P(*MAT), "b": P(*MAT)}, {"out": "matte"},
                        {"how": "enum:union|intersect|subtract|multiply"}),
    # -- merge
    "merge.over": Op({"front": P(*PIC), "back": P(*PIC), "matte": P(*MAT, required=False)}, params={"mix": "number"}),
    "merge.porter_duff": Op({"a": P(*PIC), "b": P(*PIC)}, params={"how": "enum:over|under|in|out|atop|xor"}),
    "merge.blend": Op({"a": P(*PIC), "b": P(*PIC)},
                      params={"mode": "enum:screen|add|multiply|overlay|difference|lighten|darken", "mix": "number"}),
    "merge.mix": Op({"a": P(*PIC), "b": P(*PIC), "by": P("matte", "curve")}),
    "merge.channels": Op({"red": P("signal", "matte", required=False), "green": P("signal", "matte", required=False),
                          "blue": P("signal", "matte", required=False), "alpha": P("signal", "matte", required=False)}),
    "merge.depth": Op({"pictures": P(*PIC, many=True), "depths": P(*SIG, kinds=("depth",), many=True)},
                      params={"near_is_small": "bool"}),
    # -- warp
    "warp.transform": Op({"in": P(*EITHER)}, {"out": SAME},
                         {"translate": "vector", "scale": "vector", "rotate": "vector", "pivot": "vector",
                          "perspective": "number", "depth": "number"}),
    "warp.corner_pin": Op({"in": P(*EITHER), "track": P(*TRK, required=False)}, {"out": SAME}, {"corners": "vector"}),
    "warp.displace": Op({"in": P(*EITHER), "map": P(*SIG)}, {"out": SAME},
                        {"strength": "number", "direction": "vector"}),
    "warp.procedural": Op({"in": P(*EITHER)}, {"out": SAME},
                          {"kind": "enum:ripple|swirl|bend|lens", "amount": "number", "frequency": "number",
                           "centre": "vector"}),
    # -- colour
    "colour.lut": Op({"in": P(*PIC)}, params={"file": "file", "look": "text"}),
    "colour.grade": Op({"in": P(*PIC)}, params={"lift": "vector", "gamma": "vector", "gain": "vector",
                                                "saturation": "number", "hue": "number"}),
    "colour.curve": Op({"in": P(*EITHER)}, {"out": SAME}, {"points": "vector"}),
    "colour.posterise": Op({"in": P(*PIC)}, params={"levels": "int"}),
    "colour.solarise": Op({"in": P(*PIC)}, params={"threshold": "number"}),
    "colour.cycle": Op({"in": P(*PIC)}, params={"speed": "number"}),
    "colour.invert": Op({"in": P(*EITHER)}, {"out": SAME}),
    # -- filter
    "filter.blur": Op({"in": P(*EITHER)}, {"out": SAME},
                      {"radius": "number", "kind": "enum:gaussian|box|directional|defocus", "angle": "number"}),
    "filter.sharpen": Op({"in": P(*PIC)}, params={"amount": "number"}),
    "filter.glow": Op({"in": P(*PIC)}, params={"threshold": "number", "radius": "number", "intensity": "number"}),
    "filter.edges": Op({"in": P(*PIC)}, {"out": "matte"}, {"kind": "enum:sobel|laplace|canny"}),
    "filter.morphology": Op({"in": P(*MAT)}, {"out": "matte"}, {"operation": "enum:erode|dilate", "radius": "number"}),
    "filter.noise": Op({"in": P(*PIC)}, params={"amount": "number", "size": "number", "seed": "int"}),
    # -- time
    "time.remap": Op({"in": P(*TYPES[:4])}, {"out": SAME}, {"map": "number"}),
    "time.offset": Op({"in": P(*TYPES[:4])}, {"out": SAME}, {"frames": "int"}),
    "time.blend": Op({"in": P(*PIC)}, params={"frames": "int"}),
    "time.echo": Op({"in": P(*PIC)}, params={"count": "int", "spacing": "int", "decay": "number"}),
    # -- generate
    "generate.source": Op({}, {"out": "picture", "sound": "sound", "meta": "meta"},
                          {"take": "text", "file": "file", "colorspace": "text", "alpha": "enum:straight|premultiplied",
                           "start": "number", "duration": "number"}),
    "generate.solid": Op({}, params={"colour": "vector"}),
    "generate.gradient": Op({}, params={"kind": "enum:linear|radial", "colours": "vector", "angle": "number"}),
    "generate.noise": Op({}, params={"kind": "enum:value|perlin|grain", "scale": "number", "seed": "int"}),
    "generate.text": Op({}, params={"text": "text", "font": "file", "size": "number", "colour": "vector",
                                    "position": "vector", "reveal": "number"}),
    "generate.render": Op({}, {"out": "picture", "depth": "signal", "alpha": "matte"},
                          {"renderer": "text", "scene": "file", "recipe": "text", "seed": "int", "camera": "text"},
                          kind="depth", deterministic=False),
    # -- track and curves
    "track.measure": Op({"in": P(*PIC)}, {"out": "track"},
                        {"kind": "enum:point|plane|camera", "region": "vector", "tracker": "text"}),
    "track.read": Op({}, {"out": "track"}, {"file": "file"}),
    "curve.keys": Op({}, {"out": "curve"}, {"keys": "vector"}),
    "curve.beats": Op({}, {"out": "curve"}, {"attack": "number", "decay": "number", "every": "int", "low": "number",
                                             "high": "number"}),
    "curve.from_track": Op({"track": P(*TRK)}, {"out": "curve"}, {"field": "enum:x|y|rotation|scale"}),
    "curve.progress": Op({}, {"out": "curve"}),
    "curve.noise": Op({}, {"out": "curve"}, {"seed": "int", "frequency": "number", "amplitude": "number",
                                             "offset": "number"}),
    "curve.map": Op({"in": P(*CRV)}, {"out": "curve"},
                    {"how": "enum:invert|scale|offset|clamp|remap|ease", "factor": "number", "low": "number",
                     "high": "number", "out_low": "number", "out_high": "number", "ease": "text"}),
    "curve.combine": Op({"a": P(*CRV), "b": P(*CRV)}, {"out": "curve"}, {"how": "enum:add|subtract|multiply|min|max"}),
}

#: What each way of keying needs (SPEC-0012 §3, matte.key): parameters, or the `reference` input.
KEY_NEEDS = {"luminance": ("low", "high"), "luma": ("low", "high"), "colour": ("colour", "tolerance"),
             "difference": ("reference", "tolerance")}

#: Parameters an op cannot run without; "a|b" means one of them (SPEC-0012 §9, composite_param_missing).
REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "signal.channel": ("channel",), "signal.read": ("file", "kind"), "signal.estimate": ("kind", "model"),
    "matte.shape": ("shape",), "matte.combine": ("how",), "matte.label": ("labels",),
    "merge.porter_duff": ("how",), "merge.blend": ("mode",),
    "warp.procedural": ("kind",), "warp.corner_pin": ("corners|track",),
    "colour.lut": ("file|look",), "colour.posterise": ("levels",), "colour.solarise": ("threshold",),
    "filter.morphology": ("operation", "radius"), "filter.blur": ("radius",),
    "time.remap": ("map",), "time.offset": ("frames",), "time.blend": ("frames",), "time.echo": ("count",),
    "generate.source": ("take|file",), "generate.solid": ("colour",), "generate.text": ("text",),
    "generate.render": ("renderer",), "track.measure": ("kind",), "track.read": ("file",),
    "curve.keys": ("keys",), "curve.map": ("how",), "curve.combine": ("how",), "curve.from_track": ("field",),
}

#: An opaque node declares its own ports (SPEC-0012 §3, Opaque nodes): the renderer it needs, and what it reads.
OPAQUE_PREFIX = "opaque."
OPAQUE_PORTS: dict[str, dict[str, Port]] = {
    "opaque.gl": {"from": P(*PIC), "to": P(*PIC), "progress": P(*CRV)},  # a gl-transitions shader
    "opaque.natron": {"in": P(*PIC)},  # an OFX plugin
    "opaque.blender": {},  # a scene that makes its own picture
}


@dataclass
class _Value:
    type: str
    kind: str = ""
    camera: str = ""  # for a metric depth: the camera it is measured from


def _ref(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def validate(graph: dict[str, Any]) -> list[tuple[str, str]]:
    """Every problem with a graph, before anything renders (SPEC-0012 §9)."""

    problems: list[tuple[str, str]] = []
    nodes: dict[str, dict[str, Any]] = graph.get("nodes") or {}
    external = {name: _Value(kind) for name, kind in (graph.get("ports") or {}).items()}
    for name, value in external.items():
        if value.type not in TYPES:
            problems.append(("composite_type_mismatch", f"port {name} is a {value.type!r}, not one of {TYPES}"))

    # Order the nodes so each is checked after what feeds it; a cycle is reported once.
    order: list[str] = []
    state: dict[str, int] = {}

    def feeds(node: dict[str, Any]) -> list[str]:
        """What a node reads: its input ports, and the curves its parameters follow -- never a parameter's text."""

        op = OPS.get(str(node.get("op") or ""))
        found = []
        for key, value in node.items():
            if key == "op":
                continue
            if op is not None and key not in op.inputs and not (isinstance(value, dict) and "curve" in value):
                continue
            for item in value if isinstance(value, list) else [value]:
                reference = item.get("curve") if isinstance(item, dict) else _ref(item)
                if reference:
                    found.append(reference.split(".", 1)[0])
        return [item for item in found if item in nodes]

    def visit(name: str, trail: tuple[str, ...]) -> None:
        if state.get(name) == 2:
            return
        if state.get(name) == 1:
            problems.append(("composite_cycle", f"{' -> '.join(trail + (name,))} is a cycle"))
            return
        state[name] = 1
        for upstream in feeds(nodes[name]):
            visit(upstream, trail + (name,))
        state[name] = 2
        order.append(name)

    for name in nodes:
        visit(name, ())
    if any(code == "composite_cycle" for code, _ in problems):
        return problems

    values: dict[str, _Value] = {}

    def resolve(reference: str, where: str) -> _Value | None:
        if reference in external:
            return external[reference]
        node, _, output = reference.partition(".")
        if node not in nodes:
            problems.append(("composite_input_missing", f"{where} reads {reference!r}, which is no node or port"))
            return None
        if output:
            return values.get(reference) or problems.append(
                ("composite_input_missing", f"{where} reads {reference!r}; {node} has no output {output!r}")) or None
        return values.get(node)

    for name in order:
        node = nodes[name]
        op_name = str(node.get("op") or "")
        if op_name.startswith(OPAQUE_PREFIX):
            if op_name not in OPAQUE_PORTS:
                problems.append(("composite_unknown_op", f"{name} asks for {op_name!r}; opaque nodes are "
                                                         f"{', '.join(OPAQUE_PORTS)}"))
                continue
            # Its declared ports are checked like any op's; other values are its item's own parameters.
            op = Op(OPAQUE_PORTS[op_name], {"out": "picture"}, {key: "text" for key in node if key != "op"})
            for port_name, port in op.inputs.items():
                given = _ref(node.get(port_name))
                if given is None:
                    problems.append(("composite_input_missing", f"{name} ({op_name}) has nothing on its {port_name}"))
                    continue
                value = resolve(given, f"{name}.{port_name}")
                if value is not None and value.type not in port.types and (value.type, port.types[0]) not in CONVERSIONS:
                    problems.append(("composite_type_mismatch", f"{name}.{port_name} takes {port.types[0]}; {given} "
                                                                f"gives {value.type}"))
            values[name] = _Value("picture")
            continue
        op = OPS.get(op_name)
        if op is None:
            problems.append(("composite_unknown_op", f"{name} asks for {op_name!r}, which no primitive declares"))
            continue
        first: _Value | None = None
        for port_name, port in op.inputs.items():
            given = node.get(port_name)
            if given is None:
                if port.required:
                    problems.append(("composite_input_missing", f"{name} ({op_name}) has nothing on its {port_name}"))
                continue
            for item in given if (port.many and isinstance(given, list)) else [given]:
                reference = _ref(item)
                if reference is None:
                    problems.append(("composite_type_mismatch", f"{name}.{port_name} must name a node or a port"))
                    continue
                value = resolve(reference, f"{name}.{port_name}")
                if value is None:
                    continue
                first = first or value
                if value.type not in port.types and (value.type, port.types[0]) not in CONVERSIONS:
                    problems.append(("composite_type_mismatch",
                                     f"{name}.{port_name} takes {' or '.join(port.types)}; {reference} gives "
                                     f"{value.type}"))
                elif port.kinds and value.type == "signal" and value.kind and value.kind not in port.kinds:
                    problems.append(("composite_type_mismatch",
                                     f"{name}.{port_name} takes a {' or '.join(port.kinds)} signal; {reference} gives "
                                     f"{value.kind}"))
        for key, value in node.items():
            if key == "op" or key in op.inputs:
                continue
            kind = op.params.get(key)
            if kind is None:
                problems.append(("composite_unknown_param", f"{name} ({op_name}) has no parameter {key!r}"))
                continue
            if isinstance(value, dict) and "curve" in value:
                curve = resolve(str(value["curve"]), f"{name}.{key}")
                if curve is not None and curve.type != "curve":
                    problems.append(("composite_type_mismatch", f"{name}.{key} names {value['curve']}, not a curve"))
                elif kind not in ("number", "vector", "int"):
                    problems.append(("composite_type_mismatch", f"{name}.{key} is a {kind}; it cannot follow a curve"))
                continue
            if kind.startswith("enum:") and str(value) not in kind[5:].split("|"):
                problems.append(("composite_unknown_param",
                                 f"{name}.{key} is {value!r}; it is one of {kind[5:].replace('|', ', ')}"))
            elif kind in ("number", "int") and not isinstance(value, (int, float)):
                problems.append(("composite_type_mismatch", f"{name}.{key} is a number, not {value!r}"))
        for need in REQUIRED_PARAMS.get(op_name, ()):
            choices = need.split("|")
            if not any(node.get(choice) is not None for choice in choices):
                problems.append(("composite_param_missing", f"{name} ({op_name}) needs {' or '.join(choices)}"))
        if op_name == "signal.align_depth":
            method = node.get("method") or "scale_shift"
            lacking = ([key for key in ("scale", "shift") if node.get(key) is None] if method == "manual"
                       else ([] if node.get("reference") else ["reference"]))
            if lacking:
                problems.append(("composite_param_missing", f"{name} aligns by {method} and needs {', '.join(lacking)}"))
        if op_name == "merge.depth":
            pictures, depths = node.get("pictures") or [], node.get("depths") or []
            if len(pictures) != len(depths):
                problems.append(("composite_type_mismatch",
                                 f"{name} has {len(pictures)} picture(s) and {len(depths)} depth(s); one each"))
            cameras = set()
            for reference in depths:
                value = resolve(reference, f"{name}.depths") if _ref(reference) else None
                if value is not None and value.kind == "depth":
                    if not value.camera:
                        problems.append(("composite_param_missing", f"{name}: the depth {reference} says no camera; "
                                                                    "depths are compared only within one camera"))
                    cameras.add(value.camera)
            if len(cameras - {""}) > 1:
                problems.append(("composite_type_mismatch",
                                 f"{name} compares depths from different cameras: {', '.join(sorted(cameras - {''}))}"))
        if op_name == "matte.key":
            method = str(node.get("by") or "")
            if method not in KEY_NEEDS:
                problems.append(("composite_param_missing", f"{name} (matte.key) says no `by`: "
                                                            f"{', '.join(KEY_NEEDS)}"))
            else:
                lacking = [key for key in KEY_NEEDS[method] if node.get(key) is None]
                if lacking:
                    problems.append(("composite_param_missing",
                                     f"{name} keys by {method} and needs {', '.join(lacking)}"))
        for output, kind in op.outputs.items():
            if kind == SAME:
                value = _Value(first.type, first.kind, first.camera) if first else _Value("picture")
            else:
                signal_kind = ""
                if kind == "signal":
                    signal_kind = str(node.get(op.kind[1:], "")) if op.kind.startswith("@") else op.kind
                camera = ""
                if signal_kind == "depth":
                    camera = str(node.get("camera") or "")
                    if not camera and op_name == "signal.align_depth" and _ref(node.get("reference")):
                        reference = resolve(node["reference"], f"{name}.reference")
                        camera = reference.camera if reference else ""
                value = _Value(kind, signal_kind, camera)
            if output == next(iter(op.outputs)):
                values[name] = value
            values[f"{name}.{output}"] = value

    output = graph.get("output")
    if not output:
        problems.append(("composite_input_missing", "the graph names no output"))
    else:
        result = resolve(str(output), "output")
        if result is not None and result.type != "picture":
            problems.append(("composite_type_mismatch", f"the output {output} gives {result.type}, not a picture"))
    return problems
