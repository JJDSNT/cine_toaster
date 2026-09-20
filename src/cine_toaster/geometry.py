from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .errors import ValidationError


# Every check this module can report. Knowledge records name a code here to
# declare that software enforces them, and `toast knowledge` refuses a record
# that names a code which does not exist.
CHECK_CODES = frozenset(
    {
        "axis_break",
        "axis_subject_missing",
        "camera_outside_room",
        "eyeline_height_flip",
        "eyeline_mismatch",
        "eyeline_subject_missing",
        "subjects_overlap",
        "unknown_camera",
    }
)

SENSOR_WIDTH_MM = 36.0
ON_AXIS_TOLERANCE_M = 0.15
LEVEL_ANGLE_TOLERANCE_DEG = 3.0
CENTRED_ANGLE_TOLERANCE_DEG = 5.0
SUBJECT_MIN_SEPARATION_M = 0.25


def _point(value: Any, *, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValidationError(f"{label} must be a two-number [x, y] position")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{label} must contain numbers") from error


@dataclass(frozen=True, slots=True)
class Room:
    width: float
    depth: float
    height: float

    def contains(self, position: tuple[float, float]) -> bool:
        x, y = position
        return 0.0 <= x <= self.width and 0.0 <= y <= self.depth

    def public_dict(self) -> dict[str, float]:
        return {"width": self.width, "depth": self.depth, "height": self.height}


@dataclass(frozen=True, slots=True)
class Subject:
    """A person or object the cameras are arranged around."""

    id: str
    label: str
    position: tuple[float, float]
    # Heights are optional: a plan drawn from measurements often has positions
    # long before anyone decides how high the camera sits.
    eye_height: float | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "position": list(self.position),
            "eye_height": self.eye_height,
        }


@dataclass(frozen=True, slots=True)
class Camera:
    """A fixed camera position reused by every shot that names it.

    Fixed, named positions are what keeps a generated scene coherent: two shots
    of the same character shot from the same place cut together, and two shots
    from mirrored places do not.
    """

    id: str
    label: str
    position: tuple[float, float]
    height: float | None
    target: str | tuple[float, float]
    lens_mm: float

    def horizontal_fov_degrees(self) -> float:
        return math.degrees(2 * math.atan(SENSOR_WIDTH_MM / (2 * self.lens_mm)))

    def public_dict(self) -> dict[str, Any]:
        target = self.target if isinstance(self.target, str) else list(self.target)
        return {
            "id": self.id,
            "label": self.label,
            "position": list(self.position),
            "height": self.height,
            "target": target,
            "lens_mm": self.lens_mm,
            "fov_degrees": round(self.horizontal_fov_degrees(), 2),
        }


@dataclass(frozen=True, slots=True)
class Axis:
    """The line of action between two subjects (the 180-degree line)."""

    between: tuple[str, str]

    def public_dict(self) -> dict[str, Any]:
        return {"between": list(self.between)}


@dataclass(frozen=True, slots=True)
class SceneGeometry:
    units: str = "m"
    room: Room | None = None
    subjects: dict[str, Subject] = field(default_factory=dict)
    cameras: dict[str, Camera] = field(default_factory=dict)
    axis: Axis | None = None

    def is_empty(self) -> bool:
        return self.room is None and not self.subjects and not self.cameras

    def public_dict(self) -> dict[str, Any]:
        return {
            "units": self.units,
            "room": self.room.public_dict() if self.room else None,
            "subjects": [subject.public_dict() for subject in self.subjects.values()],
            "cameras": [camera.public_dict() for camera in self.cameras.values()],
            "axis": self.axis.public_dict() if self.axis else None,
        }

    def resolve_target(self, camera: Camera) -> tuple[float, float] | None:
        if isinstance(camera.target, str):
            subject = self.subjects.get(camera.target)
            return subject.position if subject else None
        return camera.target

    def target_subject(self, camera: Camera) -> Subject | None:
        if isinstance(camera.target, str):
            return self.subjects.get(camera.target)
        return None


def parse_geometry(document: dict[str, Any] | None) -> SceneGeometry:
    """Read the optional ``[geometry]`` block of an authored scene file."""

    if not document:
        return SceneGeometry()

    room_document = document.get("room")
    room = None
    if isinstance(room_document, dict):
        try:
            room = Room(
                width=float(room_document["width"]),
                depth=float(room_document["depth"]),
                height=float(room_document.get("height", 2.7)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError("geometry.room needs numeric width and depth") from error

    subjects: dict[str, Subject] = {}
    for raw in document.get("subjects", []) or []:
        if not isinstance(raw, dict):
            raise ValidationError("Each geometry.subjects entry must be a table")
        subject_id = str(raw.get("id", "")).strip()
        if not subject_id:
            raise ValidationError("A geometry subject needs an id")
        if subject_id in subjects:
            raise ValidationError(f"Duplicate geometry subject id {subject_id!r}")
        subjects[subject_id] = Subject(
            id=subject_id,
            label=str(raw.get("label", subject_id)),
            position=_point(raw.get("position"), label=f"subject {subject_id} position"),
            eye_height=float(raw["eye_height"]) if raw.get("eye_height") is not None else None,
        )

    cameras: dict[str, Camera] = {}
    for raw in document.get("cameras", []) or []:
        if not isinstance(raw, dict):
            raise ValidationError("Each geometry.cameras entry must be a table")
        camera_id = str(raw.get("id", "")).strip()
        if not camera_id:
            raise ValidationError("A geometry camera needs an id")
        if camera_id in cameras:
            raise ValidationError(f"Duplicate geometry camera id {camera_id!r}")
        target_value = raw.get("target")
        target: str | tuple[float, float]
        if isinstance(target_value, str):
            target = target_value
        else:
            target = _point(target_value, label=f"camera {camera_id} target")
        lens = float(raw.get("lens_mm", 50))
        if lens <= 0:
            raise ValidationError(f"camera {camera_id} needs a positive lens_mm")
        cameras[camera_id] = Camera(
            id=camera_id,
            label=str(raw.get("label", camera_id)),
            position=_point(raw.get("position"), label=f"camera {camera_id} position"),
            height=float(raw["height"]) if raw.get("height") is not None else None,
            target=target,
            lens_mm=lens,
        )

    axis = None
    axis_document = document.get("axis")
    if isinstance(axis_document, dict):
        between = axis_document.get("between")
        if not isinstance(between, (list, tuple)) or len(between) != 2:
            raise ValidationError("geometry.axis.between must name exactly two subjects")
        axis = Axis(between=(str(between[0]), str(between[1])))

    return SceneGeometry(
        units=str(document.get("units", "m")),
        room=room,
        subjects=subjects,
        cameras=cameras,
        axis=axis,
    )


@dataclass(frozen=True, slots=True)
class Finding:
    """One continuity problem found by reading the scene, before generating it."""

    code: str
    severity: str
    message: str
    scene_id: str = ""
    subjects: tuple[str, ...] = ()
    cameras: tuple[str, ...] = ()
    shots: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "scene_id": self.scene_id,
            "subjects": list(self.subjects),
            "cameras": list(self.cameras),
            "shots": list(self.shots),
        }


def screen_side(
    camera_position: tuple[float, float],
    looking_at: tuple[float, float],
    other: tuple[float, float],
) -> tuple[str, float]:
    """Which half of the frame a third point falls into, and how far off centre.

    The camera looks along ``view``; screen right is that vector turned a quarter
    turn clockwise on the plan. A point almost dead ahead is reported as
    ``centred`` rather than forced onto a side, because the sign there is noise.
    """

    view_x = looking_at[0] - camera_position[0]
    view_y = looking_at[1] - camera_position[1]
    to_other_x = other[0] - camera_position[0]
    to_other_y = other[1] - camera_position[1]

    view_length = math.hypot(view_x, view_y)
    other_length = math.hypot(to_other_x, to_other_y)
    if view_length == 0 or other_length == 0:
        return "centred", 0.0

    right_x, right_y = view_y / view_length, -view_x / view_length
    lateral = to_other_x * right_x + to_other_y * right_y
    angle = math.degrees(math.asin(max(-1.0, min(1.0, lateral / other_length))))
    if abs(angle) <= CENTRED_ANGLE_TOLERANCE_DEG:
        return "centred", angle
    return ("right" if angle > 0 else "left"), angle


def _side_of_axis(
    a: tuple[float, float],
    b: tuple[float, float],
    point: tuple[float, float],
) -> tuple[int, float]:
    """Return which side of line A-B a point is on, and its distance from it."""

    ax, ay = a
    bx, by = b
    px, py = point
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0:
        return 0, 0.0
    cross = dx * (py - ay) - dy * (px - ax)
    distance = abs(cross) / length
    if distance <= ON_AXIS_TOLERANCE_M:
        return 0, distance
    return (1 if cross > 0 else -1), distance


def check_geometry(
    geometry: SceneGeometry,
    shots: list[dict[str, Any]],
    *,
    scene_id: str = "",
) -> list[Finding]:
    """Check the grammar a generated scene silently breaks.

    These are the mistakes that survive a good-looking individual shot and only
    appear once the scene is cut together, which is the most expensive moment to
    discover them.
    """

    findings: list[Finding] = []
    if geometry.is_empty():
        return findings

    used_cameras: dict[str, list[str]] = {}
    for shot in shots:
        camera_id = str(shot.get("camera", "")).strip()
        if not camera_id:
            continue
        used_cameras.setdefault(camera_id, []).append(str(shot.get("id", "")))

    for camera_id, shot_ids in sorted(used_cameras.items()):
        if camera_id not in geometry.cameras:
            findings.append(
                Finding(
                    code="unknown_camera",
                    severity="error",
                    message=(
                        f"Shot(s) {', '.join(shot_ids)} use camera {camera_id!r}, "
                        "which the scene geometry does not define."
                    ),
                    scene_id=scene_id,
                    cameras=(camera_id,),
                    shots=tuple(shot_ids),
                )
            )

    if geometry.room is not None:
        for camera in geometry.cameras.values():
            if not geometry.room.contains(camera.position):
                findings.append(
                    Finding(
                        code="camera_outside_room",
                        severity="warning",
                        message=(
                            f"Camera {camera.label} sits at {list(camera.position)}, "
                            "outside the declared room. Check the measurements."
                        ),
                        scene_id=scene_id,
                        cameras=(camera.id,),
                    )
                )

    subjects = list(geometry.subjects.values())
    for index, first in enumerate(subjects):
        for second in subjects[index + 1 :]:
            distance = math.dist(first.position, second.position)
            if distance < SUBJECT_MIN_SEPARATION_M:
                findings.append(
                    Finding(
                        code="subjects_overlap",
                        severity="warning",
                        message=(
                            f"{first.label} and {second.label} are {distance:.2f} m apart; "
                            "they will read as one body."
                        ),
                        scene_id=scene_id,
                        subjects=(first.id, second.id),
                    )
                )

    findings.extend(_check_axis(geometry, used_cameras, scene_id))
    findings.extend(_check_eyeline_height(geometry, used_cameras, scene_id))
    findings.extend(_check_eyeline_direction(geometry, shots, scene_id))
    return findings


def _check_eyeline_direction(
    geometry: SceneGeometry,
    shots: list[dict[str, Any]],
    scene_id: str,
) -> list[Finding]:
    """Two people in conversation must look toward each other across the cut.

    If a shot puts its subject's interlocutor on the right of frame, the reverse
    shot has to put its own interlocutor on the left. When both land on the same
    side, the two characters appear to look the same way instead of at one
    another -- the single most expensive mistake to discover after generating,
    because a correct-looking shot is only wrong next to its reverse.

    The scene is read from the plan, never guessed: a shot is only checked when
    it declares both who it is on and who they are addressing.
    """

    covered: list[dict[str, Any]] = []
    findings: list[Finding] = []
    for shot in shots:
        subject_id = str(shot.get("subject", "")).strip()
        looks_at_id = str(shot.get("looks_at", "")).strip()
        camera_id = str(shot.get("camera", "")).strip()
        if not subject_id or not looks_at_id:
            continue

        camera = geometry.cameras.get(camera_id)
        subject = geometry.subjects.get(subject_id)
        other = geometry.subjects.get(looks_at_id)
        shot_id = str(shot.get("id", ""))
        if subject is None or other is None:
            findings.append(
                Finding(
                    code="eyeline_subject_missing",
                    severity="error",
                    message=(
                        f"Shot {shot_id} is on {subject_id} looking at {looks_at_id}, "
                        "but the scene geometry does not define both."
                    ),
                    scene_id=scene_id,
                    subjects=(subject_id, looks_at_id),
                    shots=(shot_id,),
                )
            )
            continue
        if camera is None:
            continue

        side, angle = screen_side(camera.position, subject.position, other.position)
        covered.append(
            {
                "shot_id": shot_id,
                "camera_id": camera_id,
                "subject": subject,
                "other": other,
                "side": side,
                "angle": angle,
            }
        )

    for index, first in enumerate(covered):
        for second in covered[index + 1 :]:
            facing = (
                first["subject"].id == second["other"].id
                and second["subject"].id == first["other"].id
            )
            if not facing:
                continue
            if first["side"] == "centred" or second["side"] == "centred":
                continue
            if first["side"] != second["side"]:
                continue
            findings.append(
                Finding(
                    code="eyeline_mismatch",
                    severity="error",
                    message=(
                        f"{first['subject'].label} and {second['subject'].label} both "
                        f"look toward the {first['side']} of frame: {first['shot_id']} "
                        f"(camera {first['camera_id']}, {abs(first['angle']):.0f}\u00b0) and "
                        f"{second['shot_id']} (camera {second['camera_id']}, "
                        f"{abs(second['angle']):.0f}\u00b0). Cut together they will not "
                        "appear to look at each other. One of the two cameras belongs on "
                        "the other side."
                    ),
                    scene_id=scene_id,
                    subjects=(first["subject"].id, second["subject"].id),
                    cameras=(first["camera_id"], second["camera_id"]),
                    shots=(first["shot_id"], second["shot_id"]),
                )
            )
    return findings


def _with_distance(camera_ids: list[str], distances: dict[str, float]) -> str:
    """Name cameras with how far off the line they sit, so the author can judge.

    A camera 8 cm off the line is a different conversation from one 1.5 m off,
    and the check should not hide that difference behind a verdict.
    """

    return ", ".join(f"{camera_id} ({distances.get(camera_id, 0):.2f} m)" for camera_id in camera_ids)


def _check_axis(
    geometry: SceneGeometry,
    used_cameras: dict[str, list[str]],
    scene_id: str,
) -> list[Finding]:
    if geometry.axis is None:
        return []

    first_id, second_id = geometry.axis.between
    first = geometry.subjects.get(first_id)
    second = geometry.subjects.get(second_id)
    if first is None or second is None:
        return [
            Finding(
                code="axis_subject_missing",
                severity="error",
                message=(
                    f"The line of action names {first_id} and {second_id}, but the scene "
                    "geometry does not define both subjects."
                ),
                scene_id=scene_id,
                subjects=(first_id, second_id),
            )
        ]

    sides: dict[int, list[str]] = {}
    distances: dict[str, float] = {}
    for camera_id in used_cameras:
        camera = geometry.cameras.get(camera_id)
        if camera is None:
            continue
        side, distance = _side_of_axis(first.position, second.position, camera.position)
        distances[camera_id] = distance
        sides.setdefault(side, []).append(camera_id)

    positive = sorted(sides.get(1, []))
    negative = sorted(sides.get(-1, []))
    if positive and negative:
        if len(negative) <= len(positive):
            crossing, majority = negative, positive
        else:
            crossing, majority = positive, negative
        shots = tuple(
            shot_id for camera_id in crossing for shot_id in used_cameras.get(camera_id, [])
        )
        return [
            Finding(
                code="axis_break",
                severity="error",
                message=(
                    f"Camera(s) {_with_distance(crossing, distances)} cross the line of "
                    f"action between {first.label} and {second.label}; "
                    f"{_with_distance(majority, distances)} stay on the other side. Cut "
                    "together, the two characters will appear to swap places and stop "
                    "looking at each other."
                ),
                scene_id=scene_id,
                subjects=(first.id, second.id),
                cameras=tuple(crossing),
                shots=shots,
            )
        ]
    return []


def _check_eyeline_height(
    geometry: SceneGeometry,
    used_cameras: dict[str, list[str]],
    scene_id: str,
) -> list[Finding]:
    """Flag a subject filmed from above in one shot and below in another.

    Keeping one subject at a constant vertical relationship to the camera is
    what makes a two-hander feel like one place rather than two.
    """

    by_subject: dict[str, dict[str, list[str]]] = {}
    for camera_id in used_cameras:
        camera = geometry.cameras.get(camera_id)
        if camera is None:
            continue
        subject = geometry.target_subject(camera)
        if subject is None or camera.height is None or subject.eye_height is None:
            # Without both heights there is nothing to compare; silence beats a
            # finding invented from a default.
            continue
        distance = math.dist(camera.position, subject.position)
        if distance == 0:
            continue
        angle = math.degrees(math.atan2(camera.height - subject.eye_height, distance))
        if abs(angle) <= LEVEL_ANGLE_TOLERANCE_DEG:
            direction = "level"
        else:
            direction = "above" if angle > 0 else "below"
        by_subject.setdefault(subject.id, {}).setdefault(direction, []).append(camera_id)

    findings: list[Finding] = []
    for subject_id, directions in sorted(by_subject.items()):
        if "above" in directions and "below" in directions:
            subject = geometry.subjects[subject_id]
            cameras = tuple(sorted(directions["above"] + directions["below"]))
            shots = tuple(
                shot_id for camera_id in cameras for shot_id in used_cameras.get(camera_id, [])
            )
            findings.append(
                Finding(
                    code="eyeline_height_flip",
                    severity="warning",
                    message=(
                        f"{subject.label} is filmed from above by "
                        f"{', '.join(sorted(directions['above']))} and from below by "
                        f"{', '.join(sorted(directions['below']))}. Unless the change is "
                        "deliberate, keep one height for one character across the scene."
                    ),
                    scene_id=scene_id,
                    subjects=(subject_id,),
                    cameras=cameras,
                    shots=shots,
                )
            )
    return findings
