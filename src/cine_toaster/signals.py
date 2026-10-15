"""Signals as production records (C8 step 1, CT-0081): depth, segmentation and the like, from any maker.

A signal is a value per pixel of a medium, through time -- a depth map, a label per pixel, motion vectors --
kept as a resource of the production, not as a node's private result: one depth of a shot serves its
compositing, its tracking, its effects and tools to come. Whatever made it -- a renderer's pass, a model, a
person's paint -- it is kept the one way, under `signals/<id>/`:

    signal.yaml        what it is: its **kind** (SPEC-0012: depth, depth_relative, segmentation, vectors,
                       normals, ...), its **origin** (geometric: a renderer's or a surface's own geometry;
                       estimated: a model's guess; authored: a person's), the medium it describes, its clock,
                       its resolution and coordinates, its camera and depth conventions, its label table, the
                       data in use, a revision
    provenance.json    how it came to be, step by step: what made it (a renderer, a model, a person: name,
                       version, parameters), from what (media, other signals, files -- each by its hash or
                       revision), and every transformation since (an alignment: its method, its reference, its
                       residual) -- the history a result can be rebuilt from
    quality.json       what is known of how good it is, kept apart: **declared** (the maker's own confidence) and
                       **measured** (an error found against something, with what and how). Nothing known is
                       said as nothing: a signal is never given a confidence it was not given
    data/NNNN/         each recorded datum, never edited: one file per frame (float EXR, or .npy)
    corrections/       a person's corrections, apart: a patch of a frame (where, and the values), in force or
                       reverted -- reverting never touches the data

Three things are never mixed: what a signal is (its kind), where it came from (its origin, which a
transformation never changes -- an estimated depth aligned to a scene's geometry is still estimated) and what
was done to it (the transformations in its provenance). A signal derived from another inherits its origin.

A signal is **stale** when anything it was made from has changed: its medium, a file it depended on (a scene,
weights), or a signal it was derived from (re-recorded, or stale itself). A stale signal is refused, with the
reason. Recording is a command (an actor, an event, a revision), as every change to a production.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

from . import timebase
from .errors import ValidationError
from .events import Event, append_event
from .state import Actor, scene_lock

SIGNALS_DIRECTORY = "signals"
#: SPEC-0012's signal kinds that a record may hold: values per pixel kept for their own sake.
KINDS = ("depth", "depth_relative", "segmentation", "vectors", "normals", "luminance", "alpha")
#: Where a signal's values came from. A transformation never changes it; a derived signal inherits it.
ORIGINS = ("geometric", "estimated", "authored")
#: What a depth measures: the distance along the ray from the camera, or its z (along the camera's axis), or
#: their inverse (what a monocular model often gives: larger is nearer).
DEPTH_QUANTITIES = ("distance", "z", "inverse_distance", "inverse_z")
CHANNELS = {"vectors": 2, "normals": 3}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def directory(root: Path, signal_id: str) -> Path:
    if not _ID.match(signal_id or ""):
        raise ValidationError(f"A signal's id is lowercase letters, digits and dashes, not {signal_id!r}")
    return Path(root) / SIGNALS_DIRECTORY / signal_id


def _file_hash(path: Path) -> str:
    from .compositing.identity import file_hash

    return file_hash(path)


def _project_id(root: Path) -> str:
    from .project import load_production

    return str(load_production(root)["id"])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.part")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


# --- the contract ---------------------------------------------------------------------------------------------

def contract_problems(kind: str, origin: str, *, camera: str | None, depth: dict[str, Any] | None,
                      labels: dict[Any, str] | None) -> list[str]:
    """What a signal's declaration lacks or contradicts (SPEC-0012's kinds, CT-0081's origins)."""

    problems = []
    if kind not in KINDS:
        problems.append(f"a signal's kind is one of {', '.join(KINDS)}, not {kind!r}")
    if origin not in ORIGINS:
        problems.append(f"a signal's origin is one of {', '.join(ORIGINS)}, not {origin!r}")
    if kind in ("depth", "depth_relative"):
        depth = depth or {}
        if depth.get("quantity") not in DEPTH_QUANTITIES:
            problems.append(f"a depth says what it measures: quantity is one of {', '.join(DEPTH_QUANTITIES)}")
        if kind == "depth":
            if not camera:
                problems.append("a metric depth names the camera it is measured from (SPEC-0012)")
            if not depth.get("unit"):
                problems.append("a metric depth says its unit (metres, scene units)")
        if kind == "depth_relative" and depth.get("unit"):
            problems.append("a relative depth has no unit: its scale is unknown until it is aligned")
    if kind == "segmentation" and not labels:
        problems.append("a segmentation carries its table of labels ({number: name})")
    return problems


def _shape_problems(kind: str, frame: np.ndarray) -> list[str]:
    channels = CHANNELS.get(kind, 1)
    shape = frame.shape
    if channels == 1 and len(shape) != 2:
        return [f"a {kind} is one value per pixel (height, width), not {shape}"]
    if channels > 1 and (len(shape) != 3 or shape[2] != channels):
        return [f"a {kind} is {channels} values per pixel (height, width, {channels}), not {shape}"]
    if kind == "segmentation" and not np.issubdtype(frame.dtype, np.integer):
        return ["a segmentation's values are whole numbers (labels)"]
    return []


# --- writing and reading data ---------------------------------------------------------------------------------

def _write_frame(path_stem: Path, frame: np.ndarray, kind: str) -> str:
    """One frame: a float EXR when OpenEXR is here (a layer `Y`, or `V.x`/`V.y`, `N.x`.. for several), else .npy.
    A segmentation is kept as .npy (whole numbers)."""

    if kind != "segmentation":
        try:
            import OpenEXR
        except ImportError:
            OpenEXR = None
        if OpenEXR is not None:
            data = np.ascontiguousarray(frame, np.float32)
            channels = ({"Y": data} if data.ndim == 2 else
                        {f"{'V' if kind == 'vectors' else 'N'}.{axis}": np.ascontiguousarray(data[..., index])
                         for index, axis in enumerate("xyz"[: data.shape[2]])})
            name = path_stem.with_suffix(".exr")
            OpenEXR.File({"type": OpenEXR.scanlineimage, "compression": OpenEXR.ZIP_COMPRESSION},
                         channels).write(str(name))
            return name.name
    name = path_stem.with_suffix(".npy")
    np.save(name, frame)
    return name.name


def _read_frame(path: Path) -> np.ndarray:
    if path.suffix == ".npy":
        return np.load(path)
    import OpenEXR

    with OpenEXR.File(str(path)) as opened:
        channels = opened.channels()
        names = sorted(channels)
        planes = [np.asarray(channels[name].pixels, np.float32) for name in names]
    return planes[0] if len(planes) == 1 else np.stack(planes, axis=-1)


def _data_hash(folder: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for file in sorted(folder.iterdir()):
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()[:24]


# --- commands ---------------------------------------------------------------------------------------------------

def record_signal(root: Path, *, signal_id: str, kind: str, frames: Iterable[np.ndarray], rate: Any, actor: Actor,
                  origin: str | None = None, media: str | None = None, start: float | Fraction = 0,
                  camera: str | None = None, depth: dict[str, Any] | None = None,
                  labels: dict[Any, str] | None = None, maker: dict[str, Any] | None = None,
                  inputs: list[dict[str, Any]] | None = None, derived_from: str | None = None,
                  transformation: dict[str, Any] | None = None, declared: list[float] | None = None,
                  measured: list[dict[str, Any]] | None = None, rationale: str = "") -> dict[str, Any]:
    """Record a signal (or record it again): its data, what it is, where it came from, how good it is known to be.

    - `frames`: one array per frame (height, width) or (height, width, channels), at `rate`, the first at the
      media instant `start`;
    - `origin`: geometric, estimated or authored -- or, with `derived_from`, the parent's (a transformation
      never changes it), with `transformation` ({name, method, ...: its parameters, reference, residual})
      added to the parent's provenance;
    - `maker`: what made it ({kind: renderer | model | tool | person, name, version, parameters, ...});
    - `inputs`: what it was made from -- `{"media": path}`, `{"file": path}`, `{"signal": id}` -- each
      recorded with its hash or revision, so a change is seen;
    - `declared`: the maker's confidence per frame, if it gave one; `measured`: errors found, each
      `{"against", "metric", "value", "how"}`. Neither is invented.
    """

    root = Path(root).expanduser().resolve()
    folder = directory(root, signal_id)
    parent = load_record(root, derived_from) if derived_from else None
    if parent is not None:
        if origin not in (None, parent["origin"]):
            raise ValidationError(f"{signal_id} is derived from {derived_from}, whose origin is {parent['origin']}: "
                                  "a transformation does not change where values came from")
        origin = parent["origin"]
        media = media or parent.get("media")
        if not transformation or not transformation.get("name"):
            raise ValidationError("A derived signal says the transformation that made it ({name, ...})")
    if origin is None:
        raise ValidationError("A signal says its origin: geometric, estimated or authored")
    problems = contract_problems(kind, origin, camera=camera, depth=depth, labels=labels)
    if problems:
        raise ValidationError(f"The signal {signal_id} cannot be recorded: {'; '.join(problems)}")
    exact_rate = timebase.rate(rate)
    origin_instant = Fraction(start) if isinstance(start, Fraction) else Fraction(str(start))
    folder.mkdir(parents=True, exist_ok=True)
    with scene_lock(folder):
        record = yaml.safe_load((folder / "signal.yaml").read_text()) if (folder / "signal.yaml").is_file() else {}
        number = int(record.get("data", 0)) + 1
        target = folder / "data" / f"{number:04d}"
        target.mkdir(parents=True, exist_ok=True)
        size = None
        count = 0
        for index, frame in enumerate(frames):
            frame = np.asarray(frame)
            problems = _shape_problems(kind, frame)
            if problems:
                raise ValidationError(f"The signal {signal_id}'s frame {index}: {'; '.join(problems)}")
            if size is None:
                size = [int(frame.shape[1]), int(frame.shape[0])]
            elif [int(frame.shape[1]), int(frame.shape[0])] != size:
                raise ValidationError(f"The signal {signal_id}'s frames are all {size[0]}x{size[1]}")
            _write_frame(target / f"f_{index + 1:04d}", frame, kind)
            count += 1
        if not count:
            raise ValidationError(f"The signal {signal_id} has no frame")
        if declared is not None and len(declared) != count:
            raise ValidationError(f"The signal {signal_id}'s declared confidence has {len(declared)} values for "
                                  f"{count} frames")
        recorded_inputs = [_pinned(root, item) for item in (inputs or [])]
        if media:
            recorded_inputs.insert(0, _pinned(root, {"media": media}))
        if parent is not None:
            recorded_inputs.append(_pinned(root, {"signal": derived_from}))
            reference = (transformation or {}).get("reference")
            if isinstance(reference, str):
                recorded_inputs.append(_pinned(root, {"signal": reference}))
        step = {"step": "derived" if parent else "made", "at": _now(), "by": actor.public_dict(),
                **({"maker": maker} if maker else {}), **({"transformation": transformation} if transformation else {}),
                "inputs": recorded_inputs, "data": number}
        history = (parent["provenance"] if parent else []) + [step]
        _write(folder / "provenance.json", json.dumps(history, indent=1, default=str))
        quality = {"declared": declared, "measured": measured or []}
        _write(folder / "quality.json", json.dumps(quality, indent=1))
        record = {
            "schema_version": 1, "id": signal_id, "kind": kind, "origin": origin, "media": media,
            "clock": {"rate": timebase.ffmpeg_rate(exact_rate), "origin": timebase.to_record(origin_instant)},
            "frames": count, "size": size, "coordinates": "pixels of the medium, top-left first, rows down",
            **({"camera": camera} if camera else {}), **({"depth": depth} if depth else {}),
            **({"labels": {int(k): str(v) for k, v in labels.items()}} if labels else {}),
            "data": number, "data_hash": _data_hash(target), "revision": int(record.get("revision", 0)) + 1,
            "updated_at": _now(),
        }
        _write(folder / "signal.yaml", yaml.safe_dump(record, sort_keys=False))
        command_id = "cmd_" + uuid.uuid4().hex[:16]
        event = append_event(root, Event.create("signal.recorded", _project_id(root), signal_id=signal_id,
                                                kind=kind, origin=origin, data=number, revision=record["revision"],
                                                actor=actor.public_dict(), rationale=rationale,
                                                command_id=command_id))
    return {"command_id": command_id, "type": "signal.recorded", "signal": signal_id, "data": number,
            "revision": record["revision"], "event": event.public_dict()}


def _pinned(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    """An input as it is now: a file or medium by its content hash, a signal by its revision and data."""

    if "signal" in item:
        record = load_record(root, str(item["signal"]))
        return {"signal": item["signal"], "revision": record["revision"], "data_hash": record["data_hash"]}
    key = "media" if "media" in item else "file"
    path = Path(root) / str(item[key])
    if not path.is_file():
        raise ValidationError(f"The signal's input {item[key]} is not there")
    return {key: str(item[key]), "hash": _file_hash(path)}


def correct_signal(root: Path, *, signal_id: str, frame: int, where: np.ndarray, values: np.ndarray, actor: Actor,
                   note: str = "") -> dict[str, Any]:
    """A person's correction of one frame: `values` where `where` is true -- kept apart, in force until
    reverted, the recorded data untouched."""

    root = Path(root).expanduser().resolve()
    folder = directory(root, signal_id)
    with scene_lock(folder):
        record = load_record(root, signal_id)
        if not 0 <= frame < int(record["frames"]):
            raise ValidationError(f"The signal {signal_id} has frames 0 to {int(record['frames']) - 1}, not {frame}")
        where = np.asarray(where, bool)
        values = np.asarray(values)
        if where.shape != (record["size"][1], record["size"][0]) or values.shape[:2] != where.shape:
            raise ValidationError(f"A correction is a mask and values the signal's size, {record['size']}")
        correction_id = "cor_" + uuid.uuid4().hex[:12]
        patches = folder / "corrections"
        patches.mkdir(exist_ok=True)
        np.save(patches / f"{correction_id}.where.npy", where)
        np.save(patches / f"{correction_id}.values.npy", values)
        listed = _corrections(folder)
        listed.append({"id": correction_id, "frame": int(frame), "data": record["data"], "active": True,
                       "note": note, "at": _now(), "by": actor.public_dict()})
        _write(patches / "corrections.json", json.dumps(listed, indent=1))
        record["revision"] = int(record["revision"]) + 1
        _write(folder / "signal.yaml", yaml.safe_dump(record, sort_keys=False))
        event = append_event(root, Event.create("signal.corrected", _project_id(root), signal_id=signal_id,
                                                frame=frame, correction=correction_id, revision=record["revision"],
                                                actor=actor.public_dict(), rationale=note))
    return {"type": "signal.corrected", "signal": signal_id, "correction": correction_id,
            "revision": record["revision"], "event": event.public_dict()}


def revert_signal_corrections(root: Path, *, signal_id: str, actor: Actor, correction: str | None = None,
                              frame: int | None = None, note: str = "") -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    folder = directory(root, signal_id)
    with scene_lock(folder):
        record = load_record(root, signal_id)
        listed = _corrections(folder)
        chosen = [item for item in listed if item["active"] and (correction is None or item["id"] == correction)
                  and (frame is None or item["frame"] == frame)]
        if not chosen:
            raise ValidationError(f"The signal {signal_id} has no correction in force to revert there")
        for item in chosen:
            item["active"] = False
            item["reverted"] = {"at": _now(), "by": actor.public_dict(), "note": note}
        _write(folder / "corrections" / "corrections.json", json.dumps(listed, indent=1))
        record["revision"] = int(record["revision"]) + 1
        _write(folder / "signal.yaml", yaml.safe_dump(record, sort_keys=False))
        event = append_event(root, Event.create("signal.reverted", _project_id(root), signal_id=signal_id,
                                                corrections=[item["id"] for item in chosen],
                                                revision=record["revision"], actor=actor.public_dict(), rationale=note))
    return {"type": "signal.reverted", "signal": signal_id, "reverted": [item["id"] for item in chosen],
            "revision": record["revision"], "event": event.public_dict()}


def _corrections(folder: Path) -> list[dict[str, Any]]:
    path = folder / "corrections" / "corrections.json"
    return json.loads(path.read_text()) if path.is_file() else []


# --- reading ----------------------------------------------------------------------------------------------------

def load_record(root: Path, signal_id: str) -> dict[str, Any]:
    """The signal's record with its provenance and quality (not its data)."""

    folder = directory(Path(root), signal_id)
    if not (folder / "signal.yaml").is_file():
        raise ValidationError(f"There is no signal {signal_id} (record it first)")
    record = yaml.safe_load((folder / "signal.yaml").read_text())
    record["provenance"] = json.loads((folder / "provenance.json").read_text())
    record["quality"] = json.loads((folder / "quality.json").read_text())
    return record


def status(root: Path, signal_id: str, _seen: frozenset[str] = frozenset()) -> dict[str, Any]:
    """What a signal is and whether it may be used: `stale` lists every reason it no longer follows from what
    made it (empty when it does); its quality as known (`unknown` when nothing was declared or measured)."""

    root = Path(root).expanduser().resolve()
    record = load_record(root, signal_id)
    folder = directory(root, signal_id)
    stale = []
    if _data_hash(folder / "data" / f"{int(record['data']):04d}") != record["data_hash"]:
        stale.append("its data has been changed outside its commands")
    last = record["provenance"][-1]
    for item in last.get("inputs") or []:
        if "signal" in item:
            name = str(item["signal"])
            if name in _seen:
                stale.append(f"it depends on itself through {name}")
                continue
            try:
                now = load_record(root, name)
            except ValidationError:
                stale.append(f"the signal {name} it was made from is gone")
                continue
            if now["data_hash"] != item["data_hash"]:
                stale.append(f"the signal {name} it was made from has been recorded again")
            elif status(root, name, _seen | {signal_id})["stale"]:
                stale.append(f"the signal {name} it was made from is stale")
        else:
            key = "media" if "media" in item else "file"
            path = root / item[key]
            if not path.is_file():
                stale.append(f"its {key} {item[key]} is not there")
            elif _file_hash(path) != item["hash"]:
                stale.append(f"its {key} {item[key]} has changed since")
    quality = record["quality"]
    known = bool(quality.get("declared")) or bool(quality.get("measured"))
    return {"id": signal_id, "kind": record["kind"], "origin": record["origin"], "revision": record["revision"],
            "stale": stale, "quality": quality if known else "unknown",
            "transformations": [step["transformation"]["name"] for step in record["provenance"]
                                if step.get("transformation")],
            "corrections": len([item for item in _corrections(folder) if item["active"]
                                and item["data"] == record["data"]])}


class SignalReader:
    """A signal as a graph reads it: checked once (refused when stale), then frame by frame -- the data in use
    with the corrections in force laid over it; past its last frame its last, before its first its first."""

    def __init__(self, root: Path, signal_id: str) -> None:
        self.root = Path(root).expanduser().resolve()
        state = status(self.root, signal_id)
        if state["stale"]:
            raise ValidationError(f"The signal {signal_id} is stale: {'; '.join(state['stale'])} -- record it again")
        self.id, self.record = signal_id, load_record(self.root, signal_id)
        self.folder = directory(self.root, signal_id)
        self.corrections = [item for item in _corrections(self.folder)
                            if item["active"] and item["data"] == self.record["data"]]
        self.rate = timebase.rate(self.record["clock"]["rate"])
        self.origin = timebase.from_record(self.record["clock"]["origin"])

    def frame(self, index: int) -> np.ndarray:
        index = int(np.clip(index, 0, int(self.record["frames"]) - 1))
        stem = self.folder / "data" / f"{int(self.record['data']):04d}" / f"f_{index + 1:04d}"
        found = [path for path in (stem.with_suffix(".exr"), stem.with_suffix(".npy")) if path.is_file()]
        data = _read_frame(found[0])
        for item in self.corrections:
            if item["frame"] == index:
                where = np.load(self.folder / "corrections" / f"{item['id']}.where.npy")
                values = np.load(self.folder / "corrections" / f"{item['id']}.values.npy")
                data = data.copy()
                data[where] = values[where]
        return data

    def at(self, media: Any) -> np.ndarray:
        """The frame showing at a media instant (seconds), by the signal's clock."""

        from .compositing.semantics import remap_samples

        position = media - self.origin if isinstance(media, Fraction) else float(media) - float(self.origin)
        return self.frame(remap_samples(position, self.rate, "nearest", clamp=False)[0][0])


def frame(root: Path, signal_id: str, index: int) -> np.ndarray:
    """One frame of the signal (checked, corrected): `SignalReader(root, id).frame(index)`."""

    return SignalReader(root, signal_id).frame(index)
