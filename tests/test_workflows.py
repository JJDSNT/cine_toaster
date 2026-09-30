"""The built-in workflow stops for a person, and moves on from their decision (SPEC-0009)."""

from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from cine_toaster import jobs, spend, workflows
from cine_toaster.commands import dispatch
from cine_toaster.errors import ValidationError
from cine_toaster.jobs import JobManager, JobStore
from cine_toaster.project import load_production, load_scene, scene_directory
from cine_toaster.state import load_scene_state

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"
HAS_FFMPEG = shutil.which("ffmpeg") is not None

try:
    from PIL import Image
except ImportError:
    Image = None


def clip(path: Path, colours: list[tuple[str, int]]) -> bytes:
    inputs = []
    for colour, frames in colours:
        inputs += ["-f", "lavfi", "-i", f"color=c={colour}:s=64x36:r=24:d={frames / 24}"]
    graph = "".join(f"[{index}:v]" for index in range(len(colours))) + f"concat=n={len(colours)}:v=1:a=0[v]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path.read_bytes()


class FakeRunpod:
    """The editor answers with a picture, the video endpoint with a clip."""

    def __init__(self, picture: bytes, video: bytes) -> None:
        self.picture, self.video = picture, video
        self.sent: list[str] = []

    def __call__(self, path: str, body: dict | None) -> dict:
        endpoint = path.split("/")[1]
        if path.endswith("/run"):
            self.sent.append(endpoint)
            return {"id": f"{endpoint}-{len(self.sent)}", "status": "IN_QUEUE"}
        output = ({"image": base64.b64encode(self.picture).decode()} if endpoint == "editor"
                  else {"videos": [base64.b64encode(self.video).decode()]})
        return {"status": "COMPLETED", "delayTime": 500, "executionTime": 2000, "output": output}


@unittest.skipUnless(HAS_FFMPEG and Image is not None, "FFmpeg and Pillow are needed")
class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        keys = ("XDG_CACHE_HOME", "XDG_STATE_HOME", "RUNPOD_QWEN_ENDPOINT_ID", "RUNPOD_LTX_ENDPOINT_ID")
        self.previous = {key: os.environ.get(key) for key in keys}
        os.environ.update(XDG_CACHE_HOME=str(base / "cache"), XDG_STATE_HOME=str(base / "state"),
                          RUNPOD_QWEN_ENDPOINT_ID="editor", RUNPOD_LTX_ENDPOINT_ID="video")
        self.addCleanup(self._restore)
        self.root = base / "film"
        shutil.copytree(DEMO, self.root)
        scene = self.root / "scenes" / "030-echo-chamber"
        (scene / "blockout").mkdir()
        Image.new("RGB", (704, 384), "grey").save(scene / "blockout" / "cam-a.png")
        Image.new("RGB", (1280, 704), "red").save(scene / "work" / "p02.png")
        text = (scene / "scene.yaml").read_text(encoding="utf-8")
        text = text.replace("  - n: 2\n", "  - n: 2\n    block: A\n", 1)
        text = text.replace("  - n: 3\n", "  - n: 3\n    block: A\n    derive:\n      from: blockout/cam-a.png\n"
                            "      with: [MARA]\n      request: The figure becomes the woman in image 2.\n", 1)
        (scene / "scene.yaml").write_text(text, encoding="utf-8")
        buffer = io.BytesIO()
        Image.new("RGB", (1280, 704), "blue").save(buffer, "PNG")
        self.fake = jobs.GENERATION_TRANSPORT = FakeRunpod(buffer.getvalue(),
                                                            clip(base / "made.mp4", [("red", 200), ("blue", 280)]))
        spend.set_limit(2)
        self.manager = JobManager(store=JobStore(base / "state" / "jobs.sqlite"))
        workflows.attach(self.manager)
        self.addCleanup(self.manager.shutdown, wait=False)

    def _restore(self) -> None:
        jobs.GENERATION_TRANSPORT = None
        workflows._RUNTIME["manager"] = None
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def state(self):
        return load_scene_state(scene_directory(self.root, "SC-030"), "SC-030")

    def wait_for(self, predicate, timeout: float = 60.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.state()
            run = next(iter(state.workflows.values()), None)
            if run and predicate(state, run):
                return state, run
            time.sleep(0.1)
        self.fail(f"timed out; run is {run}")

    def waiting_gate(self, state):
        return next(gate for gate in state.gates.values() if gate["state"] == "waiting")

    def test_a_block_is_made_only_after_its_picture_is_approved(self) -> None:
        human = {"id": "director", "kind": "human"}
        dispatch(self.root, "start_workflow", {"scene_id": "SC-030", "block": "A", "actor": human})
        state, run = self.wait_for(lambda state, run: run["state"] == "waiting")
        self.assertEqual([step["id"] for step in run["steps"]], ["picture-P3", "approve-P3", "generate", "slice"])
        gate = self.waiting_gate(state)
        self.assertEqual((gate["kind"], gate["subject"]), ("approve_picture", "P3"))
        self.assertEqual(gate["candidates"], ["scenes/030-echo-chamber/work/p03-1.png"])
        self.assertEqual(self.fake.sent, ["editor"])  # nothing is animated before the gate

        # Asking for another makes a second version and asks again, with both.
        dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": gate["id"], "outcome": "changes_requested",
                                            "actor": human, "rationale": "Her head moved off the render's mark.",
                                            "reasons": ["subject_moved"]})
        state, run = self.wait_for(lambda state, run: run["state"] == "waiting"
                                   and any(g["state"] == "waiting" for g in state.gates.values()))
        second = self.waiting_gate(state)
        self.assertEqual(len(second["candidates"]), 2)
        # What was wrong went into the second edit's instructions, and is kept with it.
        import json as json_module
        made = json_module.loads((self.root / "scenes/030-echo-chamber/work/p03-2.png.provenance.json").read_text())
        self.assertIn("Correction from the director: Her head moved off the render's mark.", made["prompt"])
        self.assertIn("Keep every person exactly where image 1 has them", made["prompt"])
        self.assertEqual(made["feedback"]["text"], "Her head moved off the render's mark.")
        self.assertEqual(self.fake.sent, ["editor", "editor"])

        # A stale decision is refused.
        with self.assertRaises(Exception):
            dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": second["id"], "outcome": "approved",
                                                "chosen": second["candidates"][1], "actor": human,
                                                "expected_revision": state.revision - 1})
        with self.assertRaises(ValidationError):
            dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": second["id"], "outcome": "approved",
                                                "chosen": "somewhere/else.png", "actor": human})

        chosen = second["candidates"][1]
        dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": second["id"], "outcome": "approved",
                                            "chosen": chosen, "actor": human, "rationale": "On her mark."})
        state, run = self.wait_for(lambda state, run: run["state"] in ("done", "failed", "cancelled"))
        self.assertEqual(run["state"], "done", run)
        self.assertEqual(self.fake.sent, ["editor", "editor", "video"])

        # The approval is the shot's picture now: the generation was guided by it.
        scene = load_scene(self.root, "SC-030")
        shot = next(item for item in scene["shots"] if item["id"] == "P3")
        self.assertEqual(shot["approved_picture"], chosen)
        record = scene["blocks"][0]["records"]["scenes/030-echo-chamber/work/bA-1.mp4"]
        self.assertEqual(record["guides"][1]["path"], chosen)
        takes = [take["id"] for take in shot["takes"]]
        self.assertIn("BLOCK-AV1", takes)
        kinds = [item["kind"] for item in state.decisions]
        self.assertEqual(kinds, ["workflow.started", "gate.decided", "gate.decided"])

    def test_a_rejected_picture_ends_the_run_and_nothing_is_animated(self) -> None:
        human = {"id": "director", "kind": "human"}
        dispatch(self.root, "start_workflow", {"scene_id": "SC-030", "block": "A", "actor": human})
        state, _ = self.wait_for(lambda state, run: run["state"] == "waiting")
        gate_id = self.waiting_gate(state)["id"]
        # A refusal has to say what is wrong.
        with self.assertRaisesRegex(ValidationError, "Say what is wrong"):
            dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": gate_id, "outcome": "rejected",
                                                "actor": human})
        with self.assertRaisesRegex(ValidationError, "Unknown reason"):
            dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": gate_id, "outcome": "rejected",
                                                "reasons": ["ugly"], "actor": human})
        dispatch(self.root, "decide_gate", {"scene_id": "SC-030", "gate_id": gate_id, "outcome": "rejected",
                                            "reasons": ["identity"], "actor": human})
        self.assertEqual(self.state().gates[gate_id]["reasons"], ["identity"])
        _, run = self.wait_for(lambda state, run: run["state"] in ("done", "failed", "cancelled"))
        self.assertEqual(run["state"], "cancelled")
        self.assertEqual(self.fake.sent, ["editor"])

    def test_an_existing_picture_goes_straight_to_the_gate(self) -> None:
        Image.new("RGB", (1280, 704), "green").save(self.root / "scenes/030-echo-chamber/work/p03.png")
        dispatch(self.root, "start_workflow", {"scene_id": "SC-030", "block": "A", "actor": "director"})
        state, run = self.wait_for(lambda state, run: run["state"] == "waiting")
        self.assertEqual(run["steps"][0]["state"], "skipped")
        self.assertEqual(self.waiting_gate(state)["candidates"], ["scenes/030-echo-chamber/work/p03.png"])
        self.assertEqual(self.fake.sent, [])
        # One run per block at a time.
        with self.assertRaisesRegex(ValidationError, "already has a workflow"):
            dispatch(self.root, "start_workflow", {"scene_id": "SC-030", "block": "A", "actor": "director"})
        self.assertIsNotNone(load_production(self.root))


if __name__ == "__main__":
    unittest.main()
