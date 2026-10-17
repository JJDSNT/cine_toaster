"""The codex-image adapter against a fake codex that answers like the real one (CT-0101)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from cine_toaster.errors import ValidationError
from cine_toaster.new_production import create_production
from cine_toaster.providers import ProviderError, ProviderNotConfigured
from cine_toaster.providers.codex_image import CodexImageProvider
from cine_toaster.references import add_reference, generate_reference, load_references

THREAD = "01a14389-c70e-7f60-9442-08df971dd2b2"


class FakeCodex:
    """Records each call; on exec, saves a picture where the real image_gen does and prints its events."""

    def __init__(self, home: Path, *, make_image: bool = True, code: int = 0) -> None:
        self.home, self.make_image, self.code, self.calls = home, make_image, code, []

    def __call__(self, argv: list[str], cwd: Path, timeout: int) -> tuple[int, str, str]:
        self.calls.append(argv)
        if argv[1:] == ["--version"]:
            return 0, "codex-cli 0.162.0\n", ""
        if self.make_image:
            folder = self.home / "generated_images" / THREAD
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "exec-1.png").write_bytes(b"a picture")
        events = [{"type": "thread.started", "thread_id": THREAD}, {"type": "turn.started"},
                  {"type": "item.completed", "item": {"type": "agent_message", "text": "Generated one image."}},
                  {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}]
        return self.code, "\n".join(json.dumps(event) for event in events), "" if not self.code else "boom"


class CodexImageTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.home = self.base / "codex-home"
        self.reference = self.base / "board.png"
        self.reference.write_bytes(b"the board")

    def provider(self, fake: FakeCodex) -> CodexImageProvider:
        return CodexImageProvider("codex", codex_home=self.home, runner=fake)

    def test_the_prompt_comes_before_the_images_and_the_picture_is_found_by_its_thread(self) -> None:
        fake = FakeCodex(self.home)
        output = self.base / "out" / "image.png"

        made = self.provider(fake).generate(prompt="a girl,  1930s", references=[self.reference], output=output)

        argv = fake.calls[0]
        self.assertEqual(argv[:6], ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "--json"])
        self.assertTrue(argv[6].endswith("Image: a girl, 1930s"))
        self.assertEqual(argv[7:], ["-i", str(self.reference)])
        self.assertEqual(output.read_bytes(), b"a picture")
        self.assertEqual((made["thread"], made["made_with"]), (THREAD, "codex-cli 0.162.0"))
        self.assertEqual(made["cost"], {"kind": "subscription quota", "usd": None})
        self.assertEqual(len(made["references"][0]["sha256"]), 64)

    def test_no_image_or_a_failure_is_an_error_not_a_picture(self) -> None:
        output = self.base / "image.png"
        with self.assertRaisesRegex(ProviderError, "made no image"):
            self.provider(FakeCodex(self.home, make_image=False)).generate(prompt="x", references=[], output=output)
        with self.assertRaisesRegex(ProviderError, "codex failed"):
            self.provider(FakeCodex(self.home, code=1)).generate(prompt="x", references=[], output=output)
        self.assertFalse(output.exists())

    def test_not_installed_is_said_with_its_remedy(self) -> None:
        provider = CodexImageProvider(codex_home=self.home, runner=FakeCodex(self.home))
        provider.binary = ""
        with self.assertRaisesRegex(ProviderNotConfigured, "codex login"):
            provider.generate(prompt="x", references=[], output=self.base / "image.png")

    def test_a_generation_becomes_a_reference_with_its_lineage(self) -> None:
        root = create_production(self.base / "film", "A Film").root
        board = add_reference(root, [self.reference], title="Board", kind="generated", made_on="2026-10-16")
        fake = FakeCodex(self.home)

        folder = generate_reference(root, prompt="her at eight, 1930s", title="1930s trial", parents=[board.name],
                                    requested_by="claude-code", runner=fake, codex_home=self.home)

        self.assertEqual(fake.calls[0][-1], str(board / "board.png"))
        record = yaml.safe_load((folder / "reference.yaml").read_text(encoding="utf-8"))
        self.assertEqual(record["from"], [board.name])
        self.assertEqual(record["kind"], "generated")
        self.assertIn("asked by claude-code", record["made_by"])
        self.assertEqual(record["generation"]["references"][0]["file"], f"references/{board.name}/board.png")
        self.assertEqual(record["generation"]["thread"], THREAD)
        self.assertTrue(all(item["findings"] == [] for item in load_references(root)))


    def test_who_how_and_what_are_composed_from_their_records(self) -> None:
        root = create_production(self.base / "film", "A Film").root
        (root / "cast" / "lia").mkdir(parents=True)
        (root / "cast" / "lia" / "character.yaml").write_text(
            "id: LIA\nlabel: Lia\ndescription: Long dark hair, a linen dress.\nauthoritative_for: [face]\n"
            "variants:\n  age-8:\n    description: about eight\n", encoding="utf-8")
        (root / "styles" / "ink").mkdir(parents=True)
        (root / "styles" / "ink" / "style.toml").write_text(
            'schema_version = 1\nid = "ink"\nname = "Ink"\nkind = "animation"\nprompt = "black ink on paper"\n',
            encoding="utf-8")
        board = add_reference(root, [self.reference], title="Board", kind="generated", made_on="2026-10-16")
        fake = FakeCodex(self.home)

        folder = generate_reference(root, prompt="She runs.", title="Trial", parents=[board.name], cast="LIA@age-8",
                                    style="ink", runner=fake, codex_home=self.home)

        sent = fake.calls[0][6]
        self.assertIn("never their drawing style", sent)
        self.assertIn("Who: Lia. Long dark hair, a linen dress. Here: about eight.", sent)
        self.assertIn("How it is drawn: black ink on paper.", sent)
        self.assertTrue(sent.endswith("What happens: She runs."))
        record = yaml.safe_load((folder / "reference.yaml").read_text(encoding="utf-8"))
        self.assertEqual(record["generation"]["composed_from"], {"cast": "LIA@age-8", "style": "ink", "shot": "She runs."})
        with self.assertRaisesRegex(ValidationError, "no variant 'age-90'"):
            generate_reference(root, prompt="x", title="T2", cast="LIA@age-90", runner=fake, codex_home=self.home)


if __name__ == "__main__":
    unittest.main()
