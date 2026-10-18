"""A sequence's storyboard in time: each shot's latest drawing, held for its breakdown duration.

The director reviews a sequence, and a storyboard is judged in time as much as
in frames (Demo 01, 2026-10-18). This needs no blockout, no model and no paid
work: the drawings in the canonical sequence order, each with a gentle push-in
and a small scene/shot label, cut together with FFmpeg. Every run is a new
numbered file beside the earlier ones -- an animatic is never overwritten.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .errors import PersistenceError, ValidationError
from .project import load_production
from .storyboard import load_storyboard

WIDTH, HEIGHT, FPS = 1280, 720, 24
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
#: A shot with no declared duration is held this long, and says so in the report.
DEFAULT_SECONDS = 3.0


def plan(root: Path, sequence: str) -> list[dict[str, Any]]:
    """Each shot of the sequence, in order, with its latest drawing and its duration."""

    from .production_context import work_structure

    root = Path(root).expanduser().resolve()
    production = load_production(root)
    scope = next((item for item in work_structure(production, sequence=sequence)["sequences"]
                  if item["id"] == sequence), None)
    if scope is None:
        raise ValidationError(f"No canonical sequence {sequence!r}")
    latest: dict[tuple[str, str], dict] = {}
    for board in load_storyboard(root, production=production)["candidates"]:
        key = (board["scene"], board["shot"])
        if key not in latest or (board.get("version") or 0) >= (latest[key].get("version") or 0):
            latest[key] = board
    scenes = {item["id"]: item for item in production["scenes"]}
    shots = []
    for scene_id in scope["scene_ids"]:
        for shot in scenes[scene_id]["shots"]:
            board = latest.get((scene_id, shot["id"]))
            seconds = float(shot.get("duration_seconds") or 0)
            shots.append({"scene": scene_id, "scene_title": scenes[scene_id].get("title", ""), "shot": shot["id"],
                          "seconds": seconds or DEFAULT_SECONDS, "declared": bool(seconds),
                          "board": board["id"] if board else None, "version": board.get("version") if board else None,
                          "image": str(root / board["image"]["path"]) if board else None})
    return shots


def _clip(shot: dict[str, Any], index: int, folder: Path, ffmpeg: str) -> Path:
    out = folder / f"{index:03d}.mp4"
    frames = max(int(round(shot["seconds"] * FPS)), 1)
    label = f"{shot['scene']} {shot['shot']}" + (f"  v{shot['version']}" if shot.get("version") else "")
    fit = (f"scale={WIDTH * 2}:{HEIGHT * 2}:force_original_aspect_ratio=decrease,"
           f"pad={WIDTH * 2}:{HEIGHT * 2}:(ow-iw)/2:(oh-ih)/2:color=0x101010,setsar=1")
    push = (f"zoompan=z='1+0.04*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}")
    text = ""
    if FONT.is_file():
        text = (f",drawtext=fontfile={FONT}:text='{label}':x=24:y=h-44:fontsize=22:"
                "fontcolor=white@0.85:box=1:boxcolor=black@0.45:boxborderw=8")
    if shot["image"]:
        command = [ffmpeg, "-y", "-loglevel", "error", "-loop", "1", "-i", shot["image"],
                   "-vf", fit + "," + push + text, "-frames:v", str(frames), "-pix_fmt", "yuv420p",
                   "-c:v", "libx264", "-preset", "veryfast", "-r", str(FPS), str(out)]
    else:  # a missing drawing is shown as missing, never skipped
        command = [ffmpeg, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                   f"color=c=0x202020:s={WIDTH}x{HEIGHT}:r={FPS}", "-frames:v", str(frames),
                   "-vf", text.lstrip(",").replace(label, label + "  -- no drawing yet") if text else "null",
                   "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", str(out)]
    subprocess.run(command, check=True, capture_output=True)
    return out


def render(root: Path, sequence: str) -> dict[str, Any]:
    """Render the sequence's storyboard animatic as a new numbered file under renders/animatics/."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PersistenceError("FFmpeg is needed for the storyboard animatic (toast doctor)")
    root = Path(root).expanduser().resolve()
    shots = plan(root, sequence)
    folder = root / "renders" / "animatics"
    folder.mkdir(parents=True, exist_ok=True)
    number = 1 + max((int(path.stem.rsplit("-v", 1)[1]) for path in folder.glob(f"{sequence}-storyboard-v*.mp4")
                      if path.stem.rsplit("-v", 1)[1].isdigit()), default=0)
    target = folder / f"{sequence}-storyboard-v{number}.mp4"
    with tempfile.TemporaryDirectory() as work:
        work_dir = Path(work)
        clips = [_clip(shot, index, work_dir, ffmpeg) for index, shot in enumerate(shots)]
        listing = work_dir / "list.txt"
        listing.write_text("".join(f"file '{clip}'\n" for clip in clips), encoding="utf-8")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(target)], check=True, capture_output=True)
    return {"sequence": sequence, "path": str(target.relative_to(root)), "version": number,
            "seconds": round(sum(shot["seconds"] for shot in shots), 2), "shots": len(shots),
            "missing": [f"{shot['scene']} {shot['shot']}" for shot in shots if not shot["image"]],
            "undeclared_durations": [f"{shot['scene']} {shot['shot']}" for shot in shots if not shot["declared"]]}


def _frame(production: dict[str, Any], path: Path) -> dict[str, Any]:
    """A picture's size and whether it fits the film's frame, shown beside it so nobody approves blind."""

    from .workflows import _frame_problem

    try:
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
    except OSError:
        return {}
    return {"size": f"{width}x{height}", "ratio": round(width / height, 2),
            "frame_ok": not _frame_problem(production, path)}


def sequence_view(root: Path, sequence: str = "") -> dict[str, Any]:
    """What the storyboard page shows of a sequence: its shots in order, as a contact sheet, and its animatics."""

    root = Path(root).expanduser().resolve()
    production = load_production(root)
    sequences = [{"id": item["id"], "label": item.get("label") or item["id"]} for item in production.get("sequences") or []]
    chosen = sequence or (sequences[0]["id"] if sequences else "")
    if not chosen:
        return {"sequences": [], "sequence": "", "shots": [], "animatics": []}
    shots = plan(root, chosen)
    from .project import scene_directory
    from .state import load_scene_state
    from .workflows import phase
    scenes = {item["id"]: item for item in production["scenes"]}
    phases = {}
    masters: dict[tuple[str, str], dict] = {}
    for scene_id in dict.fromkeys(shot["scene"] for shot in shots):
        scene_state = load_scene_state(scene_directory(root, scene_id), scene_id)
        gates = scene_state.gates
        cancelled = {run_id for run_id, run in scene_state.workflows.items() if run.get("state") == "cancelled"}
        # The latest master-picture question per shot: waiting, or what was decided. A question closed
        # because its run was cancelled was never answered by anyone, so it is not shown as a verdict.
        for gate_id, gate in sorted(gates.items(), key=lambda item: item[1].get("requested_at", "")):
            if gate.get("kind") == "approve_picture" and gate.get("state") != "withdrawn" and not (
                    gate.get("workflow") in cancelled and gate.get("state") == "rejected"):
                masters[(scene_id, str(gate.get("subject", "")))] = {
                    "gate": gate_id, "state": gate.get("state", ""), "revision_scene": scene_id,
                    "candidates": [{"path": path, "url": "/media/" + path, **_frame(production, root / path)}
                                   for path in gate.get("candidates") or []],
                    "chosen": gate.get("chosen", ""), "rationale": gate.get("rationale", ""),
                    "decided_by": (gate.get("decided_by") or {}).get("kind", ""),
                    "findings": list(gate.get("findings") or [])}
        # Where no question is open, what the latest masters run says of the shot's picture: being made,
        # or refused -- a failure is shown, never left as an empty slot (the director, Demo 01).
        runs = sorted((run for run in scene_state.workflows.values() if run.get("template") == "masters"),
                      key=lambda run: run.get("created_at", ""))
        for run in runs:
            for step in run["steps"]:
                if step["kind"] != "picture":
                    continue
                key = (scene_id, step["shot"])
                current = masters.get(key)
                if current and current["state"] in ("waiting", "approved"):
                    continue
                if step["state"] == "failed":
                    masters[key] = {"gate": "", "state": "failed", "candidates": [], "chosen": "",
                                    "rationale": step.get("note", ""), "findings": [], "run": run["id"]}
                elif step["state"] in ("pending", "running") and run.get("state") not in ("failed", "cancelled"):
                    masters[key] = {"gate": "", "state": "making", "candidates": (current or {}).get("candidates", []),
                                    "chosen": "", "rationale": step.get("note", ""), "findings": [], "run": run["id"],
                                    "decided_by": "system" if (step.get("feedback") or {}).get("reasons") == ["frame"] else ""}
        found = phase(root, scenes[scene_id], gates)
        phases[scene_id] = {"phase": found["phase"], "changed_since": found.get("changed_since", False),
                            "since": found.get("since", "")}
    for shot in shots:
        shot["master"] = masters.get((shot["scene"], shot["shot"]))
        shot["image_url"] = ("/media/" + str(Path(shot["image"]).relative_to(root))) if shot["image"] else ""
        shot.pop("image", None)
    folder = root / "renders" / "animatics"
    animatics = []
    for path in folder.glob(f"{chosen}-storyboard-v*.mp4") if folder.is_dir() else []:
        number = path.stem.rsplit("-v", 1)[1]
        if number.isdigit():
            animatics.append({"version": int(number), "url": "/media/" + str(path.relative_to(root)),
                              "made_at": path.stat().st_mtime})
    animatics.sort(key=lambda item: item["version"], reverse=True)
    return {"sequences": sequences, "sequence": chosen, "shots": shots, "animatics": animatics, "phases": phases,
            "seconds": round(sum(shot["seconds"] for shot in shots), 2)}
