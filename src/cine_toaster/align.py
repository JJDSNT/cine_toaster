"""A relative depth aligned to a metric one, over a stretch, with its residual (C8 step 4, CT-0081).

A monocular model's depth (`depth_relative`, an affine-invariant inverse depth) is not in metres. Aligning it
fits, against a reference depth of the same pixels -- a renderer's Z, a surface's own depth -- the map

    1 / z  =  s * e + t          (e: the estimate; z: the reference's z along the camera's axis)

and records the result as a `depth` **derived** from the estimate: still `estimated` (ADR 0024), its
transformation in its provenance with the reference pinned, its parameters, its exclusions and its residuals.

- **Time**: `regularized` (the default) fits one (s, t) per frame with a penalty `smoothness` on how much the
  map changes between frames, over the real time between them (1: a change costs as much as that error on
  every pixel); `shared` fits one for the whole stretch; `per_frame` fits each frame alone. All three are
  fitted and compared on every alignment, and the comparison recorded. Measured in CT-0081 on a rendered
  dolly with an occlusion: none is best everywhere. A frame-by-frame model (Depth Anything V2) changes its
  own scale from frame to frame (fitted s from 0.006 to 0.027), so `shared` carries that flicker into metres
  (the worst temporal agreement in every case); `per_frame` was best in three cases of four; `regularized`
  never the worst, and the best for the video model against a partial reference (a floor). The default is
  the one that does not fail badly; the choice is the caller's and on record.
- **What is fitted on**: pixels where the reference hit something (finite, positive), the estimate is finite,
  away from the reference's depth discontinuities (a band where the inverse depth jumps by more than
  `edge_jump` of its own value between neighbours: silhouettes, where the two disagree by construction), inside an optional
  region (a segmentation's labels to keep or leave out). Robust: each frame fitted alone, its pixels beyond
  `trim` times the median absolute residual dropped, then the chosen way fitted on what is left. Absence
  is never a value: what is not measured is left out.
- **The result**: z = 1 / (s e + t); where s e + t is zero or less the estimate is beyond the calibration's
  reach and the pixel is **unknown** -- a mask kept with the signal, apart from any value: not +inf (that is
  a renderer's "nothing there"), never 0. `merge.depth` refuses an unknown pixel where its picture shows,
  unless told `unknown: behind` or `front`.
- **Residuals**, measured in metres on the calibration's pixels and, separately, **held out** two ways:
  pixels -- alternate 8-pixel blocks left out of a second fit and measured with it -- and frames -- alternate
  frames left out, their parameters interpolated in time, measured there: a calibration that holds only at
  the instants it saw is caught. Beyond a region, where the reference has values the calibration was not
  given. The three ways of fitting time are measured on the same frames, beside a constant depth (what an
  alignment must beat), and the comparison is recorded. MAE, RMSE, AbsRel, median, p90, p95, max, coverage, correlation, the share of
  pixel pairs ordered as the reference orders them, and the temporal agreement (how the aligned depth changes
  from frame to frame against how the reference does).
- **Validity**: the aligned signal covers the calibrated stretch only, and reading it outside is refused,
  not held (`outside: refuse`).
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from .errors import ValidationError
from .state import Actor

TEMPORAL = ("shared", "regularized", "per_frame")


def valid_pixels(estimate: np.ndarray, reference: np.ndarray, *, edge_jump: float,
                 region: np.ndarray | None = None) -> np.ndarray:
    """Where a calibration may look: the reference hit something, the estimate is a number, the reference's
    inverse depth does not jump there (a silhouette's band), and the region allows it."""

    usable = np.isfinite(reference) & (reference > 0) & np.isfinite(estimate)
    inverse = np.where(usable, 1.0 / np.where(usable, reference, 1.0), 0.0)
    jump = np.zeros(reference.shape, bool)
    for axis in (0, 1):
        # A jump relative to the pixels' own inverse depth, not the frame's: a step of 1 cm is an edge at
        # 10 cm and nothing at 10 m.
        here = np.minimum(inverse[:-1] if axis == 0 else inverse[:, :-1], inverse[1:] if axis == 0 else inverse[:, 1:])
        step = np.abs(np.diff(inverse, axis=axis)) > edge_jump * np.maximum(here, 1e-12)
        broken = np.diff(usable.astype(np.int8), axis=axis) != 0  # where the reference starts or stops hitting
        step |= broken
        pad = [(0, 0), (0, 0)]
        pad[axis] = (1, 0)
        jump |= np.pad(step, pad)
        pad[axis] = (0, 1)
        jump |= np.pad(step, pad)
    usable &= ~jump
    if region is not None:
        usable &= region
    return usable


def _sums(e: np.ndarray, r: np.ndarray) -> np.ndarray:
    """A frame's normal equations for (s, t): [Σe², Σe, n, Σe r, Σr]."""

    return np.array([float(np.dot(e, e)), float(e.sum()), float(e.size), float(np.dot(e, r)), float(r.sum())])


def _solve(sums: list[np.ndarray], mode: str, smoothness: float, times: list[float]) -> np.ndarray:
    count = len(sums)
    if mode == "shared":
        total = np.sum(sums, axis=0)
        matrix = np.array([[total[0], total[1]], [total[1], total[2]]])
        if abs(np.linalg.det(matrix)) < 1e-12:
            raise ValidationError("Too few pixels vary to fit a scale and a shift")
        return np.tile(np.linalg.solve(matrix, [total[3], total[4]]), (count, 1))
    matrix = np.zeros((2 * count, 2 * count))
    vector = np.zeros(2 * count)
    for index, item in enumerate(sums):
        block = slice(2 * index, 2 * index + 2)
        matrix[block, block] += [[item[0], item[1]], [item[1], item[2]]]
        vector[block] += [item[3], item[4]]
    if mode == "regularized" and count > 1:
        # λ Σ |Δmap|² / Δt: how much the map from estimate to inverse depth changes between two frames --
        # (Δs e + Δt)² averaged over the stretch's estimates, a quadratic form with E[e²], E[e] and 1 (penalizing
        # s and t apart, a change of scale is wrongly paid for by a shift) -- over the real time between the
        # frames fitted (frames left out, or sampled irregularly, are farther apart and may differ more).
        # λ = 1 makes a change cost what that error on every pixel of a frame would, at the stretch's usual
        # frame interval.
        total = np.sum(sums, axis=0)
        pixels = max(total[2], 1.0)
        form = np.array([[total[0] / pixels, total[1] / pixels], [total[1] / pixels, 1.0]])
        usual = float(np.median(np.diff(times))) or 1.0
        for index in range(1, count):
            weight = smoothness * pixels / count * usual / max(times[index] - times[index - 1], 1e-9)
            a, b = slice(2 * (index - 1), 2 * index), slice(2 * index, 2 * index + 2)
            matrix[a, a] += weight * form
            matrix[b, b] += weight * form
            matrix[a, b] -= weight * form
            matrix[b, a] -= weight * form
    return np.linalg.lstsq(matrix, vector, rcond=None)[0].reshape(count, 2)


def fit(estimates: list[np.ndarray], references: list[np.ndarray], masks: list[np.ndarray], *, mode: str,
        times: list[float], smoothness: float = 1.0, trim: float = 3.0) -> tuple[np.ndarray, list[np.ndarray]]:
    """(s, t) per frame, fitted robustly in inverse depth on each frame's mask; the masks after trimming."""

    if mode not in TEMPORAL:
        raise ValidationError(f"An alignment's time is one of {', '.join(TEMPORAL)}, not {mode!r}")
    kept = [mask.copy() for mask in masks]
    # Outliers are judged against each frame's own fit, never against a compromise across frames (a frame
    # that a smooth fit cannot follow is not made of outliers); then the chosen way is fitted on what is left.
    for attempt in range(2):
        sums = []
        for e, r, mask in zip(estimates, references, kept):
            if mask.sum() < 16:
                raise ValidationError("A frame has fewer than 16 pixels to calibrate on")
            sums.append(_sums(e[mask].astype(np.float64), 1.0 / r[mask].astype(np.float64)))
        parameters = _solve(sums, mode if attempt or trim <= 0 else "per_frame", smoothness, times)
        if trim <= 0 or attempt:
            break
        for index, (e, r, mask) in enumerate(zip(estimates, references, kept)):
            residual = np.abs(parameters[index, 0] * e[mask] + parameters[index, 1] - 1.0 / r[mask])
            # A spread never below a thousandth of the inverse depths' own level: on exact data the residuals
            # are rounding, and trimming them would throw away good pixels at random.
            floor = 1e-3 * float(np.median(1.0 / r[mask]))
            spread = max(float(np.median(np.abs(residual - np.median(residual)))), floor)
            keep = residual <= np.median(residual) + trim * 1.4826 * spread
            mask[np.nonzero(mask)[0][~keep], np.nonzero(mask)[1][~keep]] = False
    return parameters, kept


def apply(estimate: np.ndarray, s: float, t: float) -> tuple[np.ndarray, np.ndarray]:
    """z from the estimate, 1 / (s e + t), and where it has none: s e + t zero or less is the estimate beyond
    the calibration's reach -- **unknown**, not far (its value a placeholder, +inf, never 0)."""

    inverse = s * estimate.astype(np.float64) + t
    unknown = ~(inverse > 0)
    with np.errstate(divide="ignore"):
        return np.where(unknown, np.inf, 1.0 / np.where(unknown, 1.0, inverse)).astype(np.float32), unknown


def residuals(aligned: list[np.ndarray], references: list[np.ndarray], masks: list[np.ndarray],
              seed: int = 0) -> dict[str, Any]:
    """Errors in the reference's unit on the masked pixels, frame by frame and over the stretch."""

    rng = np.random.default_rng(seed)
    per_frame = []
    all_errors, all_relative = [], []
    unknown = []
    for z, r, mask in zip(aligned, references, masks):
        unknown.append(int((mask & ~np.isfinite(z)).sum()))
        usable = mask & np.isfinite(z)
        error = np.abs(z[usable].astype(np.float64) - r[usable])
        relative = error / r[usable]
        all_errors.append(error)
        all_relative.append(relative)
        pairs = rng.integers(0, int(usable.sum()), size=(4000, 2)) if usable.sum() > 1 else np.zeros((0, 2), int)
        a, b = z[usable][pairs[:, 0]], z[usable][pairs[:, 1]]
        ra, rb = r[usable][pairs[:, 0]], r[usable][pairs[:, 1]]
        apart = np.abs(ra - rb) > 0.05 * np.minimum(ra, rb)  # pairs the reference tells apart
        order = float(np.mean(np.sign(a[apart] - b[apart]) == np.sign(ra[apart] - rb[apart]))) if apart.any() else None
        per_frame.append({"mae": round(float(error.mean()), 5), "abs_rel": round(float(relative.mean()), 5),
                          "coverage": round(float(mask.sum()) / mask.size, 4),
                          "order_agreement": None if order is None else round(order, 4)})
    error, relative = np.concatenate(all_errors), np.concatenate(all_relative)
    zs = np.concatenate([z[m & np.isfinite(z)] for z, m in zip(aligned, masks)]).astype(np.float64)
    rs = np.concatenate([r[m & np.isfinite(z)] for z, r, m in zip(aligned, references, masks)])
    return {"mae": round(float(error.mean()), 5), "rmse": round(float(np.sqrt(np.mean(error ** 2))), 5),
            "abs_rel": round(float(relative.mean()), 5), "median": round(float(np.median(error)), 5),
            "p90": round(float(np.percentile(error, 90)), 5), "p95": round(float(np.percentile(error, 95)), 5),
            "max": round(float(error.max()), 5), "correlation": round(float(np.corrcoef(zs, rs)[0, 1]), 5),
            "coverage": round(float(np.mean([item["coverage"] for item in per_frame])), 4),
            # Pairs of pixels ordered as the reference orders them. An alignment with s > 0 is monotone within a
            # frame, so this measures the estimate itself; the alignment cannot invert a frame's order.
            "order_agreement": round(float(np.mean([item["order_agreement"] for item in per_frame
                                                   if item["order_agreement"] is not None])), 4),
            # Pixels the reference measured where the aligned depth has none (s e + t <= 0): left out above.
            "unknown": round(sum(unknown) / max(sum(int(m.sum()) for m in masks), 1), 4),
            "per_frame": per_frame}


def temporal_agreement(aligned: list[np.ndarray], references: list[np.ndarray],
                       masks: list[np.ndarray]) -> dict[str, Any]:
    """How the aligned depth changes from one frame to the next against how the reference does, on pixels valid
    in both: a fit that flickers changes where the scene does not."""

    changes = []
    for index in range(1, len(aligned)):
        both = masks[index] & masks[index - 1] & np.isfinite(aligned[index]) & np.isfinite(aligned[index - 1])
        if not both.any():
            continue
        mine = aligned[index][both].astype(np.float64) - aligned[index - 1][both]
        theirs = references[index][both].astype(np.float64) - references[index - 1][both]
        changes.append(float(np.mean(np.abs(mine - theirs))))
    return {"mean_change_error": round(float(np.mean(changes)), 5) if changes else None,
            "per_step": [round(value, 5) for value in changes]}


def _grown(mask: np.ndarray, pixels: int) -> np.ndarray:
    grown = mask.copy()
    for _ in range(pixels):
        step = grown.copy()
        step[1:] |= grown[:-1]
        step[:-1] |= grown[1:]
        step[:, 1:] |= grown[:, :-1]
        step[:, :-1] |= grown[:, 1:]
        grown = step
    return grown


def occlusions(aligned: list[np.ndarray], unknown: list[np.ndarray], references: list[np.ndarray],
               labels: list[np.ndarray], names: dict[int, str], *, apart: float = 0.05,
               band: int = 3) -> dict[str, Any]:
    """Each pair of objects ordered by the aligned depth against the reference, frame by frame -- where it
    decides what is seen: along the line where the two meet in the picture, each object's pixels within
    `band` pixels of the other, their medians compared (an extended surface's own median says nothing of
    what stands on it: a floor runs from the camera's feet to the wall). Where two meet and the reference sets
    them more than `apart` apart, the pair is an **occlusion**; **inverted** when the aligned depth orders
    them the other way: the one in front would be drawn behind -- an error a small average hides. Pairs that
    do not meet are ordered by their whole medians, reported apart. Flagged, never corrected."""

    pairs: dict[str, dict[str, list[int]]] = {}
    for index, (z, gone, r, label) in enumerate(zip(aligned, unknown, references, labels)):
        known = ~gone & np.isfinite(r) & np.isfinite(z)
        present = [int(n) for n in np.unique(label) if int(n) != 0 and int(n) in names]
        masks = {n: (label == n) & known for n in present}
        present = [n for n in present if masks[n].sum() >= 8]
        for i, a in enumerate(present):
            for b in present[i + 1:]:
                key = f"{names[a]}/{names[b]}"
                entry = pairs.setdefault(key, {"met": [], "occlusion_inverted": [], "apart_inverted": []})
                near_a, near_b = masks[a] & _grown(masks[b], band), masks[b] & _grown(masks[a], band)
                meet = near_a.sum() >= 4 and near_b.sum() >= 4
                pa, pb = (near_a, near_b) if meet else (masks[a], masks[b])
                za, zb = float(np.median(z[pa])), float(np.median(z[pb]))
                ra, rb = float(np.median(r[pa])), float(np.median(r[pb]))
                inverted = abs(ra - rb) > apart * min(ra, rb) and np.sign(za - zb) != np.sign(ra - rb)
                if meet and abs(ra - rb) > apart * min(ra, rb):
                    entry["met"].append(index)
                if inverted:
                    entry["occlusion_inverted" if meet else "apart_inverted"].append(index)
    flagged = {key: entry["occlusion_inverted"] for key, entry in pairs.items() if entry["occlusion_inverted"]}
    return {"pairs": pairs, "occlusions_inverted": flagged,
            "how": f"where two objects meet (within {band} pixels), the medians of each one's pixels along the "
                   f"meeting; an occlusion when the reference sets them {apart:.0%} apart there, inverted when "
                   "the aligned depth orders them the other way; pairs that do not meet by their whole medians"}


def _blocks(shape: tuple[int, int], size: int = 8) -> np.ndarray:
    rows, cols = np.indices(shape)
    return ((rows // size + cols // size) % 2).astype(bool)


def align_depth(root: Path, *, signal_id: str, estimate: str, reference: str, camera: str, actor: Actor,
                temporal: str = "regularized", smoothness: float = 1.0, first: int = 0, count: int | None = None,
                region: str | None = None, keep_labels: list[int] | None = None,
                leave_labels: list[int] | None = None, edge_jump: float = 0.05, trim: float = 3.0,
                objects: str | None = None) -> dict[str, Any]:
    """Align the relative depth `estimate` (its frames `first`.. `count`) to the metric depth `reference` at the
    same media instants, and record the result as `signal_id`. `camera` is the caller's statement that the
    reference's camera sees the estimate's medium -- checked against the reference, recorded. `region`, a
    segmentation of the same pixels, with `keep_labels` or `leave_labels`. `objects`, a segmentation of
    instances, orders each pair of objects against the reference and flags the occlusions inverted."""

    from .signals import SignalReader, record_signal

    root = Path(root).expanduser().resolve()
    source, truth = SignalReader(root, estimate), SignalReader(root, reference)
    if source.record["kind"] != "depth_relative":
        raise ValidationError(f"{estimate} is a {source.record['kind']}: only a relative depth is aligned")
    if truth.record["kind"] != "depth":
        raise ValidationError(f"{reference} is a {truth.record['kind']}: a relative depth is aligned to a metric "
                              "depth")
    if truth.record.get("camera") != camera:
        raise ValidationError(f"{reference} is from the camera {truth.record.get('camera')!r}, not {camera!r}: "
                              "say the camera that sees the estimate's medium")
    if truth.record["depth"].get("quantity") != "z":
        raise ValidationError(f"{reference} measures {truth.record['depth'].get('quantity')}; the alignment fits "
                              "an inverse z to a z")
    if source.record["depth"].get("quantity") != "inverse_z":
        raise ValidationError(f"{estimate} measures {source.record['depth'].get('quantity')}; the alignment fits "
                              "an inverse z")
    total = int(source.record["frames"])
    count = total - int(first) if count is None else int(count)
    if not (0 <= int(first) and count > 0 and int(first) + count <= total):
        raise ValidationError(f"{estimate} has frames 0 to {total - 1}, not {first} and {count} more")
    regions = SignalReader(root, region) if region else None
    if regions is not None and regions.record["kind"] != "segmentation":
        raise ValidationError(f"{region} is not a segmentation")
    reference_span = (truth.origin, truth.origin + Fraction(int(truth.record["frames"])) / truth.rate)
    estimates, references, masks, everywhere, instants = [], [], [], [], []
    for index in range(int(first), int(first) + count):
        instant = source.origin + Fraction(index) / source.rate
        if not reference_span[0] <= instant < reference_span[1]:
            raise ValidationError(f"{reference} does not reach the estimate's frame {index} ({float(instant):.3f} s "
                                  "of the medium): a calibration is measured, never extrapolated")
        e, r = source.frame(index).astype(np.float32), truth.at(instant).astype(np.float32)
        if e.shape != r.shape:
            raise ValidationError(f"{estimate} is {e.shape[1]}x{e.shape[0]}, {reference} {r.shape[1]}x{r.shape[0]}:"
                                  " aligned only pixel for pixel")
        allowed = None
        if regions is not None:
            labels = regions.at(instant)
            allowed = (np.isin(labels, keep_labels) if keep_labels else np.ones(labels.shape, bool))
            if leave_labels:
                allowed &= ~np.isin(labels, leave_labels)
        estimates.append(e)
        references.append(r)
        masks.append(valid_pixels(e, r, edge_jump=edge_jump, region=allowed))
        everywhere.append(valid_pixels(e, r, edge_jump=edge_jump))
        instants.append(instant)
    times = [float(instant) for instant in instants]
    if temporal not in TEMPORAL:
        raise ValidationError(f"An alignment's time is one of {', '.join(TEMPORAL)}, not {temporal!r}")
    settings = dict(smoothness=smoothness, trim=trim)
    chosen = _evaluate(temporal, estimates, references, masks, everywhere, times, region is not None, **settings)
    parameters = chosen["parameters"]
    if (parameters[:, 0] <= 0).any():
        frames = [int(first) + index for index in np.nonzero(parameters[:, 0] <= 0)[0]]
        raise ValidationError(f"The fit's scale is not positive on frames {frames}: the estimate would be turned "
                              "inside out (near made far). Its quantity, or the reference, is not what was said")
    # The other ways of fitting time, measured on the same frames and references: the choice is on record.
    compared = {mode: (chosen if mode == temporal else
                       _evaluate(mode, estimates, references, masks, everywhere, times, region is not None,
                                 **settings))["summary"] for mode in TEMPORAL}
    # A depth that knows nothing: every pixel at the reference's median -- what an alignment must beat.
    flat = [np.full(r.shape, float(np.median(r[m])), np.float32) for r, m in zip(references, masks)]
    compared["baseline: a constant depth"] = {"abs_rel": residuals(flat, references, masks)["abs_rel"]}
    unit = truth.record["depth"]["unit"]
    summary = chosen["summary"]
    ordering = None
    if objects:
        named = SignalReader(root, objects)
        if named.record["kind"] != "segmentation" or named.record.get("labels_are") != "instances":
            raise ValidationError(f"{objects} is not a segmentation of instances: objects are ordered one by one")
        ordering = occlusions(chosen["aligned"], chosen["unknown"], references,
                              [named.at(instant) for instant in instants],
                              {int(k): v for k, v in named.record["labels"].items()})
    transformation = {
        "name": "align_depth", "method": "affine in inverse depth: 1/z = s e + t, least squares, trimmed",
        "temporal": temporal, **({"smoothness": smoothness, "time": "penalty on the change over the real "
                                  "interval between frames fitted"} if temporal == "regularized" else {}),
        "reference": reference, "camera": camera, "camera_stated_by": actor.public_dict(),
        "stretch": {"first": int(first), "count": count},
        # The depths it was fitted on: beyond them, the map is an extrapolation (measured poor in CT-0081).
        "depth_range": chosen["depth_range"],
        "parameters": [{"s": round(float(a), 8), "t": round(float(b), 8)} for a, b in parameters],
        "excluded": {"reference_missing": "+inf, non-finite or not positive", "edges":
                     f"a band where the reference's inverse depth jumps by more than {edge_jump:.0%}",
                     "region": {"signal": region, "keep": keep_labels, "leave": leave_labels} if region else None,
                     "trim": f"beyond {trim} x the median absolute residual, after a first fit"},
        **summary, "modes_compared": compared,
        **({"objects": objects, "order_by_objects": ordering["pairs"],
            "occlusions_inverted": ordering["occlusions_inverted"]} if ordering else {}),
        "unknown": "where s e + t <= 0: no depth (masked, `unknown`), never far",
    }
    measured = [{"against": f"signal:{reference}", "metric": f"{what} ({unit})", "value": chosen["full"][key],
                 "how": how} for key, what, how in (
        ("residual", "error on the calibration's pixels", "in sample: every pixel the calibration could use"),
        ("held_out_pixels", "error, pixels held out", "fitted on alternate 8-pixel blocks, measured on the others"),
        ("held_out_frames", "error, frames held out", "fitted on alternate frames, measured on the others with "
                                                      "parameters interpolated in time"),
        ("held_out_tail", "error, the last stretch held out", "fitted without the last quarter of the frames, "
                                                              "measured there with the last fitted parameters"),
        ("beyond_region", "error beyond the region", "where the reference has a value the calibration was not "
                                                     "given"),
        ("temporal_agreement", "temporal agreement", "frame-to-frame change against the reference's, on pixels "
                                                     "valid in both"))
        if chosen["full"].get(key) is not None]
    if ordering:
        measured.append({"against": f"signal:{reference}", "metric": "order of objects by pairs", "value": ordering,
                         "how": ordering["how"] + f"; objects from {objects}"})
    depth = {"quantity": "z", "unit": unit, "near_is_small": True,
             "calibrated": {"from": "align_depth", "frames": [int(first), int(first) + count - 1],
                            "depth_range": chosen["depth_range"]}}
    made = record_signal(root, signal_id=signal_id, kind="depth", frames=chosen["aligned"], rate=source.rate,
                         start=source.origin + Fraction(int(first)) / source.rate, camera=camera, depth=depth,
                         derived_from=estimate, transformation=transformation, measured=measured, outside="refuse",
                         unknown=chosen["unknown"], unknown_means="the estimate beyond the calibration's reach "
                         "(s e + t <= 0): no depth, not far",
                         inputs=[{"signal": name} for name in (region, objects) if name] or None,
                         window=truth.record.get("window"),
                         actor=actor, rationale=f"{estimate} aligned to {reference} ({temporal})")
    return {**made, "parameters": transformation["parameters"], **summary, "modes_compared": compared,
            "occlusions_inverted": ordering["occlusions_inverted"] if ordering else None,
            "order_by_objects": ordering["pairs"] if ordering else None}


def _interpolated(parameters: np.ndarray, fitted: list[int], times: list[float]) -> np.ndarray:
    """Parameters for every frame from those fitted on some: linear in time between them, held beyond."""

    fitted_times = [times[index] for index in fitted]
    return np.stack([np.interp(times, fitted_times, parameters[:, k]) for k in range(2)], axis=1)


def _evaluate(mode: str, estimates: list, references: list, masks: list, everywhere: list, times: list[float],
              has_region: bool, *, smoothness: float, trim: float) -> dict[str, Any]:
    parameters, used = fit(estimates, references, masks, mode=mode, times=times, smoothness=smoothness, trim=trim)
    applied = [apply(e, *parameters[index]) for index, e in enumerate(estimates)]
    aligned, unknown = [item[0] for item in applied], [item[1] for item in applied]
    full: dict[str, Any] = {"residual": residuals(aligned, references, masks)}
    trimmed = round(1.0 - sum(int(m.sum()) for m in used) / max(sum(int(m.sum()) for m in masks), 1), 4)
    blocks = _blocks(estimates[0].shape)
    held, _ = fit(estimates, references, [m & blocks for m in masks], mode=mode, times=times,
                  smoothness=smoothness, trim=trim)
    full["held_out_pixels"] = residuals([apply(e, *held[i])[0] for i, e in enumerate(estimates)], references,
                                        [m & ~blocks for m in masks])
    if len(estimates) >= 3:
        # Interior frames only: the last is fitted, so every frame left out lies between two fitted ones (going
        # forward in time is the tail's question, below).
        fitted = sorted(set(range(0, len(estimates), 2)) | {len(estimates) - 1})
        left = [index for index in range(len(estimates)) if index not in fitted]
        some, _ = fit([estimates[i] for i in fitted], [references[i] for i in fitted], [masks[i] for i in fitted],
                      mode=mode, times=[times[i] for i in fitted], smoothness=smoothness, trim=trim)
        every = _interpolated(some, fitted, times)
        full["held_out_frames"] = residuals([apply(estimates[i], *every[i])[0] for i in left],
                                            [references[i] for i in left], [masks[i] for i in left])
    if len(estimates) >= 4:
        # A continuous stretch at the end left out: neighbouring frames are alike (a video model's most of
        # all), so alternate frames flatter a fit; the tail asks whether it holds forward in time. Its
        # parameters are the last fitted frame's, held -- no trend extrapolated.
        cut = len(estimates) - max(1, len(estimates) // 4)
        head, _ = fit(estimates[:cut], references[:cut], masks[:cut], mode=mode, times=times[:cut],
                      smoothness=smoothness, trim=trim)
        full["held_out_tail"] = residuals([apply(estimates[i], *head[-1])[0] for i in range(cut, len(estimates))],
                                          references[cut:], masks[cut:])
        full["held_out_tail"]["frames"] = [cut, len(estimates) - 1]
    if has_region and any((a & ~m).sum() > 16 for a, m in zip(everywhere, masks)):
        full["beyond_region"] = residuals(aligned, references, [a & ~m for a, m in zip(everywhere, masks)])
    full["temporal_agreement"] = temporal_agreement(aligned, references, used)
    calibrated = np.concatenate([r[m] for r, m in zip(references, used)])
    brief = lambda key: ({k: v for k, v in full[key].items() if k != "per_frame"}  # noqa: E731
                         if full.get(key) is not None else None)
    summary = {"residual": brief("residual"), "trimmed": trimmed, "held_out_pixels": brief("held_out_pixels"),
               "held_out_frames": brief("held_out_frames"), "held_out_tail": brief("held_out_tail"),
               "temporal_agreement": full["temporal_agreement"],
               **({"beyond_region": brief("beyond_region")} if "beyond_region" in full else {}),
               "s_range": [round(float(parameters[:, 0].min()), 6), round(float(parameters[:, 0].max()), 6)]}
    return {"parameters": parameters, "aligned": aligned, "unknown": unknown, "full": full, "summary": summary,
            "depth_range": [round(float(calibrated.min()), 4), round(float(calibrated.max()), 4)]}
