"""A version's cut as OpenTimelineIO (CT-0096): the cut as the assembly made it, read back by OpenTimelineIO."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from heavy import needs  # noqa: E402

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


@needs("opentimelineio")
class Writing(unittest.TestCase):
    """The adapter alone: the transitions' arithmetic, without an assembly."""

    def test_transitions_trim_their_handles_and_the_timeline_keeps_the_cuts_length(self) -> None:
        import opentimelineio as otio

        from cine_toaster.otio_export import write

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a.mp4", "b.mp4", "v1.mp4"):
                (root / name).write_bytes(b"")
            items = [
                {"shot": "P1", "take": "A", "kind": "take", "file": str(root / "a.mp4"), "source_in": 1.0,
                 "frames": 48, "overlap_in": 0, "transition": None},
                # 12 frames of transition into P2: 6 before the cut from P2's head, 6 after from P1's tail.
                {"shot": "P2", "take": "B", "kind": "take", "file": str(root / "b.mp4"), "source_in": 0.5,
                 "frames": 60, "overlap_in": 12, "transition": {"id": "dip-to-black", "seconds": 0.5}},
                {"shot": "P3", "take": "", "kind": "solid", "file": "", "source_in": 0.0, "frames": 24,
                 "overlap_in": 0, "transition": None, "colour": "black"},
            ]
            path = write(items, root=root, name="SC-1 v1", fps=24, size=(160, 90), version_file=root / "v1.mp4",
                         stems={}, output=root / "v1.otio")
            timeline = otio.adapters.read_from_file(str(path))
        cut = timeline.tracks[0]
        clips = [item for item in cut if isinstance(item, otio.schema.Clip)]
        transition = next(item for item in cut if isinstance(item, otio.schema.Transition))
        self.assertEqual(len(clips), 3)
        self.assertEqual((transition.in_offset.value, transition.out_offset.value), (6, 6))
        # P1 loses its last 6 frames to the transition, P2 its first 6; the timeline is the cut's 48 + 60 - 12 + 24.
        self.assertEqual(clips[0].source_range.duration.value, 42)
        self.assertEqual(clips[0].source_range.start_time.value, 24)  # 1 s into its take
        self.assertEqual(clips[1].source_range.start_time.value, 12 + 6)  # 0.5 s, and its head handle
        self.assertEqual(clips[1].source_range.duration.value, 54)
        self.assertEqual(cut.duration().value, 48 + 60 - 12 + 24)
        self.assertIsInstance(clips[2].media_reference, otio.schema.GeneratorReference)
        self.assertEqual(clips[1].metadata["cine_toaster"]["file"], "b.mp4")
        self.assertFalse(timeline.tracks[1].enabled)  # the version, to conform against


@needs("opentimelineio")
@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is missing")
class FromAnAssembly(unittest.TestCase):
    """A scene assembled with --otio, adopted, its .otio read back: the cut's shots, its transition, a shot drawn
    by its graph kept beside the version, and the length of the version itself."""

    def test_the_versions_cut_reads_back_as_it_was_made(self) -> None:
        import opentimelineio as otio

        from cine_toaster.commands import Actor, select_take
        from cine_toaster.jobs import JobManager, JobStore
        from cine_toaster.project import load_scene

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "film"
            shutil.copytree(DEMO, root)
            scene_file = root / "scenes" / "030-echo-chamber" / "scene.yaml"
            text = scene_file.read_text(encoding="utf-8")
            text = text.replace("  - n: 2\n", "  - n: 2\n    transition: {id: dip-to-black, duration_ms: 500}\n", 1)
            text = text.replace("  - n: 1\n", "  - n: 1\n    title: {id: card, text: THE REPLY}\n", 1)
            scene_file.write_text(text, encoding="utf-8")
            select_take(root, scene_id="SC-030", shot_id="P3", take_id="ONE-BLINK", actor=Actor(id="editor"))
            manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
            self.addCleanup(manager.shutdown, wait=False)
            job = manager.wait(manager.submit("assemble", root, {"scene": "SC-030", "otio": True})["id"], timeout=300)
            self.assertEqual(job["state"], "succeeded", job["error"])
            manager.adopt(job["id"])
            folder = root / "scenes" / "030-echo-chamber" / "versions"
            timeline = otio.adapters.read_from_file(str(folder / "v1.otio"))
            plan = job["result"]["summary"]["segments"]
            frames = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                                         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0",
                                         str(folder / "v1.mp4")], capture_output=True, text=True).stdout.strip())
            cut = timeline.tracks[0]
            clips = [item for item in cut if isinstance(item, otio.schema.Clip)]
            self.assertEqual([clip.metadata["cine_toaster"]["shot"] for clip in clips],
                             [segment["shot"] for segment in plan])
            self.assertEqual(sum(isinstance(item, otio.schema.Transition) for item in cut), 1)
            self.assertEqual(cut.duration().value, frames)  # the version's own length, frame for frame
            # Every file it points at is there; the drawn shot (P1, a card) beside the version.
            for track in timeline.tracks:
                for clip in track.find_clips():
                    reference = clip.media_reference
                    if isinstance(reference, otio.schema.ExternalReference):
                        self.assertTrue(Path(otio.url_utils.filepath_from_url(reference.target_url)).is_file(),
                                        reference.target_url)
            drawn = next(clip for clip in clips if clip.metadata["cine_toaster"]["shot"] == "P1")
            self.assertEqual(drawn.metadata["cine_toaster"]["kind"], "drawn")
            self.assertIn("v1.media", drawn.media_reference.target_url)
            take = next(clip for clip in clips if clip.metadata["cine_toaster"]["shot"] == "P3")
            self.assertEqual(take.metadata["cine_toaster"]["take"], "ONE-BLINK")
            self.assertEqual([track.kind for track in timeline.tracks][-1], otio.schema.TrackKind.Audio)
            del load_scene


if __name__ == "__main__":
    unittest.main()
