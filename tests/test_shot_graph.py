"""A shot drawn once (CT-0078): its picture, effects and title as one graph, written once as the cut's piece."""

from __future__ import annotations

import sys
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cine_toaster.compositing.reference import evaluate
from cine_toaster.compositing.schema import validate
from cine_toaster.compositing.shot import chain, shot_graph

sys.path.insert(0, str(Path(__file__).parent))
from heavy import needs  # noqa: E402

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

BLUE = {"ports": {}, "nodes": {"sky": {"op": "generate.solid", "colour": [0, 0, 1, 1]}}, "output": "sky"}
#: A fragment as effects and titles are: a port `picture`, nodes that may share names with the base's, a curve.
HALF = {"ports": {"picture": "picture"}, "output": "sky",
        "nodes": {"t": {"op": "curve.keys", "keys": [[0.0, 0.5], [1.0, 0.5]]},
                  "c": {"op": "curve.keys", "keys": [[0.0, [1, 0, 0, 1]], [1.0, [1, 0, 0, 1]]]},
                  "red": {"op": "generate.solid", "colour": {"curve": "c"}},
                  "sky": {"op": "merge.mix", "a": "picture", "b": "red", "by": "t"}}}


class ChainTests(unittest.TestCase):
    def test_a_fragment_reads_the_picture_so_far_and_keeps_its_own_names(self) -> None:
        graph = chain(BLUE, HALF, "fx-")
        self.assertEqual(validate(graph), [])
        self.assertEqual(graph["ports"], {})  # its `picture` is the base's output now
        self.assertEqual(graph["nodes"]["fx-sky"]["a"], "sky")  # the base's sky, not its own
        self.assertEqual(graph["nodes"]["fx-sky"]["by"], "fx-t")
        self.assertEqual(graph["nodes"]["fx-red"]["colour"], {"curve": "fx-c"})  # a parameter's curve too
        frame = evaluate(graph, {}, frames=1, size=(8, 8), fps=24)[0]
        np.testing.assert_allclose(frame[0, 0], [0.5, 0, 0.5, 1], atol=1e-6)

    def test_fragments_follow_each_other_in_order(self) -> None:
        graph = shot_graph(BLUE, [("fx-", HALF), ("title-", HALF)])
        self.assertEqual(validate(graph), [])
        self.assertEqual(graph["nodes"]["title-sky"]["a"], "fx-sky")
        frame = evaluate(graph, {}, frames=1, size=(8, 8), fps=24)[0]
        np.testing.assert_allclose(frame[0, 0], [0.75, 0, 0.25, 1], atol=1e-6)

    def test_without_a_base_the_picture_stays_a_port(self) -> None:
        graph = shot_graph(None, [("fx-", HALF)])
        self.assertEqual(graph["ports"], {"picture": "picture"})


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class CutTests(unittest.TestCase):
    def test_a_take_with_effects_and_a_title_is_drawn_once_and_not_encoded_again(self) -> None:
        from cine_toaster.assembly import _starts, plan_scene, render, still
        from cine_toaster.project import load_scene

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            shutil.copytree(DEMO, root)
            scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
            scene_file.write_text(scene_file.read_text(encoding="utf-8").replace(
                "  - n: 2\n", "  - n: 2\n    effects: [{id: vignette}]\n    title: {id: caption, text: \"03:13\"}\n",
                1), encoding="utf-8")
            scene = load_scene(root, "SC-030")
            plan = plan_scene(root, scene)
            written: list[str] = []
            messages: list[str] = []

            def run(command, expected_seconds=None, message="", span=None):
                written.append(str(command[-1]))
                messages.append(message)
                subprocess.run(command, check=True, capture_output=True)

            work = Path(directory) / "work"
            render(root, plan, Path(directory) / "cut.mp4", work, run)
            index = [segment.shot for segment in plan.segments].index("P2")
            self.assertTrue(any(note.startswith("P2: drawn in one graph") for note in plan.notes), plan.notes)
            # No pass of its own: no composite, effects or title file, and the piece is not cut again.
            for name in written:
                self.assertNotRegex(Path(name).name, r"^(composite-|title-)|\.fx\.mp4$")
            self.assertNotIn("Cutting P2", messages)
            self.assertNotIn(str(work / f"picture-{index:03d}.mp4"), written)
            # Its still is the frame the cut shows, title and vignette included, and not the bare take.
            drawn = still(root, plan_scene(root, scene), "P2", Path(directory) / "p2.png", 0.3)
            at = round((_starts(plan)[index] + 0.3) * plan_fps(plan, root))
            cut = frame_of(Path(directory) / "cut.mp4", at)
            mine = png(drawn)
            self.assertLess(float(np.abs(mine - cut).mean()), 3 / 255)
            corner, centre = mine[:20, :20].mean(), mine[mine.shape[0] // 3: 2 * mine.shape[0] // 3,
                                                          mine.shape[1] // 3: 2 * mine.shape[1] // 3].mean()
            self.assertLess(corner, centre)  # the vignette darkens the edges


class OpenFxStagingTests(unittest.TestCase):
    """An OpenFX plugin is a node of the shot's graph: Natron is run over what feeds it, before the rest."""

    def graph(self) -> dict:
        return {"ports": {"picture": "picture"}, "output": "tint",
                "nodes": {"grey": {"op": "colour.grade", "in": "picture", "gain": [0.5, 0.5, 0.5]},
                          "lens": {"op": "opaque.natron", "in": "grey", "plugin": "a.lens", "params": {"k1": 0.3}},
                          "blur": {"op": "opaque.natron", "in": "lens", "plugin": "b.blur", "params": {}},
                          "tint": {"op": "colour.grade", "in": "blur", "gain": [1.0, 0.0, 0.0]}}}

    def test_adjacent_plugins_are_one_natron_run_in_order_over_what_feeds_them(self) -> None:
        from unittest import mock

        from cine_toaster.compositing import natron

        calls = []

        def fake(plugins, pictures, *, frames, size, fps):
            calls.append([step["plugin"] for step in plugins])
            return np.stack([np.asarray(picture) for picture in pictures]) + np.array([0, 0.25, 0, 0], np.float32)

        white = np.ones((4, 8, 8, 4), np.float32)
        with mock.patch.object(natron, "run", side_effect=fake):
            from cine_toaster.compositing.reference import render

            pictures, _, _ = render(self.graph(), {"picture": white}, frames=4, size=(8, 8), fps=24, cache=False)
            frames = np.stack(list(pictures))
        self.assertEqual(calls, [["a.lens", "b.blur"]])  # one run, in the written order
        # grey (0.5), then Natron's +0.25 green, then the tint keeps red: what feeds Natron is drawn first.
        np.testing.assert_allclose(frames[0, 0, 0], [0.5, 0.0, 0.0, 1.0], atol=1e-5)

    def test_it_is_validated_as_any_graph(self) -> None:
        self.assertEqual(validate(self.graph()), [])


def _natron() -> str:
    from cine_toaster.vfx import natron_binary

    return natron_binary() or ""


@unittest.skipUnless(HAS_FFMPEG and _natron(), "Natron (the OpenFX host) is not installed")
@needs("OpenEXR")
class NatronTests(unittest.TestCase):
    def test_frames_go_to_natron_and_back_unchanged(self) -> None:
        """Float OpenEXR both ways: an empty chain returns the picture to half-float precision, light above
        white included -- nothing is encoded on the way."""

        from cine_toaster.compositing import natron

        rng = np.random.default_rng(3)
        pictures = rng.random((3, 18, 32, 4), dtype=np.float32)
        pictures[..., :3] *= pictures[..., 3:] * 3.0  # premultiplied, above white
        out = natron.run([], iter(pictures), frames=3, size=(32, 18), fps=24)
        back = np.stack([out[index] for index in range(3)])
        np.testing.assert_allclose(back, pictures, atol=4e-3)
        self.assertGreater(float(back.max()), 1.5)

    def test_a_cut_draws_a_shot_with_openfx_in_one_graph(self) -> None:
        from cine_toaster.assembly import plan_scene, render
        from cine_toaster.project import load_scene

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "film"
            shutil.copytree(DEMO, root)
            scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
            scene_file.write_text(scene_file.read_text(encoding="utf-8").replace(
                "  - n: 2\n", "  - n: 2\n    effects: [{id: ofx-lens-distortion, k1: 0.3}, {id: vignette}]\n", 1),
                encoding="utf-8")
            plan = plan_scene(root, load_scene(root, "SC-030"))
            written: list[str] = []

            def run(command, expected_seconds=None, message="", span=None):
                written.append(Path(str(command[-1])).name)
                subprocess.run(command, check=True, capture_output=True)

            render(root, plan, Path(directory) / "cut.mp4", Path(directory) / "work", run)
            self.assertTrue(any(note.startswith("P2: drawn in one graph") for note in plan.notes), plan.notes)
            self.assertFalse([name for name in written if "treated" in name or name.endswith(".fx.mp4")])


def plan_fps(plan, root: Path) -> float:
    from cine_toaster.assembly import _source_frame

    return _source_frame(root, plan)[1]


def png(path: Path) -> np.ndarray:
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


def frame_of(path: Path, number: int) -> np.ndarray:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    width, height = (int(v) for v in probe.strip().split(","))
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, height, width, 3)[number].astype(np.float32) / 255.0


if __name__ == "__main__":
    unittest.main()
