"""A character is declared once; scenes name them and hold only their state (SPEC-0003, CT-0040)."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from cine_toaster.cast import propose
from cine_toaster.project import load_production

DEMO = Path(__file__).parents[1] / "examples" / "demo-project"


def production(sheets: dict[str, str], scenes: dict[str, str], manifest_extra: str = "") -> dict:
    root = Path(tempfile.mkdtemp())
    (root / "project.yaml").write_text("id: t\ntitle: T\npaths:\n  scenes: scenes\n" + manifest_extra)
    for name, text in sheets.items():
        (root / "cast" / name).mkdir(parents=True)
        (root / "cast" / name / "character.yaml").write_text(textwrap.dedent(text))
    for name, text in scenes.items():
        (root / "scenes" / name).mkdir(parents=True)
        (root / "scenes" / name / "scene.yaml").write_text(textwrap.dedent(text))
    return load_production(root)


def codes(scene: dict) -> list[str]:
    return sorted(finding["code"] for finding in scene["findings"])


KAEL = textwrap.dedent("""\
    id: KAEL
    label: Kael
    authoritative_for: [face, voice]
    references: [{path: face.png, kind: face, role: master}]
    variants:
      boreal: {description: after the stasis, references: [{path: boreal.png, kind: face, role: master}]}
    voice: {identity: a low controlled male voice, accent: slight European}
""")
SCENE = textwrap.dedent("""\
    scene: {id}
    geography:
      room: [4, 3]
      subjects: [{{id: {who}, label: {label}, x: 1, y: 1}}]
    shots:
      - n: 1
        subject: {who}
""")


class DemoTests(unittest.TestCase):
    def test_the_demo_cast_resolves_every_speaker(self) -> None:
        loaded = load_production(DEMO)
        self.assertEqual(sorted(loaded["cast"]), ["ANNOUNCER", "MARA", "SPEAKER"])
        self.assertEqual([finding for scene in loaded["scenes"] for finding in scene["findings"]], [])


class AppearanceTests(unittest.TestCase):
    def test_each_member_knows_the_scenes_shots_and_voice_state(self) -> None:
        cast = load_production(DEMO)["cast"]
        mara = {item["scene"]: item for item in cast["MARA"]["appearances"]}
        self.assertEqual(sorted(mara), ["SC-010", "SC-030"])
        self.assertIn("P3", mara["SC-030"]["shots"])
        self.assertIn("whisper", mara["SC-030"]["voice_state"])
        self.assertEqual([item["scene"] for item in cast["ANNOUNCER"]["appearances"]], ["SC-010"])


class CheckTests(unittest.TestCase):
    def test_nothing_is_checked_without_a_cast(self) -> None:
        loaded = production({}, {"010": SCENE.format(id="S1", who="KAEL", label="Kael")})
        self.assertEqual(codes(loaded["scenes"][0]), [])

    def test_a_person_without_a_sheet_is_reported(self) -> None:
        loaded = production({"kael": KAEL}, {"010": SCENE.format(id="S1", who="CLAIRE", label="Claire")})
        self.assertIn("cast_subject_unknown", codes(loaded["scenes"][0]))

    def test_a_generated_face_needs_its_master_picture(self) -> None:
        loaded = production({"kael": KAEL}, {"010": SCENE.format(id="S1", who="KAEL", label="Kael")})
        self.assertEqual(codes(loaded["scenes"][0]), ["cast_reference_missing"])

    def test_a_voice_only_member_owes_no_picture(self) -> None:
        voice_only = "id: RADIO\nlabel: Radio\nauthoritative_for: [voice]\nvoice: {identity: static}\n"
        loaded = production({"radio": voice_only}, {"010": SCENE.format(id="S1", who="RADIO", label="Radio")})
        self.assertEqual(codes(loaded["scenes"][0]), [])

    def test_an_unknown_variant_is_an_error(self) -> None:
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "cast: {KAEL: geneva}\n"
        loaded = production({"kael": KAEL}, {"010": scene})
        self.assertIn("cast_variant_unknown", codes(loaded["scenes"][0]))

    def test_a_variant_with_another_face_is_another_person_until_it_says_why(self) -> None:
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "cast: {KAEL: boreal}\n"
        loaded = production({"kael": KAEL}, {"010": scene})
        found = [item for item in loaded["scenes"][0]["findings"] if item["code"] == "cast_identity_split"]
        self.assertEqual(len(found), 1)
        self.assertIn("2 master faces", found[0]["message"])
        self.assertIn("face_changes", found[0]["message"])

    def test_a_declared_reason_accepts_the_new_face(self) -> None:
        sheet = KAEL.replace("description: after the stasis,", "description: after the stasis, face_changes: years in stasis,")
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "cast: {KAEL: boreal}\n"
        loaded = production({"kael": sheet}, {"010": scene})
        self.assertNotIn("cast_identity_split", codes(loaded["scenes"][0]))
        self.assertEqual(loaded["cast"]["KAEL"]["variants"]["boreal"]["face_changes"], "years in stasis")

    def test_a_variant_on_the_same_master_face_is_the_same_person(self) -> None:
        sheet = KAEL.replace("boreal.png", "face.png")
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "cast: {KAEL: boreal}\n"
        self.assertNotIn("cast_identity_split", codes(production({"kael": sheet}, {"010": scene})["scenes"][0]))

    def test_the_same_person_labelled_differently_is_noticed(self) -> None:
        loaded = production({"kael": KAEL}, {
            "010": SCENE.format(id="S1", who="KAEL", label="Kael"),
            "020": SCENE.format(id="S2", who="KAEL", label="Kael Vance"),
        })
        self.assertIn("cast_label_drift", codes(loaded["scenes"][0]))

    def test_a_pose_or_a_mark_in_the_label_is_not_drift(self) -> None:
        # SINGULAR's plans label a pose: "Kael (sentado)", "Líra L1 (sentada)". The name is the same (SPEC-0003).
        loaded = production({"kael": KAEL}, {
            "010": SCENE.format(id="S1", who="KAEL", label="Kael"),
            "020": SCENE.format(id="S2", who="KAEL", label="Kael (seated)"),
            "030": SCENE.format(id="S3", who="KAEL", label="Kael K1"),
        })
        self.assertNotIn("cast_label_drift", codes(loaded["scenes"][0]))

    def test_a_scene_that_gives_another_voice_is_an_error(self) -> None:
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "vozes: {KAEL: a weak hoarse voice}\n"
        loaded = production({"kael": KAEL}, {"010": scene}, "scene_fields:\n  vozes: {maps_to: voices}\n")
        found = [item for item in loaded["scenes"][0]["findings"] if item["code"] == "voice_identity_conflict"]
        self.assertEqual([item["severity"] for item in found], ["error"])

    def test_a_scene_that_only_repeats_the_voice_is_advised(self) -> None:
        scene = (SCENE.format(id="S1", who="KAEL", label="Kael")
                 + "vozes: {KAEL: 'a low controlled male voice, slight European accent'}\n")
        loaded = production({"kael": KAEL}, {"010": scene}, "scene_fields:\n  vozes: {maps_to: voices}\n")
        self.assertIn("voice_identity_restated", codes(loaded["scenes"][0]))
        self.assertNotIn("voice_identity_conflict", codes(loaded["scenes"][0]))

    def test_generated_speech_without_a_recording_has_no_voice_to_hold(self) -> None:
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "    lines: [{who: KAEL, text: Claire}]\n"
        found = [item for item in production({"kael": KAEL}, {"010": scene})["scenes"][0]["findings"]
                 if item["code"] == "cast_voice_reference_missing"]
        self.assertEqual((found[0]["severity"], found[0]["shots"]), ("error", ["P1"]))
        recorded = KAEL.replace("accent: slight European}", "accent: slight European, references: [kael.wav]}")
        self.assertNotIn("cast_voice_reference_missing",
                         codes(production({"kael": recorded}, {"010": scene})["scenes"][0]))

    def test_a_line_whose_audio_file_is_missing_is_an_error(self) -> None:
        scene = (SCENE.format(id="S1", who="KAEL", label="Kael")
                 + "    lines: [{who: KAEL, text: Claire, voice: Deep_Man, mix: {file: voices/claire.wav, at: 0.5}}]\n")
        found = [item for item in production({"kael": KAEL}, {"010": scene})["scenes"][0]["findings"]
                 if item["code"] == "line_audio_missing"]
        self.assertEqual((found[0]["severity"], found[0]["shots"]), ("error", ["P1"]))
        spoken_here = scene.replace("voice: Deep_Man", "voice: piper/en_US-ljspeech-medium")
        found = [item for item in production({"kael": KAEL}, {"010": spoken_here})["scenes"][0]["findings"]
                 if item["code"] == "line_audio_missing"]
        self.assertEqual(found[0]["severity"], "advice")  # Cine Toaster speaks it: not made yet, not lost

    def test_one_person_in_two_named_voices_is_an_error(self) -> None:
        first = SCENE.format(id="S1", who="KAEL", label="Kael") + "    lines: [{who: KAEL, text: a, voice: Deep_Man}]\n"
        second = SCENE.format(id="S2", who="KAEL", label="Kael") + "    lines: [{who: KAEL, text: b, voice: Calm_Man}]\n"
        loaded = production({"kael": KAEL}, {"010": first, "020": second})
        for scene in loaded["scenes"]:
            self.assertIn("cast_voice_split", codes(scene))
            self.assertNotIn("cast_voice_reference_missing", codes(scene))  # a named voice holds it

    def test_a_character_answers_to_all_their_names(self) -> None:
        sheet = KAEL.replace("id: KAEL", "id: KAEL\nnames: [KAEL VANCE]")
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "    lines: [{who: KAEL VANCE, text: Hello.}]\n"
        loaded = production({"kael": sheet}, {"010": scene})
        self.assertNotIn("cast_subject_unknown", codes(loaded["scenes"][0]))


class ProposeTests(unittest.TestCase):
    def test_drafts_list_every_version_with_its_scenes(self) -> None:
        drafts = propose([
            ("1-02", {"vozes": {"KAEL": "a low controlled voice"}}),
            ("3-01", {"vozes": {"KAEL": "a low controlled voice with a slight European accent"}, "fichas": {"Kael": "kael_boreal"}}),
        ])
        self.assertEqual(len(drafts["KAEL"]["voices"]), 2)
        self.assertEqual(drafts["KAEL"]["sheets"], {"kael_boreal": ["3-01"]})


if __name__ == "__main__":
    unittest.main()
