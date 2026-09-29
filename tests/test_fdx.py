"""Final Draft interchange: nothing is lost without being reported (ADR 0014)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from cine_toaster import screenplay as sp
from cine_toaster.fdx import export_fdx, import_fdx

FIXTURES = Path(__file__).parent / "fixtures" / "fdx"
REAL = (FIXTURES / "TestFDX-FD.fdx").read_text(encoding="utf-8")
DEMO_SCRIPT = (Path(__file__).parents[1] / "examples" / "demo-project" / "story" / "screenplay.fountain").read_text(encoding="utf-8")


def enriched() -> str:
    """The real file, with what it lacks, written the way Final Draft writes it."""

    text = REAL
    start = text.index("<Text>We are in a TV station listening to the ")
    end = text.index("</Text>", start) + len("</Text>")
    text = (text[:start] + '<Text>We are in </Text><Text Style="Bold">a TV station</Text>'
            '<Text> listening to the </Text><Text Style="Italic">radio</Text><Text>.</Text>' + text[end:])
    text = text.replace('Number="2" Type="Scene Heading"', 'Number="12A" Type="Scene Heading"', 1)
    text = text.replace("<Text>Why do we pay him?</Text>", '<Text RevisionID="2">Why do we pay him?</Text>', 1)
    anchor = text.index("</Paragraph>", text.index("<Text>Maybe there")) + len("</Paragraph>")
    extra = """
    <Paragraph><DualDialogue>
      <Paragraph Type="Character"><Text>DAVE</Text></Paragraph>
      <Paragraph Type="Dialogue"><Text>Not for you.</Text></Paragraph>
      <Paragraph Type="Character"><Text>JIM</Text></Paragraph>
      <Paragraph Type="Dialogue"><Text>Not for anyone.</Text></Paragraph>
    </DualDialogue></Paragraph>
    <Paragraph Type="Shot"><Text>CLOSE ON KAY</Text></Paragraph>
    <Paragraph Type="General"><Text>A general paragraph.</Text></Paragraph>"""
    return text[:anchor] + extra + text[anchor:]


def units(fountain: str):
    return [
        (scene.heading, scene.number,
         [(u.kind, u.speaker if u.kind == "speech" else "", u.text, u.dual) for u in scene.units])
        for scene in sp.parse(fountain).scenes
    ]


def losses(conversion) -> dict[str, int]:
    return {loss.what: loss.count for loss in conversion.losses}


class ImportTests(unittest.TestCase):
    def test_a_real_final_draft_file_arrives_whole(self) -> None:
        result = import_fdx(REAL)
        play = sp.parse(result.text)
        self.assertEqual(result.elements, 16)
        self.assertEqual(play.title, "FDX Test Script")
        self.assertEqual([(s.heading, s.number) for s in play.scenes],
                         [("INT. RADIO STUDIO", "1"), ("EXT. OUTSIDE THE FOOD STORE", "2")])
        kinds = [u.kind for s in play.scenes for u in s.units]
        self.assertEqual(kinds.count("speech"), 4)
        self.assertEqual(kinds.count("transition"), 2)  # FADE TO BLACK is forced, CUT TO: is not
        self.assertEqual(losses(result), {})

    def test_styled_runs_become_emphasis_instead_of_being_cut_off(self) -> None:
        self.assertIn("We are in **a TV station** listening to the *radio*.", import_fdx(enriched()).text)

    def test_dual_dialogue_shots_and_scene_numbers(self) -> None:
        result = import_fdx(enriched())
        second = sp.parse(result.text).scenes[1]
        self.assertEqual(second.number, "12A")
        speeches = [(u.speaker, u.dual) for u in second.units if u.kind == "speech"]
        self.assertEqual(speeches[-2:], [("DAVE", False), ("JIM", True)])
        # A shot is not a scene: it must not create one, or the scene links move.
        self.assertEqual(len(sp.parse(result.text).scenes), 2)
        self.assertIn("!CLOSE ON KAY", result.text)

    def test_what_cannot_be_kept_is_reported(self) -> None:
        reported = losses(import_fdx(enriched()))
        self.assertEqual(reported["revision marks"], 1)
        self.assertEqual(reported["shots"], 1)
        self.assertNotIn("script notes", reported)

    def test_a_file_that_is_not_fdx_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            import_fdx("<html></html>")


class ExportTests(unittest.TestCase):
    def test_round_trips_keep_every_unit(self) -> None:
        for fountain in (DEMO_SCRIPT, import_fdx(enriched()).text):
            back = import_fdx(export_fdx(fountain).text).text
            self.assertEqual(units(back), units(fountain))
            self.assertEqual(sp.parse(back).title, sp.parse(fountain).title)

    def test_emphasis_dual_dialogue_and_numbers_reach_final_draft(self) -> None:
        root = ET.fromstring(export_fdx(import_fdx(enriched()).text).text.encode("utf-8"))
        styles = [run.get("Style") for run in root.iter("Text") if run.get("Style")]
        self.assertEqual(styles, ["Bold", "Italic"])
        self.assertIsNotNone(root.find("Content/Paragraph/DualDialogue"))
        numbers = [p.get("Number") for p in root.iter("Paragraph") if p.get("Type") == "Scene Heading"]
        self.assertEqual(numbers, ["1", "12A"])

    def test_fountain_only_elements_are_reported(self) -> None:
        fountain = "INT. A - DAY\n\n# Act one\n\n= The setup\n\nShe waits. [[check the light]]\n\n===\n\nShe leaves.\n"
        result = export_fdx(fountain)
        reported = losses(result)
        self.assertIn("# sections", reported)
        self.assertIn("= synopses", reported)
        root = ET.fromstring(result.text.encode("utf-8"))
        self.assertEqual([p.get("StartsNewPage") for p in root.iter("Paragraph") if "leaves" in "".join(p.itertext())], ["Yes"])


class AnchorTests(unittest.TestCase):
    def test_an_anchor_ignores_emphasis(self) -> None:
        scene = sp.parse(import_fdx(enriched()).text).scenes[0]
        self.assertEqual(len(sp.resolve_anchor(scene, "We are in a TV station listening")), 1)


class CommandTests(unittest.TestCase):
    def test_import_writes_a_new_file_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "script.fountain"
            command = [sys.executable, "-m", "cine_toaster.cli", "script", "import-fdx",
                       str(FIXTURES / "TestFDX-FD.fdx"), "--output", str(target)]
            env = {"PYTHONPATH": str(Path(__file__).parents[1] / "src")}
            first = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = target.read_text(encoding="utf-8")
            second = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(second.returncode, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
