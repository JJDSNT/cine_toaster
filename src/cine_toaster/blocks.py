"""Generation blocks: several shots made in one generation, sliced back into takes (CT-0037).

A video model can render a run of consecutive shots in one generation, cutting
between them itself. That keeps light, voices and continuity across the cuts,
but the model cuts at its own rhythm: in SINGULAR 1-02A, cuts asked for at
frames 144 and 264 came out at 91, 190 and 283. Slicing the clip at the
requested times puts every cut in the wrong place.

So the cuts are *found*: the clip's real cuts are detected, and each stretch
between them is given to the shot whose reference picture it most resembles,
in shot order (a shot may return, as in shot/reverse-shot, so identity alone
cannot decide). When that reading does not add up, the requested cuts are used
and the take says so. Each slice becomes a take of its shot, with where it came
from recorded beside it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .takes import MEDIA_SUFFIXES, shot_key

SIGNATURE = (32, 18)
SCENE_THRESHOLD = 0.25
#: Frames after a cut before the picture is compared: the change has settled.
SETTLE_FRAMES = 4
#: A generation opens on its still first frame and eases into motion; a
#: "cut" found in that opening is the model starting, not a shot change
#: (SINGULAR 1-03 b5: a false cut at frame 7).
OPENING_SECONDS = 0.35


@dataclass(slots=True)
class Block:
    id: str
    shots: list[str]
    durations: list[float]
    clip: str = ""
    contiguous: bool = True

    def public_dict(self) -> dict[str, Any]:
        return {"id": self.id, "shots": self.shots, "durations": self.durations, "clip": self.clip,
                "duration": round(sum(self.durations), 3), "contiguous": self.contiguous}


def scene_blocks(scene: dict[str, Any], work: Path | None, root: Path) -> list[Block]:
    """The scene's blocks in shot order, each with its clip when one exists."""

    order = [shot for shot in scene["shots"] if not shot.get("out_of_cut")]
    blocks: dict[str, Block] = {}
    positions: dict[str, list[int]] = {}
    for index, shot in enumerate(order):
        block_id = str(shot.get("block") or "").strip()
        if not block_id:
            continue
        block = blocks.setdefault(block_id, Block(block_id, [], []))
        block.shots.append(shot["id"])
        # A block's cuts are asked for by generation length, not edit length.
        block.durations.append(float(shot.get("generated_seconds") or shot.get("duration_seconds") or 0.0))
        positions.setdefault(block_id, []).append(index)
    for block_id, block in blocks.items():
        where = positions[block_id]
        block.contiguous = where == list(range(where[0], where[0] + len(where)))
        if work is not None:
            for suffix in MEDIA_SUFFIXES:
                candidate = work / f"b{block_id}{suffix}"
                if candidate.is_file():
                    block.clip = candidate.relative_to(root).as_posix()
                    break
    return list(blocks.values())


def _picture_stems(value: str) -> list[str]:
    """`p<n>` for a shot or master named n: `p08`/`p8` for 8, `pmA` for mA."""

    stems = [f"p{value}"]
    key = shot_key(value)
    match = re.fullmatch(r"(\d+)([a-z]*)", key)
    if match:
        stems += [f"p{int(match[1]):02d}{match[2]}", f"p{int(match[1])}{match[2]}"]
    return list(dict.fromkeys(stems))


def reference_picture(work: Path, root: Path, scene: dict[str, Any], shot: dict[str, Any]) -> Path | None:
    """The picture a shot's slice should look like.

    The shot's still if it has one, then its master image in the work
    directory (`p08.png`, beside its clip `c08.mp4`), then the image of the
    shot or master it is made from (its `from` lineage, e.g. `pmA.png`).
    """

    if shot.get("still"):
        path = root / shot["still"]
        if path.is_file():
            return path
    names = [str(shot.get("number") or "")]
    for item in shot.get("from") or []:
        if isinstance(item, dict) and item.get("ref"):
            names.append(str(item["ref"]))
    for name in filter(None, names):
        for stem in _picture_stems(name):
            for suffix in (".png", ".jpg", ".jpeg", ".webp"):
                if (work / f"{stem}{suffix}").is_file():
                    return work / f"{stem}{suffix}"
    return None


# --- reading the clip --------------------------------------------------------


def _ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("FFmpeg is needed to slice a block")
    return path


def clip_info(path: Path) -> tuple[float, float]:
    """(duration in seconds, frames per second)."""

    ffprobe = shutil.which("ffprobe") or "ffprobe"
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate:format=duration", "-of", "default=nw=1", str(path)],
                         capture_output=True, text=True, timeout=60).stdout
    rate = re.search(r"r_frame_rate=(\d+)/(\d+)", out)
    duration = re.search(r"duration=([\d.]+)", out)
    fps = int(rate[1]) / int(rate[2]) if rate and int(rate[2]) else 24.0
    return (float(duration[1]) if duration else 0.0), fps


def detected_cuts(path: Path, fps: float, threshold: float = SCENE_THRESHOLD) -> list[int]:
    """Frames where the clip's picture actually changes shot."""

    completed = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", str(path), "-vf", f"select='gt(scene,{threshold})',showinfo",
         "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    return [round(float(value) * fps) for value in re.findall(r"pts_time:([0-9.]+)", completed.stderr)]


def _raw_signature(command: list[str]) -> list[int]:
    completed = subprocess.run(command + ["-vf", f"scale={SIGNATURE[0]}:{SIGNATURE[1]},format=rgb24",
                                          "-frames:v", "1", "-f", "rawvideo", "-"],
                               capture_output=True, timeout=60)
    return list(completed.stdout)


def picture_signature(path: Path) -> list[int]:
    return _raw_signature([_ffmpeg(), "-v", "error", "-i", str(path)])


def frame_signature(clip: Path, frame: int, fps: float) -> list[int]:
    return _raw_signature([_ffmpeg(), "-v", "error", "-ss", f"{frame / fps:.4f}", "-i", str(clip)])


def distance(a: list[int], b: list[int]) -> float:
    if not a or not b or len(a) != len(b):
        return float("inf")
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


# --- deciding the cuts ---------------------------------------------------------


def requested_cuts(durations: list[float], fps: float) -> list[int]:
    """Where each shot was asked to start, in frames (multiples of 8, as LTX needs)."""

    starts, clock = [], 0.0
    for seconds in durations:
        starts.append(int(round(clock * fps / 8)) * 8)
        clock += seconds
    return starts


def assign(costs: list[list[float]], shots: int) -> list[int] | None:
    """Give each stretch a shot, in order, every shot at least one stretch.

    ``costs[i][j]`` is how unlike stretch *i* is to shot *j*'s picture. The
    assignment is monotonic -- stretches follow the shot order -- and the
    cheapest such assignment is returned, or None when none exists.
    """

    stretches = len(costs)
    if stretches < shots:
        return None
    infinity = float("inf")
    best = [[infinity] * shots for _ in range(stretches)]
    came = [[-1] * shots for _ in range(stretches)]
    best[0][0] = costs[0][0]
    for i in range(1, stretches):
        for j in range(shots):
            options = [(best[i - 1][j], j)] + ([(best[i - 1][j - 1], j - 1)] if j else [])
            value, origin = min(options)
            if value < infinity:
                best[i][j], came[i][j] = value + costs[i][j], origin
    if best[-1][-1] == infinity:
        return None
    owners, j = [0] * stretches, shots - 1
    for i in range(stretches - 1, 0, -1):
        owners[i], j = j, came[i][j]
    owners[0] = j
    return owners


@dataclass(slots=True)
class Slicing:
    starts: list[int]
    method: str
    detected: list[int] = field(default_factory=list)
    requested: list[int] = field(default_factory=list)
    note: str = ""


def decide(clip: Path, durations: list[float], references: list[Path | None], fps: float) -> Slicing:
    """Where each shot of the block starts in the clip, and how that was decided."""

    requested = requested_cuts(durations, fps)
    found = [frame for frame in detected_cuts(clip, fps) if frame > max(SETTLE_FRAMES, OPENING_SECONDS * fps)]
    shots = len(durations)
    if shots == 1:
        return Slicing([0], "single", found, requested)
    bounds = [0] + found
    if len(bounds) < shots:
        return Slicing(requested, "requested", found, requested,
                       f"{len(bounds)} stretch(es) found for {shots} shots; cut where they were asked for")
    if all(references):
        pictures = [picture_signature(path) for path in references]  # type: ignore[arg-type]
        costs = [[distance(frame_signature(clip, start + SETTLE_FRAMES, fps), picture) for picture in pictures]
                 for start in bounds]
        owners = assign(costs, shots)
        if owners is not None:
            starts = [start for index, (start, owner) in enumerate(zip(bounds, owners))
                      if index == 0 or owner != owners[index - 1]]
            return Slicing(starts, "content", found, requested)
        return Slicing(requested, "requested", found, requested, "no ordered match with the reference pictures")
    if len(bounds) == shots:
        return Slicing(bounds, "detected", found, requested,
                       "no reference pictures; the model's own cuts were used, one per shot")
    return Slicing(requested, "requested", found, requested,
                   f"{len(bounds)} stretches for {shots} shots and no reference pictures to tell them apart")
