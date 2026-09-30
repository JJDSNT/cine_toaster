"""Gaussian splats rendered along a camera path: a captured set as a plate or an element (CT-0047).

A splat (`.ply`, `.spz`, `.splat`, `.ksplat`, `.sog`) is drawn by Spark
(World Labs, MIT: three.js and WebGL2) in a headless Chromium driven by
Playwright, frame by frame, with a transparent background:

- `render(splat, poses, ...)` writes a PNG sequence for any list of camera
  poses (position, target, lens in millimetres on a 36 mm sensor);
- `turntable_poses` circles a point (a splat as an element);
- `shot_poses` samples a shot's camera move with the blocking frame's
  poses, mapped from the plan (metres, Z up) into the splat through the
  location's `splat` transform -- the captured set seen from the plan's
  cameras (a plate, SPEC-0010).

Spark and three.js are fetched once into the shared asset folder (never
bundled); Chromium comes from Playwright (`make install-splat`).
"""

from __future__ import annotations

import functools
import http.server
import json
import math
import shutil
import threading
import urllib.request
from pathlib import Path
from typing import Any

from .errors import ValidationError

ASSETS = Path.home() / ".local" / "share" / "cine-toaster" / "assets" / "spark"
LIBRARIES = {
    "three.module.js": "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js",
    "three.core.js": "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.core.js",
    "spark.module.js": "https://sparkjs.dev/releases/spark/2.3.0/spark.module.js",
    # Spark imports one of three.js's addons.
    "addons/postprocessing/Pass.js": "https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/postprocessing/Pass.js",
}
SAMPLE = "https://sparkjs.dev/assets/splats/butterfly.spz"
SENSOR_WIDTH_MM = 36.0
FORMATS = (".ply", ".spz", ".splat", ".ksplat", ".sog")

PAGE = """<!doctype html>
<meta charset="utf-8">
<style>html,body{margin:0;background:transparent;overflow:hidden}</style>
<script type="importmap">{"imports": {"three": "/lib/three.module.js", "three/addons/": "/lib/addons/",
  "@sparkjsdev/spark": "/lib/spark.module.js"}}</script>
<script type="module">
import * as THREE from "three";
import { SparkRenderer, SplatMesh } from "@sparkjsdev/spark";
const spec = await (await fetch("/spec.json")).json();
const renderer = new THREE.WebGLRenderer({ alpha: true, preserveDrawingBuffer: true, antialias: false });
renderer.setPixelRatio(1);
renderer.setSize(spec.width, spec.height);
renderer.setClearColor(0x000000, 0);
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, spec.width / spec.height, 0.01, 5000);
scene.add(new SparkRenderer({ renderer }));
const splat = new SplatMesh({ url: "/splat/" + spec.splat });
const t = spec.transform;
splat.position.set(...t.position);
splat.quaternion.set(...t.quaternion);
splat.scale.setScalar(t.scale);
scene.add(splat);
await splat.initialized;
if (t.centre) {
  // Frame the splat itself, not the origin of its file.
  const box = splat.getBoundingBox(true);
  const middle = box.getCenter(new THREE.Vector3()).multiplyScalar(t.scale).applyQuaternion(splat.quaternion);
  splat.position.sub(middle);
}
const pixels = new Uint8Array(4 * 64);
const drawn = () => {
  const gl = renderer.getContext();
  gl.readPixels(Math.floor(spec.width / 2) - 32, Math.floor(spec.height / 2), 64, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  return pixels.some((value, index) => index % 4 === 3 && value > 0);
};
window.frame = async (index) => {
  const pose = spec.poses[index];
  camera.position.set(...pose.position);
  camera.up.set(0, 1, 0);
  camera.lookAt(...pose.target);
  // Vertical field of view from the lens on a 36 mm-wide sensor.
  const horizontal = 2 * Math.atan(18 / pose.lens_mm);
  camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(Math.tan(horizontal / 2) / camera.aspect));
  camera.updateProjectionMatrix();
  // Spark sorts splats for the view in a worker: let it settle before the picture is taken
  // (and, for the first frame, until something is drawn at all).
  for (let pass = 0; pass < (index === 0 ? 240 : 2); pass++) {
    renderer.render(scene, camera);
    await new Promise((resolve) => requestAnimationFrame(resolve));
    if (index === 0 && pass > 3 && drawn()) break;
  }
  return renderer.domElement.toDataURL("image/png");
};
window.ready = true;
</script>
"""


def available() -> str:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "Playwright is not installed (make install-splat)"
    return ""


def libraries() -> Path:
    """Spark and three.js, fetched once."""

    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, url in LIBRARIES.items():
        path = ASSETS / name
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".part")
            urllib.request.urlretrieve(url, temporary)  # noqa: S310 - fixed, public URLs
            temporary.replace(path)
    return ASSETS


def sample() -> Path:
    """Spark's own sample splat (a butterfly), fetched once."""

    path = ASSETS / "butterfly.spz"
    if not path.is_file():
        ASSETS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SAMPLE, path.with_suffix(".part"))  # noqa: S310
        path.with_suffix(".part").replace(path)
    return path


def plan_to_splat(point: tuple[float, float, float]) -> list[float]:
    """The plan's metres (x right, y deep, z up) in three.js's frame (y up, -z deep)."""

    x, y, z = point
    return [x, z, -y]


def quaternion(rotation: Any) -> list[float]:
    """A splat's rotation as [x, y, z, w]: given as such, or as Euler degrees [x, y, z]."""

    values = [float(value) for value in (rotation or [0, 0, 0])]
    if len(values) == 4:
        return values
    x, y, z = (math.radians(value) / 2 for value in values)
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    return [sx * cy * cz + cx * sy * sz, cx * sy * cz - sx * cy * sz, cx * cy * sz + sx * sy * cz,
            cx * cy * cz - sx * sy * sz]


def turntable_poses(frames: int, *, radius: float = 3.0, height: float = 0.4, degrees: float = 60.0,
                    lens_mm: float = 35.0, target: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> list[dict]:
    poses = []
    for index in range(frames):
        angle = math.radians(-degrees / 2 + degrees * index / max(1, frames - 1))
        position = [target[0] + radius * math.sin(angle), target[1] + height, target[2] + radius * math.cos(angle)]
        poses.append({"position": position, "target": list(target), "lens_mm": lens_mm})
    return poses


def shot_poses(scene: dict[str, Any], shot: dict[str, Any], frames: int) -> list[dict]:
    """A shot's camera move, sampled like the blocking frame, in the splat's frame."""

    from .blocking import DEFAULT_CAMERA_HEIGHT, DEFAULT_EYE_HEIGHT, state_at

    motion = shot.get("motion") or {}
    if not (motion.get("start") or {}).get("camera"):
        raise ValidationError(f"{shot.get('id')} has no camera pose to fly through the splat")
    subjects = {item["id"]: item for item in (scene.get("geometry") or {}).get("subjects", [])}
    poses = []
    for index in range(frames):
        state = state_at(motion, index / max(1, frames - 1))
        pose = state["camera"]
        height = float(pose.get("height") or DEFAULT_CAMERA_HEIGHT)
        aim = pose.get("aim_height")
        if aim is None:
            target = subjects.get(pose.get("target_ref") or "")
            aim = (target.get("eye_height") or DEFAULT_EYE_HEIGHT) if target else height
        poses.append({"position": plan_to_splat((*pose["position"], height)),
                      "target": plan_to_splat((*pose["target"], float(aim))), "lens_mm": float(pose["lens_mm"])})
    return poses


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D401 - silence
        return


def render(splat_file: Path, poses: list[dict], output: Path, *, width: int = 640, height: int = 360,
           transform: dict[str, Any] | None = None) -> str:
    """Draw the splat from each pose into `output/f_%04d.png` (RGBA); returns the pattern."""

    missing = available()
    if missing:
        raise ValidationError(missing)
    if splat_file.suffix.lower() not in FORMATS:
        raise ValidationError(f"{splat_file.name} is not a splat Spark reads", formats=list(FORMATS))
    from playwright.sync_api import sync_playwright

    transform = transform or {}
    site = output / ".site"
    (site / "lib").mkdir(parents=True, exist_ok=True)
    (site / "splat").mkdir(exist_ok=True)
    for name in LIBRARIES:
        (site / "lib" / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(libraries() / name, site / "lib" / name)
    link = site / "splat" / splat_file.name
    if not link.exists():
        link.symlink_to(splat_file.resolve())
    (site / "index.html").write_text(PAGE, encoding="utf-8")
    (site / "spec.json").write_text(json.dumps({
        "splat": splat_file.name, "width": width, "height": height, "poses": poses,
        "transform": {"position": list(transform.get("position") or [0, 0, 0]),
                      "quaternion": quaternion(transform.get("rotation")),
                      "scale": float(transform.get("scale") or 1.0),
                      "centre": bool(transform.get("centre"))}}), encoding="utf-8")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            # WebGL2 in software (SwiftShader): no GPU needed, slower.
            browser = playwright.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                                       "--ignore-gpu-blocklist"])
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/index.html")
            try:
                page.wait_for_function("window.ready === true", timeout=120_000)
            except Exception as error:
                raise ValidationError("The splat did not load in the browser", detail="; ".join(errors)[-400:]) from error
            import base64
            import time

            loaded = time.monotonic()
            for index in range(len(poses)):
                data = page.evaluate(f"window.frame({index})")
                (output / f"f_{index + 1:04d}.png").write_bytes(base64.b64decode(data.split(",", 1)[1]))
            browser.close()
    finally:
        server.shutdown()
        shutil.rmtree(site, ignore_errors=True)
    return str(output / "f_%04d.png")


def location_splat(root: Path, location_id: str) -> tuple[Path, dict[str, Any]] | None:
    """A location's splat and its transform from the plan, if it declares one (`splat:` in location.yaml)."""

    from .locations import FILE, _read, load_locations

    location = load_locations(root).get(str(location_id).strip().upper())
    if location is None:
        return None
    folder = root / location["directory"]
    raw = _read(folder / FILE).get("splat")
    if not raw:
        return None
    declared = raw if isinstance(raw, dict) else {"file": raw}
    path = (folder / str(declared.get("file") or "")).resolve()
    if not path.is_file():
        raise ValidationError(f"{location['id']}'s splat {declared.get('file')!r} is not there")
    # The plan's metres into the splat: where the plan's origin sits in it, how it is turned and scaled.
    transform = {"position": declared.get("position") or [0, 0, 0], "rotation": declared.get("rotation") or [0, 0, 0],
                 "scale": declared.get("scale") or 1.0}
    return path, transform


def plate(root: Path, scene: dict[str, Any], shot: dict[str, Any], output: Path, *, frames: int = 24,
          width: int = 640, height: int = 360, run=None) -> dict[str, Any]:
    """The shot's camera move through the location's splat: a moving plate and its first frame."""

    import subprocess

    found = location_splat(root, scene.get("location") or "") if scene.get("location") else None
    if found is None:
        raise ValidationError(f"{scene.get('id')} is not set in a location with a splat (location.yaml: splat: {{file, ...}})")
    splat_file, transform = found
    frames_dir = output.with_suffix("")
    frames_dir.mkdir(parents=True, exist_ok=True)
    pattern = render(splat_file, shot_poses(scene, shot, frames), frames_dir, width=width, height=height,
                     transform=transform)
    ffmpeg = shutil.which("ffmpeg")
    fps = frames / max(0.1, float(shot.get("duration_seconds") or 1.0))
    (run or (lambda command: subprocess.run(command, check=True, capture_output=True)))(
        [ffmpeg, "-v", "error", "-y", "-framerate", f"{fps:.3f}", "-i", pattern, "-vf", "format=yuv420p",
         "-c:v", "libx264", "-crf", "18", str(output)])
    still = output.with_suffix(".png")
    shutil.copyfile(frames_dir / "f_0001.png", still)
    return {"video": str(output), "still": str(still), "frames": frames, "splat": str(splat_file)}
