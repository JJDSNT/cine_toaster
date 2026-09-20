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
  for (let x = 0; x <= room.width; x += 1) {
    const [sx, sy0] = project.point([x, 0]);
    const [, sy1] = project.point([x, room.depth]);
    context.beginPath();
    context.moveTo(sx, sy0);
    context.lineTo(sx, sy1);
    context.stroke();
  }
  for (let y = 0; y <= room.depth; y += 1) {
    const [sx0, sy] = project.point([0, y]);
    const [sx1] = project.point([room.width, y]);
    context.beginPath();
    context.moveTo(sx0, sy);
    context.lineTo(sx1, sy);
    context.stroke();
  }
}

function drawSubject(context, subject, project) {
  const [x, y] = project.point(subject.position);
  context.fillStyle = COLORS.subject;
  context.beginPath();
  context.arc(x, y, 9, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = COLORS.text;
  context.font = "600 12px Inter, system-ui, sans-serif";
  context.fillText(subject.label, x + 14, y + 4);
  context.fillStyle = COLORS.muted;
  context.font = "11px Inter, system-ui, sans-serif";
  context.fillText(`eye ${subject.eye_height} m`, x + 14, y + 19);
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

function drawAxis(context, geometry, project) {
  if (!geometry.axis) return;
  const [firstId, secondId] = geometry.axis.between;
  const first = geometry.subjects.find((subject) => subject.id === firstId);
  const second = geometry.subjects.find((subject) => subject.id === secondId);
  if (!first || !second) return;

  const [ax, ay] = project.point(first.position);
  const [bx, by] = project.point(second.position);
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

export function drawBlockout(canvas, geometry, { findings = [], activeCamera = "" } = {}) {
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
  context.strokeRect(originX, originY, room.width * project.scale, room.depth * project.scale);

  drawAxis(context, geometry, project);

  const flagged = new Set(findings.flatMap((finding) => finding.cameras || []));
  for (const camera of geometry.cameras) {
    const target = typeof camera.target === "string"
      ? geometry.subjects.find((subject) => subject.id === camera.target)?.position
      : camera.target;
    if (!target) continue;
    const tone = flagged.has(camera.id)
      ? "flagged"
      : camera.id === activeCamera
        ? "active"
        : "idle";
    drawCamera(context, camera, target, project, tone);
  }
  for (const subject of geometry.subjects) drawSubject(context, subject, project);

  context.fillStyle = COLORS.muted;
  context.font = "10px Inter, system-ui, sans-serif";
  context.fillText(`${room.width} × ${room.depth} m`, PADDING / 2, height - 8);
  return true;
}
