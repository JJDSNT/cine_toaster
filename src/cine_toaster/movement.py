"""Movement within a shot: where the camera and the subjects go (SPEC-0005).

Scene geometry holds where things are when the scene begins. A shot may move a
subject to a mark, restate positions after a time jump, and move its camera from
the named start position to an end pose. From that, each shot has a start state
and an end state, positions carry across the cut in shot order, and the kind of
camera move is derived from the two poses rather than taken from its name.

Nothing here reads prose. A character whose action says she walks has not moved
until the shot says `subjects_move`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .geometry import (
    CENTRED_ANGLE_TOLERANCE_DEG,
    Camera,
    Finding,
    SceneGeometry,
    _side_of_axis,
    screen_side,
)

#: A position or height change below this is not a move.
MOVE_EPSILON_M = 0.05
#: A change of aim below this many degrees is not a pan.
PAN_EPSILON_DEG = 2.0
#: An arc keeps its distance to the target within this fraction.
ARC_DISTANCE_TOLERANCE = 0.10
#: An arc of at least this many degrees is an orbit.
ORBIT_MIN_DEG = 300.0
#: Points sampled along a camera path when checking it against the axis.
PATH_SAMPLES = 24

SPEEDS = ("slow", "steady", "fast", "snap")
RIGS = ("tripod", "dolly", "slider", "steadicam", "handheld", "body", "crane", "drone", "vehicle")
KINDS = ("static", "pan", "tilt", "zoom", "dolly", "truck", "arc", "pedestal", "crane", "track")

#: Declared names accepted for a kind, beyond the kind itself.
KIND_ALIASES = {"orbit": "arc", "push": "dolly", "pull": "dolly", "follow": "track"}

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Pose:
    """Where a camera is, what it looks at, and through which lens."""

    position: Point
    target: Point
    lens_mm: float
    height: float | None = None
    target_ref: str = ""
    #: How high the camera aims, when declared (a drone looking down at a lake).
    target_height: float | None = None

    def half_fov(self) -> float:
        return math.degrees(math.atan(36.0 / (2 * self.lens_mm)))

    def public_dict(self) -> dict[str, Any]:
        return {
            "position": _rounded(self.position),
            "target": _rounded(self.target),
            "target_ref": self.target_ref,
            "lens_mm": self.lens_mm,
            "height": self.height,
            "aim_height": self.target_height,
        }


@dataclass(slots=True)
class ShotMotion:
    """One shot's start and end, and the move between them."""

    shot_id: str
    camera_id: str
    start_pose: Pose | None
    end_pose: Pose | None
    start_positions: dict[str, Point]
    end_positions: dict[str, Point]
    kind: str = "static"
    direction: str = ""
    secondary: tuple[str, ...] = ()
    degrees: float | None = None
    derived: bool = True
    declared_kind: str = ""
    declared_direction: str = ""
    speed: str = ""
    rig: str = ""
    ends_on: str = ""
    moved_subjects: tuple[str, ...] = ()
    problems: list[Finding] = field(default_factory=list)

    def framed(self, *, at: str) -> list[tuple[str, str, float]]:
        """Subjects inside the frame at the start or end: (id, side, angle)."""

        pose = self.start_pose if at == "start" else self.end_pose
        positions = self.start_positions if at == "start" else self.end_positions
        if pose is None:
            return []
        placed = []
        for subject_id, position in positions.items():
            side, angle = screen_side(pose.position, pose.target, position)
            if abs(angle) <= pose.half_fov():
                placed.append((subject_id, side, angle))
        return placed

    def public_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "camera_id": self.camera_id,
            "kind": self.kind,
            "direction": self.direction,
            "secondary": list(self.secondary),
            "degrees": round(self.degrees, 1) if self.degrees is not None else None,
            "derived": self.derived,
            "declared_kind": self.declared_kind,
            "speed": self.speed,
            "rig": self.rig,
            "ends_on": self.ends_on,
            "moved_subjects": list(self.moved_subjects),
            "start": {
                "camera": self.start_pose.public_dict() if self.start_pose else None,
                "subjects": {key: _rounded(value) for key, value in self.start_positions.items()},
                "framed": [
                    {"subject": s, "side": side, "angle": round(a, 1)}
                    for s, side, a in self.framed(at="start")
                ],
            },
            "end": {
                "camera": self.end_pose.public_dict() if self.end_pose else None,
                "subjects": {key: _rounded(value) for key, value in self.end_positions.items()},
                "framed": [
                    {"subject": s, "side": side, "angle": round(a, 1)}
                    for s, side, a in self.framed(at="end")
                ],
            },
        }


def _rounded(point: Point) -> list[float]:
    return [round(point[0], 3), round(point[1], 3)]


def _as_point(value: Any) -> Point | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return float(value[0]), float(value[1])
        except (TypeError, ValueError):
            return None
    return None


def _resolve(
    geometry: SceneGeometry,
    value: Any,
    positions: dict[str, Point],
) -> Point | None:
    """A mark id, a subject id (where they stand now), or an [x, y] point."""

    point = _as_point(value)
    if point is not None:
        return point
    reference = str(value or "").strip()
    if reference in geometry.marks:
        return geometry.marks[reference].position
    if reference in positions:
        return positions[reference]
    return None


def _pose(camera: Camera, geometry: SceneGeometry, positions: dict[str, Point]) -> Pose | None:
    target_ref = camera.target if isinstance(camera.target, str) else ""
    target = _resolve(geometry, camera.target, positions)
    if target is None:
        return None
    return Pose(camera.position, target, camera.lens_mm, camera.height, target_ref, camera.target_height)


def _declared(value: str) -> tuple[str, str]:
    """`dolly_in` -> (dolly, in); `orbit` -> (arc, '')."""

    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not text:
        return "", ""
    kind, _, direction = text.partition("_")
    kind = KIND_ALIASES.get(kind, kind)
    if text in ("push_in", "push"):
        direction = "in"
    if text in ("pull_out", "pull_back", "pull"):
        direction = "out"
    return kind, direction


def _bearing(origin: Point, point: Point) -> float:
    return math.degrees(math.atan2(point[1] - origin[1], point[0] - origin[0]))


def _angle_delta(start: float, end: float) -> float:
    return (end - start + 180.0) % 360.0 - 180.0


def _tilt(pose: Pose) -> float | None:
    """How far the camera looks up (positive) or down, when both heights are known."""

    if pose.height is None or pose.target_height is None:
        return None
    return math.degrees(math.atan2(pose.target_height - pose.height, math.dist(pose.position, pose.target) or 1e-6))


def derive_kind(
    start: Pose,
    end: Pose,
    *,
    target_moves: bool,
) -> tuple[str, str, tuple[str, ...], float | None]:
    """The kind of move between two poses: (kind, direction, secondary, degrees).

    Direction is in screen space from the start pose, the same convention as
    `screen_side`: "truck right" means the camera moves to the frame's right.
    """

    view_x = start.target[0] - start.position[0]
    view_y = start.target[1] - start.position[1]
    view_length = math.hypot(view_x, view_y) or 1.0
    view_x, view_y = view_x / view_length, view_y / view_length
    right_x, right_y = view_y, -view_x

    dx = end.position[0] - start.position[0]
    dy = end.position[1] - start.position[1]
    moved = math.hypot(dx, dy) > MOVE_EPSILON_M
    height_change = None
    if start.height is not None and end.height is not None:
        delta = end.height - start.height
        height_change = delta if abs(delta) > MOVE_EPSILON_M else 0.0
    lens_change = end.lens_mm - start.lens_mm
    aim_change = _angle_delta(
        _bearing(start.position, start.target), _bearing(end.position, end.target)
    )

    components: list[tuple[str, str]] = []
    degrees: float | None = None
    if moved and target_moves:
        components.append(("track", ""))
    elif moved:
        distance_start = math.dist(start.position, start.target)
        distance_end = math.dist(end.position, end.target)
        around = _angle_delta(
            _bearing(start.target, start.position), _bearing(end.target, end.position)
        )
        same_target = math.dist(start.target, end.target) <= MOVE_EPSILON_M
        keeps_distance = (
            distance_start > 0
            and abs(distance_end - distance_start) / distance_start <= ARC_DISTANCE_TOLERANCE
        )
        along = dx * view_x + dy * view_y
        lateral = dx * right_x + dy * right_y
        if same_target and keeps_distance and abs(around) > PAN_EPSILON_DEG:
            degrees = abs(around)
            components.append(("arc", "right" if lateral > 0 else "left"))
        elif abs(along) >= abs(lateral):
            components.append(("dolly", "in" if along > 0 else "out"))
        else:
            components.append(("truck", "right" if lateral > 0 else "left"))
    if height_change:
        vertical = "up" if height_change > 0 else "down"
        if moved:
            components.insert(0, ("crane", vertical))
        else:
            components.append(("pedestal", vertical))
    if not moved and abs(aim_change) > PAN_EPSILON_DEG:
        side, _ = screen_side(start.position, start.target, end.target)
        components.append(("pan", side if side != "centred" else ""))
    tilt = _tilt(end) - _tilt(start) if None not in (_tilt(start), _tilt(end)) else 0.0
    if abs(tilt) > PAN_EPSILON_DEG and not height_change:
        components.append(("tilt", "up" if tilt > 0 else "down"))
    if abs(lens_change) > 0.5:
        components.append(("zoom", "in" if lens_change > 0 else "out"))

    if not components:
        return "static", "", (), None
    kind, direction = components[0]
    secondary = tuple(f"{name} {way}".strip() for name, way in components[1:])
    return kind, direction, secondary, degrees


def _path(start: Pose, end: Pose, kind: str) -> list[Point]:
    """Sample the camera path: circular about the target for an arc, else straight."""

    if kind == "arc":
        centre = start.target
        radius_start = math.dist(centre, start.position)
        radius_end = math.dist(centre, end.position)
        a0 = _bearing(centre, start.position)
        sweep = _angle_delta(a0, _bearing(centre, end.position))
        points = []
        for index in range(PATH_SAMPLES + 1):
            t = index / PATH_SAMPLES
            radius = radius_start + (radius_end - radius_start) * t
            angle = math.radians(a0 + sweep * t)
            points.append((centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle)))
        return points
    return [
        (
            start.position[0] + (end.position[0] - start.position[0]) * index / PATH_SAMPLES,
            start.position[1] + (end.position[1] - start.position[1]) * index / PATH_SAMPLES,
        )
        for index in range(PATH_SAMPLES + 1)
    ]


def _crosses(axis_a: Point, axis_b: Point, points: list[Point]) -> bool:
    sides = {_side_of_axis(axis_a, axis_b, point)[0] for point in points}
    return 1 in sides and -1 in sides


def shot_motions(
    geometry: SceneGeometry,
    shots: list[dict[str, Any]],
    *,
    scene_id: str = "",
) -> list[ShotMotion]:
    """Each shot's start and end state, with positions carried in shot order."""

    positions: dict[str, Point] = {
        subject_id: subject.position for subject_id, subject in geometry.subjects.items()
    }
    motions: list[ShotMotion] = []
    for shot in shots:
        shot_id = str(shot.get("id", ""))
        problems: list[Finding] = []

        for entry in shot.get("subjects_at") or []:
            _place(geometry, entry, "at", positions, positions, shot_id, scene_id, problems)
        start_positions = dict(positions)

        end_positions = dict(start_positions)
        moved: list[str] = []
        for entry in shot.get("subjects_move") or []:
            if _place(geometry, entry, "to", start_positions, end_positions, shot_id, scene_id, problems):
                moved.append(str(entry.get("subject", "")).strip())

        camera_id = str(shot.get("camera", "")).strip()
        camera = geometry.cameras.get(camera_id)
        start_pose = _pose(camera, geometry, start_positions) if camera else None
        move = shot.get("move") or {}
        declared_kind, declared_direction = _declared(move.get("kind", ""))
        for name, value, allowed in (
            ("speed", move.get("speed"), SPEEDS),
            ("rig", move.get("rig"), RIGS),
            ("kind", declared_kind or None, KINDS),
        ):
            if value and value not in allowed:
                problems.append(
                    Finding(
                        code="move_value_unknown",
                        severity="error",
                        message=(
                            f"Shot {shot_id} gives its move {name} {value!r}; the vocabulary "
                            f"is {', '.join(allowed)}. It would be lost, not guessed."
                        ),
                        scene_id=scene_id,
                        shots=(shot_id,),
                    )
                )
        motion = ShotMotion(
            shot_id=shot_id,
            camera_id=camera_id,
            start_pose=start_pose,
            end_pose=start_pose,
            start_positions=start_positions,
            end_positions=end_positions,
            declared_kind=declared_kind,
            declared_direction=declared_direction,
            speed=str(move.get("speed", "") or ""),
            rig=str(move.get("rig", "") or ""),
            ends_on=str(shot.get("ends_on", "") or ""),
            moved_subjects=tuple(moved),
            problems=problems,
        )

        if start_pose is not None:
            end_pose = _end_pose(geometry, camera, start_pose, move, end_positions, motion, scene_id)
            # A camera aimed at a subject follows them: the end aim is where they end.
            if end_pose is start_pose and start_pose.target_ref in end_positions:
                end_pose = Pose(
                    start_pose.position,
                    end_positions[start_pose.target_ref],
                    start_pose.lens_mm,
                    start_pose.height,
                    start_pose.target_ref,
                    start_pose.target_height,
                )
            motion.end_pose = end_pose
            target_moves = bool(end_pose.target_ref) and end_pose.target_ref in moved
            kind, direction, secondary, degrees = derive_kind(
                start_pose, end_pose, target_moves=target_moves
            )
            if move.get("to") is None and declared_kind:
                # Declared only (a tilt, or intent without an end pose).
                kind, direction, secondary, degrees = declared_kind, declared_direction, (), None
                motion.derived = False
            motion.kind, motion.direction, motion.secondary, motion.degrees = (
                kind,
                direction,
                secondary,
                degrees,
            )
        motions.append(motion)
        positions = dict(end_positions)
    return motions


def _place(
    geometry: SceneGeometry,
    entry: Any,
    key: str,
    resolve_from: dict[str, Point],
    into: dict[str, Point],
    shot_id: str,
    scene_id: str,
    problems: list[Finding],
) -> bool:
    if not isinstance(entry, dict):
        return False
    subject_id = str(entry.get("subject", "")).strip()
    if subject_id not in geometry.subjects:
        problems.append(
            Finding(
                code="movement_subject_missing",
                severity="error",
                message=(
                    f"Shot {shot_id} moves {subject_id or 'an unnamed subject'!s}, "
                    "which the scene geometry does not define."
                ),
                scene_id=scene_id,
                subjects=(subject_id,) if subject_id else (),
                shots=(shot_id,),
            )
        )
        return False
    point = _resolve(geometry, entry.get(key), resolve_from)
    if point is None:
        problems.append(_unknown_mark(entry.get(key), shot_id, scene_id))
        return False
    into[subject_id] = point
    return True


def _unknown_mark(value: Any, shot_id: str, scene_id: str) -> Finding:
    return Finding(
        code="unknown_mark",
        severity="error",
        message=(
            f"Shot {shot_id} sends something to {value!r}, which is not a mark, "
            "subject or camera in the scene geometry."
        ),
        scene_id=scene_id,
        shots=(shot_id,),
    )


def _end_pose(
    geometry: SceneGeometry,
    camera: Camera,
    start: Pose,
    move: dict[str, Any],
    end_positions: dict[str, Point],
    motion: ShotMotion,
    scene_id: str,
) -> Pose:
    destination = move.get("to")
    if destination is None:
        return start
    if isinstance(destination, str):
        other = geometry.cameras.get(destination.strip())
        if other is None:
            motion.problems.append(_unknown_mark(destination, motion.shot_id, scene_id))
            return start
        pose = _pose(other, geometry, end_positions)
        return pose if pose is not None else start
    if not isinstance(destination, dict):
        motion.problems.append(_unknown_mark(destination, motion.shot_id, scene_id))
        return start

    position = start.position
    if "x" in destination and "y" in destination:
        position = (float(destination["x"]), float(destination["y"]))
    target, target_ref = start.target, start.target_ref
    if "target" in destination:
        resolved = _resolve(geometry, destination["target"], end_positions)
        if resolved is None:
            motion.problems.append(_unknown_mark(destination["target"], motion.shot_id, scene_id))
        else:
            target = resolved
            aim = destination["target"]
            target_ref = aim if isinstance(aim, str) and aim in end_positions else ""
    elif target_ref in end_positions:
        target = end_positions[target_ref]
    lens = float(destination.get("lens_mm", start.lens_mm))
    height = destination.get("height", start.height)
    aim = destination.get("target_height", start.target_height)
    return Pose(position, target, lens, float(height) if height is not None else None, target_ref,
                float(aim) if aim is not None else None)


def check_movement(
    geometry: SceneGeometry,
    shots: list[dict[str, Any]],
    *,
    scene_id: str = "",
    motions: list[ShotMotion] | None = None,
) -> list[Finding]:
    """The checks movement makes possible, run before anything is generated."""

    if geometry.is_empty():
        return []
    motions = motions if motions is not None else shot_motions(geometry, shots, scene_id=scene_id)
    names = {subject_id: subject.label for subject_id, subject in geometry.subjects.items()}
    by_id = {str(shot.get("id", "")): shot for shot in shots}
    findings: list[Finding] = []

    for motion in motions:
        findings.extend(motion.problems)
        shot = by_id.get(motion.shot_id, {})

        axis = geometry.axis
        if axis and all(subject in motion.start_positions for subject in axis.between):
            a = motion.start_positions[axis.between[0]]
            b = motion.start_positions[axis.between[1]]
            if motion.start_pose and motion.end_pose and motion.kind != "static":
                if _crosses(a, b, _path(motion.start_pose, motion.end_pose, motion.kind)):
                    findings.append(
                        Finding(
                            code="move_crosses_axis",
                            severity="error",
                            message=(
                                f"The camera's {motion.kind} in {motion.shot_id} crosses the line "
                                f"of action between {names[axis.between[0]]} and "
                                f"{names[axis.between[1]]}. Every later shot from the near side "
                                "will cut wrong against it."
                            ),
                            scene_id=scene_id,
                            subjects=axis.between,
                            cameras=(motion.camera_id,),
                            shots=(motion.shot_id,),
                        )
                    )
            for subject_id in motion.moved_subjects:
                if subject_id in axis.between:
                    continue
                path = [motion.start_positions[subject_id], motion.end_positions[subject_id]]
                steps = [
                    (
                        path[0][0] + (path[1][0] - path[0][0]) * i / PATH_SAMPLES,
                        path[0][1] + (path[1][1] - path[0][1]) * i / PATH_SAMPLES,
                    )
                    for i in range(PATH_SAMPLES + 1)
                ]
                if _crosses(a, b, steps):
                    findings.append(_path_crossing(motion, subject_id, names, scene_id))
            end_a = motion.end_positions.get(axis.between[0])
            end_b = motion.end_positions.get(axis.between[1])
            if (
                motion.end_pose
                and end_a
                and end_b
                and (end_a, end_b) != (a, b)
                and _side_of_axis(a, b, motion.end_pose.position)[0]
                * _side_of_axis(end_a, end_b, motion.end_pose.position)[0]
                < 0
            ):
                moved_axis = next(
                    (s for s in axis.between if s in motion.moved_subjects), axis.between[0]
                )
                findings.append(_path_crossing(motion, moved_axis, names, scene_id))

        declared = motion.declared_kind
        has_end_pose = (shot.get("move") or {}).get("to") is not None
        if declared and motion.derived and has_end_pose:
            direction_differs = (
                motion.declared_direction
                and motion.direction
                and motion.declared_direction != motion.direction
            )
            if declared != motion.kind or direction_differs:
                written = f"{declared} {motion.declared_direction}".strip()
                derived = f"{motion.kind} {motion.direction}".strip()
                findings.append(
                    Finding(
                        code="move_kind_mismatch",
                        severity="warning",
                        message=(
                            f"{motion.shot_id} names the move {written!r}, but its start and "
                            f"end positions make it a {derived}. Either the name or the end "
                            "position is wrong."
                        ),
                        scene_id=scene_id,
                        cameras=(motion.camera_id,),
                        shots=(motion.shot_id,),
                    )
                )

        subject_id = str(shot.get("subject", "")).strip()
        if subject_id in motion.start_positions and motion.start_pose is not None:
            in_start = any(s == subject_id for s, _, _ in motion.framed(at="start"))
            in_end = any(s == subject_id for s, _, _ in motion.framed(at="end"))
            if not in_start and not in_end:
                findings.append(
                    Finding(
                        code="framed_subject_missing",
                        severity="warning",
                        message=(
                            f"{motion.shot_id} is on {names[subject_id]}, but camera "
                            f"{motion.camera_id} frames them neither where the shot starts "
                            "nor where it ends."
                        ),
                        scene_id=scene_id,
                        subjects=(subject_id,),
                        cameras=(motion.camera_id,),
                        shots=(motion.shot_id,),
                    )
                )

    with_camera = [motion for motion in motions if motion.start_pose is not None]
    for before, after in zip(with_camera, with_camera[1:]):
        exit_sides = {s: (side, a) for s, side, a in before.framed(at="end")}
        entry_sides = {s: (side, a) for s, side, a in after.framed(at="start")}
        for subject_id in sorted(exit_sides.keys() & entry_sides.keys()):
            side_out, angle_out = exit_sides[subject_id]
            side_in, angle_in = entry_sides[subject_id]
            if "centred" in (side_out, side_in) or side_out == side_in:
                continue
            findings.append(
                Finding(
                    code="cut_screen_flip",
                    severity="warning",
                    message=(
                        f"{names[subject_id]} leaves {before.shot_id} on the {side_out} of frame "
                        f"({abs(angle_out):.0f}°) and enters {after.shot_id} on the "
                        f"{side_in} ({abs(angle_in):.0f}°). Across the cut they appear "
                        "to jump sides."
                    ),
                    scene_id=scene_id,
                    subjects=(subject_id,),
                    cameras=(before.camera_id, after.camera_id),
                    shots=(before.shot_id, after.shot_id),
                )
            )
    return findings


def _path_crossing(
    motion: ShotMotion, subject_id: str, names: dict[str, str], scene_id: str
) -> Finding:
    return Finding(
        code="subject_path_crosses_axis",
        severity="warning",
        message=(
            f"{names.get(subject_id, subject_id)} crosses the line of action in "
            f"{motion.shot_id}. That is legal, and it redraws the line for every later shot."
        ),
        scene_id=scene_id,
        subjects=(subject_id,),
        shots=(motion.shot_id,),
    )


__all__ = [
    "CENTRED_ANGLE_TOLERANCE_DEG",
    "KINDS",
    "Pose",
    "RIGS",
    "SPEEDS",
    "ShotMotion",
    "check_movement",
    "derive_kind",
    "shot_motions",
]
