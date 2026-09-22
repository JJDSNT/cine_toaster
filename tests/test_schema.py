"""SPEC-0004: the production schema holds a reel and a feature."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster.looks import load_looks, resolve
from cine_toaster.project import load_production


EXAMPLES = Path(__file__).parents[1] / "examples"


def _reel() -> dict:
    return load_production(EXAMPLES / "amiga-demo-reel")


class SourceAndEngineTests(unittest.TestCase):
    def test_every_reel_shot_declares_where_its_frames_come_from(self) -> None:
        for scene in _reel()["scenes"]:
            for shot in scene["shots"]:
                self.assertEqual(shot["source"], "composed", shot["id"])
                self.assertTrue(shot["engine"], shot["id"])

    def test_a_composed_shot_expects_no_take(self) -> None:
        for scene in _reel()["scenes"]:
            for shot in scene["shots"]:
                self.assertEqual(shot["take_count"], 0, shot["id"])

    def test_legacy_kind_still_implies_a_source(self) -> None:
        """`tipo: preto` always meant a composed solid; it still does."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "cenas" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitulo: X\n", encoding="utf-8")
            (root / "cenas" / "010" / "decupagem.yaml").write_text(
                "cena: SC-010\nplanos:\n  - n: 1\n    tipo: preto\n    dur: 2\n"
                "    plano: Preto.\n",
                encoding="utf-8",
            )
            shot = load_production(root)["scenes"][0]["shots"][0]
        self.assertEqual(shot["source"], "composed")
        self.assertEqual(shot["engine"], "solid")


class ShotFieldTierTests(unittest.TestCase):
    """Nothing is dropped: typed, declared, or passed through."""

    def test_a_declared_field_is_carried_and_not_reported(self) -> None:
        scene = next(s for s in _reel()["scenes"] if s["id"] == "SC-020")
        shot = scene["shots"][0]
        self.assertIn("copper_phase", shot["extra_fields"])
        self.assertEqual(shot["extra_fields"]["copper_phase"]["label"], "Copper phase")
        self.assertEqual(shot["extra_fields"]["copper_phase"]["value"], 0.25)
        self.assertEqual(shot["unknown_fields"], [])

    def test_an_undeclared_field_is_kept_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitle: X\n", encoding="utf-8")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: SC-010\nshots:\n  - n: 1\n    duration: 2\n    label: A.\n"
                "    lira: holds the lamp\n",
                encoding="utf-8",
            )
            scene = load_production(root)["scenes"][0]

        shot = scene["shots"][0]
        self.assertEqual(shot["unknown_fields"], ["lira"])
        # Kept, not dropped.
        self.assertEqual(shot["extra_fields"]["lira"]["value"], "holds the lamp")
        codes = [finding["code"] for finding in scene["findings"]]
        self.assertIn("shot_field_undeclared", codes)
        finding = next(f for f in scene["findings"] if f["code"] == "shot_field_undeclared")
        self.assertEqual(finding["severity"], "advice")
        self.assertEqual(finding["shots"], ["P1"])


class FamilyTests(unittest.TestCase):
    def test_seven_legacy_lineage_keys_collapse_into_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitle: X\n", encoding="utf-8")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: SC-010\nshots:\n"
                "  - n: 1\n    duration: 2\n    label: A.\n"
                "    usa: master-a\n    usa_de: P0\n    reusa: master-b\n",
                encoding="utf-8",
            )
            shot = load_production(root)["scenes"][0]["shots"][0]
        refs = [entry["ref"] for entry in shot["from"]]
        self.assertEqual(refs, ["master-a", "P0", "master-b"])
        self.assertEqual(shot["unknown_fields"], [])

    def test_lines_carry_speaker_delivery_voice_and_mix(self) -> None:
        scene = next(s for s in _reel()["scenes"] if s["id"] == "SC-010")
        line = scene["shots"][1]["lines"][0]
        self.assertEqual(line["who"], "NARRATOR")
        self.assertTrue(line["delivery"])
        self.assertTrue(line["voice"])
        self.assertEqual(line["mix"]["file"], "sound/vo-open.wav")

    def test_legacy_falas_load_as_lines(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitle: X\n", encoding="utf-8")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: SC-010\nshots:\n  - n: 1\n    dur: 2\n    plano: A.\n"
                "    falas:\n      - quem: KAEL\n        pt: Ola.\n        en: Hello.\n"
                "        como: flat\n        voz: v1\n",
                encoding="utf-8",
            )
            line = load_production(root)["scenes"][0]["shots"][0]["lines"][0]
        self.assertEqual(line["who"], "KAEL")
        self.assertEqual(line["text"], "Ola.")
        self.assertEqual(line["en"], "Hello.")
        self.assertEqual(line["delivery"], "flat")


class TransitionReferenceTests(unittest.TestCase):
    def test_the_reel_references_the_catalog_including_its_own(self) -> None:
        ids = {
            shot["transition"]["id"]
            for scene in _reel()["scenes"]
            for shot in scene["shots"]
            if shot["transition"]
        }
        self.assertIn("amiga-copper-bars", ids)
        self.assertGreaterEqual(len(ids), 4)

    def test_every_reel_transition_records_a_reason(self) -> None:
        for scene in _reel()["scenes"]:
            for shot in scene["shots"]:
                if shot["transition"]:
                    self.assertTrue(shot["transition"]["reason"], shot["id"])

    def test_an_unknown_transition_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "scenes" / "010").mkdir(parents=True)
            (root / "project.yaml").write_text("id: x\ntitle: X\n", encoding="utf-8")
            (root / "scenes" / "010" / "scene.yaml").write_text(
                "scene: SC-010\nshots:\n  - n: 1\n    duration: 2\n    label: A.\n"
                "    transition: {id: nope, reason: none}\n",
                encoding="utf-8",
            )
            scene = load_production(root)["scenes"][0]
        finding = next(f for f in scene["findings"] if f["code"] == "transition_unknown")
        self.assertEqual(finding["severity"], "error")


class LookTests(unittest.TestCase):
    def test_the_reel_declares_a_look_with_pacing(self) -> None:
        looks = load_looks(EXAMPLES / "amiga-demo-reel")
        self.assertIn("reel", looks)
        pacing = looks["reel"].pacing
        self.assertEqual(pacing["minimum_hold_seconds"], 2.0)
        self.assertEqual(pacing["transition_duration_ms"], 850)

    def test_the_cascade_reaches_every_shot_and_records_its_level(self) -> None:
        production = _reel()
        self.assertEqual(production["look"], "reel")
        self.assertIn("reel", production["looks"])
        for scene in production["scenes"]:
            for shot in scene["shots"]:
                self.assertEqual(shot["look"], "reel", shot["id"])
                self.assertEqual(shot["look_from"], "project", shot["id"])

    def test_the_nearest_declaration_wins_and_says_which(self) -> None:
        self.assertEqual(resolve(scene="archive", project="reel"), ("archive", "scene"))
        self.assertEqual(resolve(project="reel"), ("reel", "project"))
        self.assertEqual(resolve(), ("", ""))

    def test_every_card_holds_within_the_looks_pacing(self) -> None:
        """The look's rules are readable by a check, not only by a person."""

        pacing = load_looks(EXAMPLES / "amiga-demo-reel")["reel"].pacing
        for scene in _reel()["scenes"]:
            for shot in scene["shots"]:
                self.assertGreaterEqual(
                    shot["duration_seconds"], pacing["minimum_hold_seconds"], shot["id"]
                )
                self.assertLessEqual(
                    shot["duration_seconds"], pacing["maximum_hold_seconds"], shot["id"]
                )


class ReelIntegrityTests(unittest.TestCase):
    def test_the_reel_is_clean(self) -> None:
        production = _reel()
        self.assertEqual([f for s in production["scenes"] for f in s["findings"]], [])

    def test_no_two_adjacent_shots_share_a_transition(self) -> None:
        """A rule the look states, checked against the reel that states it."""

        previous = None
        for scene in _reel()["scenes"]:
            for shot in scene["shots"]:
                current = shot["transition"]["id"] if shot["transition"] else None
                if current is not None and previous is not None:
                    self.assertNotEqual(current, previous, shot["id"])
                previous = current

    def test_the_narration_is_declared_before_it_is_generated(self) -> None:
        """The reel casts and places its narration; making it is the tool's job.

        Cine Toaster has no TTS yet, so the asset does not exist. Declaring it
        anyway is the honest production state, and it is what an audio tier
        will be built against.
        """

        line = next(
            line
            for scene in _reel()["scenes"]
            for shot in scene["shots"]
            for line in shot["lines"]
        )
        self.assertTrue(line["voice"])
        self.assertEqual(line["mix"]["file"], "sound/vo-open.wav")
        self.assertFalse((EXAMPLES / "amiga-demo-reel" / line["mix"]["file"]).is_file())


if __name__ == "__main__":
    unittest.main()
