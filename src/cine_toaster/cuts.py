"""The cut: how one shot becomes the next within a scene (SPEC-0007).

A cut is declared on the incoming shot, like its `transition` already is: it
says how this shot is entered. The record joins what the outgoing shot leaves
(its exit state and last line) to what the incoming shot finds (its entry state
and first line), and checks the join before anything is generated.
"""

from __future__ import annotations

import math
from typing import Any

from .geometry import Finding, SceneGeometry
from .movement import MOVE_EPSILON_M, Pose, ShotMotion

CUT_TYPES = ("hard", "match", "action", "j", "l", "smash", "jump", "continuation")
CHAINS = ("frame",)

#: Two setups closer than this around the subject read as the same setup.
JUMP_ANGLE_DEG = 30.0
#: ...unless the framing width changes by at least this factor.
JUMP_SIZE_RATIO = 1.4
#: ...or the subject moves across the frame by this fraction of the half-width.
JUMP_SCREEN_SHIFT = 0.5


def _frame_width(pose: Pose, subject: tuple[float, float]) -> float:
    """How wide the frame is where the subject stands: the subject's size in frame."""

    distance = math.dist(pose.position, subject)
    return 2 * distance * math.tan(math.radians(pose.half_fov()))


def _bearing(origin: tuple[float, float], point: tuple[float, float]) -> float:
    return math.degrees(math.atan2(point[1] - origin[1], point[0] - origin[0]))


def _around(subject: tuple[float, float], a: Pose, b: Pose) -> float:
    delta = _bearing(subject, b.position) - _bearing(subject, a.position)
    return abs((delta + 180.0) % 360.0 - 180.0)


def _same_pose(a: Pose, b: Pose) -> bool:
    return (
        math.dist(a.position, b.position) <= MOVE_EPSILON_M
        and math.dist(a.target, b.target) <= MOVE_EPSILON_M
        and abs(a.lens_mm - b.lens_mm) <= 0.5
    )


def _state(motion: ShotMotion | None, at: str) -> dict[str, Any]:
    if motion is None:
        return {"camera": None, "framed": []}
    pose = motion.end_pose if at == "end" else motion.start_pose
    return {
        "camera": pose.public_dict() if pose else None,
        "framed": [
            {"subject": s, "side": side, "angle": round(angle, 1)}
            for s, side, angle in motion.framed(at=at)
        ],
    }


def _declared_subjects(shot: dict[str, Any]) -> set[str]:
    raw = shot.get("subject")
    if isinstance(raw, (list, tuple)):
        return {str(item).strip() for item in raw if str(item).strip()}
    return {part.strip() for part in str(raw or "").split(",") if part.strip()}


def _edge_unit(shot: dict[str, Any], last: bool) -> dict[str, Any] | None:
    script = shot.get("script")
    if not script:
        return None
    units = [unit for unit in script["units"] if unit["kind"] != "heading"]
    if not units:
        return None
    return units[-1] if last else units[0]


def scene_cuts(
    shots: list[dict[str, Any]],
    motions: list[ShotMotion] | None,
    geometry: SceneGeometry,
    *,
    scene_id: str,
    screenplay_linked: bool,
    earlier: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[Finding]]:
    """One record per adjacent pair of shots, and the findings about the joins."""

    by_shot = {motion.shot_id: motion for motion in motions or []}
    records: list[dict[str, Any]] = []
    findings: list[Finding] = []
    for before, after in zip(shots, shots[1:]):
        declared = after.get("cut") if isinstance(after.get("cut"), dict) else {}
        cut_type = str(declared.get("type") or "hard").strip().lower()
        chain = str(declared.get("chain") or "").strip().lower()
        pair: list[Finding] = []

        if cut_type not in CUT_TYPES:
            pair.append(_finding("cut_type_unknown", "error", scene_id, before, after,
                f"The cut into {after['id']} is {cut_type!r}; the vocabulary is {', '.join(CUT_TYPES)}."))
        if chain and chain not in CHAINS:
            pair.append(_finding("cut_type_unknown", "error", scene_id, before, after,
                f"The cut into {after['id']} chains {chain!r}; the only chain is 'frame'."))

        out = by_shot.get(before["id"])
        into = by_shot.get(after["id"])
        exit_pose = out.end_pose if out else None
        entry_pose = into.start_pose if into else None

        # Shots that say whom they are on and name different people are not a
        # jump, whatever one camera position frames: an insert and a close-up
        # declared on the same camera are two framings the plan did not model.
        declared_before, declared_after = _declared_subjects(before), _declared_subjects(after)
        different_subjects = bool(declared_before and declared_after and not declared_before & declared_after)

        # A continuation is one shot carried across a generation boundary: the
        # same setup on both sides is the point, not a jump.
        if exit_pose and entry_pose and cut_type not in ("jump", "continuation") and not different_subjects:
            exit_angles = {s: a for s, _, a in out.framed(at="end")}
            entry_angles = {s: a for s, _, a in into.framed(at="start")}
            for subject_id in sorted(exit_angles.keys() & entry_angles.keys()):
                position = into.start_positions[subject_id]
                angle = _around(position, exit_pose, entry_pose)
                widths = sorted((_frame_width(exit_pose, position), _frame_width(entry_pose, position)))
                ratio = widths[1] / widths[0] if widths[0] else float("inf")
                # Where the subject sits across the frame, as a fraction of the half-width.
                shift = abs(
                    exit_angles[subject_id] / exit_pose.half_fov()
                    - entry_angles[subject_id] / entry_pose.half_fov()
                )
                if angle < JUMP_ANGLE_DEG and ratio < JUMP_SIZE_RATIO and shift < JUMP_SCREEN_SHIFT:
                    label = geometry.subjects[subject_id].label if subject_id in geometry.subjects else subject_id
                    pair.append(_finding("jump_cut_undeclared", "warning", scene_id, before, after,
                        f"{before['id']} and {after['id']} see {label} from {angle:.0f}° apart with "
                        f"{ratio:.2f}× the framing. Cut together it reads as a jump. Move the camera "
                        f"at least {JUMP_ANGLE_DEG:.0f}°, change the size, or declare the cut a jump. "
                        f"If the shots frame different things (an insert), give one its own camera "
                        f"or declare each shot's subject."))
                    break

        if chain == "frame" and exit_pose and entry_pose:
            moved = [
                s for s in out.end_positions
                if s in into.start_positions
                and math.dist(out.end_positions[s], into.start_positions[s]) > MOVE_EPSILON_M
            ]
            if not _same_pose(exit_pose, entry_pose) or moved:
                pair.append(_finding("chain_pose_mismatch", "warning", scene_id, before, after,
                    f"{after['id']} chains {before['id']}'s last frame, but "
                    + ("its camera starts somewhere else" if not _same_pose(exit_pose, entry_pose) else "a subject is not where that frame left them")
                    + ". The generator would be handed a first frame from another setup."))

        if cut_type == "continuation" and chain != "frame":
            pair.append(_finding("continuation_unchained", "advice", scene_id, before, after,
                f"{after['id']} continues {before['id']} but does not open on its last frame. "
                f"Declare chain: frame, or the generator starts the continuation from nothing."))

        if cut_type in ("l", "j") and screenplay_linked:
            edge = _edge_unit(before, last=True) if cut_type == "l" else _edge_unit(after, last=False)
            if not edge or edge["kind"] != "speech":
                side = f"{before['id']} ends" if cut_type == "l" else f"{after['id']} starts"
                pair.append(_finding("split_edit_without_sound", "warning", scene_id, before, after,
                    f"An {cut_type.upper()}-cut carries sound across the join, but {side} on no dialogue."))

        transition = after.get("transition")
        if transition and transition.get("id") and not transition.get("reason"):
            pair.append(_finding("transition_reason_missing", "advice", scene_id, before, after,
                f"The {transition['id']} into {after['id']} has no reason. A choice without one cannot be reviewed."))

        # The screen-side jump is found by the movement checks (SPEC-0005);
        # the record lists it with the rest of what is wrong with this join.
        listed = [finding.public_dict() for finding in pair] + [
            finding for finding in (earlier or [])
            if finding["code"] == "cut_screen_flip" and finding["shots"] == [before["id"], after["id"]]
        ]
        records.append(
            {
                "from": before["id"],
                "to": after["id"],
                "type": cut_type,
                "chain": chain,
                "reason": str(declared.get("reason") or ""),
                # A J- or L-cut's sound across the picture cut, in seconds (0: the assembly's default).
                "split": _split(declared.get("split")) if cut_type in ("j", "l") else 0.0,
                "transition": transition,
                "exit": {**_state(out, "end"), "ends_on": out.ends_on if out else "", "unit": _edge_unit(before, True)},
                "entry": {**_state(into, "start"), "unit": _edge_unit(after, False)},
                "findings": listed,
            }
        )
        findings.extend(pair)
    return records, findings


def _split(raw: Any) -> float:
    try:
        return max(0.0, round(float(raw or 0), 3))
    except (TypeError, ValueError):
        return 0.0


def _finding(code: str, severity: str, scene_id: str, before: dict, after: dict, message: str) -> Finding:
    return Finding(
        code=code,
        severity=severity,
        message=message,
        scene_id=scene_id,
        shots=(before["id"], after["id"]),
    )
