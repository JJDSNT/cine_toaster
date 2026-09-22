"""A fresh clone must be able to ask what works here."""

from __future__ import annotations

import unittest

from cine_toaster import doctor


class DoctorTests(unittest.TestCase):
    def test_every_capability_says_what_it_enables(self) -> None:
        for capability in doctor.examine():
            self.assertTrue(capability.name, capability)
            self.assertTrue(capability.what_it_enables, capability.name)

    def test_a_missing_capability_always_carries_its_remedy(self) -> None:
        """A report that says what is wrong without saying what to type is half a report."""

        for capability in doctor.examine():
            if capability.status != doctor.OK:
                self.assertTrue(capability.remedy, capability.name)

    def test_reading_a_production_is_required_and_present(self) -> None:
        by_name = {item.name: item for item in doctor.examine()}
        self.assertTrue(by_name["PyYAML"].required)
        self.assertEqual(by_name["PyYAML"].status, doctor.OK)
        self.assertFalse(doctor.blocked())

    def test_encoding_is_optional_so_the_tool_runs_without_ffmpeg(self) -> None:
        by_name = {item.name: item for item in doctor.examine()}
        self.assertFalse(by_name["FFmpeg"].required)
        self.assertFalse(by_name["Media libraries"].required)

    def test_the_report_leads_with_what_works(self) -> None:
        text = doctor.report()
        self.assertIn("Cine Toaster", text)
        first = next(
            line for line in text.splitlines() if line.strip().startswith(("ok", "BLOCKED", "--"))
        )
        self.assertTrue(first.strip().startswith("ok"))


if __name__ == "__main__":
    unittest.main()


class StudioToolchainTests(unittest.TestCase):
    """The tools Cine Toaster is growing toward, reported honestly."""

    def test_a_tool_nothing_calls_yet_is_marked_as_such(self) -> None:
        by_name = {item.name: item for item in doctor.examine()}
        for name in ("SoX", "Blender", "ModernGL", "Transcription"):
            self.assertIn(name, by_name)
            self.assertFalse(by_name[name].wired, name)
            self.assertFalse(by_name[name].required, name)

    def test_what_is_in_use_is_marked_as_in_use(self) -> None:
        by_name = {item.name: item for item in doctor.examine()}
        for name in ("FFmpeg", "Piper narration", "Media libraries"):
            self.assertTrue(by_name[name].wired, name)

    def test_the_report_separates_the_two(self) -> None:
        text = doctor.report()
        self.assertIn("Studio toolchain", text)
        self.assertIn("does not call these yet", text)
        studio = text.split("Studio toolchain")[1]
        self.assertIn("Blender", studio)
        self.assertNotIn("PyYAML", studio)
