"""Signals estimated by models, as production records (C8 step 3, CT-0081).

`estimate` runs a model of the catalog (`models.py`) over a stretch of a medium and records what it gives
through `signals.record_signal`, the one way every signal is kept (ADR 0024):

- **Depth Anything V2 Small** -- a relative depth, frame by frame: `depth_relative`, an affine-invariant
  inverse depth (larger is nearer; scale and shift unknown). Never metric: no camera, no unit, until a step of
  alignment says how it was fitted (C8 step 4).
- **Video Depth Anything Small** -- the same kind, estimated as a **sequence**: windows of frames, each aligned
  to the last; its record keeps the windows, the overlap and the stretch estimated together, and frame i of
  the signal is frame i of that stretch by the signal's clock.
- **SAM 2** -- objects, prompted on a frame (points or a box), followed through the stretch: a
  `segmentation` whose numbers are **instances** -- the label is the object's identity through time, its
  name only a name -- with what the model declared of each object per frame (its object score) kept as
  declared, never as measured. Beside it, each object's own probability as an `alpha` signal,
  `<id>-alpha-<label>`: a soft matte of it, its edge as the model saw it, where the labels alias.

What is recorded of each run: the model by name, repository, pinned revision, licence, and every weight (and
code) file by hash -- the files themselves pinned as inputs, so changed weights make the signal stale; the
parameters and prompts; the environment (Python, torch, transformers, device, threads, dtype); the
determinism asked for and, when `repeat` is asked, what a second run gave (identical, or the largest
difference: recorded, never promised); the medium by hash and the stretch read.

No inference here: the model runs in the vision environment as a worker (`vision_worker.py`); this module
reads the medium, hands frames over, and records. Nothing is downloaded (`models.require`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import models
from .errors import ValidationError
from .state import Actor

WORKER = Path(__file__).with_name("vision_worker.py")


def _in_production(root: Path, given: str | Path) -> str:
    path = Path(given)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_file():
        raise ValidationError(f"The medium {given} is not there")
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        raise ValidationError(f"The medium {given} is outside the production: a signal belongs to a medium of "
                              "the production, pinned by its hash") from None


def _rate(path: Path) -> Fraction:
    from . import timebase

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ValidationError("ffprobe is needed to read a medium's frames (it ships with FFmpeg)")
    found = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=r_frame_rate,width,height", "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=60)
    stream = (json.loads(found.stdout or "{}").get("streams") or [{}])[0]
    if not stream.get("width"):
        raise ValidationError(f"{path.name} has no picture to estimate from")
    rate = stream.get("r_frame_rate") or "24/1"
    return timebase.rate(rate if not rate.startswith("0") else "24/1")


def read_frames(path: Path, first: int, count: int | None) -> np.ndarray:
    """A stretch of a medium's frames as sRGB bytes (count, height, width, 3): FFmpeg's rgb24, the pixels a
    viewer of the medium sees -- what a model trained on pictures expects."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValidationError("FFmpeg is needed to read a medium's frames")
    probe = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=60)
    width, height = (int(value) for value in probe.stdout.strip().split(",")[:2])
    select = f"select=gte(n\\,{int(first)})" + (f"*lt(n\\,{int(first) + int(count)})" if count else "")
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-vf", select, "-vsync", "0", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=3600)
    if raw.returncode:
        raise ValidationError(f"FFmpeg could not read {path.name}: {raw.stderr.decode(errors='replace')[-300:]}")
    frames = np.frombuffer(raw.stdout, np.uint8)
    if frames.size == 0 or frames.size % (width * height * 3):
        raise ValidationError(f"{path.name} has no frames from {first}" + (f" for {count}" if count else ""))
    frames = frames.reshape(-1, height, width, 3)
    if count and len(frames) != int(count):
        raise ValidationError(f"{path.name} has {len(frames)} frames from {first}, not {count}")
    return frames


def _run_worker(python: Path, spec: dict[str, Any], work: Path, run: Callable[[list[str]], Any]) -> tuple:
    work.mkdir(parents=True, exist_ok=True)
    (work / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    try:
        run([str(python), str(WORKER), str(work / "spec.json")])
    except subprocess.CalledProcessError as error:
        tail = "\n".join(((error.stderr or "") + (error.stdout or "")).strip().splitlines()[-8:])
        raise ValidationError(f"The model {spec['model']} failed:\n{tail}") from None
    alpha = work / "out" / "alpha.npy"
    return (np.load(work / "out" / "result.npy"), json.loads((work / "out" / "meta.json").read_text()),
            np.load(alpha) if alpha.is_file() else None)


def estimate(root: Path, *, signal_id: str, model: str, media: str | Path, actor: Actor, first: int = 0,
             count: int | None = None, objects: list[dict[str, Any]] | None = None,
             parameters: dict[str, Any] | None = None, threads: int | None = None, repeat: bool = False,
             run: Callable[[list[str]], Any] | None = None) -> dict[str, Any]:
    """Estimate a signal of a medium's stretch (`first`, `count` frames; all from `first` when not given) with a
    model of the catalog, and record it. SAM 2 takes `objects`: each `{"name", "frame" (of the stretch),
    "points": [[x, y], ...] (pixels) and optionally "point_labels" (1 in, 0 out), or "box": [x0, y0, x1, y1]}`;
    their labels are 1, 2, ... in the order given. `repeat` runs the model twice and records what differed."""

    from .signals import record_signal

    root = Path(root).expanduser().resolve()
    model_entry = models.require(model)
    python = models.vision_python()
    reason = models.vision_unavailable_reason() if python else "no vision environment"
    if reason:
        raise ValidationError(f"Models run in the vision environment: {reason}")
    parameters = dict(parameters or {})
    if model_entry["runner"] == "sam2_video":
        if not objects:
            raise ValidationError("SAM 2 follows objects it is shown: give `objects` (a name, a frame, and points "
                                  "or a box)")
        for index, item in enumerate(objects):
            if not item.get("name") or not (item.get("points") or item.get("box")):
                raise ValidationError(f"Object {index + 1} needs a name and points or a box")
        objects = [{**item, "label": index + 1, "frame": int(item.get("frame", 0))}
                   for index, item in enumerate(objects)]
        parameters["objects"] = objects
        if len(f"{signal_id}-alpha-{len(objects)}") > 63:  # each object's soft matte is a signal of its own
            raise ValidationError(f"{signal_id} is too long to name its objects' soft mattes "
                                  f"({signal_id}-alpha-{len(objects)}): 63 characters at most")
    elif objects:
        raise ValidationError(f"{model} takes no objects")
    medium = _in_production(root, media)
    rate = _rate(root / medium)
    frames = read_frames(root / medium, int(first), count)
    for item in objects or []:
        if not 0 <= item["frame"] < len(frames):
            raise ValidationError(f"{item['name']} is shown on frame {item['frame']}, outside the stretch "
                                  f"(0 to {len(frames) - 1})")
    run = run or (lambda command: subprocess.run(command, check=True, capture_output=True, text=True))
    with tempfile.TemporaryDirectory(prefix="ct-estimate-") as work:
        work = Path(work)
        np.save(work / "frames.npy", frames)
        spec = {"model": model, "runner": model_entry["runner"], "model_dir": model_entry["directory"],
                "frames": str(work / "frames.npy"), "fps": float(rate), "threads": threads,
                "parameters": parameters}
        result, meta, alpha = _run_worker(python, {**spec, "output": str(work / "a" / "out")}, work / "a", run)
        repeated = None
        if repeat:
            again, _, alpha_again = _run_worker(python, {**spec, "output": str(work / "b" / "out")}, work / "b",
                                                run)
            difference = float(np.abs(again.astype(np.float64) - result.astype(np.float64)).max())
            identical = bool(np.array_equal(again, result))
            if alpha is not None and alpha_again is not None:
                difference_alpha = float(np.abs(alpha_again.astype(np.float64) - alpha.astype(np.float64)).max())
                identical = identical and bool(np.array_equal(alpha_again, alpha))
            repeated = {"identical": identical, "max_difference": difference,
                        **({"max_difference_alpha": difference_alpha} if alpha is not None and
                           alpha_again is not None else {}),
                        "how": "the same frames, parameters, threads and weights, run twice"}
    if result.shape[0] != len(frames) or result.shape[1:3] != frames.shape[1:3]:
        raise ValidationError(f"{model} gave {result.shape}, not one value per pixel of {len(frames)} frames")

    folder = Path(model_entry["directory"])
    installed = model_entry["installed"]
    pinned = sorted(installed["files"])  # weights, configurations and code: any changed, the result may differ
    maker = {"kind": "model", "name": model, "version": model_entry["revision"], "repo": model_entry["repo"],
             "licence": model_entry["licence"], **({"code": installed["code"]} if installed.get("code") else {}),
             "files": installed["files"], "parameters": {key: value for key, value in parameters.items()
                                                         if key != "objects"},
             "time": model_entry["time"], "stretch": {"first": int(first), "count": len(frames)},
             "pixels": "FFmpeg rgb24 of the medium (sRGB as viewed)",
             "environment": {key: meta.get(key) for key in ("python", "torch", "transformers", "device", "threads",
                                                             "dtype")},
             "determinism": {**meta.get("determinism", {}), "repeat": repeated or "not checked"},
             **{key: meta[key] for key in ("model_input", "resized", "temporal", "overlaps", "threshold")
                if key in meta}}
    inputs = [{"external": str(folder / name)} for name in pinned]
    start = Fraction(int(first)) / rate
    common = dict(signal_id=signal_id, kind=model_entry["kind"], origin="estimated", rate=rate, start=start,
                  media=medium, maker=maker, inputs=inputs, actor=actor,
                  rationale=f"{model} on {medium} from frame {first}")
    if model_entry["kind"] == "segmentation":
        if alpha is None or alpha.shape != (len(frames), len(objects), *frames.shape[1:3]):
            raise ValidationError(f"{model} gave no soft matte of each object (alpha.npy, one per object a frame)")
        soft = {item["label"]: f"{signal_id}-alpha-{item['label']}" for item in objects}
        maker["alphas"] = soft
        maker["objects"] = [{"label": item["label"], "name": item["name"], "frame": item["frame"],
                             **{key: item[key] for key in ("points", "point_labels", "box") if key in item}}
                            for item in objects]
        by_object = meta["declared"]["by_object"]
        maker["declared"] = meta["declared"]
        declared = [float(np.mean([by_object[str(item["label"])][index] for item in objects]))
                    for index in range(len(frames))]
        made = record_signal(root, frames=list(result.astype(np.int32)), declared=declared,
                             labels={0: "nothing", **{item["label"]: item["name"] for item in objects}},
                             labels_are="instances", **common)
        for index, item in enumerate(objects):  # each object's soft matte, from the same run
            record_signal(root, **{**common, "signal_id": soft[item["label"]], "kind": "alpha",
                                   "maker": {**maker, "object": {"label": item["label"], "name": item["name"]},
                                             "alpha": meta.get("alpha")},
                                   "rationale": f"{item['name']}'s soft matte: {common['rationale']}"},
                          frames=list(alpha[:, index]), declared=[float(value) for value in
                                                                  meta["declared"]["by_object"][str(item["label"])]])
        made = {**made, "alphas": soft}
    else:
        made = record_signal(root, frames=list(result.astype(np.float32)), depth=dict(model_entry["depth"]),
                             **common)
    return {**made, "model": model, "frames": len(frames), "repeat": repeated, "seconds": meta.get("seconds")}


def compare(root: Path, *, signal_id: str, reference: str, actor: Actor) -> dict[str, Any]:
    """Measure an estimate against a reference signal -- a renderer's geometry, a person's matte -- frame by
    frame at the same media instants, and record it as measured quality (`signals.record_measurement`):

    - a segmentation against a segmentation: each object's intersection over union with the reference's
      object of the same name, per frame;
    - a relative depth against a metric depth: the correlation of the estimate with the reference brought to
      the estimate's quantity (an inverse z for an inverse z) where the reference hit something -- 1 when an
      affine map would fit exactly; the fitted map itself is an alignment's (C8 step 4).
    """

    from .signals import SignalReader, record_measurement

    root = Path(root).expanduser().resolve()
    estimate_reader, reference_reader = SignalReader(root, signal_id), SignalReader(root, reference)
    record, truth = estimate_reader.record, reference_reader.record
    per_frame: list[Any] = []
    for index in range(int(record["frames"])):
        instant = estimate_reader.origin + Fraction(index) / estimate_reader.rate
        mine, theirs = estimate_reader.frame(index), reference_reader.at(instant)
        if mine.shape != theirs.shape:
            raise ValidationError(f"{signal_id} is {mine.shape[1]}x{mine.shape[0]}, {reference} "
                                  f"{theirs.shape[1]}x{theirs.shape[0]}: compared only at one size")
        if record["kind"] == "segmentation" and truth["kind"] == "segmentation":
            names = {name: int(number) for number, name in truth["labels"].items()}
            scores = {}
            for number, name in record["labels"].items():
                if int(number) == 0 or name not in names:
                    continue
                a, b = mine == int(number), theirs == names[name]
                union = int((a | b).sum())
                scores[name] = round(float((a & b).sum()) / union, 4) if union else None
            per_frame.append(scores)
        elif record["kind"] == "depth_relative" and truth["kind"] == "depth":
            hit = np.isfinite(theirs) & (theirs > 0)
            quantity = record["depth"]["quantity"]
            target = 1.0 / theirs[hit] if quantity.startswith("inverse") else theirs[hit]
            per_frame.append(round(float(np.corrcoef(mine[hit].astype(np.float64), target)[0, 1]), 4))
        else:
            raise ValidationError(f"A {record['kind']} is not compared with a {truth['kind']} here")
    metric = "iou by object name" if record["kind"] == "segmentation" else "correlation with the reference's " \
        f"{record['depth']['quantity']}"
    how = f"frame by frame at the same media instants; the reference {reference} at revision {truth['revision']}"
    record_measurement(root, signal_id=signal_id, against=f"signal:{reference}", metric=metric, value=per_frame,
                       how=how, actor=actor)
    return {"signal": signal_id, "against": reference, "metric": metric, "per_frame": per_frame}
