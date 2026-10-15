"""Post-C2 convergence (CT-0072): one place for each decision, one path for each operation."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from cine_toaster.compositing import reference, semantics
from cine_toaster.compositing.gl import gl_unavailable_reason

SOURCE = Path(__file__).parents[1] / "src" / "cine_toaster"


def picture() -> np.ndarray:
    rng = np.random.default_rng(4)
    out = np.dstack([rng.uniform(0.1, 0.9, (36, 64, 3)).astype(np.float32), np.ones((36, 64), np.float32)])
    return out


SURFACE = {"ports": {"a": "picture"}, "nodes": {"out": {"op": "warp.surface", "in": "a", "shape": "sphere"}},
           "output": "out"}


class DecisionTests(unittest.TestCase):
    def test_defaults_and_derived_values_are_written_once(self) -> None:
        # Neither renderer, nor the matte recipe, holds its own copy of what semantics decides.
        for path in (SOURCE / "compositing" / "reference.py", SOURCE / "compositing" / "gl.py", SOURCE / "mattes.py"):
            text = path.read_text()
            with self.subTest(module=path.name):
                self.assertNotIn("0.002", text)
                self.assertIsNone(re.search(r"radius\s*/\s*2\.0", text))
                for key in ("perspective", "light", "detail", "supersample"):
                    self.assertIsNone(re.search(rf'p(aram)?\("{key}",\s*[0-9]', text), key)

    def test_the_eases_are_one_vocabulary(self) -> None:
        """What an ease may be is decided once (CT-0074): the reference's eases are exactly the names the
        validator accepts, and the beat curve's envelope has no defaults of its own."""

        self.assertEqual(tuple(reference._EASES), semantics.EASE_NAMES)
        text = (SOURCE / "compositing" / "reference.py").read_text()
        self.assertIsNone(re.search(r'node\.get\("(attack|decay)",\s*[0-9]', text))

    def test_a_length_in_pixels_means_the_same_at_every_size(self) -> None:
        """Lengths are pixels at 720 lines, scaled to the frame (CT-0075): a still or a preview drawn small looks
        like the cut drawn large."""

        edge = {"ports": {"a": "picture"}, "nodes": {"out": {"op": "filter.blur", "in": "a", "radius": 24}},
                "output": "out"}
        profiles = []
        for width, height in ((128, 72), (512, 288)):
            picture = np.zeros((height, width, 4), np.float32)
            picture[:, : width // 2] = 1.0
            row = reference.evaluate(edge, {"a": picture}, frames=1, size=(width, height), fps=12)[0, height // 2, :, 0]
            profiles.append(np.interp(np.linspace(0, 1, 64), np.linspace(0, 1, width), row))
        self.assertLess(float(np.abs(profiles[0] - profiles[1]).max()), 0.05)

    def test_the_reference_reads_a_default_from_semantics(self) -> None:
        options = {"frames": 1, "size": (64, 36), "fps": 12}
        before = reference.evaluate(SURFACE, {"a": picture()}, **options)
        with mock.patch.dict(semantics.DEFAULTS["warp.surface"], {"perspective": 80.0}):
            after = reference.evaluate(SURFACE, {"a": picture()}, **options)
        self.assertGreater(float(np.abs(before - after).mean()), 1e-3)

    @unittest.skipIf(gl_unavailable_reason(), "no GL context here")
    def test_both_renderers_follow_the_same_default_when_it_changes(self) -> None:
        from cine_toaster.compositing.gl import GLRenderer

        gl = GLRenderer()
        try:
            options = {"frames": 1, "size": (64, 36), "fps": 12}
            with mock.patch.dict(semantics.DEFAULTS["warp.surface"], {"perspective": 80.0, "light": 0.0}):
                drawn = gl.evaluate(SURFACE, {"a": picture()}, **options)
                expected = reference.evaluate(SURFACE, {"a": picture()}, **options)
            self.assertLess(float(np.abs(drawn - expected).mean()), 0.02)
        finally:
            gl.release()



class ConformTests(unittest.TestCase):
    def test_a_picture_of_another_shape_is_fitted_never_stretched_and_transparent_around(self) -> None:
        import shutil
        import subprocess
        import tempfile

        if not shutil.which("ffmpeg"):
            self.skipTest("FFmpeg is missing")
        with tempfile.TemporaryDirectory() as raw:
            square = Path(raw) / "square.png"  # 4:3 into a 16:9 frame
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=white:s=120x90",
                            "-frames:v", "1", str(square)], check=True)
            picture = reference.read(square, 1, (160, 90), 12)[0]
            self.assertLess(float(picture[45, 5, 3]), 0.01)    # the sides are transparent
            self.assertGreater(float(picture[45, 80, 3]), 0.99)  # the picture is there, whole
            self.assertAlmostEqual(float((picture[45, :, 3] > 0.5).sum()), 120, delta=2)  # 120 wide: not stretched


DISSOLVE = """vec4 transition(vec2 uv) {
  return mix(getFromColor(uv), getToColor(uv), progress);
}
"""


@unittest.skipIf(gl_unavailable_reason(), "no GL context here")
class OpaqueShaderTests(unittest.TestCase):
    def test_a_gl_transitions_shader_runs_in_the_gl_renderer_in_the_display_encoding(self) -> None:
        """One GL pipeline (B1): the shader is a node of the graph, mixing pictures as it was written to --
        in the display encoding -- and its picture comes back linear like every other node's."""

        import tempfile

        from cine_toaster.assembly import shader_recipe
        from cine_toaster.compositing.gl import renderer_for

        with tempfile.TemporaryDirectory() as raw:
            shader = Path(raw) / "dissolve.glsl"
            shader.write_text(DISSOLVE)
            graph = shader_recipe({"shader": str(shader)})
            black = np.zeros((36, 64, 4), np.float32)
            black[..., 3] = 1.0
            white = np.ones((36, 64, 4), np.float32)
            frames = 3
            renderer = renderer_for(graph)
            self.assertIsNotNone(renderer)
            drawn = np.stack(list(renderer.evaluate(graph, {"from": black, "to": white}, frames=frames,
                                                    size=(64, 36), fps=24, stream=True)))
        # The progress at each frame's centre, as every curve of the graph is read; half-way in the display
        # encoding is about 0.21 linear, where a linear mix would be 0.5.
        for frame in range(frames):
            expected = float(reference.decode_srgb(np.float32((frame + 0.5) / frames)))
            self.assertAlmostEqual(float(drawn[frame, ..., :3].mean()), expected, delta=0.01, msg=frame)
        # Not flipped: a picture with a bright top keeps its top.
        top = black.copy()
        top[:18, :, :3] = 1.0
        with tempfile.TemporaryDirectory() as raw:
            shader = Path(raw) / "dissolve.glsl"
            shader.write_text(DISSOLVE)
            graph = shader_recipe({"shader": str(shader)})
            first = next(iter(renderer_for(graph).evaluate(graph, {"from": top, "to": top}, frames=frames,
                                                           size=(64, 36), fps=24, stream=True)))
        self.assertGreater(float(first[:18, :, :3].mean()), 0.9)
        self.assertLess(float(first[18:, :, :3].mean()), 0.1)


class OnePathTests(unittest.TestCase):
    def test_the_quick_build_and_its_shader_pipeline_are_gone(self) -> None:
        """R1-R3: a third way of making pictures and joins, removed; nothing may bring it back by name."""

        self.assertFalse((SOURCE / "build.py").exists())
        self.assertFalse((SOURCE / "shader_render.py").exists())
        from cine_toaster.jobs import KINDS

        self.assertNotIn("build", KINDS)

    def test_toast_build_is_refused_by_the_cli(self) -> None:
        import contextlib
        import io

        from cine_toaster.cli import main

        with contextlib.redirect_stderr(io.StringIO()) as said, self.assertRaises(SystemExit) as stopped:
            main(["build", "."])
        self.assertNotEqual(stopped.exception.code, 0)
        self.assertIn("invalid choice: 'build'", said.getvalue())

    def test_the_browser_holds_no_copy_of_the_matte_rule(self) -> None:
        """B4: the Transitions room plays a clip the graph drew; it does not threshold a matte itself."""

        script = (SOURCE / "web_assets" / "app.js").read_text()
        self.assertNotIn("MATTE_SHADER", script)
        self.assertNotIn("sampleMatte", script)
        from cine_toaster.transitions import list_transitions

        item = next(item for item in list_transitions() if item["id"] == "matte-wipe")
        self.assertTrue(item["preview_path"] and item["preview_path"].is_file())

    def test_a_matte_preview_is_drawn_by_the_matte_joins_graph(self) -> None:
        import shutil
        import tempfile

        from cine_toaster import transitions

        if not shutil.which("ffmpeg"):
            self.skipTest("FFmpeg is missing")
        drawn = []
        real = reference.render

        def spy(graph, *args, **kwargs):
            drawn.append(graph)
            return real(graph, *args, **kwargs)

        from cine_toaster.mattes import recipe

        with tempfile.TemporaryDirectory() as raw, mock.patch.object(reference, "render", spy):
            out = transitions.render_preview({"id": "matte-wipe", "kind": "matte"}, Path(raw) / "p.webm",
                                             seconds=0.25, size=(64, 36))
            self.assertGreater(out.stat().st_size, 0)
        self.assertEqual(drawn, [recipe(False)])


if __name__ == "__main__":
    unittest.main()
