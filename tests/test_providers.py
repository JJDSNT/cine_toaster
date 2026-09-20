from __future__ import annotations

import base64
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from cine_toaster.errors import ValidationError
from cine_toaster.providers import ProviderError, ProviderNotConfigured
from cine_toaster.providers.comfyui import patch_workflow, save_images
from cine_toaster.providers.ltx import (
    CONTROL_RESOLUTION,
    Guide,
    LtxProvider,
    build_request,
    find_video,
)
from cine_toaster.providers.runpod import cost_usd, load_credentials, run_job


class FakeTransport:
    """A provider must be testable without spending money or reaching a network."""

    def __init__(self, statuses: list[dict], *, job_id: str = "job-1") -> None:
        self.statuses = list(statuses)
        self.job_id = job_id
        self.submissions: list[dict] = []
        self.polls = 0

    def __call__(self, path: str, body: dict | None = None) -> dict:
        if path.endswith("/run"):
            self.submissions.append(body or {})
            return {"id": self.job_id, "status": "IN_QUEUE"}
        self.polls += 1
        return self.statuses.pop(0) if self.statuses else {"status": "COMPLETED", "output": {}}


class TemporaryCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def image(self, name: str = "frame.png") -> Path:
        path = self.root / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        return path


class ComfyWorkflowTests(unittest.TestCase):
    def workflow(self) -> dict:
        return {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
            "2": {"class_type": "CLIPTextEncode", "_meta": {"title": "Negative"}, "inputs": {"text": "old"}},
            "3": {"class_type": "KSampler", "inputs": {"seed": 0, "steps": 1, "cfg": 1.0}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 64, "height": 64}},
            "5": {"class_type": "RandomNoise", "inputs": {"noise_seed": 0}},
        }

    def test_overrides_apply_by_node_type_not_by_id(self) -> None:
        patched = patch_workflow(
            self.workflow(), prompt="new", negative="no", seed=7, steps=20, width=128, height=256
        )
        self.assertEqual(patched["1"]["inputs"]["text"], "new")
        self.assertEqual(patched["2"]["inputs"]["text"], "no")
        self.assertEqual(patched["3"]["inputs"]["seed"], 7)
        self.assertEqual(patched["5"]["inputs"]["noise_seed"], 7)
        self.assertEqual(patched["4"]["inputs"]["width"], 128)

    def test_the_original_workflow_is_not_mutated(self) -> None:
        original = self.workflow()
        patch_workflow(original, prompt="new", seed=7)
        self.assertEqual(original["1"]["inputs"]["text"], "old")

    def test_only_the_first_text_node_takes_the_positive_prompt(self) -> None:
        workflow = self.workflow()
        workflow["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "third"}}
        patched = patch_workflow(workflow, prompt="new")
        self.assertEqual(patched["6"]["inputs"]["text"], "third")


class SaveImageTests(TemporaryCase):
    def test_base64_images_are_written_and_s3_references_skipped(self) -> None:
        payload = base64.b64encode(b"bytes").decode()
        saved = save_images(
            [{"data": payload, "filename": "a.png"}, {"type": "s3_url", "data": "https://x"}],
            self.root / "out",
            "tag",
        )
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_bytes(), b"bytes")


class LtxRequestTests(TemporaryCase):
    def test_prompt_whitespace_is_normalised(self) -> None:
        request = build_request(image=self.image(), seconds=5, prompt="a   b\n c", seed=1)
        self.assertEqual(request["workflow"]["398:376"]["inputs"]["value"], "a b c")

    def test_duration_is_bounded(self) -> None:
        for seconds in (0, 21):
            with self.assertRaises(ValidationError):
                build_request(image=self.image(), seconds=seconds, prompt="x", seed=1)

    def test_a_guide_frame_must_be_last_or_a_multiple_of_eight(self) -> None:
        with self.assertRaises(ValidationError):
            Guide(self.image(), 5)
        self.assertEqual(Guide(self.image(), -1).frame, -1)
        self.assertEqual(Guide(self.image(), 16).frame, 16)

    def test_guides_are_wired_into_both_passes_and_cropped(self) -> None:
        request = build_request(
            image=self.image(),
            seconds=5,
            prompt="x",
            seed=1,
            guides=(Guide(self.image("g.png"), -1, 0.7),),
        )
        workflow = request["workflow"]
        self.assertIn("g0:guide1", workflow)
        self.assertIn("g0:guide2", workflow)
        self.assertIn("g:crop1", workflow)
        self.assertIn("g:crop2", workflow)
        # Strength is scaled on the refine pass, as the official template does.
        self.assertEqual(workflow["g0:guide1"]["inputs"]["strength"], 0.7)
        self.assertEqual(workflow["g0:guide2"]["inputs"]["strength"], 1.0)
        self.assertEqual([item["name"] for item in request["images"]], ["frame.png", "guide0.png"])

    def test_a_reference_voice_adds_the_identity_lora_and_the_audio_file(self) -> None:
        voice = self.root / "voice.wav"
        voice.write_bytes(b"RIFF0000WAVE")
        request = build_request(
            image=self.image(), seconds=5, prompt="x", seed=1, reference_voice=voice
        )
        self.assertIn("id:lora", request["workflow"])
        self.assertIn("voice.wav", [item["name"] for item in request["images"]])

    def test_a_control_video_forces_the_resolution_the_lora_requires(self) -> None:
        control = self.root / "control.mp4"
        control.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        request = build_request(
            image=self.image(), seconds=5, prompt="x", seed=1, control_video=(control, 0.7)
        )
        workflow = request["workflow"]
        self.assertEqual(workflow["398:372"]["inputs"]["value"], CONTROL_RESOLUTION[0])
        self.assertEqual(workflow["398:360"]["inputs"]["value"], CONTROL_RESOLUTION[1])
        self.assertIn("ic:guide", workflow)

    def test_control_and_keyframes_share_one_crop(self) -> None:
        control = self.root / "control.mp4"
        control.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        request = build_request(
            image=self.image(),
            seconds=5,
            prompt="x",
            seed=1,
            guides=(Guide(self.image("g.png"), -1),),
            control_video=(control, 0.7),
        )
        self.assertNotIn("ic:crop", request["workflow"])
        self.assertEqual(request["workflow"]["g:crop1"]["inputs"]["positive"], ["ic:guide", 0])

    def test_the_same_seed_produces_the_same_graph(self) -> None:
        first = build_request(image=self.image(), seconds=5, prompt="x", seed=99)
        second = build_request(image=self.image(), seconds=5, prompt="x", seed=99)
        self.assertEqual(first["workflow"], second["workflow"])


class FindVideoTests(unittest.TestCase):
    def video(self) -> str:
        return base64.b64encode(b"\x00\x00\x00\x18ftypmp42" + b"0" * 64).decode()

    def test_a_video_is_recognised_by_its_header_not_its_key(self) -> None:
        self.assertIsNotNone(find_video({"images": [{"data": self.video()}]}))
        self.assertIsNotNone(find_video({"videos": [self.video()]}))
        self.assertIsNotNone(find_video({"output": {"videos": [{"video": self.video()}]}}))

    def test_a_response_without_a_video_returns_nothing(self) -> None:
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
        self.assertIsNone(find_video({"images": [{"data": png}]}))
        self.assertIsNone(find_video({}))


class JobPersistenceTests(TemporaryCase):
    """Generation is slow and paid for, so a lost session must not resubmit."""

    def state_file(self) -> Path:
        return self.root / "clip.mp4.job.json"

    def test_a_completed_job_records_its_state_and_returns_the_output(self) -> None:
        transport = FakeTransport([{"status": "COMPLETED", "output": {"videos": ["x"]}}])
        output = run_job(
            "ep", {"workflow": {}}, state_file=self.state_file(), transport=transport, poll_seconds=0
        )
        self.assertEqual(output, {"videos": ["x"]})
        state = json.loads(self.state_file().read_text())
        self.assertEqual(state["status"], "COMPLETED")
        self.assertEqual(state["id"], "job-1")

    def test_each_submission_gets_its_own_output_prefix(self) -> None:
        transport = FakeTransport([{"status": "COMPLETED", "output": {}}])
        payload = {"workflow": {"1": {"inputs": {"filename_prefix": "clip"}}}}
        run_job("ep", payload, state_file=self.state_file(), transport=transport, poll_seconds=0)
        sent = transport.submissions[0]["input"]["workflow"]["1"]["inputs"]["filename_prefix"]
        self.assertTrue(sent.startswith("clip-"))
        self.assertNotEqual(sent, "clip")
        # The caller's payload is left alone.
        self.assertEqual(payload["workflow"]["1"]["inputs"]["filename_prefix"], "clip")

    def test_resuming_the_same_request_does_not_submit_again(self) -> None:
        payload = {"workflow": {"a": 1}}
        first = FakeTransport([{"status": "COMPLETED", "output": {}}])
        run_job("ep", payload, state_file=self.state_file(), transport=first, poll_seconds=0)

        second = FakeTransport([{"status": "COMPLETED", "output": {"again": True}}])
        run_job("ep", payload, state_file=self.state_file(), transport=second, poll_seconds=0)
        self.assertEqual(second.submissions, [])

    def test_a_different_pending_request_is_refused_rather_than_resent(self) -> None:
        self.state_file().write_text(
            json.dumps({"endpoint": "ep", "sha256": "other", "status": "IN_QUEUE", "id": "x"})
        )
        transport = FakeTransport([])
        with self.assertRaises(ProviderError) as caught:
            run_job("ep", {"workflow": {}}, state_file=self.state_file(), transport=transport, poll_seconds=0)
        self.assertIn("different pending request", str(caught.exception))
        self.assertEqual(transport.submissions, [])

    def test_a_submission_with_no_confirmed_id_is_refused(self) -> None:
        payload = {"workflow": {"a": 1}}
        digest_state = {"endpoint": "ep", "status": "SUBMITTING"}
        self.state_file().write_text(json.dumps(digest_state))
        with self.assertRaises(ProviderError):
            run_job("ep", payload, state_file=self.state_file(), transport=FakeTransport([]), poll_seconds=0)

    def test_a_failed_job_raises_with_the_worker_reason(self) -> None:
        transport = FakeTransport([{"status": "FAILED", "error": "out of memory"}])
        with self.assertRaises(ProviderError) as caught:
            run_job("ep", {"workflow": {}}, state_file=self.state_file(), transport=transport, poll_seconds=0)
        self.assertIn("out of memory", str(caught.exception))
        self.assertEqual(json.loads(self.state_file().read_text())["status"], "FAILED")

    def test_an_error_inside_a_completed_output_is_still_a_failure(self) -> None:
        transport = FakeTransport([{"status": "COMPLETED", "output": {"error": "bad node"}}])
        with self.assertRaises(ProviderError) as caught:
            run_job("ep", {"workflow": {}}, state_file=self.state_file(), transport=transport, poll_seconds=0)
        self.assertIn("bad node", str(caught.exception))

    def test_a_job_that_vanished_from_the_queue_is_terminal(self) -> None:
        class Gone(FakeTransport):
            def __call__(self, path, body=None):
                if path.endswith("/run"):
                    return super().__call__(path, body)
                raise urllib.error.HTTPError(path, 404, "gone", {}, None)

        with self.assertRaises(ProviderError) as caught:
            run_job("ep", {"workflow": {}}, state_file=self.state_file(), transport=Gone([]), poll_seconds=0)
        self.assertIn("no longer in the queue", str(caught.exception))
        self.assertEqual(json.loads(self.state_file().read_text())["status"], "FAILED")

    def test_polling_reports_progress(self) -> None:
        seen: list[str] = []
        transport = FakeTransport(
            [{"status": "IN_PROGRESS"}, {"status": "COMPLETED", "output": {}}]
        )
        run_job(
            "ep",
            {"workflow": {}},
            state_file=self.state_file(),
            transport=transport,
            poll_seconds=0,
            on_progress=lambda label, state: seen.append(state["status"]),
        )
        self.assertEqual(seen, ["IN_PROGRESS", "COMPLETED"])

    def test_an_empty_endpoint_id_is_a_configuration_error(self) -> None:
        with self.assertRaises(ProviderNotConfigured):
            run_job("", {"workflow": {}}, state_file=self.state_file(), transport=FakeTransport([]))


class CredentialTests(TemporaryCase):
    def test_env_values_are_loaded_without_overriding_the_environment(self) -> None:
        import os

        env = self.root / ".env"
        env.write_text("# comment\nSOME_TOKEN=abc\nEMPTY\n", encoding="utf-8")
        os.environ.pop("SOME_TOKEN", None)
        self.addCleanup(os.environ.pop, "SOME_TOKEN", None)
        load_credentials(env)
        self.assertEqual(os.environ["SOME_TOKEN"], "abc")

    def test_a_missing_file_is_not_an_error(self) -> None:
        load_credentials(self.root / "nope.env")

    def test_an_unconfigured_provider_reports_it_before_any_work(self) -> None:
        provider = LtxProvider(endpoint_id="")
        with self.assertRaises(ProviderNotConfigured):
            provider.generate(
                image=self.image(), output=self.root / "out.mp4", seconds=5, prompt="x"
            )


class CostTests(unittest.TestCase):
    def test_cost_comes_from_the_time_the_platform_reports(self) -> None:
        self.assertAlmostEqual(
            cost_usd({"delayTime": 1000, "executionTime": 3600_000}, 1.75), 1.75 * 3601 / 3600
        )


if __name__ == "__main__":
    unittest.main()
