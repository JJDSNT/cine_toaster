"""OpenFX plugins as a node of the graph: the adapter to Natron (CT-0078, a shot drawn once).

An OpenFX plugin runs inside Natron, a process that reads and writes frames as
files. So `opaque.natron` (SPEC-0012's opaque node for an OFX plugin) cannot be
drawn frame by frame like the other ops: before a graph is drawn, `stage` draws
what feeds each such node, hands those frames to Natron as float OpenEXR -- the
node's own files, linear and premultiplied, no video encode and no clipping --
and reads Natron's frames back as that node's value. The rest of the graph is
then drawn as usual, by GL when it holds every other op.

Adjacent plugins are one Natron chain: a plugin whose only reader is another
plugin is run with it, in order.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from ..errors import ValidationError

OP = "opaque.natron"


def _reads(node: dict[str, Any]) -> list[str]:
    """The nodes and ports a node reads (as the schema's validation finds them)."""

    from .schema import OPAQUE_PORTS, OPS

    op = str(node.get("op") or "")
    ports = set(OPAQUE_PORTS.get(op) or (OPS[op].inputs if op in OPS else {}))
    found = []
    for key, value in node.items():
        if key == "op":
            continue
        for item in value if isinstance(value, list) else [value]:
            if key in ports and isinstance(item, str):
                found.append(item.split(".", 1)[0])
            elif isinstance(item, dict) and isinstance(item.get("curve"), str):
                found.append(item["curve"].split(".", 1)[0])
    return found


def _upstream(nodes: dict[str, Any], start: str) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        name = stack.pop()
        if name in seen or name not in nodes:
            continue
        seen.add(name)
        stack.extend(_reads(nodes[name]))
    return seen


def _frames_of(value: Any, frames: int):
    """A port's pictures frame by frame: a clip or a stack by its frames, a still picture on every frame."""

    still = isinstance(value, np.ndarray) and value.ndim == 3
    return (value if still else value[index] for index in range(frames))


def has_plugins(graph: dict[str, Any]) -> bool:
    return any(node.get("op") == OP for node in (graph.get("nodes") or {}).values())


def stage(graph: dict[str, Any], inputs: dict[str, Any], *, frames: int, size: tuple[int, int], fps: float,
          root: Path | None = None, beats: list[float] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """The graph with each OpenFX chain run by Natron and in its place a port, fed by Natron's frames."""

    from . import reference
    from .gl import renderer_for

    graph = {**graph, "ports": dict(graph.get("ports") or {}), "nodes": dict(graph["nodes"])}
    inputs = dict(inputs)
    while has_plugins(graph):
        nodes = graph["nodes"]
        plugins = [name for name, node in nodes.items() if node.get("op") == OP]
        # The first chain whose picture no other plugin makes.
        first = next(name for name in plugins
                     if not any(nodes[up].get("op") == OP for up in _upstream(nodes, str(nodes[name]["in"]).split(".")[0])))
        chain = [first]
        while True:
            readers = [name for name, node in nodes.items() if chain[-1] in _reads(node)]
            if graph["output"].split(".")[0] == chain[-1] or len(readers) != 1 or nodes[readers[0]].get("op") != OP:
                break
            chain.append(readers[0])
        source = str(nodes[first]["in"])
        if source.split(".")[0] in graph["ports"]:
            pictures: Any = _frames_of(inputs[source.split(".")[0]], frames)
        else:
            sub = {"ports": graph["ports"], "nodes": {name: nodes[name] for name in _upstream(nodes, source.split(".")[0])},
                   "output": source}
            pictures, _identity, _cached = reference.render(sub, inputs, frames=frames, size=size, fps=fps, root=root,
                                                            beats=beats, renderer=renderer_for(sub))
        clip = run([{"plugin": nodes[name]["plugin"], "params": nodes[name].get("params") or {}} for name in chain],
                   pictures, frames=frames, size=size, fps=fps)
        last = chain[-1]
        for name in chain:
            del nodes[name]
        graph["ports"][last] = "picture"
        inputs[last] = clip
    return graph, inputs


def run(plugins: list[dict[str, Any]], pictures: Any, *, frames: int, size: tuple[int, int], fps: float):
    """`pictures` (linear, premultiplied) through Natron's chain of `plugins`; Natron's frames as a clip."""

    from ..vfx import natron_binary

    natron = natron_binary()
    if not natron:
        raise ValidationError("OpenFX effects run in Natron, which is not found (install it, or set "
                              "CINE_TOASTER_NATRON)")
    try:
        import OpenEXR
    except ImportError as error:
        raise ValidationError("Handing frames to Natron needs OpenEXR: pip install -e '.[vfx]'") from error
    work = Path(tempfile.mkdtemp(prefix="natron-"))
    try:
        return _run(natron, OpenEXR, plugins, pictures, work, frames=frames, size=size, fps=fps)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _run(natron: str, OpenEXR: Any, plugins: list[dict[str, Any]], pictures: Any, work: Path, *, frames: int,
         size: tuple[int, int], fps: float):
    from ..vfx import NATRON_CHAIN_SCRIPT
    from . import reference

    width, height = size
    (work / "in").mkdir()
    (work / "out").mkdir()
    for index, picture in zip(range(frames), pictures):
        data = np.ascontiguousarray(np.asarray(picture, dtype=np.float32)).astype(np.float16)
        OpenEXR.File({"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION},
                     {"RGBA": data}).write(str(work / "in" / f"f_{index + 1:04d}.exr"))
    spec = work / "spec.json"
    spec.write_text(json.dumps({"input": str(work / "in" / "f_####.exr"), "output": str(work / "out" / "o_####.exr"),
                                "frames": frames, "width": width, "height": height, "effects": plugins}),
                    encoding="utf-8")
    completed = subprocess.run([natron, "-w", "Out", f"1-{frames}", str(NATRON_CHAIN_SCRIPT)], cwd=work,
                               env={**os.environ, "CINE_TOASTER_OFX_SPEC": str(spec)}, capture_output=True,
                               text=True, timeout=3600)
    if completed.returncode != 0 or not sorted((work / "out").glob("o_*.exr")):
        raise ValidationError("Natron could not run the OpenFX chain",
                              detail=(completed.stderr or completed.stdout)[-600:])
    # Read back as any float sequence is: linear, premultiplied, its range kept (the range rule). The clip
    # holds its frames in its own storage, so Natron's files can go.
    return reference.read(work / "out" / "o_%04d.exr", frames, size, fps)
