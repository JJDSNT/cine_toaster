"""Migrating SINGULAR into Cine Toaster's own format (CT-0054, ADR 0021).

    toast migrate singular ~/confyui/singular ~/films/singular

Reads the production where it is, never writing there, and writes a new
directory in Cine Toaster's native layout and schema:

    project.yaml  README.md  MIGRATION.md
    story/        the book, the screenplay and its versions, the proposals
    cast/         one sheet per character, gathered from every scene; library/ the original material
    locations/    the sets' reference material
    look/         the aesthetic (LUTs, visual grammar, worlds)
    sounds/       the library, each recording a catalog item with its licence
    scenes/<id>-<slug>/
        scene.yaml    the active breakdown, in the English schema
        work/         takes, pictures and their sidecars (_takes, _rejected)
        versions/     every cut with the breakdown that made it, VERSIONS.md
        review/       review PDFs
        archive/      the other breakdown and its material, tests
    sequences/<id>/versions/
    docs/  knowledge/  archive/

What it cannot place natively stays, under its original key, declared in
`project.yaml`; `MIGRATION.md` lists what was converted, approximated and
left as it was. Repeatable: a target made by an earlier run (it carries
`.migrated-from`) is replaced with `replace=True`; any other non-empty
target is refused.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ValidationError

MARKER = ".migrated-from"

#: SINGULAR's ambience beds (`ambiente`), as the sound catalog's items (CT-0048).
AMBIENCES = {"camara": "station-hum", "corredor": "corridor-hum", "quarto_genebra": "hospital-room",
             "corredor_hospital": "air-conditioning", "cidade_amanhecer": "city-distant", "prologo": "low-pulse"}
#: SINGULAR's montage effects (`som` as a list, `som_montagem`), as catalog items.
EFFECTS = {"respiracao": "breath", "estrondo": "boom", "porta": "door", "bip": "beep",
           "bip_dissonante": "dissonant-beep", "tom_continuo": "flatline", "alarme": "alarm"}

#: Scene keys renamed to the English schema, meaning unchanged.
SCENE_KEYS = {"cena": "scene", "titulo": "title", "direcao": "direction", "decisoes": "decisions",
              "geografia": "geography", "planos": "shots", "variante": "variant", "motor": "engine",
              "situacao": "summary", "ordem": "order", "sequencia": "sequence", "impedimentos": "blockers",
              "vozes": "voices", "sujeitos": "refer_as", "fichas": "cast"}
#: Scene keys already in the native schema.
SCENE_CANONICAL = {"look", "script", "location", "cast", "voices", "refer_as", "voice_state", "ambience", "music",
                   "style", "enter", "deliver", "surround", "geography"}
#: Shot keys renamed, meaning unchanged.
SHOT_KEYS = {"tipo": "kind", "plano": "label", "dur": "duration", "atuacao": "action", "falas": "lines",
             "fora_do_corte": "out_of_cut", "seg": "generated_seconds", "bloco": "block", "corte": "trim",
             "nivel": "level_db", "quem": "in_frame",
             # What the video model is told the starting picture shows (cena_ltx.py `prompt`: `quadro`).
             "quadro": "picture"}
LINE_KEYS = {"quem": "who", "como": "delivery", "voz": "voice", "fora": "off_screen", "emocao": "emotion_hint",
             "velocidade": "pace", "montagem": "mix"}
#: A voice laid in the montage (`falas: [{montagem: {arquivo, em}}]`): its file and its time in the shot.
MIX_KEYS = {"arquivo": "file", "em": "at"}
DECISION_KEYS = {"pergunta": "question", "proposta": "proposal", "resposta": "answer"}
GEOGRAPHY_KEYS = {"sala": "room", "pessoas": "subjects", "altura_olhos": "eye_height", "altura": "height",
                  "mira": "target", "lente": "lens_mm", "eixo": "axis", "objetos": "objects"}
TRIM_KEYS = {"antes": "before", "depois": "after", "inicio": "in", "fim": "out", "ate_o_fim": "to_end"}
#: SINGULAR's source fields, read in the order Cine Toaster's reader reads them, as native relations
#: (their meaning from SINGULAR's cena_ltx.py: `origem`, `ultimo_quadro`).
SOURCE_RELATIONS = {"usa": "picture_of", "usa_de": "picture_of", "usa_arquivo": "file",
                    "usa_ultimo_de": "last_frame_of", "reusa": "reuses"}
KINDS = {"preto": "black", "branco": "white", "cartela": "title_card", "imagem": "image", "trecho": "clip"}
#: Media a work folder keeps: takes, pictures, voices and their sidecars; the rest is a run's scratch.
KEEP_SUFFIXES = (".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".wav", ".mp3", ".json")
SKIP_WORK = ("partes",)


@dataclass
class Report:
    converted: list[str] = field(default_factory=list)
    approximated: list[str] = field(default_factory=list)
    #: SINGULAR's own fields, kept as written and declared in project.yaml: no native home yet.
    kept: dict[str, int] = field(default_factory=dict)
    #: Fields Cine Toaster reads through its legacy vocabulary (LEGACY_KEYS): understood, to be rewritten natively.
    legacy: dict[str, int] = field(default_factory=dict)
    copied_files: int = 0
    copied_bytes: int = 0
    scenes: list[dict[str, Any]] = field(default_factory=list)

    def keep(self, key: str) -> None:
        self.kept[key] = self.kept.get(key, 0) + 1

    def read_as_legacy(self, key: str) -> None:
        self.legacy[key] = self.legacy.get(key, 0) + 1


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:40] or "scene"


# --- copying -------------------------------------------------------------------------


def _copy(source: Path, target: Path, report: Report, *, skip=lambda path: False,
          rename: dict[str, str] | None = None) -> None:
    """Copy a file or a tree (never hard links: SINGULAR's tools overwrite in place)."""

    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report.copied_files += 1
        report.copied_bytes += source.stat().st_size
        return
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if skip(relative) or not path.is_file():
            continue
        parts = [(rename or {}).get(part, part) for part in relative.parts]
        destination = target.joinpath(*parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report.copied_files += 1
        report.copied_bytes += path.stat().st_size


def _work_skip(relative: Path) -> bool:
    return (relative.parts[0] in SKIP_WORK or relative.suffix.lower() not in KEEP_SUFFIXES)


# --- the breakdown --------------------------------------------------------------------


def _rewrite_paths(value: Any, prefixes: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        for old, new in prefixes:
            if value.startswith(old):
                return new + value[len(old):]
        return value
    if isinstance(value, list):
        return [_rewrite_paths(item, prefixes) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_paths(item, prefixes) for key, item in value.items()}
    return value


def _rename(document: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    renamed = {mapping.get(key, key): value for key, value in document.items()}
    if mapping is LINE_KEYS and isinstance(renamed.get("mix"), dict):
        renamed["mix"] = _rename(renamed["mix"], MIX_KEYS)
    return renamed


def convert_scene(document: dict[str, Any], report: Report, scene_id: str,
                  identities: dict[str, str] | None = None) -> dict[str, Any]:
    """A SINGULAR breakdown in the English schema; what has no native home is kept as it was.

    `identities` are the cast sheets' voices: a scene's voice that only repeats one is dropped (the sheet
    owns it); one that differs stays, and the check asks the author to split identity from state.
    """

    from .cast import cast_key

    out: dict[str, Any] = {}
    for key, value in document.items():
        if key == "vozes" and isinstance(value, dict) and identities:
            kept = {name: text for name, text in value.items()
                    if " ".join(str(text).split()) != identities.get(cast_key(name))}
            if len(kept) < len(value):
                report.converted.append(f"{scene_id}: {len(value) - len(kept)} voice(s) the cast sheet now owns, "
                                        "not repeated")
            if kept:
                out["voices"] = kept
            continue
        if key == "ambiente":
            bed: dict[str, Any] = {"id": AMBIENCES.get(str(value), str(value))}
            if document.get("ambiente_ate"):
                bed["duration"] = float(document["ambiente_ate"])
            out["ambience"] = bed
            report.converted.append(f"{scene_id}: ambiente {value!r} -> ambience {bed['id']!r}"
                                    + (f" for {bed['duration']} s" if "duration" in bed else ""))
        elif key in ("ambiente_ate", "variante"):
            # The migrated breakdown is the scene, no longer one of its variants; the engine says what made it.
            continue
        elif key in ("personagens", "looks"):
            continue  # moved whole into the cast sheets and the look definitions (see _cast, _looks)
        elif key in SCENE_CANONICAL:
            out[key] = value
        elif key == "fonte":
            out["source_ref"] = value  # the book's / screenplay's anchor, as SINGULAR wrote it
            report.keep("scene.fonte (as source_ref)")
        elif key == "decisoes":
            out["decisions"] = [_rename(item, DECISION_KEYS) if isinstance(item, dict) else item for item in value or []]
        elif key == "geografia":
            out["geography"] = _rename(value, GEOGRAPHY_KEYS) if isinstance(value, dict) else value
        elif key == "planos":
            out["shots"] = [convert_shot(shot, report, scene_id) for shot in value or []]
        elif key in SCENE_KEYS:
            out[SCENE_KEYS[key]] = value
        else:
            out[key] = value
            report.keep(f"scene.{key}")
    return out


#: SINGULAR's montage fields that become a title, effects or sound fields (from cena_ltx.py: `cartela`, the clip's vf/af).
MONTAGE = {"texto_tela", "corpo", "cor_texto", "pos", "fade", "texto_entra", "espacado", "escurece", "espelhar",
           "recorte", "silenciar", "som_baixa_de", "so_a_luz", "entra_sai"}
POSITIONS = {"rodape": "bottom", "alto": "top"}
#: The frame SINGULAR's LTX takes are made at: `recorte` is in its pixels.
TAKE_FRAME = (1280, 704)


def _montage(shot: dict[str, Any], report: Report, scene_id: str) -> dict[str, Any]:
    """SINGULAR's on-screen text, picture operations and sound cuts, as a title, effects and native fields."""

    out: dict[str, Any] = {}
    where = f"{scene_id} P{shot.get('n')}"
    effects = []
    if shot.get("texto_tela"):
        fade = float(shot.get("fade", 0.9))
        colour = str(shot.get("cor_texto") or "0xE6E6E6")
        out["title"] = {"id": "card", "text": str(shot["texto_tela"]), "size": int(shot.get("corpo", 34)),
                        "color": "#" + colour[2:] if colour.lower().startswith("0x") else colour,
                        "position": POSITIONS.get(str(shot.get("pos") or ""), "centre"),
                        "fade_in": fade, "fade_out": 0.001 if shot.get("escurece") else fade,
                        "enter_at": float(shot.get("texto_entra", 0)), "spaced": bool(shot.get("espacado", True))}
        report.converted.append(f"{where}: on-screen text -> title card ({out['title']['text'][:30]!r})")
    if shot.get("escurece"):
        effects.append({"id": "fade-to-black", "length": float(shot["escurece"])})
        report.converted.append(f"{where}: escurece {shot['escurece']} -> fade-to-black")
    if shot.get("espelhar"):
        effects.append({"id": "mirror"})
        report.converted.append(f"{where}: espelhar -> mirror")
    if shot.get("recorte"):
        w, h, x, y = (float(value) for value in shot["recorte"])
        width, height = TAKE_FRAME
        effects.append({"id": "crop", "x": round(x / width, 4), "y": round(y / height, 4),
                        "width": round(w / width, 4), "height": round(h / height, 4)})
        report.approximated.append(f"{where}: recorte in pixels -> crop as fractions of a {width}x{height} take")
    if effects:
        out["effects"] = effects
    if shot.get("silenciar"):
        out["mute"] = [[float(a), float(b)] for a, b in shot["silenciar"]]
        report.converted.append(f"{where}: silenciar -> mute {out['mute']}")
    if shot.get("som_baixa_de") is not None:
        out["sound_fades_at"] = float(shot["som_baixa_de"])
        report.converted.append(f"{where}: som_baixa_de -> sound_fades_at {out['sound_fades_at']}")
    return out


def convert_shot(shot: dict[str, Any], report: Report, scene_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    sources = []
    for key in ("usa", "usa_de", "usa_arquivo", "usa_ultimo_de", "reusa"):
        if shot.get(key) not in (None, "", [], {}):
            values = shot[key] if isinstance(shot[key], list) else [shot[key]]
            for value in values:
                ref = str(value)
                if key == "reusa":
                    # "1-02/ltx c03": a clip of another scene's variant; variants are gone, the scene remains.
                    ref = re.sub(r"^([^/\s]+)/[^\s]+\s+", r"\1 ", ref)
                sources.append({"ref": ref, "relation": SOURCE_RELATIONS[key]})
    if sources:
        out["from"] = sources
        report.converted.append(f"{scene_id} P{shot.get('n')}: source fields -> from "
                                + ", ".join(f"{item['relation']} {item['ref']}" for item in sources))
    montage = _montage(shot, report, scene_id)
    if str(shot.get("tipo") or "") == "imagem" and not shot.get("fora_do_corte"):
        # An auxiliary picture (another shot's montage uses it); SINGULAR never cuts `imagem` shots in.
        out["out_of_cut"] = True
        report.converted.append(f"{scene_id} P{shot.get('n')}: an auxiliary picture -> out_of_cut")
    for key, value in shot.items():
        if key in SOURCE_RELATIONS or key in MONTAGE:
            continue
        if key == "deriva" and isinstance(value, dict):
            cast = value.get("com") or []
            out["derive"] = {"from": str(value.get("de") if value.get("de") is not None else ""),
                             "with": cast if isinstance(cast, list) else [cast], "request": value.get("pedido") or ""}
            for extra in sorted(set(value) - {"de", "com", "pedido"}):
                out["derive"][extra] = value[extra]
                report.approximated.append(f"{scene_id} P{shot.get('n')}: deriva.{extra} kept on derive")
            report.converted.append(f"{scene_id} P{shot.get('n')}: deriva -> derive (a picture edit with "
                                    f"{', '.join(map(str, out['derive']['with'])) or 'no cast'})")
            continue
        if key == "ref" and value is False:
            out["cast_references"] = False  # SINGULAR: no face edit for this shot's picture
            report.keep("shot.cast_references")
            continue
        if key == "tipo":
            out["kind"] = KINDS.get(str(value), value)
        elif key == "som":
            if isinstance(value, list):
                out["sounds"] = [EFFECTS.get(str(item), str(item)) for item in value]
                report.converted.append(f"{scene_id} P{shot.get('n')}: som {value} -> sounds {out['sounds']}")
            else:
                out["sound"] = value
        elif key == "som_montagem":
            out.setdefault("sounds", [])
            out["sounds"] += [EFFECTS.get(str(item), str(item)) for item in value or []]
            report.converted.append(f"{scene_id} P{shot.get('n')}: som_montagem {value} -> sounds")
        elif key == "fala" and isinstance(value, dict):
            out["lines"] = [_rename(value, LINE_KEYS)]
            report.approximated.append(f"{scene_id} P{shot.get('n')}: fala (one line, its emocao kept as emotion_hint)")
        elif key == "falas":
            out["lines"] = [_rename(item, LINE_KEYS) if isinstance(item, dict) else item for item in value or []]
        elif key == "corte" and isinstance(value, dict):
            out["trim"] = _rename(value, TRIM_KEYS)
        elif key in SHOT_KEYS:
            out[SHOT_KEYS[key]] = value
            from .vocabulary import CORE_SHOT_FIELDS

            if SHOT_KEYS[key] not in CORE_SHOT_FIELDS:
                report.keep(f"shot.{SHOT_KEYS[key]}")  # renamed to English, still SINGULAR's own: declared
        else:
            from .vocabulary import CORE_SHOT_FIELDS, KNOWN_SHOT_FIELDS

            out[key] = value
            if key in CORE_SHOT_FIELDS:
                continue
            if key in KNOWN_SHOT_FIELDS:
                report.read_as_legacy(f"shot.{key}")
            else:
                report.keep(f"shot.{key}")
    out.update(montage)
    if shot.get("so_a_luz"):
        out["holds"] = "light"  # SINGULAR: only the light changes
        report.converted.append(f"{scene_id} P{shot.get('n')}: so_a_luz -> holds: light")
    elif shot.get("entra_sai"):
        out["holds"] = "open"  # SINGULAR: someone enters or leaves on purpose
        report.converted.append(f"{scene_id} P{shot.get('n')}: entra_sai -> holds: open")
    if shot.get("montagem_pov"):
        # SINGULAR keeps a POV montage's opening (cena_ltx.py `corte`: ini_min = 0 for montagem_pov): the effect
        # starts at the first frame. An explicit cut-in at 0 says the same here.
        out["trim"] = {**(out.get("trim") or {}), "in": 0.0}
        report.converted.append(f"{scene_id} P{shot.get('n')}: montagem_pov -> trim.in 0 (the montage's opening kept)")
    return out


# --- versions ---------------------------------------------------------------------------


ROW = re.compile(r"^\|\s*(v\d+)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|")


def read_versoes(path: Path, year: int) -> list[dict[str, Any]]:
    """SINGULAR's VERSOES.md: one row a version -- date, length, what changed, the author's notes."""

    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if not match:
            continue
        version, when, length, changed, notes = (part.strip() for part in match.groups())
        stamp = ""
        date = re.match(r"(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", when)
        if date:
            day, month, hour, minute = date.groups()
            stamp = datetime.datetime(year, int(month), int(day), int(hour or 0), int(minute or 0)).isoformat()
        seconds = re.match(r"(\d+(?:[.,]\d+)?)", length)
        lowered = notes.lower()
        if "✅" in notes and "aprovad" in lowered:
            verdict = "approved"
        elif "não enviada" in lowered or "nao enviada" in lowered:
            verdict = "not_sent"  # reviewed internally, never shown to the author
        elif notes.strip(" *_—-"):
            verdict = "rejected"  # the author's notes on a version sent to them: what had to change
        else:
            verdict = "pending"
        rows.append({"id": version, "created_at": stamp, "duration_seconds": float(seconds.group(1).replace(",", "."))
                     if seconds else 0.0, "summary": changed, "note": notes, "verdict": verdict})
    return rows


def _import_versions(source_versions: Path, scene_dir: Path, scene_id: str, cut_prefix: str, report: Report,
                     year: int) -> list[dict[str, Any]]:
    """Copy every cut and breakdown snapshot; return the versions as records."""

    rows = {row["id"]: row for row in read_versoes(source_versions / "VERSOES.md", year)}
    target = scene_dir / "versions"
    found = []
    for video in sorted(source_versions.glob(f"{cut_prefix}-v*.mp4"), key=lambda p: int(re.search(r"-v(\d+)", p.name).group(1))):
        number = re.search(r"-v(\d+)\.mp4$", video.name)
        if not number:
            continue
        version = f"v{number.group(1)}"
        _copy(video, target / f"{version}.mp4", report)
        snapshot = source_versions / f"decupagem-{version}.yaml"
        if snapshot.is_file():
            # The breakdown as it was, in SINGULAR's own words: history is not translated.
            _copy(snapshot, target / f"{version}.decupagem.yaml", report)
        subtitles = source_versions / f"{cut_prefix}-{version}.srt"
        if subtitles.is_file():
            _copy(subtitles, target / f"{version}.srt", report)
        row = rows.get(version, {})
        found.append({"id": version, "media": (target / f"{version}.mp4"), "created_at": row.get("created_at", ""),
                      "duration_seconds": row.get("duration_seconds", 0.0),
                      "summary": row.get("summary") or "Imported from SINGULAR.", "note": row.get("note", ""),
                      "verdict": row.get("verdict", "pending")})
    for version, row in rows.items():
        if not any(item["id"] == version for item in found):
            report.approximated.append(f"{scene_id}: {version} is in VERSOES.md but its file is gone ({row['note'][:60]})")
    return found


def _record_versions(root: Path, scene_dir: Path, scene_id: str, versions: list[dict[str, Any]]) -> None:
    """The imported versions as the scene's records, and their arrival in its history."""

    from .state import Assembly, Actor, load_scene_state, write_scene_state

    state = load_scene_state(scene_dir, scene_id)
    importer = Actor(id="singular-migration", kind="system")
    assemblies = []
    decisions = list(state.decisions)
    for item in versions:
        assemblies.append(Assembly(
            id=item["id"], created_at=item["created_at"] or datetime.datetime.now().isoformat(timespec="seconds"),
            media=item["media"].relative_to(root).as_posix(), summary=item["summary"],
            duration_seconds=item["duration_seconds"], verdict=item["verdict"], note=item["note"],
            reviewed_by=Actor(id="author", kind="human") if item["verdict"] == "approved" else None))
        decisions.append({"kind": "assembly.imported", "shot_id": "", "assembly_id": item["id"],
                          "actor": importer.public_dict(), "rationale": "Imported from SINGULAR's versoes/.",
                          "command_id": f"import-{scene_id}-{item['id']}", "decided_at": item["created_at"]})
    from dataclasses import replace

    write_scene_state(scene_dir, replace(state, assemblies=assemblies, decisions=decisions[-200:]))


# --- cast -------------------------------------------------------------------------------


def _cast(documents: list[tuple[str, dict[str, Any]]], target: Path, report: Report) -> dict[str, str]:
    """One sheet per character from every scene's descriptions, voices and sheets; returns name -> id."""

    from .cast import cast_key

    members: dict[str, dict[str, Any]] = {}
    for scene_id, document in documents:
        sheets = document.get("fichas") or {}
        for name, text in (document.get("personagens") or {}).items():
            member = members.setdefault(cast_key(name), {"name": name, "variants": {}, "descriptions": {}, "voices": {}})
            variant = str(sheets.get(name) or "default")
            entry = member["variants"].setdefault(variant, {"texts": {}, "scenes": []})
            entry["texts"].setdefault(" ".join(str(text).split()), []).append(scene_id)
            entry["scenes"].append(scene_id)
            member["descriptions"].setdefault(" ".join(str(text).split()), []).append(scene_id)
        for name, text in (document.get("vozes") or {}).items():
            member = members.setdefault(cast_key(name), {"name": name, "variants": {}, "descriptions": {}, "voices": {}})
            member["voices"].setdefault(" ".join(str(text).split()), []).append(scene_id)
    ids = {}
    for key, member in sorted(members.items()):
        folder = target / key.lower()
        folder.mkdir(parents=True, exist_ok=True)
        variants = {}
        for name, variant in member["variants"].items():
            picture = target / "library" / "fichas" / f"{name}.png"
            texts = sorted(variant["texts"].items(), key=lambda item: -len(item[1]))
            entry = {"description": texts[0][0], "scenes": variant["scenes"]}
            if len(texts) > 1:
                # Scenes described the same variant differently: every wording kept, for the author to settle.
                entry["described_elsewhere"] = {text: scenes for text, scenes in texts[1:]}
                report.approximated.append(f"cast {key} {name}: {len(texts)} descriptions across scenes; the most "
                                           "used is the variant's, the others kept beside it")
            if picture.is_file():
                entry["references"] = [{"path": os.path.relpath(picture, folder), "kind": "face", "role": "master"}]
            variants[name] = entry
        voices = sorted(member["voices"].items(), key=lambda item: -len(item[1]))
        sheet = {
            "id": key, "label": member["name"].title(), "names": [member["name"]],
            "description": "",
            "authoritative_for": ["face", "voice"] if voices else ["face"],
            "variants": variants,
        }
        if voices:
            sheet["voice"] = {"identity": voices[0][0]}
            if len(voices) > 1:
                sheet["voice_as_written_elsewhere"] = {text: scenes for text, scenes in voices[1:]}
                report.approximated.append(f"cast {key}: {len(voices)} voice descriptions across scenes; the most used "
                                           "is the identity, the others listed for the author")
        (folder / "character.yaml").write_text(
            "# Gathered from SINGULAR's scenes by the migration (CT-0054): review and keep it as the one truth.\n"
            + yaml.safe_dump(sheet, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        ids[member["name"]] = key
        report.converted.append(f"cast {key}: {len(variants)} variant(s) from {sum(len(v['scenes']) for v in member['variants'].values())} scene(s)")
    return ids


def _locations(source: Path, target: Path, documents: list[tuple[str, dict[str, Any]]], report: Report) -> dict[str, str]:
    """Each set of `cenarios/` as a location, and which scenes are shot there; returns scene -> location id.

    A set's sheet (FICHA.md) names its scenes in bold ("Cena: **3-01**"); a scene whose set fragments
    (`cenario`) are those of a mapped scene is in the same room.
    """

    where: dict[str, str] = {}
    folder = source / "cenarios"
    if not folder.is_dir():
        return where
    for place in sorted(path for path in folder.iterdir() if path.is_dir()):
        location_id = place.name.upper()
        sheet = place / "FICHA.md"
        text = sheet.read_text(encoding="utf-8") if sheet.is_file() else ""
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), place.name)
        head = "\n".join(text.splitlines()[:8])
        scenes = re.findall(r"\*\*(\d+-\d+[A-Z]?)\*\*", head)
        for scene_id in scenes:
            where.setdefault(scene_id, location_id)
        # The set as it is described, not the sheet's status lines ("Cenas: ...", "**PROPOSTA**").
        paragraphs = [block.strip() for block in text.split("\n\n")[1:] if block.strip()
                      and not re.match(r"\s*(#|\*\*|Cenas?\b|Cena:|```|\||-\s)", block)]
        location = {"id": location_id, "label": title,
                    "description": " ".join(paragraphs[0].split()) if paragraphs else "",
                    "scenes": scenes, "sheet": "FICHA.md"}
        references = [{"path": path.relative_to(target / "locations" / place.name).as_posix(),
                       "kind": "blockout" if "blockout" in path.parts else "reference"}
                      for path in sorted((target / "locations" / place.name).rglob("*"))
                      if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and "versoes" not in path.parts]
        if references:
            location["references"] = references
        (target / "locations" / place.name / "location.yaml").write_text(
            "# A set of SINGULAR, gathered by the migration (CT-0054); its sheet is FICHA.md beside it.\n"
            + yaml.safe_dump(location, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        report.converted.append(f"location {location_id}: {title} ({', '.join(scenes) or 'no scene named'})")
    fragments = {scene_id: set((document.get("cenario") or {}).keys()) for scene_id, document in documents}
    for scene_id, keys in fragments.items():
        if scene_id in where or not keys:
            continue
        twin = next((other for other, theirs in fragments.items() if other in where and theirs == keys), None)
        if twin:
            where[scene_id] = where[twin]
            report.approximated.append(f"{scene_id}: shot in {where[twin]}, as {twin} (the same set fragments)")
    return where


def _pov_takes(target: Path, documents: list[tuple[str, dict[str, Any]]], report: Report) -> None:
    """A shot SINGULAR cuts through its POV montage (`montagem_pov`: pov_foco.py's focus and overlay) uses that
    montage's result, already in its work folder as the POV take: the cut is SINGULAR's, decided as such."""

    from .commands import select_take
    from .project import load_scene
    from .state import Actor

    for scene_id, document in documents:
        wanted = [str(shot.get("n")) for shot in document.get("planos") or [] if shot.get("montagem_pov")]
        if not wanted:
            continue
        scene = load_scene(target, scene_id)
        for shot in scene["shots"]:
            if str(shot.get("number")) in wanted and any(take["id"] == "POV" for take in shot.get("takes") or []):
                select_take(target, scene_id=scene_id, shot_id=shot["id"], take_id="POV",
                            actor=Actor(id="singular-migration", kind="system"),
                            rationale="SINGULAR cuts this shot through its POV montage (pov_foco.py); its result is "
                                      "the POV take.")
                report.converted.append(f"{scene_id} {shot['id']}: montagem_pov -> the POV take selected "
                                        "(SINGULAR's montage result)")


def _identities(folder: Path) -> dict[str, str]:
    """Each cast sheet's voice identity, by member key."""

    identities = {}
    for sheet in folder.glob("*/character.yaml"):
        raw = yaml.safe_load(sheet.read_text(encoding="utf-8")) or {}
        identity = ((raw.get("voice") or {}).get("identity") or "")
        if identity:
            identities[str(raw.get("id"))] = " ".join(identity.split())
    return identities


def _plan_names(target: Path, report: Report) -> None:
    """Tie the people the scenes' plans name by pose ("Líra L1 (sentada)") to their cast sheets."""

    from .cast import cast_key
    from .project import load_production

    sheets = {}
    for path in (target / "cast").glob("*/character.yaml"):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sheets[str(raw.get("id"))] = (path, raw)
    production = load_production(target)
    for scene in production["scenes"]:
        for subject in (scene.get("geometry") or {}).get("subjects", []):
            key = cast_key(subject["id"])
            if key in sheets or any(key in [cast_key(n) for n in raw.get("names") or []] for _, raw in sheets.values()):
                continue
            stem = key.split("-")[0]
            owner = next((member for member in sheets if key.startswith(member + "-") or (
                len(os.path.commonprefix([stem, member])) >= max(6, len(member) - 2))), None)
            if owner is None:
                continue
            path, raw = sheets[owner]
            raw.setdefault("names", []).append(subject["id"])
            report.approximated.append(f"{scene['id']}: the plan's {subject['id']!r} is {owner} (by name)")
    for path, raw in sheets.values():
        header = path.read_text(encoding="utf-8").split("\n", 1)[0]
        path.write_text(header + "\n" + yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=100),
                        encoding="utf-8")


def _looks(documents: list[tuple[str, dict[str, Any]]], target: Path, report: Report) -> None:
    """SINGULAR's per-scene look descriptions as look definitions (`looks/<id>/look.yaml`)."""

    looks: dict[str, dict[str, list[str]]] = {}
    for scene_id, document in documents:
        for name, text in (document.get("looks") or {}).items():
            looks.setdefault(str(name), {}).setdefault(" ".join(str(text).split()), []).append(scene_id)
    for name, texts in sorted(looks.items()):
        ordered = sorted(texts.items(), key=lambda item: -len(item[1]))
        definition = {"id": name, "label": name.title(),
                      "generation": {"prompt": ordered[0][0], "scenes": ordered[0][1]}}
        if len(ordered) > 1:
            definition["generation"]["written_elsewhere"] = {text: scenes for text, scenes in ordered[1:]}
            report.approximated.append(f"look {name}: {len(ordered)} wordings across scenes; the most used leads")
        folder = target / "looks" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "look.yaml").write_text(
            "# Gathered from SINGULAR's scenes by the migration (CT-0054).\n"
            + yaml.safe_dump(definition, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")
        report.converted.append(f"look {name}: a look definition from {sum(len(v) for v in texts.values())} scene(s)")


# --- the production ---------------------------------------------------------------------


def migrate(source: Path, target: Path, *, replace: bool = False, proposals: Path | None = None,
            year: int = 2026, git: bool = True) -> Report:
    source, target = source.expanduser().resolve(), target.expanduser().resolve()
    manifest_path = source / "project.yaml"
    if not manifest_path.is_file():
        raise ValidationError(f"{source} has no project.yaml")
    if target.exists() and any(target.iterdir()):
        if not (target / MARKER).is_file():
            raise ValidationError(f"{target} is not empty and was not made by a migration; refusing to write there")
        if not replace:
            raise ValidationError(f"{target} holds an earlier migration; pass replace to make it again")
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    report = Report()
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

    # The material, folder by folder.
    plan = [("livro", "story/book"), ("roteiro", "story/screenplay"), ("elenco", "cast/library"),
            ("cenarios", "locations"), ("estetica", "looks/reference"), ("docs", "docs"), ("knowledge", "knowledge"),
            ("arquivo", "archive")]
    for old, new in plan:
        if (source / old).exists():
            _copy(source / old, target / new, report)
    if proposals and proposals.is_dir():
        _copy(proposals, target / "story" / "proposals", report)

    # Scenes.
    active = str((manifest.get("producao") or {}).get("variante") or "")
    scenes_root = source / str((manifest.get("caminhos") or {}).get("cenas") or "cenas")
    documents = []
    scene_dirs: dict[str, str] = {}
    imported: dict[str, list[dict[str, Any]]] = {}
    found = []
    for folder in sorted(path for path in scenes_root.iterdir() if path.is_dir()):
        chosen = folder / active if active and (folder / active / "decupagem.yaml").is_file() else folder
        breakdown = chosen / "decupagem.yaml"
        if not breakdown.is_file():
            continue
        document = yaml.safe_load(breakdown.read_text(encoding="utf-8")) or {}
        scene_id = str(document.get("cena") or folder.name)
        if chosen != folder and (folder / "decupagem.yaml").is_file():
            # The scene keeps its own title; "versão LTX" named a variant, and the variant is now the scene.
            main = yaml.safe_load((folder / "decupagem.yaml").read_text(encoding="utf-8")) or {}
            if main.get("titulo") and main["titulo"] != document.get("titulo"):
                report.converted.append(f"{scene_id}: title {document.get('titulo')!r} -> {main['titulo']!r} (the scene's own)")
                document = {**document, "titulo": main["titulo"]}
        documents.append((scene_id, document))
        found.append((folder, chosen, breakdown, scene_id, document))

    # Cast and looks first, from every scene: a scene is then written without what they now own.
    cast_ids = _cast(documents, target / "cast", report)
    _looks(documents, target, report)
    identities = _identities(target / "cast")
    locations = _locations(source, target, documents, report)

    for folder, chosen, breakdown, scene_id, document in found:
        name = f"{scene_id}-{slug(document.get('titulo') or '')}"
        scene_dir = target / "scenes" / name
        scene_dirs[scene_id] = name
        nested = chosen != folder
        # Paths the breakdown names: its own work folder, and (from a variant) the scene's other work folder.
        prefixes = [("../trabalho/", "archive/main/work/"), ("trabalho/", "work/")] if nested else [("trabalho/", "work/")]
        prefixes.append(("teste/", "archive/tests/"))  # the scene's tests folder, archived below
        converted = _rewrite_paths(convert_scene(document, report, scene_id, identities), prefixes)
        if scene_id in locations:
            converted = {**{key: value for key, value in converted.items() if key != "shots"},
                         "location": locations[scene_id], "shots": converted.get("shots") or []}
        # Material outside the scene: the author's proposals, and the sets (cenarios/, now locations/).
        converted = _rewrite_paths(converted, [("propostas/", "../../story/proposals/"),
                                               ("../../../cenarios/", "../../locations/"),
                                               ("../../cenarios/", "../../locations/")])
        header = breakdown.read_text(encoding="utf-8").split("\n")
        comment = "\n".join(line for line in header[:40] if line.startswith("#"))
        scene_dir.mkdir(parents=True, exist_ok=True)
        (scene_dir / "scene.yaml").write_text(
            (comment + "\n#\n" if comment else "")
            + f"# Migrated from SINGULAR ({breakdown.relative_to(source)}) by `toast migrate` (CT-0054).\n"
            + yaml.safe_dump(converted, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
        rename = {"_tomadas": "_takes", "_descartados": "_rejected", "trabalho": "work"}
        if (chosen / "trabalho").is_dir():
            _copy(chosen / "trabalho", scene_dir / "work", report, skip=_work_skip, rename=rename)
        if (chosen / "teste").is_dir():
            _copy(chosen / "teste", scene_dir / "archive" / "tests", report)
        for pdf in chosen.glob("*.pdf"):
            _copy(pdf, scene_dir / "review" / pdf.name, report)
        prefix = f"cena-{scene_id}" + (f"-{active}" if nested else "")
        versions = _import_versions(chosen / "versoes", scene_dir, scene_id, prefix, report, year)
        if nested:
            # The scene's other breakdown, with its own material and history, kept whole in the archive.
            _copy(folder, scene_dir / "archive" / "main", report,
                  skip=lambda relative: relative.parts[0] == active or (
                      relative.parts[0] == "trabalho" and _work_skip(Path(*relative.parts[1:]) if len(relative.parts) > 1 else relative)),
                  rename={**rename})
        report.scenes.append({"id": scene_id, "folder": f"scenes/{name}", "variant": active if nested else "main",
                              "shots": len(document.get("planos") or []), "versions": len(versions)})
        imported[scene_id] = versions


    # Sounds: the library with its licences.
    if (source / "sons").is_dir():
        _copy(source / "sons", target / "sounds" / "library", report)
        from .sound_sources import import_library

        made = import_library(target, target / "sounds" / "library", prefix="singular-")
        report.converted.append(f"sounds: {len(made)} recordings registered in the catalog with their licences")

    # Sequences and their versions.
    sequences = []
    for item in manifest.get("sequencias") or []:
        entry = {"id": item["id"], "label": item.get("rotulo") or item["id"], "act": item.get("ato") or "",
                 "scenes": item.get("cenas") or []}
        sequences.append(entry)
        render = item.get("montagem")
        if render and (source.parent / render).is_file():
            _copy(source.parent / render, target / "sequences" / item["id"] / "versions" / "v1.mp4", report)
    if (source / "sequencias").is_dir():
        for path in (source / "sequencias").iterdir():
            if path.is_file() and not any(path.name == Path(str(item.get("montagem") or "")).name
                                          for item in manifest.get("sequencias") or []):
                _copy(path, target / "sequences" / "_reviews" / path.name, report)

    # The production manifest.
    report.converted.append("production: format feature-scope (2.39:1, SINGULAR's 1280x536) and burned subtitles "
                            "(Portuguese lines timed to the English speech, an .srt beside every version)")
    kept_shot_fields = {key for key in report.kept if key.startswith("shot.")}
    declared = manifest.get("shot_fields") or {}
    shot_fields = {}
    for key in sorted(kept_shot_fields):
        name = key.split(".", 1)[1]
        shot_fields[name] = {"label": (declared.get(name) or {}).get("label") or name}
    screenplay = "story/screenplay/v4"
    project = {
        "schema_version": 1, "id": manifest.get("id") or "singular", "title": manifest.get("titulo") or "SINGULAR",
        "format": manifest.get("formato") or "", "logline": manifest.get("logline") or "",
        "paths": {"scenes": "scenes", "script": screenplay, "cast": "cast"},
        "screenplay_generated_by": f"{screenplay}/monta_v4.py",
        "words_sidecar": manifest.get("words_sidecar") or "{stem}.words.json",
        "production": {"phase": (manifest.get("producao") or {}).get("fase") or "production",
                       "active_scene": (manifest.get("producao") or {}).get("cena_ativa") or ""},
        "sequences": sequences,
        # SINGULAR's montage crops every take to 1280x536 (cena_ltx.py: W, H) and burns Portuguese subtitles
        # timed to the English speech while the author reviews: the same, natively.
        "style": {"format": "feature-scope"},
        "subtitles": {"burn": True},
        "shot_fields": shot_fields,
    }
    (target / "project.yaml").write_text(
        "# SINGULAR, migrated from ~/confyui/singular by `toast migrate` (CT-0054). The schema is English\n"
        "# (ADR 0013); the film's own words stay in Portuguese. Fields kept from SINGULAR's own pipeline are\n"
        "# declared under shot_fields until they have a native home (see MIGRATION.md).\n"
        + yaml.safe_dump(project, allow_unicode=True, sort_keys=False, width=110), encoding="utf-8")
    (target / MARKER).write_text(json.dumps({"source": str(source), "at": datetime.datetime.now().isoformat(
        timespec="seconds")}) + "\n", encoding="utf-8")

    # The history: imported versions as records, and their indexes.
    for scene_id, name in scene_dirs.items():
        versions = imported.get(scene_id) or []
        if versions:
            _record_versions(target, target / "scenes" / name, scene_id, versions)
            from .versions import index_scene

            index_scene(target, scene_id)
    for item in sequences:
        if (target / "sequences" / item["id"] / "versions" / "v1.mp4").is_file():
            from . import sequence_state

            data = sequence_state.load(target)
            data["sequences"].setdefault(item["id"], {"versions": []})["versions"].append({
                "id": "v1", "created_at": "", "media": f"sequences/{item['id']}/versions/v1.mp4",
                "summary": "Imported from SINGULAR.", "duration_seconds": 0.0, "scenes": {},
                "verdict": "pending", "note": "", "reviewed_by": None, "renditions": {}})
            sequence_state.write(target, data)
            from .versions import index_sequence

            index_sequence(target, item["id"])

    _pov_takes(target, documents, report)
    _plan_names(target, report)
    _write_report(target, report, cast_ids)
    from .versions import write_overview

    write_overview(target)
    _gitignore(target)
    if git and shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "add", "-A"], cwd=target, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Migrated from SINGULAR (toast migrate, CT-0054)"], cwd=target,
                       check=False, capture_output=True)
    return report


def _gitignore(target: Path) -> None:
    (target / ".gitignore").write_text(
        "# The film's text is versioned here (ADR 0021); its media's history is the versions folders.\n"
        "*.mp4\n*.mov\n*.webm\n*.wav\n*.mp3\n*.flac\n*.png\n*.jpg\n*.jpeg\n*.webp\n*.exr\n*.pdf\n*.zip\n"
        "*.safetensors\n*.ckpt\n*.blend\n*.blend1\n*.usd*\n*.vdb\n*.abc\n*.ply\n*.splat\n*.cube\n", encoding="utf-8")


def _write_report(target: Path, report: Report, cast_ids: dict[str, str]) -> None:
    lines = ["# Migration from SINGULAR", "",
             f"{report.copied_files} files, {report.copied_bytes / 1e9:.2f} GB copied; nothing in the source was changed.",
             "", "## Scenes", "", "| scene | folder | breakdown | shots | versions |", "|---|---|---|---|---|"]
    lines += [f"| {item['id']} | {item['folder']} | {item['variant']} | {item['shots']} | {item['versions']} |"
              for item in report.scenes]
    lines += ["", "## Converted", ""] + [f"- {item}" for item in report.converted]
    lines += ["", "## Approximated", ""] + [f"- {item}" for item in report.approximated]
    lines += ["", "## Read through the legacy vocabulary (understood; to be rewritten natively)", "",
              "| field | times |", "|---|---|"] + [f"| {key} | {count} |" for key, count in sorted(
                  report.legacy.items(), key=lambda item: -item[1])]
    lines += ["", "## Kept as SINGULAR wrote them (no native home yet)", "",
              "| field | times |", "|---|---|"] + [f"| {key} | {count} |" for key, count in sorted(
                  report.kept.items(), key=lambda item: -item[1])]
    (target / "MIGRATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- checking the migration -----------------------------------------------------------


def _moved(ref: str, prefixes: list[tuple[str, str]]) -> str:
    for old, new in prefixes:
        if ref.startswith(old):
            return new + ref[len(old):]
    return ref


def compare(source: Path, target: Path) -> list[str]:
    """What Cine Toaster reads differently in the migrated film than in the original: [] when nothing.

    Scenes, shots, their durations, labels, lines and takes must be the same;
    findings may only go down; versions and cast may only appear.
    """

    from .project import load_production

    before, after = load_production(source.expanduser()), load_production(target.expanduser())
    differences: list[str] = []
    old = {scene["id"]: scene for scene in before["scenes"]}
    new = {scene["id"]: scene for scene in after["scenes"]}
    if set(old) != set(new):
        differences.append(f"scenes differ: only before {sorted(set(old) - set(new))}, only after {sorted(set(new) - set(old))}")
    for scene_id in sorted(set(old) & set(new)):
        a, b = old[scene_id], new[scene_id]
        shots_a = {shot["id"]: shot for shot in a["shots"]}
        shots_b = {shot["id"]: shot for shot in b["shots"]}
        if list(shots_a) != list(shots_b):
            differences.append(f"{scene_id}: shots differ ({len(shots_a)} -> {len(shots_b)})")
            continue
        for shot_id, shot in shots_a.items():
            other = shots_b[shot_id]
            for key in ("duration_seconds", "label", "source", "engine", "out_of_cut"):
                if key == "out_of_cut" and str(shot.get("kind") or "").lower() in ("imagem", "image") \
                        and not shot.get(key) and other.get(key):
                    continue  # an auxiliary picture, now said to be out of the cut, as SINGULAR always treated it
                if shot.get(key) != other.get(key):
                    differences.append(f"{scene_id} {shot_id}: {key} {shot.get(key)!r} -> {other.get(key)!r}")
            if len(shot.get("lines") or []) != len(other.get("lines") or []):
                differences.append(f"{scene_id} {shot_id}: lines {len(shot.get('lines') or [])} -> {len(other.get('lines') or [])}")
            # The same sources, where the migration moved them; `ref: false` was never one.
            moved = [("../trabalho/", "archive/main/work/"), ("trabalho/", "work/"), ("teste/", "archive/tests/"),
                     ("propostas/", "../../story/proposals/"),
                     ("../../../cenarios/", "../../locations/"), ("../../cenarios/", "../../locations/")]
            refs_a = sorted(re.sub(r"^([^/\s]+)/[^\s]+\s+", r"\1 ", _moved(str(item.get("ref")), moved))
                            if item.get("relation") == "reusa" else _moved(str(item.get("ref")), moved)
                            for item in shot.get("from") or [] if item.get("ref") not in (False, "False"))
            refs_b = sorted(str(item.get("ref")) for item in other.get("from") or [])
            if refs_a != refs_b:
                differences.append(f"{scene_id} {shot_id}: sources {refs_a} -> {refs_b}")
            folder = (target.expanduser() / b["file"]).parent
            for ref in [str(item.get("ref")) for item in other.get("from") or [] if item.get("relation") != "reuses"]:
                if "/" in ref and not (folder / ref).exists():
                    differences.append(f"{scene_id} {shot_id}: its source {ref} is missing in the migrated film")
            takes_a = sorted(take["id"] for take in shot.get("takes") or [])
            takes_b = sorted(take["id"] for take in other.get("takes") or [])
            if takes_a != takes_b:
                differences.append(f"{scene_id} {shot_id}: takes {takes_a} -> {takes_b}")
        if len(b["findings"]) > len(a["findings"]):
            gained = sorted({f["code"] for f in b["findings"]} - {f["code"] for f in a["findings"]})
            differences.append(f"{scene_id}: findings {len(a['findings'])} -> {len(b['findings'])} (new: {gained})")
    return differences
