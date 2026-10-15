"""CT-0080 step 7: C7's three done-when films, made in the music-piece demo production.

    PYTHONPATH=src python scripts/research/c7_films.py <production> setup     # scenes, the moving plate, its track
    PYTHONPATH=src python scripts/research/c7_films.py <production> measure   # check each film against its claim

1. SC-060 Ramp -- the launch, 1x until the music's third beat, ramping to 2x and landing on the fifth.
2. SC-070 Trails -- a launch flown across the Earth, trails behind it as it moves.
3. SC-080 Window -- Orion's cabin under a camera move (the real footage of SC-040, moved by a known
   homography: a synthetic move, so the truth is known), its windows replaced by the Earth, pinned by a plane
   track measured on the moving plate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

RAMP = """scene: SC-060
order: 60
title: Ramp
sequence: The Piece
summary: C7 (CT-0080) -- a speed ramp landing on a beat. The launch runs at 1x to the music's third beat, ramps,
  and lands at 2x on the fifth.
music:
  id: circuit-synthwave
  level: -14
  fade_in: 0
  fade_out: 0.5
  duck: 0
shots:
  - n: 1
    duration: 3.4
    label: The launch, speeding up onto the beat.
    layers:
      - source: scenes/010-orbit/work/c02.mp4
    retime:
      speed:
        - {t: 0, speed: 1, ease: hold}
        - {beat: 3, speed: 1}
        - {beat: 5, speed: 2, ease: hold}
"""

TRAILS = """scene: SC-070
order: 70
title: Trails
sequence: The Piece
summary: C7 (CT-0080) -- trails following a moving layer (the ADO's Infinity) -- a launch flown across the Earth.
shots:
  - n: 1
    duration: 4
    label: A launch flown across the Earth, its past behind it.
    layers:
      - source: scenes/030-inset/work/c01.mp4
      - source: scenes/010-orbit/work/c03.mp4
        place:
          scale: 0.26
          translate:
            keys:
              - {t: 0.0, value: [-0.75, 0.35], ease: in-out}
              - {t: 2.0, value: [0.0, -0.25], ease: in-out}
              - [4.0, [0.75, 0.3]]
          rotate:
            keys:
              - {t: 0.0, value: -18, ease: in-out}
              - [4.0, 18]
        echo: {count: 6, spacing: 3, decay: 0.62}
        border: {width: 3, colour: "#f2ead9"}
"""

WINDOW = """scene: SC-080
order: 80
title: Window, moving
sequence: The Piece
summary: C7 (CT-0080) -- a replaced window following a moving camera. The cabin of SC-040 under a camera move
  (synthetic, so its truth is known); its middle display becomes a window on the Earth, pinned by a plane track
  measured on the plate.
shots:
  - n: 1
    source: archival
    duration: 4
    label: Orion's cabin, the camera drifting; the Earth stays in its middle display.
    layers:
      - source: CUT
      - source: scenes/010-orbit/work/c04.mp4
        garbage: {{shape: polygon, feather: 0.003, points: {screen}}}
        pin: {{track: cabin, of: 1, corners: [[0, 0], [1, 0], [1, 1], [0, 1]]}}
"""

#: SC-040's windows, drawn on the fixed camera's frame.
LEFT = [[0.0, 0.205], [0.06, 0.205], [0.15, 0.207], [0.215, 0.21], [0.25, 0.213], [0.255, 0.222],
        [0.20, 0.242], [0.13, 0.268], [0.06, 0.293], [0.0, 0.318]]
RIGHT = [[1.0, 0.205], [0.94, 0.205], [0.85, 0.208], [0.785, 0.21], [0.745, 0.213], [0.742, 0.222],
         [0.80, 0.242], [0.87, 0.268], [0.94, 0.295], [1.0, 0.322]]
#: The middle display's glass, on the fixed camera's frame.
SCREEN = [[0.427, 0.281], [0.571, 0.281], [0.571, 0.504], [0.429, 0.504]]
FPS = Fraction(30000, 1001)
SECONDS = 4.2


def camera(t: float) -> dict:
    """The synthetic camera move at `t` seconds: a drift, a slow turn, a tilt in perspective, a push in."""

    # Kept inside the picture: the zoom covers every edge the drift and turns would open.
    return {"translate": [0.025 * np.sin(1.3 * t), 0.02 * np.sin(0.8 * t) - 0.01 * t / 4.2],
            "rotate": [0.0, 3.0 * np.sin(0.9 * t), 2.5 * np.sin(0.6 * t)], "scale": 1.15 + 0.02 * t / 4.2,
            "perspective": 35.0}


def moved_corners(t: float) -> list[list[float]]:
    from cine_toaster.compositing.warp import transform_corners

    move = camera(t)
    return transform_corners(translate=move["translate"], scale=move["scale"], rotate=move["rotate"], pivot=[0.5, 0.5],
                             perspective=move["perspective"], aspect=16 / 9, skew=0.0)


def truth(t: float, points: list[list[float]]) -> np.ndarray:
    """Where a point of the fixed frame is in the moved plate at `t`."""

    from cine_toaster.compositing.warp import UNIT, homography

    h = homography(UNIT, moved_corners(t))
    p = np.c_[np.asarray(points, np.float64), np.ones(len(points))] @ h.T
    return p[:, :2] / p[:, 2:3]


def setup(root: Path) -> None:
    from cine_toaster import tracks
    from cine_toaster.compositing import reference
    from cine_toaster.state import Actor

    for name, text in (("060-ramp", RAMP), ("070-trails", TRAILS)):
        (root / "scenes" / name).mkdir(parents=True, exist_ok=True)
        (root / "scenes" / name / "scene.yaml").write_text(text)
    # The moving plate: SC-040's real footage under the known move, drawn by the compositing engine.
    work = root / "scenes" / "080-window-moving" / "work"
    work.mkdir(parents=True, exist_ok=True)
    plate = work / "c01.mp4"
    frames = int(round(SECONDS * float(FPS)))
    keys = {name: [] for name in ("translate", "rotate", "scale")}
    for frame in range(frames + 1):
        t = frame / float(FPS)
        move = camera(t)
        for name in keys:
            keys[name].append([round(t, 6), move[name] if not isinstance(move[name], np.ndarray) else list(move[name])])
    graph = {"ports": {}, "output": "out", "nodes": {
        "src": {"op": "generate.source", "file": str(root / "scenes/040-window/work/c01.mp4")},
        **{f"{name}-k": {"op": "curve.keys", "keys": [[t, (list(map(float, v)) if isinstance(v, list) else float(v))]
                                                     for t, v in keys[name]]} for name in keys},
        "out": {"op": "warp.transform", "in": "src", "translate": {"curve": "translate-k"},
                "rotate": {"curve": "rotate-k"}, "scale": {"curve": "scale-k"}, "perspective": 35.0}}}
    from cine_toaster.compositing.gl import renderer_for

    pictures, _, _ = reference.render(graph, {}, frames=frames, size=(1920, 1080), fps=float(FPS),
                                      renderer=renderer_for(graph), cache=False)
    silent = work / "c01.picture.mp4"
    reference.write(pictures, silent, float(FPS))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-c:v", "libx264", "-crf", "14",
                    "-pix_fmt", "yuv420p", str(plate)], check=True)
    silent.unlink()
    (work / "c01.mp4.provenance.json").write_text(json.dumps({"origin": {
        "kind": "derived", "from": "scenes/040-window/work/c01.mp4",
        "how": "a synthetic camera move (scripts/research/c7_films.py: camera()), for C7's moving-window trial",
        "licence": "Public domain (NASA media usage guidelines)", "credit": "NASA"}}, indent=2))
    screen = truth(0.0, SCREEN).round(4).tolist()
    (root / "scenes" / "080-window-moving" / "scene.yaml").write_text(WINDOW.format(screen=screen))
    # The plane track, measured once on the moving plate: a production record.
    done = tracks.measure_track(root, track_id="cabin", media="scenes/080-window-moving/work/c01.mp4", kind="plane",
                                region=[0.25, 0.28, 0.75, 0.52], actor=Actor(id="claude", kind="agent"),
                                rationale="C7 step 7: the moving-window film")
    state = tracks.status(root, "cabin")
    print(f"cabin track: measurement {done['measurement']}, weak {state['weak'] or 'none'}")


def measure(root: Path) -> None:
    from cine_toaster import tracks

    # 3. How well the plane track follows the known move: the windows' corners, tracked against true.
    track = tracks.load_track(root, "cabin")
    first = np.asarray(track["frames"][0]["corners"])
    from cine_toaster.compositing.warp import homography

    errors = []
    for index, entry in enumerate(track["frames"]):
        t = index / float(FPS)
        h = homography(first.tolist(), entry["corners"])
        start = truth(0.0, SCREEN)
        p = np.c_[start, np.ones(len(start))] @ np.asarray(h).T
        tracked = p[:, :2] / p[:, 2:3]
        errors.append(np.abs((tracked - truth(t, SCREEN)) * [1920, 1080]).max())
    errors = np.array(errors)
    edges = np.array([moved_corners(i / float(FPS)) for i in range(len(track["frames"]))])
    covered = bool((edges[:, 0] <= 0).all() and (edges[:, 2] >= 1).all())
    print(f"picture's corners stay outside the frame (no borders): {covered}")
    print(f"display corners, tracked against the true move: mean {errors.mean():.2f} px, worst {errors.max():.2f} px "
          f"(frame {int(errors.argmax())}), over {len(errors)} frames at 1920x1080; "
          f"confidence min {min(e['confidence'] for e in track['frames']):.2f}")


if __name__ == "__main__":
    production = Path(sys.argv[1]).expanduser()
    {"setup": setup, "measure": measure}[sys.argv[2]](production)
