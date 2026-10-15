"""CT-0081 step 8: C8's done-when film -- a Blender object behind a person in a generated picture, by depth.

    PYTHONPATH=src python scripts/research/c8_film.py <production> setup     # the records, the render, the scene
    PYTHONPATH=src python scripts/research/c8_film.py <production> measure   # the delivered version, judged

The picture: SINGULAR's take 1-02B c09 (LTX), Kael in a hospital corridor, copied read-only into the production
as `plates/kael-corredor-c09.mp4` (nothing of SINGULAR is run). Its first 3 s:

- Video Depth Anything Small estimates its depth (input 392); SAM 2 follows Kael from a box round him and a
  point on his face;
- nothing in it was measured, so a calibration is *stated* (`corridor-reference`, authored): his face 1.0 m,
  the far door 8.5 m, from a 50 mm lens assumed; the estimate is aligned to it (`corridor-z`);
- Blender renders an orb crossing 2 m from the camera at his temple's height, its camera stated to be the
  shot's (`camera_id: shot-cam`);
- the scene's shot is three layers: the plate by its depth, Kael cut out with one depth, the orb by its own.

`measure` decodes the assembled version and checks the claim: where the orb is behind Kael its pixels are the
plate's (to the encoding's noise), where it is not they are the orb's; and GL draws the shot as the reference.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

TAKE = Path.home() / "films/singular/scenes/1-02B-kael-no-corredor/work/c09.mp4"
PLATE = "plates/kael-corredor-c09.mp4"
ORB = {"objects": [
    {"name": "orb", "type": "sphere", "radius": 0.09, "location": [-0.9, 2.0, 0.105], "colour": [0.55, 0.62, 0.68],
     "keys": [{"frame": 1, "location": [-0.9, 2.0, 0.105]}, {"frame": 72, "location": [0.9, 2.0, 0.105]}]}],
    "camera": {"name": "cam", "lens": 50, "sensor_width": 36,
               "keys": [{"frame": 1, "location": [0, 0, 0], "rotation": [90, 0, 0]},
                        {"frame": 72, "location": [0, 0, 0], "rotation": [90, 0, 0]}]}}
SCENE = """scene: SC-010
order: 10
title: Corredor
summary: CT-0081's done-when film -- a Blender object behind a person in a generated picture, ordered by depth.
shots:
  - n: 1
    duration: 3
    label: Kael in the corridor; an orb crosses behind his head, before the corridor.
    layers:
      - source: plates/kael-corredor-c09.mp4
        depth: {signal: corridor-z, camera: shot-cam, estimated: true}
      - source: plates/kael-corredor-c09.mp4
        cut: {signal: kael-person, labels: [1]}
        depth: {signal: corridor-z, camera: shot-cam, estimated: true, object: true}
      - render: orb
        depth: {render: true, camera: shot-cam}
"""


def _grown(mask: np.ndarray, pixels: int) -> np.ndarray:
    grown = mask.copy()
    for _ in range(pixels):
        step = grown.copy()
        step[1:] |= grown[:-1]
        step[:-1] |= grown[1:]
        step[:, 1:] |= grown[:, :-1]
        step[:, :-1] |= grown[:, 1:]
        grown = step
    return grown


def setup(root: Path) -> None:
    import json

    from cine_toaster import align, estimates, renders, signals
    from cine_toaster.state import Actor

    actor = Actor(id="claude", kind="agent")
    (root / "plates").mkdir(parents=True, exist_ok=True)
    (root / "scenes" / "010-corredor").mkdir(parents=True, exist_ok=True)
    if not (root / "project.yaml").is_file():
        (root / "project.yaml").write_text("id: c8-corridor\ntitle: C8 -- an object behind a person in a generated "
                                           "picture\npaths:\n  scenes: scenes\n")
    if not (root / PLATE).is_file():
        shutil.copyfile(TAKE, root / PLATE)  # read-only: a copy
    present = lambda name: (root / "signals" / name / "signal.yaml").is_file()  # noqa: E731
    if not present("kael-person"):
        estimates.estimate(root, signal_id="kael-person", model="sam2.1-hiera-tiny", media=PLATE, actor=actor, first=0,
                           count=72, objects=[{"name": "kael", "frame": 0, "box": [390, 20, 1160, 704],
                                               "points": [[775, 300]], "point_labels": [1]}])
    if not present("kael-vda"):
        estimates.estimate(root, signal_id="kael-vda", model="video-depth-anything-small", media=PLATE, actor=actor,
                           first=0, count=72, parameters={"input_size": 392})
    if True:  # the stated calibration and the alignment are cheap: made again every time, from the records above
        person = signals.SignalReader(root, "kael-person")
        frames = []
        for index in range(72):
            face = person.frame(index) == 1
            face &= np.indices(face.shape)[0] < 430  # his head, above the shoulders
            face = ~_grown(~face, 8)
            stated = np.full(face.shape, np.inf, np.float32)
            stated[face] = 1.0
            stated[350:550, 430:600] = 8.5
            frames.append(stated)
        signals.record_signal(root, signal_id="corridor-reference", kind="depth", origin="authored", rate=24,
                              actor=actor, frames=frames, media=PLATE, camera="shot-cam",
                              depth={"quantity": "z", "unit": "m", "near_is_small": True, "empty": "inf"},
                              maker={"kind": "person", "name": "claude (agent)",
                                     "how": "stated, not measured: his face 1.0 m (a head ~16 cm wide at ~290 px of "
                                            "1280, a 50 mm lens on a 36 mm sensor assumed); the far door 8.5 m "
                                            "(~1 m wide at ~210 px); nothing else stated (+inf)",
                                     "uncertainty": "the lens is assumed: every distance scales with it"},
                              inputs=[{"signal": "kael-person"}])
        align.align_depth(root, signal_id="corridor-z", estimate="kael-vda", reference="corridor-reference",
                          camera="shot-cam", actor=actor)
    if not (root / "renders" / "passes" / "orb" / "render.json").is_file():
        (root / "scenes" / "orb.json").write_text(json.dumps(ORB, indent=1))
        renders.render_passes(root, render_id="orb", camera="cam", first=1, last=72, size=(1280, 704), fps=24,
                              recipe="scenes/orb.json", samples=32, camera_id="shot-cam", actor=actor)
    (root / "scenes" / "010-corredor" / "scene.yaml").write_text(SCENE)


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=1280:704", "-frames:v", "72",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 704, 1280, 3).astype(np.float32) / 255


def measure(root: Path) -> None:
    from cine_toaster import renders
    from cine_toaster.compositing import reference
    from cine_toaster.compositing.gl import renderer_for
    from cine_toaster.project import load_production
    from cine_toaster.signals import SignalReader

    versions = sorted((root / "scenes" / "010-corredor" / "versions").glob("v*.mp4"),
                      key=lambda path: int(path.stem[1:]))
    video, plate = decode(versions[-1]), decode(root / PLATE)
    orb, person = renders.RenderReader(root, "orb"), SignalReader(root, "kael-person")
    behind, shown, away, frames = [], [], [], 0
    for index in range(72):
        orb_there = orb.picture(index)[..., 3] > 0.5
        kael = person.frame(index) == 1
        difference = np.abs(video[index] - plate[index]).mean(-1)
        away.append(float(difference[~_grown(orb_there, 4)].mean()))
        hidden, seen = orb_there & ~_grown(~kael, 3), orb_there & ~_grown(kael, 3)
        if hidden.any():
            behind.append(float(difference[hidden].mean()))
            frames += 1
        if seen.any():
            shown.append(float(difference[seen].mean()))
    print(f"{versions[-1].name}: the orb behind Kael on {frames} frames")
    print(f"  difference from the plate where the orb is behind him {np.mean(behind):.4f}, where it shows "
          f"{np.mean(shown):.4f}, away from it (the encoding) {np.mean(away):.4f}")
    graph = load_production(root)["scenes"][0]["shots"][0]["composite"]
    made = reference.evaluate(graph, {}, frames=72, size=(1280, 704), fps=24, root=root)
    drawn = renderer_for(graph).evaluate(graph, {}, frames=72, size=(1280, 704), fps=24, root=root)
    print(f"  GL against the reference: largest difference {float(np.abs(made - drawn).max()):.1e}")


if __name__ == "__main__":
    production = Path(sys.argv[1]).expanduser()
    {"setup": setup, "measure": measure}[sys.argv[2]](production)
