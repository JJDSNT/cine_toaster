"""The signal ops on GL against the reference, timed by part (C8 step 6, CT-0081).

    PYTHONPATH=src python scripts/research/gl_signal_bench.py [width height frames]
    GALLIUM_DRIVER=d3d12 PYTHONPATH=src python scripts/research/gl_signal_bench.py   # WSL's GPU

A production with three depth signals (one with unknown pixels) and a segmentation; a graph merging three
layers by depth with coverage, one of them given an object's depth, a label matte over the result. Printed:
the reference's time a frame; GL's, split into reading the records (CPU), uploads, draws (submitted), the
download of the output (which waits for the GPU), and the rest; and the largest difference between them.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from cine_toaster import signals
from cine_toaster.compositing import reference
from cine_toaster.compositing.gl import renderer_for
from cine_toaster.state import Actor

TOOL = Actor(id="bench", kind="system")


def scene(width: int, height: int, frames: int) -> tuple[Path, dict, dict]:
    root = Path(tempfile.mkdtemp(prefix="ct-gl-signals-"))
    (root / "project.yaml").write_text("id: bench\ntitle: Bench\n")
    rows, cols = np.indices((height, width), dtype=np.float32)
    depth = {"quantity": "z", "unit": "m", "near_is_small": True}
    inputs, nodes = {}, {}
    for index, (cx, radius, z) in enumerate(((0.35, 0.22, 3.0), (0.55, 0.3, 4.0), (0.5, 2.0, 6.0))):
        distance = np.hypot(cols / width - cx, (rows / height - 0.5) * height / width)
        alpha = np.clip((radius - distance) * width / 2, 0, 1).astype(np.float32)
        value = np.where(alpha > 0.5, z + 0.5 * distance, np.inf).astype(np.float32)
        unknown = [(np.indices(value.shape)[0] < height // 10) & (alpha > 0.5)] * frames if index == 1 else None
        signals.record_signal(root, signal_id=f"z{index}", kind="depth", origin="authored", rate=24, actor=TOOL,
                              frames=[value] * frames, camera="cam", depth=depth, unknown=unknown)
        colour = np.array([0.8, 0.3 + 0.2 * index, 0.2, 1.0], np.float32)
        inputs[f"p{index}"] = np.repeat((alpha[..., None] * colour)[None], frames, 0)
        nodes[f"z{index}"] = {"op": "signal.read", "signal": f"z{index}", "kind": "depth", "camera": "cam"}
    labels = ((cols // 64 + rows // 64) % 4).astype(np.int32)
    signals.record_signal(root, signal_id="labels", kind="segmentation", origin="authored", rate=24, actor=TOOL,
                          frames=[labels] * frames, labels={i: str(i) for i in range(4)}, labels_are="classes")
    nodes.update({
        "alpha": {"op": "signal.channel", "picture": "p0", "channel": "alpha"},
        "m0": {"op": "matte.from_signal", "signal": "alpha"},
        "whole": {"op": "signal.object_depth", "signal": "z0", "matte": "m0", "camera": "cam"},
        "merged": {"op": "merge.depth", "pictures": ["p0", "p1", "p2"], "depths": ["whole", "z1", "z2"],
                   "unknown": "behind"},
        "s": {"op": "signal.read", "signal": "labels", "kind": "segmentation"},
        "chosen": {"op": "matte.label", "signal": "s", "labels": [1, 3]},
        "tint": {"op": "generate.solid", "colour": [0.2, 0.2, 0.9, 1]},
        "out": {"op": "merge.over", "front": "tint", "back": "merged", "matte": "chosen", "mix": 0.3}})
    graph = {"ports": {f"p{i}": "picture" for i in range(3)}, "output": "out", "nodes": nodes}
    return root, graph, inputs


def main(argv: list[str]) -> None:
    width, height, frames = (int(argv[0]), int(argv[1]), int(argv[2])) if len(argv) >= 3 else (1920, 1080, 12)
    root, graph, inputs = scene(width, height, frames)
    size = (width, height)
    started = time.perf_counter()
    made = reference.evaluate(graph, inputs, frames=frames, size=size, fps=24, root=root)
    reference_s = (time.perf_counter() - started) / frames
    renderer = renderer_for(graph)
    renderer.evaluate(graph, inputs, frames=1, size=size, fps=24, root=root)  # programs compiled, pools filled
    import cine_toaster.compositing.reference as shared

    reading = {"s": 0.0}
    original = shared.read_signal

    def timed(*args, **kwargs):
        begun = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            reading["s"] += time.perf_counter() - begun

    shared.read_signal = timed
    started = time.perf_counter()
    drawn = renderer.evaluate(graph, inputs, frames=frames, size=size, fps=24, root=root)
    gl_s = (time.perf_counter() - started) / frames
    shared.read_signal = original
    stats = renderer.stats
    per = lambda key: stats.get(f"{key}_s", 0.0) / frames * 1000  # noqa: E731
    print(f"{renderer.name} at {width}x{height}, {frames} frames")
    print(f"reference           {reference_s * 1000:8.1f} ms a frame")
    print(f"GL                  {gl_s * 1000:8.1f} ms a frame ({reference_s / gl_s:.1f}x)")
    print(f"  reading records   {reading['s'] / frames * 1000:8.1f} ms (CPU)")
    print(f"  uploads           {per('upload'):8.1f} ms ({stats.get('upload', 0) / frames:.0f})")
    print(f"  draws, submitted  {per('draw'):8.1f} ms ({stats.get('draw', 0) / frames:.0f})")
    print(f"  downloads         {per('download'):8.1f} ms ({stats.get('download', 0) / frames:.0f}, waiting on the GPU)")
    rest = gl_s * 1000 - reading["s"] / frames * 1000 - per("upload") - per("draw") - per("download")
    print(f"  the rest          {rest:8.1f} ms")
    print(f"largest difference  {float(np.abs(drawn - made).max()):.2e}")


if __name__ == "__main__":
    main(sys.argv[1:])
