// Top-down blockout of a scene: the room, where people are, where the cameras
// are, and the line of action between them.
//
// This is deliberately a 2D plan on a plain canvas rather than a 3D scene. What
// a director needs to check before generating a shot -- which side of the line
// a camera sits on, whether two cameras look at the same person from opposite
// heights, whether coverage is reused -- is all readable from above, and a plan
// works offline with no dependency. A real 3D viewer stays a candidate for when
// set dressing and sightline occlusion matter.

const PADDING = 28;
const COLORS = {
  room: "#2b3134",
  floor: "#101314",
  grid: "#1b2022",
  subject: "#70aee8",
  camera: "#8c9597",
  cameraActive: "#ef6a3a",
  cameraFlagged: "#ed6e68",
  axis: "#e7b75c",
  mark: "#b99be0",
  path: "#70aee8",
  cameraPath: "#ef6a3a",
  text: "#f1eee7",
  muted: "#8c9597",
};

function projector(room, width, height) {
  const usableWidth = width - PADDING * 2;
  const usableHeight = height - PADDING * 2;
  const scale = Math.min(usableWidth / room.width, usableHeight / room.depth);
  const offsetX = (width - room.width * scale) / 2;
  const offsetY = (height - room.depth * scale) / 2;
  // Depth grows away from the viewer, so it is drawn upward on screen.
  return {
    scale,
    point: ([x, y]) => [offsetX + x * scale, offsetY + (room.depth - y) * scale],
  };
}

function drawGrid(context, room, project) {
  context.strokeStyle = COLORS.grid;
  context.lineWidth = 1;
  // A metre grid for a room; ten metres for a street or a landscape.
  const step = Math.max(room.width, room.depth) > 30 ? 10 : 1;
  for (let x = 0; x <= room.width; x += step) {
    const [sx, sy0] = project.point([x, 0]);
    const [, sy1] = project.point([x, room.depth]);
    context.beginPath();
    context.moveTo(sx, sy0);
    context.lineTo(sx, sy1);
    context.stroke();
  }
  for (let y = 0; y <= room.depth; y += step) {
    const [sx0, sy] = project.point([0, y]);
    const [sx1] = project.point([room.width, y]);
    context.beginPath();
    context.moveTo(sx0, sy);
    context.lineTo(sx1, sy);
    context.stroke();
  }
}

function drawSubject(context, subject, project, { position = subject.position, ghost = false } = {}) {
  const [x, y] = project.point(position);
  context.beginPath();
  if (subject.kind === "object") {
    // An object is its footprint, not a person's dot.
    const side = subject.width || 0.6;
    footprint(position, side, side).map(project.point).forEach(([px, py], index) => (index ? context.lineTo(px, py) : context.moveTo(px, py)));
    context.closePath();
  } else {
    context.arc(x, y, 9, 0, Math.PI * 2);
  }
  if (ghost) {
    // Where the subject was when the shot began: an outline, not a body.
    context.strokeStyle = COLORS.subject;
    context.lineWidth = 1.5;
    context.stroke();
    return;
  }
  context.fillStyle = COLORS.subject;
  context.fill();
  // Beside the body: past the footprint's edge for an object.
  const gap = subject.kind === "object" ? ((subject.width || 0.6) / 2) * project.scale + 6 : 14;
  context.fillStyle = COLORS.text;
  context.font = "600 12px Inter, system-ui, sans-serif";
  context.fillText(subject.label, x + gap, y + 4);
  const note = subject.kind === "object" && subject.height ? `${subject.height} m tall`
    : subject.eye_height != null ? `eye ${subject.eye_height} m` : "";
  if (note) {
    context.fillStyle = COLORS.muted;
    context.font = "11px Inter, system-ui, sans-serif";
    context.fillText(note, x + gap, y + 19);
  }
}

// A set piece or an object subject: its footprint, turned, and its height (CT-0025).
function footprint(position, width, depth, rotation = 0) {
  const angle = (rotation * Math.PI) / 180;
  const [cos, sin] = [Math.cos(angle), Math.sin(angle)];
  return [[-width / 2, -depth / 2], [width / 2, -depth / 2], [width / 2, depth / 2], [-width / 2, depth / 2]]
    .map(([dx, dy]) => [position[0] + dx * cos - dy * sin, position[1] + dx * sin + dy * cos]);
}

function drawPiece(context, piece, project) {
  const corners = footprint(piece.position, piece.width, piece.depth, piece.rotation_deg || 0).map(project.point);
  context.beginPath();
  corners.forEach(([x, y], index) => (index ? context.lineTo(x, y) : context.moveTo(x, y)));
  context.closePath();
  context.fillStyle = "rgba(89, 99, 106, 0.55)";
  context.fill();
  context.strokeStyle = "#8a9499";
  context.lineWidth = 1.2;
  context.stroke();
  const [x, y] = project.point(piece.position);
  context.fillStyle = COLORS.muted;
  context.font = "10px Inter, system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText(`${piece.label} · ${piece.height} m`, x, y + 3);
  context.textAlign = "left";
}

function drawMark(context, mark, project) {
  const [x, y] = project.point(mark.position);
  context.strokeStyle = COLORS.mark;
  context.lineWidth = 1.5;
  context.beginPath();
  context.moveTo(x, y - 7);
  context.lineTo(x + 7, y);
  context.lineTo(x, y + 7);
  context.lineTo(x - 7, y);
  context.closePath();
  context.stroke();
  // Labelled on the left: a subject standing on the mark labels itself on the right.
  context.fillStyle = COLORS.mark;
  context.font = "10px Inter, system-ui, sans-serif";
  context.textAlign = "right";
  context.fillText(mark.label || mark.id, x - 11, y + 18);
  context.textAlign = "left";
}

function drawArrow(context, from, to, color, label, { dashed = false } = {}) {
  const [x0, y0] = from;
  const [x1, y1] = to;
  if (Math.hypot(x1 - x0, y1 - y0) < 4) return;
  const heading = Math.atan2(y1 - y0, x1 - x0);
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = 1.5;
  if (dashed) context.setLineDash([5, 4]);
  context.beginPath();
  context.moveTo(x0, y0);
  context.lineTo(x1, y1);
  context.stroke();
  context.setLineDash([]);
  context.beginPath();
  context.moveTo(x1, y1);
  context.lineTo(x1 - Math.cos(heading - 0.45) * 9, y1 - Math.sin(heading - 0.45) * 9);
  context.lineTo(x1 - Math.cos(heading + 0.45) * 9, y1 - Math.sin(heading + 0.45) * 9);
  context.closePath();
  context.fill();
  if (label) {
    context.font = "700 10px Inter, system-ui, sans-serif";
    context.fillText(label, (x0 + x1) / 2 + 6, (y0 + y1) / 2 - 6);
  }
}

function fovDegrees(lens) {
  return (2 * Math.atan(36 / (2 * lens)) * 180) / Math.PI;
}

function drawCamera(context, camera, target, project, tone) {
  const [x, y] = project.point(camera.position);
  const [tx, ty] = project.point(target);
  const heading = Math.atan2(ty - y, tx - x);
  const half = (camera.fov_degrees * Math.PI) / 360;
  const reach = Math.max(40, project.scale * 2.4);

  context.fillStyle = tone === "flagged" ? "rgba(237,110,104,.16)" : "rgba(239,106,58,.12)";
  context.beginPath();
  context.moveTo(x, y);
  context.arc(x, y, reach, heading - half, heading + half);
  context.closePath();
  context.fill();

  const color = tone === "flagged"
    ? COLORS.cameraFlagged
    : tone === "active"
      ? COLORS.cameraActive
      : COLORS.camera;
  context.fillStyle = color;
  context.beginPath();
  context.arc(x, y, 7, 0, Math.PI * 2);
  context.fill();
  context.strokeStyle = color;
  context.lineWidth = 1.5;
  context.beginPath();
  context.moveTo(x, y);
  context.lineTo(x + Math.cos(heading) * 18, y + Math.sin(heading) * 18);
  context.stroke();

  context.fillStyle = color;
  context.font = "700 11px Inter, system-ui, sans-serif";
  context.fillText(camera.id, x + 11, y - 8);
  context.fillStyle = COLORS.muted;
  context.font = "10px Inter, system-ui, sans-serif";
  context.fillText(`${camera.lens_mm}mm · ${camera.height} m`, x + 11, y + 6);
}

function drawAxis(context, geometry, project, positions = {}) {
  if (!geometry.axis) return;
  const [firstId, secondId] = geometry.axis.between;
  const first = geometry.subjects.find((subject) => subject.id === firstId);
  const second = geometry.subjects.find((subject) => subject.id === secondId);
  if (!first || !second) return;

  // The line runs between the two where they stand when the shown shot begins.
  const [ax, ay] = project.point(positions[firstId] || first.position);
  const [bx, by] = project.point(positions[secondId] || second.position);
  const dx = bx - ax;
  const dy = by - ay;
  const length = Math.hypot(dx, dy) || 1;
  // Extend the line well past both subjects: what matters is the whole plane it
  // divides, not the segment between the two people.
  const extend = 2000 / length;
  context.setLineDash([7, 6]);
  context.strokeStyle = COLORS.axis;
  context.lineWidth = 1.5;
  context.beginPath();
  context.moveTo(ax - dx * extend, ay - dy * extend);
  context.lineTo(bx + dx * extend, by + dy * extend);
  context.stroke();
  context.setLineDash([]);

  context.fillStyle = COLORS.axis;
  context.font = "700 10px Inter, system-ui, sans-serif";
  context.fillText("LINE OF ACTION", (ax + bx) / 2 + 8, (ay + by) / 2 - 8);
}

export function drawBlockout(
  canvas,
  geometry,
  { findings = [], activeCamera = "", motions = [], activeShot = "" } = {},
) {
  const room = geometry.room;
  if (!room) return false;

  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 640;
  const height = Math.round(width * (room.depth / room.width));
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  canvas.style.height = `${height}px`;

  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);
  context.clearRect(0, 0, width, height);

  const project = projector(room, width, height);
  const [originX, originY] = project.point([0, room.depth]);
  context.fillStyle = COLORS.floor;
  context.fillRect(originX, originY, room.width * project.scale, room.depth * project.scale);
  drawGrid(context, room, project);
  context.strokeStyle = COLORS.room;
  context.lineWidth = 2;
  // Outdoors the edge is only where the plan stops, not a wall.
  if (room.exterior) context.setLineDash([8, 6]);
  context.strokeRect(originX, originY, room.width * project.scale, room.depth * project.scale);
  context.setLineDash([]);

  const active = activeShot ? motions.find((motion) => motion.shot_id === activeShot) : null;
  drawAxis(context, geometry, project, active ? active.start.subjects : {});

  for (const piece of geometry.set_pieces || []) drawPiece(context, piece, project);
  for (const mark of geometry.marks || []) drawMark(context, mark, project);

  // Movement within shots (SPEC-0005): subject paths and camera paths. With a
  // shot selected, only that shot's start and end are drawn.
  const shown = activeShot ? motions.filter((motion) => motion.shot_id === activeShot) : motions;
  for (const motion of shown) {
    for (const subjectId of motion.moved_subjects || []) {
      const from = motion.start.subjects[subjectId];
      const to = motion.end.subjects[subjectId];
      if (from && to) {
        drawArrow(context, project.point(from), project.point(to), COLORS.path, motion.shot_id);
      }
    }
    const start = motion.start.camera;
    const end = motion.end.camera;
    if (start && end && motion.kind !== "static" &&
        (start.position[0] !== end.position[0] || start.position[1] !== end.position[1])) {
      drawArrow(context, project.point(start.position), project.point(end.position),
        COLORS.cameraPath, `${motion.shot_id} ${motion.kind} ${motion.direction}`.trim(), { dashed: true });
    }
  }

  const flagged = new Set(findings.flatMap((finding) => finding.cameras || []));
  for (const camera of geometry.cameras) {
    const target = typeof camera.target === "string"
      ? geometry.subjects.find((subject) => subject.id === camera.target)?.position
      : camera.target;
    if (!target) continue;
    // The selected shot's camera is drawn below at its own start and end aim.
    if (active && camera.id === active.camera_id && active.start.camera) continue;
    const endPosition = active?.end.camera?.position;
    if (endPosition && endPosition[0] === camera.position[0] && endPosition[1] === camera.position[1]) continue;
    const tone = flagged.has(camera.id)
      ? "flagged"
      : camera.id === activeCamera
        ? "active"
        : "idle";
    drawCamera(context, camera, target, project, tone);
  }
  if (active && active.start.camera && active.end.camera) {
    // The selected shot's camera at its start and its end, whatever its name.
    const camera = geometry.cameras.find((item) => item.id === active.camera_id) || { id: active.camera_id };
    for (const [pose, suffix] of [[active.start.camera, "start"], [active.end.camera, "end"]]) {
      drawCamera(context, {
        ...camera,
        id: active.kind === "static" ? active.camera_id : `${active.camera_id} ${suffix}`,
        position: pose.position,
        lens_mm: pose.lens_mm,
        height: pose.height,
        fov_degrees: fovDegrees(pose.lens_mm),
      }, pose.target, project, "active");
      if (active.kind === "static") break;
    }
  }

  for (const subject of geometry.subjects) {
    if (!active) {
      drawSubject(context, subject, project);
      continue;
    }
    const from = active.start.subjects[subject.id] || subject.position;
    const to = active.end.subjects[subject.id] || from;
    if (from[0] !== to[0] || from[1] !== to[1]) drawSubject(context, subject, project, { position: from, ghost: true });
    drawSubject(context, subject, project, { position: to });
  }

  context.fillStyle = COLORS.muted;
  context.font = "10px Inter, system-ui, sans-serif";
  context.fillText(`${room.width} × ${room.depth} m`, PADDING / 2, height - 8);
  return true;
}
