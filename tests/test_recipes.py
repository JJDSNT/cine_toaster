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


if __name__ == "__main__":
    unittest.main()
