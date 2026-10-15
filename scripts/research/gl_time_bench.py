"""CT-0080 step 6: time and track graphs drawn by the reference and by GL, timed, at 1280x720.

    PYTHONPATH=src python scripts/research/gl_time_bench.py <folder>

Four graphs over a 3 s numbered source: a 2x remap with blending; a moving layer with trails; a picture pinned
by a track with a clock; all of them together with an offset and a ramp. Each is drawn by the reference and,
when GL holds every op, by GL; both times, and the largest difference between them, are printed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from cine_toaster.compositing.gl import renderer_for
from cine_toaster.compositing.reference import evaluate

W, H, FPS, FRAMES = 1280, 720, 24, 48


def source(count: int = 120) -> np.ndarray:
    rng = np.random.default_rng(1)
    base = rng.random((H // 8, W // 8, 3)).astype(np.float32)
    frames = np.zeros((count, H, W, 4), np.float32)
    for index in range(count):
        frames[index, ..., :3] = np.kron(np.roll(base, index, axis=1), np.ones((8, 8, 1), np.float32)) * 0.8
        frames[index, ..., 0] += index / 400
        frames[index, ..., 3] = 1.0
    return frames


def graphs(track: Path) -> dict[str, dict]:
    ramp = {"op": "curve.keys", "keys": [[0, 0], [1, 1], [2, 3]]}
    moving = {"op": "curve.keys", "keys": [[0, [-0.4, 0]], [2, [0.4, 0]]]}
    return {
        "remap 2x blend": {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "m": {"op": "curve.keys", "keys": [[0, 0], [10, 20]]},
            "out": {"op": "time.remap", "in": "plate", "map": {"curve": "m"}, "interpolation": "blend"}}},
        "trails": {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "move": moving,
            "small": {"op": "warp.transform", "in": "plate", "scale": 0.2, "translate": {"curve": "move"}},
            "trail": {"op": "time.echo", "in": "small", "count": 4, "spacing": 2, "decay": 0.6},
            "black": {"op": "generate.solid", "colour": [0, 0, 0, 1]},
            "out": {"op": "merge.over", "front": "trail", "back": "black"}}},
        "pin by track": {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "t": {"op": "track.read", "file": str(track), "of": "plate"},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "pinned": {"op": "warp.corner_pin", "in": "white", "track": "t"},
            "out": {"op": "merge.over", "front": "pinned", "back": "plate"}}},
        "all together": {"ports": {"plate": "picture"}, "output": "out", "nodes": {
            "r": ramp, "move": moving,
            "fast": {"op": "time.remap", "in": "plate", "map": {"curve": "r"}, "interpolation": "blend"},
            "late": {"op": "time.offset", "in": "fast", "frames": 2},
            "t": {"op": "track.read", "file": str(track), "of": "plate"},
            "white": {"op": "generate.solid", "colour": [1, 1, 1, 1]},
            "pinned": {"op": "warp.corner_pin", "in": "white", "track": "t"},
            "small": {"op": "warp.transform", "in": "pinned", "scale": 0.3, "translate": {"curve": "move"}},
            "trail": {"op": "time.echo", "in": "small", "count": 3, "spacing": 1, "decay": 0.5},
            "out": {"op": "merge.over", "front": "trail", "back": "late"}}},
    }


def main() -> None:
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    track = folder / "plane.track.json"
    track.write_text(json.dumps({"kind": "plane", "clock": {"rate": "24", "origin": {"ticks": 0}}, "frames": [
        {"corners": [[0.3 + i / 400, 0.3], [0.6 + i / 400, 0.32], [0.62 + i / 400, 0.7], [0.28 + i / 400, 0.68]],
         "confidence": 1.0} for i in range(120)]}))
    plate = source()
    for name, graph in graphs(track).items():
        started = time.time()
        exact = evaluate(graph, {"plate": plate}, frames=FRAMES, size=(W, H), fps=FPS)
        reference_seconds = time.time() - started
        fast = renderer_for(graph)
        if fast is None:
            print(f"{name:16s} reference {reference_seconds:6.2f} s ({reference_seconds / FRAMES * 1000:6.1f} ms/frame) | GL: "
                  "falls back to the reference", flush=True)
            continue
        started = time.time()
        drawn = np.stack(list(fast.evaluate(graph, {"plate": plate}, frames=FRAMES, size=(W, H), fps=FPS, stream=True)))
        gl_seconds = time.time() - started
        print(f"{name:16s} reference {reference_seconds:6.2f} s ({reference_seconds / FRAMES * 1000:6.1f} ms/frame) | GL "
              f"{gl_seconds:6.2f} s ({gl_seconds / FRAMES * 1000:6.1f} ms/frame), {reference_seconds / gl_seconds:5.1f}x; "
              f"largest difference {float(np.abs(exact - drawn).max()):.5f}", flush=True)


if __name__ == "__main__":
    main()
