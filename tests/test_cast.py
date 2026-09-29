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

    def test_the_same_person_labelled_differently_is_noticed(self) -> None:
        loaded = production({"kael": KAEL}, {
            "010": SCENE.format(id="S1", who="KAEL", label="Kael"),
            "020": SCENE.format(id="S2", who="KAEL", label="Kael (seated)"),
        })
        self.assertIn("cast_label_drift", codes(loaded["scenes"][0]))

    def test_a_scene_that_restates_the_voice_is_advised(self) -> None:
        scene = SCENE.format(id="S1", who="KAEL", label="Kael") + "vozes: {KAEL: a weak hoarse voice}\n"
        loaded = production({"kael": KAEL}, {"010": scene}, "scene_fields:\n  vozes: {maps_to: voices}\n")
        self.assertIn("voice_identity_restated", codes(loaded["scenes"][0]))

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
