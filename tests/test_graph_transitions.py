"""Transitions as recipes of SPEC-0012 primitives (ADR 0022), drawn by the reference."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import Plan, Segment, _resolve_join, probe, render
from cine_toaster.transitions import TransitionFormatError, list_transitions

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


class CatalogTests(unittest.TestCase):
    def test_the_displace_wipe_is_a_checked_recipe_with_its_pictures_and_preview(self) -> None:
        item = {entry["id"]: entry for entry in list_transitions()}["displace-wipe"]
        self.assertEqual((item["kind"], item["category"]), ("graph", "wipe/custom"))
        self.assertEqual(sorted(item["inputs"]), ["map_picture", "order_picture"])
        self.assertTrue(item["preview_path"].is_file())
        self.assertEqual(item["graph"]["output"], "out")

    def test_a_recipe_that_is_not_a_valid_graph_is_refused_when_the_catalog_loads(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw) / "transitions" / "broken"
            folder.mkdir(parents=True)
            (folder / "transition.toml").write_text(
                'id = "broken"\nname = "Broken"\nkind = "graph"\ndescription = "x"\nlicense = "MIT"\n'
                '[graph]\nports = {from = "picture", to = "picture", progress = "curve"}\noutput = "out"\n'
                '[graph.nodes]\nout = {op = "matte.threshold", matte = "from", progress = "progress"}\n')
            with self.assertRaisesRegex(TransitionFormatError, "not valid"):
                list_transitions(Path(raw))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class AssemblyTests(unittest.TestCase):
    def test_a_displace_wipe_join_is_drawn_in_the_version_with_both_pictures_playing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, colour in (("a.mp4", "red"), ("b.mp4", "blue")):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"color={colour}:s=160x90:r=24:d=4", "-f", "lavfi", "-i", "anullsrc", "-shortest",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(root / name)], check=True)
            catalog = {item["id"]: item for item in list_transitions()}
            plan = Plan(scene="S", segments=[Segment("P1", "A", "a.mp4", 0.0, 4.0, normalize=False)])
            incoming = Segment("P2", "B", "b.mp4", 0.0, 4.0, normalize=False)
            _resolve_join(root, plan, {"transition": {"id": "displace-wipe", "duration_ms": 2000}}, incoming,
                          {"catalog": catalog, "gl": None})
            self.assertIn("graph", incoming.transition)
            plan.segments.append(incoming)
            out = root / "cut.mp4"
            render(root, plan, out, root / "work", run)
            self.assertAlmostEqual(probe(out)["duration"], 6.0, delta=0.1)
            frames = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-f", "rawvideo", "-pix_fmt",
                                     "rgb24", "-"], capture_output=True).stdout
            import numpy as np

            pictures = np.frombuffer(frames, np.uint8).reshape(-1, 90, 160, 3)
            middle = pictures[72]  # the middle of the join
            self.assertGreater(middle[45, 80, 2], 200)  # the centre already shows the incoming picture
            self.assertGreater(middle[4, 4, 0], 200)    # a corner still the outgoing one
            self.assertGreater(pictures[20, 45, 80, 0], 200)
            self.assertGreater(pictures[130, 4, 4, 2], 200)


if __name__ == "__main__":
    unittest.main()


class SurfaceTests(unittest.TestCase):
    """warp.surface: the playing picture on a 3D object (the warp wipe, as the Toaster did it)."""

    def picture(self, value: float) -> "np.ndarray":
        import numpy as np

        out = np.zeros((36, 64, 4), np.float32)
        out[..., 0] = np.linspace(0, 1, 64)[None] * value  # a ramp, so its place on the surface can be read
        out[..., 3] = 1.0
        return out

    def run_surface(self, **params) -> tuple:
        import numpy as np

        from cine_toaster.compositing.warp import surface

        defaults = {"shape": "sphere", "morph": 1.0, "rotate": [0, 0, 0], "translate": [0, 0, 0], "scale": 1.0,
                    "perspective": 35.0, "light": 0.0, "detail": 32, "supersample": 2, "aspect": 64 / 36}
        return surface(self.picture(1.0), **{**defaults, **params})

    def test_flat_is_the_picture_and_a_ball_covers_less_and_has_depth(self) -> None:
        import numpy as np

        flat, flat_depth = self.run_surface(morph=0.0)
        self.assertGreater(float(flat[..., 3].mean()), 0.97)
        ball, depth = self.run_surface(morph=1.0)
        covered = ball[..., 3] > 0.5
        self.assertLess(float(covered.mean()), 0.6)
        self.assertTrue(np.isfinite(depth[covered]).all())
        self.assertTrue(np.isinf(depth[~(ball[..., 3] > 0.01)]).all())

    def test_a_turned_ball_shows_another_part_of_the_picture_and_flying_away_shrinks_it(self) -> None:
        front, _ = self.run_surface()
        turned, _ = self.run_surface(rotate=[0, 90, 0])
        self.assertGreater(abs(float(front[18, 32, 0]) - float(turned[18, 32, 0])), 0.1)
        far, _ = self.run_surface(translate=[0, 0, 2.0])
        self.assertLess(float(far[..., 3].sum()), 0.5 * float(front[..., 3].sum()))

    def test_every_warp_wipe_starts_on_the_outgoing_picture_and_ends_on_the_incoming_one(self) -> None:
        import numpy as np

        from cine_toaster.compositing.reference import evaluate

        catalog = {item["id"]: item for item in list_transitions()}
        a, b = self.picture(1.0), np.zeros((36, 64, 4), np.float32)
        b[..., 2] = b[..., 3] = 1.0
        for name in ("warp-ball", "warp-roll", "page-turn"):
            with self.subTest(recipe=name):
                out = evaluate(catalog[name]["graph"], {"from": a, "to": b}, frames=12, size=(64, 36), fps=12)
                self.assertGreater(float(out[0, ..., 3].mean()), 0.99)
                self.assertLess(float(np.abs(out[0, 18, 10:54, 0] - a[18, 10:54, 0]).max()), 0.25)
                self.assertGreater(float(out[-1, ..., 2].mean()), 0.97)  # only the incoming picture is left


class SurfaceQualityTests(unittest.TestCase):
    """warp.surface checked in geometry, image and time, and used outside a transition."""

    def frames(self, shape: str, frames: int = 16) -> "np.ndarray":
        import numpy as np

        from cine_toaster.compositing.reference import evaluate

        picture = np.zeros((72, 128, 4), np.float32)
        picture[..., 0] = np.linspace(0.1, 1, 128)[None]
        picture[..., 1] = np.linspace(0.1, 1, 72)[:, None]
        picture[..., 3] = 1.0
        graph = {"ports": {"a": "picture", "progress": "curve"},
                 "nodes": {"spin": {"op": "curve.keys", "in": "progress", "keys": [[0, [0, 0, 0]], [1, [20, 160, 0]]]},
                           "out": {"op": "warp.surface", "in": "a", "shape": shape, "morph": {"curve": "progress"},
                                   "rotate": {"curve": "spin"} if shape != "page" else [0, 0, 0],
                                   "perspective": 35, "light": 0.3}},
                 "output": "out"}
        return evaluate(graph, {"a": picture}, frames=frames, size=(128, 72), fps=16)

    def test_no_tears_in_the_surface(self) -> None:
        import numpy as np

        for shape in ("sphere", "cylinder", "page"):
            with self.subTest(shape=shape):
                for frame in self.frames(shape)[::3]:
                    solid = frame[..., 3] > 0.5
                    rows = [np.flatnonzero(row) for row in solid if row.any()]
                    # Along each covered row the surface is one run, or two where a tube or page shows both
                    # sides; never a scatter of gaps that would be cracks between triangles.
                    for run in rows:
                        gaps = int((np.diff(run) > 1).sum())
                        self.assertLessEqual(gaps, 1)

    def test_it_moves_continuously_from_frame_to_frame(self) -> None:
        import numpy as np

        for shape in ("sphere", "cylinder", "page"):
            with self.subTest(shape=shape):
                frames = self.frames(shape, 24)
                coverage = frames[..., 3].reshape(len(frames), -1).sum(axis=1)
                steps = np.abs(np.diff(coverage)) / coverage.max()
                self.assertLess(float(steps.max()), 0.12)  # no jump of more than an eighth of the area in a frame

    def test_the_same_primitive_works_on_a_single_shot(self) -> None:
        import yaml

        from cine_toaster.compositing.schema import validate

        shot = yaml.safe_load("""
            nodes:
              take: {op: generate.source, take: CUT}
              ball: {op: warp.surface, in: take, shape: sphere, morph: 0.6, rotate: [0, 30, 0], perspective: 35}
              sky:  {op: generate.gradient, kind: linear, colours: [[0, 0, 0.2, 1], [0, 0.1, 0.4, 1]], angle: 90}
              out:  {op: merge.over, front: ball, back: sky}
            output: out
        """)
        self.assertEqual(validate(shot), [])  # a shot's composite, not a join: the same op, no recipe needed
