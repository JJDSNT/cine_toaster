"""The blocking frame: what a shot's camera sees, computed from geometry (CT-0025).

No model is called. The camera is a pinhole with the shot's lens on a
full-frame 16:9 sensor, placed at the shot's start or end pose; subjects are
silhouettes at their positions for that moment (SPEC-0005). Because the frame
comes from the same numbers `toast check` reads, it cannot disagree with it:
a subject the checks call "left" is on the left here.

The frame is derived and never stored. It is the lowest storyboard fidelity
level, and later the composition input a master image is generated from.
"""

from __future__ import annotations

import math
from html import escape
from typing import Any

from .geometry import SENSOR_WIDTH_MM, screen_side

ASPECT = 16 / 9
SENSOR_HEIGHT_MM = SENSOR_WIDTH_MM / ASPECT
#: Where a camera sits, and where eyes are, when the plan does not say.
DEFAULT_CAMERA_HEIGHT = 1.5
DEFAULT_EYE_HEIGHT = 1.6
HEAD_RADIUS = 0.11
SHOULDER_WIDTH = 0.46
NEAR = 0.05

WIDTH, HEIGHT = 640, 360
PALETTE = ("#e7b75c", "#6fb7d9", "#d97a6f", "#8fcf8a", "#b99ae0", "#d9c56f")

Vec = tuple[float, float, float]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a: Vec) -> Vec:
    length = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


class _Camera:
    """A pinhole looking from `eye` at `aim`, level unless the aim has a height."""

    def __init__(self, eye: Vec, aim: Vec, lens_mm: float) -> None:
        self.eye = eye
        self.forward = _unit(_sub(aim, eye))
        # Screen right is the plan view vector turned a quarter clockwise --
        # the convention `screen_side` uses, so both agree on every side.
        self.right = _unit((self.forward[1], -self.forward[0], 0.0))
        f, r = self.forward, self.right
        self.up = (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])
        self.lens_mm = lens_mm
        self.tilt_deg = math.degrees(math.asin(max(-1.0, min(1.0, f[2]))))

    def depth(self, point: Vec) -> float:
        return _dot(_sub(point, self.eye), self.forward)

    def project(self, point: Vec) -> tuple[float, float, float] | None:
        """Normalised frame coordinates: x and y in [-1, 1] are in frame, y up."""

        d = _sub(point, self.eye)
        depth = _dot(d, self.forward)
        if depth <= NEAR:
            return None
        x = _dot(d, self.right) / depth * self.lens_mm / (SENSOR_WIDTH_MM / 2)
        y = _dot(d, self.up) / depth * self.lens_mm / (SENSOR_HEIGHT_MM / 2)
        return x, y, depth

    def metres_to_frame(self, metres: float, depth: float) -> float:
        """A length at a depth, as a fraction of the frame's half-width."""

        return metres / depth * self.lens_mm / (SENSOR_WIDTH_MM / 2)

    def clip_segment(self, a: Vec, b: Vec) -> tuple[Vec, Vec] | None:
        da, db = self.depth(a) - NEAR, self.depth(b) - NEAR
        if da <= 0 and db <= 0:
            return None
        if da > 0 and db > 0:
            return a, b
        t = da / (da - db)
        cut = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
        return (a, cut) if da > 0 else (cut, b)

    def clip_polygon(self, points: list[Vec]) -> list[Vec]:
        kept: list[Vec] = []
        for index, current in enumerate(points):
            previous = points[index - 1]
            inside_now = self.depth(current) > NEAR
            inside_before = self.depth(previous) > NEAR
            if inside_now != inside_before:
                segment = self.clip_segment(previous, current)
                if segment:
                    kept.append(segment[1] if inside_now else segment[0])
            if inside_now:
                kept.append(current)
        return kept


def blocking_frame(scene: dict[str, Any], shot: dict[str, Any], at: str = "start") -> dict[str, Any] | None:
    """The camera's view at a shot's start or end, as numbers and shapes.

    Returns None when the shot has no camera pose to look from.
    """

    if at not in ("start", "end"):
        raise ValueError("at must be 'start' or 'end'")
    geometry = scene.get("geometry") or {}
    motion = shot.get("motion") or {}
    state = motion.get(at) or {}
    pose = state.get("camera")
    if not pose:
        return None

    subjects = {item["id"]: item for item in geometry.get("subjects", [])}
    positions = {key: tuple(value) for key, value in (state.get("subjects") or {}).items()}
    camera_height = pose.get("height") or DEFAULT_CAMERA_HEIGHT
    target_ref = pose.get("target_ref") or ""
    aim_height = camera_height
    if target_ref in subjects:
        aim_height = subjects[target_ref].get("eye_height") or DEFAULT_EYE_HEIGHT
    eye = (pose["position"][0], pose["position"][1], camera_height)
    aim = (pose["target"][0], pose["target"][1], aim_height)
    camera = _Camera(eye, aim, float(pose["lens_mm"]))

    figures = []
    for order, subject_id in enumerate(sorted(positions)):
        x, y = positions[subject_id]
        info = subjects.get(subject_id, {"label": subject_id})
        eye_height = info.get("eye_height") or DEFAULT_EYE_HEIGHT
        foot = camera.project((x, y, 0.0))
        head = camera.project((x, y, eye_height + 0.02))
        side, angle = screen_side(pose["position"], pose["target"], (x, y))
        if foot is None or head is None:
            figures.append({"subject": subject_id, "label": info.get("label", subject_id),
                            "behind": True, "in_frame": False, "side": side, "angle": round(angle, 1)})
            continue
        depth = head[2]
        half_width = camera.metres_to_frame(SHOULDER_WIDTH / 2, depth)
        figures.append(
            {
                "subject": subject_id,
                "label": info.get("label", subject_id),
                "behind": False,
                "x": round(head[0], 3),
                "eye_y": round(head[1], 3),
                "foot_y": round(foot[1], 3),
                "depth": round(depth, 2),
                # How much of the frame's height the figure fills, foot to crown.
                "height_fraction": round((head[1] - foot[1]) / 2, 3),
                "in_frame": abs(head[0]) - half_width <= 1.0 and foot[1] <= 1.0 and head[1] >= -1.0,
                "side": side,
                "angle": round(angle, 1),
                "colour": PALETTE[order % len(PALETTE)],
                "_shape": _figure_shape(camera, (x, y), eye_height),
            }
        )

    room = geometry.get("room") or {}
    lines = _room_lines(camera, room) if room else []
    axis = geometry.get("axis") or {}
    between = [positions.get(s) for s in axis.get("between", [])]
    axis_line = None
    if len(between) == 2 and all(between):
        segment = camera.clip_segment((*between[0], 0.0), (*between[1], 0.0))
        if segment:
            a, b = camera.project(segment[0]), camera.project(segment[1])
            if a and b:
                axis_line = ((a[0], a[1]), (b[0], b[1]))
    marks = []
    for mark in geometry.get("marks", []):
        point = camera.project((mark["position"][0], mark["position"][1], 0.0))
        if point:
            marks.append({"id": mark["id"], "x": point[0], "y": point[1], "depth": point[2]})

    return {
        "scene": scene.get("id"),
        "shot": shot.get("id"),
        "at": at,
        "camera": {
            "id": motion.get("camera_id", ""),
            "lens_mm": camera.lens_mm,
            "height": camera_height,
            "height_declared": pose.get("height") is not None,
            "tilt_deg": round(camera.tilt_deg, 1),
        },
        "figures": sorted(figures, key=lambda item: -item.get("depth", 0.0)),
        "_lines": lines,
        "_floor": _floor(camera, room) if room else [],
        "_axis": axis_line,
        "_marks": marks,
    }


def _figure_shape(camera: _Camera, plan: tuple[float, float], eye_height: float) -> dict[str, Any]:
    """A silhouette facing the camera: a tapered body and a head."""

    x, y = plan
    r = camera.right
    half = SHOULDER_WIDTH / 2
    # Shoulders sit just under the head, leaving a neck's gap.
    shoulder = max(eye_height - 0.14, 0.1)
    corners = [
        (x - r[0] * half * 0.6, y - r[1] * half * 0.6, 0.0),
        (x + r[0] * half * 0.6, y + r[1] * half * 0.6, 0.0),
        (x + r[0] * half, y + r[1] * half, shoulder),
        (x - r[0] * half, y - r[1] * half, shoulder),
    ]
    body = [camera.project(point) for point in camera.clip_polygon(corners)]
    centre = camera.project((x, y, eye_height + 0.02))
    radius = camera.metres_to_frame(HEAD_RADIUS, centre[2]) if centre else 0.0
    return {
        "body": [(p[0], p[1]) for p in body if p],
        "head": (centre[0], centre[1], radius) if centre else None,
    }


def _room_lines(camera: _Camera, room: dict[str, float]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    w, d, h = room.get("width", 0.0), room.get("depth", 0.0), room.get("height", 0.0) or 2.7
    corners = [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)]
    segments = []
    for index, (x, y) in enumerate(corners):
        nx, ny = corners[(index + 1) % 4]
        segments.append(((x, y, 0.0), (nx, ny, 0.0)))
        segments.append(((x, y, h), (nx, ny, h)))
        segments.append(((x, y, 0.0), (x, y, h)))
    lines = []
    for a, b in segments:
        clipped = camera.clip_segment(a, b)
        if not clipped:
            continue
        pa, pb = camera.project(clipped[0]), camera.project(clipped[1])
        if pa and pb:
            lines.append(((pa[0], pa[1]), (pb[0], pb[1])))
    return lines


def _floor(camera: _Camera, room: dict[str, float]) -> list[tuple[float, float]]:
    w, d = room.get("width", 0.0), room.get("depth", 0.0)
    kept = camera.clip_polygon([(0.0, 0.0, 0.0), (w, 0.0, 0.0), (w, d, 0.0), (0.0, d, 0.0)])
    return [(p[0], p[1]) for p in (camera.project(point) for point in kept) if p]


def public_frame(frame: dict[str, Any]) -> dict[str, Any]:
    """The frame's facts, without the drawing."""

    return {
        key: value if key != "figures" else [
            {k: v for k, v in figure.items() if not k.startswith("_")} for figure in value
        ]
        for key, value in frame.items()
        if not key.startswith("_")
    }


def _px(point: tuple[float, float]) -> str:
    return f"{(point[0] + 1) * WIDTH / 2:.1f},{(1 - point[1]) * HEIGHT / 2:.1f}"


def render_svg(frame: dict[str, Any]) -> str:
    """The frame as an SVG drawing, 640x360, in the palette of the blockout."""

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" font-family="system-ui, sans-serif">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#101315"/>',
    ]
    if frame["_floor"]:
        out.append(f'<polygon points="{" ".join(_px(p) for p in frame["_floor"])}" fill="#1a1f22"/>')
    for a, b in frame["_lines"]:
        out.append(f'<line x1="{_px(a).split(",")[0]}" y1="{_px(a).split(",")[1]}" '
                   f'x2="{_px(b).split(",")[0]}" y2="{_px(b).split(",")[1]}" stroke="#3a4247" stroke-width="1"/>')
    if frame["_axis"]:
        a, b = frame["_axis"]
        (ax, ay), (bx, by) = _px(a).split(","), _px(b).split(",")
        out.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#ed6e68" '
                   f'stroke-width="1.2" stroke-dasharray="6 5" opacity="0.8"/>')
    for mark in frame["_marks"]:
        x, y = (float(v) for v in _px((mark["x"], mark["y"])).split(","))
        out.append(f'<path d="M{x - 5},{y - 3} L{x + 5},{y + 3} M{x - 5},{y + 3} L{x + 5},{y - 3}" '
                   f'stroke="#8a9499" stroke-width="1.2"/>')
    for third in (1, 2):
        out.append(f'<line x1="{WIDTH * third / 3:.1f}" y1="0" x2="{WIDTH * third / 3:.1f}" y2="{HEIGHT}" '
                   f'stroke="#ffffff" stroke-opacity="0.06"/>')
        out.append(f'<line x1="0" y1="{HEIGHT * third / 3:.1f}" x2="{WIDTH}" y2="{HEIGHT * third / 3:.1f}" '
                   f'stroke="#ffffff" stroke-opacity="0.06"/>')

    offscreen = []
    for figure in frame["figures"]:
        shape = figure.get("_shape")
        if figure["behind"] or not figure["in_frame"] or not shape:
            offscreen.append(figure)
            continue
        colour = figure["colour"]
        if len(shape["body"]) >= 3:
            out.append(f'<polygon points="{" ".join(_px(p) for p in shape["body"])}" '
                       f'fill="{colour}" fill-opacity="0.85"/>')
        if shape["head"]:
            hx, hy, radius = shape["head"]
            cx, cy = (float(v) for v in _px((hx, hy)).split(","))
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius * WIDTH / 2:.1f}" fill="{colour}"/>')
            label_y = max(cy - radius * WIDTH / 2 - 6, 12)
            out.append(f'<text x="{min(max(cx, 40), WIDTH - 40):.1f}" y="{label_y:.1f}" fill="#e8ecee" '
                       f'font-size="12" text-anchor="middle">{escape(figure["label"])}</text>')

    for index, figure in enumerate(offscreen):
        left = figure["side"] == "left" or (figure["side"] == "centred" and figure["behind"])
        text = f'◂ {figure["label"]}' if left else f'{figure["label"]} ▸'
        if figure["behind"]:
            text = f'{figure["label"]} (behind camera)'
        out.append(f'<text x="{8 if left else WIDTH - 8}" y="{HEIGHT - 32 - 16 * index}" fill="#8a9499" '
                   f'font-size="11" text-anchor="{"start" if left else "end"}">{escape(text)}</text>')

    out.append(f'<rect y="{HEIGHT - 22}" width="{WIDTH}" height="22" fill="#101315" fill-opacity="0.85"/>')
    camera = frame["camera"]
    height = f'{camera["height"]:.2f} m' + ("" if camera["height_declared"] else " (assumed)")
    caption = (f'{frame["shot"]} · {frame["at"]} · {camera["id"]} · {camera["lens_mm"]:g} mm · '
               f'height {height} · tilt {camera["tilt_deg"]:+.0f}°')
    out.append(f'<text x="8" y="{HEIGHT - 8}" fill="#8a9499" font-size="11">{escape(caption)}</text>')
    out.append("</svg>")
    return "\n".join(out)
