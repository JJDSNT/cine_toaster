"""Migrating SINGULAR into Cine Toaster's own format (CT-0054)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from cine_toaster.errors import ValidationError
from cine_toaster.migrate import compare, migrate, read_versoes


def write(path: Path, text: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text) if isinstance(text, bytes) else path.write_text(textwrap.dedent(text), encoding="utf-8")


BREAKDOWN = """\
    # SINGULAR — cena 9-01, versão LTX
    cena: "9-01"
    variante: ltx
    titulo: "O teste — versão LTX"
    fonte: "#9-1#"
    motor: ltx
    ambiente: camara
    look: CAMARA
    looks:
      CAMARA: soft omnidirectional light
    personagens:
      KAEL: a tired man in his forties
    fichas:
      KAEL: kael_boreal
    vozes:
      KAEL: a low, controlled male voice
    direcao: Tudo começa no escuro.
    planos:
      - n: 1
        tipo: preto
        plano: Tela preta.
        dur: 2
        som: [respiracao]
        texto_tela: "04:02"
        corpo: 20
        cor_texto: "0x8C8F96"
        pos: rodape
        fade: 1.0
        escurece: 3.0
      - n: 2
        tipo: ltx
        plano: Kael acorda.
        dur: 3
        seg: 4
        atuacao: he opens his eyes
        som: a quiet room hum
        falas:
          - {quem: KAEL, en: "Claire...", pt: "Claire...", emocao: sad}
          - {quem: NARRADOR, en: "Long ago.", pt: "Há muito tempo.", montagem: {arquivo: trabalho/vozes/vo-01.wav, em: 1.8}}
        corte: {antes: 0.4, depois: 0.3}
        quadro: a man in a bed
        silenciar: [[0.0, 1.0]]
        som_baixa_de: 2.5
        espelhar: true
        montagem_pov: true
      - n: 3
        tipo: ltx
        plano: Dela.
        dur: 2
        usa_ultimo_de: 2
        deriva: {de: 2, com: [KAEL], pedido: The man becomes Kael.}
      - n: 4
        tipo: ltx
        plano: O quarto.
        dur: 2
        usa_arquivo: ../../../cenarios/quarto/blockout/A.png
        ref: false
      - n: 5
        tipo: ltx
        plano: De outra cena.
        dur: 2
        reusa: 1-02/ltx c03
"""


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        self.previous = {key: os.environ.get(key) for key in ("XDG_CACHE_HOME", "XDG_STATE_HOME")}
        os.environ["XDG_CACHE_HOME"], os.environ["XDG_STATE_HOME"] = str(base / "cache"), str(base / "state")
        self.addCleanup(self._restore)
        self.source = base / "confyui" / "singular"
        self.target = base / "films" / "singular"
        s = self.source
        write(s / "project.yaml", """\
            schema_version: 1
            id: singular
            titulo: SINGULAR
            caminhos: {cenas: cenas, roteiro: roteiro/v4}
            words_sidecar: "{stem}.palavras.json"
            producao: {fase: producao, cena_ativa: "9-01", variante: ltx}
            sequencias:
              - {id: teste, rotulo: Teste, cenas: ["9-01"]}
            shot_fields:
              seg: {label: segundos gerados, maps_to: generated_seconds}
              quadro: {label: quadro inicial (prompt)}
              fala: {label: fala, maps_to: lines}
              corte: {label: aparo do clipe, maps_to: trim}
            """)
        write(s / "cenas" / "9-01" / "decupagem.yaml", "cena: '9-01'\ntitulo: O teste\nplanos: []\n")
        write(s / "cenas" / "9-01" / "ltx" / "decupagem.yaml", BREAKDOWN)
        work = s / "cenas" / "9-01" / "ltx" / "trabalho"
        write(work / "c02.mp4", b"take")
        write(work / "c02-pov.mp4", b"the take through SINGULAR's POV montage")
        write(work / "c02.palavras.json", "[]")
        write(work / "_tomadas" / "c02-t2.mp4", b"another take")
        write(work / "_descartados" / "c02-errado.mp4", b"rejected")
        write(work / "partes" / "junto.mp4", b"scratch")
        write(work / "clipes.log", "scratch")
        versions = s / "cenas" / "9-01" / "ltx" / "versoes"
        for number in (1, 2, 3):
            write(versions / f"cena-9-01-ltx-v{number}.mp4", f"cut {number}".encode())
        write(versions / "decupagem-v2.yaml", BREAKDOWN)
        write(versions / "VERSOES.md", """\
            | versão | data | duração | o que mudou | notas do autor |
            |---|---|---|---|---|
            | v1 | 17/09 10:00 | 80 s | primeira | "o olhar está errado" |
            | v2 | 17/09 11:00 | 81 s | segunda | *(não enviada: ainda errado)* |
            | v3 | 17/09 12:00 | 82 s | terceira | ✅ **aprovada pelo autor** |
            """)
        write(s / "elenco" / "fichas" / "kael_boreal.png", b"face")
        write(s / "cenarios" / "quarto" / "blockout" / "A.png", b"set")
        write(s / "cenarios" / "quarto" / "FICHA.md", "# O quarto\n\n**PROPOSTA.** Cena: **9-01**.\n\n"
              "Um quarto pequeno, luz fria.\n\n```\nblender ...\n```\n")
        write(s / "roteiro" / "v4" / "roteiro.fountain", "INT. TESTE - NOITE\n")
        self.before = self.digest(s)

    def _restore(self) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @staticmethod
    def digest(folder: Path) -> str:
        hashed = hashlib.sha256()
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                hashed.update(path.relative_to(folder).as_posix().encode() + path.read_bytes())
        return hashed.hexdigest()

    def test_the_film_arrives_in_the_native_layout_with_its_history(self) -> None:
        report = migrate(self.source, self.target, git=False)
        t = self.target
        self.assertEqual(self.digest(self.source), self.before)  # the source is never written
        scene_dir = t / "scenes" / "9-01-o-teste"  # the scene's own title, not its variant's
        scene = yaml.safe_load((scene_dir / "scene.yaml").read_text(encoding="utf-8"))
        self.assertEqual((scene["scene"], scene["title"], scene["ambience"]), ("9-01", "O teste", {"id": "station-hum"}))
        self.assertNotIn("variant", scene)
        self.assertNotIn("personagens", scene)  # moved to the cast sheet
        self.assertNotIn("voices", scene)  # the same as the sheet's: not repeated
        first, second, third, fourth, fifth = scene["shots"]
        # On-screen text as a title from the catalog; picture operations as effects; sound cuts as native fields.
        self.assertEqual(first["title"], {"id": "card", "text": "04:02", "size": 20, "color": "#8C8F96",
                                          "position": "bottom", "fade_in": 1.0, "fade_out": 0.001, "enter_at": 0.0,
                                          "spaced": True})
        self.assertEqual(first["effects"], [{"id": "fade-to-black", "length": 3.0}])
        self.assertEqual((second["mute"], second["sound_fades_at"], second["effects"]),
                         ([[0.0, 1.0]], 2.5, [{"id": "mirror"}]))
        self.assertEqual(second["trim"], {"before": 0.4, "after": 0.3, "in": 0.0})  # the POV montage's opening kept
        # The production: SINGULAR's scope frame and its subtitles, natively.
        project = yaml.safe_load((t / "project.yaml").read_text(encoding="utf-8"))
        self.assertEqual((project["style"], project["subtitles"]), ({"format": "feature-scope"}, {"burn": True}))
        # SINGULAR's source fields as native relations, its edits as `derive`, its outside paths moved.
        self.assertEqual(third["from"], [{"ref": "2", "relation": "last_frame_of"}])
        self.assertEqual(third["derive"], {"from": "2", "with": ["KAEL"], "request": "The man becomes Kael."})
        self.assertEqual(fourth["from"], [{"ref": "../../locations/quarto/blockout/A.png", "relation": "file"}])
        self.assertFalse(fourth["cast_references"])
        self.assertEqual(fifth["from"], [{"ref": "1-02 c03", "relation": "reuses"}])
        self.assertTrue((scene_dir / fourth["from"][0]["ref"]).is_file())
        # The set its sheet names the scene in, as a location the scene is shot in.
        self.assertEqual(scene["location"], "QUARTO")
        location = yaml.safe_load((self.target / "locations" / "quarto" / "location.yaml").read_text(encoding="utf-8"))
        self.assertEqual((location["label"], location["description"], location["scenes"]),
                         ("O quarto", "Um quarto pequeno, luz fria.", ["9-01"]))
        self.assertEqual(location["references"], [{"path": "blockout/A.png", "kind": "blockout"}])
        self.assertEqual((first["kind"], first["label"], first["sounds"]), ("black", "Tela preta.", ["breath"]))
        self.assertEqual((second["sound"], second["generated_seconds"]), ("a quiet room hum", 4))
        self.assertEqual(second["lines"][0]["who"], "KAEL")
        # A voice laid in the montage: its file and its time, natively; not said in the take.
        self.assertEqual(second["lines"][1]["mix"], {"file": "work/vozes/vo-01.wav", "at": 1.8})
        self.assertEqual(second["picture"], "a man in a bed")  # SINGULAR's `quadro`
        # Takes kept, renamed to the canonical folders; a run's scratch left behind.
        work = scene_dir / "work"
        self.assertTrue((work / "_takes" / "c02-t2.mp4").is_file())
        self.assertTrue((work / "_rejected" / "c02-errado.mp4").is_file())
        self.assertFalse((work / "partes").exists() or (work / "clipes.log").exists())
        # The other breakdown, archived; the cuts and the breakdown that made one.
        self.assertTrue((scene_dir / "archive" / "main" / "decupagem.yaml").is_file())
        self.assertTrue((scene_dir / "versions" / "v2.decupagem.yaml").is_file())
        # The versions are the scene's records, with the author's verdicts, and the index says so.
        from cine_toaster.project import load_scene

        loaded = load_scene(t, "9-01")
        # SINGULAR cuts shot 2 through its POV montage: that take is selected, as a decision of the migration.
        self.assertEqual(next(shot for shot in loaded["shots"] if shot["id"] == "P2")["selected_take"], "POV")
        verdicts = {item["id"]: item["verdict"] for item in loaded["assemblies"]}
        self.assertEqual(verdicts, {"v1": "rejected", "v2": "not_sent", "v3": "approved"})
        index = (scene_dir / "versions" / "VERSIONS.md").read_text(encoding="utf-8")
        self.assertIn("Approved: **v3**", index)
        history = (scene_dir / "history.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(history), 4)  # three versions imported, and the POV take chosen
        self.assertIn("POV montage", history[-1])
        # The cast sheet, gathered from the scene.
        sheet = yaml.safe_load((t / "cast" / "kael" / "character.yaml").read_text(encoding="utf-8"))
        self.assertEqual(sheet["voice"]["identity"], "a low, controlled male voice")
        self.assertEqual(sheet["variants"]["kael_boreal"]["references"][0]["path"], "../library/fichas/kael_boreal.png")
        self.assertTrue((t / "looks" / "CAMARA" / "look.yaml").is_file())
        # The overview, the report, and nothing read differently than in the original.
        self.assertIn("✅ v3", (t / "README.md").read_text(encoding="utf-8"))
        self.assertIn("cast_references", (t / "MIGRATION.md").read_text(encoding="utf-8"))
        self.assertEqual(report.scenes[0]["versions"], 3)
        self.assertEqual([item for item in compare(self.source, t) if "findings" not in item], [])

    def test_a_target_is_never_overwritten_unless_it_is_an_earlier_migration(self) -> None:
        write(self.target / "my-notes.txt", "mine")
        with self.assertRaisesRegex(ValidationError, "not made by a migration"):
            migrate(self.source, self.target, git=False)
        shutil.rmtree(self.target)
        migrate(self.source, self.target, git=False)
        with self.assertRaisesRegex(ValidationError, "pass replace"):
            migrate(self.source, self.target, git=False)
        migrate(self.source, self.target, replace=True, git=False)
        self.assertTrue((self.target / ".migrated-from").is_file())

    def test_versoes_rows(self) -> None:
        rows = read_versoes(self.source / "cenas" / "9-01" / "ltx" / "versoes" / "VERSOES.md", 2026)
        self.assertEqual([(row["id"], row["created_at"], row["duration_seconds"]) for row in rows],
                         [("v1", "2026-09-17T10:00:00", 80.0), ("v2", "2026-09-17T11:00:00", 81.0),
                          ("v3", "2026-09-17T12:00:00", 82.0)])


if __name__ == "__main__":
    unittest.main()
