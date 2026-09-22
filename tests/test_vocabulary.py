"""The schema is English (ADR 0013), and legacy names still load."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cine_toaster import vocabulary
from cine_toaster.project import load_production


LEGACY_PROJECT = """\
schema_version: 1
id: legacy
titulo: Legacy Production
formato: Short
caminhos:
  cenas: cenas
producao:
  cena_ativa: SC-010
sequencias:
  - id: one
    rotulo: Opening
    ato: Act I
    cenas: ["SC-010"]
"""

LEGACY_SCENE = """\
cena: SC-010
ordem: 10
titulo: Opening
situacao: Waiting on masters.
direcao: |
  Keep her on the right.
planos:
  - n: 1
    tipo: preto
    dur: 3
    plano: Black screen.
  - n: 2
    dur: 8
    sujeito: MARA
    olha_para: SPEAKER
    plano: She adjusts the receiver.
    atuacao: One blink, or none.
"""

CANONICAL_PROJECT = LEGACY_PROJECT.replace("titulo:", "title:").replace(
    "formato:", "format:"
).replace("caminhos:", "paths:").replace("  cenas: cenas", "  scenes: scenes").replace(
    "producao:", "production:"
).replace("  cena_ativa:", "  active_scene:").replace("sequencias:", "sequences:").replace(
    "    rotulo:", "    label:"
).replace("    ato:", "    act:").replace('    cenas: ["SC-010"]', '    scenes: ["SC-010"]')

CANONICAL_SCENE = (
    LEGACY_SCENE.replace("cena:", "scene:")
    .replace("ordem:", "order:")
    .replace("titulo:", "title:")
    .replace("situacao:", "summary:")
    .replace("direcao:", "direction:")
    .replace("planos:", "shots:")
    .replace("    tipo: preto", "    kind: black")
    .replace("    dur:", "    duration:")
    .replace("    plano:", "    label:")
    .replace("    sujeito:", "    subject:")
    .replace("    olha_para:", "    looks_at:")
    .replace("    atuacao:", "    action:")
)


def _write(root: Path, manifest: str, scene: str, scenes_dir: str, scene_file: str) -> None:
    (root / scenes_dir / "010-opening").mkdir(parents=True)
    (root / "project.yaml").write_text(manifest, encoding="utf-8")
    (root / scenes_dir / "010-opening" / scene_file).write_text(scene, encoding="utf-8")


class VocabularyTests(unittest.TestCase):
    def test_canonical_and_legacy_files_load_identically(self) -> None:
        loaded = []
        for manifest, scene, directory, filename in (
            (CANONICAL_PROJECT, CANONICAL_SCENE, "scenes", "scene.yaml"),
            (LEGACY_PROJECT, LEGACY_SCENE, "cenas", "decupagem.yaml"),
        ):
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                _write(root, manifest, scene, directory, filename)
                production = load_production(root)
            scene_data = production["scenes"][0]
            loaded.append(
                {
                    "title": production["title"],
                    "format": production["format"],
                    "active": production["active_scene"]["id"],
                    "sequence": production["sequences"][0]["label"],
                    "act": production["sequences"][0]["act"],
                    "scene_title": scene_data["title"],
                    "summary": scene_data["summary"],
                    "direction": scene_data["direction"],
                    "kinds": [shot["kind"] for shot in scene_data["shots"]],
                    "labels": [shot["label"] for shot in scene_data["shots"]],
                    "subject": scene_data["shots"][1]["subject"],
                    "looks_at": scene_data["shots"][1]["looks_at"],
                    "action": scene_data["shots"][1]["description"],
                    "durations": [shot["duration_seconds"] for shot in scene_data["shots"]],
                }
            )
        self.assertEqual(loaded[0], loaded[1])
        self.assertEqual(loaded[0]["kinds"][0], "black")
        self.assertEqual(loaded[0]["title"], "Legacy Production")

    def test_canonical_name_wins_over_legacy(self) -> None:
        document = {"title": "English", "titulo": "Portugues"}
        self.assertEqual(vocabulary.field(document, "title"), "English")

    def test_legacy_shot_kinds_normalize(self) -> None:
        for legacy, canonical in vocabulary.LEGACY_SHOT_KINDS.items():
            self.assertEqual(vocabulary.shot_kind(legacy), canonical)
            self.assertIn(canonical, vocabulary.GENERATED_NOTHING)

    def test_no_legacy_names_leak_into_the_domain_model(self) -> None:
        """A loaded production exposes English keys only (ADR 0013)."""

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _write(root, LEGACY_PROJECT, LEGACY_SCENE, "cenas", "decupagem.yaml")
            production = load_production(root)

        legacy_names = {name for names in vocabulary.LEGACY_KEYS.values() for name in names}
        seen: set[str] = set()

        def walk(node: object) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    seen.add(str(key))
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        # `production` echoes the authored block verbatim by design; the rest of
        # the model must not.
        production.pop("production", None)
        walk(production)
        self.assertEqual(seen & legacy_names, set())


if __name__ == "__main__":
    unittest.main()
