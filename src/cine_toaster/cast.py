"""Cast: a recurring character declared once, referenced by id (SPEC-0003, ADR 0012).

A cast member lives at `cast/<id>/character.yaml`: who they are, what the sheet
is authoritative for, the reference pictures a generation must use, the
variants of the same person a film needs (an age, a state -- SINGULAR's Kael in
Geneva and in Boreal), and their **voice** (CT-0040):

- identity -- timbre, age, accent, language, reference recordings -- is the
  same in every scene, and only the sheet states it;
- state -- tired, hoarse, out of breath -- belongs to a scene (`voice_state`);
- delivery belongs to a line (`delivery`).

Checks read declared state only. They run only when the production has a cast.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .geometry import Finding

AUTHORITY = ("face", "hair", "wardrobe", "build", "age", "voice")
REFERENCE_KINDS = ("subject", "face")
CAST_DIRECTORY = "cast"
CHARACTER_FILE = "character.yaml"


def cast_key(value: Any) -> str:
    """One spelling for a character: `Kael`, `KAEL` and `kael` are the same person."""

    return re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")


@dataclass(slots=True)
class Reference:
    path: str
    kind: str
    role: str
    exists: bool
    digest: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {"path": self.path, "kind": self.kind, "role": self.role, "exists": self.exists, "digest": self.digest}


@dataclass(slots=True)
class Voice:
    identity: str = ""
    accent: str = ""
    language: str = ""
    references: list[str] = field(default_factory=list)

    def describe(self) -> str:
        parts = [self.identity] + ([f"{self.accent} accent"] if self.accent else [])
        return ", ".join(part for part in parts if part)

    def public_dict(self) -> dict[str, Any]:
        return {"identity": self.identity, "accent": self.accent, "language": self.language,
                "references": self.references, "described": self.describe()}


@dataclass(slots=True)
class Member:
    id: str
    label: str
    description: str
    authoritative_for: list[str]
    references: list[Reference]
    variants: dict[str, dict[str, Any]]
    voice: Voice | None
    directory: str
    problems: list[str] = field(default_factory=list)
    #: Other names the character goes by: the screenplay's cue, a geometry id.
    names: list[str] = field(default_factory=list)

    def master(self, kind: str = "face", variant: str = "") -> Reference | None:
        pool = self.references
        if variant and variant in self.variants:
            pool = self.variants[variant]["references"] or pool
        return next((ref for ref in pool if ref.kind == kind and ref.role == "master"), None)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "label": self.label, "description": self.description,
            "authoritative_for": self.authoritative_for,
            "references": [ref.public_dict() for ref in self.references],
            "variants": {name: {"description": value["description"],
                                "references": [ref.public_dict() for ref in value["references"]],
                                "face_changes": value.get("face_changes", "")}
                         for name, value in self.variants.items()},
            "voice": self.voice.public_dict() if self.voice else None,
            "directory": self.directory, "problems": self.problems, "names": self.names,
        }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.is_file() else ""


def _references(raw: Any, base: Path, root: Path, problems: list[str], where: str) -> list[Reference]:
    references = []
    for item in raw or []:
        if not isinstance(item, dict) or not item.get("path"):
            problems.append(f"{where}: a reference needs a path")
            continue
        kind = str(item.get("kind") or "face")
        role = str(item.get("role") or "supporting")
        if kind not in REFERENCE_KINDS:
            problems.append(f"{where}: reference kind {kind!r} is not one of {', '.join(REFERENCE_KINDS)}")
        path = (base / str(item["path"])).resolve()
        inside = path.is_relative_to(root.resolve())
        references.append(Reference(path.relative_to(root.resolve()).as_posix() if inside else str(item["path"]),
                                    kind, role, path.is_file(), _digest(path)))
    for kind in REFERENCE_KINDS:
        masters = [ref for ref in references if ref.kind == kind and ref.role == "master"]
        if len(masters) > 1:
            problems.append(f"{where}: {len(masters)} masters for {kind}; exactly one is allowed")
    return references


def load_cast(root: Path, manifest: dict[str, Any]) -> dict[str, Member]:
    """Every cast member of the production, by id; empty when it declares none."""

    paths = manifest.get("paths") or {}
    directory = root / str(paths.get("cast") or CAST_DIRECTORY)
    members: dict[str, Member] = {}
    if not directory.is_dir():
        return members
    for sheet in sorted(directory.glob(f"*/{CHARACTER_FILE}")):
        raw = yaml.safe_load(sheet.read_text(encoding="utf-8")) or {}
        base = sheet.parent
        problems: list[str] = []
        member_id = cast_key(raw.get("id") or base.name)
        authority = [str(item) for item in raw.get("authoritative_for") or []]
        if not authority:
            problems.append("authoritative_for is required: say what this sheet decides")
        unknown = sorted(set(authority) - set(AUTHORITY))
        if unknown:
            problems.append(f"authoritative_for has {', '.join(unknown)}; allowed: {', '.join(AUTHORITY)}")
        variants = {}
        for name, value in (raw.get("variants") or {}).items():
            value = value or {}
            variants[str(name)] = {
                "description": str(value.get("description") or ""),
                "references": _references(value.get("references"), base, root, problems, f"variant {name}"),
                # Why this variant's face is not the character's master face (age, years in stasis): CT-0060.
                "face_changes": str(value.get("face_changes") or "").strip(),
            }
        voice_raw = raw.get("voice")
        voice = None
        if isinstance(voice_raw, dict):
            recordings = []
            for item in voice_raw.get("references") or []:
                path = (base / str(item)).resolve()
                recordings.append(path.relative_to(root.resolve()).as_posix() if path.is_relative_to(root.resolve()) else str(item))
            voice = Voice(
                identity=str(voice_raw.get("identity") or ""),
                accent=str(voice_raw.get("accent") or ""),
                language=str(voice_raw.get("language") or ""),
                references=recordings,
            )
        members[member_id] = Member(
            id=member_id,
            label=str(raw.get("label") or member_id.title()),
            description=str(raw.get("description") or ""),
            authoritative_for=authority,
            references=_references(raw.get("references"), base, root, problems, "sheet"),
            variants=variants,
            voice=voice,
            directory=base.relative_to(root).as_posix(),
            problems=problems,
            names=[str(name) for name in raw.get("names") or []],
        )
    return members


def resolver(cast: dict[str, Member]) -> dict[str, Member]:
    """Every name a cast member answers to, by key."""

    by_name: dict[str, Member] = {}
    for member in cast.values():
        for name in [member.id, member.label, *member.names]:
            by_name.setdefault(cast_key(name), member)
    return by_name


def _finding(code: str, severity: str, scene_id: str, message: str, shots: tuple[str, ...] = ()) -> Finding:
    return Finding(code=code, severity=severity, message=message, scene_id=scene_id, shots=shots)


def _bare(label: str) -> str:
    """A plan label without its pose or mark: "Líra L1 (sentada)" -> "líra"."""

    text = re.sub(r"\([^)]*\)", " ", label)
    text = re.sub(r"\b[A-Z]\d+\b", " ", text)
    return " ".join(text.lower().split())


def check_cast(scenes: list[dict[str, Any]], cast: dict[str, Member]) -> dict[str, list[Finding]]:
    """Findings per scene. Nothing is reported for a production without a cast."""

    findings: dict[str, list[Finding]] = {scene["id"]: [] for scene in scenes}
    if not cast:
        return findings
    names = resolver(cast)
    labels: dict[str, set[tuple[str, str]]] = {}
    for scene in scenes:
        scene_id = scene["id"]
        out = findings[scene_id]
        geometry = scene.get("geometry") or {}
        people = {cast_key(subject["id"]): subject for subject in geometry.get("subjects", [])}
        for key, subject in people.items():
            if key in names:
                labels.setdefault(names[key].id, set()).add((scene_id, str(subject.get("label") or "")))
        referenced: dict[str, list[str]] = {}
        for shot in scene["shots"]:
            speakers = [line.get("who") for line in shot.get("lines") or []]
            speakers += [line.get("who") for line in (shot.get("script") or {}).get("dialogue") or []]
            for who in [shot.get("subject"), *speakers]:
                if who:
                    key = cast_key(who)
                    referenced.setdefault(names[key].id if key in names else key, []).append(shot["id"])
        for key in people:
            referenced.setdefault(names[key].id if key in names else key, [])
        variants = {(names[cast_key(n)].id if cast_key(n) in names else cast_key(n)): str(v)
                    for n, v in (scene.get("cast") or {}).items()}
        for key, shots in sorted(referenced.items()):
            member = cast.get(key)
            if member is None:
                out.append(_finding("cast_subject_unknown", "warning", scene_id,
                    f"{key} appears in this scene but has no cast sheet (cast/{key.lower()}/character.yaml).",
                    tuple(sorted(set(shots)))))
                continue
            variant = variants.get(key, "")
            if variant and variant not in member.variants:
                out.append(_finding("cast_variant_unknown", "error", scene_id,
                    f"This scene asks for {member.label} as {variant!r}; the sheet's variants are "
                    f"{', '.join(member.variants) or 'none'}."))
            # Only a sheet that decides the face owes a picture of it: a voice
            # heard from off screen (a loudspeaker, a narrator) does not.
            generates = "face" in member.authoritative_for and any(
                shot.get("source") == "generated" for shot in scene["shots"] if shot["id"] in shots)
            master = member.master("face", variant)
            if generates and (master is None or not master.exists):
                out.append(_finding("cast_reference_missing", "warning", scene_id,
                    f"{member.label} is generated here, but the sheet"
                    + (f" (variant {variant})" if variant else "")
                    + (" names no master face." if master is None else f" names {master.path}, which is missing."),
                    tuple(sorted(set(shots)))))
        for name, text in sorted((scene.get("voices") or {}).items()):
            member = names.get(cast_key(name))
            if member is None or member.voice is None or not member.voice.describe():
                continue
            if _plain(text) == _plain(member.voice.describe()) or _plain(text) == _plain(member.voice.identity):
                out.append(_finding("voice_identity_restated", "advice", scene_id,
                    f"This scene repeats {member.label}'s voice as the sheet has it. The sheet owns the voice's "
                    f"identity; the scene can drop it, and keep only how it sounds now in voice_state."))
            else:
                # The scene's description wins in the prompt (CT-0055): it is another voice, not a state (CT-0062).
                out.append(_finding("voice_identity_conflict", "error", scene_id,
                    f"This scene gives {member.label} another voice (\"{str(text)[:90]}\") than the sheet's "
                    f"(\"{member.voice.describe()[:90]}\"). One person has one voice: keep the identity on the sheet "
                    f"and put how it sounds here -- tired, hoarse, a whisper -- in voice_state."))
        out.extend(_unanchored_voices(scene, cast, names))
    for scene_id, found in _identity_splits(scenes, cast, names).items():
        findings[scene_id].extend(found)
    for scene_id, found in _voice_splits(scenes, names).items():
        findings[scene_id].extend(found)
    for key, seen in labels.items():
        # Drift is one person named differently from scene to scene. A pose or a mark in the plan's label
        # ("Kael (sentado)", "Líra L1") is not a name, and several people of a group in one scene are not drift.
        by_scene: dict[str, set[str]] = {}
        for scene, label in seen:
            if label:
                by_scene.setdefault(scene, set()).add(_bare(label))
        if len(by_scene) > 1 and len({name for names in by_scene.values() for name in names}) > 1 and not all(
                len(names) > 1 for names in by_scene.values()):
            where = ", ".join(f"{scene} as {label!r}" for scene, label in sorted(seen))
            for scene_id in sorted(by_scene):
                findings[scene_id].append(_finding("cast_label_drift", "advice", scene_id,
                    f"{cast[key].label} is labelled differently across scenes: {where}."))
    return findings


def _plain(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _spoken(scene: dict[str, Any], names: dict[str, Member]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Each cast member's lines in the scene's cut, with the shot that holds them."""

    out: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for shot in scene["shots"]:
        if shot.get("out_of_cut"):
            continue
        for line in shot.get("lines") or []:
            key = cast_key(line.get("who"))
            if key in names:
                out.setdefault(names[key].id, []).append((shot["id"], {**line, "_source": shot.get("source")}))
    return out


def _unanchored_voices(scene: dict[str, Any], cast: dict[str, Member], names: dict[str, Member]) -> list[Finding]:
    """Generated speech with nothing to hold the voice: no recording on the sheet, no named voice (CT-0062).

    A video model invents a voice in every generation; a description narrows it,
    it does not fix it. A recording lets the cut convert every line to the same
    voice (`toast revoice`); a provider's named voice is the same in every call.
    Without either, each clip is another person speaking.
    """

    out = []
    for member_id, lines in sorted(_spoken(scene, names).items()):
        member = cast[member_id]
        if "voice" not in member.authoritative_for or (member.voice and member.voice.references):
            continue
        loose = sorted({shot for shot, line in lines if not line.get("voice") and (
            line["_source"] == "generated" or (line.get("mix") or {}).get("file"))})
        if loose:
            out.append(_finding("cast_voice_reference_missing", "error", scene["id"],
                f"{member.label} speaks {len(loose)} shot(s) here in a generated voice, and the sheet has no "
                f"recording of it: every generation invents the voice again, and nothing can bring the lines back "
                f"to one. Give the sheet a recording (voice.references), so the cut can convert them "
                f"(toast revoice).", tuple(loose)))
    return out


def _voice_splits(scenes: list[dict[str, Any]], names: dict[str, Member]) -> dict[str, list[Finding]]:
    """One character, more than one named provider voice (CT-0062): the voice's version of two faces."""

    used: dict[str, dict[str, list[str]]] = {}
    for scene in scenes:
        for member_id, lines in _spoken(scene, names).items():
            for _, line in lines:
                if line.get("voice"):
                    used.setdefault(member_id, {}).setdefault(str(line["voice"]), [])
                    if scene["id"] not in used[member_id][str(line["voice"])]:
                        used[member_id][str(line["voice"])].append(scene["id"])
    out: dict[str, list[Finding]] = {}
    for member_id, voices in used.items():
        if len(voices) < 2:
            continue
        member = next(item for item in names.values() if item.id == member_id)
        where = "; ".join(f"{voice} in {', '.join(scene_ids)}" for voice, scene_ids in voices.items())
        for scene_id in sorted({scene_id for scene_ids in voices.values() for scene_id in scene_ids}):
            out.setdefault(scene_id, []).append(_finding("cast_voice_split", "error", scene_id,
                f"{member.label} speaks in {len(voices)} voices ({where}). One person has one voice: choose it "
                f"on the sheet and use it everywhere."))
    return out


def _same_picture(first: Reference, second: Reference) -> bool:
    if first.digest and second.digest:
        return first.digest == second.digest
    return first.path == second.path


def _identity_splits(scenes: list[dict[str, Any]], cast: dict[str, Member],
                     names: dict[str, Member]) -> dict[str, list[Finding]]:
    """One character, more than one face: a variant changes how someone looks, not who they are (CT-0060).

    The character's face is the sheet's own master, or else its first variant's.
    A variant whose master face is another picture must say why (`face_changes`);
    until it does, every scene that shows it is told.
    """

    out: dict[str, list[Finding]] = {}
    for member in cast.values():
        if "face" not in member.authoritative_for:
            continue
        own = member.master("face")
        masters = {name: next((ref for ref in value["references"] if ref.kind == "face" and ref.role == "master"),
                              None) for name, value in member.variants.items()}
        primary_name, primary = ("", own) if own is not None else next(
            ((name, ref) for name, ref in masters.items() if ref is not None), ("", None))
        if primary is None:
            continue
        others = {name: ref for name, ref in masters.items()
                  if ref is not None and not _same_picture(ref, primary)}
        faces = 1 + len({ref.digest or ref.path for ref in others.values()})
        for scene in scenes:
            for name, variant in (scene.get("cast") or {}).items():
                key = cast_key(name)
                if key not in names or names[key].id != member.id or str(variant) not in others:
                    continue
                if member.variants[str(variant)].get("face_changes"):
                    continue
                reference = others[str(variant)]
                against = f"{primary_name} ({primary.path})" if primary_name else f"the sheet's master ({primary.path})"
                out.setdefault(scene["id"], []).append(_finding(
                    "cast_identity_split", "error", scene["id"],
                    f"{member.label} has {faces} master faces. Here the variant {variant} uses {reference.path}, "
                    f"another face than {against}. A variant changes how someone looks -- wardrobe, hair, an "
                    f"injury -- not who they are: make its picture from the master face, or say why the face "
                    f"changes (face_changes: <reason> on the variant)."))
    return out


def voice_for(member: Member | None, state: str = "") -> str:
    """The voice a line is spoken in: the sheet's identity, then how it sounds now."""

    if member is None or member.voice is None:
        return state
    described = member.voice.describe()
    return f"{described}; now {state}" if state and described else (described or state)


# --- drafting sheets from what the scenes already say --------------------------


def propose(scenes_raw: list[tuple[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Draft cast sheets from the scenes' own descriptions, showing every variant.

    Writes nothing. Where scenes disagree -- three voices for one man -- every
    version is listed with its scenes, for the person who decides.
    """

    drafts: dict[str, dict[str, Any]] = {}
    for scene_id, document in scenes_raw:
        for field_name, target in (("personagens", "descriptions"), ("characters", "descriptions"),
                                   ("vozes", "voices"), ("voices", "voices"), ("fichas", "sheets"), ("cast", "sheets")):
            for name, text in (document.get(field_name) or {}).items():
                draft = drafts.setdefault(cast_key(name), {"descriptions": {}, "voices": {}, "sheets": {}})
                draft[target].setdefault(" ".join(str(text).split()), []).append(scene_id)
    return drafts


def appearances(scenes: list[dict[str, Any]], cast: dict[str, Member]) -> dict[str, list[dict[str, Any]]]:
    """Where each cast member is: the scenes, the shots, the variant and how their voice sounds."""

    names = resolver(cast)
    found: dict[str, list[dict[str, Any]]] = {key: [] for key in cast}
    for scene in scenes:
        shots: dict[str, list[str]] = {}
        for subject in (scene.get("geometry") or {}).get("subjects", []):
            member = names.get(cast_key(subject["id"]))
            if member:
                shots.setdefault(member.id, [])
        for shot in scene["shots"]:
            speakers = [line.get("who") for line in shot.get("lines") or []]
            speakers += [line.get("who") for line in (shot.get("script") or {}).get("dialogue") or []]
            for who in [shot.get("subject"), *speakers]:
                member = names.get(cast_key(who)) if who else None
                if member and shot["id"] not in shots.setdefault(member.id, []):
                    shots[member.id].append(shot["id"])
        variants = {names[cast_key(n)].id: str(v) for n, v in (scene.get("cast") or {}).items() if cast_key(n) in names}
        states = {names[cast_key(n)].id: str(v) for n, v in (scene.get("voice_state") or {}).items() if cast_key(n) in names}
        for member_id, member_shots in shots.items():
            found[member_id].append({"scene": scene["id"], "title": scene.get("title", ""), "shots": member_shots,
                                     "variant": variants.get(member_id, ""), "voice_state": states.get(member_id, "")})
    return found

