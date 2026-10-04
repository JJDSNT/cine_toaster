"""A block is generated from the production's records, within a budget, as a new version (CT-0037)."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cine_toaster import jobs, spend
from cine_toaster.errors import ValidationError
from cine_toaster.generation import estimate, plan_block
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.project import load_production, load_scene


def clip(path: Path, colours: list[tuple[str, int]]) -> Path:
    """A 24 fps clip of solid colours, each for a number of frames, with sound."""

    inputs = []
    for colour, frames in colours:
        inputs += ["-f", "lavfi", "-i", f"color=c={colour}:s=64x36:r=24:d={frames / 24}"]
    total = sum(frames for _, frames in colours) / 24
    graph = "".join(f"[{index}:v]" for index in range(len(colours))) + f"concat=n={len(colours)}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={total}",
                    "-filter_complex", graph, "-map", "[v]", "-map", f"{len(colours)}:a", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None


class FakeRunpod:
    """Queues, runs, and returns a small video; remembers what it was sent."""

    def __init__(self, video: bytes, *, fail: bool = False) -> None:
        self.video = video
        self.fail = fail
        self.calls: list[tuple[str, dict | None]] = []
        self.polls = 0

    def __call__(self, path: str, body: dict | None) -> dict:
        self.calls.append((path, body))
        if path.endswith("/run"):
            return {"id": "remote-1", "status": "IN_QUEUE"}
        if "/cancel/" in path:
            return {"status": "CANCELLED"}
        self.polls += 1
        if self.polls == 1:
            return {"status": "IN_PROGRESS", "delayTime": 2000}
        if self.fail:
            return {"status": "FAILED", "delayTime": 2000, "executionTime": 30000, "error": "out of memory"}
        return {"status": "COMPLETED", "delayTime": 2000, "executionTime": 120000,
                "output": {"videos": [base64.b64encode(self.video).decode()]}}


@unittest.skipUnless(HAS_FFMPEG, "FFmpeg is missing")
class GenerateBlockTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME", "RUNPOD_LTX_ENDPOINT_ID")}
        os.environ["RUNPOD_LTX_ENDPOINT_ID"] = "test-endpoint"
        os.environ["XDG_CACHE_HOME"] = str(base / "cache")
        os.environ["XDG_STATE_HOME"] = str(base / "state")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        text = scene.read_text(encoding="utf-8")
        text = text.replace("  - n: 2\n", "  - n: 2\n    block: A\n    picture: A woman at a console in a dark room\n", 1)
        text = text.replace("  - n: 3\n", "  - n: 3\n    block: A\n    lines: {who: MARA, text: That's it, delivery: says quietly}\n"
                            "    sound: a low electrical hum\n", 1)
        scene.write_text(text, encoding="utf-8")
        self.work = self.root / "scenes" / "030-echo-chamber" / "work"
        for number, colour in (("02", "red"), ("03", "blue")):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=64x36",
                            "-frames:v", "1", str(self.work / f"p{number}.png")], check=True)
        (self.work / "bA.mp4").write_bytes((self.work / "c02.mp4").read_bytes())
        # What the model returns: its own cut at frame 200, near the 216 asked for.
        self.video = clip(base / "made.mp4", [("red", 200), ("blue", 280)]).read_bytes()
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        jobs.GENERATION_TRANSPORT = None
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def plan(self):
        return plan_block(self.root, load_production(self.root), "SC-030", "A")

    def test_the_plan_is_built_from_the_records(self) -> None:
        plan = self.plan()
        self.assertEqual((plan.shots, plan.seconds), (["P2", "P3"], 20))
        self.assertEqual([(ref.role, ref.frame, ref.path.name) for ref in plan.guides],
                         [("first", 0, "p02.png"), ("P3", 216, "p03.png")])
        self.assertTrue(plan.prompt.startswith("A woman at a console in a dark room."))
        self.assertIn("A hard cut transitions to a new shot", plan.prompt)
        # Mara's identity comes from her cast sheet; how she sounds, from the scene.
        self.assertIn("soft Scottish accent; now barely above a whisper", plan.prompt)
        self.assertIn('Mara says quietly, in a low', plan.prompt)
        self.assertIn('"That\'s it."', plan.prompt)
        self.assertIn("A hard cut transitions to a new shot.", plan.prompt)
        self.assertIn("P3 has no picture description", plan.notes[0])
        self.assertIn("Sound: a low electrical hum", plan.prompt)
        self.assertEqual(plan.estimate_usd, estimate(20))
        # The prompt by shot, for a person to read; joined, the prompt itself.
        self.assertEqual([section["shot"] for section in plan.sections], ["P2", "P3", ""])
        self.assertEqual(" ".join(section["text"] for section in plan.sections), plan.prompt)

    def test_a_shot_can_ask_for_no_guide_or_a_softer_one(self) -> None:
        scene = self.root / "scenes" / "030-echo-chamber" / "scene.yaml"
        scene.write_text(scene.read_text(encoding="utf-8").replace(
            "    block: A\n    lines:", "    block: A\n    guide_strength: 0.4\n    lines:", 1), encoding="utf-8")
        self.assertEqual([(ref.role, ref.strength) for ref in self.plan().guides], [("first", 0.7), ("P3", 0.4)])
        scene.write_text(scene.read_text(encoding="utf-8").replace(
            "guide_strength: 0.4", "guide_at_cut: false"), encoding="utf-8")
        plan = self.plan()
        self.assertEqual([ref.role for ref in plan.guides], ["first"])
        self.assertIn("P3 asks for no guide at its cut", plan.notes[-1])

    def test_a_shot_outside_any_block_becomes_a_take_of_its_own(self) -> None:
        from cine_toaster.generation import plan_shot

        with self.assertRaisesRegex(ValidationError, "part of block A"):
            plan_shot(self.root, load_production(self.root), "SC-030", "P2")
        (self.work / "p01.png").write_bytes((self.work / "p02.png").read_bytes())
        plan = plan_shot(self.root, load_production(self.root), "SC-030", "P1")
        self.assertEqual((plan.shots, plan.seconds, len(plan.guides)), (["P1"], 6, 1))
        jobs.GENERATION_TRANSPORT = FakeRunpod(self.video)
        spend.set_limit(2)
        job = self.manager.wait(self.manager.submit("generate_block", self.root, {"scene": "SC-030", "shot": "P1"})["id"], timeout=60)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])
        shot = next(item for item in load_scene(self.root, "SC-030")["shots"] if item["id"] == "P1")
        take = next(item for item in shot["takes"] if item["id"] == "GEN")
        self.assertEqual(take["provenance"]["kind"], "shot-generation")
        self.assertTrue(take["media"].endswith("work/_takes/c01-gen.mp4"))

    def test_nothing_is_generated_without_a_budget(self) -> None:
        jobs.GENERATION_TRANSPORT = FakeRunpod(self.video)
        with self.assertRaises(spend.BudgetExceeded):
            self.manager.submit("generate_block", self.root, {"scene": "SC-030", "block": "A"})
        spend.set_limit(0.01)
        with self.assertRaises(spend.BudgetExceeded):
            self.manager.submit("generate_block", self.root, {"scene": "SC-030", "block": "A"})
        self.assertEqual(jobs.GENERATION_TRANSPORT.calls, [])

    def test_a_generation_becomes_a_new_version_with_its_lineage(self) -> None:
        fake = jobs.GENERATION_TRANSPORT = FakeRunpod(self.video)
        spend.set_limit(2)
        job = self.manager.wait(self.manager.submit("generate_block", self.root, {"scene": "SC-030", "block": "A", "seed": 7})["id"], timeout=60)
        self.assertEqual(job["state"], "succeeded", job["error"])
        self.manager.adopt(job["id"])
        # The production's own clip is untouched; the generation is b<id>-1.
        block = load_scene(self.root, "SC-030")["blocks"][0]
        self.assertTrue(block["clip"].endswith("work/bA.mp4"))
        self.assertEqual([path.rsplit("/", 1)[-1] for path in block["versions"]], ["bA.mp4", "bA-1.mp4"])
        provenance = json.loads((self.work / "bA-1.mp4.provenance.json").read_text())
        self.assertEqual((provenance["seed"], provenance["shots"], provenance["guides"][1]["frame"]), (7, ["P2", "P3"], 216))
        self.assertEqual(len(provenance["guides"][0]["digest"]), 16)
        self.assertTrue((self.work / "bA-1.mp4.job.json").is_file())
        # The provider's own execution id, the key billing is reconciled with (CT-0058).
        self.assertEqual({key: provenance["execution"][key] for key in ("provider", "id", "execution_ms")},
                         {"provider": "runpod", "id": "remote-1", "execution_ms": 120000})
        sent = fake.calls[0][1]["input"]
        self.assertEqual([image["name"] for image in sent["images"]], ["frame.png", "guide0.png", "guide1.png"])
        # What the platform billed is in the ledger.
        self.assertAlmostEqual(spend.spent(), 122 * 1.75 / 3600, places=4)

    def test_a_failed_generation_still_records_what_it_cost(self) -> None:
        jobs.GENERATION_TRANSPORT = FakeRunpod(self.video, fail=True)
        spend.set_limit(2)
        job = self.manager.wait(self.manager.submit("generate_block", self.root, {"scene": "SC-030", "block": "A"})["id"], timeout=60)
        self.assertEqual(job["state"], "failed")
        self.assertAlmostEqual(spend.spent(), 32 * 1.75 / 3600, places=4)
        self.assertEqual(spend.load()["entries"][0]["status"], "FAILED")

    def test_a_retry_after_the_runtime_died_waits_for_the_remote_job_instead_of_paying_again(self) -> None:
        class DiesWhileWaiting(FakeRunpod):
            def __call__(self, path, body):
                if body is None and not getattr(self, "died", False):
                    self.died = True
                    self.calls.append((path, body))
                    raise RuntimeError("the runtime died while waiting")
                return super().__call__(path, body)

        fake = jobs.GENERATION_TRANSPORT = DiesWhileWaiting(self.video)
        spend.set_limit(2)
        first = self.manager.wait(self.manager.submit("generate_block", self.root, {"scene": "SC-030", "block": "A"})["id"], timeout=60)
        self.assertEqual(first["state"], "failed")
        remote = Path(os.environ["XDG_STATE_HOME"]) / "cine-toaster" / "remote"
        self.assertEqual(len(list(remote.glob("generate_block-*.job.json"))), 1)  # kept for the retry
        again = self.manager.wait(self.manager.retry(first["id"])["id"], timeout=60)
        self.assertEqual(again["state"], "succeeded", again["error"])
        runs = [path for path, _ in fake.calls if path.endswith("/run")]
        self.assertEqual(len(runs), 1)  # sent once, paid once
        self.assertEqual(len(spend.load()["entries"]), 1)
        self.assertAlmostEqual(spend.spent(), 122 * 1.75 / 3600, places=4)
        # Adopted, the request is free again: asking once more really asks.
        self.manager.adopt(again["id"])
        self.assertEqual(list(remote.glob("*.json")), [])

    def test_a_chosen_version_can_be_sliced(self) -> None:
        jobs.GENERATION_TRANSPORT = FakeRunpod(self.video)
        spend.set_limit(2)
        job = self.manager.wait(self.manager.submit("generate_block", self.root, {"scene": "SC-030", "block": "A"})["id"], timeout=60)
        self.manager.adopt(job["id"])
        submitted = self.manager.submit("slice_block", self.root, {"scene": "SC-030", "block": "A", "clip": "bA-1.mp4"})
        self.assertEqual(submitted["params"]["clip"], "scenes/030-echo-chamber/work/bA-1.mp4")
        sliced = self.manager.wait(submitted["id"], timeout=120)
        self.assertEqual(sliced["state"], "succeeded", sliced["error"])
        self.assertTrue(all(item["take"].startswith("BLOCK-AV1") for item in sliced["result"]["summary"]["slices"]))
        # The block's record travels with the version and with each slice of it.
        self.manager.adopt(sliced["id"])
        scene = load_scene(self.root, "SC-030")
        record = scene["blocks"][0]["records"]["scenes/030-echo-chamber/work/bA-1.mp4"]
        self.assertEqual((record["kind"], record["job"]["id"]), ("block-generation", "remote-1"))
        self.assertEqual(scene["blocks"][0]["records"]["scenes/030-echo-chamber/work/bA.mp4"], {})
        take = next(item for item in scene["shots"][1]["takes"] if item["id"].startswith("BLOCK-AV1"))
        self.assertEqual(take["provenance"]["block_generation"]["prompt"], record["prompt"])

    def test_the_control_room_sees_the_plan_before_paying(self) -> None:
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer

        from cine_toaster.index import ProjectIndex, build_index
        from cine_toaster.web import ProjectBrowserHandler

        server = ThreadingHTTPServer(("127.0.0.1", 0), ProjectBrowserHandler)
        build_index(self.root)
        server.project_index = ProjectIndex(self.root)
        server.project_root = self.root.resolve()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(5)))
        base = f"http://127.0.0.1:{server.server_address[1]}/api/generation-plan"
        spend.set_limit(2)
        with urllib.request.urlopen(f"{base}?scene=SC-030&block=A", timeout=30) as response:
            plan = json.loads(response.read())
        self.assertEqual((plan["seconds"], plan["limit_usd"], plan["spent_usd"]), (20, 2.0, 0.0))
        self.assertTrue(plan["image"].endswith("work/p02.png"))
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{base}?scene=SC-030&block=Z", timeout=30)
        self.assertEqual(caught.exception.code, 422)
        self.assertIn("no block", json.loads(caught.exception.read())["error"]["message"])


if __name__ == "__main__":
    unittest.main()
