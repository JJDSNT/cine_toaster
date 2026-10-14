"""Joins shaped by a picture, and pictures riding them (SPEC-0011)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster.assembly import Plan, Segment, probe, render
from cine_toaster.shader_render import gl_unavailable_reason
from cine_toaster.transitions import list_transitions

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def run(command, expected_seconds=None, message="", span=None):
    subprocess.run(command, check=True, capture_output=True)


def ffmpeg(*arguments: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *arguments], check=True)


class CatalogTests(unittest.TestCase):
    def test_luma_displacement_and_the_matte_wipe_are_in_the_catalog_with_their_pictures(self) -> None:
        catalog = {item["id"]: item for item in list_transitions()}
        self.assertEqual({name: path.name for name, path in catalog["luma"]["inputs"].items()}, {"luma": "radial.png"})
        self.assertEqual(list(catalog["displacement"]["inputs"]), ["displacementMap"])
        self.assertEqual((catalog["matte-wipe"]["kind"], catalog["matte-wipe"]["asset_path"]), ("matte", None))
        self.assertTrue(all(path.is_file() for item in catalog.values() for path in item["inputs"].values()))


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class MatteJoinTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        # A brightens over its 4 s and B darkens: each frame says what time it is, so a frozen side would show.
        for name, colour in (("a.mp4", "red"), ("b.mp4", "blue")):
            ffmpeg("-f", "lavfi", "-i", f"color={colour}:s=160x90:r=24:d=4", "-f", "lavfi", "-i", "anullsrc",
                   "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(self.root / name))

    def cut(self, transition: dict) -> tuple[Plan, Path]:
        plan = Plan(scene="S", segments=[Segment("P1", "A", "a.mp4", 0.0, 4.0, normalize=False),
                                         Segment("P2", "B", "b.mp4", 0.0, 4.0, normalize=False, transition=transition)])
        out = self.root / "cut.mp4"
        render(self.root, plan, out, self.root / "work", run)
        return plan, out

    def pixel(self, path: Path, at: float, x: int, y: int = 45) -> tuple[int, int, int]:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(at), "-i", str(path), "-frames:v", "1",
                              "-vf", f"crop=4:4:{x}:{y - 2},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True).stdout
        return raw[0], raw[1], raw[2]

    def test_a_still_matte_is_an_order_left_changes_before_right(self) -> None:
        ffmpeg("-f", "lavfi", "-i", "nullsrc=s=160x90,geq=lum='X/W*255':cb=128:cr=128", "-frames:v", "1",
               str(self.root / "ramp.png"))
        plan, out = self.cut({"id": "matte-wipe", "seconds": 2.0, "matte": str(self.root / "ramp.png"),
                              "softness": 0.05})
        self.assertAlmostEqual(probe(out)["duration"], 6.0, delta=0.1)
        left, right = self.pixel(out, 3.0, 8), self.pixel(out, 3.0, 148)  # the middle of the join
        self.assertGreater(left[2], 200)   # the dark end of the matte has already changed: blue
        self.assertGreater(right[0], 200)  # the bright end has not: still red
        self.assertGreater(self.pixel(out, 1.0, 80)[0], 200)
        self.assertGreater(self.pixel(out, 5.0, 80)[2], 200)

    def test_a_moving_matte_is_the_shape_and_one_that_stops_short_is_completed_and_said(self) -> None:
        # A white bar grows from the left to half the frame: it never reaches white everywhere.
        ffmpeg("-f", "lavfi", "-i", "color=black:s=160x90:r=24:d=2,geq=lum='255*lt(X,W*T/4)':cb=128:cr=128",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self.root / "bar.mp4"))
        plan, out = self.cut({"id": "matte-wipe", "seconds": 2.0, "matte": str(self.root / "bar.mp4")})
        self.assertGreater(self.pixel(out, 3.2, 8)[2], 200)    # inside the bar: blue
        self.assertGreater(self.pixel(out, 3.2, 150)[0], 200)  # beyond it: red
        self.assertGreater(self.pixel(out, 4.2, 150)[2], 200)  # after the join: blue everywhere
        self.assertTrue(any("does not end white" in note for note in plan.notes), plan.notes)

    def test_an_overlay_rides_the_join_and_one_without_transparency_is_refused(self) -> None:
        # A green square, opaque, on nothing: transparent everywhere else.
        ffmpeg("-f", "lavfi", "-i", "color=black:s=160x90,format=rgba,"
               "geq=r=0:g=255:b=0:a='255*between(X,60,100)*between(Y,30,60)'", "-frames:v", "1",
               str(self.root / "badge.png"))
        plan, out = self.cut({"id": "cross-dissolve", "seconds": 2.0, "mode": "fade",
                              "overlay": str(self.root / "badge.png"), "blend": "normal"})
        self.assertGreater(self.pixel(out, 3.0, 80)[1], 100)  # the badge, in the middle of the join
        self.assertLess(self.pixel(out, 1.0, 80)[1], 60)      # and not before it
        ffmpeg("-f", "lavfi", "-i", "color=green:s=160x90", "-frames:v", "1", str(self.root / "flat.jpg"))
        plan, _ = self.cut({"id": "cross-dissolve", "seconds": 2.0, "mode": "fade",
                            "overlay": str(self.root / "flat.jpg")})
        self.assertTrue(any("no transparency" in note for note in plan.notes), plan.notes)

    def luma_by(self, gl: str | None) -> Path:
        """The same `luma` join, resolved as on a machine with GL (None) or without it (a reason)."""

        from cine_toaster.assembly import _resolve_join

        catalog = {item["id"]: item for item in list_transitions()}
        plan = Plan(scene="S", segments=[Segment("P1", "A", "a.mp4", 0.0, 4.0, normalize=False)])
        second = Segment("P2", "B", "b.mp4", 0.0, 4.0, normalize=False)
        _resolve_join(self.root, plan, {"transition": {"id": "luma", "duration_ms": 2000}}, second,
                      {"catalog": catalog, "gl": gl})
        plan.segments.append(second)
        out = self.root / f"luma-{'ffmpeg' if gl else 'gl'}.mp4"
        render(self.root, plan, out, self.root / f"work-{bool(gl)}", run)
        return out

    def test_without_gl_luma_is_drawn_by_the_matte_renderer(self) -> None:
        out = self.luma_by("no GL in this test")
        self.assertGreater(self.pixel(out, 3.0, 80)[2], 200)   # the radial order: centre first
        self.assertGreater(self.pixel(out, 3.0, 4, 4)[0], 200)

    @unittest.skipIf(gl_unavailable_reason(), "no GL context here")
    def test_the_shader_and_the_matte_renderer_give_the_same_luma_join(self) -> None:
        shader, stand_in = self.luma_by(None), self.luma_by("no GL in this test")
        for x, y in ((80, 45), (40, 20), (4, 4), (150, 80)):
            a, b = self.pixel(shader, 3.0, x, y), self.pixel(stand_in, 3.0, x, y)
            self.assertLess(max(abs(p - q) for p, q in zip(a, b)), 24, (x, y, a, b))

    @unittest.skipIf(gl_unavailable_reason(), "no GL context here")
    def test_luma_reads_its_texture(self) -> None:
        item = next(item for item in list_transitions() if item["id"] == "luma")
        plan, out = self.cut({"id": "luma", "seconds": 2.0, "shader": str(item["asset_path"]), "params": [],
                              "textures": {"luma": str(item["inputs"]["luma"])}})
        centre, corner = self.pixel(out, 3.0, 80), self.pixel(out, 3.0, 4, 4)
        self.assertGreater(centre[2], 200)  # the radial order changes the centre first
        self.assertGreater(corner[0], 200)



class CheckTests(unittest.TestCase):
    def test_a_join_names_pictures_that_are_in_the_production(self) -> None:
        from cine_toaster.project import load_production

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "film"
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: S1\nshots:\n  - {n: 1, duration: 2}\n  - n: 2\n    duration: 2\n"
                "    transition: {id: matte-wipe, matte: mattes/ink.mp4, overlay: ../outside.png, reason: a test}\n")
            codes = sorted(f["code"] for f in load_production(root)["scenes"][0]["findings"]
                           if f["code"].startswith("transition_input"))
            self.assertEqual(codes, ["transition_input_missing", "transition_input_outside"])

if __name__ == "__main__":
    unittest.main()
