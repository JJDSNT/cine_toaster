"""Generation recipes: what each path makes, read from its adapter; health from the data plane (ADR 0034)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cine_toaster.errors import CineToasterError
from cine_toaster.providers.ltx import HOURLY_RATE_USD
from cine_toaster.providers.recipes import RECIPES, describe, health, recipes, workflow_models

ENV = {"RUNPOD_API_KEY": "not-a-real-key", "RUNPOD_LTX_ENDPOINT_ID": "endpoint-1"}


class RecipeTests(unittest.TestCase):
    def test_the_numbers_are_the_adapters_own(self):
        self.assertEqual(describe(RECIPES["ltx-2-5"])["rate_usd_per_hour"], HOURLY_RATE_USD)

    def test_the_graph_says_which_model_files_the_endpoint_must_hold(self):
        files = [item["file"] for item in workflow_models(RECIPES["ltx-2-5"].workflow)]
        self.assertIn("ltx-2.5-video-vae-bf16.safetensors", files)
        self.assertEqual(len(files), len(set(files)))

    def test_configuration_is_named_never_shown(self):
        with patch.dict(os.environ, {}, clear=True):
            item = describe(RECIPES["ltx-2-5"])
        self.assertEqual(item["missing"], ["RUNPOD_LTX_ENDPOINT_ID", "RUNPOD_API_KEY"])
        with patch.dict(os.environ, ENV, clear=True):
            item = describe(RECIPES["ltx-2-5"])
        self.assertTrue(item["configured"])
        self.assertNotIn("not-a-real-key", str(recipes()))

    def test_known_failures_come_from_the_measured_notes(self):
        ids = {item["id"] for item in describe(RECIPES["ltx-2-5"])["known_failures"]}
        self.assertIn("silent-gpu-swap", ids)  # runpod-serverless.md

    def test_health_reads_workers_and_queue_and_warns_of_a_cold_start(self):
        asked = []

        def transport(path, body):
            asked.append((path, body))
            return {"workers": {"idle": 0, "running": 0, "initializing": 1}, "jobs": {"inQueue": 2}}

        with patch.dict(os.environ, ENV, clear=True):
            value = health("ltx-2-5", transport)
        self.assertEqual(asked, [("/endpoint-1/health", None)])  # a GET on the data plane, nothing else
        self.assertTrue(value["readable"] and value["cold_start_likely"])

    def test_what_cannot_be_read_is_said(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn("not set", health("ltx-2-5")["reason"])
        self.assertFalse(health("codex-image")["readable"])

        def broken(path, body):
            raise OSError("unreachable")

        with patch.dict(os.environ, ENV, clear=True):
            self.assertIn("unreachable", health("ltx-2-5", broken)["reason"])
        with self.assertRaises(CineToasterError):
            health("no-such-recipe")



class DevelopmentSkillTests(unittest.TestCase):
    def test_the_development_skill_never_reaches_production_agents(self):
        from pathlib import Path

        root = Path(__file__).parents[1]
        self.assertTrue((root / ".agents/skills/runpod-comfyui/SKILL.md").is_file())
        product = root / "src" / "cine_toaster"
        for path in product.rglob("*.py"):
            self.assertNotIn(".agents/skills", path.read_text(encoding="utf-8"), path)



class BatchTests(unittest.TestCase):
    COLD = {"readable": True, "warm_workers": 0, "jobs": {"inQueue": 0, "inProgress": 0}}
    CONFIG = {"readable": True, "workers_max": 2, "idle_timeout_seconds": 60}

    def test_together_pays_cold_starts_once_one_by_one_pays_each(self):
        from cine_toaster.providers.recipes import batch_plan

        plan = batch_plan("ltx-2-5", 6, seconds_each=64, state=self.COLD, config=self.CONFIG)
        self.assertEqual(plan["together"]["cold_starts"], 2)        # two workers start, once
        self.assertEqual(plan["one_by_one_worst"]["cold_starts"], 6)
        self.assertLess(plan["together"]["seconds"], plan["one_by_one_worst"]["seconds"])
        self.assertTrue(any("together" in line for line in plan["advice"]))
        self.assertTrue(any("idle timeout is shorter" in line for line in plan["advice"]))  # 60 s < 64 s a job

    def test_warm_workers_mean_no_cold_start(self):
        from cine_toaster.providers.recipes import batch_plan

        warm = {**self.COLD, "warm_workers": 2}
        self.assertEqual(batch_plan("ltx-2-5", 4, seconds_each=64, state=warm, config=self.CONFIG)
                         ["together"]["cold_starts"], 0)

    def test_scaling_down_mid_batch_is_flagged(self):
        from cine_toaster.providers.recipes import batch_plan, scale_down_guard

        busy = {**self.COLD, "jobs": {"inQueue": 3, "inProgress": 1}}
        self.assertEqual(scale_down_guard(busy), {"safe": False, "in_flight": 4, "reason":
                         "4 job(s) queued or running: lowering workers or idle timeout now strands them"})
        self.assertFalse(scale_down_guard({"readable": False})["safe"])  # unknown is never safe
        plan = batch_plan("ltx-2-5", 2, state=busy, config=self.CONFIG)
        self.assertTrue(any("Do not lower workers" in line for line in plan["advice"]))

    def test_the_endpoint_configuration_is_read_from_rest_v2(self):
        from cine_toaster.providers.recipes import endpoint_config

        asked = []

        def fetch(path, query):
            asked.append(path)
            return {"workers": {"min": 0, "max": 2, "idleTimeout": 60}, "flashboot": "FLASHBOOT",
                    "scaling": {"type": "QUEUE_DELAY", "queueDelay": 4}}

        with patch.dict(os.environ, ENV, clear=True):
            config = endpoint_config("ltx-2-5", fetch)
        self.assertEqual(asked, ["/serverless/endpoint-1"])
        self.assertEqual((config["workers_max"], config["idle_timeout_seconds"]), (2, 60))
        self.assertFalse(endpoint_config("codex-image")["readable"])


if __name__ == "__main__":
    unittest.main()
