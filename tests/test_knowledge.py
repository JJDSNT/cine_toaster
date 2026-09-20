from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster.errors import ValidationError
from cine_toaster.geometry import CHECK_CODES
from cine_toaster.knowledge import (
    coverage,
    load_practices,
    load_providers,
    parse_frontmatter,
    practices_for_check,
)


PRACTICE = """+++
id = "test-practice"
title = "A rule we learned the hard way"
domain = "continuity"
status = "measured"
learned_on = "2026-09-17"
enforced_by = ["axis_break"]
evidence = ["scenes/010/shots/SH-1"]
cost = "5 discarded versions"
+++

The body explains why, in prose, because a person has to want to write it.
"""

UNENFORCED = """+++
id = "still-manual"
title = "Nothing checks this yet"
domain = "craft"
status = "convention"
+++

Recorded so the gap stays visible.
"""

PROVIDER = """+++
id = "test-model"
title = "Test Model"
kind = "video"
version = "1.0"

[[claims]]
id = "negation-provokes"
claim = "Negation produces the thing negated."
status = "measured"
measured_on = "2026-09-18"
impact = "high"
workaround = "Describe what happens, not what must not."

[[claims]]
id = "unverified"
claim = "Something we suspect but have not tested."
status = "suspected"
+++

Prose about the model.
"""


class FrontmatterTests(unittest.TestCase):
    def test_header_and_body_are_split(self) -> None:
        header, body = parse_frontmatter(PRACTICE, Path("x.md"))
        self.assertEqual(header["id"], "test-practice")
        self.assertTrue(body.startswith("The body explains"))

    def test_missing_fence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            parse_frontmatter("no header here", Path("x.md"))

    def test_unclosed_fence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            parse_frontmatter('+++\nid = "x"\n', Path("x.md"))


class KnowledgeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "knowledge" / "practices").mkdir(parents=True)
        (self.root / "knowledge" / "providers").mkdir(parents=True)

    def write_practice(self, name: str, text: str) -> Path:
        path = self.root / "knowledge" / "practices" / name
        path.write_text(text, encoding="utf-8")
        return path

    def write_provider(self, name: str, text: str) -> Path:
        path = self.root / "knowledge" / "providers" / name
        path.write_text(text, encoding="utf-8")
        return path


class PracticeTests(KnowledgeTestCase):
    def test_project_practices_are_loaded_alongside_built_ins(self) -> None:
        self.write_practice("test-practice.md", PRACTICE)
        practices = load_practices(self.root)
        ids = {practice.id for practice in practices}
        self.assertIn("test-practice", ids)
        self.assertIn("line-of-action", ids)  # built-in

        mine = next(item for item in practices if item.id == "test-practice")
        self.assertEqual(mine.origin, "project")
        self.assertEqual(mine.cost, "5 discarded versions")
        self.assertTrue(mine.enforced)

    def test_a_project_practice_overrides_a_built_in_by_id(self) -> None:
        self.write_practice(
            "line-of-action.md",
            '+++\nid = "line-of-action"\ntitle = "Ours"\nstatus = "convention"\n+++\n\nLocal.\n',
        )
        practice = next(
            item for item in load_practices(self.root) if item.id == "line-of-action"
        )
        self.assertEqual(practice.title, "Ours")
        self.assertEqual(practice.origin, "project")

    def test_claiming_an_unknown_check_is_rejected(self) -> None:
        self.write_practice(
            "bad.md",
            '+++\nid = "bad"\ntitle = "x"\nstatus = "convention"\n'
            'enforced_by = ["no_such_check"]\n+++\n\nBody.\n',
        )
        with self.assertRaises(ValidationError) as caught:
            load_practices(self.root)
        self.assertIn("no_such_check", str(caught.exception))

    def test_unknown_status_is_rejected(self) -> None:
        self.write_practice(
            "bad.md", '+++\nid = "bad"\ntitle = "x"\nstatus = "vibes"\n+++\n\nBody.\n'
        )
        with self.assertRaises(ValidationError):
            load_practices(self.root)

    def test_a_refuted_practice_is_not_treated_as_enforced(self) -> None:
        self.write_practice(
            "old.md",
            '+++\nid = "old"\ntitle = "x"\nstatus = "refuted"\n'
            'enforced_by = ["axis_break"]\n+++\n\nWe were wrong.\n',
        )
        practice = next(item for item in load_practices(self.root) if item.id == "old")
        self.assertFalse(practice.enforced)
        self.assertNotIn("old", [item.id for item in practices_for_check("axis_break", self.root)])


class ProviderTests(KnowledgeTestCase):
    def test_claims_are_parsed_with_status_and_date(self) -> None:
        self.write_provider("test-model.md", PROVIDER)
        profile = next(item for item in load_providers(self.root) if item.id == "test-model")
        self.assertEqual(len(profile.claims), 2)
        first = profile.claims[0]
        self.assertEqual(first.status, "measured")
        self.assertEqual(first.measured_on, "2026-09-18")
        self.assertIn("Describe what happens", first.workaround)

    def test_duplicate_claim_id_is_rejected(self) -> None:
        self.write_provider(
            "dupe.md",
            '+++\nid = "dupe"\n[[claims]]\nid = "a"\nclaim = "x"\nstatus = "measured"\n'
            '[[claims]]\nid = "a"\nclaim = "y"\nstatus = "measured"\n+++\n\nBody.\n',
        )
        with self.assertRaises(ValidationError):
            load_providers(self.root)

    def test_unknown_claim_status_is_rejected(self) -> None:
        self.write_provider(
            "bad.md",
            '+++\nid = "bad"\n[[claims]]\nid = "a"\nclaim = "x"\nstatus = "vibes"\n+++\n\nBody.\n',
        )
        with self.assertRaises(ValidationError):
            load_providers(self.root)


class CoverageTests(KnowledgeTestCase):
    def test_coverage_counts_what_software_enforces(self) -> None:
        self.write_practice("test-practice.md", PRACTICE)
        self.write_practice("still-manual.md", UNENFORCED)
        self.write_provider("test-model.md", PROVIDER)
        report = coverage(self.root)

        self.assertGreaterEqual(report.practices, 8)
        self.assertIn("still-manual", report.unenforced)
        self.assertNotIn("test-practice", report.unenforced)
        self.assertEqual(report.claims, 2)
        self.assertEqual(report.measured_claims, 1)
        self.assertIn("craft", report.by_domain)

    def test_every_built_in_check_has_recorded_reasoning(self) -> None:
        """A check nobody can explain is a check nobody will trust."""

        self.assertEqual(coverage().checks_without_practice, ())

    def test_check_codes_and_practices_stay_in_step(self) -> None:
        claimed = {code for item in load_practices() for code in item.enforced_by}
        self.assertTrue(claimed.issubset(CHECK_CODES))


if __name__ == "__main__":
    unittest.main()
