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
                                "references": [ref.public_dict() for ref in value["references"]]}
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
            out.append(_finding("voice_identity_restated", "advice", scene_id,
                f"This scene describes {member.label}'s voice itself (\"{str(text)[:80]}\"). The sheet owns the "
                f"voice's identity (\"{member.voice.describe()}\"); keep only how it sounds now in voice_state."))
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

